# Store paper embeddings in pgvector (HS-010)

## Why

HS-009 built a provider that turns text into vectors, but nothing stores the
result. The corpus has 5,000 papers and no embeddings, so the semantic half of
the ranker described in AGENTS.md §3 cannot be built or measured. This change
gives every paper a persisted vector, which is the prerequisite for vector
search (HS-011) and hybrid fusion (HS-012).

It also fixes the moment at which the dimension stops being a setting and
becomes a schema. Today `EMBEDDING_DIMENSION` is only a number a system check
compares; once a migration freezes it into a column, it is the contract, and the
system needs to notice when the two drift apart.

## What Changes

- `Paper` gains `embedding`, `embedding_model` and `embedded_at`, plus an
  `embedding_text` property defining what actually gets embedded
  (`title + "\n" + abstract`, AGENTS.md §6).
- The `vector` extension is enabled by a committed Django migration rather than
  a manual `psql` step, and an HNSW index over the cosine operator class ships
  in a migration too.
- A new `embed_papers` management command fills in missing vectors: batched,
  resumable, offline-testable.
- A paper is considered to need embedding when it has **no vector or a vector
  produced by a different model**, which makes `embedding_model` operationally
  meaningful instead of decorative and lets the corpus converge on one model.
- **BREAKING (internal):** `--force` narrows in meaning. Because a model change
  is now handled by an ordinary run, `--force` means only "recompute even though
  the recorded model already matches".
- Ingestion stops being able to destroy embeddings. `apps/ingestion` currently
  derives the fields it writes from the model, so the three new fields would
  silently enrol and a re-ingest would null out the entire corpus's vectors.
  This change adds them to the exclusion set; HS-016 replaces the derivation
  with an explicit allow-list.
- Ingestion gains one narrow counterpart duty: when it updates a paper's title
  or abstract, it clears that paper's embedding, so the next `embed_papers` run
  rebuilds a vector that would otherwise silently describe superseded text.

Deliberately **not** changed: the HS-009 provider interface. No `warmup()` is
added, and the embedding system check stays database-unaware. Validation that
needs a database belongs to the command that has one.

## Capabilities

### New Capabilities

- `paper-embeddings`: persisting one vector per paper — the storage schema, the
  ANN index, and the `embed_papers` command that fills and refreshes it,
  including its pre-flight validation and staleness rules.

### Modified Capabilities

- `paper-model`: the domain gains embedding storage fields and an
  `embedding_text` property defining the text that represents a paper.
- `corpus-ingestion`: "only genuinely changed papers are written" is tightened —
  ingestion must write only INSPIRE-owned fields, so re-ingesting never
  disturbs a stored vector, and must invalidate a vector whose source text it
  has just changed.

`text-embedding` is deliberately absent: HS-009's contract is sufficient as
written and this change does not alter it.

## Impact

- **Code:** `apps/papers` (model, migrations, admin), new
  `apps/papers/management/commands/embed_papers.py`, `apps/ingestion/writer.py`
  (exclusion set only), tests in both apps.
- **Database:** `CREATE EXTENSION vector` and an HNSW index build. The extension
  is untrusted and needs a superuser — invisible locally, the first thing to
  break against a least-privilege role.
- **Dependencies:** `pgvector` (the Python package providing `VectorField`).
  No new services, no new settings beyond what HS-009 established.
- **Operational:** a full run embeds ~5,000 abstracts on CPU and takes minutes.
  A model change now triggers a mass recompute, so the command must say so and
  ask before doing it.
