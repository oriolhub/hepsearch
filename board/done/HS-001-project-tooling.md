# HS-001: Set up Python tooling and the test harness

**Status:** done
**Depends on:** nothing
**OpenSpec change:** `bootstrap-python-tooling`

## Story

As a developer, I want a reproducible Python environment with linting and a
working test runner, so that every later card can be verified by running one
command instead of by reading the diff.

## Context

`uv` manages the environment and the lockfile; `ruff` owns formatting and
linting; `pytest` runs the tests. See AGENTS.md §2 and §5.

Nothing Django-specific is configured here — this card must be finishable and
verifiable before a Django project exists. `pytest-django` is *installed* now but
deliberately left *unconfigured*, because `DJANGO_SETTINGS_MODULE` does not exist
until HS-003 and HS-003 transitively depends on this card.

Design decisions and their alternatives are recorded in
`openspec/changes/bootstrap-python-tooling/design.md`. Two of them are
load-bearing and fail loudly if skipped: **application mode** (`uv` will
otherwise try to build a `hepsearch` package that does not exist) and the
**import path** (`apps.*` imports will otherwise fail at HS-004).

## Acceptance criteria

### Manifest and environment

- [x] `pyproject.toml` declares `name = "hepsearch"` and `requires-python = ">=3.13"`
- [x] `[project.dependencies]` is empty — this card adds no runtime dependency
- [x] `[tool.uv]` sets `package = false` **and** no `[build-system]` table exists
- [x] `.python-version` pins 3.13
- [x] `[dependency-groups]` declares a `dev` group with `pytest`, `pytest-django`
      and `ruff`
- [x] `uv sync` on a clean checkout exits 0, and does **not** attempt to build the
      project itself
- [x] `uv.lock` is generated and committed

### Lint and format

- [x] Ruff selects `E4`, `E7`, `E9`, `F`, `I`, `UP`, `B`, `DJ`, `RUF`
- [x] `line-length = 100`
- [x] `uv run ruff check .` exits 0 on a clean tree
- [x] `uv run ruff format --check .` exits 0 on a clean tree and leaves files
      unmodified
- [x] The `I` and `B` rules are demonstrated to actually fire (disorder an import
      / add a mutable default in a scratch file, observe the violation, delete it)

### Test harness

- [x] `[tool.pytest.ini_options]` sets `pythonpath = ["."]`
- [x] `testpaths = ["tests", "apps"]`, so project-level and per-app tests are both
      discovered
- [x] A comment records that `DJANGO_SETTINGS_MODULE` is absent on purpose and is
      configured by HS-003
- [x] `uv run pytest` collects and passes at least one test, exiting **0** — not
      the exit code 5 that pytest returns for an empty suite
- [x] `uv run pytest tests/test_environment.py::test_python_version -q` runs that
      single test
- [x] Collection succeeds with no `DJANGO_SETTINGS_MODULE` set anywhere
- [x] No `sys.path` manipulation exists in any test file or `conftest.py`

### Smoke test

- [x] `tests/test_environment.py` asserts the interpreter is Python 3.13 or newer
- [x] It asserts the repository root resolves on the import path
- [x] It contains no `assert True` or equivalent vacuous assertion — this test
      survives into later cards rather than being deleted at HS-004

### Repository hygiene

- [x] `.gitattributes` declares `* text=auto` and `eol=lf` for `*.py`, `*.md`,
      `*.toml`, `*.yaml`, `*.yml`
- [x] After renormalizing, `git add -A` emits no "LF will be replaced by CRLF"
      warning
- [x] **Verify** (do not re-create) that `.gitignore` already covers `.venv/`,
      `__pycache__/`, `*.pyc`, `.env`, `.pytest_cache/`, `.ruff_cache/` and model
      caches — the HS-000 foundation commit added it
- [x] `.venv/`, `.pytest_cache/` and `.ruff_cache/` are untracked; `.env` is absent

## Definition of done

- [x] Acceptance criteria met
- [x] Deleting `.venv/` and re-running `uv sync` reproduces a working environment
- [x] `uv run pytest` passes
- [x] `uv run ruff check .` passes
- [x] `uv run ruff format --check .` passes
- [x] AGENTS.md updated if a decision changed
- [x] Committed as `HS-001: Set up Python tooling and the test harness` with the
      card moved to `board/done/`

## Out of scope

Django itself and any settings module (HS-003), any database (HS-002),
`.env.example` (created by HS-002 — the first card that reads an environment
variable), `mypy`, coverage thresholds, and CI (a recorded v1 non-goal).
