## Context

HS-010 stores one L2-normalized 384-dimensional vector per paper in
`Paper.embedding`, records which model produced it in `Paper.embedding_model`,
and builds an HNSW index with `vector_cosine_ops`. HS-007 ships a keyword ranker
in `apps/search/ranking.py` — a pure function over a queryset, deliberately free
of HTTP. HS-012 will fuse the two with Reciprocal Rank Fusion and make hybrid the
default mode.

This change sits between them, and its design is constrained from both sides: it
must not disturb the keyword path, and it must leave HS-012 a module it can
compose rather than rewrite.

The embedding provider is reached only through `apps.embedding.registry.
get_provider()`, which is `@cache`-d behind a lock. The provider's `model_name`
identifies the vector space; its `embed()` contract guarantees normalized vectors
in input order and raises `BlankTextError` on empty text.

### Evidence gathered before designing

A synthetic 3,500-row probe (inserted, `EXPLAIN`ed, rolled back) settled four
questions that would otherwise have been guesswork:

| Query shape | HNSW used? | Plan |
|---|---|---|
| `ORDER BY embedding <=> q` | yes | Index Scan |
| `ORDER BY embedding <=> q, inspire_id DESC` | **yes** | Index Scan → Incremental Sort, distance as Presorted Key |
| `+ WHERE embedding_model = '…'` | yes | Index Scan + Filter |
| `+ WHERE embedding IS NOT NULL` | yes | Index Scan + Filter |

Three consequences:

1. **A secondary tiebreak does not defeat the index.** The initial assumption
   that it would was wrong. HS-007's `-rank, -inspire_id` determinism pattern
   carries over unchanged.
2. **Filters are applied after the index scan** (`Rows Removed by Filter`), so
   `hnsw.ef_search` bounds the candidate pool *before* eligibility is checked.
3. **Null embeddings are not inherently excluded** — they sort last on a NULL
   distance, which means they surface whenever fewer than `limit` papers are
   embedded. The explicit filter is load-bearing, not defensive decoration.

The planner chose the index naturally at 3,500 rows, so the `EXPLAIN` acceptance
criterion is honestly satisfiable at 5,000 without forcing `enable_seqscan=off`.

## Goals / Non-Goals

**Goals:**

- Rank by cosine distance in PostgreSQL, never in Python.
- Compare only vectors from the same model, so a similarity score always means
  something.
- Keep `apps/search/ranking.py` pure — no HTTP, no provider, no model loading —
  so HS-012 can call it.
- Make a stale or unusable corpus visible to an operator rather than silently
  degrading results.
- Ship a response shape HS-012 can extend without reshaping.

**Non-Goals:**

- Fusing keyword and semantic ranking (HS-012).
- Tuning ANN recall (`hnsw.ef_search`) before measuring a problem.
- Re-ranking models, LLM answer generation, or query expansion.
- Proving thread-safety of `sentence-transformers` inference under concurrency.

## Decisions

### D1 — `semantic_search` takes a vector, never text

```
  REJECTED                          CHOSEN
  ────────────────────────────      ────────────────────────────
  semantic_search(text, limit)      semantic_search(qs, vector, limit)
    ↓ loads provider                  ↓ pure
    ↓ loads model (~19s)              ↓ DB-testable
    ↓ embeds                          ↓ fake-vector testable
    ↓ ranks                           ↓ no ML dependency
  ranking layer owns ML             view owns the provider call
```

Embedding and retrieval are different layers. The moment the ranker accepts text
it owns model loading, `BlankTextError`, and provider configuration — none of
which belong to ranking. Tests can then pass a hand-written vector and assert
ordering with no provider at all.

**Alternative rejected:** a convenience wrapper that accepts text. It would
become the path everything uses, and the purity would be theoretical.

### D2 — Eligibility is "has an embedding from the current model"

```sql
WHERE embedding IS NOT NULL AND embedding_model = <provider.model_name>
```

Both predicates are required. The null check is load-bearing per the probe. The
model check is the difference between a similarity score and a number: vectors
from different models occupy unrelated spaces, and comparing them produces
confident nonsense rather than an error.

**Alternative rejected:** ranking everything and hoping mismatched vectors sort
themselves out. They do not — they produce plausible-looking rankings that are
meaningless.

