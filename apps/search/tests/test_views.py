import logging
from unittest import mock

import pytest

from apps.embedding import registry
from apps.embedding.fake import FakeEmbeddingProvider
from apps.papers.models import Paper


def make_paper(inspire_id, **overrides):
    defaults = {
        "inspire_id": inspire_id,
        "title": "A title",
        "abstract": "An abstract",
    }
    return Paper.objects.create(**(defaults | overrides))


@pytest.mark.django_db
def test_a_missing_query_returns_400_and_no_papers(client):
    make_paper(1, title="Higgs boson", abstract="A study of the higgs boson.")

    response = client.get("/api/search/")

    assert response.status_code == 400
    assert "results" not in response.json()


@pytest.mark.django_db
def test_an_empty_query_returns_400(client):
    response = client.get("/api/search/", {"q": ""})

    assert response.status_code == 400


@pytest.mark.django_db
def test_a_whitespace_only_query_returns_400(client):
    response = client.get("/api/search/", {"q": "   "})

    assert response.status_code == 400


@pytest.mark.django_db
def test_a_query_matching_nothing_returns_200_with_zero_count(client):
    make_paper(1, title="Higgs boson", abstract="A study of the higgs boson.")

    response = client.get("/api/search/", {"q": "zzznonexistentqueryxyz", "mode": "keyword"})

    assert response.status_code == 200
    assert response.json() == {
        "mode": "keyword",
        "count": 0,
        "next": None,
        "previous": None,
        "results": [],
    }


@pytest.mark.django_db
def test_keyword_results_include_scores_and_mode(client):
    make_paper(1, title="Higgs boson", abstract="A study of the higgs boson.")

    response = client.get("/api/search/", {"q": "higgs", "mode": "keyword"})

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "keyword"
    assert body["results"][0]["score"] > 0
    assert body["results"][0]["methods"] == []


@pytest.mark.django_db
def test_omitted_mode_uses_hybrid_and_reports_methods(client, settings):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()
    provider = FakeEmbeddingProvider()
    paper = make_paper(
        1,
        title="Higgs self coupling",
        abstract="A study of the Higgs self coupling.",
        embedding=provider.embed(["higgs self coupling"])[0],
        embedding_model=provider.model_name,
    )

    response = client.get("/api/search/", {"q": "higgs self coupling"})

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert response.json()["mode"] == "hybrid"
    assert result["id"] == paper.pk
    assert set(result["methods"]) == {"keyword", "semantic"}
    assert "degraded" not in response.json()


@pytest.mark.django_db
def test_hybrid_returns_semantic_only_results_when_keyword_has_no_hits(client, settings):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()
    provider = FakeEmbeddingProvider()
    paper = make_paper(
        1,
        title="Higgs",
        abstract="Self coupling",
        embedding=provider.embed(["higgs self coupling"])[0],
        embedding_model=provider.model_name,
    )

    with mock.patch("apps.search.views.keyword_search", return_value=Paper.objects.none()):
        response = client.get("/api/search/", {"q": "higgs self coupling", "mode": "hybrid"})

    assert response.status_code == 200
    assert response.json()["results"][0]["id"] == paper.pk


@pytest.mark.django_db
def test_hybrid_degrades_when_the_provider_cannot_be_loaded(client, settings, caplog):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()
    make_paper(1, title="Higgs boson", abstract="A higgs paper.")

    with (
        caplog.at_level(logging.ERROR, logger="apps.search.views"),
        mock.patch.object(
            FakeEmbeddingProvider,
            "embed",
            side_effect=ImportError("sentence-transformers is not installed"),
        ),
    ):
        response = client.get("/api/search/", {"q": "higgs", "mode": "hybrid"})

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "hybrid"
    assert body["degraded"] is True
    assert "provider" in body["warning"]
    assert body["results"][0]["methods"] == ["keyword"]
    # The outage must not be silent just because the request still returned 200.
    assert "embedding provider could not be loaded" in caplog.text


