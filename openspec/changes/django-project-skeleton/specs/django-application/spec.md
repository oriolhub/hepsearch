## ADDED Requirements

### Requirement: Django project boots from the repository root

The repository SHALL contain a Django project that can be administered from the
repository root without the project being installed as a distribution.

#### Scenario: Management commands are reachable
- **WHEN** a developer runs `uv run python manage.py check`
- **THEN** the command completes and exits with status 0
- **AND** no `ModuleNotFoundError` is raised for `config` or `apps`

#### Scenario: The project package is complete
- **WHEN** a developer inspects the repository root
- **THEN** `manage.py` exists
- **AND** a `config/` package exists containing `settings.py`, `urls.py`,
  `wsgi.py` and `asgi.py`

#### Scenario: Settings are a single module
- **WHEN** a developer inspects `config/`
- **THEN** `settings.py` is a single module, not a `settings/` package
- **AND** `DJANGO_SETTINGS_MODULE` resolves to `config.settings`

#### Scenario: The development server starts cleanly
- **WHEN** migrations have been applied and `uv run python manage.py runserver`
  is started
- **THEN** the server reports it is running
- **AND** no system check warning and no unapplied-migration warning is printed

### Requirement: Application boundaries exist before any code does

The project SHALL install three app packages — `apps.papers`, `apps.ingestion`
and `apps.search` — each declaring an explicit `AppConfig`, so that the
dependency rule in AGENTS.md §3 is expressible from the first commit.

#### Scenario: All three apps are installed
- **WHEN** a developer inspects `INSTALLED_APPS` in `config/settings.py`
- **THEN** it contains `apps.papers`, `apps.ingestion` and `apps.search`
- **AND** each entry resolves to an explicit `AppConfig` subclass rather than to
  a bare module path with an implicit default config

#### Scenario: App configs name their dotted path
- **WHEN** a developer reads any `apps/<app>/apps.py`
- **THEN** the `AppConfig` sets `name` to the dotted `apps.<app>` path
- **AND** it sets `default_auto_field`, so Django emits no `models.W042` warning

#### Scenario: Apps carry no scaffolding
- **WHEN** a developer lists the contents of `apps/papers`, `apps/ingestion` and
  `apps/search`
- **THEN** each contains only `__init__.py` and `apps.py`
- **AND** no `tests.py` module exists in any of them, because per-app tests live
  in an `apps/<app>/tests/` package

#### Scenario: No app imports a sibling app
- **WHEN** a developer greps the `apps/` tree for imports
- **THEN** no module under `apps/search` imports from `apps.ingestion`
- **AND** no module under `apps/ingestion` imports from `apps.search`
- **AND** no module under `apps/papers` imports from either sibling

### Requirement: Configuration is read from the environment

Settings that vary between machines or that are secret SHALL be read from the
environment through `django-environ`, and no secret SHALL have a literal value in
source.

#### Scenario: The secret key has no fallback
- **WHEN** a developer reads `config/settings.py`
- **THEN** `SECRET_KEY` is read from the environment with no default value
- **AND** no string literal resembling a key appears in the module

#### Scenario: A missing secret key fails loudly
- **WHEN** `manage.py` is run in an environment where `SECRET_KEY` is unset and
  no `.env` file supplies it
- **THEN** Django raises `ImproperlyConfigured`
- **AND** the message names the missing variable

#### Scenario: Debug fails safe
- **WHEN** `DEBUG` is absent from the environment
- **THEN** `settings.DEBUG` is `False`
- **AND** the value is parsed as a boolean, not left as the string `"False"`

#### Scenario: Allowed hosts is a list
- **WHEN** `ALLOWED_HOSTS` is read from the environment
- **THEN** it is parsed as a comma-separated list
- **AND** it defaults to `localhost` and `127.0.0.1` when unset

#### Scenario: Every new variable is documented
- **WHEN** a developer compares `config/settings.py` with `.env.example`
- **THEN** every environment variable the settings module reads appears in
  `.env.example`

#### Scenario: The environment contract is honest about being required
- **WHEN** a developer reads `.env.example`
- **THEN** it states that a `.env` file is now required, because `SECRET_KEY` has
  no default
- **AND** it no longer claims that copying the file is optional

### Requirement: Database connection is assembled from the POSTGRES_* contract

The `DATABASES` setting SHALL be built from the five `POSTGRES_*` variables
established by the database-infrastructure capability, and no second spelling of
those credentials SHALL be introduced.

#### Scenario: All five variables are consumed
- **WHEN** a developer reads the `DATABASES` definition in `config/settings.py`
- **THEN** the name, user, password, host and port are each populated from the
  corresponding `POSTGRES_*` variable
- **AND** the engine is `django.db.backends.postgresql`

#### Scenario: No DATABASE_URL exists
- **WHEN** a developer greps the repository for `DATABASE_URL`
- **THEN** it appears in no settings module, no `.env.example` entry and no
  Compose file
- **AND** `env.db()` is not called

#### Scenario: Migrations apply against the Compose database
- **WHEN** the Compose database is running and `uv run python manage.py migrate`
  is executed
