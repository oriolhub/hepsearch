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

    response = client.get("/api/search/", {"q": "zzznonexistentqueryxyz"})

    assert response.status_code == 200
    assert response.json() == {"mode": "keyword", "count": 0, "results": []}


@pytest.mark.django_db
def test_keyword_results_include_scores_and_mode(client):
    make_paper(1, title="Higgs boson", abstract="A study of the higgs boson.")

    response = client.get("/api/search/", {"q": "higgs"})

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "keyword"
    assert body["results"][0]["score"] > 0


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

    response = client.get("/api/search/", {"q": query})

    assert response.status_code == 200


@pytest.mark.django_db
def test_unknown_mode_returns_400(client):
    response = client.get("/api/search/", {"q": "higgs", "mode": "hybrid"})

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
def test_semantic_empty_corpus_returns_200(client, settings):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()

    response = client.get("/api/search/", {"q": "higgs", "mode": "semantic"})

    assert response.status_code == 200
    assert response.json() == {"mode": "semantic", "count": 0, "results": []}


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

    response = client.get("/api/search/", {"q": "higgs self-coupling"})

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
