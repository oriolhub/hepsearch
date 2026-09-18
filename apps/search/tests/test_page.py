import re

import pytest

from apps.embedding import registry
from apps.papers.models import Paper
from apps.search.modes import SearchMode
from apps.search.views import _ranked_papers


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
    assert b"rephras" in response.content
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
    assert "Another " in no_author_fragment
    assert "abstract" in no_author_fragment


@pytest.mark.django_db
def test_search_page_renders_metadata_links_badge_and_retrieved_timing(client):
    paper = make_paper(
        1,
        title="Higgs coupling measurement",
        abstract="Measurements of the Higgs coupling.",
        arxiv_id="1234.5678",
        earliest_date="2024-03-01",
        citation_count=0,
        journal="Physical Review D",
    )

    response = client.get("/", {"q": "higgs coupling", "mode": "keyword"})
    body = response.content.decode()

    assert paper.title in body
    assert "Physical Review D" in body
    assert "1 March 2024" in body
    assert "0 citations" in body
    assert f'href="https://arxiv.org/abs/{paper.arxiv_id}"' in body
    assert "Found by: Keyword" in body
    assert "retrieved results" in body
    assert "Search completed in" in body


@pytest.mark.django_db
def test_search_page_omits_arxiv_link_and_reference_when_the_paper_has_neither(client):
    make_paper(
        1,
        title="Higgs coupling measurement",
        abstract="Measurements of the Higgs coupling.",
        arxiv_id="",
        doi="",
        journal="",
        citation_count=7,
    )

    response = client.get("/", {"q": "higgs coupling", "mode": "keyword"})
    body = response.content.decode()

    metadata = re.search(r'<div class="metadata">(.*?)</div>', body, re.DOTALL).group(1)

    assert "arxiv.org" not in body
    assert metadata.split() == ["7", "citations"]


@pytest.mark.django_db
def test_search_page_highlights_stemmed_matches_and_keeps_markup_literal(client):
    make_paper(
        1,
        title="<b>Higgs</b> coupling",
        abstract="<b>Measurements</b> of the Higgs coupling.",
    )

    response = client.get("/", {"q": "measure", "mode": "keyword"})
    body = response.content.decode()

    assert "<mark>Measurements</mark>" in body
    assert "&lt;b&gt;Higgs&lt;/b&gt;" in body
    assert "<b>Higgs</b>" not in body


@pytest.mark.django_db
def test_search_page_keeps_semantic_only_excerpt_unmarked(client, settings):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()
    paper = make_paper(
        1,
        title="A distant paper",
        abstract="A paragraph with no query words.",
    )
    provider = registry.get_provider()
    paper.embedding = provider.embed([paper.embedding_text])[0]
    paper.embedding_model = provider.model_name
    paper.save(update_fields=["embedding", "embedding_model"])

    response = client.get("/", {"q": "higgs", "mode": "semantic"})
    body = response.content.decode()

    assert paper.abstract in body
    assert "<mark>" not in body
    assert "Found by: Semantic" in body


@pytest.mark.django_db
def test_page_highlighting_does_not_load_large_ranker_columns(settings):
    paper = make_paper(1, title="Higgs paper", abstract="A higgs abstract.")

    papers, unavailable = _ranked_papers("higgs", SearchMode.KEYWORD, highlight=True)

    assert unavailable is None
    assert papers[0].pk == paper.pk
    assert {"embedding", "search_vector"} <= papers[0].get_deferred_fields()


@pytest.mark.django_db
def test_page_highlighting_does_not_add_a_database_query(client, django_assert_num_queries):
    make_paper(1, title="Higgs paper", abstract="A higgs abstract.")

    with django_assert_num_queries(1):
        response = client.get("/", {"q": "higgs", "mode": "keyword"})

    assert response.status_code == 200


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


@pytest.mark.django_db
def test_search_page_offers_and_preserves_mode(client, settings):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()
    first = make_paper(
        1,
        title="Higgs self coupling",
        abstract="A study of the Higgs self coupling.",
    )
    provider = registry.get_provider()
    first.embedding = provider.embed([first.embedding_text])[0]
    first.embedding_model = provider.model_name
    first.save(update_fields=["embedding", "embedding_model"])

    response = client.get("/", {"q": "higgs self coupling", "mode": "semantic"})

    assert response.status_code == 200
    assert b'name="mode"' in response.content
    assert b'value="semantic" selected' in response.content
    assert first.title.encode() in response.content


@pytest.mark.django_db
def test_search_page_defaults_to_hybrid(client, settings):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()
    provider = registry.get_provider()
    paper = make_paper(
        1,
        title="Higgs self coupling",
        abstract="A study of the Higgs self coupling.",
    )
    paper.embedding = provider.embed([paper.embedding_text])[0]
    paper.embedding_model = provider.model_name
    paper.save(update_fields=["embedding", "embedding_model"])

    response = client.get("/", {"q": "higgs self coupling"})

    assert response.status_code == 200
    assert b'value="hybrid" selected' in response.content
    assert b"Found by:" in response.content
    assert paper.title.encode() in response.content


@pytest.mark.django_db
def test_search_page_shows_hybrid_degradation_notice(client, settings):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()
    make_paper(1, title="Higgs boson", abstract="A higgs paper.")

    response = client.get("/", {"q": "higgs", "mode": "hybrid"})

    assert response.status_code == 200
    assert b"embed_papers" in response.content
    assert b"No results found." not in response.content


@pytest.mark.django_db
def test_search_page_degraded_with_no_hits_does_not_claim_no_results(client, settings):
    """Nothing was properly searched, so "No results found." would be a false claim."""
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()
    make_paper(1, title="Higgs boson", abstract="A higgs paper.")

    response = client.get("/", {"q": "zzznonexistentqueryxyz"})
    body = response.content.decode()

    assert response.status_code == 200
    assert "embed_papers" in body
    assert "No results found." not in body


@pytest.mark.django_db
def test_search_page_does_not_reflect_an_unknown_mode_unescaped(client):
    response = client.get("/", {"q": "higgs", "mode": "<script>alert(1)</script>"})
    body = response.content.decode()

    assert response.status_code == 400
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body


@pytest.mark.django_db
def test_search_page_reports_an_unusable_semantic_corpus(client, settings):
    settings.EMBEDDING_PROVIDER = "apps.embedding.fake.FakeEmbeddingProvider"
    registry.reset()
    make_paper(1, title="Higgs boson", abstract="A higgs paper.")

    response = client.get("/", {"q": "higgs", "mode": "semantic"})
    body = response.content.decode()

    assert response.status_code == 200
    assert "No results found." not in body
    assert "embed_papers" in body
