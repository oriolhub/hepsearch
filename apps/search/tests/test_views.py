import pytest

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
    assert response.json() == {"count": 0, "results": []}


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
