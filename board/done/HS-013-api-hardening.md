# HS-013: Harden the API with pagination, throttling and clear errors

**Status:** done
**Depends on:** HS-012

## Story

As an API consumer, I want paginated results, predictable limits, and error
responses I can act on, so that the API is usable by something other than a demo.

## Context

HS-012 made hybrid the default. On the real 5,000-paper corpus, keyword retrieval
reaches 4,429 rows for `higgs`, semantic retrieval reaches 41 rows because the
HNSW scan uses `ef_search=40`, and the hybrid union reaches about 74 rows. Pagination
therefore bounds the retrieved ranking depth; it does not expose the entire corpus.
Keyword is cheapest, semantic embeds once, and hybrid is most expensive because it
embeds and runs both ranking arms.

## Acceptance criteria

- [x] Search responses are paginated with a documented page size of 20 and retrieval
      depth of 60; pagination is bounded by the ranking depth, not the full corpus
- [x] Requesting any unusable page (malformed or beyond the reachable depth) returns
      `404` consistently, never a 500
- [x] Anonymous DRF throttling is configured with a documented rate
- [x] Exceeding the rate returns `429` with a `Retry-After` header
- [x] Keyword requests use a generous anonymous rate; semantic and hybrid share one
      stricter rate because both embed the query
- [x] The HTML search page is throttled on the same terms as the API
- [x] Invalid parameters (`q` missing, unknown `mode`, overlong `q`, out-of-range
      page size) return `400` with a message naming the offending parameter; unusable
      page values consistently return `404`
- [x] No stack trace or internal detail leaks in any error response with
      `DEBUG=False`
- [x] An overlong `q` is rejected with `400` rather than embedded
- [x] Slow searches are logged with the query and elapsed time
- [x] Tests cover each error case and assert the throttle returns `429`
- [x] `count` reports the total retrievable within the configured depth, while each
      response carries only one page; this modifies the keyword-search response spec

## Definition of done

- [x] Acceptance criteria met
- [x] Verified with `DEBUG=False` that errors stay opaque
- [x] `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` pass
- [x] Committed as `HS-013: Harden the API with pagination, throttling and clear errors`

## Out of scope

Authentication and API keys (the API is public), caching layers, Redis, rate
limiting by API key.
