# HS-007: Expose keyword search over the corpus

**Status:** backlog
**Depends on:** HS-006

## Story

As a physicist, I want to search the corpus by keywords through an API, so that I
can find relevant papers without leaving my tooling.

## Context

**This is the first card that delivers user value.** Everything before it was
scaffolding.

PostgreSQL full-text search via `django.contrib.postgres` needs no ML
dependencies, so it ships now and becomes the baseline that the semantic work in
HS-011 has to beat. It is also **half of the final hybrid ranker** (AGENTS.md
§3) — do not treat it as throwaway and do not delete it later.

## Acceptance criteria

- [ ] `GET /api/search/?q=<query>` returns JSON ranked by relevance
- [ ] Each result includes id, title, authors, publication date, an abstract
      snippet, and the INSPIRE URL
- [ ] Ranking uses `SearchVector`/`SearchQuery`/`SearchRank` over title and
      abstract, with the title weighted above the abstract
- [ ] A GIN index backs the search; the migration creating it is committed
- [ ] `EXPLAIN` on the search query confirms the index is used, not a sequential
      scan over 5,000 rows
- [ ] A missing or empty `q` returns `400` with a helpful message, not a 500 and
      not the entire corpus
- [ ] A query matching nothing returns `200` with an empty result list
- [ ] Result count is capped, and the cap is a named constant
- [ ] Queries containing punctuation or quotes do not raise
- [ ] Tests cover: a ranked match, title outranking abstract-only, empty `q`,
      zero results, and a punctuation-heavy query
- [ ] Search logic is a function testable without going through the HTTP layer

## Definition of done

- [ ] Acceptance criteria met
- [ ] A real query against the ingested corpus returns sensible papers, with an
      example recorded in the commit body
- [ ] `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` pass
- [ ] Committed as `HS-007: Expose keyword search over the corpus`

## Out of scope

Embeddings and semantic search (HS-009 to HS-011), the HTML page (HS-008),
pagination and throttling (HS-013).
