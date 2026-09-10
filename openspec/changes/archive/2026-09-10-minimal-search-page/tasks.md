# Tasks

Two commits, in this order. Each leaves the application working, tested and
demonstrable (AGENTS.md §7).

## Commit 1 — `HS-008: Bound the author list in search results`

### 1. Model display helpers

- [x] 1.1 Change `Paper.author_summary`'s separator from `", "` to `"; "`, so that
      `"Last, First"` names stay unambiguous
- [x] 1.2 Leave `author_summary`'s `max_authors` default at 3 — the admin column is
      dense on purpose and the listing chooses its own density at the call site
- [x] 1.3 Add `Paper.display_authors`, an argument-free property returning
      `author_summary(5)`, so a template can render it without passing arguments
- [x] 1.4 Return an empty string from `display_authors` when there are no authors, so
      the template can omit the line entirely rather than render an empty label
- [x] 1.5 Add `Paper.display_date`, an argument-free property rendering `earliest_date`
      at the precision stored — full date, month and year, or year alone
- [x] 1.6 Return an empty string from `display_date` for an empty or unparseable
      `earliest_date`, without raising
- [x] 1.7 Confirm `display_date` never mutates or reformats the stored `earliest_date`
- [x] 1.8 Add `Paper.abstract_snippet`, an argument-free property delegating to the
      existing `excerpt_abstract` with `settings.ABSTRACT_SNIPPET_CHARS`
- [x] 1.9 Confirm `apps/papers` still imports neither `apps.search` nor `apps.ingestion`
      — importing `django.conf.settings` is framework, not an app dependency

### 2. Bounded API results

- [x] 2.1 Add a named bound for the author sample to `config/settings.py`, defaulting
      to 5 and read via `env.int`, following the `SEARCH_RESULT_LIMIT` precedent
- [x] 2.2 Truncate `authors` in `PaperSearchResultSerializer` to that bound
- [x] 2.3 Add a required `author_count` field carrying the paper's true author total
- [x] 2.4 Reuse `Paper.abstract_snippet` in the serializer rather than calling
      `excerpt_abstract` separately, so page and API excerpt identically
- [x] 2.5 Leave `publication_date` exactly as HS-007 shipped it — the API keeps the
      padded, typed date; only the page dates itself by precision
- [x] 2.6 Confirm no migration is generated: nothing about the schema changed

### 3. Tests for commit 1

- [x] 3.1 `author_summary` separates names with `"; "`
- [x] 3.2 Update the existing `test_author_summary` for the new separator
- [x] 3.3 `display_authors` names five authors and states the true total for a
      collaboration paper
- [x] 3.4 `display_authors` is empty for a paper with no authors
- [x] 3.5 `display_date` renders full, year-month and year-only dates at their stored
      precision, and empty for `""`
- [x] 3.6 `display_date` leaves `earliest_date` untouched
- [x] 3.7 `abstract_snippet` excerpts a long abstract at a word boundary and returns a
      short one whole
- [x] 3.8 Serializer: `authors` is bounded to the configured sample for a
      thousand-author paper, and `author_count` reports the true total
- [x] 3.9 Serializer: a paper with fewer authors than the bound carries all of them,
      with a matching `author_count`
- [x] 3.10 Serializer: a paper with no authors carries an empty list and a count of zero
- [x] 3.11 Update any HS-007 test asserting the full `authors` list

### 4. Gates and commit 1

- [x] 4.1 `git mv` the HS-008 card from `board/backlog/` to `board/in-progress/`
- [x] 4.2 Record on the card that this card ships as two commits, and why
- [x] 4.3 `uv run pytest`
- [x] 4.4 `uv run ruff check .`
- [x] 4.5 `uv run ruff format --check .`
- [x] 4.6 Measure a real API response before and after, and record both sizes in the
      commit body
- [x] 4.7 Commit as `HS-008: Bound the author list in search results`, leaving the card
      in `board/in-progress/`

## Commit 2 — `HS-008: Add a minimal search page`

### 5. The view and the route

- [x] 5.1 Add a plain Django view to `apps/search/views.py`, beside the existing DRF
      view, not replacing it
- [x] 5.2 Read `q` from the query string; treat absent and whitespace-only identically
- [x] 5.3 Call `ranking.search()` with `settings.SEARCH_RESULT_LIMIT` — never a copy of
      the ranking logic, never an HTTP call to the project's own API
- [x] 5.4 Skip the search entirely when there is no real query, so an empty submission
      costs no database work
- [x] 5.5 Pass the submitted query back to the template so it can be redisplayed
- [x] 5.6 Distinguish "no query was asked" from "a query matched nothing" in the
      context, so the template can stay free of that logic
- [x] 5.7 Route `""` to the view in `config/urls.py`, keeping the existing direct-import
      pattern rather than adding `apps/search/urls.py`
- [x] 5.8 Confirm the view module still imports nothing from `apps.ingestion`

### 6. The template

- [x] 6.1 Create `apps/search/templates/search/search.html` — one template, no
      `base.html`
- [x] 6.2 Render a `GET` form with a text input named `q` and a submit control
- [x] 6.3 Redisplay the submitted query as the input's value
- [x] 6.4 Render each result: title linked to `paper.inspire_url`, `display_authors`,
      `display_date`, `abstract_snippet`
- [x] 6.5 Omit the author line entirely when `display_authors` is empty
- [x] 6.6 Render a "no results" message only when a real query matched nothing
- [x] 6.7 Render neither results nor a "no results" message on a first visit or an empty
      submission
- [x] 6.8 Keep Django's autoescaping on — no `|safe`, no `mark_safe`, anywhere
- [x] 6.9 Put the small amount of CSS in an inline `<style>` block; add no static files
- [x] 6.10 Confirm the page renders without executing any client-side script

### 7. Tests for commit 2

- [x] 7.1 A query renders the expected paper titles in the HTML
- [x] 7.2 A result links to the paper's INSPIRE URL
- [x] 7.3 A query containing `<script>` is escaped — the raw tag is absent, the escaped
      text present
- [x] 7.4 The submitted query is redisplayed in the input, escaped
- [x] 7.5 A query matching nothing renders the "no results" message, status 200
- [x] 7.6 A first visit with no `q` renders the form, status 200, with no error and no
      "no results" message
- [x] 7.7 An empty `q` behaves identically to a first visit
- [x] 7.8 A whitespace-only `q` behaves identically to a first visit
- [x] 7.9 A collaboration paper renders a summarised author line, not thousands of names
- [x] 7.10 A paper with no authors renders no author line
- [x] 7.11 The page and the API return the same papers in the same order for one query
- [x] 7.12 Confirm no page test makes a network request

### 8. Verify against the real corpus

- [x] 8.1 Run the page by hand against the ingested 5,000 papers and read the results
- [x] 8.2 Confirm a collaboration-heavy query renders in reasonable time and does not
      produce a wall of author names
- [x] 8.3 Confirm a year-only paper shows just its year, with no fabricated day
- [x] 8.4 Record the query used and what it returned in the commit body

### 9. Gates and commit 2

- [x] 9.1 `uv run pytest`
- [x] 9.2 `uv run ruff check .`
- [x] 9.3 `uv run ruff format --check .`
- [x] 9.4 Tick the card's acceptance criteria and Definition of Done
- [x] 9.5 Note on the card that the DRF browsable API still renders unbounded HTML, for
      HS-013
- [x] 9.6 `git mv` the card from `board/in-progress/` to `board/done/` in this commit
- [x] 9.7 Commit as `HS-008: Add a minimal search page`
