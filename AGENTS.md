# AGENTS.md — hepsearch

Single source of truth for anyone (human or agent) working in this repository.
Read this before writing code. If a decision here turns out to be wrong, change
this file in the same commit that changes the behaviour.

---

## 1. What this project is

**hepsearch** is a Django + Django REST Framework + PostgreSQL application that
provides **semantic search over high-energy-physics literature** sourced from the
public INSPIRE-HEP API.

A user asks a question in natural language — *"how do we measure the Higgs
self-coupling?"* — and gets back ranked, genuinely relevant papers, even when the
papers never use the words in the query.

### Definition of done (v1)

> A user can type a natural-language physics question into a web page and get
> back ranked, relevant HEP papers with title, authors, abstract snippet, and a
> link to INSPIRE — served by a DRF API over a locally ingested and embedded
> 5,000-paper corpus, with tests and docs.

### Explicit non-goals

Do not build these. Do not propose these. They are out of scope for v1:

- User accounts, personalization, saved searches
- Full-text PDF ingestion (INSPIRE gives us abstracts; that is enough)
- LLM answer generation (v2 — the retrieval layer must be good first)
- Mirroring all of INSPIRE (~1.5M records; we ingest a bounded slice)
- Production deployment, Kubernetes, autoscaling
- HEPData numeric tables (see §4.3)

---

## 2. Stack and why

| Concern | Decision | Why |
|---|---|---|
| Language | Python 3.13 | |
| Framework | Django 5.2 LTS | LTS, and `django.contrib.postgres` gives full-text search for free |
| API | Django REST Framework | |
| Database | PostgreSQL + `pgvector` | One datastore for rows *and* vectors — no second system to sync, back up, or keep consistent |
| Package manager | `uv` | Fast, single tool for `pyproject.toml` + lockfile |
| Lint/format | `ruff` | Replaces black + isort + flake8 |
| Tests | `pytest` + `pytest-django` | |
| Settings | `django-environ` + `.env` | Typed env parsing |
| Embeddings | Pluggable interface, local `sentence-transformers` as default | No API key, no per-query cost, works offline |
| Frontend | DRF JSON API + minimal Django templates | The API is the product; the page proves it |
| Background work | Synchronous management commands | Ingestion is a batch job an operator runs, not a request-path concern. No Celery, no Redis, no broker |
| Local infra | Docker Compose for **Postgres only** | Django runs on the host via `uv` for a fast edit-reload loop |
| CI | None yet | Deliberate; add later if it earns its place |

### Things we deliberately did not add

Celery, Redis, a separate vector database, a JS frontend, Kubernetes, a service
layer of abstract base classes. If you feel the urge to add one, first write down
which acceptance criterion currently fails without it.

---

## 3. Architecture

```
config/                 Django project: settings, urls, wsgi/asgi
apps/
  papers/               Domain: the Paper model, admin, migrations
  ingestion/            INSPIRE client + management commands that fill the corpus
  search/               Query parsing, ranking, DRF views/serializers, templates
board/                  The local task board (see §7)
```

### Dependency rule

```
search  ──▶ papers
ingestion ──▶ papers
search  ──✗  ingestion        (never)
papers  ──✗  anything          (the domain depends on nothing)
```

`apps/papers` is the centre. It knows nothing about INSPIRE, HTTP, or embeddings.
`apps/ingestion` may import `papers` models; `apps/search` may import `papers`
models. **`search` and `ingestion` must never import each other.** If they need
to share something, it belongs in `papers`.

### The three layers that matter

1. **Ingestion** — talks to INSPIRE, normalizes messy external JSON into `Paper`
   rows. This is the only place that knows INSPIRE's field names exist.
2. **Embedding** — a provider interface (`embed(texts) -> list[vector]`) with a
   local sentence-transformers implementation. Nothing outside the provider
   imports `sentence_transformers`. Swapping to a hosted API must touch one file.
3. **Retrieval** — turns a user query into ranked `Paper` rows. Grows in three
   increments: full-text → vector → hybrid fusion. Each increment ships working.

### Search evolution (deliberately incremental)

| Increment | Mechanism | Why not skip to the end |
|---|---|---|
| 1 | PostgreSQL full-text (`SearchVector`/`SearchRank`) | Ships user value with zero ML dependencies, and becomes the baseline we measure against |
| 2 | `pgvector` cosine similarity over abstract embeddings | The actual semantic feature |
| 3 | Hybrid: fuse both with Reciprocal Rank Fusion | Pure vector search fails badly on exact tokens — `ATLAS`, `arXiv:2609.04868`, an author's name. Keyword search fails on paraphrase. Neither alone is good enough |

Do not delete the full-text path once vectors work. It is half of the final ranker.

---

## 4. The data source

### 4.1 INSPIRE-HEP API — verified behaviour

Base: `https://inspirehep.net/api/literature`. No auth, no API key.

```
GET /api/literature?q=<query>&fields=<csv>&size=<n>&page=<n>&sort=mostrecent
```

Verified against the live API:

- `size` **caps at 1000**; `size=1001` returns `400 BAD REQUEST`
- Deep pagination works (`page=400` at `size=25` returns `200`)
- `fields=` trims the response — always use it; full records are enormous
- No rate-limit headers are returned, which is not permission to hammer it.
  Ingestion must throttle politely and set a descriptive `User-Agent`

Response shape: `hits.total` (int), `hits.hits[].metadata`.

### 4.2 Field reality — assume almost everything is missing

This is the single most important ingestion fact. Observed on live records:

