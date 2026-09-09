from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable, Iterator, Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from django.conf import settings

from apps.papers.models import Paper

logger = logging.getLogger(__name__)

INSPIRE_URL = "https://inspirehep.net/api/literature"
USER_AGENT = "hepsearch/0.1 (INSPIRE literature ingestion)"
FIELDS = ",".join(
    (
        "control_number",
        "titles",
        "abstracts",
        "authors.full_name",
        "arxiv_eprints",
        "dois",
        "publication_info",
        "earliest_date",
        "citation_count",
    )
)
MAX_PAGE_SIZE = 1000
MAX_RESULT_WINDOW = 10_000
TOO_MANY_REQUESTS = 429
SERVER_ERROR = 500


class InspireRequestError(RuntimeError):
    """Raised when a request still fails after every permitted attempt."""

    def __init__(self, url: str, attempts: int, cause: Exception) -> None:
        response = getattr(cause, "response", None)
        self.status_code = getattr(response, "status_code", None)
        self.url = url
        self.attempts = attempts
        detail = f"HTTP {self.status_code}" if self.status_code else type(cause).__name__
        super().__init__(f"{url} failed after {attempts} attempt(s): {detail} ({cause})")


def _setting(name: str, default: Any) -> Any:
    return getattr(settings, name, default)


def _is_retryable(status_code: int) -> bool:
    # A rate limit or a server error may succeed on repetition; no other 4xx will.
    return status_code == TOO_MANY_REQUESTS or status_code >= SERVER_ERROR


def _retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())


def _sleep_for_retry(response: httpx.Response | None, attempt: int, base: float) -> None:
    retry_after = _retry_after(response.headers.get("Retry-After") if response else None)
    # Jitter stays below `base` so successive delays always grow.
    delay = (
        retry_after if retry_after is not None else base * (2**attempt) + random.uniform(0, base)
    )
    time.sleep(delay)


