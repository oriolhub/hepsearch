# HS-001: Set up Python tooling and the test harness

**Status:** backlog
**Depends on:** nothing

## Story

As a developer, I want a reproducible Python environment with linting and a
working test runner, so that every later card can be verified by running one
command instead of by reading the diff.

## Context

`uv` manages the environment and the lockfile; `ruff` owns formatting and
linting; `pytest` + `pytest-django` runs the tests. See AGENTS.md §2 and §5.

Nothing Django-specific belongs here yet — this card must be finishable and
verifiable before a Django project exists.

## Acceptance criteria

- [ ] `pyproject.toml` declares `requires-python = ">=3.13"` and project name `hepsearch`
- [ ] `uv sync` creates the environment from a committed `uv.lock`
- [ ] `ruff` is configured in `pyproject.toml` with a line length and a rule set,
      and `uv run ruff check .` exits 0 on a clean tree
- [ ] `pytest` is configured in `pyproject.toml` (`[tool.pytest.ini_options]`)
- [ ] A trivial placeholder test exists and `uv run pytest` reports it passing
- [ ] `.gitignore` covers `.venv/`, `__pycache__/`, `*.pyc`, `.env`,
      `.pytest_cache/`, `.ruff_cache/`, and local model caches
- [ ] `.env.example` exists, is committed, and lists every variable the project
      will read — with placeholder values, never real secrets
- [ ] `.env` is git-ignored and is **not** committed

## Definition of done

- [ ] Acceptance criteria met
- [ ] `uv run pytest` and `uv run ruff check .` both pass
- [ ] Committed as `HS-001: Set up Python tooling and the test harness`

## Out of scope

Django itself (HS-003), any database (HS-002), CI (deliberately not in v1).
