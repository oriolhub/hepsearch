# HS-012: Fuse keyword and semantic results into hybrid ranking

**Status:** backlog
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

- [ ] `mode=hybrid` fuses keyword and semantic results, and becomes the default
      for both the API and the page
- [ ] Fusion is implemented as a pure function over two ranked id lists
- [ ] A paper appearing in both lists outranks one appearing in only a single list
      at a comparable position
- [ ] Papers found by only one method still appear in the results
- [ ] The RRF `k` constant and any per-method weights are named constants,
      configurable, and their values justified in a comment
- [ ] Each result reports which method(s) found it and its fused score
- [ ] Both underlying searches run per request without an N+1 query pattern
- [ ] Unit tests for the fusion function alone, with no database: dual-hit
      promotion, single-method survival, tie handling, empty input on either side
- [ ] Integration tests confirm hybrid returns results when either method alone
      returns none
- [ ] A documented comparison on the real corpus of at least three queries — one
      exact-identifier, one paraphrase, one mixed — showing hybrid is not worse
      than either mode

## Definition of done

- [ ] Acceptance criteria met
- [ ] The three-query comparison is recorded in the commit body
- [ ] `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` pass
- [ ] Committed as `HS-012: Fuse keyword and semantic results into hybrid ranking`

## Out of scope

Cross-encoder re-ranking, learned weights, personalization (a non-goal),
evaluation harnesses with labelled relevance judgements.