@pytest.mark.django_db
def test_hybrid_reports_stale_embeddings(client, settings, caplog):
    """Hybrid is the default mode, so drift must not go unreported on it."""
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()
    provider = FakeEmbeddingProvider()
    make_paper(
        1,
        title="Higgs self coupling",
        abstract="A study of the Higgs self coupling.",
        embedding=provider.embed(["higgs self coupling"])[0],
        embedding_model=provider.model_name,
    )
    make_paper(
        2,
        title="Higgs boson mass",
        abstract="A study of the Higgs boson mass.",
        embedding=provider.embed(["higgs boson mass"])[0],
        embedding_model="a-retired-model",
    )

    with caplog.at_level(logging.WARNING, logger="apps.search.health"):
        response = client.get("/api/search/", {"q": "higgs self coupling", "mode": "hybrid"})

    assert response.status_code == 200
    assert "1 stale embeddings" in caplog.text


@pytest.mark.django_db
def test_hybrid_empty_corpus_has_no_degradation(client, settings):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()

    response = client.get("/api/search/", {"q": "higgs", "mode": "hybrid"})

    assert response.status_code == 200
    assert response.json() == {
        "mode": "hybrid",
        "count": 0,
        "next": None,
        "previous": None,
        "results": [],
    }


@pytest.mark.django_db
def test_hybrid_uses_one_query_per_arm_plus_the_corpus_health_check(
    client, settings, django_assert_num_queries
):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()
    provider = FakeEmbeddingProvider()
    make_paper(
        1,
        title="Higgs self coupling",
        abstract="A study of the Higgs self coupling.",
        embedding=provider.embed(["higgs self coupling"])[0],
        embedding_model=provider.model_name,
    )

    # One per ranking, plus the stale-embedding count, which is cached for the life of
    # the process and so is paid once rather than per request.
    with django_assert_num_queries(3):
        response = client.get("/api/search/", {"q": "higgs self coupling", "mode": "hybrid"})

    assert response.status_code == 200


@pytest.mark.django_db
def test_a_stopword_only_query_returns_200_with_zero_count(client):
    make_paper(1, title="Higgs boson", abstract="A study of the higgs boson.")

    response = client.get("/api/search/", {"q": "the"})

    assert response.status_code == 200
    assert response.json()["count"] == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query",
    [
        '"unbalanced quote',
        "colons: and (parentheses) & ampersands!",
        "trailing-",
        "-leading",
        "()()",
        "!!!???",
    ],
)
def test_punctuation_heavy_queries_do_not_raise(client, query):
    make_paper(1, title="Higgs boson", abstract="A study of the higgs boson.")

    response = client.get("/api/search/", {"q": query, "mode": "keyword"})

    assert response.status_code == 200


@pytest.mark.django_db
def test_unknown_mode_returns_400(client):
    response = client.get("/api/search/", {"q": "higgs", "mode": "unknown"})

    assert response.status_code == 400
    assert "results" not in response.json()


@pytest.mark.django_db
def test_semantic_search_uses_the_configured_provider_and_returns_score(client, settings):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()
    provider = FakeEmbeddingProvider()
    paper = make_paper(
        1,
        title="Higgs self coupling",
        abstract="A study of the Higgs self coupling.",
        embedding=provider.embed(["higgs self coupling"])[0],
        embedding_model=provider.model_name,
    )

    response = client.get(
        "/api/search/",
        {"q": "higgs self coupling", "mode": "semantic"},
    )

    assert response.status_code == 200
    assert response.json()["mode"] == "semantic"
    assert response.json()["results"][0]["id"] == paper.pk
    assert response.json()["results"][0]["score"] == pytest.approx(1.0)


@pytest.mark.django_db
def test_semantic_retrieval_can_have_a_smaller_total_without_a_warning(client, settings):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()
    provider = FakeEmbeddingProvider()
    embedding = provider.embed(["higgs"])[0]
    for inspire_id in range(45):
        make_paper(
            inspire_id,
            title="Higgs paper",
            abstract="A study of the higgs boson.",
            embedding=embedding,
            embedding_model=provider.model_name,
        )

    keyword = client.get("/api/search/", {"q": "higgs", "mode": "keyword"}).json()
    semantic = client.get("/api/search/", {"q": "higgs", "mode": "semantic"}).json()

    assert keyword["count"] == 45
    assert semantic["count"] == 40
    assert "warning" not in semantic