| Field | Reliability | Notes |
|---|---|---|
| `control_number` | Always present | **The stable INSPIRE id — use it as the natural key** |
| `titles[0].title` | Always present | |
| `abstracts[].value` | **~90% of records** | Multiple abstracts with different `source` values are common |
| `authors[].full_name` | Usually | Can be 50+ entries; collaboration papers can be thousands |
| `arxiv_eprints[0]` | Usually | Has `value` and `categories[]` |
| `dois` | **Often absent entirely** | Preprints have no DOI. Indexing it as null-array crashes naive code |
| `publication_info` | **Often absent entirely** | Unpublished preprints |
| `earliest_date`, `citation_count`, `document_type`, `texkeys`, `inspire_categories` | Usually | |

Consequences that are **not** negotiable:

- Every field except `control_number` and `title` is nullable on the model.
- **Ingestion skips records with no abstract.** A paper with no abstract cannot
  be embedded and pollutes results. To land 5,000 usable papers, fetch ~5,600.
- Never index into a possibly-absent list. `metadata.get("dois", [{}])[0]` is a
  crash waiting to happen.

### 4.3 HEPData — dropped, and why

HEPData (`hepdata.net`) is behind Cloudflare and returns **403 Forbidden** to
programmatic requests, including with a browser `User-Agent`. Its payload is also
numeric measurement tables, which are a poor fit for text embeddings. It is out
of scope. Do not reintroduce it without a working access story.

### 4.4 The corpus

Default slice: **Higgs boson physics**, ~5,000 papers with abstracts.

The ingestion command takes the INSPIRE query as an argument — the topic is a
default, not a hardcoded constant.

---

## 5. Commands

> The repository currently contains this documentation and the board. The code
> skeleton is built by the board cards, in order. Commands below are the target
> contract — a card is not done until its commands work.

```powershell
# Infrastructure (Postgres + pgvector only; Django runs on the host)
docker compose up -d
docker compose down

# Dependencies
uv sync                          # install from the lockfile
uv add <package>                 # add a dependency (never edit pyproject by hand)

# Django
uv run python manage.py migrate
uv run python manage.py runserver
uv run python manage.py createsuperuser

# Fill the corpus
uv run python manage.py ingest_inspire --query "higgs boson" --limit 5000
uv run python manage.py embed_papers            # only embeds rows missing a vector

# Tests
uv run pytest                                   # whole suite
uv run pytest apps/search                       # one app
uv run pytest apps/search/tests/test_ranking.py # one file
uv run pytest apps/search/tests/test_ranking.py::test_rrf_prefers_dual_hits   # ONE test
uv run pytest -k "rrf and not slow"             # by expression
uv run pytest -x -q --lf                        # stop at first failure, rerun last failures

# Lint & format
uv run ruff check .
uv run ruff check . --fix
uv run ruff format .
```

---

## 6. Conventions

### Ingestion must be idempotent

`ingest_inspire` is re-run constantly during development. It upserts on
`inspire_id` (`control_number`). Running it twice must not duplicate a row.
Same for `embed_papers`: it only processes papers whose embedding is null, so
re-running is cheap and resumable after an interrupt.

### Embeddings

- One vector per paper, over `title + "\n" + abstract`.
- Default model `all-MiniLM-L6-v2`, **384 dimensions** — the `VectorField` dim
  and the model must not drift apart. Changing models is a migration.
- No chunking. Abstracts are ~1,200 characters, comfortably inside the model's
  512-token window. Chunking is for full texts we do not have.

### Tests

- `pytest` + `pytest-django`. Test files live in `apps/<app>/tests/`.
- **Never hit the INSPIRE network in a test.** Ingestion tests run against a
  small committed JSON fixture of real INSPIRE responses — including at least one
  record with no abstract and one with no DOI, because those are the cases that
  break things.
- Tests that need the database use `@pytest.mark.django_db`.
- Test the ranking maths directly, without the database, where possible.

### API shape

Read-only and public. DRF throttling is on; ingestion is admin/CLI only.
Search results always carry an INSPIRE link built from `inspire_id`
(`https://inspirehep.net/literature/<inspire_id>`).

### Code style

`ruff` decides formatting; do not argue with it. Keep functions small and I/O at
the edges — the ranking logic should be testable without a database or a network.

---

## 7. Workflow

### The board

`board/` is a local Jira-like board of markdown cards.

```
board/backlog/       Not started
board/in-progress/   Being worked on right now (keep this to ONE card)
board/done/          Finished and committed
```

Cards are `HS-NNN-short-slug.md` and carry a user story, acceptance criteria, a
definition of done, and dependencies. **Moving a card between folders is a `git
mv`, and it happens in the same commit as the work.** The board's history is the
project's history.

Cards later become user stories, so write acceptance criteria as if a QA engineer
who has never seen the code has to verify them.

### Commits

Format, mirroring the team's existing style:

```
HS-007: Add full-text search endpoint

WHY the change was needed, not what the diff shows.
```

- One purpose per commit. Tests ship in the same commit as the code they cover.
- Title ≤72 chars, imperative, capitalized, no trailing period.
- The `HS-NNN` id must match the card being worked on.

### Baby steps

Every card must leave the application working and demonstrable. If a card cannot
be finished without breaking `main`, it is too big — split it.

---

## 8. For agents specifically

- Read this file before proposing anything. Read the card you are working on.
- **Work one card at a time.** Do not batch three cards into one commit.
- Do not add a dependency, a service, or an abstraction that no acceptance
  criterion requires. Ask first.
- Prefer the standard library and what Django already ships. Django has full-text
  search, caching, pagination, an admin, and a test client. Use them before
  reaching for a package.
- When a card's acceptance criteria are ambiguous, ask — do not guess and build.
- Windows host: use PowerShell syntax and backslash paths in commands.
