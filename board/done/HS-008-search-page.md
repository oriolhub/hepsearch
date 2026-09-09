# HS-008: Add a minimal search page

**Status:** done
**Depends on:** HS-007

## Story

As a physicist, I want a web page with a search box, so that I can use the tool
without writing HTTP requests.

## Context

A plain Django template — no JavaScript framework, no build step (AGENTS.md §2).
The page renders server-side and calls the same search function the API uses, so
the two can never disagree about ranking.

Deliberately ugly-but-usable at this stage; polish is HS-014, after the ranking
is actually good.

This card ships as two commits: the first bounds author data and adds shared
display helpers; the second adds the page. The split keeps each commit focused
and leaves the application working at every step.

## Acceptance criteria

- [x] `GET /` renders a page with a search input and a submit button
- [x] Submitting a query renders ranked results: title (linked to INSPIRE),
      authors, date, and an abstract snippet
- [x] The view calls the shared search function, not a copy of the ranking logic
- [x] The submitted query stays visible in the input after submission
- [x] Zero results renders a clear "no results" message, not an empty page
- [x] An empty submission re-renders the form without an error page
- [x] All user-supplied text is escaped — a query containing `<script>` renders
      as literal text
- [x] Static assets, if any, are served through Django's staticfiles
- [x] A test asserts a query renders expected paper titles in the HTML
- [x] A test asserts the `<script>` query is escaped

## Definition of done

- [x] Acceptance criteria met
- [x] The page has been used by hand against the real corpus
- [x] `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` pass
- [x] Committed as `HS-008: Add a minimal search page`

## Out of scope

Styling and polish (HS-014), semantic results (HS-011), pagination (HS-013), any
JavaScript framework (never). The DRF browsable API still renders its own
unbounded HTML representation; HS-013 owns that hardening.
