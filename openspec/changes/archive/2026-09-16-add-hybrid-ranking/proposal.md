## Why

Keyword ranking and semantic ranking each fail on the queries the other handles well:
vector similarity cannot pin an exact token, and full-text matching cannot follow a
paraphrase. HS-012 fuses the two into one default ranking so a physicist does not have
to guess which mode their question needs.

A measurement against the ingested 5,000-paper corpus, run before any code was written,
invalidated three assumptions the board card was written on. This proposal carries the
corrected versions, because each one would otherwise have shipped as a plausible-looking
constant that silently did the wrong thing:

- **Candidate depth is capped by the vector index, not by a setting.** The HNSW index
  returns at most `hnsw.ef_search` rows (default 40) regardless of the SQL `LIMIT`.
  A `HYBRID_CANDIDATE_DEPTH` above 40 is a placebo.
- **`RRF_K = 60`, the canonical constant, measurably degrades the flagship query.** On
  *"measuring the strength of the Higgs coupling to itself"*, fusion at k=60 promoted
  three mid-ranked papers that both arms agreed on above both arms' on-target first
  picks. k=60 is tuned for fusing many redundant retrieval systems over deep lists;
  this system fuses two deliberately complementary arms over 40 candidates, where
  agreement is a weak signal and top rank is a strong one.
- **Exact identifiers are not a ranking problem at all.** `search_vector` is built from
  title and abstract only, so `arXiv:2207.00043` returns zero keyword hits. Fusion
  cannot rank a paper neither arm retrieved. The card's exact-identifier comparison
  measures a retrieval path that does not exist.

## What Changes

- Add a `hybrid` ranking mode that fuses the existing keyword and semantic rankings with
  Reciprocal Rank Fusion over ranked id lists.
- **BREAKING** `hybrid` becomes the ranking used when no `mode` parameter is supplied,
  for both the API and the search page. Callers omitting `mode` will observe different
  papers in a different order, scored on a different scale.
- Fusion is a pure function over two ranked id lists, with no database and no model.
- When semantic ranking cannot run, `hybrid` degrades to keyword-only results and says
  so in the response, rather than failing. `mode=semantic` continues to return 503.
  Without this, a default `uv sync` install — where the embedding extra is absent —
  would answer the default search with 503 where it answers 200 today.
- Each result reports which arm or arms found it, alongside its fused score.
- The search page offers Hybrid, selects it by default, and renders the degraded notice.
- Amend the card's real-corpus comparison: the exact-identifier query is replaced by an
  exact-token query, because identifiers are not retrievable by either arm.

Not included, deliberately: per-method weights (no evidence any are needed), per-request
`hnsw.ef_search` tuning (a pgvector tuning concern, not a ranking one), and indexing
identifiers or author names for exact lookup (a separate retrieval-coverage change).

## Capabilities

### New Capabilities
- `hybrid-search`: Fusing two independent rankings into one ordering — the fusion
  function and its constants, candidate collection bounded by the vector index, how a
  result reports its provenance, degradation when one arm is unavailable, and the
  evidence required to justify the fusion constant against the real corpus.

### Modified Capabilities
- `keyword-search`: The requirement that an absent `mode` parameter selects keyword
  ranking is replaced — an absent `mode` now selects hybrid ranking. Keyword ranking
  remains reachable by naming it explicitly, and its own behaviour is unchanged.

## Impact

- `config/settings.py` — two new constants (`HYBRID_CANDIDATE_DEPTH`, `RRF_K`).
- `apps/search/modes.py` — a third mode, and a changed default.
- `apps/search/ranking.py` — the fusion function, alongside the existing rankers.
- `apps/search/views.py` — hybrid orchestration, degradation handling; the existing
  503 path for `mode=semantic` is unchanged.
- `apps/search/serializers.py` — a `methods` field on each result.
- `apps/search/templates/search/search.html` — Hybrid option, default selection,
  degraded notice.
- Existing tests asserting `mode == "keyword"` for an absent `mode` parameter change
  in the same commit.
- No new dependency, no migration, no schema change.
- `apps/ingestion` is untouched, and `apps/search` continues not to import it.
