# HS-010: Store paper embeddings in pgvector

**Status:** backlog
**Depends on:** HS-009

## Story

As an operator, I want every paper in the corpus to have a stored embedding, so
that semantic similarity can be computed inside the database.

## Context

One vector per paper, over `title + "\n" + abstract` (AGENTS.md §6). The
`VectorField` dimension **must** equal the provider's dimension from HS-009.

Like ingestion, this command must be resumable: embedding 5,000 abstracts on CPU
takes minutes, and nobody should have to start over after a Ctrl+C.

## Acceptance criteria

- [ ] The `vector` extension is enabled through a Django migration
      (`CreateExtension`), not a manual `psql` step
- [ ] `Paper.embedding` is a nullable `VectorField` whose dimension comes from
      the configured provider
- [ ] `embedding_model` and `embedded_at` are stored per paper, so a model change
      is detectable
- [ ] `uv run python manage.py embed_papers` embeds every paper missing a vector
- [ ] Re-running the command immediately after does nothing and says so
- [ ] Interrupting mid-run and re-running resumes; already-embedded papers are
      not recomputed
- [ ] Papers are embedded in batches, and the batch size is configurable
- [ ] Progress and a final summary are printed
- [ ] `--force` re-embeds everything, for use after a model change
- [ ] An ANN index (HNSW or IVFFlat) exists for the cosine operator class, added
      by a committed migration
- [ ] The index choice and its parameters are justified in a comment
- [ ] Tests use the fake provider from HS-009 and assert: vectors are stored,
      re-running is a no-op, and `--force` recomputes
- [ ] After a real run, no paper in the corpus has a null embedding

## Definition of done

- [ ] Acceptance criteria met
- [ ] A real embedding run has been performed; the count and elapsed time are
      recorded in the commit body
- [ ] `uv run pytest` and `uv run ruff check .` pass
- [ ] Committed as `HS-010: Store paper embeddings in pgvector`

## Out of scope

Querying by vector (HS-011), hybrid ranking (HS-012), embedding the user's query
(HS-011).
