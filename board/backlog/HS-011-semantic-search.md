# HS-011: Add semantic search

**Status:** backlog
**Depends on:** HS-010

## Story

As a physicist, I want to describe what I am looking for in my own words and get
relevant papers back, so that I find work that does not happen to share my
vocabulary.

## Context

**This is the point of the project.** The user's query is embedded with the same
provider used for the corpus, then compared by cosine distance in PostgreSQL.

Keyword search from HS-007 stays in place and untouched — it becomes half of the
hybrid ranker in HS-012.

## Acceptance criteria

- [ ] `GET /api/search/?q=<query>&mode=semantic` returns papers ranked by cosine
      similarity
- [ ] `mode` defaults to the existing keyword behaviour, so HS-007 and HS-008 do
      not change behaviour
- [ ] The query is embedded with the same provider and model used for the corpus
- [ ] A mismatch between the query model and the stored `embedding_model` is
      detected and reported, not silently ranked
- [ ] Ordering happens in the database via the pgvector distance operator, not by
      loading rows into Python
- [ ] `EXPLAIN` confirms the ANN index is used
- [ ] Each result exposes its similarity score
- [ ] Papers with a null embedding are excluded rather than crashing the query
- [ ] An unknown `mode` value returns `400`, not a 500
- [ ] Tests with the fake provider assert that the nearest vector ranks first and
      that null-embedding papers are excluded
- [ ] A documented manual check: a paraphrased query with no shared keywords
      returns relevant papers that keyword search misses — the exact query and
      its results are recorded

## Definition of done

- [ ] Acceptance criteria met
- [ ] The paraphrase comparison against keyword mode is recorded in the commit body
- [ ] `uv run pytest` and `uv run ruff check .` pass
- [ ] Committed as `HS-011: Add semantic search`

## Out of scope

Fusing the two modes (HS-012), LLM answer generation (v2, AGENTS.md §1),
re-ranking models.
