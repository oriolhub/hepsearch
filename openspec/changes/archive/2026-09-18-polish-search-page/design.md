## Context

HS-008 shipped the page as a form and a list of titles, explicitly deferring polish
until the ranking was worth presenting. Two cards later it is: HS-012 fuses keyword and
semantic ranking, HS-013 bounds and paginates it. The page reflects none of this.

Everything below was decided against measurements taken on the ingested 5,000-paper
corpus rather than from first principles, because two of the card's criteria turned out
to rest on false premises.

**Corpus field coverage**, which decides what a result line can actually show:

| Field | Present | Note |
|---|---|---|
| `citation_count` | 100.0% | 1,787 papers (35.7%) have exactly zero |
| `earliest_date` | 100.0% | |
| `doi` | 68.7% | |
| `arxiv_id` | 63.4% | |
| `journal` | 62.5% | |
| *neither journal nor arXiv* | **22.6%** | 1,131 papers |
| `authors` | mean 190, **max 5,360** | 379 papers carry over 100 |

**Ranking mix on the first hybrid page** of a paraphrase query: 9 semantic-only, 8
keyword-only, 3 both.

**Latency**: 65.3s on the first search after a restart (the sentence-transformers model
loads lazily), 0.089s once warm.

## Goals / Non-Goals

**Goals**

- A reader can tell *why* a paper was retrieved, including when it shares no words with
  the query.
- Excerpts show the matching passage, not the opening sentence.
- Numbers shown to a reader are true, including when the true answer is unflattering.
- The page stays readable in a narrow window.

**Non-Goals**

- JavaScript, a framework, a build step, a design system, dark mode (AGENTS.md §2).
- Changing the JSON API. The page's snippet may differ from the API's; see decision 7.
- Changing anything in `apps/search/ranking.py`.
- Reorganising page requirements that already live in other capabilities.
- Fixing the 65-second cold start. Real, out of scope, see Risks.

## Decisions

### 1. The page reports *retrieved* results, never a corpus-wide total

The page renders "Showing 1–20 of 60 retrieved". It does not render "4,429 results".

`higgs` matches 4,429 papers; the system retrieves 60 of them. It does not know the
4,429 and cannot learn it without a `COUNT(*)`, which `api-hardening` forbids:

> The system SHALL paginate the rows a ranking already returned, and SHALL NOT issue a
> separate query to count matches.

Three options were considered: display the retrieval figure labelled as retrieved;
display a corpus-wide total (needs the forbidden query); display the retrieval figure
unlabelled (a false statement). The first is the only one that is both cheap and true.
What damages a demo is not an ugly truth, it is a confident falsehood.

The denominator differs per mode — 60 for keyword and hybrid, 40 for semantic, whose
ceiling is the HNSW index's `ef_search` rather than the query. This is correct and is
noted on the card so it is not later reported as a defect.

This makes HS-014's "the result count is shown" stale. The card is corrected; no
specification changes, because the specifications already say this.

### 2. Elapsed time is wall-clock, and the cold start is shown

The page shows what actually happened. It does not show a "ranking-only" figure that
excludes model loading.

A reader who waited 65 seconds and is told "89 ms" correctly concludes the interface is
lying. The cold start is a real defect with real fixes — preload at startup, or warm the
model during deployment — and none of them is redefining the metric until it flatters us.

The measurable boundary: timing starts when the view begins ranking and stops before
the template renders. A page cannot time its own rendering, so template render and
middleware (single-digit milliseconds) fall outside. This covers the model load, which
happens inside ranking, so the 65-second case is reported honestly.

### 3. Highlighting uses `ts_headline`, because nothing else stems

The query "measuring the strength of the Higgs **coupling**" must highlight
"measurements", "measured" and "couplings". Verified against the corpus:

```
query terms:  measuring, strength, Higgs, coupling
highlighted:  measured, measurements, strengths, Higgs, coupling, couplings
```

A Python regex over the query's literal words cannot do this without reimplementing the
`english` snowball stemmer. PostgreSQL already has one, and it is the same one that
built the `search_vector` the ranking scored against — so the highlight agrees with the
retrieval by construction rather than by coincidence.

A second property, found by measurement: on a document containing **no** match,
`ts_headline` returns the head of the text unmarked — behaviourally identical to today's
`abstract_snippet`. Semantic-only results therefore degrade into current behaviour with
no special case, which matters given decision 5.

Cost: **0.050s for 20 rows**, as an annotation on the ranking query. Negligible beside
the embedding inference and vector scan already in the request.

### 4. The annotation is composed onto the ranker's queryset, before pagination

`SearchHeadline` attaches in the **view**, onto the queryset `search()` and
`semantic_search()` return. Verified: annotating an already-sliced queryset works on
both arms, the `LIMIT` survives, and the generated `SELECT` is byte-identical to the
HS-007 baseline plus the headline expression. The instance still reports `embedding` and
`search_vector` deferred, so AGENTS.md's large-column rule is not violated.

This placement is the whole reason the decision is cheap:

```
ranking.py      returns ranked queryset      ← untouched, presentation-free
     │
views.py        .annotate(headline=...)      ← presentation composed here
     │
paginator       slices to 20
     │
template        escapes, marks, renders
```

`keyword-search` requires that ranking performs no excerpting, and separately blesses
composition by the caller ("the result is composable"). Putting the annotation in the
ranker would have violated the first; putting it in the view exercises the second.

