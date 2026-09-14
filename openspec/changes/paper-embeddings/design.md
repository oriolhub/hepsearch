## Context

HS-009 delivered `apps/embedding`: a provider protocol, a configured registry, a
local sentence-transformers implementation, a deterministic fake, and a system
check tying `settings.EMBEDDING_DIMENSION` to the provider's declared dimension.
It produces vectors and guarantees they are L2-normalized. Nothing stores them.

`apps/papers` holds the domain model. A database `CheckConstraint` already
guarantees `abstract != ""`, so **every stored paper is embeddable** — there is
no "unembeddable row" case to design around. `apps/ingestion` fills the corpus
and is re-run constantly.

The dimension currently exists in three places. This change adds a fourth, and
it is the only one that is not merely a declaration:

```
  settings.EMBEDDING_DIMENSION ──── declared intent (HS-009 system check)
            │
            ├── provider.dimension ──── declared statically, no model load
            │         │
            │         └── loaded model's real width ── verified at load (HS-009)
            │
            └── migration-frozen column width ── THE ACTUAL CONTRACT  ◀── new
                    a setting change cannot move it; it can only make
                    the setting lie
```

## Goals / Non-Goals

**Goals:**

- One persisted, normalized vector per paper, derived from a single documented
  definition of "the text that represents a paper".
- A command that is resumable, idempotent, batched, and safe to interrupt.
- Detect and heal a model change instead of silently serving a mixed corpus.
- Fail before touching any row when configuration and schema disagree.
- Establish the pgvector schema contract — extension, typed column, ANN index,
  migration story — while the corpus is small enough that mistakes are cheap.

**Non-Goals:**

- Querying by vector, ranking, or fusion (HS-011, HS-012).
- Tuning ANN recall or build parameters. We need the schema contract today, not
  the speed.
- Changing the HS-009 provider interface. No `warmup()`, no database awareness
  in the embedding system check.
- Replacing ingestion's field-derivation mechanism (HS-016).

## Decisions

### D1 — A paper needs embedding when it has no vector *or* a foreign one

```sql
embedding IS NULL OR embedding_model != <provider.model_name>
```

Not simply `embedding IS NULL`. Three reasons: interrupted runs become
self-healing, `embedding_model` becomes operationally meaningful rather than
decorative, and the corpus provably converges on a single configured model.

*Alternative rejected:* `embedding IS NULL` only, with model changes handled
exclusively by `--force`. That makes a mixed-model corpus the silent default
state and relies on an operator remembering a flag.

### D2 — `embedding_model` is never NULL

This falls directly out of D1. In SQL, `embedding_model != 'x'` evaluates to
NULL — not TRUE — when the column is NULL, so a row holding a vector but no
recorded model would be **permanently invisible** to the command. Making the
column non-nullable removes the trap rather than working around it with
`COALESCE`.

```python
embedding       = VectorField(dimensions=settings.EMBEDDING_DIMENSION,
                              null=True, blank=True)
embedding_model = models.CharField(max_length=128, blank=True, default="")
embedded_at     = models.DateTimeField(null=True, blank=True)
```

This matches house style: `arxiv_id`, `doi` and `journal` are all
`blank=True, default=""`; `citation_count` is `null=True, blank=True`. Only
`embedding` itself is nullable, because "no vector" is a real state that an
empty string cannot express.

### D3 — Pre-flight validates everything before any row is touched

```
  embed_papers
     │
     ├─ 1. get_provider()                                config resolves?
     ├─ 2. provider.dimension == EMBEDDING_DIMENSION?     declaration agrees?
     ├─ 3. EMBEDDING_DIMENSION == column width?           schema agrees?
     ├─ 4. provider.embed(["probe"])                      deps installed?
     │                                                    model actually loads?
     ├─ 5. count missing / count stale
     │        └─▶ "Detected N stale embeddings due to model change"
     │
     └─ loop ────────────────────────────────────────────  only now touch rows
```

Checks 2 and 3 are the response to the four-way dimension diagram above: nothing
in HS-009 can compare a setting against a column, because the check layer has no
database. Doing it here — in the one place that has a connection and is about to
write vectors — keeps the system check cheap and context-free.

Check 4 defines provider validation as **successful inference**, not
introspection of imports or files. If a vector comes back, the provider works;
anything short of that is guessing. It also warms the cached provider, so the
first real batch does not pay the model load. That is a side effect, not the
justification.

*Alternative rejected:* teaching HS-009's system check to read the column.
`manage.py check` would then require a reachable database, which breaks it as a
pre-migration and CI-time tool.