class InspireClient:
    def __init__(
        self,
        *,
        timeout: float | None = None,
        throttle: float | None = None,
        max_retries: int | None = None,
        backoff_base: float | None = None,
        page_size: int | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.timeout = timeout if timeout is not None else _setting("INSPIRE_TIMEOUT_SECONDS", 30.0)
        self.throttle = (
            throttle if throttle is not None else _setting("INSPIRE_THROTTLE_SECONDS", 1.0)
        )
        self.max_retries = (
            max_retries if max_retries is not None else _setting("INSPIRE_MAX_RETRIES", 3)
        )
        self.backoff_base = (
            backoff_base if backoff_base is not None else _setting("INSPIRE_BACKOFF_BASE", 1.0)
        )
        configured_size = page_size if page_size is not None else _setting("INSPIRE_PAGE_SIZE", 250)
        self.page_size = min(max(1, int(configured_size)), MAX_PAGE_SIZE)
        self._client = client or httpx.Client(timeout=self.timeout)
        self._owns_client = client is None
        self._last_request: float | None = None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> InspireClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _throttle(self) -> None:
        if self._last_request is not None:
            remaining = self.throttle - (time.monotonic() - self._last_request)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request = time.monotonic()

    def fetch_page(self, query: str, page: int = 1, size: int | None = None) -> dict[str, Any]:
        page_size = min(max(1, int(size if size is not None else self.page_size)), MAX_PAGE_SIZE)
        params = {
            "q": query,
            "fields": FIELDS,
            "size": page_size,
            "page": page,
            "sort": "mostrecent",
        }
        attempts = self.max_retries + 1
        last_error: Exception
        for attempt in range(attempts):
            self._throttle()
            response: httpx.Response | None = None
            try:
                # The User-Agent is set per request rather than on the client so that an
                # injected client (the seam the tests replace) is identified too.
                response = self._client.get(
                    INSPIRE_URL,
                    params=params,
                    headers={"User-Agent": USER_AGENT},
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as error:
                if not _is_retryable(error.response.status_code):
                    raise
                last_error = error
            except httpx.RequestError as error:
                last_error = error
            if attempt < attempts - 1:
                _sleep_for_retry(response, attempt, self.backoff_base)
        raise InspireRequestError(INSPIRE_URL, attempts, last_error) from last_error

    def iter_papers(self, query: str, limit: int) -> Iterator[Paper | None]:
        yield from iter_records(query, limit, self.fetch_page, page_size=self.page_size)


PageFetcher = Callable[[str, int, int], Mapping[str, Any]]


def iter_records(
    query: str,
    limit: int,
    fetcher: PageFetcher,
    *,
    page_size: int = 250,
) -> Iterator[Paper | None]:
    """Yield one result per fetched record: a `Paper`, or `None` for a record with no
    usable abstract. `limit` counts only the `Paper` results, so a caller receives
    approximately `limit` papers; it must filter out the `None`s before writing.
    """
    if limit <= 0:
        return
    page_size = min(max(1, page_size), MAX_PAGE_SIZE)
    yielded = 0
    page = 1
    total: int | None = None
    while yielded < limit:
        offset = (page - 1) * page_size
        if offset >= MAX_RESULT_WINDOW:
            logger.warning("INSPIRE result window reached for query %r; stopping early", query)
            return
        payload = fetcher(query, page, page_size)
        hits = payload.get("hits", {})
        total = hits.get("total", total)
        records = hits.get("hits", [])
        if not records:
            return
        for hit in records:
            paper = normalize(hit.get("metadata", hit))
            yield paper
            if paper is not None:
                yielded += 1
                if yielded >= limit:
                    return
        if total is not None and offset + len(records) >= total:
            return
        page += 1


def _first_value(items: Any) -> str:
    if isinstance(items, list) and items and isinstance(items[0], Mapping):
        value = items[0].get("value", "")
        return value if isinstance(value, str) else ""
    return ""


def _first_title(items: Any) -> str:
    if isinstance(items, list) and items and isinstance(items[0], Mapping):
        value = items[0].get("title", "")
        return value if isinstance(value, str) else ""
    return ""


def _abstract(metadata: Mapping[str, Any]) -> str | None:
    abstracts = metadata.get("abstracts")
    if not isinstance(abstracts, list):
        return None
    usable = [
        item
        for item in abstracts
        if isinstance(item, Mapping) and isinstance(item.get("value"), str) and item["value"]
    ]
    # Prefer the first non-empty arXiv abstract; otherwise use the first non-empty entry.
    for item in usable:
        if str(item.get("source", "")).casefold() == "arxiv":
            return item["value"]
    return usable[0]["value"] if usable else None


def normalize(metadata: Mapping[str, Any]) -> Paper | None:
    abstract = _abstract(metadata)
    if abstract is None:
        return None
    titles = metadata.get("titles")
    title = _first_title(titles)
    authors = metadata.get("authors")
    author_names = (
        [
            author["full_name"]
            for author in authors
            if isinstance(author, Mapping) and isinstance(author.get("full_name"), str)
        ]
        if isinstance(authors, list)
        else []
    )
    arxiv = metadata.get("arxiv_eprints")
    first_arxiv = (
        arxiv[0] if isinstance(arxiv, list) and arxiv and isinstance(arxiv[0], Mapping) else {}
    )
    publication_info = metadata.get("publication_info")
    # publication_info entries without a journal_title carry no journal at all, so
    # scan for the first entry that has one rather than taking entry zero blindly.
    journal = (
        next(
            (
                entry["journal_title"]
                for entry in publication_info
                if isinstance(entry, Mapping) and isinstance(entry.get("journal_title"), str)
            ),
            "",
        )
        if isinstance(publication_info, list)
        else ""
    )
    categories = first_arxiv.get("categories", [])
    arxiv_id = first_arxiv.get("value", "")
    earliest_date = metadata.get("earliest_date", "")
    return Paper(
        inspire_id=metadata["control_number"],
        title=title,
        abstract=abstract,
        authors=author_names,
        categories=categories if isinstance(categories, list) else [],
        arxiv_id=arxiv_id if isinstance(arxiv_id, str) else "",
        doi=_first_value(metadata.get("dois")),
        journal=journal,
        earliest_date=earliest_date if isinstance(earliest_date, str) else "",
        citation_count=metadata.get("citation_count"),
    )
