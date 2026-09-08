## 1. Project manifest and environment

- [x] 1.1 Create `.python-version` pinning 3.13
- [x] 1.2 Create `pyproject.toml` with `[project]`: `name = "hepsearch"`, a
      version, and `requires-python = ">=3.13"`, leaving `dependencies` empty
- [x] 1.3 Add `[tool.uv]` with `package = false` and confirm no `[build-system]`
      table is present (D1)
- [x] 1.4 Add `[dependency-groups]` with a `dev` group containing `pytest`,
      `pytest-django` and `ruff` (D6)
- [x] 1.5 Run `uv sync` and confirm it exits 0, creates `.venv/`, generates
      `uv.lock`, and does not attempt to build the project itself
- [x] 1.6 Confirm `uv.lock` is not excluded by `.gitignore` and will be committed

## 2. Lint and format configuration

- [x] 2.1 Add `[tool.ruff]` with `line-length = 100` and `target-version` matching
      Python 3.13
- [x] 2.2 Add `[tool.ruff.lint]` selecting `E4`, `E7`, `E9`, `F`, `I`, `UP`, `B`,
      `DJ`, `RUF` (D4)
- [x] 2.3 Run `uv run ruff check .` and confirm exit 0 on the clean tree
- [x] 2.4 Run `uv run ruff format .`, then `uv run ruff format --check .` and
      confirm exit 0
- [x] 2.5 Verify the `I` rule fires: temporarily disorder imports in a scratch
      file, confirm a violation is reported, then delete the scratch file
- [x] 2.6 Verify the `B` rule fires: temporarily add a function with a mutable
      default argument, confirm a violation is reported, then delete it

## 3. Test harness configuration

- [x] 3.1 Add `[tool.pytest.ini_options]` with `pythonpath = ["."]` (D2)
- [x] 3.2 Set `testpaths = ["tests", "apps"]` so both locations are discovered,
      tolerating that `apps/` does not exist yet (D8)
- [x] 3.3 Add a comment recording that `DJANGO_SETTINGS_MODULE` is deliberately
      absent and is configured by the change that creates the Django project (D3)
- [x] 3.4 Confirm no `sys.path` manipulation exists in any test file or
      `conftest.py`

## 4. Environment smoke test

- [x] 4.1 Create `tests/` and `tests/test_environment.py`
- [x] 4.2 Write `test_python_version` asserting the running interpreter is
      3.13 or newer
- [x] 4.3 Write a test asserting the repository root resolves on the import path
- [x] 4.4 Confirm neither test contains `assert True` or an equivalent vacuous
      assertion (D7)
- [x] 4.5 Run `uv run pytest` and confirm tests are collected, pass, and the
      command exits 0 rather than 5
- [x] 4.6 Run `uv run pytest tests/test_environment.py::test_python_version -q`
      and confirm the single-test selector works
- [x] 4.7 Confirm collection succeeds with no `DJANGO_SETTINGS_MODULE` set
      anywhere in the environment or configuration

## 5. Line ending policy

- [x] 5.1 Create `.gitattributes` with `* text=auto` and explicit `eol=lf` for
      `*.py`, `*.md`, `*.toml`, `*.yaml`, `*.yml` (D9)
- [x] 5.2 Renormalize the index with `git add --renormalize .`
- [x] 5.3 Run `git add -A` and confirm no "LF will be replaced by CRLF" warning
      is emitted

## 6. Board amendments

- [x] 6.1 In `board/backlog/HS-001-project-tooling.md`, remove the `.env.example`
      acceptance criterion (D10)
- [x] 6.2 In the same card, reword the `.gitignore` criterion as a verification
      that the HS-000 foundation commit already satisfied it
- [x] 6.3 In the same card, replace the vague tooling criteria with the concrete
      decisions: `package = false`, `pythonpath = ["."]`,
      `testpaths = ["tests", "apps"]`, the ruff rule set, line length 100, and
      deferred `pytest-django` configuration
- [x] 6.4 In the same card, replace the throwaway placeholder-test criterion with
      the surviving smoke test, and add the `.gitattributes` criterion
- [x] 6.5 In `board/backlog/HS-002-docker-postgres-pgvector.md`, add an
      acceptance criterion that it creates `.env.example`
- [x] 6.6 Add `uv run ruff format --check .` to the definition of done in
      `board/TEMPLATE.md`
- [x] 6.7 Add the same gate to the definition of done in every card in
      `board/backlog/`
- [x] 6.8 Update `AGENTS.md` §5 to list `ruff format --check` among the commands
      and §6 to state that both gates are enforced

## 7. Verification and commit

- [x] 7.1 Delete `.venv/` and re-run `uv sync` from scratch to prove a clean
      checkout installs in one command
- [x] 7.2 Run the full gate set: `uv run ruff check .`,
      `uv run ruff format --check .`, `uv run pytest` — all exit 0
- [x] 7.3 Confirm `.venv/`, `.pytest_cache/` and `.ruff_cache/` are untracked and
      that `.env` is absent
- [x] 7.4 `git mv board/backlog/HS-001-project-tooling.md board/in-progress/` at
      the start of implementation, and to `board/done/` in the finishing commit
- [x] 7.5 Tick every acceptance criterion checkbox in the HS-001 card to reflect
      reality before committing
- [x] 7.6 Commit as `HS-001: Set up Python tooling and the test harness` with a
      body explaining why application mode and the import path had to be explicit
