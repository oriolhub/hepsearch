## Why

The project's whole point is semantic search, and semantic search needs vectors. Three
later cards need to turn text into vectors — HS-010 embeds 5,000 stored abstracts,
HS-011 embeds the user's query, HS-012 fuses the result with keyword ranking — and if
each reaches for `sentence_transformers` directly, the model becomes impossible to swap
and impossible to fake in a test. AGENTS.md §3 already states the rule this change
exists to make true: **nothing outside the provider imports `sentence_transformers`**,
and swapping to a hosted embedding API must touch exactly one file.

Doing it now, before anything stores a vector, is what keeps the 384-dimension contract
honest. Once HS-010 freezes that number into a migration, the seam has to already exist.

## What Changes

- A new `apps/embedding` app holding the entire embedding layer. It has no models, no
  views and no migrations; it exists so the provider has a home that neither
  `apps/search` nor `apps/ingestion` owns, since the dependency rule forbids either of
  them importing the other.
- An `EmbeddingProvider` protocol declaring `dimension`, `model_name` and
  `embed(texts) -> vectors`. Vectors are L2-normalized as part of the contract, which
  lets HS-010 choose freely between the cosine and inner-product operator classes.
- A local implementation wrapping `sentence-transformers` with `all-MiniLM-L6-v2`. It is
  the only module in the repository that names that package, and it imports it inside a
  method so the module stays importable when the package is absent.
- A deterministic bag-of-words fake provider, shipped as application code rather than
  test scaffolding, so HS-010 and HS-011 can assert real ordering — "the nearest vector
  ranks first" is only meaningful if similar texts genuinely land near each other.
- Provider selection through a `EMBEDDING_PROVIDER` dotted-path setting resolved with
  `import_string`, cached per process behind a lock, with the model loaded lazily on
  first use rather than at construction.
- A dimension contract in three parts: `EMBEDDING_DIMENSION` is the schema contract, the
  provider declares its dimension statically, and the loaded model is verified against
  that declaration. A cheap Django system check compares the first two on every
  `manage.py` invocation without ever loading a model.
- `sentence-transformers` enters as an **optional extra**, not a main dependency. It
  pulls `torch`; a default `uv sync` must not grow by hundreds of megabytes for a test
  suite that never touches it.
- One `slow`-marked test, excluded from the default run, verifying the real model against
  the declared dimension and confirming that related sentences score above unrelated
  ones.
- **AGENTS.md is amended** in the same commit: §3's app tree gains `apps/embedding`, and
  the line asserting that `apps/papers` "knows nothing about embeddings" is corrected,
  since the embedding layer was always listed as one of the three layers that matter but
  had no home in the documented tree.

No user-visible behaviour changes. Nothing is stored, nothing is searched, no endpoint
moves. This change ships a seam and the tests that hold it in place.

## Capabilities

### New Capabilities

- `text-embedding`: turning text into vectors through a single swappable provider —
  the interface, its normalization and ordering guarantees, how an implementation is
  selected and cached, how the dimension contract is enforced, and the requirement that
  the default test run stays fast, offline and free of any model download.

### Modified Capabilities

None. No existing requirement changes: `paper-model`, `keyword-search`,
`corpus-ingestion` and `inspire-client` are all untouched, because this change stores
nothing and searches nothing.

## Impact

**New code**

- `apps/embedding/` — `protocol.py`, `local.py`, `fake.py`, `registry.py`, `checks.py`,
  `apps.py`, and `tests/`.

**Modified**

- `config/settings.py` — adds `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`,
  `EMBEDDING_DIMENSION`, and registers the new app in `INSTALLED_APPS`.
- `.env.example` — documents the three new settings.
- `pyproject.toml` — adds the `local-embeddings` optional extra, registers the `slow`
  marker, deselects it by default and enables `--strict-markers`.
- `conftest.py` — an autouse fixture resetting the cached provider between tests, so a
  provider cannot leak from one test into the next.
- `AGENTS.md` — §3 architecture amendment described above.

**Dependencies**

- `sentence-transformers` (and transitively `torch`), installed only via
  `uv sync --extra local-embeddings`. Verified to work alongside `[tool.uv]
  package = false`.

**Downstream cards**

- HS-010 consumes `get_provider()`, `dimension` and `model_name`; its card has already
  been updated to read `EMBEDDING_DIMENSION` for the `VectorField` and to validate the
  provider before mutating any row.
- HS-011 embeds the user's query and owns rejecting blank input at the HTTP boundary,
  because the provider raises on whitespace-only text rather than inventing a vector.

**Risks**

- The optional extra means a contributor who skips it hits an `ImportError` on first
  embed. This is deliberate and loud; the alternative — defaulting to the fake — would
  silently write meaningless vectors into 5,000 rows.
- The model download (~90 MB) happens on first use of the slow test or a real HS-010
  run, into the user's cache outside the repository.
