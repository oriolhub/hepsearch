## Context

`apps/search` will need to embed a user's query (HS-011) and `apps/ingestion`-style
batch work will need to embed 5,000 abstracts (HS-010). The dependency rule in
AGENTS.md §3 is absolute — `search` and `ingestion` must never import each other — so
the code they both need cannot live in either.

AGENTS.md §3 lists "Embedding — a provider interface" as one of the three layers that
matter, but its `apps/` tree names only `papers`, `ingestion` and `search`. The layer
was specified without a home. This change gives it one.

The corpus is already ingested and keyword-searchable (HS-006, HS-007, HS-008). Nothing
here changes what a user sees. The constraint that shapes almost every decision below is
AGENTS.md §6: **no test may touch the network or download a model in the default
`pytest` run**, and that run is currently 107 tests in under two seconds.

## Goals / Non-Goals

**Goals:**

- Exactly one module in the repository imports `sentence_transformers`.
- Swapping to a hosted embedding API touches one file.
- The 384-dimension contract is enforced by something that fails loudly, before HS-010
  freezes the number into a migration.
- A fake provider good enough that HS-011 and HS-012 can assert *ranking*, not just
  plumbing, entirely offline.
- The default `uv sync` does not install `torch`.
- The default `uv run pytest` stays fast, offline, and never downloads a model.

**Non-Goals:**

- Storing vectors, the `VectorField`, the `vector` extension, ANN indexes — HS-010.
- Querying by vector or embedding the user's query — HS-011.
- Hybrid ranking — HS-012.
- Chunking. Abstracts are ~1,200 characters and fit inside the model's 512-token
  window; AGENTS.md §6 rules chunking out permanently.
- Caching individual embeddings. Nothing re-embeds the same text twice in a request
  path yet; HS-013 can revisit if query embedding proves hot.
- A hosted-API provider. The interface must *permit* one; writing one now would be
  speculative.

## Decisions

### D1 — The provider lives in a new `apps/embedding` app

Four homes were considered:

| Option | Verdict |
|---|---|
| `apps/papers/embedding.py` | Rejected. AGENTS.md §3 says papers "knows nothing about INSPIRE, HTTP, or embeddings", and papers is the one app that must depend on nothing. |
| **`apps/embedding/`, in `INSTALLED_APPS`** | **Chosen.** |
| Root-level `embedding/` package | Rejected. Breaks the "everything is in `apps/` or `config/`" layout and needs a new `ruff` `include` entry. |
| `config/embedding.py` | Rejected. `config/` is wiring, not a model runtime. |

It is a Django app with no models, no views and no migrations, which is unusual enough
to deserve a reason: **Django only auto-discovers system checks from installed apps**,
and D6 puts a system check at the heart of the dimension contract. An app is the
cheapest way to get that discovery, and it keeps the folder convention intact.

Resulting dependency graph — still acyclic, and `papers` still depends on nothing:

```
                    ┌──────────────┐
                    │ apps/papers  │  (depends on nothing)
                    └──────▲───────┘
                           │
              ┌────────────┴────────────┐
              │                         │
      ┌───────┴────────┐       ┌────────┴───────┐
      │ apps/ingestion │       │  apps/search   │
      └───────┬────────┘       └────────┬───────┘
              │      (never each other)  │
              └────────────┬─────────────┘
                           ▼
                   ┌───────────────┐
                   │ apps/embedding│  (depends on nothing but settings)
                   └───────┬───────┘
                           ▼
                 sentence_transformers
                 (local.py only, imported inside a method)
```

`apps/embedding` imports no other app. It takes text and returns floats; it has never
heard of a `Paper`.

### D2 — `typing.Protocol`, not an ABC

The fake and the local provider share no implementation worth inheriting, and a base
class invites logic to accumulate on it. A Protocol also means a future hosted provider
need not import anything from this project to satisfy the interface.

The cost is that shared contract rules — the empty-list short-circuit, the
whitespace-raises rule, normalization — cannot be enforced by inheritance. They are
stated in the protocol's docstring and enforced by a **shared test suite parametrized
over both implementations**, so a third provider added later gets the same scrutiny by
adding one line.

### D3 — Selection by dotted path plus `import_string`

```python
EMBEDDING_PROVIDER = "apps.embedding.local.LocalEmbeddingProvider"
```

