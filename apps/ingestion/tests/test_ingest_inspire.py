"""Tests for the `ingest_inspire` management command.

The network is never touched: `InspireClient` is replaced at the module seam the
command imports it through, with a stand-in whose `iter_papers` yields canned
`Paper` objects (and `None` for unusable records), exactly matching the client's
real contract.
"""

from __future__ import annotations

import ast
import io
import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from django.core.management import call_command

from apps.ingestion.client import InspireClient
from apps.ingestion.management.commands import ingest_inspire
from apps.papers.models import Paper

FIXTURE = Path(__file__).parent / "fixtures" / "inspire_literature.json"


class FakeClient:
    """Stands in for `InspireClient`: same `iter_papers` contract, no network."""

    def __init__(self, results: list[Paper | None]) -> None:
        self._results = results
        self.queries: list[tuple[str, int]] = []

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def iter_papers(self, query: str, limit: int) -> Iterator[Paper | None]:
        self.queries.append((query, limit))
        yielded = 0
        for result in self._results:
            if yielded >= limit:
                return
            yield result
            if result is not None:
                yielded += 1


def make_paper(inspire_id, **overrides):
    defaults = {
        "inspire_id": inspire_id,
        "title": f"Title {inspire_id}",
        "abstract": f"Abstract {inspire_id}",
        "authors": ["A. Author"],
        "categories": ["hep-ph"],
        "arxiv_id": "1234.5678",
        "doi": "10.1/x",
        "journal": "A Journal",
        "earliest_date": "2020-01-01",
        "citation_count": 5,
    }
    return Paper(**(defaults | overrides))


@pytest.fixture
def patch_client(monkeypatch):
    """Replaces `InspireClient` with a factory returning the given fake client."""

    def _patch(fake: FakeClient):
        monkeypatch.setattr(ingest_inspire, "InspireClient", lambda *a, **kw: fake)
        return fake

    return _patch


def run_command(**options):
    stdout = io.StringIO()
    call_command("ingest_inspire", stdout=stdout, **options)
    return stdout.getvalue()


@pytest.mark.django_db
def test_a_first_run_stores_papers_and_counts_skips(patch_client):
    patch_client(FakeClient([make_paper(1), None, make_paper(2), None]))

    output = run_command(limit=2)

    assert Paper.objects.count() == 2
    assert all(paper.abstract for paper in Paper.objects.all())
    assert "fetched=3" in output
    assert "skipped=1" in output
    assert "created=2" in output


@pytest.mark.django_db
def test_running_twice_is_idempotent(patch_client):
    patch_client(FakeClient([make_paper(1), make_paper(2)]))
    run_command(limit=2)

    patch_client(FakeClient([make_paper(1), make_paper(2)]))
    second_output = run_command(limit=2)

    assert Paper.objects.count() == 2
    assert Paper.objects.filter(inspire_id=1).count() == 1
    assert Paper.objects.filter(inspire_id=2).count() == 1
    assert "created=0" in second_output
    assert "unchanged=2" in second_output


@pytest.mark.django_db
def test_a_changed_record_updates_and_moves_the_timestamp(patch_client):
    patch_client(FakeClient([make_paper(1, citation_count=5), make_paper(2)]))
    run_command(limit=2)
    original_updated_1 = Paper.objects.get(inspire_id=1).updated_at
    original_updated_2 = Paper.objects.get(inspire_id=2).updated_at

    patch_client(FakeClient([make_paper(1, citation_count=99), make_paper(2)]))
    output = run_command(limit=2)

    changed = Paper.objects.get(inspire_id=1)
    unchanged = Paper.objects.get(inspire_id=2)
    assert changed.citation_count == 99
    assert changed.updated_at > original_updated_1
    assert unchanged.updated_at == original_updated_2
    assert "updated=1" in output
    assert "unchanged=1" in output


