## Context

HS-012 shipped hybrid ranking and made it the default mode. That changed the cost
profile of an unqualified request: it now embeds a query and issues two ranking queries
where it previously issued one and embedded nothing.

The API has no `REST_FRAMEWORK` block, no `CACHES` block and no `LOGGING` block. AGENTS.md
§6 nevertheless states "DRF throttling is on", which is aspirational text describing this
card's output sitting in the document that calls itself the single source of truth. This
is the same species of drift that HS-012 found in the identifier example, and it is
corrected the same way: measure, then amend the claim.

Three measurements against the ingested 5,000-paper corpus drive most of what follows.

**How deep each ranking can actually reach.** Rows available to page through, same
corpus, comparable queries:

| Ranking | Rows retrievable | Pages at size 20 |
|---|---|---|
| keyword `higgs` | 4,429 | 222 |
| semantic | 41 | 3 |
| hybrid (union of both arms) | 74 | 4 |

**Why semantic stops at 41.** It is the index, not the query. With `SQL LIMIT 200` held
constant:

| `hnsw.ef_search` | Rows returned |
|---|---|
| 40 (the default, never set in this repo) | 41 |
| 200 | 200 |
| 500 | 200 |

An HNSW scan returns at most `ef_search` candidates and the SQL `LIMIT` cannot reach
past them. Notably, the `hnsw.ef_search` GUC is *not registered on a connection* until
the vector extension's library loads in that session: `SHOW hnsw.ef_search` on a fresh
connection raises `ProgrammingError: unrecognized configuration parameter`, and only
succeeds after a vector query has run. Any design that issued `SET LOCAL hnsw.ef_search`
at the top of a request would fail on the first request served by a newly-opened pooled
connection.

**What each mode costs.** The inversion that invalidates the throttling criterion:

| Mode | Embeds? | Ranking queries | Cost |
|---|---|---|---|
| keyword | no | 1 | cheapest |
| semantic | yes | 1 | middle |
| hybrid | yes | 2 | **most expensive** |

## Goals / Non-Goals

**Goals:**

- Bound every public request in both work and response size, on the page as well as the
  API.
- State the retrieval ceiling honestly instead of letting a reader mistake "the index
  stopped looking" for "the corpus ran out".
- Give every bad parameter one predictable status and a message naming what was wrong.
- Leave `DEBUG=False` responses free of internal detail.
- Make AGENTS.md §6's throttling claim true.

**Non-Goals:**

- Authentication, API keys, or per-key rate limiting. The API is public.
- Redis, a cache server, or any shared throttle state. Rejected in AGENTS.md §2; the
  consequence is recorded under Risks.
- Raising `hnsw.ef_search`, globally or per request. Considered and rejected below.
- Caching search results. No criterion fails without it.
- Cursor pagination. The result sets are three pages deep.
- Page styling and highlighting — HS-014.
- Reconciling the rest of AGENTS.md against the code — HS-015.

## Decisions

### 1. Retrieval depth and page size are separate settings: 60 and 20

Pagination over a bound that equals the page size is not pagination. Depth 60 at page
size 20 gives three pages, which sits under hybrid's ~74-row union and just above
semantic's 41 — so semantic yields two full pages and a partial third, and no mode
advertises pages it cannot fill from its own arm.

`SEARCH_RESULT_LIMIT` is repurposed as the depth with its default raised from 20 to 60,
and `SEARCH_PAGE_SIZE = 20` is added. Repurposing rather than renaming keeps the diff
small and leaves the existing spec scenario about a named, configurable cap true.

*Alternatives:* depth 40 to match `HYBRID_CANDIDATE_DEPTH` exactly — only two pages, and
throws away a third of hybrid's reachable union. Depth 100 — keyword gets five pages
while semantic still stops at 41, advertising pages that are empty for two modes out of
three.

### 2. Pagination is bounded by retrieval depth, and the bound is documented

The corrected criterion. The alternative was to paginate the full match set, which is
impossible for semantic at any page size: the ceiling is a property of the index, and
the caller cannot distinguish "no more matches" from "the index stopped scanning".

Rejected: raising `hnsw.ef_search` globally in `postgresql.conf`. It is one line, and it
would genuinely deepen the semantic arm — but it is infrastructure configuration the
application cannot see or assert on, which is a fresh drift surface of exactly the kind
this change exists to close. Deferred until a criterion fails without it.

Rejected again: per-request `SET LOCAL`, already rejected on design grounds in HS-012
and now known to be unsafe on a cold connection.

### 3. Rankers keep returning lists; the paginator paginates the list

Every ranker already materialises its rows, and DRF's `paginate_queryset` accepts a
list. So `count` is `len(list)` and **no COUNT query is issued**: one query for keyword,
two for hybrid, on every page including the last. Deep pagination costs nothing extra
because there is no depth to go to.

This also keeps the "one query per ranking and no more" requirement HS-012 established
true under pagination, which slicing a queryset per page would not.

### 4. A custom paginator preserves the fields DRF's envelope would drop

