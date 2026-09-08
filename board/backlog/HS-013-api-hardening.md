# HS-013: Harden the API with pagination, throttling and clear errors

**Status:** backlog
**Depends on:** HS-012

## Story

As an API consumer, I want paginated results, predictable limits, and error
responses I can act on, so that the API is usable by something other than a demo.

## Context

The API is public and read-only, so throttling is the only protection it has
(AGENTS.md §6). Embedding a query is CPU work, which makes the semantic endpoint
the expensive one — an unthrottled public embedding endpoint is a free denial of
service.

## Acceptance criteria

- [ ] Search responses are paginated with a documented default and maximum page size
- [ ] Requesting a page beyond the end returns an empty page or `404`
      consistently, never a 500
- [ ] Anonymous DRF throttling is configured with a documented rate
- [ ] Exceeding the rate returns `429` with a `Retry-After` header
- [ ] The semantic/hybrid endpoints have a stricter rate than keyword search,
      because embedding costs CPU
- [ ] Invalid parameters (`q` missing, unknown `mode`, non-integer page,
      out-of-range page size) return `400` with a message naming the offending
      parameter
- [ ] No stack trace or internal detail leaks in any error response with
      `DEBUG=False`
- [ ] An overlong `q` is rejected with `400` rather than embedded
- [ ] Slow searches are logged with the query and elapsed time
- [ ] Tests cover each error case and assert the throttle returns `429`

## Definition of done

- [ ] Acceptance criteria met
- [ ] Verified with `DEBUG=False` that errors stay opaque
- [ ] `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` pass
- [ ] Committed as `HS-013: Harden the API with pagination, throttling and clear errors`

## Out of scope

Authentication and API keys (the API is public), caching layers, Redis, rate
limiting by API key.
