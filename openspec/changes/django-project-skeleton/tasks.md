## 1. Dependencies

- [x] 1.1 `git mv board/backlog/HS-003-django-skeleton.md board/in-progress/`
- [x] 1.2 `uv add django djangorestframework django-environ "psycopg[binary]"` —
      four runtime dependencies, all named in AGENTS.md §2, landing in
      `[project.dependencies]` and `uv.lock`
- [x] 1.3 Confirm `uv sync` succeeds and `uv run python -c "import django; print(django.__version__)"`
      reports a 5.2.x release

## 2. Project skeleton

- [x] 2.1 Create `manage.py` pointing `DJANGO_SETTINGS_MODULE` at `config.settings`
- [x] 2.2 Create `config/` with `__init__.py`, `settings.py`, `urls.py`,
      `wsgi.py`, `asgi.py` — a single settings module, not a package (design D1)
- [x] 2.3 Create `apps/__init__.py`, and `apps/<papers|ingestion|search>/` each
      containing only `__init__.py` and `apps.py` (design D8) — no `startapp`
      scaffolding, no `tests.py`
- [x] 2.4 Give each app an explicit `AppConfig` with `name = "apps.<app>"` and
      `default_auto_field = "django.db.models.BigAutoField"`, and reference the
      config path in `INSTALLED_APPS`
- [x] 2.5 Add `rest_framework` to `INSTALLED_APPS` with no `REST_FRAMEWORK`
      settings block

## 3. Configuration

- [x] 3.1 Wire `django-environ`: instantiate `Env`, read `.env` from `BASE_DIR`
- [x] 3.2 `SECRET_KEY = env("SECRET_KEY")` with **no** default (design D3)
- [x] 3.3 `DEBUG = env.bool("DEBUG", default=False)` and
      `ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])`
- [x] 3.4 Build `DATABASES["default"]` field by field from `POSTGRES_DB`,
      `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`
      (design D2) — do not call `env.db()`
- [x] 3.5 Keep Django's default `TEMPLATES` (`APP_DIRS=True`) and `STATIC_URL`;
      omit `STATIC_ROOT` (design D9)
- [x] 3.6 Add `SECRET_KEY`, `DEBUG` and `ALLOWED_HOSTS` to `.env.example`, and
      rewrite the "copying is OPTIONAL" paragraph — a `.env` is now required
- [x] 3.7 Replace the HS-003 deferral note at the bottom of `.env.example` with
      the fact it was deferring

## 4. Health endpoint

- [x] 4.1 In `config/health.py`, add `database_ok() -> bool` executing
      `SELECT 1` via a cursor, returning `False` only on
      `django.db.utils.OperationalError` (design D4, D5)
- [x] 4.2 Add a plain `JsonResponse` view returning `200`/`503` from that
      boolean — no DRF wrapper (design D6)
- [x] 4.3 Route it at `/api/health/` in `config/urls.py`

## 5. Test integration

- [x] 5.1 Set `DJANGO_SETTINGS_MODULE = "config.settings"` in
      `[tool.pytest.ini_options]` and delete the deferral comment HS-001 left
- [x] 5.2 Add rootdir `conftest.py` doing `os.environ.setdefault("SECRET_KEY", ...)`
      with an obviously-throwaway value, plus a comment explaining it must run
      before `django.setup()` (design D3)
- [x] 5.3 `tests/test_health.py`: patch `database_ok` to `True` → assert `200`;
      patch to `False` → assert `503`. Neither test carries `django_db`
- [x] 5.4 Same file: one `@pytest.mark.django_db` test asserting `200` against a
      real connection (design D7)

## 6. Verification

- [x] 6.1 `docker compose up -d --wait`, then
      `uv run python manage.py migrate` → succeeds; run it twice, second run is
      a no-op
- [x] 6.2 `uv run python manage.py runserver` starts with no system-check or
      unapplied-migration warning; `curl http://127.0.0.1:8000/api/health/`
      returns `200`
- [x] 6.3 `docker compose stop db`, `curl` the endpoint again → `503`; restart
      the database
- [x] 6.4 `uv run pytest` (all green) and `uv run pytest -m "not django_db"`
      with the database stopped (all green)
- [x] 6.5 `uv run ruff check .` and `uv run ruff format --check .` pass
- [x] 6.6 `uv run python manage.py check --deploy` — record every reported ID and
      its justification for the commit body (design: no `SILENCED_SYSTEM_CHECKS`)
- [x] 6.7 Grep application/configuration files for `DATABASE_URL` — must return
      nothing; historical OpenSpec and archived board documents may retain the
      rejected design term

## 7. Land it

- [x] 7.1 Tick the HS-003 acceptance criteria, adding the `503` branch and the
      `.env.example` correction to the card
- [x] 7.2 `git mv board/in-progress/HS-003-django-skeleton.md board/done/`
- [x] 7.3 Commit as `HS-003: Create the Django project skeleton`, body covering
      why `SECRET_KEY` is required, why the health check uses `SELECT 1`, and the
      `check --deploy` findings
- [ ] 7.4 `openspec archive django-project-skeleton`
