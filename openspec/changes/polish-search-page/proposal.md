## Why

The page is the project's shop window and the only surface a physicist will actually
use, but it has not been touched since HS-008 shipped it "deliberately ugly-but-usable".
Since then the ranking underneath it changed completely: HS-012 made hybrid the default
and HS-013 bounded and paginated it. The page renders none of that.

The sharpest gap is measurable. On a paraphrase query, **45% of the first hybrid page is
semantic-only** — papers that contain none of the words the reader typed:

| Found by | Results on hybrid page 1 |
|---|---|
| semantic only | 9 |
| keyword only | 8 |
| both | 3 |

Those nine results are the entire point of the project, and on today's page they are
indistinguishable from noise: no highlight, no explanation, no reason for a reader to
believe they belong. Polish was deferred until the ranking was worth presenting. It now
is, and the presentation is what is holding the demo back.

One of HS-014's acceptance criteria is also stale. It asks for "the result count", a
concept HS-013 removed two hours before this proposal was written.

## What Changes

- Result snippets become **PostgreSQL `ts_headline` fragments with matched terms
  highlighted**, replacing the fixed first-280-characters excerpt on the page. The
  headline is a stemming-aware fragment selected *around* the match, so the excerpt
  shows why the paper was retrieved rather than merely what it opens with.
- Highlighting is rendered **escape-first**: the database emits inert sentinels, the
  whole string is HTML-escaped, and only then do the known sentinels become `<mark>`.
  PostgreSQL's headline output is never treated as trusted HTML.
- Every result carries a **method badge** naming which ranking found it. This is
  promoted from the card's "even if subtly" to unmissable, because it is what makes a
  semantic-only result with no highlighted terms legible instead of looking like a bug.
- Results gain a **metadata line**: journal, else arXiv id, else DOI, else nothing, plus
  the citation count and date.
- The page reports **how many results were retrieved and how long the search took**,
  using the honest retrieval-bound figure rather than a corpus-wide total.
- Zero results gets a message suggesting a rephrase, and the layout becomes readable in
  a narrow window. No JavaScript, no build step, no framework (AGENTS.md §2).

### Acceptance criterion corrected

| HS-014 as written | Correction | Evidence |
|---|---|---|
| "The result count and the elapsed search time are shown" | The number of *retrieved* results is shown, explicitly labelled as retrieved | HS-013 redefined `count` as the total within the retrieval bound, and `api-hardening` forbids a separate count query. `higgs` matches 4,429 papers; the system retrieves 60 and knows only that |

The card was written before HS-013 existed. This is the same class of correction applied
to five of HS-013's own criteria, and is recorded in the commit body rather than silently
implemented.

## Capabilities

### New Capabilities

- `search-page`: how ranked papers are presented to a human — highlighted snippets,
  metadata, external links, method badges, author truncation, retrieval and timing
  reporting, zero-result messaging, and a layout that survives a narrow window.

**This capability deliberately does not own every behaviour of the page.** Retrieval mode
semantics, degradation messaging, navigation state preservation and operational limits
stay with the capabilities that already specify them:

| Page behaviour | Stays in | Because |
|---|---|---|
| Hybrid is the default mode | `hybrid-search` | "An unqualified search means hybrid" is a contract that outlives this page; a CLI or second UI would inherit it |
| Semantic mode is reachable and its outage is announced | `semantic-search` | The capability asserting it is demonstrable |
| Pagination preserves query and mode | `api-hardening` | Added by HS-013 with the pagination it belongs to |
| The page is throttled | `api-hardening` | An operational limit, not a presentation choice |

Their absence here is deliberate, not an omission, and the capability's Purpose says so.

### Modified Capabilities

None. No existing requirement changes meaning.

## Impact

- `apps/search/views.py` — the page path annotates its rankings with `SearchHeadline`
  and reports elapsed time and retrieved count; the API path is unchanged.
- `apps/search/presentation.py` or equivalent (new) — the escape-first sentinel-to-
  `<mark>` conversion, as a pure function testable without a database.
- `apps/search/templates/search/search.html` — metadata line, badges, highlighted
  snippet, zero-result message, and CSS for a narrow window.
- `apps/papers/models.py` — a display helper for the journal/arXiv/DOI fallback, beside
  the existing `display_authors` and `display_date`.
- `board/backlog/HS-014-search-page-polish.md` — one acceptance criterion amended.
- **No changes to `apps/search/ranking.py`.** The headline annotation is composed by the
  caller onto the queryset the ranker returns, which `keyword-search` already permits
  ("the result is composable") and which keeps intact its requirement that ranking
  performs no presentation.
- No new dependencies. `SearchHeadline` ships with `django.contrib.postgres`.
- No API response change. The JSON `abstract_snippet` stays as it is.
