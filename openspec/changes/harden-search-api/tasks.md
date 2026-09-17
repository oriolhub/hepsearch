## 1. Amend the card before building

- [x] 1.1 `git mv board/backlog/HS-013-api-hardening.md board/in-progress/`
- [x] 1.2 Amend the pagination criterion: bounded by retrieval depth, not corpus size,
      with the measured per-mode ceiling (keyword 4,429 / semantic 41 / hybrid ~74)
      recorded in the card's Context
- [x] 1.3 Amend the page-error criterion: all unusable `page` values return 404, because
      DRF raises `NotFound` for a malformed and an out-of-range page from one code path
- [x] 1.4 Amend the throttling criterion: keyword generous, semantic and hybrid sharing
      one stricter rate, with the cost table showing hybrid is the most expensive mode
- [x] 1.5 Add a criterion that the HTML page is throttled on the same terms as the API
- [x] 1.6 Record in the card that `count` changes meaning, and that this modifies the
      existing `keyword-search` response-shape requirement

## 2. Settings

- [x] 2.1 Raise `SEARCH_RESULT_LIMIT` to 60 and comment it as the retrieval depth,
      naming its relationship to the page size
- [x] 2.2 Add `SEARCH_PAGE_SIZE = 20` and `SEARCH_MAX_PAGE_SIZE`, each with a comment
- [x] 2.3 Add `SEARCH_QUERY_MAX_CHARS = 1000`, commented with the reason: the encoder
      reads ~512 tokens and silently discards the rest
- [x] 2.4 Add `SEARCH_SLOW_SECONDS`, commented with what it is quiet at on this corpus
- [x] 2.5 Add `THROTTLE_RATE_KEYWORD` and `THROTTLE_RATE_EMBEDDING` as named settings,
      with a comment recording that semantic and hybrid deliberately share one rate
- [x] 2.6 Add the `REST_FRAMEWORK` block wiring the paginator, page size and throttle
      rates; select the mode-specific throttle manually after parsing the mode because
      static DRF throttle classes would rate-limit invalid modes before validation
- [x] 2.7 Add a `CACHES` block naming the local-memory backend, with a comment recording
      that throttle counters are per-process and do not survive a restart, and that a
      shared cache is the second system AGENTS.md section 2 refused
- [x] 2.8 Add a `LOGGING` block that emits `apps.search` and `apps.ingestion` warnings to
      the console

## 3. Pagination

- [x] 3.1 Add `apps/search/pagination.py` with a `PageNumberPagination` subclass whose
      `get_paginated_response` preserves `mode`, `degraded` and `warning` alongside
      `count`, `next`, `previous` and `results`
- [x] 3.2 Document in that module why the subclass exists: DRF's default envelope drops
      those keys, which would make HS-012's "degradation is never silent" requirement
      false
- [x] 3.3 Paginate the ranker's returned list rather than a queryset, so no COUNT query
      is issued and a later page costs no more than the first
- [x] 3.4 Have `search` return the paginated envelope, keeping `.defer(...)` intact on
      both arms

## 4. Throttling

- [x] 4.1 Add two `SimpleRateThrottle` scopes, one for keyword and one shared by semantic
      and hybrid
- [x] 4.2 Select the throttle after `parse_mode`, so an unrecognised mode is refused with
      400 rather than being throttled into a 429
- [x] 4.3 Add a shared helper that applies the same throttle classes to `search_page`,
      documenting that `AnonRateThrottle` needs only `request.user` and `request.META`,
      both present on a plain `HttpRequest`
- [x] 4.4 Return a plain-text 429 with `Retry-After` from the page, matching how
      `search_page` already returns `HttpResponseBadRequest` for an unknown mode
- [x] 4.5 Ensure a throttled page request embeds nothing and ranks nothing

## 5. Request validation and errors

- [x] 5.1 Refuse a query longer than `SEARCH_QUERY_MAX_CHARS` with 400 before any
      embedding is attempted, with a message naming the limit
- [x] 5.2 Ensure every 400 message names the offending parameter
- [x] 5.3 Confirm an unusable `page` yields 404 from the paginator for both the malformed
      and the out-of-range case, and that neither returns 500

## 6. Slow-search logging

- [x] 6.1 Time each search and log a warning when it exceeds `SEARCH_SLOW_SECONDS`,
      carrying elapsed time, mode and query
- [x] 6.2 Escape newline and control characters in the logged query, so public input
      cannot forge a second log record

## 7. Page

- [x] 7.1 Render next/previous navigation that preserves `q` and `mode`
- [x] 7.2 Omit navigation entirely when the results fit on one page
- [x] 7.3 Confirm a `page` value containing HTML is not reflected back as executable
      markup

## 8. Tests

- [x] 8.1 Pagination: a broad query pages; the depth bounds the reachable pages; a narrow
      query is a single page with no next
- [x] 8.2 Query count: a paginated search issues one query per ranking plus the cached
      health count, and the last page costs the same as the first
- [x] 8.3 A degraded hybrid search still reports `degraded` and `warning` on a page beyond
      the first
- [x] 8.4 An unusable `page`, malformed and out of range, both return 404 with no results
- [x] 8.5 Exceeding the rate returns 429 with `Retry-After`, from the API and from the
      page
- [x] 8.6 An unrecognised mode returns 400 rather than 429
- [x] 8.7 An overlong `q` returns 400 and is never embedded, and a query exactly at the
      bound succeeds
- [x] 8.8 A slow search is logged with elapsed time, mode and escaped query; a fast one is
      not
- [x] 8.9 With `DEBUG=False`, no error response carries a stack trace or internal path
- [x] 8.10 Page navigation preserves query and mode; a `page` containing HTML is escaped
- [x] 8.11 Reset the throttle cache between tests, so throttle state cannot leak across
      them the way the embedding provider once did

## 9. Definition of done

- [x] 9.1 `uv run pytest`
- [x] 9.2 `uv run ruff check .`
- [x] 9.3 `uv run ruff format --check .`
- [x] 9.4 Verify by hand against the real corpus with `DEBUG=False` that errors stay
      opaque and that the measured per-mode page ceilings hold
- [x] 9.5 Confirm every amended acceptance criterion has a literal corresponding test,
      not merely a passing suite
- [x] 9.6 `git mv board/in-progress/HS-013-api-hardening.md board/done/` in the same
      commit as the work
- [x] 9.7 Commit as `HS-013: Harden the API with pagination, throttling and clear errors`,
      recording in the body why five criteria were amended and what was measured
