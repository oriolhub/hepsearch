## Context

`apps/papers` is the centre of the dependency graph (`AGENTS.md §3`): it depends on
nothing, and both `apps/ingestion` and `apps/search` depend on it. Whatever shape the
`Paper` model takes is a contract that five later cards must live with, so the field
types were chosen against **measured** INSPIRE data rather than against the card's
prose or `AGENTS.md §4.2`'s summary.

### The spike

Four read-only calls to `https://inspirehep.net/api/literature` (public, no auth,
descriptive `User-Agent`, sleeps between calls), sampling both the `mostcited` and
`mostrecent` slices of `q=higgs boson` (~29,128 hits). Findings:

| Observation | Measured | Consequence |
|---|---|---|
| `earliest_date` is a **partial** date | 144/200 partial: 19 year-only (`"2014"`), 125 year+month (`"2012-07"`), 56 full | **D2** — a `DateField` cannot store this without inventing a day |
| `earliest_date` ≠ publication year | 78/186 records carrying both **disagree on the year** (`1977-11`→1978, `2016-10-25`→2017) | **D3** — the card's name `publication_date` is factually wrong |
| Author list length | max **5,154** (also 2,881) | **D4** — `AGENTS.md §4.2`'s "50+" is an order of magnitude low |
| Abstract length | max **5,333 chars** (~1,300 tokens) | Open question OQ1 — contradicts `AGENTS.md §6` |
| Title length | max **187 chars** | **D6** — any guessed `max_length` is a crash risk |
| Absence (`mostrecent`, preprint-heavy) | `dois` absent 44/50, `publication_info` absent 43/50, `arxiv_eprints` present 44/50, `citation_count` present 50/50 | **D5, D7** |
| Absence (`mostcited`) | no abstract 10/200, no `dois` 13/200, no `publication_info` 14/200 | ~5-10% abstract loss confirms the `AGENTS.md` skip rule |
| Multiple abstracts | 52/200; sources `arXiv`(84) / `Elsevier`(46) / **absent**(40) / `APS`(38) / others | Deferred to HS-005 — a "prefer arXiv" rule fails for the 40 source-less ones |

## Goals / Non-Goals

**Goals:**
- One table that can hold any INSPIRE literature record without crashing or silently
  fabricating data.
- The "every paper has an abstract" invariant enforced by the database.
- Idempotent upsert made possible: a unique natural key HS-006 can target.
- Readable in the Django admin without rendering a 5,154-name author list.

**Non-Goals:**
- Parsing INSPIRE JSON into these fields — that is HS-005, and this app must not know
  INSPIRE's field names (`AGENTS.md §3`). The one sanctioned exception is the INSPIRE
  URL, explicitly required by `AGENTS.md §6`.
- The embedding `VectorField` (HS-009), the full-text `SearchVector` index (HS-007),
  serializers (HS-007), and any query or ranking code.
- Modelling authors, journals, or categories as related tables.

## Decisions

### D1 — Default surrogate primary key; `inspire_id` is a unique, indexed column

