# HS-007: Expose keyword search over the corpus

**Status:** done
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

## Decisions

- The search vector is a database-generated, stored column (`GeneratedField`,
  `db_persist=True`) rather than an expression index, so a query is an ordinary
  filter on an ordinary indexed column and cannot silently stop matching the index
  the way an expression index can. See `openspec/changes/fulltext-search-api/design.md`.
- Title (weight A) outranks abstract (weight B) via `SearchVector`'s weight
  parameter baked into the generated column; ranking relies on `SearchRank`'s
  default weight array rather than a pinned custom one.
- User input is parsed with `websearch_to_tsquery`, giving quoted phrases,
  `-exclusion` and `or` for free and guaranteeing no input can raise.
- **Author names are explicitly out of scope for this card.** `authors` is a
  `text[]` and `array_to_string` is STABLE, so it cannot go into a generated
  column without an `IMMUTABLE` SQL wrapper. AGENTS.md §3 names author-name
  lookup as something the keyword half is meant to carry — this is a real,
  knowingly-taken gap that HS-012 (hybrid ranking) inherits.
- `publication_date` pads partial `earliest_date` values (`YYYY`, `YYYY-MM`) to
  the first of the period, in the serializer only — no model or ingestion change.
- The `EXPLAIN` acceptance criterion was verified once, by hand, rather than as an
  automated test (see the verification note below); asserting a query plan in a
  test is brittle and would fail on a different corpus size or after `ANALYZE`.

## Acceptance criteria

- [x] `GET /api/search/?q=<query>` returns JSON ranked by relevance
- [x] Each result includes id, title, authors, publication date, an abstract
      snippet, and the INSPIRE URL
- [x] Ranking uses `SearchVector`/`SearchQuery`/`SearchRank` over title and
      abstract, with the title weighted above the abstract
- [x] A GIN index backs the search; the migration creating it is committed
- [x] `EXPLAIN` on the search query confirms the index is used, not a sequential
      scan over 5,000 rows
- [x] A missing or empty `q` returns `400` with a helpful message, not a 500 and
      not the entire corpus
- [x] A query matching nothing returns `200` with an empty result list
- [x] Result count is capped, and the cap is a named constant
- [x] Queries containing punctuation or quotes do not raise
- [x] Tests cover: a ranked match, title outranking abstract-only, empty `q`,
      zero results, and a punctuation-heavy query
- [x] Search logic is a function testable without going through the HTTP layer

## Definition of done

- [x] Acceptance criteria met
- [x] A real query against the ingested corpus returns sensible papers, with an
      example recorded in the commit body
- [x] `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` pass
- [x] Committed as `HS-007: Expose keyword search over the corpus`

## Verification note (EXPLAIN)

Run by hand against the live 5,000-row corpus, after `ANALYZE`:

- `self-coupling` (9 matching rows, selective) → `Bitmap Index Scan on
  paper_search_vector_gin`
- `higgs` (4,430 matching rows, 88.6% of the corpus, not selective) → `Seq Scan`,
  which is PostgreSQL's planner correctly choosing not to use the index rather
  than the index being broken. This is exactly the risk anticipated in
  `openspec/changes/fulltext-search-api/design.md` and is why the check is a
  manual verification rather than an automated test.

## Out of scope

Embeddings and semantic search (HS-009 to HS-011), the HTML page (HS-008),
pagination and throttling (HS-013), author-name search (deferred to HS-012, see
Decisions above).