DRF's `PageNumberPagination.get_paginated_response` returns exactly
`{count, next, previous, results}`, which would silently drop `mode`, and — worse —
`degraded` and `warning`, turning HS-012's "degradation is never silent" requirement
false. A small subclass overriding `get_paginated_response` keeps them. Scores and
`methods` are per-result and unaffected.

### 5. Two throttle rates, split by whether the request embeds

Keyword gets a generous rate; semantic and hybrid share one stricter rate. The criterion
as written ("stricter for semantic/hybrid than keyword") is preserved in spirit, but its
internal tiering is dropped: hybrid costs *more* than semantic, so any scheme that
throttles semantic harder than hybrid is inverted with respect to real cost.

Because `search` is a single `@api_view` function serving all three modes, the rate
cannot be a static `throttle_classes` list — the mode must be parsed first. The throttle
is therefore selected after `parse_mode`, which also means an unparseable mode is
refused before any throttle decision, and a 400 for a bad mode is not itself rate-limited
into a 429.

*Alternatives:* a single rate for everything — simpler, but lets a caller spend the
embedding budget through the cheapest endpoint. Three tiers by exact cost — more precise
than the measurement justifies, and hybrid being both the default and the strictest tier
is a trap for casual use.

### 6. The HTML page is throttled through the same classes

`search_page` is a plain Django view calling the same `_ranked_papers`. Left
unthrottled, a loop over `/?q=...` buys unlimited free embedding while `/api/search/`
sits politely limited.

`AnonRateThrottle` reads only `request.user` and `request.META`, both present on a plain
`HttpRequest` given `AuthenticationMiddleware` is installed, so the DRF throttle classes
can be reused directly from a small shared helper. No middleware, no view rewrite, no
new dependency. Exceeding the rate renders a plain-text 429 with `Retry-After`, matching
how `search_page` already returns `HttpResponseBadRequest` for an unknown mode.

### 7. All page trouble is one 404

`?page=abc` and `?page=999` leave DRF's paginator from the same line: `PageNotAnInteger`
subclasses `InvalidPage`, which is caught and re-raised as `NotFound`. Splitting them
into 400 and 404 means intercepting before the paginator to re-validate a parameter DRF
has already validated. One consistent 404 is both what the library does and what the
original criterion offered as its first option.

The 400 contract still covers every other parameter: missing `q`, empty `q`, unknown
`mode`, overlong `q`, out-of-range page size.

### 8. `q` is bounded at 1,000 characters

The bound exists to avoid lying about what was searched, not to save CPU. The encoder
truncates at 512 tokens — roughly 2,000 characters — and silently discards the rest, so
a caller submitting an essay would receive results for its first paragraph with no
indication that the remainder was ignored. Refusing at 1,000 characters keeps the
accepted input comfortably inside what the model actually reads. A named setting, since
it is a property of the configured model rather than a universal truth.

### 9. `LOGGING` is configured here, because the criterion requires it

There is no `LOGGING` block today, so `apps.search.*` records reach stderr only through
Python's `lastResort` handler. "Slow searches are logged" has nowhere to log to without
one. This is the minimum console configuration that makes the project's existing warnings
— stale embeddings, provider outages — visible, plus a slow-search record carrying the
elapsed time and the mode.

The query text is logged with newlines and control characters escaped. It is unvalidated
public input and a raw newline in a log line forges a second record.

## Risks / Trade-offs

**Throttle counters are per-process and do not survive a restart** → The cache is
Django's default `LocMemCache`; AGENTS.md §2 rejects Redis. Under `runserver` this is
honest. Under any multi-worker deployment the effective rate is N× the advertised one.
Recorded in the setting's comment rather than solved, since v1 has no deployment story
and a shared cache is exactly the "second system" the project refused.

**`count` changes meaning for existing callers** → BREAKING, and the reason
`keyword-search`'s response-shape requirement is modified rather than left alone. The
project has no external consumers and the page is updated in the same change, so the
blast radius is the test suite.

**Hybrid's arms stay at depth 40 while keyword mode reaches 60** → A paper at keyword
rank 50 is on keyword's third page but invisible to hybrid, which is the default. Raising
`HYBRID_CANDIDATE_DEPTH` to 60 would fix the keyword arm and do nothing for the semantic
arm, which is pinned at 40 by `ef_search` — producing uneven arms for no measured gain.
Left as is, documented, revisited if a comparison shows a miss.

**Throttling the page could lock out a demo** → The page is the project's shop window and
a demonstrator clicking through modes must not hit a 429. The keyword rate is generous
and the embedding rate is set for interactive use, not for defending a production
service. Rates are named settings so a demo can raise them.

**A slow-search threshold that is too low floods the log** → It is a named setting with a
default chosen to be quiet on the measured corpus, where a hybrid request is well under
a second.

**Pagination interacts with hybrid degradation** → When hybrid degrades to keyword-only,
the paginated envelope must still carry `degraded` and `warning` on *every* page, not
just the first. Covered by decision 4 and pinned by a test, because this is precisely the
kind of regression a paginator refactor introduces silently. The sharp edge is the
*empty* degraded response: an outage that also leaves the keyword ranking with no hits
must not be answered by a short-circuit envelope built beside the paginator, or the
outage reads as an honest miss. Every response therefore goes through the paginator,
empty ones included.
