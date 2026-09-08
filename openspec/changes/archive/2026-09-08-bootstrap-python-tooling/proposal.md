## Why

hepsearch has an agreed architecture (`AGENTS.md`) and a 15-card board, but no
Python project — there is no way to install a dependency, run a linter, or
execute a test. Every subsequent card's definition of done is stated as "`uv run
pytest` and `uv run ruff check .` pass", so none of them are verifiable until
this exists.

Exploration of board card `HS-001` surfaced four defects in it that would each
have forced the implementer to guess, two of which fail loudly (a `uv sync`
error, and unimportable `apps.*` packages at HS-004). This change fixes the card
and delivers the tooling it describes.

## What Changes

- Add `pyproject.toml` declaring `hepsearch`, `requires-python >= 3.13`, and
  **application mode** (`[tool.uv] package = false`, no build backend) so `uv`
  does not attempt to build a distribution package that does not exist.
- Add a committed `uv.lock` and a `.python-version` pin so every environment
  resolves identically.
- Declare dev dependencies via PEP 735 `[dependency-groups]`, installed by
  `uv sync` by default: `pytest`, `pytest-django`, `ruff`.
- Configure `ruff` with `E4, E7, E9, F, I, UP, B, DJ, RUF` at a 100-character
  line length. Both `ruff check` and `ruff format --check` become gates.
- Configure `pytest` with `pythonpath = ["."]` and
  `testpaths = ["tests", "apps"]`, so `apps.*` imports resolve from HS-004
  onward and project-level tests have a permanent home.
- Install `pytest-django` now but **defer its configuration**
  (`DJANGO_SETTINGS_MODULE`) to HS-003, resolving a circular dependency: the card
  as written required Django settings that HS-003 has not yet created.
- Add `tests/test_environment.py`, a smoke test that asserts the interpreter
  version and that the repository root is importable. It replaces the card's
  throwaway `assert True` placeholder and survives into later cards.
- Add `.gitattributes` to normalize line endings, ending the 28 LF/CRLF warnings
  currently emitted on every `git add`.
- **Amend board card HS-001**: remove the `.env.example` acceptance criterion
  (unverifiable — the project reads zero environment variables at this point;
  HS-002 and HS-003 already own it), and note that the `.gitignore` criterion was
  satisfied by the HS-000 foundation commit and is now a verification step.
- **Amend HS-002** to explicitly own the creation of `.env.example`.
- **Amend `board/TEMPLATE.md` and the remaining backlog cards** so
  `ruff format --check` appears in every definition of done, not only HS-001's.

Not breaking: there is no existing behaviour to break.

## Capabilities

### New Capabilities
- `python-tooling`: The developer environment contract — how dependencies are
  declared, resolved and installed; how code is linted and formatted; how tests
  are discovered, imported and executed; and which of these are enforced gates.

### Modified Capabilities

None. This is the first capability in the project.

## Impact

**Created**: `pyproject.toml`, `uv.lock`, `.python-version`, `.gitattributes`,
`tests/test_environment.py`.

**Modified**: `board/backlog/HS-001-project-tooling.md`,
`board/backlog/HS-002-docker-postgres-pgvector.md`, `board/TEMPLATE.md`, and the
definition-of-done section of the remaining backlog cards.

**Dependencies added**: `pytest`, `pytest-django`, `ruff` (dev group only). No
runtime dependencies — Django itself arrives in HS-003.

**Downstream**: unblocks every board card. The `pythonpath` decision is a
prerequisite for HS-004's `apps.papers` imports; the `DJ` ruff rules directly
target the nullable-field modelling that HS-004 must get right, given that
INSPIRE's `dois` and `publication_info` are frequently absent
(`AGENTS.md` §4.2).

**Verified constraints**: `uv 0.11.16`, `Python 3.13.1`, `Docker 29.5.3` and
`git 2.55` are present on the development machine. A dry-run resolution
confirmed `sentence-transformers 6.0.1` and `torch 2.14.0` install cleanly on
Python 3.13/Windows, retiring the risk that the pinned interpreter would block
HS-009.

**Out of scope**: Django, any database, `.env`/settings handling, CI. Those
belong to HS-002, HS-003 and a deliberate non-goal respectively.
