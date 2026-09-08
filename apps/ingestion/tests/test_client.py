import ast
import json
from pathlib import Path

import httpx
import pytest

from apps.ingestion.client import (
    InspireClient,
    InspireRequestError,
    iter_records,
    normalize,
)

FIXTURE = Path(__file__).parent / "fixtures" / "inspire_literature.json"


@pytest.fixture
def payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def make_client(handler, **kwargs):
    """Build a client whose HTTP seam is a canned handler, never the network."""
    options = {"throttle": 0, "backoff_base": 1.0, "max_retries": 1} | kwargs
    return InspireClient(client=httpx.Client(transport=httpx.MockTransport(handler)), **options)


def ok(request):
    return httpx.Response(200, json={"hits": {"total": 0, "hits": []}}, request=request)


def test_fixture_normalizes_full_record(payload):
    paper = normalize(payload["hits"]["hits"][2]["metadata"])

    assert paper is not None
    assert paper.inspire_id == 1325552
    assert paper.title
    assert paper.abstract
    assert len(paper.authors) == 11
    assert paper.arxiv_id == "1410.8849"
    assert paper.doi == "10.1007/JHEP04(2015)040"
    assert paper.journal
    assert paper.earliest_date
    assert paper.citation_count is not None


def test_normalize_skips_missing_or_empty_abstract(payload):
    no_abstract = payload["hits"]["hits"][0]["metadata"]
    assert normalize(no_abstract) is None
    base = {"control_number": 1, "titles": [{"title": "Title"}]}
    assert normalize({**base, "abstracts": []}) is None
    assert normalize({**base, "abstracts": [{"value": ""}]}) is None


def test_abstract_selection_prefers_arxiv_and_is_repeatable(payload):
    metadata = payload["hits"]["hits"][2]["metadata"]
    first = normalize(metadata)
    second = normalize(metadata)

    assert first is not None and second is not None
    assert first.abstract == second.abstract
    assert metadata["abstracts"][1]["source"].casefold() == "arxiv"
    assert first.abstract == metadata["abstracts"][1]["value"]


def test_abstract_selection_rules_on_synthetic_records():
    base = {"control_number": 1, "titles": [{"title": "Title"}]}

    late_arxiv = normalize(
        {
            **base,
            "abstracts": [
                {"value": "publisher", "source": "Elsevier"},
                {"value": "arxiv", "source": "ARXIV"},
            ],
        }
    )
    unsourced = normalize({**base, "abstracts": [{"value": "first"}, {"value": "second"}]})
    empty_preferred = normalize(
        {**base, "abstracts": [{"value": "", "source": "arXiv"}, {"value": "publisher"}]}
    )

    assert late_arxiv is not None and late_arxiv.abstract == "arxiv"
    assert unsourced is not None and unsourced.abstract == "first"
    assert empty_preferred is not None and empty_preferred.abstract == "publisher"


@pytest.mark.parametrize(
    "metadata",
    [
        {
            "control_number": 10,
            "titles": [{"title": "No optional fields"}],
            "abstracts": [{"value": "Abstract"}],
        },
        {
            "control_number": 11,
            "titles": [{"title": "No arxiv"}],
            "abstracts": [{"value": "Abstract"}],
            "dois": [],
            "publication_info": [],
        },
    ],
)
def test_normalize_tolerates_absent_optional_fields(metadata):
    paper = normalize(metadata)

    assert paper is not None
    assert paper.authors == []
    assert paper.categories == []
    assert paper.arxiv_id == ""
    assert paper.doi == ""
    assert paper.journal == ""
    assert paper.citation_count is None


def test_normalize_uses_first_doi_and_journal_with_title(payload):
    metadata = payload["hits"]["hits"][5]["metadata"]
    paper = normalize(metadata)

    assert paper is not None
    assert paper.doi == "10.1103/PhysRevD.10.275"
    assert paper.journal == "Phys.Rev.D"


