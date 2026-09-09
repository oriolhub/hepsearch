"""Fill the papers corpus from the INSPIRE-HEP literature API.

Idempotent and interruption-safe: identifies papers by `inspire_id`, writes only
papers whose content genuinely changed, and a re-run after an interruption simply
starts over from the first page — the diff-then-write path makes the already-landed
pages cheap.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from apps.ingestion.client import InspireClient
from apps.ingestion.writer import apply_batch, diff_batch, load_existing
from apps.papers.models import Paper

DEFAULT_QUERY = "higgs boson"
DEFAULT_LIMIT = 5000


class Command(BaseCommand):
    help = "Ingest a bounded slice of INSPIRE literature records into the papers corpus."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--query",
            default=DEFAULT_QUERY,
            help=f"INSPIRE query string (default: {DEFAULT_QUERY!r})",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=DEFAULT_LIMIT,
            help=f"Number of usable papers to land (default: {DEFAULT_LIMIT})",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be written without writing anything",
        )

    def handle(self, *_args: Any, **options: Any) -> None:
        query: str = options["query"]
        limit: int = options["limit"]
        dry_run: bool = options["dry_run"]
        batch_size: int = settings.INGEST_BATCH_SIZE

        fetched = skipped = created = updated = unchanged = 0
        batch: list[Paper] = []

        with InspireClient() as client:
            for result in client.iter_papers(query, limit):
                fetched += 1
                if result is None:
                    skipped += 1
                    continue
                batch.append(result)
                if len(batch) >= batch_size:
                    created, updated, unchanged = self._flush(
                        batch, dry_run=dry_run, totals=(created, updated, unchanged)
                    )
                    batch = []
            if batch:
                created, updated, unchanged = self._flush(
                    batch, dry_run=dry_run, totals=(created, updated, unchanged)
                )

        landed = created + updated + unchanged
        prefix = "[dry run] " if dry_run else ""
        self.stdout.write(
            f"{prefix}fetched={fetched} skipped={skipped} created={created} "
            f"updated={updated} unchanged={unchanged}"
        )
        if landed < limit:
            self.stdout.write(
                self.style.WARNING(f"landed {landed} paper(s), fewer than the requested {limit}")
            )

    def _flush(
        self,
        batch: list[Paper],
        *,
        dry_run: bool,
        totals: tuple[int, int, int],
    ) -> tuple[int, int, int]:
        """Diff one batch against the database, write it unless this is a dry run, and
        return the running created/updated/unchanged totals.
        """
        created_total, updated_total, unchanged_total = totals
        existing = load_existing([paper.inspire_id for paper in batch])
        result = diff_batch(batch, existing)
        if not dry_run:
            apply_batch(result)
        created_total += len(result.created)
        updated_total += len(result.updated)
        unchanged_total += result.unchanged
        prefix = "[dry run] " if dry_run else ""
        self.stdout.write(
            f"{prefix}batch: +{len(result.created)} created, {len(result.updated)} "
            f"updated, {result.unchanged} unchanged"
        )
        return created_total, updated_total, unchanged_total
