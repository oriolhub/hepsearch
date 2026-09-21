# HS-019: Run lint and tests in continuous integration

**Status:** done
**Depends on:** HS-001

## Story

As a contributor, I want every push and pull request to run the same lint and test
commands I run locally, so that a broken commit is caught by the repository rather
than by the next person who clones it.

## Context

The project has enforced `uv run pytest`, `uv run ruff check .` and
`uv run ruff format --check .` in every card's definition of done since HS-001, but
nothing verified them outside the author's machine. A public repository with 250+
tests and no evidence they pass asks a reader to take the test suite on trust.

The database is a service container rather than Compose: GitHub Actions already
owns container lifecycle and health-gating, so `compose.yaml` would only duplicate
it. The image tag is pinned to the same tag Compose uses, because a CI database on
a different pgvector or PostgreSQL major than the development one would test
something nobody runs.

The run stays offline. AGENTS.md §6 requires the default test run to download no
model, so CI installs a plain `uv sync` without the `local-embeddings` extra;
`slow` is already deselected by pyproject's `addopts`.

## Acceptance criteria

- [x] Lint, format check and tests run on every push to `main` and every pull request
- [x] The three commands are byte-for-byte the ones in every card's definition of done
- [x] Tests run against pgvector on the same image tag as `compose.yaml`
- [x] Migrations are applied during the run, covering `CreateExtension("vector")`
      and the HNSW index build, because pytest-django builds the test database
- [x] The database role is a superuser, which migration `papers/0003` requires
- [x] No database environment variables are duplicated: the service publishes 5433
      to match `POSTGRES_PORT`'s default in `config/settings.py`
- [x] No `SECRET_KEY` is configured; `config/settings.py` generates one under pytest
- [x] No embedding model is downloaded during the run
- [x] A superseded run is cancelled when the same branch is pushed again

## Definition of done

- [x] Acceptance criteria met
- [x] `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` pass
- [x] Committed as `HS-019: Run lint and tests in continuous integration`

## Out of scope

A Python version matrix (the project pins 3.13 in `.python-version`), coverage
measurement and upload, deployment, publishing a container image, and running the
`slow` model-dependent tests on a schedule.