def test_normalize_skips_publication_entries_without_a_journal_title():
    paper = normalize(
        {
            "control_number": 12,
            "titles": [{"title": "Erratum first"}],
            "abstracts": [{"value": "Abstract"}],
            "publication_info": [{"year": 1974}, {"journal_title": "Phys.Rev.D"}],
        }
    )
    untitled = normalize(
        {
            "control_number": 13,
            "titles": [{"title": "No journal anywhere"}],
            "abstracts": [{"value": "Abstract"}],
            "publication_info": [{"year": 1974}, {"pubinfo_freetext": "Proceedings"}],
        }
    )

    assert paper is not None and paper.journal == "Phys.Rev.D"
    assert untitled is not None and untitled.journal == ""


def test_arxiv_ids_and_partial_dates_are_stored_verbatim(payload):
    legacy = normalize(payload["hits"]["hits"][4]["metadata"])
    modern = normalize(payload["hits"]["hits"][2]["metadata"])

    assert legacy is not None and modern is not None
    assert legacy.arxiv_id == "hep-ph/0603175"
    assert legacy.earliest_date == "2006-03"
    assert modern.arxiv_id == "1410.8849"
    assert modern.earliest_date == "2014-10-31"


def test_iter_records_yields_usable_limit_and_stops_at_total():
    pages = {
        1: {
            "hits": {
                "total": 3,
                "hits": [
                    {"metadata": {"control_number": 1, "titles": [{"title": "A"}]}},
                    {
                        "metadata": {
                            "control_number": 2,
                            "titles": [{"title": "B"}],
                            "abstracts": [{"value": "B abstract"}],
                        }
                    },
                ],
            }
        },
        2: {
            "hits": {
                "total": 3,
                "hits": [
                    {
                        "metadata": {
                            "control_number": 3,
                            "titles": [{"title": "C"}],
                            "abstracts": [{"value": "C abstract"}],
                        }
                    }
                ],
            }
        },
    }
    calls = []

    def fetcher(query, page, size):
        calls.append((query, page, size))
        return pages[page]

    papers = list(iter_records("test", 2, fetcher, page_size=250))

    assert [paper.inspire_id for paper in papers] == [2, 3]
    assert calls == [("test", 1, 250), ("test", 2, 250)]


def test_iter_records_stops_when_corpus_is_smaller_than_limit():
    calls = []

    def fetcher(query, page, size):
        calls.append(page)
        return {
            "hits": {
                "total": 1,
                "hits": [
                    {
                        "metadata": {
                            "control_number": 7,
                            "titles": [{"title": "Only"}],
                            "abstracts": [{"value": "Only abstract"}],
                        }
                    }
                ],
            }
        }

    papers = list(iter_records("test", 500, fetcher, page_size=250))

    assert [paper.inspire_id for paper in papers] == [7]
    assert calls == [1]


def test_iter_records_warns_and_does_not_cross_result_window(caplog):
    calls = []

    def fetcher(query, page, size):
        calls.append(page)
        return {"hits": {"total": 20_000, "hits": [{"metadata": {}}]}}

    papers = list(iter_records("test", 10_001, fetcher, page_size=1000))

    assert papers == []
    assert calls == list(range(1, 11))
    assert "result window reached" in caplog.text


def test_fetch_page_shapes_request_and_clamps_size():
    requests = []

    def handler(request):
        requests.append(request)
        return ok(request)

    with make_client(handler) as client:
        payload = client.fetch_page("higgs", page=2, size=5000)

    request = requests[0]
    assert request.url.host == "inspirehep.net"
    assert request.url.params["size"] == "1000"
    assert "authors.full_name" in request.url.params["fields"]
    assert "authors," not in request.url.params["fields"]
    assert "hepsearch" in request.headers["user-agent"]
    assert payload["hits"]["total"] == 0


