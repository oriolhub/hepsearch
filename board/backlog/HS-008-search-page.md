# HS-008: Add a minimal search page

**Status:** backlog
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

## Acceptance criteria

- [ ] `GET /` renders a page with a search input and a submit button
- [ ] Submitting a query renders ranked results: title (linked to INSPIRE),
      authors, date, and an abstract snippet
- [ ] The view calls the shared search function, not a copy of the ranking logic
- [ ] The submitted query stays visible in the input after submission
- [ ] Zero results renders a clear "no results" message, not an empty page
- [ ] An empty submission re-renders the form without an error page
- [ ] All user-supplied text is escaped — a query containing `<script>` renders
      as literal text
- [ ] Static assets, if any, are served through Django's staticfiles
- [ ] A test asserts a query renders expected paper titles in the HTML
- [ ] A test asserts the `<script>` query is escaped

## Definition of done

- [ ] Acceptance criteria met
- [ ] The page has been used by hand against the real corpus
- [ ] `uv run pytest` and `uv run ruff check .` pass
- [ ] Committed as `HS-008: Add a minimal search page`

## Out of scope

Styling and polish (HS-014), semantic results (HS-011), pagination (HS-013), any
JavaScript framework (never).
