## Why

`apps/papers` is an empty app. Nothing can be ingested, embedded, or searched until
the corpus has a shape to be stored in. Board card **HS-004 — Model the Paper domain
entity** is the first card that produces domain code, and every card after it
(HS-005 normalization, HS-006 ingestion, HS-007 full-text search, HS-009/HS-010
embeddings, HS-014 the results page) reads or writes this one table.

Getting the field types wrong here is expensive: a wrong `max_length` is a crash in
production ingestion, and a wrong date type silently fabricates data. A live spike
against the INSPIRE API (documented in `design.md`) measured the real shape of the
data and invalidated several assumptions written on the card and in `AGENTS.md §4.2`.

## What Changes

- Add the `Paper` model to `apps/papers/models.py`, with `inspire_id`
  (INSPIRE's `control_number`) as the unique natural key alongside Django's default
  surrogate primary key.
- Store dates **as INSPIRE returns them** — a `CharField` holding an ISO prefix
  (`"2014"`, `"2012-07"`, `"2016-10-25"`) rather than a `DateField`. 72% of measured
  records carry a partial date; a `DateField` would have to invent a day.
- **BREAKING (card amendment):** the field the card calls `publication_date` is named
  **`earliest_date`**. It is not the publication date — the two disagree on the year
  for 42% of records that carry both.
- **BREAKING (card amendment):** the card's "nullable/blankable" strings become
  `blank=True, default=""`, not `null=True`. Ruff rule `DJ001` is enabled in this
  repository and rejects `null=True` on `CharField`/`TextField`. An absent DOI is
  `""`, never `NULL`.
- Enforce the "every paper has an abstract" invariant with a database
  `CheckConstraint`, rather than trusting ingestion to uphold it. A paper with no
  abstract cannot be embedded and pollutes search results (`AGENTS.md §4.2`).
- Store all authors in an `ArrayField` (5,154 observed on one record) and truncate at
  display time via a method on the model, reused by the admin and later by HS-014.
- Register `Paper` in the Django admin with a searchable, readable list view.
- Ship the initial migration and the tests that cover the constraints.

Deliberately **not** in scope: any INSPIRE JSON parsing (HS-005), any embedding or
`VectorField` (HS-009), any search index (HS-007), any API serializer (HS-007).

## Capabilities

### New Capabilities
- `paper-model`: the persistent shape of a HEP paper in this system — its fields and
  their types, the natural key and its uniqueness, the abstract invariant, the INSPIRE
  link derivation, the author-truncation rule, and its presence in the admin.

### Modified Capabilities
<!-- None. `django-application` (HS-003) is untouched: no settings, URL, or
     INSTALLED_APPS change is required. `django.contrib.postgres` is NOT needed for
     `ArrayField` — see design.md D9. -->

## Impact

- **New code:** `apps/papers/models.py`, `apps/papers/admin.py`,
  `apps/papers/migrations/0001_initial.py`, `apps/papers/tests/test_models.py`.
- **Board:** `board/backlog/HS-004-paper-model.md` moves to `board/done/`, with its
  `publication_date` and "nullable" wording corrected and a criterion added for the
  abstract constraint.
- **Dependencies:** none added. `psycopg` and `django` are already present; `pgvector`
  is deferred to HS-009.
- **Database:** one new table, `papers_paper`, with a unique index on `inspire_id` and
  one check constraint. Requires a running Postgres (`docker compose up -d --wait`).
- **Downstream contract:** HS-005 must emit `earliest_date` verbatim without padding;
  HS-006 must upsert on `inspire_id`; HS-007's serializer must not confuse the
  surrogate `id` with `inspire_id` when building INSPIRE links.
- **Open question raised, not resolved:** `AGENTS.md §6` claims abstracts sit
  "comfortably inside the model's 512-token window". The spike measured a 5,333-character
  abstract (~1,300 tokens). This is flagged against HS-009/HS-010, not fixed here.