`inspire_id` (INSPIRE's `control_number`) is the natural key and is what HS-006 upserts
on, but it stays an ordinary `BigIntegerField(unique=True)` rather than
`primary_key=True`.

*Alternatives considered:* `inspire_id` as the primary key. Rejected because it makes
the PK externally controlled — if INSPIRE ever merges two records or we need a row for
a paper without a `control_number`, the table has no identity to fall back on. It also
makes every future foreign key carry an external number, and Django's admin URLs would
expose it. The cost of the surrogate key is one extra `bigint` column and one index.

*Consequence for HS-007:* the serializer will see both `id` and `inspire_id`. The
INSPIRE link must be built from `inspire_id`; exposing the surrogate `id` invites a
consumer to build the wrong URL. Serving `inspire_url` pre-built (D8) removes the trap.

### D2 — `earliest_date` is a `CharField`, storing INSPIRE's ISO prefix verbatim

`CharField(max_length=10, blank=True, default="")` holding exactly what INSPIRE
returned: `"2014"`, `"2012-07"`, or `"2016-10-25"`. Never padded, never parsed.

*Alternatives considered:*
- `DateField` — would need `"2012-07"` padded to `"2012-07-01"`. That is a fabricated
  day on 72% of rows, and it is unrecoverable: nothing downstream can tell a real
  1st-of-the-month from a padded one. The Higgs discovery paper itself is `"2012-07"`.
- Three integer columns (`year`/`month`/`day`, nullable) — honest and sortable, but
  three columns and three null checks for a field that v1 only ever displays.
- `DateField` + a `date_precision` enum — correct, and what a citation manager would
  do. Rejected as more machinery than any acceptance criterion requires.

The chosen form sorts correctly as a string precisely because ISO prefixes are
lexicographically ordered, which is enough for v1's needs.

`max_length=10` is the exact width of `YYYY-MM-DD`, so it is a genuine bound rather
than a guess — unlike D6's fields.

### D3 — The field is named `earliest_date`, not the card's `publication_date`

The spike showed the two are different facts and disagree on the year 42% of the time.
Naming it `publication_date` would make every downstream consumer — the API, the
results page, a future citation export — state something false.

*Alternatives considered:* keeping `publication_date` for a friendlier domain
vocabulary. Rejected: `AGENTS.md §3` wants `apps/papers` free of INSPIRE vocabulary,
but a mildly INSPIRE-flavoured name that is **true** beats a clean name that is
**false**. This is a deliberate, contained vocabulary leak; it does not import INSPIRE
concepts, only borrows a word.

*Consequence:* HS-007 and HS-014 will surface "earliest date", not "published". The
HS-004 card is amended to match.

### D4 — All authors in an `ArrayField(TextField())`, truncated at display

`ArrayField(models.TextField(), default=list, blank=True)`. Every author is stored;
truncation is a presentation concern, handled by a model method used by the admin and
later by HS-014.

*Alternatives considered:*
- A related `Author` table — the correct relational answer, and wrong here. It buys
  author-level querying that no v1 acceptance criterion asks for, at the price of a
  join on every result page and a de-duplication problem (INSPIRE full names are not
  stable identifiers). `AGENTS.md §2` forbids abstractions no criterion requires.
- Storing only the first N authors — loses data permanently to save display effort.
- A `JSONField` — no advantage over `ArrayField` for a flat list of strings, and worse
  querying.

`default=list` is the callable, never `default=[]`; a mutable default would be shared
across instances and Django's system checks reject it.

### D5 — Absent strings are `""`, never `NULL`

`arxiv_id`, `doi`, `journal` and `earliest_date` use `blank=True, default=""`.

This is not a free choice: ruff rule `DJ001` is enabled in `pyproject.toml` and fails
the build on `null=True` for `CharField`/`TextField`. It also matches Django's own
convention — two representations of "no value" in a text column is a bug factory.
The HS-004 card's "nullable/blankable" wording is amended accordingly.

`citation_count` is the exception: it is an `IntegerField(null=True, blank=True)`,
because `0` is a real, meaningful citation count and must not be confused with
"INSPIRE did not tell us". The spike found `citation_count` present on 50/50 sampled
records, but nullable costs nothing and absence is not guaranteed.

### D6 — `TextField` for `title` and `abstract`; no guessed `max_length`

Observed maxima are 187 and 5,333 characters, but those are sample maxima, not bounds
INSPIRE documents. On PostgreSQL, `varchar(n)` and `text` have identical storage and
performance, so a `max_length` buys nothing except a future `DataError` on ingest.

`categories` uses `ArrayField(CharField(max_length=32))` — arXiv category identifiers
(`hep-ph`, `hep-ex`, `astro-ph.CO`) are a short, controlled vocabulary, so a bound is
safe there.

### D7 — `categories` comes from `arxiv_eprints[0].categories`

Not from `inspire_categories`. arXiv categories are the vocabulary physicists actually
use and recognise, and the spike found `arxiv_eprints` present on 44/50 records.

*Note for HS-005:* this is a **double index into two possibly-absent lists** — exactly
the crash `AGENTS.md §4.2` warns about. `metadata.get("arxiv_eprints", [{}])[0]` is not
safe. HS-005 owns that; this card only fixes the destination.

### D8 — `inspire_url` is a property, `author_summary()` is a method

`inspire_url` returns `f"https://inspirehep.net/literature/{self.inspire_id}"`, as
required by `AGENTS.md §6` and the card. `author_summary()` returns the first three
names plus `et al. (N)` when there are more.

Both live on the model rather than in the admin or a template filter so that the admin
(this card), the serializer (HS-007) and the results page (HS-014) share one
implementation instead of three. Putting `author_summary` on the `ModelAdmin` would
guarantee it is rewritten in HS-014.

### D9 — `django.contrib.postgres` is **not** added to `INSTALLED_APPS`

`ArrayField` is importable from `django.contrib.postgres.fields` without the app being
installed. Verified by reading `django/contrib/postgres/apps.py`: `PostgresConfig.ready()`
only registers the `unaccent`/trigram lookups, the `__search` lookup, and range
serializers — none of which `ArrayField` needs. HS-007's `SearchVector`/`SearchRank`
also work without it.

This keeps HS-004 from touching `config/settings.py` at all, so the change is confined
to one app.

### D10 — The abstract invariant is a `CheckConstraint`, not an ingestion rule

```python
models.CheckConstraint(condition=~models.Q(abstract=""), name="paper_abstract_not_empty")
```

`AGENTS.md §4.2` states ingestion skips abstract-less records. That rule lives in code
that will be rewritten, re-run with different flags, and bypassed by `loaddata`, the
admin, and future backfills. A database constraint cannot be bypassed.

*Alternatives considered:* trusting HS-006, or a `clean()` validator (which `bulk_create`
skips entirely — the exact path HS-006 will use). Rejected.

Note the kwarg is `condition=`, **not** `check=`: `CheckConstraint.check` is deprecated
in Django 5.2 with a `RemovedInDjango60Warning`.

### D11 — No `Meta.ordering`

Tempting, since papers have dates. Rejected: `Meta.ordering` silently appends an
`ORDER BY` to **every** queryset, including HS-007's relevance-ranked queries — where
it would either override the ranking or force Postgres into a needless sort — and
including `.count()`. Ordering is a query-site decision.

`Meta` carries only `constraints` and verbose names. Field order in the model body
follows ruff `DJ012`.

### D12 — `created_at` / `updated_at` timestamps

`auto_now_add` and `auto_now`. Ingestion is re-run constantly during development
(`AGENTS.md §6`); knowing when a row was last refreshed is what makes a partial or
interrupted ingest diagnosable.

*Trap for HS-006:* `auto_now` is applied by `Model.save()`, **not** by `bulk_update()`
or `bulk_create(update_conflicts=...)`. If HS-006 upserts in bulk it must include
`updated_at` in the updated field list explicitly, or the column silently rots.

## Risks / Trade-offs

- **`earliest_date` as text cannot be range-queried by date** → Accepted. Nothing in v1
  filters by date. String prefix comparison covers "papers from 2012" if it is ever
  needed, and a later migration to a `DateField` + precision column is mechanical
  because the raw value was never lossily transformed.
- **`ArrayField` ties the model to PostgreSQL** → Accepted, and already true:
  `AGENTS.md §2` commits to Postgres for `pgvector`. Portability is not a goal.
- **A 5,154-element array on one row** → Postgres TOASTs it transparently; the cost is
  paid only when the column is selected. HS-007 can `.defer("authors")` if the results
  page ever needs to. `author_summary()` reading the full array is a display-time cost
  on ~10 rows per page.
- **The `CheckConstraint` will reject rows that HS-006 might otherwise have written**
  → That is the point, but it means HS-006 must filter abstract-less records *before*
  a bulk insert, since one violating row aborts the whole statement. Recorded here so
  HS-006 is not surprised.
- **`inspire_id` uniqueness raises `IntegrityError` in tests** → Under
  `@pytest.mark.django_db`, an `IntegrityError` breaks the surrounding transaction and
  every later query in that test fails with `TransactionManagementError`. The duplicate
  test must wrap the failing insert in `transaction.atomic()`.
- **Amending the HS-004 card's field names** → The card is the spec a QA engineer reads.
  Leaving `publication_date` in it while the code says `earliest_date` would make the
  card unverifiable. Precedent: HS-002's change amended the HS-003 card the same way.

## Migration Plan

One forward migration, `apps/papers/migrations/0001_initial.py`, generated by
`makemigrations` and committed. The table does not exist yet and there is no data, so
there is no backfill and no data migration. Rollback is `migrate papers zero`.

The migration must be verified against a live Postgres (`docker compose up -d --wait`),
not just generated — the `CheckConstraint` is emitted as DDL and is the part most
likely to fail at the database rather than at `makemigrations` time. Re-running
`migrate` must be a no-op, and `makemigrations --check --dry-run` must report no
pending changes, proving the model and the migration agree.

## Open Questions

- **OQ1 — abstracts may exceed the embedding window.** `AGENTS.md §6` asserts abstracts
  are "~1,200 characters, comfortably inside the model's 512-token window" and uses
  that to rule out chunking. The spike measured 5,333 characters (~1,300 tokens), so
  `all-MiniLM-L6-v2` would silently truncate the tail of the longest abstracts. This
  does not affect HS-004 — a `TextField` stores them either way — and is deliberately
  **not** resolved here. It must be settled in HS-009/HS-010, and `AGENTS.md §6`
  amended at that point.
- **OQ2 — which abstract, when there are several?** 52/200 records carry multiple
  abstracts and 40 abstract entries have no `source` field at all, so a naive "prefer
  arXiv" rule is non-deterministic. Owned by HS-005; the model stores one string
  regardless.
