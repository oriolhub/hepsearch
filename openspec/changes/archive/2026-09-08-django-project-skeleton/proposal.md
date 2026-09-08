## Why

There is a toolchain (HS-001) and a database (HS-002), but no application: nothing
imports Django, nothing reads `.env`, and there is no place to put a model, a
view or a URL. Every card from HS-004 onward is blocked on the same missing
skeleton.

Creating the three apps *empty and up front* is the point of the card, not
ceremony. The dependency rule in AGENTS.md §3 (`search` and `ingestion` must
never import each other) is cheap to honour when both packages start empty and
expensive to retrofit once code has already landed in the wrong one.

Exploration also surfaced two things the card does not say, both of which change
the shape of the work:

1. **`SECRET_KEY` with no default breaks `pytest`, not just `runserver`.**
   `.env` is git-ignored, so a fresh clone has none, and `pytest-django` imports
   the settings module at startup — the entire suite would error, including the
   two environment tests that pass today.
2. **A health check that touches the database drags Docker into `uv run pytest`.**
   `pytest-django` blocks database access in any test without the `django_db`
   marker, so a naive test of the endpoint returns 503 and fails the very
   criterion it exists to prove.

## What Changes

- Add `manage.py` and a `config/` package (`settings.py`, `urls.py`, `wsgi.py`,
  `asgi.py`) — a **single settings module**, not a `settings/` package: there is
  one environment and `.env` already varies it.
- Add `apps/papers`, `apps/ingestion`, `apps/search` as installed apps with
  explicit `AppConfig` classes and dotted `apps.<name>` labels. Each contains
  only `__init__.py` and `apps.py`; no `startapp` boilerplate is kept.
- Add `django` and `djangorestframework` as the first runtime dependencies.
  `rest_framework` goes in `INSTALLED_APPS`; nothing uses it yet, and that is
  fine — HS-007 does.
- Read `SECRET_KEY`, `DEBUG` and `ALLOWED_HOSTS` from the environment via
  `django-environ`. No secret has a literal value in `settings.py`. `DEBUG`
  defaults to `False`, so a missing variable fails safe.
- Assemble `DATABASES` field by field from the five `POSTGRES_*` variables that
  HS-002 established. There is deliberately **no** `DATABASE_URL` — see the
  archived `dockerized-postgres-pgvector` proposal for why.
- Add `GET /api/health/`: `200` when the database answers, **`503` when it does
  not**, so the endpoint is usable as a readiness probe rather than a liveness
  theatre. Liveness is proven by `SELECT 1`, not by `connection.ensure_connection()`,
  which is a no-op on an already-open connection and would report healthy against
  a dead server.
- Add a rootdir `conftest.py` that sets a throwaway `SECRET_KEY` via
  `os.environ.setdefault` before `pytest-django` calls `django.setup()`, keeping
  the suite runnable on a fresh clone without weakening the settings module.
- Set `DJANGO_SETTINGS_MODULE` in `[tool.pytest.ini_options]`, replacing the
  deferral comment HS-001 left there.
- Test the endpoint at three points: the `200` branch and the `503` branch with
  the liveness check patched (no database), plus one `@pytest.mark.django_db`
  test that proves a real connection.
- **BREAKING (documentation only):** `.env.example` currently promises that
  copying it is optional. Once `SECRET_KEY` is required that is false, and the
  file must say so.

## Capabilities

### New Capabilities

- `django-application`: how the Django project is laid out, how it reads its
  configuration from the environment, how the app boundaries of AGENTS.md §3 are
  expressed and enforced, how the service reports its readiness over HTTP, and
  how the test suite runs without a `.env` file.

### Modified Capabilities

<!-- None. `database-infrastructure` keeps every requirement it has; this change
     consumes the POSTGRES_* contract it defined rather than altering it, and
     `python-tooling` explicitly deferred DJANGO_SETTINGS_MODULE to this change,
     so filling it in satisfies that requirement instead of changing it. -->

## Impact

**New files:** `manage.py`, `config/{__init__,settings,urls,wsgi,asgi}.py`,
`apps/__init__.py`, `apps/<papers|ingestion|search>/{__init__,apps}.py`,
`conftest.py`, `tests/test_health.py`.

**Modified files:** `pyproject.toml` (runtime dependencies,
`DJANGO_SETTINGS_MODULE`), `uv.lock`, `.env.example` (new variables; the
"copying is optional" claim corrected).

**Dependencies added:** `django`, `djangorestframework`, `django-environ`,
`psycopg[binary]`. All four are named in AGENTS.md §2, so none needs a fresh
argument.

**Board card:** `HS-003` acceptance criteria gain the `503` branch and the
`.env.example` correction; the card moves `backlog → done` in the commit.

**Test suite:** gains a database-backed test. `uv run pytest` now expects
`docker compose up -d`; `uv run pytest -m "not django_db"` remains fully
infra-free.

**Deferred:** DRF throttling and error handling (HS-013), templates and static
files beyond Django's defaults (HS-008), any model (HS-004), any custom user
model (never — AGENTS.md §1 rules out accounts).
