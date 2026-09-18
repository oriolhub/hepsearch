import pytest
from django.conf import settings

from apps.papers.models import Paper
from apps.search.ranking import search, semantic_search


def make_paper(inspire_id, title="A title", abstract="An abstract", **overrides):
    defaults = {
        "inspire_id": inspire_id,
        "title": title,
        "abstract": abstract,
    }
    return Paper.objects.create(**(defaults | overrides))


@pytest.mark.django_db
def test_a_ranked_match_returns_papers_in_descending_relevance():
    # "higgs" appears once in one abstract and twice in another; the one with two
    # mentions should rank first.
    make_paper(1, title="Unrelated", abstract="A study of the higgs boson.")
    make_paper(2, title="Unrelated", abstract="The higgs mechanism and the higgs field.")

    results = list(search("higgs", limit=10))

    assert [paper.inspire_id for paper in results] == [2, 1]


@pytest.mark.django_db
def test_a_title_match_outranks_an_abstract_only_match():
    title_match = make_paper(
        1, title="Supersymmetric extensions", abstract="Nothing relevant here."
    )
    abstract_only = make_paper(
        2, title="Unrelated title", abstract="A brief mention of supersymmetric models."
    )

    results = list(search("supersymmetric", limit=10))

    assert results[0].inspire_id == title_match.inspire_id
    assert results[1].inspire_id == abstract_only.inspire_id


@pytest.mark.django_db
def test_the_limit_bounds_the_number_of_rows_returned():
    for i in range(5):
        make_paper(i, title="Quarks", abstract="A study of quarks.")

    results = list(search("quarks", limit=2))

    assert len(results) == 2


@pytest.mark.django_db
def test_repeating_a_query_returns_the_same_order():
    make_paper(1, title="Neutrinos", abstract="A study of neutrinos.")
    make_paper(2, title="Neutrinos", abstract="Another study of neutrinos and oscillations.")

    first = [paper.inspire_id for paper in search("neutrinos", limit=10)]
    second = [paper.inspire_id for paper in search("neutrinos", limit=10)]

    assert first == second


@pytest.mark.django_db
def test_a_query_matching_nothing_returns_no_rows():
    make_paper(1, title="Quarks", abstract="A study of quarks.")

    results = list(search("zzznonexistentqueryxyz", limit=10))

    assert results == []


@pytest.mark.django_db
def test_ranking_returns_a_lazy_composable_queryset():
    from django.db.models import QuerySet

    make_paper(1, title="Bosons", abstract="A study of bosons.")

    results = search("bosons", limit=10)

    # A plain QuerySet, not a materialised list: a caller such as the future hybrid
    # ranker can combine it (e.g. via `Paper.objects.filter(pk__in=results)`) instead
    # of reimplementing this query.
    assert isinstance(results, QuerySet)
    assert list(Paper.objects.filter(pk__in=results).values_list("inspire_id", flat=True)) == [1]


def vector(index, value=1.0):
    result = [0.0] * settings.EMBEDDING_DIMENSION
    result[index] = value
    return result


@pytest.mark.django_db
def test_semantic_search_orders_by_nearest_vector():
    nearest = make_paper(
        1,
        embedding=vector(0),
        embedding_model="test-model",
    )
    distant = make_paper(
        2,
        embedding=vector(1),
        embedding_model="test-model",
    )

    results = list(
        semantic_search(
            Paper.objects.all(),
            vector(0),
            limit=10,
            model_name="test-model",
        )
    )

    assert [paper.pk for paper in results] == [nearest.pk, distant.pk]
    assert results[0].score > results[1].score


@pytest.mark.django_db
def test_semantic_search_excludes_null_and_foreign_model_embeddings():
    compatible = make_paper(
        1,
        embedding=vector(0),
        embedding_model="test-model",
    )
    make_paper(2, embedding=None, embedding_model="")
    make_paper(3, embedding=vector(0), embedding_model="old-model")

    results = list(
        semantic_search(
            Paper.objects.all(),
            vector(0),
            limit=10,
            model_name="test-model",
        )
    )

    assert [paper.pk for paper in results] == [compatible.pk]


@pytest.mark.django_db
def test_semantic_search_returns_empty_queryset_without_compatible_rows():
    make_paper(1, embedding=None, embedding_model="")

    results = semantic_search(
        Paper.objects.all(),
        vector(0),
        limit=10,
        model_name="test-model",
    )

    assert list(results) == []


@pytest.mark.django_db
def test_semantic_search_is_capped_by_the_vector_index_scan_width():
    for inspire_id in range(45):
        make_paper(
            inspire_id,
            embedding=vector(0),
            embedding_model="test-model",
        )

    results = list(
        semantic_search(
            Paper.objects.all(),
            vector(0),
            limit=60,
            model_name="test-model",
        )
    )

    assert len(results) == 40


@pytest.mark.django_db
def test_semantic_similarity_is_not_clamped():
    paper = make_paper(
        1,
        embedding=vector(0),
        embedding_model="test-model",
    )

    results = list(
        semantic_search(
            Paper.objects.all(),
            vector(0, value=-1.0),
            limit=10,
            model_name="test-model",
        )
    )

    assert results[0].pk == paper.pk
    assert results[0].score == pytest.approx(-1.0)
