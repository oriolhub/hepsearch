## Why

HS-007 put ranked search behind `GET /api/search/`, which is only reachable by
someone willing to write HTTP requests. A physicist wants a box to type into. This
card closes that gap with a plain server-rendered Django template — no JavaScript
framework, no build step (AGENTS.md §2).

Building it surfaced a defect in what HS-007 already shipped. The corpus is HEP
literature, so collaboration papers are normal, not exotic:

| measured against the live 5,000-paper corpus | |
|---|---|
| largest author list on one paper | **5,360** |
| mean authors per paper | 190 |
| papers with more than 500 authors | 347 (6.9%) |
| papers with no authors at all | 264 (5.3%) |

`PaperSearchResultSerializer` returns `authors` in full, so a single 20-result
response weighs **338 KB and carries 16,818 author names** — about 99% of the
payload. The page would render that same list as HTML, pushing every abstract below
thousands of names. The page is therefore not buildable in a usable form until the
result shape is bounded, so this change fixes both.

## What Changes

- A new `GET /` renders a search form and, when a query is submitted, the ranked
  results: title linked to INSPIRE, a summarised author line, the publication date,
  and an abstract snippet.
- The page calls the same `apps.search.ranking.search()` the API calls, so the page
  and the API can never disagree about ranking.
- **The API result shape becomes bounded.** `authors` is truncated to the first five
  names and a new `author_count` reports the true total. A response becomes ~12.8 KB
  regardless of query, instead of varying between 70 KB and 355 KB.
- `Paper` gains three display helpers — `display_authors`, `display_date` and
  `abstract_snippet` — joining `inspire_url` and `author_summary`, which already live
  there. Django templates cannot call methods with arguments, so a helper the template
  can read without arguments is what makes the "dumb template" possible.
- `Paper.author_summary` changes its separator from `", "` to `"; "`. INSPIRE supplies
  `full_name` as `"Last, First"`, so comma-joining is genuinely ambiguous: five authors
  currently read as ten.
- The page presents partial dates at the precision actually stored — `2020`,
  `May 2020`, `10 May 2020` — rather than the API's padded `date`, because rendering
  "1 January 2020" for a paper we only know the year of is a fabrication a human will
  read as fact. 588 papers (12%) are affected.

Breaking: the `authors` field of the API changes meaning from "every author" to "the
first five". Nothing consumes the API yet, so the cost is zero and the time to do it
is now.

## Capabilities

### New Capabilities

- `search-page`: The browser-facing surface — the form, the rendering of results, the
  three empty states, escaping of user-supplied text, and the requirement that the
  page reuse the search function rather than copy it.

### Modified Capabilities

- `keyword-search`: A result now carries a bounded author list plus a total count,
  rather than every author. This is a contract change, not an implementation detail:
  a caller must be told that what it received is a sample and how large the real list
  is.
- `paper-model`: The existing author-summary requirement gains a separator guarantee
  that keeps `"Last, First"` names unambiguous, and the model gains display helpers
  for the date and the abstract excerpt so that every consumer derives them once.

## Impact

**Code**
- `apps/papers/models.py` — `display_authors`, `display_date`, `abstract_snippet`;
  `author_summary` separator
- `apps/search/views.py` — a plain Django view alongside the existing DRF view
- `apps/search/templates/search/search.html` — new, the only template
- `apps/search/serializers.py` — bounded `authors`, new `author_count`
- `config/urls.py` — routes `""`
- Tests in `apps/papers/tests/` and `apps/search/tests/`

**Not touched**
- `apps/search/ranking.py` — the page reuses it unchanged, which is the point
- `apps/ingestion` — `authors` is still stored complete; only presentation is bounded
- No new dependency, no static files, no settings beyond what HS-007 added

**Deliberately deferred**
- Styling, highlighting, pagination, mode switching, elapsed time — HS-014
- Throttling and the DRF browsable API's own unbounded HTML rendering — HS-013
