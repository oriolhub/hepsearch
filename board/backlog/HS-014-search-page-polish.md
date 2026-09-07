# HS-014: Make the search page demo-ready

**Status:** backlog
**Depends on:** HS-013

## Story

As a physicist, I want a search page that is pleasant and informative to use, so
that I can judge result relevance at a glance.

## Context

Polish comes last, deliberately: styling a page whose ranking is still changing
is wasted work. By now hybrid ranking (HS-012) is in place, so the page finally
has something worth presenting.

Still no JavaScript framework and no build step (AGENTS.md §2). Plain templates
and a small amount of CSS.

## Acceptance criteria

- [ ] The page uses hybrid search by default, with a visible way to switch modes
- [ ] Results show title, authors (truncated sensibly for 50-author papers),
      journal or arXiv id, date, citation count, and an abstract snippet
- [ ] Every result links to its INSPIRE page, and to arXiv when an arXiv id exists
- [ ] Matched query terms are highlighted in the snippet, with the highlighting
      applied safely — a `<script>` query must still render as literal text
- [ ] Pagination controls work and preserve the query and mode
- [ ] The result count and the elapsed search time are shown
- [ ] Zero results shows a helpful message suggesting a rephrase
- [ ] The page is readable on a narrow window
- [ ] Which method found each result is visible, even if subtly — it is the most
      interesting thing about the project
- [ ] Tests assert: escaping of a `<script>` query, pagination preserving state,
      and the zero-result message

## Definition of done

- [ ] Acceptance criteria met
- [ ] Walked through by hand end to end against the real corpus
- [ ] `uv run pytest` and `uv run ruff check .` pass
- [ ] Committed as `HS-014: Make the search page demo-ready`

## Out of scope

A JS framework, a design system, dark mode, accessibility auditing beyond
sensible semantic HTML.