def test_default_page_size_is_moderate():
    requests = []

    def handler(request):
        requests.append(request)
        return ok(request)

    with make_client(handler) as client:
        client.fetch_page("higgs")

    assert requests[0].url.params["size"] == "250"


def test_fetch_page_retries_server_error(monkeypatch):
    statuses = iter([503, 200])
    sleeps = []

    def handler(request):
        return httpx.Response(
            next(statuses), json={"hits": {"total": 0, "hits": []}}, request=request
        )

    monkeypatch.setattr("apps.ingestion.client.time.sleep", sleeps.append)
    with make_client(handler) as client:
        client.fetch_page("higgs")

    assert len(sleeps) == 1


def test_fetch_page_retries_timeout(monkeypatch):
    attempts = iter([httpx.ReadTimeout("timed out"), None])
    sleeps = []

    def handler(request):
        failure = next(attempts)
        if failure:
            raise failure
        return ok(request)

    monkeypatch.setattr("apps.ingestion.client.time.sleep", sleeps.append)
    with make_client(handler) as client:
        client.fetch_page("higgs")

    assert len(sleeps) == 1


def test_fetch_page_honours_retry_after(monkeypatch):
    statuses = iter([429, 200])
    sleeps = []

    def handler(request):
        status = next(statuses)
        if status == 429:
            return httpx.Response(429, headers={"Retry-After": "7"}, request=request)
        return ok(request)

    monkeypatch.setattr("apps.ingestion.client.time.sleep", sleeps.append)
    with make_client(handler) as client:
        client.fetch_page("higgs")

    assert sleeps == [7.0]


def test_fetch_page_backoff_grows_between_attempts(monkeypatch):
    statuses = iter([503, 503, 200])
    sleeps = []

    def handler(request):
        return httpx.Response(
            next(statuses), json={"hits": {"total": 0, "hits": []}}, request=request
        )

    monkeypatch.setattr("apps.ingestion.client.time.sleep", sleeps.append)
    with make_client(handler, max_retries=2) as client:
        client.fetch_page("higgs")

    assert len(sleeps) == 2
    assert sleeps[1] > sleeps[0]


def test_fetch_page_does_not_retry_a_client_error(monkeypatch):
    requests = []
    sleeps = []

    def handler(request):
        requests.append(request)
        return httpx.Response(400, json={"message": "bad query"}, request=request)

    monkeypatch.setattr("apps.ingestion.client.time.sleep", sleeps.append)
    with make_client(handler, max_retries=3) as client, pytest.raises(httpx.HTTPStatusError):
        client.fetch_page("higgs")

    assert len(requests) == 1
    assert sleeps == []


def test_fetch_page_raises_a_clear_error_once_retries_are_exhausted(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(503, json={"message": "unavailable"}, request=request)

    monkeypatch.setattr("apps.ingestion.client.time.sleep", lambda _: None)
    with make_client(handler, max_retries=2) as client:
        with pytest.raises(InspireRequestError) as excinfo:
            client.fetch_page("higgs")

    error = excinfo.value
    assert len(requests) == 3
    assert error.attempts == 3
    assert error.status_code == 503
    assert "inspirehep.net" in str(error)
    assert "503" in str(error)


def test_ingestion_does_not_import_search():
    for path in Path("apps/ingestion").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(not alias.name.startswith("apps.search") for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("apps.search")


def test_fixture_has_required_shapes(payload):
    metadata = [hit["metadata"] for hit in payload["hits"]["hits"]]

    assert any(not item.get("abstracts") for item in metadata)
    assert any(not item.get("dois") and not item.get("publication_info") for item in metadata)
    assert any(len(item.get("abstracts", [])) > 1 for item in metadata)
    assert any("arxiv_eprints" not in item for item in metadata)
    assert any("/" in item.get("arxiv_eprints", [{}])[0].get("value", "") for item in metadata)
    assert any(len(item.get("dois", [])) > 1 for item in metadata)
    assert all(paper.abstract for paper in (normalize(item) for item in metadata) if paper)
