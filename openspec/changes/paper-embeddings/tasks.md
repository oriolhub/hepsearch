## 1. Dependency and schema foundation

- [x] 1.1 Add the `pgvector` Python package with `uv add pgvector` (never edit `pyproject.toml` by hand) and confirm `uv.lock` is updated
- [x] 1.2 Add a migration to `apps/papers` containing only `CreateExtension("vector")`, with a comment recording that `vector` is untrusted, requires a superuser, and what an operator must do when the application role is not one
- [x] 1.3 Verify `migrate` applies 1.2 against a database where the extension is absent (see 8.1 — this cannot be proven on the current dev volume)

## 2. The domain model

- [x] 2.1 Add `embedding = VectorField(dimensions=settings.EMBEDDING_DIMENSION, null=True, blank=True)` to `Paper`, importing the dimension from settings and never from a provider
- [x] 2.2 Add `embedding_model = CharField(max_length=128, blank=True, default="")` — non-nullable, per design D2, so the staleness predicate can never return NULL
- [x] 2.3 Add `embedded_at = DateTimeField(null=True, blank=True)`
- [x] 2.4 Add the `embedding_text` property returning `title + "\n" + abstract`, next to `SEARCH_CONFIG`
- [x] 2.5 Generate the field migration; confirm it is ordered after 1.2 and that the column is created as `vector(384)`
- [x] 2.6 Add the HNSW index migration over `vector_cosine_ops`, with a comment justifying HNSW over IVFFlat (migrations run on an empty database; IVFFlat needs training data) and cosine over inner product (equivalent under HS-009's normalization; chosen for legibility)
- [x] 2.7 Surface the three fields sensibly in the Django admin (read-only; do not render a 384-float widget)
- [x] 2.8 Confirm `makemigrations --check --dry-run` reports nothing outstanding

## 3. Domain tests

- [x] 3.1 Test `embedding_text` combines title and abstract with a separator, without a database query or a provider
- [x] 3.2 Test a newly created paper has no embedding, an empty (not null) `embedding_model`, and no `embedded_at`
- [x] 3.3 Test the embedding column's declared width equals `settings.EMBEDDING_DIMENSION` by reading `pg_attribute.atttypmod`
- [x] 3.4 Test that no module in `apps/papers` imports a provider or `sentence_transformers`

## 4. Protect and extend ingestion

- [x] 4.1 Add `embedding`, `embedding_model` and `embedded_at` to `_EXCLUDED_FIELDS` in `apps/ingestion/writer.py`
- [x] 4.2 Assert the derived `COMPARE_FIELDS` still contains exactly the nine INSPIRE-owned fields, so a future model addition fails this test rather than the corpus
- [x] 4.3 Implement D13 invalidation: when a write changes `title` or `abstract`, clear `embedding`, `embedding_model` and `embedded_at` on that row, without loading a provider
- [x] 4.4 Include the cleared fields in the batch `bulk_update` so invalidation is written atomically with the content change
- [x] 4.5 Test that re-ingesting an identical record leaves a stored embedding, its model and its timestamp untouched
- [x] 4.6 Test that changing citation count, DOI, journal, authors, categories or earliest date updates those fields and leaves the embedding intact
- [x] 4.7 Test that changing the abstract clears the embedding, and separately that changing the title clears it
- [x] 4.8 Test that ingestion never imports or instantiates an embedding provider

## 5. The embed_papers command

- [x] 5.1 Create `apps/papers/management/commands/embed_papers.py` with `--batch-size`, `--force` and `--noinput`, mirroring `ingest_inspire`'s argument and reporting idiom
- [x] 5.2 Implement pre-flight step 1: resolve the provider via `apps.embedding.registry.get_provider()`, failing with `CommandError` if configuration is invalid
- [x] 5.3 Implement pre-flight step 2: fail when `provider.dimension != settings.EMBEDDING_DIMENSION`, naming both values
- [x] 5.4 Implement pre-flight step 3: read the column width from `pg_attribute.atttypmod` and fail when it disagrees with the setting, naming both values; treat `-1` (dimensionless column) as a failure
- [x] 5.5 Implement pre-flight step 4: call `provider.embed(["probe"])` and fail on any exception — successful inference is the definition of a working provider
- [x] 5.6 Implement the work predicate as a reusable queryset: `embedding IS NULL OR embedding_model != provider.model_name` (`--force` widens it to every paper)
- [x] 5.7 Count and report missing and stale separately, printing `Detected N stale embeddings due to model change` when N > 0
- [x] 5.8 Prompt for confirmation when stale > 0 or `--force` is given, skipped by `--noinput`; declining must exit without writing
- [x] 5.9 Implement the batching loop as a primary-key cursor over the filtered queryset until it is empty — never offset pagination, never `.iterator()`
- [x] 5.10 Embed each batch via `provider.embed([p.embedding_text for p in batch])` and write it in one atomic `bulk_update` of `embedding`, `embedding_model` and `embedded_at` — and deliberately not `updated_at`
- [x] 5.11 Report progress per batch and print a final summary of embedded and skipped counts
- [x] 5.12 Report and exit cleanly when nothing needs embedding

## 6. Command tests

- [x] 6.1 Test a corpus with no vectors is fully embedded, with every vector at the configured dimension
- [x] 6.2 Test an immediate re-run embeds nothing, says so, and leaves every vector byte-identical
- [x] 6.3 Test a recorded model differing from the provider's triggers re-embedding and updates the recorded model
- [x] 6.4 Test a paper whose recorded model matches is left alone
- [x] 6.5 Test `--force` recomputes papers that are already current and moves `embedded_at`
- [x] 6.6 Test `updated_at` does not move when a paper is embedded, while `embedded_at` is set
- [x] 6.7 Test each pre-flight failure (unresolvable provider, dimension mismatch against the setting, setting mismatch against the column, provider raising on embed) exits with an error and writes nothing
- [x] 6.8 Test the confirmation prompt: stale > 0 interactively asks and declining changes nothing; `--noinput` proceeds and still reports the count; a purely-missing run does not prompt
- [x] 6.9 Test a corpus larger than one batch leaves no paper unembedded, which is the regression test for the offset-skip bug in design D6
- [x] 6.10 Test an interrupted run (simulate a provider raising on batch 3) preserves the batches already written and that a resumed run completes exactly the remainder
- [x] 6.11 Test `--batch-size` is honoured and has a default
- [x] 6.12 Confirm all of the above use the fake provider and that the default `pytest` run touches no network and loads no model

## 7. Documentation

- [x] 7.1 Confirm `embed_papers` behaves as AGENTS.md §5 already documents, and update that section if the flags differ
- [x] 7.2 Document in AGENTS.md §6 that embedding is not a paper-content change, so `updated_at` deliberately does not move
- [x] 7.3 Note the superuser requirement for `CreateExtension` where an operator will find it

## 8. Verification and delivery

- [x] 8.1 Prove the migration on a fresh volume: `docker compose down -v`, `docker compose up -d --wait`, `migrate` — this is the only run that exercises `CreateExtension`, which is a no-op on an existing dev volume
- [x] 8.2 Re-ingest the corpus, then perform a real `embed_papers` run; record the paper count and elapsed time for the commit body
- [x] 8.3 Confirm no paper in the corpus has a null embedding
- [x] 8.4 Spot-check that the HNSW index exists and that a `<=>` query against it plans as expected — HS-011 depends on the operator matching the operator class
- [x] 8.5 Run `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .`
- [x] 8.6 `git mv` the card from `board/in-progress/` to `board/done/` in the same commit as the work, committed as `HS-010: Store paper embeddings in pgvector`
