import datetime

import pytest

from apps.papers.models import Paper
from apps.papers.presentation import excerpt_abstract
from apps.search.serializers import PaperSearchResultSerializer, complete_date


def make_paper(inspire_id, **overrides):
    defaults = {
        "inspire_id": inspire_id,
        "title": "A title",
        "abstract": "An abstract",
        "authors": ["A. Author"],
    }
    return Paper(**(defaults | overrides))


@pytest.mark.django_db
def test_a_result_carries_every_required_field():
    paper = Paper.objects.create(
        inspire_id=42,
        title="A title",
        abstract="An abstract",
        authors=["A. Author"],
        earliest_date="2020-05-10",
    )

    data = PaperSearchResultSerializer(paper).data

    assert data["id"] == paper.pk
    assert data["title"] == "A title"
    assert data["authors"] == ["A. Author"]
    assert data["author_count"] == 1
    assert data["publication_date"] == datetime.date(2020, 5, 10)
    assert data["abstract_snippet"] == "An abstract"
    assert data["inspire_url"] == "https://inspirehep.net/literature/42"


@pytest.mark.django_db
def test_serializer_bounds_authors_and_reports_the_total():
    paper = Paper.objects.create(
        inspire_id=43,
        title="A title",
        abstract="An abstract",
        authors=[f"Author {index}" for index in range(1000)],
    )

    data = PaperSearchResultSerializer(paper).data

    assert data["authors"] == [f"Author {index}" for index in range(5)]
    assert data["author_count"] == 1000


@pytest.mark.django_db
def test_serializer_returns_all_short_author_lists_and_zero_for_empty():
    short = Paper.objects.create(
        inspire_id=44,
        title="Short",
        abstract="An abstract",
        authors=["First", "Second"],
    )
    empty = Paper.objects.create(
        inspire_id=45,
        title="Empty",
        abstract="An abstract",
        authors=[],
    )

    short_data = PaperSearchResultSerializer(short).data
    empty_data = PaperSearchResultSerializer(empty).data

    assert short_data["authors"] == ["First", "Second"]
    assert short_data["author_count"] == 2
    assert empty_data["authors"] == []
    assert empty_data["author_count"] == 0


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ("2020-05-10", datetime.date(2020, 5, 10)),
        ("2020-05", datetime.date(2020, 5, 1)),
        ("2020", datetime.date(2020, 1, 1)),
        ("", None),
    ],
)
def test_complete_date(stored, expected):
    assert complete_date(stored) == expected


def test_a_long_abstract_is_excerpted_at_a_word_boundary_and_marked():
    abstract = "word " * 100

    excerpt = excerpt_abstract(abstract, max_chars=50)

    assert len(excerpt) <= 51  # allows for the trailing ellipsis character
    assert excerpt.endswith("\u2026")
    assert not excerpt[:-1].endswith(" ")


def test_a_short_abstract_is_returned_whole_and_unmarked():
    abstract = "A short abstract."

    excerpt = excerpt_abstract(abstract, max_chars=280)

    assert excerpt == abstract
    assert not excerpt.endswith("\u2026")
