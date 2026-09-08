## 1. Start the card

- [x] 1.1 `git mv board/backlog/HS-004-paper-model.md board/in-progress/` and set its
      status line to `in-progress`
- [x] 1.2 Confirm Postgres is up: `docker compose up -d --wait`
- [x] 1.3 Confirm a clean baseline before touching anything: `uv run pytest`,
      `uv run ruff check .`, `uv run ruff format --check .`

## 2. The model

- [x] 2.1 Write `apps/papers/models.py` with the `Paper` model: `inspire_id`
      (`BigIntegerField(unique=True)`), `title` and `abstract` (`TextField`),
      `authors` and `categories` (`ArrayField`, `default=list`, `blank=True`),
      `arxiv_id` / `doi` / `journal` / `earliest_date` (`blank=True, default=""`),
      `citation_count` (`IntegerField(null=True, blank=True)`), `created_at`
      (`auto_now_add`) and `updated_at` (`auto_now`) — per design D1–D7 and D12
- [x] 2.2 Add `Meta` with the abstract `CheckConstraint`, using `condition=` not the
      Django-5.2-deprecated `check=` (design D10), plus `verbose_name` /
      `verbose_name_plural`, and deliberately **no** `ordering` (design D11)
- [x] 2.3 Add `__str__`, the `inspire_url` property and the `author_summary()` method
      on the model, not on the admin (design D8)
- [x] 2.4 Confirm no `INSTALLED_APPS` or settings change is needed —
      `django.contrib.postgres` is not required for `ArrayField` (design D9)

## 3. Migration

- [x] 3.1 `uv run python manage.py makemigrations papers` and read the generated file:
      it must contain the unique constraint on `inspire_id` and the check constraint
- [x] 3.2 `uv run python manage.py migrate` against the live container, then run it a
      second time and confirm it is a no-op
- [x] 3.3 `uv run python manage.py makemigrations --check --dry-run` reports nothing
      pending
- [x] 3.4 Verify rollback works: `migrate papers zero`, then `migrate` forward again

## 4. Admin

- [x] 4.1 Write `apps/papers/admin.py`: register `Paper` with `list_display` covering
      inspire id, title, the truncated author summary, `earliest_date` and
      `citation_count`; `search_fields` on title, abstract and `inspire_id`;
      `readonly_fields` on the timestamps
- [x] 4.2 Manually confirm the changelist renders with a paper carrying thousands of
      authors, via `runserver` and a superuser

## 5. Tests

- [x] 5.1 Create `apps/papers/tests/__init__.py` and `apps/papers/tests/test_models.py`
- [x] 5.2 Test that a minimal paper (id, title, abstract only) saves, and that its
      optional strings are `""`, `citation_count` is `None`, and its list fields are
      empty
- [x] 5.3 Test that a duplicate `inspire_id` raises `IntegrityError`, wrapping the
      failing insert in `transaction.atomic()` so the test transaction survives
      (design Risks)
- [x] 5.4 Test that an empty abstract raises `IntegrityError`, likewise wrapped, and
      that the constraint also fires via a path that skips `full_clean()`
- [x] 5.5 Test that `earliest_date` round-trips `"2014"`, `"2012-07"` and
      `"2016-10-25"` unmodified
- [x] 5.6 Test that a paper with several thousand authors stores and reads back every
      name in order
- [x] 5.7 Test `inspire_url` returns `https://inspirehep.net/literature/<inspire_id>`,
      built from `inspire_id` and not the surrogate pk — no database needed
- [x] 5.8 Test `author_summary()` for the short, long and empty cases — no database
      needed
- [x] 5.9 Confirm `apps/papers` imports nothing from `apps.ingestion` or `apps.search`

## 6. Verify

- [x] 6.1 `uv run pytest` — whole suite green, including HS-003's health tests
- [x] 6.2 `uv run pytest -m "not django_db"` still passes without a database, proving
      the pure tests stayed pure
- [x] 6.3 `uv run ruff check .` and `uv run ruff format --check .` both clean —
      in particular DJ001 and DJ012 must not fire
- [x] 6.4 `uv run python manage.py check` clean

## 7. Land it

- [x] 7.1 Amend the HS-004 card: rename `publication_date` to `earliest_date` with the
      measured rationale, correct "nullable" to `blank=True, default=""` for strings,
      and add an acceptance criterion for the abstract check constraint
- [x] 7.2 Tick every acceptance criterion on the card, set status to `done`, and
      `git mv board/in-progress/HS-004-paper-model.md board/done/`
- [x] 7.3 Commit everything as `HS-004: Model the Paper domain entity`, with a body
      explaining why the date is a string and why the abstract invariant is a database
      constraint, and the `Co-authored-by: Copilot` trailer
- [x] 7.4 Record open question OQ1 (abstracts exceed the 512-token window assumed by
      `AGENTS.md §6`) against HS-009/HS-010 rather than amending `AGENTS.md` here
- [x] 7.5 `openspec archive paper-domain-model` and commit the archive separately