resolved with `django.utils.module_loading.import_string`. This is Django's own idiom
for swappable backends (`STORAGES`, `AUTHENTICATION_BACKENDS`), and it means adding a
hosted provider requires no edit to a registry enum. The alternative — a short
`"local"`/`"fake"` enum behind a factory — is harder to point at something hostile but
would have to be edited by the very change the seam exists to make cheap.

The default is the **real** provider, not the fake. See D11 for why that is safe even
without the optional extra installed, and R2 for why the fake must never be the default.

### D4 — Two independent layers of laziness

These are separate mechanisms answering separate questions:

```
  layer 1: which object?          layer 2: when is the model loaded?
  ──────────────────────          ────────────────────────────────
  get_provider()                  provider.embed([...])
    @cache on a module factory      first call acquires a lock,
    + explicit reset()              imports and loads the model,
                                    verifies its dimension, memoizes
```

Constructing a provider is cheap and touches no model. `embed([])` returns `[]` without
loading anything — that guarantee only holds because loading is deferred to the first
*non-empty* call.

A `threading.Lock` guards the load. Under `runserver` this is nearly free; under a
threaded WSGI server it prevents two requests loading `all-MiniLM-L6-v2` concurrently
and briefly doubling resident memory. The synchronization is a few lines and buys a
lifecycle guarantee that is otherwise merely probable.

`reset()` is explicit rather than implicit. Tests do not mutate `EMBEDDING_PROVIDER`
underneath a process-global cache and hope; a root `conftest.py` autouse fixture calls
`reset()` so no provider leaks between tests.

### D5 — The dimension contract has three values, compared at three moments

A provider cannot know its dimension without loading a model, but D6 forbids loading a
model to run `manage.py check`. Both constraints hold only if the declaration is
separate from the reality:

```
  settings.EMBEDDING_DIMENSION = 384     ← the schema contract; HS-010's VectorField
            ║
            ║   system check — cheap, every manage.py invocation
            ▼
  provider.dimension           = 384     ← DECLARED, statically, by the implementation
            ║
            ║   assertion on first model load — once per process
            ▼
  model.get_sentence_embedding_dimension()   ← reality
```

The static model → dimension map is **owned by the implementation**, not a third
configuration source. `LocalEmbeddingProvider` carries `{"all-MiniLM-L6-v2": 384, ...}`
and derives `dimension` from `EMBEDDING_MODEL`; an unknown model name is a configuration
error raised at construction, not a silent default. Adding a model means editing that
map — deliberately, because that edit is exactly the moment someone should be reminded
that changing the model is a migration.

`FakeEmbeddingProvider` has no intrinsic dimension, so it adopts
`settings.EMBEDDING_DIMENSION`. The system check is therefore vacuous for the fake,
which is correct: the fake is not a schema risk, because a fake run is not meant to
populate anything durable.

Rejected: reading the dimension off the provider into HS-010's `VectorField`. That would
make every `makemigrations` depend on a loadable model.

### D6 — The system check is cheap and never loads a model

`manage.py check` runs on every `migrate`, every `runserver` boot and in every developer
loop. It compares `settings.EMBEDDING_DIMENSION` against `provider.dimension` — both
static — and reports an **error** when they disagree, because that mismatch will either
corrupt a column or crash an insert.

It also reports a **warning** when the fake provider is configured, so a misconfiguration
is visible on every invocation rather than discovered after 5,000 meaningless rows. That
warning is suppressed under pytest, following the idiom the codebase already uses twice
(`config/settings.py` gates `SECRET_KEY` on `"pytest" in sys.modules`, and the root
`conftest.py` sets a test-only key). Permanent warning noise in a test suite that
legitimately uses the fake would train people to ignore warnings, which is worse than
having none.

Inspecting `sys.modules` from a system check is mildly distasteful; consistency with an
established house idiom won over inventing a second convention.

### D7 — Vectors are L2-normalized, unconditionally, as part of the contract

Not a flag, not an implementation detail of the local provider — a promise of the
interface, which the fake must keep too. Two consequences:

- Cosine distance and inner product become equivalent, so HS-010 may choose
  `vector_ip_ops` for speed or `vector_cosine_ops` for clarity without the choice
  reaching back into this card.
