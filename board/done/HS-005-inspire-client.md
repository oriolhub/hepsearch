# HS-005: Build a tested INSPIRE API client

**Status:** done
**Depends on:** HS-004

## Story

As a developer, I want a small client that fetches and normalizes INSPIRE
literature records, so that the messy external JSON is translated into clean
domain data in exactly one place.

## Context

The verified API contract is in AGENTS.md §4.1 — in particular `size` caps at
**1000**, `fields=` must always be used to trim responses, and the API returns no
rate-limit headers (which is not a licence to hammer it).

This card produces a client only: it fetches and normalizes, it does not touch
the database. That separation is what makes it testable without Postgres.

## Acceptance criteria

- [x] Lives in `apps/ingestion/` and imports nothing from `apps.search`
- [x] Exposes a function/class that takes an INSPIRE query and a limit, and
      yields normalized records
- [x] Requests always send `fields=` limited to what `Paper` needs
- [x] Page size is clamped to 1000; requesting more must not produce a 400
- [x] Pagination continues until the yielded limit or `hits.total` is reached,
      stopping before the API's 10,000-record result window
- [x] A descriptive `User-Agent` identifying this project is sent on every request
- [x] A delay between requests throttles politely; the delay is configurable
- [x] Transient failures (timeouts, 5xx, 429) are retried with backoff a bounded
      number of times, then raise a clear error
- [x] Normalization returns `None`/skips when `abstracts` is missing or empty
- [x] Normalization never raises on a record missing `dois`, `publication_info`,
      `arxiv_eprints`, `authors`, or `inspire_categories`; multiple abstracts use
      the first non-empty arXiv-sourced value, otherwise the first non-empty value
- [x] When several abstracts exist, the selection rule is deterministic and
      documented in a comment
- [x] Tests run entirely offline against a committed JSON fixture of real
      responses, including **one record with no abstract**, **one with no DOI
      and no publication_info**, a multi-abstract record, a record without
      `arxiv_eprints`, a legacy arXiv id, and multiple DOIs
- [x] No test performs a network request

## Definition of done

- [x] Acceptance criteria met
- [x] `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` pass
- [ ] Committed as `HS-005: Build a tested INSPIRE API client`

## Out of scope

Writing to the database (HS-006), embeddings (HS-009), HEPData (dropped — see
AGENTS.md §4.3).
