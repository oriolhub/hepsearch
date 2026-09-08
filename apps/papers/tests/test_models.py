import ast
import sys

import pytest
from django.db import IntegrityError, transaction

from apps.papers.models import Paper


@pytest.mark.django_db
def test_minimal_paper_creation():
    paper = Paper.objects.create(
        inspire_id=1000001,
        title="Minimal Paper",
        abstract="Minimal abstract content.",
    )
    assert paper.pk is not None
    assert paper.pk != paper.inspire_id
    assert paper.arxiv_id == ""
    assert paper.doi == ""
    assert paper.journal == ""
    assert paper.earliest_date == ""
    assert paper.citation_count is None
    assert paper.authors == []
    assert paper.categories == []


@pytest.mark.django_db
def test_duplicate_inspire_id_raises_integrity_error():
    Paper.objects.create(
        inspire_id=1000002,
        title="First Paper",
        abstract="First abstract.",
    )
    with transaction.atomic(), pytest.raises(IntegrityError):
        Paper.objects.create(
            inspire_id=1000002,
            title="Second Paper",
            abstract="Second abstract.",
        )


@pytest.mark.django_db
def test_empty_abstract_raises_integrity_error_and_skips_clean():
    with transaction.atomic(), pytest.raises(IntegrityError):
        Paper.objects.create(
            inspire_id=1000003,
            title="Empty Abstract Paper",
            abstract="",
        )


@pytest.mark.django_db
@pytest.mark.parametrize("date_str", ["2014", "2012-07", "2016-10-25"])
def test_earliest_date_round_trips(date_str):
    paper = Paper.objects.create(
        inspire_id=1000004 + hash(date_str) % 1000,
        title="Date Test Paper",
        abstract="Date test abstract.",
        earliest_date=date_str,
    )
    refetched = Paper.objects.get(pk=paper.pk)
    assert refetched.earliest_date == date_str


@pytest.mark.django_db
def test_thousands_of_authors_stored_in_order():
    author_list = [f"Author {i}" for i in range(3000)]
    paper = Paper.objects.create(
        inspire_id=1000010,
        title="Collaboration Paper",
        abstract="Collaboration abstract.",
        authors=author_list,
    )
    refetched = Paper.objects.get(pk=paper.pk)
    assert len(refetched.authors) == 3000
    assert refetched.authors == author_list


def test_inspire_url_derivation():
    paper = Paper(inspire_id=1234567, title="Title", abstract="Abstract")
    assert paper.inspire_url == "https://inspirehep.net/literature/1234567"


def test_author_summary():
    p_empty = Paper(authors=[])
    assert p_empty.author_summary() == ""

    p_short = Paper(authors=["Alice Smith", "Bob Jones"])
    assert p_short.author_summary() == "Alice Smith, Bob Jones"

    p_exact_3 = Paper(authors=["Alice Smith", "Bob Jones", "Carol White"])
    assert p_exact_3.author_summary() == "Alice Smith, Bob Jones, Carol White"

    p_long = Paper(authors=["Alice Smith", "Bob Jones", "Carol White", "Dave Black"])
    assert p_long.author_summary() == "Alice Smith, Bob Jones, Carol White et al. (4)"


def test_papers_app_has_no_dependant_imports():
    for mod_name, mod in list(sys.modules.items()):
        if mod_name.startswith("apps.papers") and mod:
            file_path = getattr(mod, "__file__", "")
            if file_path and file_path.endswith(".py"):
                with open(file_path, encoding="utf-8") as f:
                    tree = ast.parse(f.read(), filename=file_path)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            assert not alias.name.startswith("apps.ingestion")
                            assert not alias.name.startswith("apps.search")
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        assert not node.module.startswith("apps.ingestion")
                        assert not node.module.startswith("apps.search")