- `all-MiniLM-L6-v2` is trained for cosine similarity and its own documentation
  recommends `normalize_embeddings=True`, so this costs nothing on the real path.

A configurable flag was rejected: two normalization modes would mean stored vectors whose
comparability depends on a setting that was true at write time.

### D8 — The input contract is about text, not tokens

```
  embed([])                       -> []            and the model is never loaded
  embed(["", "  ", "\t"])         -> ValueError
  embed(["higgs", "..."])         -> two unit vectors, in that order
```

The contract is defined on **non-whitespace content**, not on whether anything survives
tokenization. That distinction is what stops the fake from being stricter than the real
provider: a transformer happily embeds `"..."`, whereas a naive bag-of-words yields zero
tokens, a zero vector, and a `ZeroDivisionError` when normalized. Under this contract the
fake must fall back to hashing the raw string when tokenization yields nothing, so any
string a user can type behaves identically against both.

Raising on blank input rather than returning a zero vector is deliberate: a zero vector
is equidistant from everything and would return arbitrary "nearest" papers. Rejecting
blank input at the **HTTP boundary** is HS-011's job, and the precedent already exists —
`apps/search/views.py` rejects a blank `q` with 400, and `search_page` treats whitespace
as no query at all.

Signature: `Sequence[str]` in, so HS-010's batching loop can pass a slice or a tuple
without copying; `list[list[float]]` out, because that is what `psycopg` and `pgvector`
want and it keeps numpy out of the interface. The `.tolist()` on the real path is a real
cost at 5,000 x 384 floats, accepted in exchange for a dependency-free signature.

Order is guaranteed: output *i* corresponds to input *i*.

### D9 — The fake is a bag-of-words model, and it ships

Three fakes were considered:

| | Determinism | Distances | HS-011/HS-012 reach |
|---|---|---|---|
| hash → random floats | yes | meaningless | plumbing only |
| hand-fed lookup table | yes | stated per fixture | order asserted, reads artificially |
| **hashed bag-of-words** | yes | **meaningful** | order asserted, reads naturally |

The third is chosen because "the nearest vector ranks first" (HS-011) and "RRF prefers a
dual hit" (HS-012) are only real assertions if similar texts genuinely land near each
other. It costs roughly twenty lines.

Implementation notes that are load-bearing rather than incidental:

- **Stable hashing.** `hash("higgs")` is randomized per interpreter via `PYTHONHASHSEED`,
  so `zlib.crc32` (or `hashlib.blake2b`) is required. Without it, a vector written in one
  process and compared in another silently disagrees — precisely HS-010 writing and
  HS-011 asserting.
- **Dimension from the setting**, so the fake is drop-in against HS-010's
  `VectorField(dimensions=384)`.
- **Normalized**, per D7.
- **Raw-string fallback** when no tokens survive, per D8.

It ships as application code rather than living under `tests/` so that
`EMBEDDING_PROVIDER` can name it and HS-010's and HS-011's tests can configure it the
same way an operator would. The safety net for that exposure is the D6 warning and D10's
name.

### D10 — `model_name` is an embedding-space identifier, not a label

`model_name` joins `dimension` on the interface because HS-010 stamps it into
`Paper.embedding_model` and HS-011 must detect a mismatch between the model that wrote a
vector and the model asking the question. It identifies the *space*, so two providers
producing incomparable vectors must never share a name.

The fake's is `fake-bow-384` — self-incriminating on purpose. An operator who finds that
string in a production database column has been told exactly what went wrong.

### D11 — `sentence-transformers` is an optional extra

It pulls `torch`: hundreds of megabytes to low gigabytes, for a test suite that must
never touch it.

```
  uv sync                              django, drf, httpx, psycopg      (~40 MB)
  uv sync --extra local-embeddings     + sentence-transformers, torch   (~1 GB)
```

An extra was verified to work alongside `[tool.uv] package = false` before being chosen
(uv 0.11.16, scratch project, `uv sync --extra` installed cleanly). A PEP 735 dependency
group was the alternative and the repository already uses one for `dev`, but groups can
be pulled in implicitly via `default-groups` whereas an extra is never implicit — and
"you cannot install `torch` by accident" is the guarantee worth optimizing for. An extra
is also the semantically honest choice: this is an optional *runtime* feature an operator
opts into, not a development tool.