### D3 — Model mismatch is a corpus-health condition, not a request error

A half-stale corpus still returns twenty plausible rows, so empty results are a
poor staleness detector. Detection therefore does not live in the ranking path
and does not depend on the result set being empty.

Two reporting levels, no new surface invented:

```
Level 1  embed_papers  →  "Detected N stale embeddings due to model change"
Level 2  first semantic request in a process
             → logger.warning("Semantic corpus contains %s stale embeddings", n)
```

**Alternative rejected:** a database-aware Django system check. HS-010 already
decided (Q4) that `manage.py check` stays database-independent, so that
`migrate`, `check` and `test` do not require a live corpus. Adding a DB-aware
check now for embedding health would contradict that precedent for no gain.

### D4 — The health probe lives in its own module, memoized once per process

```
semantic_search(vector)      pure — no counting, no logging          ✗
view, inline                 a COUNT on every request                ✗
apps/search/health.py        probed once per process, memoized       ✓
```

The probe runs **once per process unconditionally** — not "retry until drift is
found" — so the cost is one query per process lifetime and the semantics stay
predictable. Drift appearing later in a long-lived process is covered by
Level 1; `embed_papers` is the tool an operator actually runs.

The memo exposes an explicit `reset()`, mirroring `apps.embedding.registry.
reset()`, which the root `conftest.py` already calls around every test. A
process-global memo that tests cannot clear is test pollution waiting to happen.

### D5 — Rankers return rankings; views decide what HTTP means

This is the organizing rule of the change, and the same cut as D1 applied to
failure instead of input.

```
        ┌──────────────────────── view ────────────────────────┐
        │ validate mode      → 400 on unknown                  │
        │ reject blank q     → 400 (existing HS-007 behaviour) │
        │ health.check_once()→ logger.warning if stale         │
        │ provider.embed([q])→ vector                          │
        │                                                      │
        │   ┌──────────── semantic_search(vector) ──────────┐  │
        │   │ filter → order by distance → limit            │  │
        │   │ returns QuerySet[Paper], possibly empty       │  │
        │   │ raises nothing, knows no status codes         │  │
        │   └───────────────────────────────────────────────┘  │
        │                                                      │
        │ empty? → 0 papers total    → 200 []                  │
        │          papers exist      → 503                     │
        └──────────────────────────────────────────────────────┘
```

`semantic_search` never raises for an unusable corpus. It returns an empty
queryset and the view decides what that means. This is what makes HS-012 cheap:
hybrid will degrade to keyword-only with `200` and a `degraded` flag rather than
`503`-ing the default mode, and that is purely an orchestration change — the
ranker does not move.

**Alternative rejected:** raising a domain exception from the ranker. It would
force every future caller, including the hybrid orchestrator, to catch an
exception describing a condition it intends to tolerate.

### D6 — Empty corpus and incompatible corpus are different states

```
Paper.objects.exists() == False        → 200 []   nothing is wrong,
                                                  nobody has ingested yet

papers exist, 0 compatible embeddings  → 503      the user asked for semantic
                                                  search; the system cannot
                                                  perform it
```

`503 Service Unavailable` is the honest code. Not `409` — no request conflicted
with anything. Not `500` — nothing crashed, and the condition is known and
diagnosable. The service is genuinely unavailable until an operator runs
`embed_papers`, which is textbook 503.

The diagnostic query only runs in the already-empty branch, so it costs nothing
on the happy path.

### D7 — `similarity = 1 - cosine_distance`, unclamped

If the field is named `similarity`, returning a distance is a lie. Clamping a
negative value to zero is a different lie: it asserts that two genuinely
different scores are identical. A negative similarity is real information about a
query pointing away from the corpus.

Documented as: *similarity may be negative.*

### D8 — One `score` field, in every mode, annotated to one attribute name

The serializer must not branch on mode; that branch only grows when hybrid
arrives. Keyword's `SearchRank` and semantic's `1 - distance` are both annotated
to `score`, which requires renaming the existing `rank` annotation in
`ranking.py` — an internal name nothing outside that module reads.

Adding `score` to keyword mode does not violate HS-011's "HS-007 and HS-008 do
not change behaviour": behaviour means selection, ordering and ranking, none of
which move. The field is additive and breaks no consumer. The alternative is
reshaping the response twice, since HS-012 needs both scores anyway.

