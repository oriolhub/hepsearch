## Context

HS-007 shipped ranked keyword search as a DRF endpoint. HS-008 adds the page a human
uses. The card is prescriptive about *what* the page does and mostly silent about how
the page obtains presentable values from a `Paper`, which is where the real decisions
are.

Three facts from the live corpus drive most of what follows:

```
authors per paper        max 5,360   mean 190   >500: 347 papers   zero: 264 papers
earliest_date precision  full 4,303  year-month 109  year-only 588  empty 0
API response size        70 KB - 355 KB, ~99% author names
```

The dependency rule (AGENTS.md §3) is unchanged: the page lives in `apps/search`,
imports `apps/papers`, and never imports `apps/ingestion`.

## Goals / Non-Goals

**Goals**
- A usable, ugly page at `GET /` that shares ranking with the API.
- A bounded API response, so neither surface can emit a 355 KB result set.
- One derivation per displayed value, reachable from both the page and the API.
- Escaping proven by test, so HS-014's highlighting has a regression guard to break.

**Non-Goals**
- Styling beyond legibility, highlighting, pagination, mode switching, timing — HS-014.
- Throttling, error hardening, disabling the DRF browsable API — HS-013.
- Any change to ranking. `ranking.search()` is reused verbatim.
- Any change to what ingestion stores. Author lists stay complete in the database.

## Decisions

### 1. The page renders from `Paper` objects, not from serializer output

The page view calls `ranking.search()` and hands the resulting `Paper` rows straight
to the template. It does not run `PaperSearchResultSerializer`.

The alternative — serialize, then render the dicts — would guarantee the page and API
agree on every field. It was rejected because it couples a plain Django page to DRF
and, more importantly, because the two surfaces *should* disagree in two places: the
page wants an author sentence where the API wants a list, and the page wants an honest
partial date where the API wants a typed one. Forcing a shared representation would
mean the page inherits decisions made for machines.

What must not diverge is ranking, and that is guaranteed structurally: there is exactly
one `ranking.search()` and both callers use it.

### 2. Display helpers live on `Paper`

Django templates cannot call a method with arguments, so `{{ paper.author_summary }}`
invokes it with the default of three, not the five we want, and there is no way to pass
`ABSTRACT_SNIPPET_CHARS` to an excerpt function from a template.

Three options were considered:

| | approach | verdict |
|---|---|---|
| a | change `author_summary`'s default, use the builtin `truncatechars` filter | rejected: `truncatechars` cuts mid-word, so the page's excerpt rule would silently differ from the API's |
| b | custom template filters wrapping the existing plain functions | rejected: a new `templatetags` package to expose logic the model can expose for free |
| c | argument-free properties on `Paper` | **chosen** |

`Paper` already carries `inspire_url` and `author_summary` for exactly this reason —
the `paper-model` spec says the INSPIRE URL exists on the model "so that the admin, the
API and the results page share one derivation". The results page it anticipated is this
one. Adding `display_authors`, `display_date` and `abstract_snippet` continues an
established pattern rather than inventing one.

**Accepted trade-off:** `abstract_snippet` reads `settings.ABSTRACT_SNIPPET_CHARS`,
which puts a presentation bound on the domain model. AGENTS.md §3's "the domain depends
on nothing" governs *app* dependencies — `papers` must not import `search` or
`ingestion` — and Django settings are framework infrastructure, not an app. So this does
not violate the rule, but it is a real smell and is recorded here rather than
discovered later. If it becomes a problem, the bound moves to a module constant in
`apps/papers`.

### 3. `author_summary` joins with `"; "`, not `", "`

Rendered against real data, the current separator is ambiguous:

```
  now:  Aad, Georges, Aakvaag, Erlend, Abbott, Braden Keim, ... et al. (2880)
             ^^^^^^^^                ^^^^^^^^
             five authors that read as ten

  after: Aad, Georges; Aakvaag, Erlend; Abbott, Braden Keim; ... et al. (2880)
```

INSPIRE's `full_name` is `"Last, First"`, so the names contain the separator. This is a
change to shipped code with an existing test, and it changes the admin's author column
too — which is an improvement there for the same reason.

### 4. The page shows five authors; the API returns five names plus a count

Five, not ten: with real `"Last, First"` names, five authors is roughly 90 characters,
which sits on one or two lines under a title. Ten is roughly 180 and dominates the row.
Five is passed explicitly by `display_authors`, so `author_summary`'s own default of
three stays as it is and the admin is unaffected.

For the API the same bound applies but the shape stays machine-readable: `authors`
becomes the first five names and `author_count` carries the true total. A client that
needs every author has `inspire_url`; the corpus is not the system of record.

Measured effect:

```
  "higgs boson pair production ATLAS"   355,601 B  ->  12,807 B
  "self-coupling"                       124,726 B  ->  12,818 B
  "Higgs"                                72,705 B  ->  12,945 B
```

The ratio is not the point. Bounded is the point: the response no longer depends on
whether an ATLAS paper happened to match.

