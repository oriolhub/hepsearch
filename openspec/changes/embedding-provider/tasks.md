# Tasks

One commit: `HS-009: Add a pluggable embedding provider`. The card ships a seam, not a
user-visible slice, so splitting it would leave a half-defined interface on `main`.
The application must remain working and demonstrable throughout (AGENTS.md §7).

## 1. Tooling and the optional dependency

- [x] 1.1 Add `[project.optional-dependencies] local-embeddings = ["sentence-transformers"]`
      to `pyproject.toml`; do **not** add it to `dependencies` (design D11)
- [x] 1.2 Run `uv sync` (no extra) and confirm the lockfile updates without installing
      `torch`
- [x] 1.3 Register the marker in `[tool.pytest.ini_options]`:
      `markers = ["slow: requires a downloaded embedding model; excluded by default"]`
- [x] 1.4 Add `addopts = "-m 'not slow' --strict-markers"`
- [x] 1.5 Confirm `uv run pytest` still collects and passes the existing 107 tests
- [x] 1.6 Confirm `uv run pytest -m slow` overrides the default marker expression rather
      than intersecting with it
- [x] 1.7 Confirm `.gitignore` already covers a relocated model cache (`.cache/`,
      `models/`, `.sentence_transformers/`); add nothing if it does

## 2. Settings and environment

- [x] 2.1 Add `EMBEDDING_PROVIDER`, defaulting to
      `"apps.embedding.local.LocalEmbeddingProvider"` — the real one, not the fake (D3)
- [x] 2.2 Add `EMBEDDING_MODEL`, defaulting to `"all-MiniLM-L6-v2"`
- [x] 2.3 Add `EMBEDDING_DIMENSION` via `env.int`, defaulting to `384`, with a comment
      naming it the schema contract HS-010 will build its column from
- [x] 2.4 Register `apps.embedding.apps.EmbeddingConfig` in `INSTALLED_APPS`, following
      the existing `apps.<name>.apps.<Name>Config` style
- [x] 2.5 Document all three settings in `.env.example`, in a section explaining that the
      real provider needs `uv sync --extra local-embeddings`
- [x] 2.6 Confirm `uv run python manage.py check` still passes with no extra installed

## 3. The app skeleton

- [x] 3.1 Create `apps/embedding/` with `__init__.py` and `apps.py`
- [x] 3.2 Give `apps.py` a docstring stating why an app with no models exists: Django
      only auto-discovers system checks from installed apps (D1)
- [x] 3.3 Create `apps/embedding/tests/__init__.py`
- [x] 3.4 Confirm the app has no `models.py`, no `views.py` and no `migrations/`
- [x] 3.5 Confirm `uv run python manage.py makemigrations --check --dry-run` reports
      nothing to do

## 4. The protocol

- [x] 4.1 Create `apps/embedding/protocol.py` with `EmbeddingProvider(Protocol)` —
      `Protocol`, not `ABC` (D2)
- [x] 4.2 Declare `dimension: int` and `model_name: str` as read-only members
- [x] 4.3 Declare `embed(texts: Sequence[str]) -> list[list[float]]` (D8)
- [x] 4.4 State the whole contract in the module/protocol docstring: normalization,
      input order, empty batch, blank-text rejection, punctuation-only acceptance
- [x] 4.5 Define a `BlankTextError` (or reuse `ValueError` deliberately) and state which
      in the docstring, so HS-011 knows what to catch
- [x] 4.6 Confirm this module imports nothing beyond `typing` and `collections.abc`

## 5. The deterministic offline provider

- [x] 5.1 Create `apps/embedding/fake.py` with `FakeEmbeddingProvider`
- [x] 5.2 Hash tokens with `zlib.crc32`, never the builtin `hash()`, because `str`
      hashing is randomised per interpreter (D9)
- [x] 5.3 Read `dimension` from `settings.EMBEDDING_DIMENSION` so it is drop-in against
      HS-010's `VectorField` (D5)
- [x] 5.4 Set `model_name = "fake-bow-384"` and document it as an embedding-space
      identifier, not a display label (D10)