The consequence is mandatory: `local.py` imports `sentence_transformers` **inside** the
load method. A module-level import would make `apps/embedding` unimportable — and
therefore `manage.py` unusable — on a machine that ran a plain `uv sync`.

This is also what makes D3's default safe. With the extra absent and the real provider
configured, `manage.py`, the system check and the entire test suite work; the failure
arrives at the first genuine `embed()` call, loudly, as an `ImportError` naming the
extra. Defaulting to the fake would trade that loud, late failure for a silent, permanent
one.

### D12 — The slow test is deselected by default and skipped when uninstallable

```toml
markers = ["slow: requires a downloaded model; excluded from the default run"]
addopts = "-m 'not slow' --strict-markers"
```

`pytest -m slow` overrides the `addopts` marker expression, so opting in stays a single
flag. `--strict-markers` is added while the section is open, so a typo'd
`@pytest.mark.slwo` fails instead of silently running.

Deselection alone is not enough: pytest **collects before it deselects**, so a
module-level `from sentence_transformers import ...` would crash the default run on a
machine without the extra.

`pytest.importorskip("sentence_transformers")` therefore guards the import — but at
**fixture** scope, not module scope, which is a correction to this decision made during
implementation. Module scope fixes the crash and creates a different problem: collection
still runs, so on a machine *with* the extra installed the default suite pays for
importing torch. Measured, that was 3.1 s → 15.2 s, and the card requires the default run
to stay fast. Fixture scope pays the import only when a slow test actually runs, and
still skips rather than crashes when the extra is absent. Nothing else in the module
needs the library, because `apps/embedding/local.py` imports it lazily by design.

The model cache stays outside the repository, in the user's standard Hugging Face cache,
where it is shared across projects and never at risk of being committed. `.gitignore`
already covers `.cache/`, `models/` and `.sentence_transformers/` should anyone
deliberately relocate it.

### D13 — AGENTS.md is amended in this commit

§3's tree gains `apps/embedding`, the dependency rule gains the two arrows into it, and
the sentence claiming `apps/papers` "knows nothing about ... embeddings" is corrected —
`papers` still knows nothing about embedding *providers*, but HS-010 puts a vector column
on it, so the blanket phrasing would become false one card later. AGENTS.md's own rule
requires this: "if a decision here turns out to be wrong, change this file in the same
commit that changes the behaviour."

### D14 — Batching is the caller's concern

HS-010 needs a configurable batch size for **resumability** — how much work is lost to a
Ctrl+C. `sentence-transformers` has its own internal `batch_size` for **throughput**.
Same word, different concerns, and conflating them would make one setting silently govern
the other. The provider accepts whatever sequence it is given and may batch internally as
an implementation detail; the resumable outer batching belongs to HS-010's command and is
named separately there.

## Risks / Trade-offs

**A contributor runs a plain `uv sync` and hits `ImportError` on first embed** →
Deliberate. Mitigated by naming the extra in the error path, in `.env.example` and in
AGENTS.md §5's command list. The alternative (defaulting to the fake) fails silently and
durably, which is strictly worse.

**The fake is importable in production and could be configured by accident** → The D6
system check warns on every `manage.py` invocation outside tests, and D10's
`fake-bow-384` identifier makes a wrong run self-evident in the database. HS-011's
model-mismatch check then refuses to query a corpus embedded by a different space.

**Two providers could disagree about the dimension without anyone noticing** → The D5
three-way contract: cheap static comparison at every check, real verification at model
load. The remaining window is a model whose published dimension differs from the map's
entry, which the load-time assertion closes.

**`PYTHONHASHSEED` makes the fake non-deterministic across processes** → Identified
during design, closed by requiring `zlib.crc32`. A test asserts that the same text embeds
identically in a fresh interpreter, so the bug cannot return quietly.

**`.tolist()` on 5,000 x 384 floats is wasted work** → Accepted. It keeps numpy out of the
interface signature; if HS-010's real run shows it to be material, the conversion can move
without changing the contract.

**A Protocol cannot enforce the contract** → Mitigated by a shared test suite parametrized
over every implementation, so contract coverage is obtained by registration rather than by
discipline.

**Inspecting `sys.modules` from a system check is a smell** → Accepted for consistency
with the existing house idiom; inventing a second "are we testing?" convention would be
worse than reusing a slightly ugly one.
