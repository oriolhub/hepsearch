## 1. Board and constants

- [x] 1.1 `git mv board/backlog/HS-012-hybrid-ranking.md board/in-progress/`
- [x] 1.2 Amend the card: replace the exact-identifier comparison query with an
      exact-token query, and state that identifiers are absent from `search_vector` so
      neither ranking retrieves them
- [x] 1.3 Amend the card: state that the candidate depth is bounded by `hnsw.ef_search`
- [x] 1.4 Add `HYBRID_CANDIDATE_DEPTH = 40` to `config/settings.py` with a comment
      naming the `hnsw.ef_search` coupling and that raising it alone has no effect
- [x] 1.5 Add `RRF_K = 5` with a comment recording what was measured on this corpus —
      that k=60 demoted both rankings' first picks below three mid-ranked agreements on
      the paraphrase query — and claiming no more than that

## 2. Fusion function (pure, no database)

- [x] 2.1 Add `reciprocal_rank_fusion(keyword_ids, semantic_ids)` to
      `apps/search/ranking.py`, returning entries carrying paper id, fused score and
      contributing methods, ordered by descending score with a deterministic tie-break
- [x] 2.2 Write `apps/search/tests/test_fusion.py` with no `django_db` mark: dual-hit
      promotion over a single hit at the same position, a single-ranking paper
      surviving, equal fused scores broken deterministically, empty keyword list, empty
      semantic list, both empty
- [x] 2.3 Add a test asserting the fusion function consumes only orderings — it accepts
      no scores and returns the same result for the same id order
- [x] 2.4 Run `uv run pytest apps/search/tests/test_fusion.py` and confirm it passes
      without a database

## 3. Hybrid mode and orchestration

- [x] 3.1 Add `HYBRID = "hybrid"` to `SearchMode` and make `parse_mode(None)` return it
- [x] 3.2 Add a hybrid branch to `views._rank` that runs both rankings at
      `HYBRID_CANDIDATE_DEPTH`, fuses their ids, and hydrates results from the `Paper`
      instances the two querysets already returned — no third query
- [x] 3.3 Attach the fused score and the contributing methods to each hydrated paper,
      and truncate to `SEARCH_RESULT_LIMIT`
- [x] 3.4 Make the hybrid path degrade: reuse the existing `ImportError` handling and
      `_empty_semantic_reason` to detect that semantic ranking could not run, return the
      keyword results with a 200, and carry the reason as a degradation signal
- [x] 3.5 Confirm `mode=semantic` still returns 503 in the same circumstances, unchanged
- [x] 3.6 Confirm a genuinely empty corpus returns 200 with no results and no
      degradation signal

## 4. Response shape

- [x] 4.1 Add a `methods` field to `PaperSearchResultSerializer`, present for hybrid
      results and absent or empty for single-mode results
- [x] 4.2 Add the degradation signal to the search response body, named so a caller can
      distinguish keyword-only results from fused ones
- [x] 4.3 Confirm no per-ranking position appears anywhere in the response

## 5. Page

- [x] 5.1 Add a Hybrid option to the mode select in
      `apps/search/templates/search/search.html` and select it when no mode is given
- [x] 5.2 Render the degraded notice, distinct from the existing "no results" and
      "unavailable" messages
- [x] 5.3 Extend `apps/search/tests/test_page.py`: hybrid is the default selection,
      hybrid ranks the page, and the degraded notice appears without claiming no results
      were found

## 6. Integration tests

- [x] 6.1 Extend `apps/search/tests/test_views.py`: an omitted `mode` reports hybrid
- [x] 6.2 Test that keyword ranking named explicitly is byte-for-byte what it was —
      update the existing assertions that expected keyword as the default rather than
      deleting them
- [x] 6.3 Test hybrid returning results when keyword ranking matches nothing
- [x] 6.4 Test hybrid returning results when semantic ranking contributes nothing
- [x] 6.5 Test hybrid degrading with a 200 when the provider cannot be loaded, and again
      when the corpus carries no compatible embedding, with the degradation reported
- [x] 6.6 Test that a hybrid request issues exactly two queries, using
      `django_assert_num_queries`
- [x] 6.7 Confirm the whole suite still runs offline and loads no real model

## 7. Real-corpus comparison

- [x] 7.1 Confirm `docker compose ps` is healthy and the corpus is ingested and embedded
- [x] 7.2 Run the three comparison queries through the API in all three modes: exact
      token (`monojet`), paraphrase (*"measuring the strength of the Higgs coupling to
      itself"*), mixed (`ATLAS dark matter monojet search`)
- [x] 7.3 Record each query and each mode's returned papers for the commit body
- [x] 7.4 Record why an exact-identifier query was not used

## 7b. Review corrections

Found reviewing the implementation against the project's own conventions, before the
change was archived.

- [x] 7b.1 Call `check_stale_embeddings` on the hybrid path: it is the default mode, so
      omitting it left drift unreported for nearly all traffic
- [x] 7b.2 Log the `ImportError` when hybrid degrades; a fault that only ever answers
      200 must not also be silent
- [x] 7b.3 Reuse `_empty_semantic_reason` from one `_degraded_hybrid` helper instead of
      inlining its predicate three times, and mark the keyword-only survivors there
      rather than in the API view, so the page degrades identically
- [x] 7b.4 Stop the page claiming "No results found." when hybrid degraded and the
      keyword ranking matched nothing: nothing was fully searched
- [x] 7b.5 Pin `RRF_K` with a fusion test that fails at the canonical 60, and pin the
      empty `methods` list that keyword and semantic results now carry

## 8. Definition of done

- [x] 8.1 `uv run pytest`
- [x] 8.2 `uv run ruff check .`
- [x] 8.3 `uv run ruff format --check .`
- [x] 8.4 Verify every acceptance criterion on the card has a literal corresponding test,
      not merely a passing suite
- [x] 8.5 Write `board/backlog/HS-017-index-identifiers-and-authors.md`: extend the
      generated `search_vector` to cover `arxiv_id`, `doi` and author names, with the
      measured evidence that `arXiv:2207.00043` returns zero keyword hits today
- [x] 8.6 `git mv board/in-progress/HS-012-hybrid-ranking.md board/done/` in the same
      commit as the work
- [x] 8.7 Commit as `HS-012: Fuse keyword and semantic results into hybrid ranking`,
      with the three-query comparison and the `RRF_K` justification in the body