- [x] 5.5 Bucket tokens into the dimension, count them, then L2-normalize (D7)
- [x] 5.6 Fall back to hashing the raw string when tokenization yields no tokens, so
      `"..."` yields a unit vector rather than dividing by zero (D8)
- [x] 5.7 Raise on empty or whitespace-only text, before any tokenization
- [x] 5.8 Return `[]` for an empty sequence
- [x] 5.9 Add a module docstring stating plainly that this is a test double and must not
      be used to populate a real corpus

## 6. The local provider

- [x] 6.1 Create `apps/embedding/local.py` with `LocalEmbeddingProvider`
- [x] 6.2 Carry the static model → dimension map on the class, owned by the
      implementation rather than added as a third configuration source (D5)
- [x] 6.3 Derive `dimension` from `settings.EMBEDDING_MODEL` via that map, without
      loading anything
- [x] 6.4 Raise at construction when the configured model is not in the map — never guess
      a dimension
- [x] 6.5 Set `model_name` to the configured model identifier
- [x] 6.6 Import `sentence_transformers` **inside** the load method, never at module
      level, so the module stays importable without the extra (D11)
- [x] 6.7 Raise an error naming `uv sync --extra local-embeddings` when the import fails
- [x] 6.8 Load the model at most once, guarded by a `threading.Lock` (D4)
- [x] 6.9 Assert the loaded model's true dimension equals the declared one, and fail if
      not (D5)
- [x] 6.10 Pass `normalize_embeddings=True` and convert to `list[list[float]]` (D7, D8)
- [x] 6.11 Return `[]` for an empty sequence **before** touching the model
- [x] 6.12 Raise on empty or whitespace-only text, matching the fake exactly
- [x] 6.13 Log one line when the model is loaded; log nothing per call
- [x] 6.14 Confirm this is the only module in the repository importing
      `sentence_transformers`

## 7. The registry

- [x] 7.1 Create `apps/embedding/registry.py` with `get_provider()`
- [x] 7.2 Resolve `settings.EMBEDDING_PROVIDER` with
      `django.utils.module_loading.import_string` (D3)
- [x] 7.3 Cache the constructed provider with a module-level `functools.cache`
- [x] 7.4 Guard construction with a lock so concurrent first callers share one instance
- [x] 7.5 Expose an explicit `reset()` clearing the cache (D4)
- [x] 7.6 Let an unresolvable import path propagate; substitute no fallback provider
- [x] 7.7 Confirm importing this module constructs nothing

## 8. The system check

- [x] 8.1 Create `apps/embedding/checks.py` and register the check from
      `EmbeddingConfig.ready()`
- [x] 8.2 Compare `settings.EMBEDDING_DIMENSION` against the configured provider's
      declared `dimension`; report an **Error** naming both values on a mismatch (D6)
- [x] 8.3 Report a **Warning** when the configured provider is the fake
- [x] 8.4 Suppress that warning when `"pytest" in sys.modules`, matching the idiom already
      used in `config/settings.py` and `conftest.py` (D6)
- [x] 8.5 Confirm the check loads no model — it may construct a provider, never embed
- [x] 8.6 Give each message a stable `id` (e.g. `embedding.E001`, `embedding.W001`)

## 9. Test wiring

- [x] 9.1 Add an autouse fixture to the root `conftest.py` calling `registry.reset()`
      around each test, so no provider leaks between tests (D4)
- [x] 9.2 Confirm the fixture does not itself import `sentence_transformers`

## 10. Contract tests, shared by every implementation

- [x] 10.1 Create `apps/embedding/tests/test_contract.py` parametrized over both
      implementations, so a third provider gains coverage by registration (D2)
- [x] 10.2 Every returned vector has unit norm
- [x] 10.3 Every returned vector has `provider.dimension` components
- [x] 10.4 A batch returns one vector per input, positionally aligned
- [x] 10.5 An empty sequence returns `[]`
- [x] 10.6 `""` and whitespace-only text raise
- [x] 10.7 Punctuation-only text returns exactly one unit vector — the case that would
      otherwise make the fake stricter than the real provider (D8)
- [x] 10.8 `model_name` and `dimension` are readable without embedding anything

## 11. Fake-specific tests

