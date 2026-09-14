from __future__ import annotations

import io
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.embedding.fake import FakeEmbeddingProvider
from apps.papers.management.commands import embed_papers
from apps.papers.models import Paper


def make_paper(inspire_id: int, **overrides) -> Paper:
    return Paper(
        inspire_id=inspire_id,
        title=f"Title {inspire_id}",
        abstract=f"Abstract {inspire_id}",
        **overrides,
    )


def create_paper(inspire_id: int, **overrides) -> Paper:
    return Paper.objects.create(
        inspire_id=inspire_id,
        title=f"Title {inspire_id}",
        abstract=f"Abstract {inspire_id}",
        **overrides,
    )


def run_command(**options) -> str:
    stdout = io.StringIO()
    call_command("embed_papers", stdout=stdout, **options)
    return stdout.getvalue()


class InteractiveStdin(io.StringIO):
    """Stands in for a terminal, so the confirmation prompt is reachable under pytest."""

    def isatty(self) -> bool:
        return True


@pytest.fixture
def fake_provider(settings):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    return FakeEmbeddingProvider()


@pytest.mark.django_db
def test_embeds_every_paper_and_records_provenance(fake_provider):
    Paper.objects.bulk_create([make_paper(1), make_paper(2)])

    output = run_command(noinput=True)

    papers = list(Paper.objects.order_by("inspire_id"))
    assert all(paper.embedding is not None for paper in papers)
    assert all(len(paper.embedding) == 384 for paper in papers)
    assert all(paper.embedding_model == fake_provider.model_name for paper in papers)
    assert all(paper.embedded_at is not None for paper in papers)
    assert "Embedded 2 paper(s); skipped 0 already current." in output


@pytest.mark.django_db
def test_rerun_is_a_noop(fake_provider):
    create_paper(1)
    run_command(noinput=True)
    before = Paper.objects.get(inspire_id=1)

    output = run_command(noinput=True)
    after = Paper.objects.get(inspire_id=1)

    assert after.embedding == before.embedding
    assert after.embedded_at == before.embedded_at
    assert "No papers needed embedding." in output


@pytest.mark.django_db
def test_model_change_reembeds_and_reports_stale(fake_provider):
    paper = create_paper(1)
    paper.embedding = fake_provider.embed([paper.embedding_text])[0]
    paper.embedding_model = "old-model"
    paper.embedded_at = timezone.now() - timedelta(days=1)
    paper.save(update_fields=["embedding", "embedding_model", "embedded_at"])

    output = run_command(noinput=True)

    paper.refresh_from_db()
    assert paper.embedding_model == fake_provider.model_name
    assert "Detected 1 stale embeddings due to model change" in output


@pytest.mark.django_db
def test_force_recomputes_current_embeddings(fake_provider):
    paper = create_paper(1)
    run_command(noinput=True)
    before = Paper.objects.get(pk=paper.pk).embedded_at

    output = run_command(force=True, noinput=True)

    after = Paper.objects.get(pk=paper.pk)
    assert after.embedded_at > before
    assert "Embedded 1 paper(s)" in output


@pytest.mark.django_db
def test_embedding_does_not_change_updated_at(fake_provider):
    paper = create_paper(1)
    original_updated_at = paper.updated_at

    run_command(noinput=True)

    paper.refresh_from_db()
    assert paper.updated_at == original_updated_at
    assert paper.embedded_at is not None


@pytest.mark.django_db
def test_requerying_head_does_not_skip_rows(fake_provider):
    Paper.objects.bulk_create([make_paper(index) for index in range(1, 6)])

    run_command(batch_size=2, noinput=True)

    assert Paper.objects.filter(embedding__isnull=True).count() == 0


@pytest.mark.django_db
def test_stale_prompt_can_cancel_without_writing(fake_provider, monkeypatch):
    paper = create_paper(1)
    paper.embedding = fake_provider.embed([paper.embedding_text])[0]
    paper.embedding_model = "old-model"
    paper.embedded_at = timezone.now()
    paper.save(update_fields=["embedding", "embedding_model", "embedded_at"])
    before = Paper.objects.get(pk=paper.pk)

    monkeypatch.setattr("sys.stdin", InteractiveStdin())
    monkeypatch.setattr("builtins.input", lambda: "no")
    with pytest.raises(CommandError, match="Cancelled"):
        run_command()

    after = Paper.objects.get(pk=paper.pk)
    assert after.embedding == before.embedding
    assert after.embedding_model == "old-model"


