# HS-003: Create the Django project skeleton

**Status:** backlog
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

- [ ] `manage.py` and a `config/` package (settings, urls, wsgi, asgi) exist
- [ ] `apps/papers`, `apps/ingestion`, `apps/search` exist as installed Django
      apps with explicit `AppConfig` entries
- [ ] `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, and `DATABASE_URL` are read from
      the environment via `django-environ`; no secret has a hardcoded value
- [ ] `.env.example` is updated with every new variable
- [ ] `djangorestframework` is installed and in `INSTALLED_APPS`
- [ ] `uv run python manage.py migrate` succeeds against the Compose database
- [ ] `uv run python manage.py runserver` starts with no warnings
- [ ] `GET /api/health/` returns `200` with a small JSON body reporting that the
      database connection is alive
- [ ] `uv run python manage.py check --deploy` output is reviewed; anything
      deliberately ignored is noted in the commit body
- [ ] A test asserts `/api/health/` returns 200

## Definition of done

- [ ] Acceptance criteria met
- [ ] `uv run pytest` and `uv run ruff check .` pass
- [ ] Committed as `HS-003: Create the Django project skeleton`

## Out of scope

Any domain model (HS-004), any search behaviour (HS-007), templates (HS-008),
authentication (there is none — the API is public and read-only).