### D4 — The column width is read from `pg_attribute.atttypmod`

Verified empirically against pgvector 0.8.6: for a `vector(n)` column,
`atttypmod` is `n` **directly**, with none of the `VARHDRSZ` offset that
`varchar` applies.

```sql
SELECT atttypmod FROM pg_attribute
WHERE attrelid = 'papers_paper'::regclass AND attname = 'embedding';
-- vector(384) -> 384      (format_type() -> 'vector(384)')
```

One catalog lookup, no pgvector-specific function required. A dimensionless
`vector` column would report `-1`; that is a broken schema and must be treated
as a failure, not as "unknown, proceed".

### D5 — HNSW over the cosine operator class

**HNSW, and the reason is architectural rather than performance.** IVFFlat
performs a training phase to choose centroids and therefore needs representative
data present when the index is built. **Migrations run against an empty
database.** An IVFFlat index created by a migration would be trained on nothing.
HNSW builds incrementally and has no such requirement, so it is the only one of
the two that is honestly expressible as a migration.

Default build parameters. We do not need the speed today; we need the schema
contract today — that pgvector, a typed vector column, an operator class, an ANN
index and a migration all work together before the corpus grows large enough for
mistakes to be expensive.

`vector_cosine_ops`, not `vector_ip_ops`. HS-009 guarantees every stored vector
is unit length, which makes cosine similarity and inner product mathematically
identical here, so the choice is about legibility: "cosine" says what we mean.
**HS-011 must query with the matching operator (`<=>`)** or the index will not
be used.

### D6 — Batching walks a primary-key cursor; it never paginates by offset

Offset pagination over a queryset filtered on the very column being mutated
silently skips rows, because embedding a batch removes it from the filter:

```
  qs = papers_needing_embedding()

  offset:   [0:100]   → embed → those 100 leave the filter
            [100:200] → SKIPS the 100 unembedded rows that shifted down   💥

  keyset:   take [:100] of the live filter where pk > the last pk seen
            terminates even when the filter never shrinks (--force)   ✓
```

Keying on `pk` rather than on an offset eliminates an entire class of silent-skip
bug, and makes "interrupt and resume" fall out of the design instead of being
engineered. Each batch is written in one atomic `bulk_update`.

Re-querying the *head* of the filter with no cursor was the first cut, and it is
wrong under `--force`: that predicate is every paper, so embedding a batch never
removes it from the filter and the loop never ends. Excluding a growing set of
processed ids terminates the loop but makes every batch query carry one bound
parameter per paper already done — quadratic, and it meets PostgreSQL's
65,535-parameter ceiling. A `pk` cursor is O(1) per batch and one loop serves
both modes.

Each batch loads only `pk`, `title` and `abstract`. These rows are about to have
their vectors overwritten, so fetching the existing 384-float `embedding` and the
`search_vector` tsvector would be pure wire cost.

*Alternative rejected:* `.iterator()` — a server-side cursor held open across
minutes of CPU-bound inference while the same rows are being written.

### D7 — Embedding does not move `updated_at`

`updated_at` is `auto_now`, which does not fire on `bulk_update` anyway. Rather
than leave that as an accident that a future reader "fixes", it is a decision:
**embedding generation is not considered a paper-content change.** `updated_at`
tracks what INSPIRE told us; `embedded_at` tracks what we computed.

### D8 — `Paper.embedding_text` owns the definition of what gets embedded

`title + "\n" + abstract` lives as a property on the model, alongside the data
it derives from and next to `SEARCH_CONFIG`, the existing precedent for a shared
contract declared in the model file.

| Option | Verdict |
|---|---|
| `Paper.embedding_text` | ✅ one definition, testable without a command |
| Inline in the command | 😐 works, but HS-011 and any future re-embedder must duplicate it |
| Helper in `apps/embedding` | ❌ that app has never heard of a `Paper`, and must not |

### D9 — `--force` narrows to "recompute even though the model matches"

Since D1 makes an ordinary run handle model changes, `--force` is left with one
honest meaning: recompute rows whose recorded model already matches. Its real
use is a provider bug or a library upgrade that changed output under an
unchanged model name.

### D10 — A mass recompute asks first

Pre-flight already kills the cheap mistakes: a typo'd model name fails check 4,
a wrong-dimension model fails check 2 or the load-time width check. The residual
risk is a **valid, same-dimension model swap** — precisely the case where every
automated check passes and only a human knows it was unintended.

Django's own convention for destructive commands (`flush`) is a prompt plus
`--noinput`, so it costs no new vocabulary:

```
stale == 0            → proceed silently
stale > 0, TTY        → confirm before recomputing
stale > 0, --noinput  → proceed, having printed the count
```

Old vectors are reproducible by reverting the setting, so the loss is compute,
not data. A prompt is proportionate; a hard block is not. `--force` is subject
to the same rule.

### D11 — Ingestion must stop writing embedding fields, immediately

`apps/ingestion/writer.py` derives `COMPARE_FIELDS` from `Paper._meta` minus a
deny-list. Adding three fields to the model therefore **enrols them in ingestion
automatically**, and because INSPIRE supplies no value for them, the next
`ingest_inspire` run would write nulls over every vector in the corpus.

This change adds `embedding`, `embedding_model` and `embedded_at` to
`_EXCLUDED_FIELDS` and ships an ingestion test proving a re-ingest preserves a
stored vector. The deny-list is the wrong mechanism — the next person to add a
field walks into the same trap — but replacing it with an explicit allow-list is
a separable design change, filed as **HS-016**.

### D13 — Ingestion invalidates an embedding whose source text changed

D11 stops ingestion *populating* embedding fields. It does not address the
opposite failure, which the specs surfaced only once they were written out:

```
  INSPIRE revises an abstract, ingest_inspire runs again
        │
        ├─ abstract updated                  ✓
        └─ embedding untouched                ← describes the OLD abstract
              embedding_model still matches   ← D1's predicate sees nothing wrong
              ⇒ never re-embedded, and no signal that anything is stale
```

A vector that silently stops describing its paper is worse than a missing one,
because the corpus looks complete. So ingestion gets one narrow, deliberate
exception to D11: **when it updates `title` or `abstract`, it clears the stored
embedding and its provenance.** The next `embed_papers` run then heals the paper
through the ordinary `embedding IS NULL` branch — no new detection mechanism, no
new flag, no new state.

The exception is *invalidation only*. Ingestion still never writes a vector,
never loads a provider, and never touches these fields for any other reason. The
asymmetry is the point: destroying a value it knows to be wrong is within
ingestion's competence; producing a correct one is not.

*Alternative rejected:* accept the staleness and rely on `--force`. It requires
an operator to know, out of band, that an abstract changed — which is precisely
the knowledge ingestion has and nobody else does.

*Alternative rejected:* store a hash of the embedded text and compare it. That is
a second staleness mechanism alongside `embedding_model`, and it re-derives at
query time what ingestion already knew at write time.

### D12 — The migration is proven on a fresh volume

`vector` is already installed in the current development database, so
`CreateExtension` is a no-op locally and would otherwise ship **unexercised** —
the single step this change flags as the first thing to break elsewhere. The
Definition of Done therefore requires `docker compose down -v`, a fresh
`migrate`, a re-ingest and a real embedding run.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| `CREATE EXTENSION vector` needs a superuser; untrue for any least-privilege production role | Documented in the spec and the card. A DBA installs it out of band and the migration must then be a guarded no-op. Not solved here — made explicit |
| The migration freezes the dimension; changing `EMBEDDING_DIMENSION` afterwards only makes the setting lie | Pre-flight check 3 turns the lie into a loud failure before any row is written |
| A same-dimension model swap silently invalidates the corpus | D1 detects it, D10 announces it and asks |
| HNSW build is memory-hungry | HS-002 already sized `shm_size: 256mb` for exactly this |
| The keyset loop costs one query per batch | Accepted; batches are ~100 rows against minutes of inference, so the query is noise |
| D13 invalidation means a large re-ingest of revised abstracts can queue a large re-embed, and it arrives through the `IS NULL` branch, which by D10 does **not** prompt | Correct by design — those vectors are genuinely wrong, and refusing to rebuild them would serve stale results. The run still reports the count, so the size is visible before it is paid for |
| ANN index returns approximate results, so recall is below exact search | Irrelevant at 5,000 rows and not measured here; revisit when HS-011 can measure ranking quality |

## Migration Plan

1. Migration A: `CreateExtension("vector")`.
2. Migration B: add the three fields.
3. Migration C: add the HNSW index over `vector_cosine_ops`.

Separate migrations so the extension exists before a column needs its type, and
so an environment whose DBA pre-installed the extension can fake exactly one
step. Rollback is `migrate papers <previous>`; dropping the column discards
vectors, which `embed_papers` simply recreates — no data is unrecoverable.

## Open Questions

None blocking. Deferred by decision: the allow-list rework (HS-016), ANN recall
tuning (post-HS-011), and the least-privilege installation story (D11 risk row).