@pytest.mark.django_db
def test_non_interactive_run_without_noinput_refuses_to_guess(fake_provider, monkeypatch):
    """An unattended run that needs confirmation must fail loudly, not silently do nothing."""
    paper = create_paper(1)
    paper.embedding = fake_provider.embed([paper.embedding_text])[0]
    paper.embedding_model = "old-model"
    paper.embedded_at = timezone.now()
    paper.save(update_fields=["embedding", "embedding_model", "embedded_at"])

    monkeypatch.setattr("sys.stdin", io.StringIO())

    with pytest.raises(CommandError, match="stdin is not interactive"):
        run_command()

    paper.refresh_from_db()
    assert paper.embedding_model == "old-model"


@pytest.mark.django_db
def test_confirmation_prompt_at_end_of_file_fails_loudly(fake_provider, monkeypatch):
    """isatty() is unreliable (Windows calls nul a tty), so EOF must be refused too."""
    paper = create_paper(1)
    paper.embedding = fake_provider.embed([paper.embedding_text])[0]
    paper.embedding_model = "old-model"
    paper.embedded_at = timezone.now()
    paper.save(update_fields=["embedding", "embedding_model", "embedded_at"])

    def raise_eof():
        raise EOFError

    monkeypatch.setattr("sys.stdin", InteractiveStdin())
    monkeypatch.setattr("builtins.input", raise_eof)

    with pytest.raises(CommandError, match="end-of-file"):
        run_command()

    paper.refresh_from_db()
    assert paper.embedding_model == "old-model"


@pytest.mark.django_db
def test_force_walks_every_paper_across_several_batches(fake_provider):
    """--force must terminate and cover every row; its filter never shrinks as it works."""
    Paper.objects.bulk_create([make_paper(index) for index in range(1, 6)])
    run_command(noinput=True)

    output = run_command(force=True, batch_size=2, noinput=True)

    assert Paper.objects.filter(embedding__isnull=True).count() == 0
    assert Paper.objects.filter(embedding_model=fake_provider.model_name).count() == 5
    assert "Embedded 5 paper(s)" in output


class OneDimensionalProvider:
    dimension = 1
    model_name = "one-dimensional"

    def embed(self, texts):
        return [[1.0] for _ in texts]


class BrokenProvider:
    dimension = 384
    model_name = "broken"

    def embed(self, texts):
        raise RuntimeError("model unavailable")


@pytest.mark.django_db
def test_dimension_mismatch_writes_nothing(monkeypatch):
    paper = create_paper(1)
    monkeypatch.setattr(embed_papers, "get_provider", lambda: OneDimensionalProvider())

    with pytest.raises(CommandError, match="does not match"):
        run_command(noinput=True)

    paper.refresh_from_db()
    assert paper.embedding is None


@pytest.mark.django_db
def test_provider_validation_failure_writes_nothing(monkeypatch):
    paper = create_paper(1)
    monkeypatch.setattr(embed_papers, "get_provider", lambda: BrokenProvider())

    with pytest.raises(CommandError, match="validation failed"):
        run_command(noinput=True)

    paper.refresh_from_db()
    assert paper.embedding is None


@pytest.mark.django_db
def test_column_dimension_mismatch_writes_nothing(monkeypatch, settings):
    paper = create_paper(1)
    settings.EMBEDDING_DIMENSION = 2
    monkeypatch.setattr(embed_papers, "get_provider", lambda: FakeEmbeddingProvider())

    with pytest.raises(CommandError, match="column dimension"):
        run_command(noinput=True)

    paper.refresh_from_db()
    assert paper.embedding is None


@pytest.mark.django_db
def test_unresolvable_provider_writes_nothing(monkeypatch):
    paper = create_paper(1)
    monkeypatch.setattr(
        embed_papers,
        "get_provider",
        lambda: (_ for _ in ()).throw(ImportError("missing provider")),
    )

    with pytest.raises(CommandError, match="Could not resolve"):
        run_command(noinput=True)

    paper.refresh_from_db()
    assert paper.embedding is None


class FailingProvider(FakeEmbeddingProvider):
    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        if self.calls == 4:
            raise RuntimeError("interrupted")
        return super().embed(texts)


@pytest.mark.django_db
def test_interrupted_run_preserves_completed_batches(monkeypatch, settings):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    Paper.objects.bulk_create([make_paper(index) for index in range(1, 6)])
    provider = FailingProvider()
    monkeypatch.setattr(embed_papers, "get_provider", lambda: provider)

    with pytest.raises(RuntimeError, match="interrupted"):
        run_command(batch_size=2, noinput=True)

    assert Paper.objects.filter(embedding__isnull=False).count() == 4

    monkeypatch.setattr(embed_papers, "get_provider", lambda: FakeEmbeddingProvider())
    run_command(batch_size=2, noinput=True)
    assert Paper.objects.filter(embedding__isnull=True).count() == 0
