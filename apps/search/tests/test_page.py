import re

import pytest

from apps.papers.models import Paper


def make_paper(inspire_id, **overrides):
    defaults = {
        "inspire_id": inspire_id,
        "title": "A title",
        "abstract": "An abstract",
        "authors": ["A. Author"],
    }
    return Paper.objects.create(**(defaults | overrides))


@pytest.mark.django_db
def test_search_page_renders_ranked_titles_and_inspire_links(client):
    first = make_paper(
        1,
        title="Higgs self-coupling measurement",
        abstract="A paper about the higgs self-coupling.",
    )
    second = make_paper(
        2,
        title="Higgs boson study",
        abstract="A paper mentioning the higgs self-coupling once.",
    )

    response = client.get("/", {"q": "higgs self-coupling"})
    body = response.content.decode()

    assert response.status_code == 200
    assert first.title in body
    assert second.title in body
    assert body.index(first.title) < body.index(second.title)
    assert f'href="{first.inspire_url}"' in body


@pytest.mark.django_db
def test_search_page_redisplays_and_escapes_the_query(client):
    response = client.get("/", {"q": "<script>alert(1)</script>"})
    body = response.content.decode()

    assert response.status_code == 200
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body


@pytest.mark.django_db
def test_search_page_shows_no_results_message_for_a_real_miss(client):
    response = client.get("/", {"q": "zzznonexistentqueryxyz"})

    assert response.status_code == 200
    assert b"No results found." in response.content
    assert b'value="zzznonexistentqueryxyz"' in response.content


@pytest.mark.django_db
@pytest.mark.parametrize("query", [None, "", "   "])
def test_search_page_shows_only_the_form_without_a_query(client, query):
    response = client.get("/", {} if query is None else {"q": query})

    assert response.status_code == 200
    assert b"No results found." not in response.content
    assert b"<article>" not in response.content


@pytest.mark.django_db
def test_search_page_summarises_authors_and_omits_empty_author_lines(client):
    collaboration = make_paper(
        1,
        title="Collaboration Higgs paper",
        abstract="A higgs abstract.",
        authors=[f"Author {index}, Given" for index in range(100)],
    )
    no_authors = make_paper(
        2,
        title="Another Higgs paper",
        abstract="Another higgs abstract.",
        authors=[],
    )

    response = client.get("/", {"q": "higgs"})
    body = response.content.decode()

    assert collaboration.display_authors in body
    assert "Author 5, Given" not in body
    no_author_start = body.index(no_authors.title)
    no_author_end = body.index("</article>", no_author_start)
    no_author_fragment = body[no_author_start:no_author_end]
    assert "Author 0, Given" not in no_author_fragment
    assert no_authors.abstract in no_author_fragment


@pytest.mark.django_db
def test_search_page_and_api_keep_the_same_result_order(client):
    first = make_paper(
        1,
        title="Higgs self-coupling measurement",
        abstract="A paper about self-coupling.",
    )
    second = make_paper(
        2,
        title="Higgs boson study",
        abstract="A paper mentioning self-coupling.",
    )

    page_body = client.get("/", {"q": "higgs self-coupling"}).content.decode()
    api_results = client.get("/api/search/", {"q": "higgs self-coupling"}).json()["results"]
    page_ids = [int(value) for value in re.findall(r"inspirehep\.net/literature/(\d+)", page_body)]

    assert page_ids[:2] == [first.inspire_id, second.inspire_id]
    assert [result["title"] for result in api_results[:2]] == [
        first.title,
        second.title,
    ]
