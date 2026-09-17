## Why

The search API is public, unauthenticated, and currently has no `REST_FRAMEWORK`
configuration at all: no throttle, no pagination, no error contract. Embedding a query
is CPU work, so an unthrottled public embedding endpoint is a free denial of service —
and since HS-012 made hybrid the default mode, the *default* request is the one that
embeds. AGENTS.md §6 already asserts "DRF throttling is on", which is not true of the
code; this change makes the document honest.

Five of HS-013's ten acceptance criteria were written before HS-012 shipped and rest on
premises that measurement has since falsified. They are corrected here rather than
implemented as written.

## What Changes

- Search responses become paginated, with a page size and a retrieval depth that are
  separate named settings (depth 60, page 20 — three pages).
- **BREAKING**: the response envelope gains `count`/`next`/`previous`, and `count`
  becomes the total within the retrieval bound rather than the number of results in the
  body. A caller reading `count` as "results in this response" will be wrong on any page
  but the last.
- The documented retrieval ceiling is stated rather than implied. Pagination is bounded
  by how deep each ranking retrieves, not by how many papers match: on the ingested
  corpus, keyword reaches 4,429 rows for `higgs` while semantic reaches 41 and hybrid's
  union of both arms reaches ~74. The semantic figure is the HNSW index's `ef_search`,
  not the query.
- Anonymous throttling is configured with two documented rates: a generous rate for
  keyword ranking, which embeds nothing and issues one indexed query, and a shared
  stricter rate for semantic and hybrid ranking, which both embed.
- The HTML search page is throttled on the same terms as the API. It is a plain Django
  view performing identical embedding and fusion work, so a throttle that covers only
  `/api/search/` is theatre.
- Any unusable `page` parameter — malformed or out of range — is refused consistently
  with a 404, matching what DRF's paginator raises for both from a single code path.
- An overlong `q` is refused with 400 rather than truncated silently by the encoder.
- A `LOGGING` configuration is added, without which "slow searches are logged" has
  nowhere to log to, and slow searches are recorded with their elapsed time.
- `DEBUG=False` is verified to leak no stack trace or internal detail in any error
  response.

### Acceptance criteria corrected

| HS-013 as written | Correction | Evidence |
|---|---|---|
| "Search responses are paginated with a documented default and maximum page size" | Pagination is bounded by retrieval depth, not corpus size, and the ceiling is documented per mode | keyword 4,429 / semantic 41 / hybrid ~74 rows on the real corpus |
| "non-integer page ... returns 400" | All page trouble returns one consistent 404 | DRF raises `NotFound` for `?page=abc` and `?page=999` from the same line; `PageNotAnInteger` subclasses `InvalidPage` |
| "The semantic/hybrid endpoints have a stricter rate than keyword search" | Keyword is generous; semantic and hybrid share one rate | hybrid costs *more* than semantic (embed + two queries), so tiering hybrid below semantic is cost-inverted |
| (absent) | The HTML page is throttled too | `search_page` is not a DRF view and does the same work |
| (absent, and in another capability) | `keyword-search`'s "count matches the results" requirement becomes false | DRF pagination reports a total, not a per-response length |

## Capabilities

### New Capabilities
- `api-hardening`: pagination bounded by retrieval depth, anonymous throttling by
  ranking cost across both the API and the page, a uniform error contract for bad
  parameters, query length limits, operational logging, and opaque errors under
  `DEBUG=False`.

### Modified Capabilities
- `keyword-search`: the response-shape requirement changes. `count` becomes the total
  number of results retrievable within the bound rather than the number carried in the
  body, and the envelope gains pagination links. The requirement that every result
  carries a score, and all ranking behaviour, are unchanged.

## Impact

- `config/settings.py` — new `REST_FRAMEWORK`, `CACHES` and `LOGGING` blocks;
  `SEARCH_RESULT_LIMIT` repurposed as the retrieval depth alongside a new page size and
  query-length bound.
- `apps/search/views.py` — both `search` and `search_page` gain throttling; `search`
  gains pagination; `q` length validation.
- `apps/search/pagination.py` (new) — a paginator preserving `mode`, `degraded` and
  `warning` in the envelope, which DRF's default would drop.
- `apps/search/templates/search/search.html` — pagination controls preserving query and
  mode.
- `openspec/specs/keyword-search/spec.md` — response-shape requirement.
- `board/backlog/HS-013-api-hardening.md` — five acceptance criteria amended.
- No new dependencies. DRF supplies pagination and throttling; the `Retry-After` header
  on a 429 is already emitted by DRF's exception handler.
