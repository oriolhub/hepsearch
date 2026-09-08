## ADDED Requirements

### Requirement: Reproducible environment creation

The project SHALL be installable from a clean checkout with a single command,
resolving to identical package versions on every machine.

#### Scenario: Clean checkout installs successfully
- **WHEN** a developer runs `uv sync` in a freshly cloned repository
- **THEN** a virtual environment is created and every dev dependency is installed
- **AND** the command exits with status 0

#### Scenario: Resolution is pinned, not floating
- **WHEN** `uv sync` runs
- **THEN** package versions are taken from a committed `uv.lock`
- **AND** no dependency resolution is performed against the network for versions
  already present in the lockfile

#### Scenario: Interpreter version is pinned
- **WHEN** `uv sync` runs on a machine with several Python versions installed
- **THEN** the interpreter selected is the one recorded in `.python-version`
- **AND** that version satisfies `requires-python = ">=3.13"` declared in
  `pyproject.toml`

### Requirement: Application mode, not package mode

The project SHALL be treated by `uv` as an application rather than a
distributable library, because the source lives in `apps/` and `config/` and
there is no importable `hepsearch` top-level package to build.

#### Scenario: uv does not attempt to build the project
- **WHEN** `uv sync` runs
- **THEN** `uv` does not attempt to build or install the project itself as a
  distribution
- **AND** no error is raised about a missing package directory or a missing build
  backend

#### Scenario: Application mode is explicit in configuration
- **WHEN** a developer inspects `pyproject.toml`
- **THEN** `[tool.uv]` sets `package = false`
- **AND** no `[build-system]` table declares a build backend

### Requirement: Dev dependencies are declared as a group

Development-only tooling SHALL be declared in a PEP 735 `[dependency-groups]`
`dev` group, keeping it separate from the runtime dependencies that later cards
introduce.

#### Scenario: Dev group is installed by default
- **WHEN** `uv sync` runs without additional flags
- **THEN** `pytest`, `pytest-django` and `ruff` are installed
- **AND** they are declared under `[dependency-groups]`, not under
  `[project.dependencies]`

#### Scenario: Runtime dependency list is empty
- **WHEN** a developer inspects `[project.dependencies]` in `pyproject.toml`
- **THEN** it contains no entries, because Django arrives in a later change

### Requirement: Linting is an enforced gate

The project SHALL enforce a configured `ruff` rule set, and a violation SHALL
fail the gate with a non-zero exit status.

#### Scenario: Clean tree passes linting
- **WHEN** `uv run ruff check .` runs against an unmodified checkout
- **THEN** it reports no violations and exits with status 0

#### Scenario: Configured rule set is active
- **WHEN** a developer inspects the `ruff` configuration in `pyproject.toml`
- **THEN** the selected rules include `E4`, `E7`, `E9`, `F`, `I`, `UP`, `B`, `DJ`
  and `RUF`
- **AND** the configured line length is 100

#### Scenario: An unsorted import is rejected
- **WHEN** a Python file contains imports in non-alphabetical order
- **AND** `uv run ruff check .` runs
- **THEN** the `I` rule reports a violation and the command exits non-zero

#### Scenario: A mutable default argument is rejected
- **WHEN** a function is defined with a mutable default argument such as `[]`
- **AND** `uv run ruff check .` runs
- **THEN** the `B` rule reports a violation and the command exits non-zero

### Requirement: Formatting is an enforced gate

Code formatting SHALL be verifiable in a non-mutating check, so that formatting
drift fails a gate rather than silently accumulating in future diffs.

#### Scenario: Clean tree passes the format check
- **WHEN** `uv run ruff format --check .` runs against an unmodified checkout
- **THEN** it reports that all files are already formatted and exits with status 0

#### Scenario: Misformatted code fails the check without being modified
- **WHEN** a file's formatting deviates from `ruff format` output
- **AND** `uv run ruff format --check .` runs
- **THEN** the command exits non-zero
- **AND** the file on disk is left unchanged

### Requirement: Test discovery and execution

The project SHALL discover and run tests through `pytest`, reporting success with
exit status 0.

#### Scenario: Test suite runs and passes
- **WHEN** `uv run pytest` runs against a clean checkout
- **THEN** at least one test is collected and passes
- **AND** the command exits with status 0, not the status 5 that `pytest` returns
  when no tests are collected

#### Scenario: Both test locations are discovered
- **WHEN** a developer inspects the `pytest` configuration in `pyproject.toml`
- **THEN** `testpaths` includes both `tests` and `apps`
- **AND** project-level tests may live in `tests/` while per-app tests live in
  `apps/<app>/tests/`

#### Scenario: A single test can be run in isolation
- **WHEN** a developer runs
  `uv run pytest tests/test_environment.py::test_python_version -q`
- **THEN** only that test executes
- **AND** the command exits with status 0

### Requirement: Repository root is importable under pytest

Test modules SHALL be able to import project packages by their repository-root
path, because the project is not installed as a distribution.

#### Scenario: Import path is configured
- **WHEN** a developer inspects the `pytest` configuration in `pyproject.toml`
- **THEN** `pythonpath` includes `"."`

#### Scenario: Root-relative imports resolve
- **WHEN** a test module imports a package addressed from the repository root
- **AND** `uv run pytest` runs
- **THEN** the import resolves without a `ModuleNotFoundError`
- **AND** no `sys.path` manipulation is present in any test file or `conftest.py`

### Requirement: Environment smoke test

The repository SHALL contain a test that verifies the environment assumptions
this change establishes, and that remains meaningful in later changes rather than
being deleted.

#### Scenario: Interpreter version is asserted
- **WHEN** `uv run pytest tests/test_environment.py` runs
- **THEN** a test asserts the running interpreter is Python 3.13 or newer
- **AND** the test passes

#### Scenario: Repository root resolution is asserted
- **WHEN** `uv run pytest tests/test_environment.py` runs
- **THEN** a test asserts the repository root is present on the import path
- **AND** the test passes

#### Scenario: The smoke test contains no placeholder assertions
- **WHEN** a reviewer reads `tests/test_environment.py`
- **THEN** it contains no `assert True` or equivalent vacuous assertion

### Requirement: Django test integration is deferred

`pytest-django` SHALL be installed but left unconfigured by this change, because
configuring it requires a Django settings module that does not yet exist.

#### Scenario: Test collection succeeds without Django settings
- **WHEN** `uv run pytest` runs and no `DJANGO_SETTINGS_MODULE` is set anywhere
- **THEN** collection completes without error
- **AND** no test fails or errors because Django settings are unconfigured

#### Scenario: The deferral is recorded, not implied
- **WHEN** a developer inspects the `pytest` configuration
- **THEN** `DJANGO_SETTINGS_MODULE` is absent
- **AND** a comment records that it is configured by the change that creates the
  Django project

### Requirement: Line ending normalization

The repository SHALL declare its line ending policy, so that checkouts on
different platforms do not produce spurious whole-file diffs.

#### Scenario: Policy is declared
- **WHEN** a developer inspects `.gitattributes`
- **THEN** it declares a default text handling rule
- **AND** it declares LF as the normalized form for `.py`, `.md`, `.toml`,
  `.yaml` and `.yml` files

#### Scenario: Staging produces no line ending warnings
- **WHEN** `git add -A` runs after the policy is in place and the index has been
  refreshed
- **THEN** no "LF will be replaced by CRLF" warning is emitted
