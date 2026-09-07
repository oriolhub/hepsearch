# HS-005: Build a tested INSPIRE API client

**Status:** backlog
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

- [ ] Lives in `apps/ingestion/` and imports nothing from `apps.search`
- [ ] Exposes a function/class that takes an INSPIRE query and a limit, and
      yields normalized records
- [ ] Requests always send `fields=` limited to what `Paper` needs
- [ ] Page size is clamped to 1000; requesting more must not produce a 400
- [ ] Pagination continues until the limit or `hits.total` is reached
- [ ] A descriptive `User-Agent` identifying this project is sent on every request
- [ ] A delay between requests throttles politely; the delay is configurable
- [ ] Transient failures (timeouts, 5xx, 429) are retried with backoff a bounded
      number of times, then raise a clear error
- [ ] Normalization returns `None`/skips when `abstracts` is missing or empty
- [ ] Normalization never raises on a record missing `dois`, `publication_info`,
      `arxiv_eprints`, `authors`, or `inspire_categories`
- [ ] When several abstracts exist, the selection rule is deterministic and
      documented in a comment
- [ ] Tests run entirely offline against a committed JSON fixture of real
      responses, including **one record with no abstract** and **one with no DOI
      and no publication_info**
- [ ] No test performs a network request

## Definition of done

- [ ] Acceptance criteria met
- [ ] `uv run pytest` and `uv run ruff check .` pass
- [ ] Committed as `HS-005: Build a tested INSPIRE API client`

## Out of scope

Writing to the database (HS-006), embeddings (HS-009), HEPData (dropped — see
AGENTS.md §4.3).
