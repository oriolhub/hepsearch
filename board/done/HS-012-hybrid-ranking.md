# HS-012: Fuse keyword and semantic results into hybrid ranking

**Status:** in progress
**Depends on:** HS-011

## Story

As a physicist, I want one search that handles both exact terms and vague
descriptions, so that I do not have to guess which search mode my question needs.

## Context

AGENTS.md §3 states why this exists: pure vector search fails on exact tokens
(`ATLAS`, `arXiv:2609.04868`, an author's surname), and keyword search fails on
paraphrase. Neither alone is good enough, so the two are fused.

Reciprocal Rank Fusion is the default because it combines *ranks* rather than
scores, so it needs no score normalization between two incomparable scales.

The fusion maths must be a pure function — testable with plain lists, no database
and no model.

## Acceptance criteria

- [x] `mode=hybrid` fuses keyword and semantic results, and becomes the default
      for both the API and the page
- [x] Fusion is implemented as a pure function over two ranked id lists
- [x] A paper appearing in both lists outranks one appearing in only a single list
      at a comparable position
- [x] Papers found by only one method still appear in the results
- [x] The RRF `k` constant and any per-method weights are named constants,
      configurable, and their values justified in a comment
- [x] Each result reports which method(s) found it and its fused score
- [x] Both underlying searches run per request without an N+1 query pattern
- [x] Unit tests for the fusion function alone, with no database: dual-hit
      promotion, single-method survival, tie handling, empty input on either side
- [x] Integration tests confirm hybrid returns results when either method alone
      returns none
- [x] A documented comparison on the real corpus of at least three queries — one
      exact-token, one paraphrase, one mixed — showing hybrid is not worse. The
      identifier query is excluded because `arxiv_id`, `doi` and authors are not
      present in the current `search_vector`, so neither arm can retrieve them.
- [x] Candidate collection is bounded by pgvector's `hnsw.ef_search` (currently 40);
      increasing the SQL limit alone has no effect

## Definition of done

- [x] Acceptance criteria met
- [x] The three-query comparison is recorded in the commit body
- [x] `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` pass
- [x] Committed as `HS-012: Fuse keyword and semantic results into hybrid ranking`

## Out of scope

Cross-encoder re-ranking, learned weights, personalization (a non-goal),
evaluation harnesses with labelled relevance judgements, identifier and author
indexing (tracked separately).
