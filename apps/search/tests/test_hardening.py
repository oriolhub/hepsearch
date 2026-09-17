import logging
from unittest import mock

import pytest

from apps.embedding import registry
from apps.embedding.fake import FakeEmbeddingProvider
from apps.papers.models import Paper
from apps.search.pagination import SearchPagination
from apps.search.throttling import EmbeddingThrottle, KeywordThrottle
from apps.search.views import PROVIDER_UNAVAILABLE


def make_paper(inspire_id, **overrides):
    defaults = {"inspire_id": inspire_id, "title": "Higgs paper", "abstract": "Higgs physics."}
    return Paper.objects.create(**(defaults | overrides))


@pytest.mark.django_db
def test_keyword_results_are_paginated_and_count_is_bounded(client, settings, monkeypatch):
    settings.SEARCH_RESULT_LIMIT = 3
    monkeypatch.setattr(SearchPagination, "page_size", 2)
    for inspire_id in range(1, 5):
        make_paper(inspire_id)

    first = client.get("/api/search/", {"q": "higgs", "mode": "keyword"})
    second = client.get("/api/search/", {"q": "higgs", "mode": "keyword", "page": 2})

    assert first.status_code == second.status_code == 200
    assert first.json()["count"] == 3
    assert len(first.json()["results"]) == 2
    assert first.json()["next"]
    assert second.json()["previous"]
    assert len(second.json()["results"]) == 1


@pytest.mark.django_db
def test_invalid_pages_return_404(client):
    make_paper(1)

    for page in ("abc", "999"):
        response = client.get("/api/search/", {"q": "higgs", "mode": "keyword", "page": page})
        assert response.status_code == 404


@pytest.mark.django_db
def test_invalid_page_size_names_the_parameter(client):
    response = client.get("/api/search/", {"q": "higgs", "mode": "keyword", "page_size": "abc"})

    assert response.status_code == 400
    assert "page_size" in response.json()["detail"]


