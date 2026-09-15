import pytest

from apps.papers.models import Paper
from apps.search.health import check_stale_embeddings


@pytest.mark.django_db
def test_stale_embeddings_are_logged_once(caplog):
    Paper.objects.create(
        inspire_id=1,
        title="A title",
        abstract="An abstract",
        embedding=[1.0] + [0.0] * 383,
        embedding_model="old-model",
    )

    with caplog.at_level("WARNING"):
        assert check_stale_embeddings("current-model") == 1
        assert check_stale_embeddings("current-model") == 1

    assert caplog.text.count("Semantic corpus contains 1 stale embeddings") == 1


@pytest.mark.django_db
def test_clean_embeddings_are_silent(caplog):
    Paper.objects.create(
        inspire_id=1,
        title="A title",
        abstract="An abstract",
        embedding=[1.0] + [0.0] * 383,
        embedding_model="current-model",
    )

    with caplog.at_level("WARNING"):
        assert check_stale_embeddings("current-model") == 0

    assert not caplog.records
