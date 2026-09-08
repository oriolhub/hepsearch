## 1. Start the card

- [x] 1.1 `git mv board/backlog/HS-005-inspire-client.md board/in-progress/` and set
      its status line to `in-progress`
- [x] 1.2 Confirm a clean baseline: `uv run pytest`, `uv run ruff check .`,
      `uv run ruff format --check .`
- [x] 1.3 `uv add httpx` (never hand-edit `pyproject.toml`), and confirm the lockfile
      records it plus its transitive set

## 2. Capture the fixture first

- [x] 2.1 Write a throwaway capture script (not committed) that queries the live API
      with `fields=` including `authors.full_name`, throttled, with a descriptive
      `User-Agent`
- [x] 2.2 Capture ~10 real records into `apps/ingestion/tests/fixtures/` covering, at
      minimum: no abstract; no DOI **and** no `publication_info`; several abstracts
      from different sources; no `arxiv_eprints` at all; a legacy `hep-ph/…`
      identifier; several DOIs (design D13)
- [x] 2.3 Include one moderately large collaboration paper — enough to prove nothing
      chokes, not the 2,932-author monster
- [x] 2.4 Keep the surrounding envelope (`hits.total`, `hits.hits[]`) intact so the
      fixture can drive pagination tests too, and check the committed size is sane

## 3. Fetching

- [x] 3.1 Write the fetch seam in `apps/ingestion/`: one function that takes query,
      page and size and returns the decoded payload, using a single `httpx.Client`
      holding the `User-Agent` and timeout (design D1, D2)
- [x] 3.2 Build the `fields=` list from exactly what `Paper` needs, requesting
      `authors.full_name` rather than `authors` (design D3)
- [x] 3.3 Clamp the page size to 1000 and default it to 250 (design D4)
- [x] 3.4 Add the retry wrapper: retry timeouts, connection errors, 5xx and 429;
      never other 4xx; honour `Retry-After`, else exponential backoff with jitter;
      bounded attempts, then raise an error naming the request and the failure
      (design D7)
- [x] 3.5 Add the configurable inter-request throttle, separate from backoff, settable
      to zero for tests (design D12)

## 4. Pagination

- [x] 4.1 Write the record iterator, taking the fetcher as a parameter so tests can
      replace it (design D2)
- [x] 4.2 Implement the three stop conditions: `limit` usable records yielded,
      `hits.total` exhausted, and the 10,000-record window (design D5, D6)
- [x] 4.3 Detect the window **before** issuing the request that would cross it, and
      emit a `logging` warning — never `print` (design D6)

## 5. Normalization

- [x] 5.1 Write `normalize()` as a pure function returning an unsaved `Paper` or
      `None`, importing `apps.papers.models` and nothing from `apps.search`
      (design D8)
- [x] 5.2 Implement abstract selection: first case-insensitive `arxiv`-sourced entry
      with non-empty text, else first entry with non-empty text, else `None` — with
      the rule stated in a comment at the point of use (design D9)
- [x] 5.3 Map every optional field through an absence-tolerant guard per the design
      D10 table; never index into a list that may be missing
- [x] 5.4 Take the first DOI, and the first `publication_info` entry that actually
      carries a `journal_title` (design D10)
- [x] 5.5 Store `arxiv_id` and `earliest_date` verbatim, both arXiv id shapes, no
      padding and no added prefix (design D11)

## 6. Tests

- [x] 6.1 Create `apps/ingestion/tests/__init__.py` and the test modules
- [x] 6.2 Normalization against the fixture: a full record maps every field correctly
- [x] 6.3 The no-abstract record returns `None`; empty abstract list and empty
      abstract text likewise
- [x] 6.4 Multi-abstract selection: arXiv wins regardless of position; case-insensitive
      match; falls back to first non-empty when no arXiv entry; an empty arXiv entry
      does not win; the same record normalizes identically twice
- [x] 6.5 The DOI-less, `publication_info`-less, `arxiv_eprints`-less records all
      normalize without raising, yielding `""` and `[]` rather than `None` for strings
      and lists
- [x] 6.6 Legacy `hep-ph/…` and modern identifiers both round-trip verbatim; multiple
      DOIs take the first
- [x] 6.7 Every yielded paper has a non-empty abstract — the interlock HS-006 relies on
      to avoid a bulk insert aborting on the check constraint (design D8)
- [x] 6.8 Pagination with a fake fetcher: skipped records do not reduce the yield;
      stops at `limit`; stops when `hits.total` is exhausted; stops and warns at the
      10,000 window without issuing the crossing request
- [x] 6.9 Retry with a fake fetcher: 5xx then success; timeout then success;
      `Retry-After` honoured; backoff grows; a non-429 4xx is not retried; exhausted
      attempts raise
- [x] 6.10 Page size clamped at 1000; `fields=` always sent and containing
      `authors.full_name`; `User-Agent` present on every request
- [x] 6.11 Confirm `apps/ingestion` imports nothing from `apps.search`
- [x] 6.12 Confirm no test opens a socket and that the normalization tests stay in the
      `pytest -m "not django_db"` lane

## 7. Verify

- [x] 7.1 `uv run pytest` — whole suite green, HS-003 and HS-004 tests included
- [x] 7.2 `uv run pytest -m "not django_db"` still passes without a database
- [x] 7.3 `uv run ruff check .` and `uv run ruff format --check .` clean
- [x] 7.4 `uv run python manage.py check` clean
- [x] 7.5 One manual smoke run against the live API fetching a handful of records,
      confirming the client works end to end — not automated, not a test

## 8. Land it

- [x] 8.1 Amend `AGENTS.md`: §2 gains an httpx row with its rationale and transitive
      set; §4.1 gains dotted sub-field selection and the 10,000-record window; §4.2
      corrects `arxiv_eprints` from "Usually" to ~29% absent on most-cited records
- [x] 8.2 Amend the HS-005 card: `limit` counts yielded records, and the fixture
      criteria are widened to the six shapes in design D13
- [x] 8.3 Amend the HS-006 card: "fetching roughly 5,600" becomes an internal detail
      of the client, since `--limit 5000` now lands ~5,000 rows
- [x] 8.4 Add any new environment variables to `.env.example`
- [x] 8.5 Tick every acceptance criterion, set status to `done`, and
      `git mv board/in-progress/HS-005-inspire-client.md board/done/`
- [x] 8.6 Commit as `HS-005: Build a tested INSPIRE API client`, with a body
      explaining why httpx earned its place, why `authors.full_name` matters, and why
      the abstract rule optimises for stability. No `Co-authored-by` trailer: the
      repository's commit guidelines forbid it and the `commit-msg` hook rejects it
- [x] 8.7 `openspec archive inspire-api-client` and commit the archive as
      `HS-005: Archive the inspire-api-client change`