@pytest.mark.django_db
def test_empty_results_reject_a_non_first_page(client):
    response = client.get(
        "/api/search/",
        {"q": "does-not-match", "mode": "keyword", "page": 2},
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_unknown_mode_is_rejected_before_throttling(client):
    response = client.get("/api/search/", {"q": "higgs", "mode": "unknown"})

    assert response.status_code == 400
    assert "mode" in response.json()["detail"]


@pytest.mark.django_db
def test_overlong_query_is_rejected_before_embedding(client, settings):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()
    with mock.patch.object(FakeEmbeddingProvider, "embed") as embed:
        response = client.get(
            "/api/search/",
            {"q": "x" * (settings.SEARCH_QUERY_MAX_CHARS + 1), "mode": "semantic"},
        )

    assert response.status_code == 400
    assert "'q'" in response.json()["detail"]
    embed.assert_not_called()


@pytest.mark.django_db
def test_query_at_the_bound_is_accepted(client, settings):
    with mock.patch("apps.search.views._ranked_papers", return_value=([], None)):
        response = client.get(
            "/api/search/",
            {"q": "x" * settings.SEARCH_QUERY_MAX_CHARS, "mode": "keyword"},
        )

    assert response.status_code == 200


@pytest.mark.django_db
def test_keyword_throttle_returns_retry_after(client, monkeypatch):
    make_paper(1)
    monkeypatch.setattr(KeywordThrottle, "get_rate", lambda self: "1/min")

    assert client.get("/api/search/", {"q": "higgs", "mode": "keyword"}).status_code == 200
    response = client.get("/api/search/", {"q": "higgs", "mode": "keyword"})

    assert response.status_code == 429
    assert response["Retry-After"]


@pytest.mark.django_db
def test_page_throttle_returns_retry_after(client, settings, monkeypatch):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()
    make_paper(1)
    monkeypatch.setattr(EmbeddingThrottle, "get_rate", lambda self: "1/min")

    assert client.get("/", {"q": "higgs", "mode": "hybrid"}).status_code == 200
    response = client.get("/", {"q": "higgs", "mode": "hybrid"})

    assert response.status_code == 429
    assert response["Retry-After"]
    assert b"Too many requests" in response.content


@pytest.mark.django_db
def test_degraded_page_preserves_warning_on_later_page(client, settings):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()
    for inspire_id in range(1, 26):
        make_paper(inspire_id, title=f"Higgs paper {inspire_id}")

    with mock.patch.object(
        FakeEmbeddingProvider,
        "embed",
        side_effect=ImportError("sentence-transformers is not installed"),
    ):
        response = client.get("/", {"q": "higgs", "mode": "hybrid", "page": 2})

    assert response.status_code == 200
    assert b"embed_papers" not in response.content
    assert b"embedding provider could not be loaded" in response.content
    assert b"Higgs paper 1" in response.content


@pytest.mark.django_db
def test_later_hybrid_page_costs_the_same_as_first(
    client, settings, monkeypatch, django_assert_num_queries
):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    settings.SEARCH_RESULT_LIMIT = 3
    monkeypatch.setattr(SearchPagination, "page_size", 2)
    registry.reset()
    provider = FakeEmbeddingProvider()
    for inspire_id in range(1, 4):
        paper = make_paper(inspire_id, title=f"Higgs paper {inspire_id}")
        paper.embedding = provider.embed([paper.embedding_text])[0]
        paper.embedding_model = provider.model_name
        paper.save(update_fields=["embedding", "embedding_model"])

    with django_assert_num_queries(3):
        first = client.get("/", {"q": "higgs", "mode": "hybrid", "page_size": 2})
    with django_assert_num_queries(2):
        second = client.get("/", {"q": "higgs", "mode": "hybrid", "page": 2, "page_size": 2})

    assert first.status_code == second.status_code == 200


@pytest.mark.django_db
def test_page_navigation_preserves_query_and_mode(client):
    for inspire_id in range(1, 26):
        make_paper(inspire_id, title=f"Higgs paper {inspire_id}")

    response = client.get("/", {"q": "higgs", "mode": "keyword"})

    assert response.status_code == 200
    assert b"page=2" in response.content
    assert b"q=higgs" in response.content
    assert b"mode=keyword" in response.content


@pytest.mark.django_db
def test_single_page_omits_navigation(client):
    make_paper(1)

    response = client.get("/", {"q": "higgs", "mode": "keyword"})

    assert response.status_code == 200
    assert b'aria-label="Search result pages"' not in response.content


def test_debug_false_errors_are_opaque(client, settings):
    settings.DEBUG = False

    response = client.get("/api/search/", {"q": "higgs", "mode": "unknown"})

    assert response.status_code == 400
    assert b"Traceback" not in response.content
    assert b"workspace" not in response.content


def test_page_parameter_is_not_reflected(client):
    response = client.get("/", {"q": "higgs", "page": "<script>alert(1)</script>"})

    assert response.status_code == 404
    assert b"<script>" not in response.content


@pytest.mark.django_db
def test_slow_search_logs_elapsed_mode_and_escaped_query(client, settings, caplog):
    settings.SEARCH_SLOW_SECONDS = 0
    with (
        caplog.at_level(logging.WARNING, logger="apps.search.views"),
        mock.patch("apps.search.views._ranked_papers", return_value=([], None)),
    ):
        response = client.get("/api/search/", {"q": "line\nbreak", "mode": "keyword"})

    assert response.status_code == 200
    assert "Slow search" in caplog.text
    assert "mode=keyword" in caplog.text
    assert r"line\nbreak" in caplog.text


@pytest.mark.django_db
def test_fast_search_does_not_log_slow_search(client, settings, caplog):
    settings.SEARCH_SLOW_SECONDS = 999

    with caplog.at_level(logging.WARNING, logger="apps.search.views"):
        response = client.get("/api/search/", {"q": "higgs", "mode": "keyword"})

    assert response.status_code == 200
    assert "Slow search" not in caplog.text


@pytest.mark.django_db
def test_degraded_hybrid_reports_itself_when_keyword_finds_nothing(client, settings):
    """An outage that also leaves no keyword hits must not read as an honest miss.

    The empty response once bypassed the paginator and so dropped `degraded`, making a
    provider failure indistinguishable from a query that simply matched nothing.
    """
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()
    make_paper(1)

    with mock.patch.object(
        FakeEmbeddingProvider,
        "embed",
        side_effect=ImportError("sentence-transformers is not installed"),
    ):
        response = client.get("/api/search/", {"q": "zzznomatch", "mode": "hybrid"})

    body = response.json()
    assert response.status_code == 200
    assert body["count"] == 0
    assert body["results"] == []
    assert body["degraded"] is True
    assert body["warning"] == PROVIDER_UNAVAILABLE


def test_query_less_page_load_is_not_charged_the_embedding_rate(client, monkeypatch):
    """Browsing to the form ranks nothing, so it must not spend the search budget."""
    monkeypatch.setattr(EmbeddingThrottle, "get_rate", lambda self: "1/min")

    first = client.get("/")
    second = client.get("/")

    assert first.status_code == second.status_code == 200