The alternative — a second query hydrating only the 20 displayed rows — computes exactly
what is shown and wastes nothing. It was rejected anyway. It adds a query to a path
HS-013 spent a card proving costs nothing extra per page, it invalidates the
`django_assert_num_queries` assertions pinning that, and it buys an architectural
exception for a cosmetic gain. Annotating 60 rows to display 20 wastes roughly 0.1s of
database time and no engineering credibility.

### 5. The method badge is load-bearing, not decoration

Every result names the ranking that found it, in every mode.

The card asks for this "even if subtly". The measurement argues the opposite: 45% of a
hybrid page is semantic-only, and by decision 3 those rows show no highlighted terms.
Without a badge, nearly half the page reads as a ranking failure. With one, it reads as
the feature the project exists to demonstrate.

```
┌────────────────────────────────────────────────────┐
│ Non-resonant HH production at the HL-LHC           │
│ [semantic]                                         │
│ ...predicted production rate roughly 1000 times    │
│    smaller than single-Higgs production...         │
│                     ↑ no marks — explained, not a bug │
└────────────────────────────────────────────────────┘
```

In keyword and semantic modes every result carries the same badge as the mode. That is
redundant but consistent, and a special case that hides the badge in single-mode
searches would cost more than it saves.

### 6. Metadata falls back journal → arXiv → DOI → nothing

22.6% of the corpus has neither a journal nor an arXiv id, so "journal or arXiv id" as
the card words it renders an empty line for 1,131 papers. The DOI covers 68.7% and is
useful to a physicist; the INSPIRE id is an internal identifier and is not a fallback,
though every result already links to its INSPIRE record.

`0 citations` is rendered rather than suppressed. 35.7% of the corpus has zero, and
hiding the line for those papers makes rows change height for a reason the reader cannot
see, while removing the information that the paper is genuinely uncited.

Authors keep the existing `display_authors`: five names, then `et al. (5360)`. No
`<details>` toggle — it earns no acceptance criterion, and anyone needing all 5,360
names has an INSPIRE link.

### 7. The page's snippet may differ from the API's

The page shows a headline fragment; the JSON keeps `abstract_snippet`, the first 280
characters. These will differ for the same paper.

HS-008's guarantee was that page and API "can never disagree about **ranking**", and
that holds — both call the same ranker. A snippet is presentation. Propagating headlines
into the JSON to eliminate a cosmetic difference would mean redesigning a public
response shape to satisfy a template, which is the scope creep this project's
non-goals exist to prevent.

The consequence is that the page path must opt into highlighting while the API path does
not, so the shared ranking helper in `views.py` becomes conditional on it. That is the
one structural change these decisions force.

### 8. Highlighting is escape-first; the database's HTML is never trusted

```
ts_headline(StartSel=SENTINEL_OPEN, StopSel=SENTINEL_CLOSE)
        │
        ▼
django.utils.html.escape(whole string)      ← all paper text now inert
        │
        ▼
replace SENTINEL_OPEN  → <mark>
        replace SENTINEL_CLOSE → </mark>
        │
        ▼
mark_safe                                    ← only known markers are markup
```

The safety property is positional: *everything* is escaped, and afterwards exactly two
known tokens become markup. No property of PostgreSQL's output is relied upon.

This matters because measurement showed `ts_headline` does transform markup in the
source text — `<script>alert(1)</script>` came back as ` alert(1) `, and a literal
`<<<fake>>>` came back as `<< >>`. That behaviour is convenient but it is not a
documented security guarantee, it varies with the text-search parser's tag handling, and
building an XSS defence on it would be indefensible. Sentinels are chosen not to look
like tags, so the parser does not mangle them.

The resulting test is deterministic and does not depend on PostgreSQL's behaviour: a
`<script>` query, and an abstract containing markup, both render as literal text.

### 9. One card, one commit

Nothing here is independently shippable. "Make the page demo-ready" is not satisfied by
metadata without badges, or highlighting without the layout that makes it readable. A
midpoint commit would leave the page in a state no acceptance criterion describes.

HS-008 split into two commits because it had a genuine seam — bounding author data was
useful on its own. This card has no such seam.

## Risks / Trade-offs

**The 65-second cold start is now visible on the page** → Decision 2 makes it visible
rather than hidden, which is the point. It is a pre-existing defect, out of scope here,
and the honest display is what will motivate fixing it. Mitigation is a deployment
concern (warm the model), not a template concern.

**Annotating 60 rows to render 20** → Roughly 0.1s of wasted database work per search.
Accepted deliberately in exchange for a flat query count and an untouched ranking module.
If the retrieval depth ever grows substantially, revisit — the trade tilts with depth.

**The retrieved count will be read as a corpus total by someone** → "Retrieved" is in the
label for exactly this reason. The per-mode difference (60/60/40) makes it more visible,
not less, which is a feature.

**Page and API snippets diverge** → Accepted in decision 7. The risk is a future reader
assuming one is a bug; the design note above is the mitigation.

**`ts_headline` re-parses the abstract on every search** → It cannot use an index and is
known to be the slow part of PostgreSQL full-text display. Measured at 0.050s for 20
rows on this corpus, against a 512-token abstract; acceptable, and bounded by the
retrieval depth rather than the corpus size.

**Badge redundancy in single-mode searches** → Every result in `mode=keyword` says
"keyword". Consistency was chosen over a conditional; if it reads as noise in practice,
suppressing it is a one-line template change with no specification impact.
