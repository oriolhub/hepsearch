## Context

`apps/search` is an empty shell. The corpus is real: 5,000 papers, ~1,100-character
abstracts, and `django.contrib.postgres` plus `rest_framework` are already installed.

Three properties of the live database drove this design, and each was verified
against it rather than assumed:

| Checked | Result | Consequence |
|---|---|---|
| `to_tsvector` volatility | one-arg form is **STABLE**, two-arg is IMMUTABLE | the text search config must be passed explicitly or PostgreSQL refuses to index the expression at all |
| `array_to_string` volatility | **STABLE** | `authors` (a `text[]`) cannot go into a generated column or expression index without an immutable wrapper |
| `length(earliest_date)` | 4,303 full dates, 109 year-month, 588 year-only | 14% of the corpus cannot become a real date without inventing digits |

A weighted `tsvector` generated column plus a GIN index was built end to end against
the running database before being written up here, so the central mechanism is known
to work rather than hoped to.

## Goals / Non-Goals

**Goals:**

- Ranked keyword retrieval that a physicist would call sensible, over the real corpus
- Title matches outrank abstract-only matches, by a fixed and stated ratio
- The ranking is a plain function over a queryset — no HTTP, no DRF, no request object
  needed to test it or to reuse it from the hybrid ranker in HS-012
- A malformed, punctuation-heavy or hostile `q` cannot produce a 500
- The index is a real, committed migration, not an afterthought

**Non-Goals:**

- Embeddings and semantic ranking (HS-009 to HS-011)
- The HTML page (HS-008)
- Pagination, throttling and API hardening (HS-013) — but the response shape must not
  have to change when they arrive
- Searching author names (see Decision 7)
- Beating the corpus's own vocabulary: this is a keyword baseline, and it is meant to
  be beaten later

## Decisions

### 1. A stored generated column, not an expression index

`Paper.search_vector` is a `GeneratedField` with `db_persist=True`, computed by
PostgreSQL as:

```
setweight(to_tsvector('english', coalesce(title,    '')), 'A') ||
setweight(to_tsvector('english', coalesce(abstract, '')), 'B')
```

with a plain `GinIndex` on the resulting column.

*Why over an expression index:* an expression index is only used when the query
repeats the indexed expression character for character. That coupling is invisible,
easy to break, and would have to be re-established in HS-012 when the hybrid ranker
rewrites the query. A stored column reduces the query to an ordinary filter on an
ordinary indexed column, which the planner cannot fail to match.

*Cost accepted:* one extra `tsvector` column and a table rewrite on migration. At
5,000 rows the rewrite takes seconds.

*Why ingestion does not change:* the column is `GENERATED ALWAYS`, so PostgreSQL
maintains it on every insert and update. `apps/ingestion` writes `title` and
`abstract` exactly as it does today, and HS-006's finished work stays closed. It must
**not** be added to the ingestion writer's compare-fields, because it is not a field
ingestion supplies.

### 2. `config='english'` is mandatory, not stylistic

`to_tsvector(text)` without a config resolves the config at run time, making it
STABLE — PostgreSQL will reject it in a generated column outright. The config is
therefore pinned to `'english'` and named as a constant, because the same value must
be used by the query side and by HS-012. English stemming behaves well on the corpus:
`self-coupling` indexes as `self-coupl`, `self` and `coupl`, so hyphenated physics
terms stay reachable.

### 3. Weighting lives in the column; ranking uses `SearchRank`'s defaults

Weights `A` (title) and `B` (abstract) are baked into the generated column, so the
title-over-abstract contract is enforced by the schema and cannot drift with a query
rewrite. `SearchRank`'s default weight array — `D=0.1, C=0.2, B=0.4, A=1.0` — then
gives a title hit 2.5x an abstract hit with no tuning.

*Alternative rejected:* pinning an explicit weights list in the query. It is one more
number to keep in sync for a ratio that is already reasonable, and the defaults are
stable across Django versions.

### 4. `websearch_to_tsquery` for parsing user input

`SearchQuery(q, search_type='websearch', config=...)`.

*Why:* it never raises, whatever punctuation arrives, which satisfies the safety
requirement by construction rather than by sanitising input. It also gives users
quoted phrases, `-exclusion` and `or` for free. `plainto_tsquery` is equally safe but
silently discards quotes, which is worse behaviour for the same effort. `raw` is
unsafe and is not an option.

*Consequence:* a query of nothing but stopwords (`q=the`) parses to an empty tsquery
and matches nothing. That is a legitimate empty result, not an error — see Decision 6.

### 5. Snippet by truncation, not `ts_headline`

The snippet is the leading N characters of the abstract, cut on a word boundary, with
an ellipsis when truncated.

*Why over `SearchHeadline`:* `ts_headline` would highlight the matched terms, which is
prettier, but it embeds HTML markup in a JSON API, re-parses the document per result
row, and creates an escaping question this card does not need to answer. HS-008 can
add highlighting to the page if it wants it. Truncation has no failure mode.

### 6. Two different kinds of "nothing", answered differently

| Input | Meaning | Response |
|---|---|---|
| `q` absent, empty, or only whitespace | the caller asked nothing | `400` with a helpful message |
| `q` present and meaningful, no rows match | the caller asked, the corpus had nothing | `200`, `count: 0`, empty list |
| `q` present but only stopwords | parses to an empty query | `200`, `count: 0`, empty list |

