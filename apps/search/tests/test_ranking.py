import pytest

from apps.papers.models import Paper
from apps.search.ranking import search


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
