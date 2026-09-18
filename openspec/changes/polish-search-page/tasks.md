## 1. Amend the card before building

- [x] 1.1 `git mv board/backlog/HS-014-search-page-polish.md board/in-progress/`
- [x] 1.2 Amend the count criterion: the number of *retrieved* results and the elapsed
      time are shown, with "retrieved" explicit. HS-013 redefined `count` as the total
      within the retrieval bound and `api-hardening` forbids a separate count query, so
      a corpus-wide total is not available
- [x] 1.3 Record in the card's Context that the retrieval denominator differs per mode
      (keyword and hybrid 60, semantic 40, the latter set by `hnsw.ef_search`), so the
      difference is not later reported as a defect
- [x] 1.4 Record in the card's Context the measured hybrid page composition (9
      semantic-only, 8 keyword-only, 3 both), which is why the method badge is promoted
      from "even if subtly" to always visible
- [x] 1.5 Note in the card that AC-1 (hybrid default, mode switch) and AC-5 (pagination
      preserving query and mode) are already specified by `hybrid-search` and
      `api-hardening` respectively, and are verified here rather than newly specified

## 2. Presentation helpers

- [x] 2.1 Add a `display_reference` helper on `Paper` returning journal, else arXiv id,
      else DOI, else nothing, beside the existing `display_authors` and `display_date`
- [x] 2.2 Test it against all four cases, including the 22.6% of papers with neither a
      journal nor an arXiv id
- [x] 2.3 Add the sentinel constants and the escape-first highlight function in
      `apps/search/presentation.py` — escape the whole string, then replace only the
      generated sentinels with `<mark>`, then mark safe
- [x] 2.4 Choose sentinels that the text-search parser will not treat as tags, and
      comment why
- [x] 2.5 Test the highlight function as a pure function, with no database: markup in
      the text, markup in the sentinels' neighbourhood, and text with no sentinels at all

## 3. The page view

- [x] 3.1 Annotate the ranked queryset with `SearchHeadline` in the page path only,
      after ranking and before pagination, leaving `apps/search/ranking.py` untouched
- [x] 3.2 Make highlighting opt-in so the API path does not compute headlines it discards
- [x] 3.3 Configure the headline with the sentinel delimiters and the same search
      configuration that built `search_vector`
- [x] 3.4 Pass the elapsed wall-clock ranking duration and the retrieved total to the
      template
- [x] 3.5 Assert with `django_assert_num_queries` that the query count for a page is
      unchanged from before this change
- [x] 3.6 Assert the ranked instances still report `embedding` and `search_vector`
      deferred after annotation

## 4. The template

- [x] 4.1 Render the metadata line: authors, date, citation count including `0
      citations`, and `display_reference`
- [x] 4.2 Render the INSPIRE link on every result, and the arXiv link when an arXiv id
      exists
- [x] 4.3 Render the highlighted excerpt through the escape-first helper
- [x] 4.4 Render a method badge on every result in every mode
- [x] 4.5 Render "Showing 1–20 of 60 retrieved" and the elapsed time
- [x] 4.6 Render a zero-result message suggesting a rephrase, shown only after a search
      and not on the unsearched page
- [x] 4.7 Add the narrow-window stylesheet rules — no JavaScript, no build step

## 5. Tests

- [x] 5.1 A `<script>` query renders as literal text with no element added
- [x] 5.2 A paper whose title or abstract contains markup renders as literal text
- [x] 5.3 Matched terms are marked, including a stemmed inflection of a query term
- [x] 5.4 A result with no matching terms still shows an unmarked excerpt
- [x] 5.5 Method badges appear for every result in hybrid, keyword and semantic modes
- [x] 5.6 The retrieved total and range are rendered, and the wording says "retrieved"
- [x] 5.7 An elapsed time is rendered
- [x] 5.8 The zero-result message appears for an unmatched query and not for the
      unsearched page
- [x] 5.9 Pagination preserves the query and the mode — re-asserted here, though it is
      `api-hardening`'s requirement
- [x] 5.10 Confirm each scenario named in the delta spec has a literal corresponding
      test before checking this section off

## 6. Verify

- [x] 6.1 Walk the page by hand against the real corpus in all three modes, including a
      paraphrase query where semantic-only results dominate
- [x] 6.2 Confirm by hand that the reported elapsed time matches a stopwatch on a cold
      first search
- [x] 6.3 Check the layout in a narrow window
- [x] 6.4 `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`,
      `uv run python manage.py check`
- [x] 6.5 `openspec validate polish-search-page --strict`

## 7. Ship

- [x] 7.1 `git mv board/in-progress/HS-014-search-page-polish.md board/done/` and check
      off the acceptance criteria and definition of done
- [x] 7.2 Commit everything as one commit: `HS-014: Make the search page demo-ready`,
      with a body explaining why the count criterion was corrected and why the method
      badge was promoted to always visible
- [ ] 7.3 When syncing the spec, carry the boundary statement into the `search-page`
      capability's Purpose: presentation is owned here, while hybrid-as-default remains
      with `hybrid-search`, semantic reachability with `semantic-search`, and navigation
      state preservation and throttling with `api-hardening` — so a reader understands
      the omissions are deliberate
