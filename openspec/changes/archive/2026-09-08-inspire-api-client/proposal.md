## Why

`apps/papers` now has a table (HS-004) and nothing to put in it. Board card
**HS-005 — Build a tested INSPIRE API client** builds the only component in the
system that is allowed to know INSPIRE's JSON field names, translating a messy,
deeply-optional external payload into clean domain objects in exactly one place
(`AGENTS.md §3`).

Separating this from HS-006's database writes is what makes it testable: fetching
and normalizing have no dependency on Postgres, so the rules that decide *which
abstract*, *which DOI*, and *what happens when a field is simply absent* can be
tested directly against a committed fixture.

A live spike (11 throttled read-only calls, documented in `design.md`) measured the
API's real behaviour and produced three findings that neither this card nor
`AGENTS.md` records — one of which changes the corpus download from gigabytes to
tens of megabytes.

## What Changes

- Add an INSPIRE client to `apps/ingestion/`: a paged fetcher plus a pure
  normalizer that yields unsaved `Paper` instances, or skips a record entirely.
- Request `authors.full_name` rather than `authors`. INSPIRE supports **dotted
  sub-field selection**, and using it cuts the payload for the most-cited slice to
  **6.4%** of its former size — the difference between a multi-gigabyte and an
  ~84 MB corpus download.
- Default to a page size of **250**, keeping 1000 only as the hard clamp the card
  requires. A 1000-record page is a 15 MB JSON parse on the light slice and far
  worse on collaboration-heavy pages.
- Stop pagination on any of three conditions: the requested count of *usable*
  records is reached, `hits.total` is exhausted, or the API's **10,000-record
  result window** would be exceeded. The last case logs a warning rather than
  failing, so HS-006's summary can report the shortfall.
- Retry timeouts, connection errors, 5xx and 429 a bounded number of times,
  honouring `Retry-After` when present and otherwise backing off exponentially
  with jitter, then raise a clear error. **httpx does not do this for us** — its
  transport-level `retries` covers connection failures only.
- Select one abstract deterministically when a record carries several — **33% of
  measured records do** — preferring the arXiv-sourced entry, since stability
  across re-ingests matters more than which near-identical variant wins.
- Skip records with no usable abstract, returning `None` rather than a `Paper`.
- **BREAKING (dependency):** add `httpx` as a runtime dependency. `AGENTS.md §2`
  keeps an explicit ledger of what was deliberately *not* added, so the stack
  table gains a row and a rationale in the same commit.
- **BREAKING (card amendment):** `limit` counts records **yielded**, not records
  fetched. HS-006 currently asserts both that `--limit 5000` lands ~5,000 papers
  and that reaching 5,000 requires fetching ~5,600; under this change the client
  absorbs that arithmetic and HS-006's wording is corrected.
- **BREAKING (card amendment):** the HS-005 fixture requirement is widened. The
  card asks for one abstract-less record and one lacking DOI and `publication_info`;
  the measurements show the fixture must also carry a multi-abstract record, a
  record with no `arxiv_eprints` at all, an old-style `hep-ph/…` identifier, and a
  record with multiple DOIs, because those are the branches the selection rules
  actually execute.
- Amend `AGENTS.md`: §2 gains httpx; §4.1 gains dotted sub-field selection and the
  10,000-record window; §4.2 corrects `arxiv_eprints` from "Usually" present to
  **absent on ~29%** of most-cited records.

Deliberately **not** in scope: any database write, the management command, progress
reporting or `--dry-run` (all HS-006); embeddings (HS-009); search (HS-007).

## Capabilities

### New Capabilities
- `inspire-client`: fetching literature records from the INSPIRE-HEP API — request
  shaping, polite throttling, bounded retry, pagination and its stop conditions —
  and normalizing those records into domain objects, including every rule that
  decides which value wins and when a record is unusable.

### Modified Capabilities
<!-- None. `paper-model` (HS-004) is unchanged: this change writes no migration and
     alters no field. It consumes the model as-is by constructing unsaved instances. -->

## Impact

- **New code:** an INSPIRE client module and a normalizer in `apps/ingestion/`,
  their tests under `apps/ingestion/tests/`, and a committed JSON fixture of real
  INSPIRE responses.
- **Dependencies:** `httpx` added (pulls in httpcore, h11, anyio, certifi, idna,
  sniffio). No other package is required — retry and backoff are hand-written.
- **Settings:** the throttle delay, request timeout, page size and retry budget
  become configurable; anything exposed as an environment variable must land in
  `.env.example`.
- **Docs:** `AGENTS.md` §2, §4.1 and §4.2 amended as above.
- **Board:** `board/backlog/HS-005-inspire-client.md` moves to `board/done/`, with
  its `limit` semantics and fixture criteria corrected; HS-006's card is amended
  for the `limit` change.
- **Network:** the implementation talks to the live API, but **no test does**. The
  fetch boundary is a seam the tests replace, so the default `pytest` run stays
  offline and fast.
- **Downstream contract:** HS-006 receives unsaved `Paper` instances ready for
  `bulk_create(update_conflicts=...)`, and must filter nothing further — the
  normalizer has already guaranteed every yielded paper satisfies the abstract
  check constraint.