### 5. The page dates itself honestly; the API keeps padding

`earliest_date` is stored verbatim as INSPIRE supplies it, and the `paper-model` spec
forbids padding it at rest. HS-007 pads it *in the serializer* so that JSON carries one
consistent type. That reasoning holds for a machine and fails for a human:

```
  stored         API (typed date)      page (display_date)
  "2020-05-10"   2020-05-10            10 May 2020
  "2020-05"      2020-05-01            May 2020
  "2020"         2020-01-01            2020
```

Padding is invisible in JSON — a caller sees a `date` and knows nothing was promised
about precision. On a page it renders as "1 January 2020", which a reader takes as a
fact about the paper. 588 papers (12%) would carry a fabricated month and day. So the
page formats by the precision actually present, and the API is left exactly as HS-007
shipped it.

### 6. Three empty states, two responses

| state | response |
|---|---|
| `GET /` with no `q` | the form, nothing else |
| `GET /?q=` or whitespace | the form, nothing else — identical to above |
| `GET /?q=zzz` matching nothing | the form plus an explicit "no results" message |

The page deliberately diverges from the API here. The API answers a missing `q` with
`400`, which is right for a caller that made a malformed request. A person who pressed
Enter on an empty box did not make an error and must not be shown one, so the page just
re-renders. Only a *real* query that found nothing earns a message — telling someone
there are "no results for ''" is noise.

### 7. GET, with `q` in the query string

The form submits with `GET`, so `/?q=higgs` is a real, shareable, bookmarkable URL, the
back button works, and no CSRF token is involved. The parameter is named `q` to match
the API, so one mental model covers both surfaces.

### 8. One template, styles inline, no static files

A single `apps/search/templates/search/search.html` with a small `<style>` block. The
card's "static assets, if any, are served through staticfiles" is satisfied vacuously
by having none, which is the honest reading: `django.contrib.staticfiles` is already
installed and `STATIC_URL` set, so the moment HS-014 adds a real stylesheet it works
with no further configuration. Adding a CSS file now, only to rewrite it in HS-014,
would be work performed to satisfy a checkbox.

No `base.html`. There is one page; a base template with a single child is indirection
without a reader.

### 9. The page view sits beside the API view, and routing stays in `config/urls.py`

`apps/search/views.py` gains a plain Django view next to the existing `@api_view`.
Introducing `apps/search/urls.py` and an `include()` was considered and rejected: the
project currently wires every route directly in `config/urls.py`, there are three
routes in total, and consistency with the existing pattern beats a structure sized for
a project that does not exist yet. HS-013 or HS-014 can split it when there is enough
to split.

### 10. Escaping is inherited, and tested anyway

Django templates auto-escape, so a `<script>` query renders as literal text with no
code written. The test is still worth having — not to prove Django works, but as a
regression guard for HS-014, which will add term highlighting in the snippet and will
be tempted to reach for `mark_safe` or `|safe`. That is exactly the change that
reintroduces the hole, and this test is what will catch it.

### 11. Two commits under one card

The card's Definition of Done names a single commit, but this change has two distinct
purposes: bounding what a result carries, and adding a page. AGENTS.md's "one purpose
per commit" wins, so:

1. `HS-008: Bound the author list in search results` — separator, model display
   helpers, serializer truncation, `author_count`, spec deltas. Card stays in
   `board/in-progress/`.
2. `HS-008: Add a minimal search page` — view, template, tests, card moves to
   `board/done/`.

Each leaves the application working and tested, which is what "baby steps" (AGENTS.md
§7) asks for. The card's DoD is updated to name both commits.

## Risks / Trade-offs

**The API contract changes meaning.** `authors` stops meaning "every author". A client
reading `len(authors)` gets 5 for a 2,880-author paper. `author_count` exists precisely
so that number is still reachable, and the field is mandatory rather than optional so a
caller cannot miss it. Nothing consumes the API today, so this is free now and would not
be later.

**A presentation bound reaches the domain model.** Recorded under decision 2. Contained
to one property; the escape hatch is a module constant.

**Changing `author_summary` touches shipped code.** The admin column changes too. It has
a test, which will be updated in the same commit; the ambiguity being fixed is real and
visible in production data.

**`display_date` is a fourth date representation.** Stored string, padded API `date`,
and now a formatted page string. The alternative was one representation that is wrong
for one of the two audiences. Each has a single definition in one place, so the count is
tolerable — but a fifth would mean the design is wrong.

**Rendering 20 papers hits the database for authors regardless.** Truncation happens in
Python, after PostgreSQL has already returned complete author arrays, so the 355 KB
still crosses the database boundary even though it no longer crosses the network one.
Fixing that means slicing the array in SQL, which is a real optimisation with no
measured need behind it at 20 rows. Explicitly not done.

## Migration Plan

No schema change, no migration, no data change. `authors` remains stored complete and
ingestion is untouched, so the whole change is reversible by reverting the two commits.

## Open Questions

None. Twelve design questions were resolved before this proposal was written; the
answers are recorded as decisions 1-11 above.