@pytest.mark.django_db
def test_semantic_empty_corpus_returns_200(client, settings):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()

    response = client.get("/api/search/", {"q": "higgs", "mode": "semantic"})

    assert response.status_code == 200
    assert response.json() == {
        "mode": "semantic",
        "count": 0,
        "next": None,
        "previous": None,
        "results": [],
    }


@pytest.mark.django_db
def test_semantic_incompatible_corpus_returns_503(client, settings):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()
    provider = FakeEmbeddingProvider()
    make_paper(
        1,
        embedding=provider.embed(["higgs"])[0],
        embedding_model="old-model",
    )

    response = client.get("/api/search/", {"q": "higgs", "mode": "semantic"})

    assert response.status_code == 503
    assert "embed_papers" in response.json()["detail"]


@pytest.mark.django_db
def test_a_quoted_phrase_is_preferred_over_loose_words():
    from apps.search.ranking import search as rank_papers

    exact_phrase = make_paper(
        1, title="Higgs self-coupling analysis", abstract="Nothing else relevant."
    )
    loose_words = make_paper(
        2,
        title="Higgs and other bosons",
        abstract="A discussion mentioning self and coupling apart.",
    )

    results = list(rank_papers('"self-coupling"', limit=10))

    assert results[0].inspire_id == exact_phrase.inspire_id
    assert loose_words.inspire_id not in [paper.inspire_id for paper in results]


@pytest.mark.django_db
def test_an_excluded_term_is_absent_from_the_results():
    from apps.search.ranking import search as rank_papers

    with_term = make_paper(
        1, title="Higgs boson", abstract="A study of the higgs boson and supersymmetry."
    )
    without_term = make_paper(
        2, title="Higgs boson", abstract="A study of the higgs boson without extensions."
    )

    results = list(rank_papers("higgs -supersymmetry", limit=10))
    result_ids = [paper.inspire_id for paper in results]

    assert without_term.inspire_id in result_ids
    assert with_term.inspire_id not in result_ids


@pytest.mark.django_db
def test_keyword_scores_descend_with_the_result_order(client):
    make_paper(1, title="Higgs self-coupling", abstract="A paper about the higgs self-coupling.")
    make_paper(2, title="Higgs boson study", abstract="A paper mentioning self-coupling once.")
    make_paper(3, title="Collider physics", abstract="A paper that mentions higgs in passing.")

    response = client.get("/api/search/", {"q": "higgs self-coupling", "mode": "keyword"})

    scores = [result["score"] for result in response.json()["results"]]
    assert len(scores) >= 2
    assert scores == sorted(scores, reverse=True)


@pytest.mark.django_db
def test_a_drifted_corpus_still_serves_its_compatible_papers(client, settings):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()
    provider = registry.get_provider()
    compatible = make_paper(1, title="Higgs self coupling", abstract="A higgs paper.")
    compatible.embedding = provider.embed([compatible.embedding_text])[0]
    compatible.embedding_model = provider.model_name
    compatible.save(update_fields=["embedding", "embedding_model"])
    stale = make_paper(2, title="Higgs boson mass", abstract="Another higgs paper.")
    stale.embedding = provider.embed([stale.embedding_text])[0]
    stale.embedding_model = "a-retired-model"
    stale.save(update_fields=["embedding", "embedding_model"])

    response = client.get("/api/search/", {"q": "higgs", "mode": "semantic"})

    assert response.status_code == 200
    titles = [result["title"] for result in response.json()["results"]]
    assert titles == [compatible.title]


@pytest.mark.django_db
def test_semantic_search_returns_503_when_the_provider_cannot_be_loaded(client, settings):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()
    make_paper(1, title="Higgs boson", abstract="A higgs paper.")

    def explode(texts):
        raise ImportError("sentence-transformers is not installed")

    with mock.patch.object(FakeEmbeddingProvider, "embed", side_effect=explode):
        response = client.get("/api/search/", {"q": "higgs", "mode": "semantic"})

    assert response.status_code == 503
    body = response.json()
    assert body["mode"] == "semantic"
    assert "provider" in body["detail"]
    assert "results" not in body