The two scores are **not comparable across modes** — a `SearchRank` and a cosine
similarity are different scales. This is documented rather than encoded in a
`score_type` discriminator, because a single corpus-wide meaning per response is
already carried by the `mode` field the response returns.

### D9 — The mode enum arrives now

HS-012 needs `KEYWORD | SEMANTIC | HYBRID`. Introducing two of three now and the
third later costs nothing; deferring the enum means parsing a bare string twice.
Unknown values are rejected at the boundary with `400`, never reaching the
ranker.

The demo page gets a minimal `<select>`. An API that supports semantic search
while the page cannot demonstrate it is a half-shipped feature; HS-014 can
polish the presentation.

### D10 — The model loads lazily, on the first semantic request

`AppConfig.ready()` is explicitly rejected: `manage.py check`, `migrate` and the
test suite would all pay a ~19-second model load, which is precisely what the
HS-009 provider seam exists to avoid. No `warmup()` API is added — HS-010
already declined one.

The cost is honest and documented: *the embedding model is loaded lazily on the
first semantic-search request.*

### D11 — Ordering is `distance ASC, inspire_id DESC`

Determinism matters for pagination and for tests. The probe proved the tiebreak
is free — Postgres adds an Incremental Sort with the distance as a Presorted
Key and keeps the index scan.

## Risks / Trade-offs

**ANN under-fetch during a mixed-model corpus state** → Accepted and documented,
not fixed. Because eligibility filters apply after the index scan, a corpus
containing many incompatible embeddings can yield fewer than `limit` results.
The real fix is `SET LOCAL hnsw.ef_search`, but introducing ANN tuning before
measuring a problem is premature, and the condition is practically unreachable
with a uniform, fully-embedded 5,000-paper corpus. Documented as: *during a
mixed-model corpus state, candidate filtering can return fewer than the requested
limit.*

**First request after a restart takes ~19 seconds** → Accepted (D10). Every
alternative pushes the cost onto commands that have no use for a model.

**`sentence-transformers` inference under concurrent requests** → Stated
assumption, not a verified property. The registry's lock guards provider
*construction*, not `embed()`. Under `runserver` this is not exercised. Recorded
as a known assumption to spike before moving to a threaded or multi-worker
server; it does not block this change.

**Staleness appearing after the once-per-process probe** → Accepted. Level 1
(`embed_papers`) is the surface an operator actually watches; Level 2 is a
cheap runtime signal, not a monitor.

**Renaming the `rank` annotation to `score`** → Contained. The name is internal
to `apps/search/ranking.py`; the ordering clause and one serializer reference
change together, and the existing keyword tests assert ordering, which would
catch a miss.

## Migration Plan

No schema change — HS-010 already created the column, the index and the
`embedding_model` field. Deployment is code-only.

Completing the change requires a corpus:

```powershell
uv run python manage.py ingest_inspire --query "higgs boson" --limit 5000
uv run python manage.py embed_papers
```

This is part of the work, not a separate operator activity: the paraphrase
acceptance criterion is a corpus-level property and cannot be demonstrated
against a handful of fixtures. Rollback is reverting the commit; no data is
written by this change.

### Verification record

The real run fetched 5,049 records, skipped 49 without abstracts, and produced
4,999 new papers plus one existing row. `embed_papers --noinput` embedded all
4,999 missing vectors. The first semantic request in a fresh process took
39.79 seconds, including lazy model loading.

The semantic query plan over the resulting corpus used
`paper_embedding_hnsw` with an Index Scan followed by Incremental Sort; the
model and non-null embedding predicates were applied as a post-scan filter.

For the query **"what makes the newly discovered particle unique"**, keyword
mode returned no results while semantic mode returned (top two):

1. 8307 — *Hints of lepton flavor universality violations*
2. 6570 — *The end of the particle era?*

This is a demonstration of semantic retrieval finding papers when the keyword
ranker has no match; the fake provider remains test-only and was not used for
this corpus run.

## Open Questions

None blocking. Two deliberately deferred to a later card:

- Whether `hnsw.ef_search` needs tuning, to be revisited only with a measured
  recall problem.
- Whether `sentence-transformers` inference is thread-safe, to be spiked when the
  project leaves `runserver`.
