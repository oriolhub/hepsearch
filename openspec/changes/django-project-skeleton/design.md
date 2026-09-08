## Context

HS-001 produced a toolchain and HS-002 a containerised PostgreSQL with pgvector.
Neither installed Django. The repository has no `manage.py`, no settings module,
and `pyproject.toml` carries an explicit note that `DJANGO_SETTINGS_MODULE` is
deferred to this change.

Constraints inherited, not chosen here:

- **AGENTS.md §3** fixes the layout: `config/` plus `apps/{papers,ingestion,search}`,
  with `search` and `ingestion` forbidden from importing each other and `papers`
  importing nothing.
- **HS-002** owns the credential contract: five `POSTGRES_*` variables, three of
  which Compose passes into the container, two of which are host-side facts.
  `DATABASE_URL` was rejected on the grounds that the two spellings cannot be
  derived from one another and would drift.
- **HS-001** established that nothing is installed as a distribution
  (`[tool.uv] package = false`), so `apps.*` resolves only via `pythonpath = ["."]`.
- The application is public and read-only. There are no accounts, ever.

## Goals / Non-Goals

**Goals:**

- A Django project that boots against the Compose database and answers a
  readiness probe.
- Three empty app packages whose boundaries exist before any code can violate
  them.
- Configuration read from the environment with no secret literal in source.
- A test suite that still runs on a fresh clone with no `.env` file.

**Non-Goals:**

- Any model, any search behaviour, any template beyond Django's defaults.
- Split settings modules, a service layer, a custom user model, DRF throttling,
  logging configuration, or CI. Each arrives when a criterion fails without it.
- A production-clean `manage.py check --deploy`. This is a development skeleton;
  the deploy warnings are reviewed and recorded, not silenced.

## Decisions

### D1: One `config/settings.py`, not a `settings/` package

A `settings/base.py` + `development.py` + `production.py` split is the standard
Django recommendation and it is wrong here. It exists to vary configuration per
environment; this project has exactly one environment, and `.env` already varies
it. Three modules and an import chain would encode a distinction that does not
exist, and the first person to add a setting would have to guess which file.

*Alternative considered:* the split package. Revisit if and when a second
deployment target appears — that is a mechanical refactor, not a rewrite.

### D2: `DATABASES` assembled field by field from `POSTGRES_*`

`django-environ` is used for its typed `env.str`/`env.bool`/`env.list` parsing,
**not** for `env.db()`, which expects a `DATABASE_URL`. The five variables are
read individually and placed into the `DATABASES["default"]` dict.

*Alternative considered:* building a DSN string in settings and passing it
through `env.db_url_config()`. Same result, one more layer of string formatting
to get wrong, and it silently URL-encodes (or fails to encode) a password
containing `@` or `/`.

### D3: `SECRET_KEY` is required; `pytest` supplies its own

`env("SECRET_KEY")` with no default means a missing variable is a loud
`ImproperlyConfigured` at startup rather than a quiet fallback that could reach a
real deployment. The cost is that `.env` becomes mandatory — including for
`pytest`, which imports the settings module before collecting anything.

A rootdir `conftest.py` sets a throwaway value via `os.environ.setdefault`. It
runs before `pytest-django` calls `django.setup()`, and `setdefault` means a real
`.env`-derived value already in the environment always wins.

*Alternatives considered:* a `django-insecure-` fallback in settings (the exact
pattern that lets an unset key reach production); a committed `.env.test` (a
second file restating the same variables, which is the duplication HS-002
rejected in another costume).

*Consequence, deliberately accepted:* `.env.example` can no longer claim that
copying is optional, and this change corrects that sentence.

### D4: Health check uses `SELECT 1`, not `connection.ensure_connection()`

`ensure_connection()` returns immediately when `connection.connection` is already
set — it establishes a connection, it does not test one. Under Django's default
`CONN_MAX_AGE = 0` connections close per request so the two behave identically
today, but the day anyone sets `CONN_MAX_AGE` the check silently starts reporting
healthy against a dead server. `SELECT 1` is the same number of lines and
round-trips to the server by construction.

### D5: The endpoint returns 503 when the database is unreachable

A readiness probe that always returns 200 and hides the truth in a JSON body is
useless to every tool that consumes one. `200` means ready; `503` means not.
`django.db.utils.OperationalError` is caught specifically — a bare `except` would
swallow programming errors and report them as a database outage.

### D6: The health view lives in `config/`, not in an app

It belongs to no domain. `apps/search` is the tempting host and would be the
first crack in the §3 dependency rule — a health endpoint importing nothing
domain-specific has no business inside the search app. It is a plain
`JsonResponse` view: DRF must be *installed* by the acceptance criteria, not
*used*, and a `@api_view` wrapper here would buy content negotiation nobody asked
for.

### D7: A one-function seam so the endpoint is testable without Docker

The view calls `database_ok() -> bool`. That indirection exists for exactly one
reason: `pytest-django` blocks database access in unmarked tests, so without a
patchable seam the `200` case cannot be asserted without a running container, and
the `503` case cannot be asserted at all — nobody is going to stop Postgres
mid-suite.

Three tests result: `200` and `503` with the seam patched (no database), and one
`@pytest.mark.django_db` test that exercises the real connection. The first two
prove routing and status mapping; the third proves the query.

*Alternative considered:* dropping the seam and marking every health test
`django_db`. Honest, but it makes a running container a precondition for the
entire suite forever.

### D8: Apps are hand-written, not `startapp` scaffolded

`django-admin startapp` emits `views.py`, `models.py`, `tests.py`, `admin.py` and
a `migrations/` package. All five are empty and three are actively wrong here —
`tests.py` conflicts with the `apps/<app>/tests/` package convention AGENTS.md
§6 mandates. Each app gets `__init__.py` and `apps.py` with an explicit
`AppConfig` whose `name` is the dotted `apps.<app>` path. `default_auto_field` is
set on each config to avoid Django's `W042` warning.

### D9: Django's default `TEMPLATES` and `STATIC_URL` are kept

`APP_DIRS = True` costs nothing now and is what HS-008 will need. `STATIC_ROOT`
is omitted: nothing collects static files, and adding it now would be
configuration for a command no one runs.

## Risks / Trade-offs

- **`uv run pytest` now needs a running container for one test.** → The `django_db`
  marker makes it selectable: `uv run pytest -m "not django_db"` stays infra-free,
  and this is documented rather than discovered.
- **A required `SECRET_KEY` makes the first-run experience worse.** → `.env.example`
  is corrected in the same change, and the failure is a named
  `ImproperlyConfigured` telling the developer exactly which variable is missing.
- **The `database_ok()` seam is an abstraction with one caller.** → Accepted
  knowingly; its justification is testability, and it is one function in the same
  module as its only caller, not an interface in a separate package.
- **`check --deploy` will report `DEBUG`, SSL, HSTS and cookie warnings.** → They
  are inherent to a development skeleton with no deployment story. The specific
  IDs are recorded in the commit body rather than silenced with
  `SILENCED_SYSTEM_CHECKS`, which would hide them from the card that eventually
  deploys.
- **`rest_framework` is installed but unused.** → An acceptance criterion, and it
  keeps HS-007 from bundling a dependency addition into a feature commit.
