from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from apps.embedding.registry import get_provider
from apps.papers.models import Paper

DEFAULT_BATCH_SIZE = 100


class Command(BaseCommand):
    help = "Generate and store embeddings for papers that need them."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=f"Number of papers per embedding batch (default: {DEFAULT_BATCH_SIZE})",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recompute embeddings even when the recorded model already matches",
        )
        parser.add_argument(
            "--noinput",
            action="store_true",
            help="Skip confirmation prompts for unattended runs",
        )

    def handle(self, *_args: Any, **options: Any) -> None:
        batch_size: int = options["batch_size"]
        force: bool = options["force"]
        noinput: bool = options["noinput"]
        if batch_size < 1:
            raise CommandError("--batch-size must be a positive integer")

        provider = self._resolve_provider()
        self._validate_dimensions(provider)
        self._validate_provider(provider)

        missing = Paper.objects.filter(embedding__isnull=True).count()
        stale = (
            Paper.objects.filter(
                embedding__isnull=False,
            )
            .exclude(embedding_model=provider.model_name)
            .count()
        )
        if missing:
            self.stdout.write(f"Detected {missing} papers without embeddings")
        if stale:
            self.stdout.write(f"Detected {stale} stale embeddings due to model change")

        needs_embedding = self._needs_embedding(provider.model_name, force)
        total = needs_embedding.count()
        if total == 0:
            self.stdout.write("No papers needed embedding.")
            return

        if (stale or force) and not noinput:
            action = "recompute all embeddings" if force else f"recompute {stale} stale embeddings"
            self._confirm(action)

        embedded = 0
        last_pk = 0
        while True:
            # Keyset, not re-query-the-head: under --force the predicate is every paper
            # and never shrinks, so only a cursor terminates the loop. It also keeps each
            # batch query O(1), and loads just the columns needed to build the text.
            batch = list(
                needs_embedding.filter(pk__gt=last_pk)
                .only("pk", "title", "abstract")
                .order_by("pk")[:batch_size]
            )
            if not batch:
                break
            vectors = provider.embed([paper.embedding_text for paper in batch])
            if len(vectors) != len(batch):
                raise CommandError(
                    f"provider returned {len(vectors)} vectors for {len(batch)} papers"
                )
            embedded += self._store_batch(batch, vectors, provider.model_name)
            last_pk = batch[-1].pk
            self.stdout.write(f"Embedded {embedded}/{total} papers")

        skipped = max(Paper.objects.count() - embedded, 0)
        self.stdout.write(f"Embedded {embedded} paper(s); skipped {skipped} already current.")

    def _confirm(self, action: str) -> None:
        if not sys.stdin.isatty():
            raise CommandError(
                f"This would {action}, but stdin is not interactive so the confirmation "
                "cannot be answered. Re-run with --noinput to confirm up front."
            )
        self.stdout.write(f"This will {action}. Type 'yes' to continue: ", ending="")
        try:
            answer = input()
        except EOFError:
            # isatty() is not wholly reliable (Windows reports the nul device as a tty),
            # so refuse on end-of-file too rather than crash on an unanswerable prompt.
            raise CommandError(
                f"This would {action}, but stdin reached end-of-file before the "
                "confirmation was answered. Re-run with --noinput to confirm up front."
            ) from None
        if answer.strip().lower() != "yes":
            raise CommandError("Cancelled.")

    @staticmethod
    def _resolve_provider():
        try:
            return get_provider()
        except (ImportError, AttributeError, TypeError, ValueError) as exc:
            raise CommandError(f"Could not resolve embedding provider: {exc}") from exc

    @staticmethod
    def _validate_dimensions(provider: Any) -> None:
        configured = settings.EMBEDDING_DIMENSION
        if provider.dimension != configured:
            raise CommandError(
                f"Provider dimension {provider.dimension} does not match "
                f"settings.EMBEDDING_DIMENSION {configured}"
            )

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT atttypmod
                FROM pg_attribute
                WHERE attrelid = %s::regclass
                  AND attname = %s
                  AND NOT attisdropped
                """,
                [Paper._meta.db_table, "embedding"],
            )
            row = cursor.fetchone()
        column_dimension = row[0] if row else -1
        if column_dimension != configured:
            raise CommandError(
                f"Embedding column dimension {column_dimension} does not match "
                f"settings.EMBEDDING_DIMENSION {configured}"
            )

    @staticmethod
    def _validate_provider(provider: Any) -> None:
        try:
            vectors = provider.embed(["provider validation probe"])
        except Exception as exc:
            raise CommandError(f"Embedding provider validation failed: {exc}") from exc
        if len(vectors) != 1 or len(vectors[0]) != provider.dimension:
            raise CommandError("Embedding provider validation returned an invalid vector")

    @staticmethod
    def _needs_embedding(model_name: str, force: bool):
        if force:
            return Paper.objects.all()
        return Paper.objects.filter(Q(embedding__isnull=True) | ~Q(embedding_model=model_name))

    @staticmethod
    def _store_batch(
        batch: Sequence[Paper],
        vectors: Sequence[Sequence[float]],
        model_name: str,
    ) -> int:
        computed_at = timezone.now()
        for paper, vector in zip(batch, vectors, strict=True):
            paper.embedding = list(vector)
            paper.embedding_model = model_name
            paper.embedded_at = computed_at
        with transaction.atomic():
            Paper.objects.bulk_update(batch, ["embedding", "embedding_model", "embedded_at"])
        return len(batch)