Returning the whole corpus for an empty `q` is explicitly wrong, and a 500 is
explicitly wrong. The stopword case is deliberately grouped with "no match" rather
than with "asked nothing", because the caller did supply a real query.

### 7. Authors are not searchable in this change

AGENTS.md §3 names "an author's name" as an exact-token query the keyword half is
supposed to carry, so this is a real gap and it is being taken knowingly.

*Why deferred:* `authors` is a `text[]`, and `array_to_string` is STABLE, so
PostgreSQL rejects it in a generated column. Including authors needs either an
`IMMUTABLE` SQL wrapper function or a denormalised text column maintained by
ingestion — the second reopens HS-006. Both also raise a ranking question this card
has no room for: a collaboration paper with 2,000 authors becomes a large lexeme bag
that dilutes its own rank, which needs `ts_rank` normalisation to be chosen
deliberately.

HS-007 as carded scopes search to title and abstract. The contradiction with
AGENTS.md §3 is noted on the board card so HS-012 inherits it rather than losing it.

### 8. `publication_date` is padded in the serializer, not stored

`earliest_date` is a `CharField` holding `2026`, `2026-09` or `2026-09-05`. The API
emits a real date, padding partial values to the first of the period.

*Why in the serializer:* it is a presentation concern. Adding a real `DateField` to
the model would mean a migration, an ingestion change, a compare-fields update and a
5,000-row backfill — reopening HS-006 to change how an existing value is displayed.

*Cost accepted, and it is a real one:* 697 papers (14%) will report a day they were
not published on. Sorting by this field would therefore be subtly wrong, which is
tolerable only because this change sorts by relevance and never by date.

### 9. The ranking function returns a queryset

`search(query: str, limit: int) -> QuerySet[Paper]`, in `apps/search/ranking.py`,
annotated with rank and ordered.

*Why a queryset over a list of dicts:* it stays lazy and composable, so HS-012 can
fuse it with a vector queryset instead of re-implementing it, and it keeps
serialisation in the serializer where it belongs. It is still fully testable without
HTTP — the tests call it directly.

### 10. Envelope response shape from the start

`{"count": <int>, "results": [...]}` rather than a bare list, so HS-013 can add
pagination without breaking a consumer. `count` is the number of results returned,
which equals the number matched only until the cap bites — a distinction HS-013 will
have to make honest when it adds real pagination.

### 11. The cap is a setting

`SEARCH_RESULT_LIMIT` in `config/settings.py`, following the `INGEST_BATCH_SIZE`
precedent, defaulting to 20. It bounds the response and, with `SearchRank` ordering,
bounds the work the database does per request.

### 12. DRF stays on its defaults

No `REST_FRAMEWORK` settings block. The browsable API is a convenience while
developing and HS-013 owns hardening. Adding configuration now would pre-empt a card
that exists to make those choices deliberately.

## Risks / Trade-offs

**The `EXPLAIN` acceptance criterion may be unsatisfiable as literally worded** → At
5,000 rows PostgreSQL will correctly prefer a sequential scan for a non-selective term.
In a Higgs corpus, `q=higgs` matches most of the table, and choosing a seq scan there
is the planner being right, not the index being broken. The check is therefore done
once, by hand, against a deliberately selective term, and pasted into the commit body.
It is **not** encoded as an automated test: asserting query plans is brittle and would
fail on a different corpus, a different row count, or after `ANALYZE`.

**Table rewrite on migration** → Adding a stored generated column rewrites
`papers_paper` and holds an `ACCESS EXCLUSIVE` lock. Seconds at 5,000 rows, on a
local single-developer database, with no production deployment in scope for v1.

**Rollback is a plain reverse migration** → The column is derived, so dropping it
loses nothing. Ingestion does not reference it, so a rollback cannot orphan data.

**English stemming is wrong for some physics tokens** → Stemming collapses word
forms, which mostly helps, but detector names, collaboration acronyms and identifiers
are not English words. This is precisely the gap the hybrid ranker in HS-012 exists to
cover, and this change is the baseline it must beat.

**Padded dates are a small lie in the payload** → 14% of results report a
first-of-period day. Accepted because results are ranked by relevance, never by date;
it becomes a real problem the moment anyone sorts or filters on this field, and that
should be revisited if HS-013 or HS-014 wants date filtering.

**`count` is not the total match count once the cap bites** → A caller cannot tell
"20 results" from "20 of 4,000". Deliberate: making it honest needs a second
`COUNT(*)` query per request, and HS-013 owns pagination.

## Migration Plan

1. Add `search_vector` and the `GinIndex` to `Paper`; generate the migration.
2. Apply it against the existing 5,000-row corpus — PostgreSQL backfills the column
   during the rewrite, so no data migration or re-ingestion is needed.
3. Confirm the vector is populated and the index exists before wiring up the view.
4. Rollback: reverse the migration. The column is derived and unreferenced elsewhere.

## Open Questions

These were decided to keep momentum and are cheap to reverse before implementation:

- **Weights (Decision 3):** relying on `SearchRank` defaults rather than pinning an
  explicit ratio. Reversible in one line.
- **Dates (Decision 8):** padding partial dates in the serializer. The alternative
  worth considering is emitting `date` plus a `date_precision` field so HS-008 can
  render `2026` as `2026` rather than as a specific day.
- **Authors (Decision 7):** deferred to HS-012. If author lookup is what would make
  this feel real, the `IMMUTABLE` wrapper route is roughly fifteen lines and does not
  reopen ingestion.