# HS-003: Create the Django project skeleton

**Status:** done
**Depends on:** HS-002

## Story

As a developer, I want a Django project that boots against the Dockerised
PostgreSQL and answers a health check, so that there is a running application to
add features to.

## Context

Layout and the dependency rule are defined in AGENTS.md §3: a `config/` settings
package plus `apps/papers`, `apps/ingestion`, `apps/search`. Settings read from
`.env` via `django-environ`.

The three apps are created empty here so the boundaries exist from the first
commit and nobody is tempted to put ingestion code in the search app "for now".

## Acceptance criteria

- [x] `manage.py` and a `config/` package (settings, urls, wsgi, asgi) exist
- [x] `apps/papers`, `apps/ingestion`, `apps/search` exist as installed Django
      apps with explicit `AppConfig` entries
- [x] `SECRET_KEY`, `DEBUG` and `ALLOWED_HOSTS` are read from the environment
      via `django-environ`; no secret has a hardcoded value
- [x] The database connection is assembled from the five `POSTGRES_*` variables
      that HS-002 established. There is **no** `DATABASE_URL`: adding one would
      restate credentials Compose already owns in a second spelling, and neither
      spelling can be derived from the other. Populate `DATABASES` field by field,
      or build the DSN in settings from those five variables
- [x] `.env.example` is updated with every new variable
- [x] A copied `.env` is required for Django because `SECRET_KEY` has no default
- [x] `djangorestframework` is installed and in `INSTALLED_APPS`
- [x] `uv run python manage.py migrate` succeeds against the Compose database
- [x] `uv run python manage.py runserver` starts with no warnings
- [x] `GET /api/health/` returns `200` with a small JSON body reporting that the
      database connection is alive
- [x] `GET /api/health/` returns `503` with a small JSON body when the database
      is unavailable
- [x] `uv run python manage.py check --deploy` output is reviewed; anything
      deliberately ignored is noted in the commit body
- [x] A test asserts `/api/health/` returns 200

## Definition of done

- [x] Acceptance criteria met
- [x] `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` pass
- [ ] Committed as `HS-003: Create the Django project skeleton`

## Out of scope

Any domain model (HS-004), any search behaviour (HS-007), templates (HS-008),
authentication (there is none — the API is public and read-only).
