## Why

HS-010 filled the corpus with 384-dimensional vectors and indexed them, but
nothing reads them. A user still cannot ask a question in their own words — a
query that paraphrases a paper's abstract without sharing its vocabulary returns
nothing from the keyword ranker. Turning those stored vectors into a ranking is
the point of the project (AGENTS.md §1); until it ships, the embedding pipeline
is write-only.

## What Changes

- `GET /api/search/?q=<query>&mode=semantic` ranks papers by cosine distance
  against the query's embedding, ordered in PostgreSQL by the pgvector operator
  so the HNSW index does the work.
- A `mode` parameter is introduced with a `KEYWORD` / `SEMANTIC` enum. It
  defaults to keyword, so HS-007 and HS-008 selection, ordering and ranking are
  unchanged. An unknown value is rejected with `400`.
- Every result gains a `score` field, in **both** modes. This is additive — no
  existing field changes meaning or disappears. Keyword mode reports its
  `SearchRank`; semantic mode reports `1 - cosine_distance`, unclamped.
- Semantic ranking considers only papers whose `embedding_model` matches the
  configured provider. Papers with a null embedding, or one produced by a
  different model, are excluded rather than compared across vector spaces.
- A stale corpus is surfaced as an operational health condition, logged once per
  process, rather than silently degrading the ranking or failing the request.
- Semantic mode returns `503` when papers exist but none carry a compatible
  embedding, and `200` with an empty list when the corpus is simply empty. The
  status decision lives in the view; the ranker returns a queryset and raises
  nothing.
- The demo page gains a minimal mode selector so the feature is demonstrable
  without curl.

## Capabilities

### New Capabilities

- `semantic-search`: ranking papers by vector distance to an embedded query —
  eligibility, ordering, the similarity score, corpus-health reporting, and the
  HTTP policy for a corpus that cannot serve semantic results.

### Modified Capabilities

- `keyword-search`: results now carry a `score`; the endpoint accepts and
  validates a `mode` parameter, whose absence preserves today's behaviour
  exactly.

## Impact

- **Code**: `apps/search/ranking.py` (new semantic ranker, annotation renamed to
  a mode-agnostic `score`), `apps/search/views.py` (mode validation, provider
  call, status policy), `apps/search/serializers.py` (score field), a new
  corpus-health module, and the search template.
- **Dependencies**: none added. `pgvector.django.CosineDistance` and the
  embedding provider registry both already exist.
- **Runtime**: the local embedding model is loaded lazily on the first semantic
  request, which pays a one-time ~19s cost after a restart.
- **Operations**: completing this change requires the real corpus —
  `ingest_inspire --query "higgs boson" --limit 5000` followed by
  `embed_papers` — because the paraphrase criterion cannot be demonstrated
  against a handful of fixtures.
- **Not touched**: `apps/ingestion`, `apps/papers` models, and the keyword
  ranking algorithm itself.