- [x] 11.1 The same text embeds identically in a **separate interpreter**, proving the
      hash is not `PYTHONHASHSEED`-dependent (D9)
- [x] 11.2 Two texts sharing words are closer to each other than either is to an
      unrelated text
- [x] 11.3 Changing `EMBEDDING_DIMENSION` changes the returned vector width
- [x] 11.4 `model_name` is `fake-bow-384`
- [x] 11.5 No network request and no model load occurs

## 12. Local-provider tests that never load a model

- [x] 12.1 An unknown `EMBEDDING_MODEL` raises at construction
- [x] 12.2 `dimension` and `model_name` are readable without the extra installed
- [x] 12.3 `embed([])` returns `[]` without importing `sentence_transformers`
- [x] 12.4 A missing `sentence_transformers` raises an error naming the extra, using a
      patched import rather than a real uninstall
- [x] 12.5 A stubbed model whose dimension disagrees with the declaration causes a failure
- [x] 12.6 A stubbed model is loaded exactly once across several `embed` calls

## 13. Registry and check tests

- [x] 13.1 `get_provider()` returns the same instance twice
- [x] 13.2 `reset()` causes a fresh instance to be constructed
- [x] 13.3 Pointing `EMBEDDING_PROVIDER` at the fake yields the fake after a reset
- [x] 13.4 An unresolvable `EMBEDDING_PROVIDER` raises rather than falling back
- [x] 13.5 Matching dimensions produce no check error
- [x] 13.6 A mismatched `EMBEDDING_DIMENSION` produces a check error naming both values
- [x] 13.7 The fake-provider warning is suppressed under pytest and emitted when the
      pytest signal is simulated as absent

## 14. The one slow test

- [x] 14.1 Create `apps/embedding/tests/test_local_model_slow.py`
- [x] 14.2 Guard the import with `pytest.importorskip("sentence_transformers")` in a
      fixture, not at module level: collection precedes deselection, so a module-scope
      import costs the default run ~12 s of torch import wherever the extra is
      installed (D12, corrected during implementation)
- [x] 14.3 Mark the test `@pytest.mark.slow`
- [x] 14.4 Assert the real model returns vectors of `settings.EMBEDDING_DIMENSION`
- [x] 14.5 Assert two related physics sentences score higher against each other than
      against an unrelated sentence, computing cosine ad hoc in the test (no shipped
      similarity helper)
- [x] 14.6 Confirm `uv run pytest` does not run it
- [x] 14.7 Run `uv run pytest -m slow` once with the extra installed and record the
      elapsed time and model download size in the commit body

## 15. Documentation

- [x] 15.1 Amend AGENTS.md §3: add `apps/embedding/` to the tree with a one-line
      description (D13)
- [x] 15.2 Amend AGENTS.md §3's dependency rule to show `search → embedding` and
      `ingestion → embedding`, and that `embedding` depends on nothing
- [x] 15.3 Correct the sentence asserting `apps/papers` "knows nothing about ...
      embeddings" so it stays true once HS-010 adds a vector column
- [x] 15.4 Add `uv sync --extra local-embeddings` and `uv run pytest -m slow` to
      AGENTS.md §5's command list
- [x] 15.5 Note in AGENTS.md §6 that the provider normalizes, so HS-010 may choose either
      the cosine or inner-product operator class

## 16. Gates and commit

- [x] 16.1 `uv run pytest` — passes, stays offline, and shows no material slowdown
- [x] 16.2 `uv run pytest` on a machine state without the extra — confirm collection
      succeeds and the slow test reports as skipped
- [x] 16.3 `uv run ruff check .`
- [x] 16.4 `uv run ruff format --check .`
- [x] 16.5 `uv run python manage.py check` — no errors, and the fake warning appears only
      when the fake is configured outside pytest
- [x] 16.6 Tick the card's acceptance criteria and Definition of Done
- [x] 16.7 `git mv` the card from `board/backlog/` to `board/done/` in this commit
- [ ] 16.8 Commit as `HS-009: Add a pluggable embedding provider`, with a body explaining
      why the seam exists before anything stores a vector, and recording the slow-test
      timing from 14.7
