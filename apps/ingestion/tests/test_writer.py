from django.utils import timezone

from apps.ingestion.writer import COMPARE_FIELDS, BatchResult, diff_batch
from apps.papers.models import Paper


def make_paper(inspire_id, **overrides):
    defaults = {
        "inspire_id": inspire_id,
        "title": "A title",
        "abstract": "An abstract",
        "authors": ["A. Author"],
        "categories": ["hep-ph"],
        "arxiv_id": "1234.5678",
        "doi": "10.1/x",
        "journal": "A Journal",
        "earliest_date": "2020-01-01",
        "citation_count": 5,
    }
    return Paper(**(defaults | overrides))


def test_a_new_paper_is_created():
    incoming = [make_paper(1)]

    result = diff_batch(incoming, existing_by_inspire_id={})

    assert result.created == incoming
    assert result.updated == []
    assert result.unchanged == 0


def test_an_identical_paper_is_unchanged():
    stored = make_paper(1)
    incoming = [make_paper(1)]

    result = diff_batch(incoming, existing_by_inspire_id={1: stored})

    assert result.created == []
    assert result.updated == []
    assert result.unchanged == 1


def test_a_paper_differing_only_in_citation_count_is_updated():
    stored = make_paper(1, citation_count=5)
    incoming = [make_paper(1, citation_count=42)]

    result = diff_batch(incoming, existing_by_inspire_id={1: stored})

    assert result.created == []
    assert len(result.updated) == 1
    assert result.updated[0] is stored
    assert stored.citation_count == 42
    assert result.unchanged == 0


def test_a_paper_differing_in_a_list_field_is_updated():
    stored = make_paper(1, authors=["A. Author"])
    incoming = [make_paper(1, authors=["A. Author", "B. Author"])]

    result = diff_batch(incoming, existing_by_inspire_id={1: stored})

    assert len(result.updated) == 1
    assert stored.authors == ["A. Author", "B. Author"]
    assert result.unchanged == 0


def test_updated_at_moves_only_for_a_changed_paper():
    stored = make_paper(1, citation_count=5)
    original_updated_at = stored.updated_at
    incoming = [make_paper(1, citation_count=42)]

    diff_batch(incoming, existing_by_inspire_id={1: stored})

    assert stored.updated_at != original_updated_at


def test_updated_at_does_not_move_for_an_unchanged_paper():
    stored = make_paper(1)
    original_updated_at = stored.updated_at

    diff_batch([make_paper(1)], existing_by_inspire_id={1: stored})

    assert stored.updated_at == original_updated_at


def test_created_at_is_not_touched_by_diffing():
    stored = make_paper(1, citation_count=5)
    original_created_at = stored.created_at
    incoming = [make_paper(1, citation_count=42)]

    diff_batch(incoming, existing_by_inspire_id={1: stored})

    assert stored.created_at == original_created_at


def test_compare_fields_excludes_identity_and_bookkeeping_columns():
    assert "id" not in COMPARE_FIELDS
    assert "inspire_id" not in COMPARE_FIELDS
    assert "created_at" not in COMPARE_FIELDS
    assert "updated_at" not in COMPARE_FIELDS


def test_compare_fields_includes_the_fields_ingestion_populates():
    assert set(COMPARE_FIELDS) == {
        "title",
        "abstract",
        "authors",
        "categories",
        "arxiv_id",
        "doi",
        "journal",
        "earliest_date",
        "citation_count",
    }


def test_embedding_fields_are_not_ingestion_owned():
    assert {"embedding", "embedding_model", "embedded_at"}.isdisjoint(COMPARE_FIELDS)


def test_changing_source_text_invalidates_embedding():
    stored = make_paper(
        1,
        embedding=[1.0, 0.0],
        embedding_model="fake-bow-2",
        embedded_at=timezone.now(),
    )
    incoming = [make_paper(1, abstract="A revised abstract")]

    result = diff_batch(incoming, existing_by_inspire_id={1: stored})

    assert result.updated == [stored]
    assert stored.embedding is None
    assert stored.embedding_model == ""
    assert stored.embedded_at is None


def test_changing_non_source_text_preserves_embedding():
    embedded_at = timezone.now()
    stored = make_paper(
        1,
        embedding=[1.0, 0.0],
        embedding_model="fake-bow-2",
        embedded_at=embedded_at,
    )
    incoming = [make_paper(1, citation_count=42)]

    result = diff_batch(incoming, existing_by_inspire_id={1: stored})

    assert result.updated == [stored]
    assert stored.embedding == [1.0, 0.0]
    assert stored.embedding_model == "fake-bow-2"
    assert stored.embedded_at == embedded_at


def test_batch_result_defaults_are_independent_between_instances():
    a = BatchResult()
    b = BatchResult()
    a.created.append(make_paper(1))

    assert b.created == []