- **THEN** Django's built-in migrations apply successfully
- **AND** the command exits with status 0

#### Scenario: Re-running migrate is a no-op
- **WHEN** `uv run python manage.py migrate` is run a second time
- **THEN** it reports no migrations to apply
- **AND** exits with status 0

### Requirement: The service reports database readiness over HTTP

The application SHALL expose `GET /api/health/` reporting whether it can reach
its database, with a status code usable directly by a readiness probe.

#### Scenario: Healthy service returns 200
- **WHEN** the database is reachable and a client issues `GET /api/health/`
- **THEN** the response status is `200`
- **AND** the body is JSON reporting that the database connection is alive

#### Scenario: Unreachable database returns 503
- **WHEN** the database cannot be reached and a client issues `GET /api/health/`
- **THEN** the response status is `503`
- **AND** the body is JSON reporting the database as unavailable

#### Scenario: Liveness is proven by a round trip
- **WHEN** a developer reads the health check implementation
- **THEN** it executes a query against the database
- **AND** it does not rely on `connection.ensure_connection()`, which is a no-op
  on an already-open connection

#### Scenario: Only database failure is treated as unhealthy
- **WHEN** the health check's database call raises
  `django.db.utils.OperationalError`
- **THEN** the endpoint responds `503`
- **AND** exceptions that are not database connection errors are not caught and
  reported as an outage

#### Scenario: The endpoint belongs to no domain app
- **WHEN** a developer locates the health view
- **THEN** it lives in the `config/` package
- **AND** it is not defined inside `apps/papers`, `apps/ingestion` or
  `apps/search`

### Requirement: REST framework is installed ahead of its first use

`djangorestframework` SHALL be a declared runtime dependency and an installed
app, so that the change that adds the first API endpoint adds behaviour only.

#### Scenario: The dependency is declared and locked
- **WHEN** a developer inspects `pyproject.toml`
- **THEN** `djangorestframework` appears under `[project.dependencies]`
- **AND** it is pinned in `uv.lock`

#### Scenario: The app is installed
- **WHEN** a developer inspects `INSTALLED_APPS`
- **THEN** it contains `rest_framework`

#### Scenario: No REST framework configuration is invented
- **WHEN** a developer reads `config/settings.py`
- **THEN** no throttling, pagination or renderer settings are configured, because
  no endpoint requires them yet

### Requirement: The test suite runs without a .env file

`uv run pytest` SHALL succeed on a freshly cloned repository that has no `.env`
file, and SHALL offer a selection that requires no running database.

#### Scenario: Django settings are wired into pytest
- **WHEN** a developer inspects `[tool.pytest.ini_options]` in `pyproject.toml`
- **THEN** `DJANGO_SETTINGS_MODULE` is set to `config.settings`
- **AND** the comment deferring this configuration to a later change is gone

#### Scenario: A missing secret key does not break collection
- **WHEN** `uv run pytest` runs with no `.env` file present and `SECRET_KEY`
  unset in the environment
- **THEN** a rootdir `conftest.py` supplies a throwaway value before Django is
  configured
- **AND** collection completes and the pre-existing environment tests still pass

#### Scenario: A real environment value is never overridden
- **WHEN** `SECRET_KEY` is already set in the environment and `pytest` runs
- **THEN** the `conftest.py` fallback does not replace it

#### Scenario: The infra-free selection passes with no database
- **WHEN** the Compose database is stopped and
  `uv run pytest -m "not django_db"` is run
- **THEN** every selected test passes
- **AND** no test attempts a database connection

### Requirement: The health endpoint is tested on both branches

Both outcomes of the health check SHALL be covered by tests, and the real
database path SHALL be covered separately from the status-mapping logic.

#### Scenario: The healthy branch is asserted without a database
- **WHEN** the liveness check is patched to report success and the test client
  issues `GET /api/health/`
- **THEN** the response status is `200`
- **AND** the test carries no `django_db` marker

#### Scenario: The unhealthy branch is asserted without a database
- **WHEN** the liveness check is patched to report failure and the test client
  issues `GET /api/health/`
- **THEN** the response status is `503`
- **AND** the test carries no `django_db` marker

#### Scenario: The real connection is asserted once
- **WHEN** a test marked `@pytest.mark.django_db` issues `GET /api/health/`
- **THEN** the response status is `200`
- **AND** the check has executed a real query against the test database

### Requirement: Deployment check findings are recorded, not silenced

The output of Django's deployment check SHALL be reviewed, and any finding left
unaddressed SHALL be recorded in writing rather than suppressed in configuration.

#### Scenario: The check is run and its findings recorded
- **WHEN** `uv run python manage.py check --deploy` is run
- **THEN** each reported check identifier is listed in the commit body with the
  reason it is acceptable for a development skeleton

#### Scenario: Nothing is silenced in settings
- **WHEN** a developer reads `config/settings.py`
- **THEN** `SILENCED_SYSTEM_CHECKS` is absent
- **AND** no deployment warning is hidden from the change that eventually
  deploys the application
