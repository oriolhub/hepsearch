# HS-014: Make the search page demo-ready

**Status:** done
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

The page reports retrieved results, not a corpus-wide count: HS-013 bounds retrieval
at 60 for keyword and hybrid, while semantic retrieval reaches 40 because the current
HNSW `ef_search` is 40. On a representative paraphrase query, the first hybrid page
contained 9 semantic-only, 8 keyword-only, and 3 dual-hit results. That makes method
badges explanatory, not decorative.

AC-1's hybrid default and mode switch are specified by `hybrid-search`; AC-5's
pagination state preservation is specified by `api-hardening`. HS-014 verifies both
while adding presentation polish.

## Acceptance criteria

- [x] The page uses hybrid search by default, with a visible way to switch modes
- [x] Results show title, authors (truncated sensibly for 50-author papers),
      journal or arXiv id, date, citation count, and an abstract snippet
- [x] Every result links to its INSPIRE page, and to arXiv when an arXiv id exists
- [x] Matched query terms are highlighted in the snippet, with the highlighting
      applied safely — a `<script>` query must still render as literal text
- [x] Pagination controls work and preserve the query and mode
- [x] The retrieved result range and total, explicitly labelled "retrieved", and the
      elapsed search time are shown
- [x] Zero results shows a helpful message suggesting a rephrase
- [x] The page is readable on a narrow window
- [x] Which method found each result is visible, even if subtly — it is the most
      interesting thing about the project
- [x] Tests assert: escaping of a `<script>` query, pagination preserving state,
      and the zero-result message

## Definition of done

- [x] Acceptance criteria met
- [x] Walked through by hand end to end against the real corpus
- [x] `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` pass
- [x] Committed as `HS-014: Make the search page demo-ready`

## Out of scope

A JS framework, a design system, dark mode, accessibility auditing beyond
sensible semantic HTML.