@pytest.mark.django_db
def test_created_at_survives_an_update(patch_client):
    patch_client(FakeClient([make_paper(1, citation_count=5)]))
    run_command(limit=1)
    original_created_at = Paper.objects.get(inspire_id=1).created_at

    patch_client(FakeClient([make_paper(1, citation_count=99)]))
    run_command(limit=1)

    assert Paper.objects.get(inspire_id=1).created_at == original_created_at


@pytest.mark.django_db
def test_reingest_preserves_embedding_and_source_change_invalidates_it(patch_client):
    patch_client(FakeClient([make_paper(1)]))
    run_command(limit=1)
    paper = Paper.objects.get(inspire_id=1)
    paper.embedding = [0.0] * 384
    paper.embedding_model = "fake-bow-384"
    paper.embedded_at = paper.created_at
    paper.save(update_fields=["embedding", "embedding_model", "embedded_at"])

    patch_client(FakeClient([make_paper(1)]))
    run_command(limit=1)
    paper.refresh_from_db()
    assert paper.embedding == [0.0] * 384
    assert paper.embedding_model == "fake-bow-384"
    assert paper.embedded_at == paper.created_at

    patch_client(FakeClient([make_paper(1, abstract="A revised abstract")]))
    run_command(limit=1)
    paper.refresh_from_db()
    assert paper.embedding is None
    assert paper.embedding_model == ""
    assert paper.embedded_at is None


@pytest.mark.django_db
def test_dry_run_stores_and_modifies_nothing(patch_client):
    patch_client(FakeClient([make_paper(1)]))
    run_command(limit=1)

    patch_client(FakeClient([make_paper(1, citation_count=999), make_paper(2)]))
    output = run_command(limit=2, dry_run=True)

    assert Paper.objects.count() == 1
    assert Paper.objects.get(inspire_id=1).citation_count == 5
    assert "created=1" in output
    assert "updated=1" in output


@pytest.mark.django_db
def test_a_short_corpus_is_reported_and_exits_cleanly(patch_client):
    patch_client(FakeClient([make_paper(1)]))

    output = run_command(limit=10)

    assert Paper.objects.count() == 1
    assert "fewer than the requested 10" in output


@pytest.mark.django_db
def test_progress_is_reported_per_batch(settings, patch_client):
    settings.INGEST_BATCH_SIZE = 1
    patch_client(FakeClient([make_paper(1), make_paper(2), make_paper(3)]))

    output = run_command(limit=3)

    assert output.count("batch:") == 3
    assert "fetched=3" in output
    assert "created=3" in output


@pytest.mark.django_db
def test_a_run_against_the_real_client_and_fixture_lands_the_usable_records(monkeypatch):
    """End-to-end through the unmodified `InspireClient` pipeline — `fetch_page`,
    `iter_records` and `normalize` all run for real — with only the HTTP transport
    replaced by the committed fixture. The FakeClient-based tests above cover the
    command's own logic in isolation; this one proves the wiring to the real client
    still works.
    """
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    def build_real_client(*_args, **_kwargs) -> InspireClient:
        return InspireClient(
            client=httpx.Client(transport=httpx.MockTransport(handler)), throttle=0
        )

    monkeypatch.setattr(ingest_inspire, "InspireClient", build_real_client)

    output = run_command(limit=9)

    # The fixture carries 10 records, one of which has no abstract.
    assert Paper.objects.count() == 9
    assert all(paper.abstract for paper in Paper.objects.all())
    assert "fetched=10" in output
    assert "skipped=1" in output
    assert "created=9" in output


def test_ingestion_command_does_not_import_search():
    tree = ast.parse(
        Path(ingest_inspire.__file__).read_text(encoding="utf-8"),
        filename=ingest_inspire.__file__,
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("apps.search")
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("apps.search")


def test_ingestion_writer_does_not_import_embedding():
    writer_path = Path(__file__).parents[1] / "writer.py"
    tree = ast.parse(writer_path.read_text(encoding="utf-8"), filename=str(writer_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(not alias.name.startswith("apps.embedding") for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("apps.embedding")
