# api-hardening Specification

## Purpose

Define bounded, predictable, and observable HTTP behavior for the public search API and
HTML search page.

## Requirements


### Requirement: Results are paginated over a bounded retrieval depth

The system SHALL return search results in pages, and SHALL bound the total it will
retrieve for any query by a named setting distinct from the page size. Both SHALL be
configurable without editing code.

The bound exists because retrieval is bounded in fact: an approximate-nearest-neighbour
scan returns a fixed number of candidates regardless of how many papers match, so a
caller paging through semantic results reaches the end of what the index examined rather
than the end of the corpus. Advertising pagination over the whole corpus would be a
claim the retrieval layer cannot honour.

#### Scenario: A broad query is served in pages
- **WHEN** a query matches more papers than the page size
- **THEN** the response carries at most one page of results
- **AND** it indicates that a further page exists

#### Scenario: Retrieval depth bounds the pages available
- **WHEN** a query matches more papers than the configured retrieval depth
- **THEN** no page beyond the depth is reachable
- **AND** the number of results reported is the depth rather than the number of matching
  papers

#### Scenario: The depth and the page size are separate settings
- **WHEN** the configuration is inspected
- **THEN** the retrieval depth and the page size are distinct named settings
- **AND** the depth exceeds the page size

#### Scenario: A narrow query is not padded
- **WHEN** a query matches fewer papers than the page size
- **THEN** the single page carries only the matching papers
- **AND** it indicates that no further page exists

#### Scenario: The ceiling is documented per ranking
- **WHEN** the retrieval bound is documented
- **THEN** it records that each ranking reaches a different depth in practice, and that
  the semantic ranking's depth is set by the vector index's scan width rather than by
  the query

### Requirement: Paging costs no additional query and loads no page twice

The system SHALL paginate the rows a ranking already returned, and SHALL NOT issue a
separate query to count matches or to fetch a later page. The cost of serving the last
page SHALL equal the cost of serving the first.

Neither ranking SHALL load the embedding or the stored search vector columns, which
remains true under pagination.

#### Scenario: No counting query is issued
- **WHEN** a paginated search is performed
- **THEN** the number of database queries is the number of rankings that ran, plus the
  cached corpus-health count
- **AND** no query is issued solely to count matching papers

#### Scenario: A later page costs no more than the first
- **WHEN** the last reachable page of a query is requested
- **THEN** the number of database queries equals the number issued for the first page

#### Scenario: Large columns stay unloaded under pagination
- **WHEN** the queries issued for a paginated search are inspected
- **THEN** neither the embedding column nor the stored search vector column is selected

### Requirement: The paginated envelope preserves the mode and any degradation

The paginated response SHALL continue to carry the ranking mode that produced it, and
SHALL carry any degradation report on every page rather than only the first, because a
reader who arrives on a later page is owed the same warning as one who arrives on the
first.

#### Scenario: Every page names its mode
- **WHEN** any page of any successful search is inspected
- **THEN** it reports which ranking mode produced the results

#### Scenario: A degraded hybrid search warns on every page
- **WHEN** a hybrid search has degraded to keyword-only and a page beyond the first is
  requested
- **THEN** that page reports that the results were degraded and why

#### Scenario: A degraded search with no surviving results still warns
- **WHEN** a hybrid search has degraded to keyword-only and the keyword ranking matched
  nothing
- **THEN** the response reports that the results were degraded and why
- **AND** it is distinguishable from a query that simply matched nothing

#### Scenario: Pagination links are present
- **WHEN** a paginated response is inspected
- **THEN** it carries a link or indicator for the next and previous pages, absent where
  no such page exists

### Requirement: An unusable page parameter is refused consistently

Any `page` value the system cannot serve SHALL be refused with a 404 status, whether it
is malformed or beyond the last reachable page, so that a caller reads one outcome for
one class of mistake. A refused page SHALL NOT return a server error and SHALL NOT
silently serve a different page.

#### Scenario: A page beyond the end is refused
- **WHEN** a page beyond the last reachable page is requested
- **THEN** the response status is 404
- **AND** no server error occurs

#### Scenario: A malformed page is refused the same way
- **WHEN** a `page` value that is not a positive integer is requested
- **THEN** the response status is 404
- **AND** the outcome is the same as for a page beyond the end

#### Scenario: A refused page does not fall back
- **WHEN** a page request is refused
- **THEN** no results are present in the response

### Requirement: Anonymous requests are throttled by what the ranking costs

The system SHALL throttle anonymous requests at documented rates, and SHALL apply a
stricter rate to rankings that embed the query than to the keyword ranking, which embeds
nothing and issues a single indexed query.

Semantic and hybrid ranking SHALL share one rate. Hybrid costs more than semantic, not
less, so a scheme that throttled hybrid more leniently than semantic would be inverted
with respect to the work each performs. The rates SHALL be named settings.

Exceeding a rate SHALL be reported with a 429 status and a header telling the caller how
long to wait.

#### Scenario: Keyword ranking is throttled generously
- **WHEN** repeated keyword searches are performed from one client
- **THEN** they are permitted up to the documented keyword rate

#### Scenario: An embedding ranking is throttled more strictly
- **WHEN** the configured rates are inspected
- **THEN** the rate applied to semantic and hybrid ranking is stricter than the rate
  applied to keyword ranking

#### Scenario: Semantic and hybrid share one rate
- **WHEN** the configured rates are inspected
- **THEN** semantic and hybrid ranking are governed by the same rate

#### Scenario: Exceeding the rate is refused with a wait
- **WHEN** a client exceeds its rate
- **THEN** the response status is 429
- **AND** the response carries a header stating how long to wait before retrying

#### Scenario: A rejected mode is not throttled into the wrong error
- **WHEN** a request naming an unrecognised mode is made
- **THEN** the response status is 400 rather than 429

### Requirement: The search page is throttled on the same terms as the API

The search page SHALL be throttled by the same rates as the API, because it performs the
same ranking and the same query embedding. A throttle covering only the API would leave
the identical work reachable without limit through the page.

A page request that carries no query SHALL NOT be charged against the rate, because it
ranks nothing and embeds nothing. Charging it would let ordinary browsing of the form
exhaust the budget and refuse a reader who had not yet searched.

When a reader exceeds the rate, the page SHALL say so plainly and SHALL carry the same
wait header as the API.

#### Scenario: Page requests count against the rate
- **WHEN** repeated searches are performed through the page
- **THEN** they are limited by the same rate that governs the API for that ranking mode

#### Scenario: The page reports being throttled
- **WHEN** a reader exceeds the rate on the page
- **THEN** the response status is 429
- **AND** the body states that too many requests were made
- **AND** the response carries the wait header

#### Scenario: No ranking runs for a throttled page request
- **WHEN** a page request is refused for exceeding the rate
- **THEN** no query is embedded and no ranking is performed

#### Scenario: Loading the empty form is not charged against the rate
- **WHEN** the page is loaded repeatedly without a query
- **THEN** every load succeeds, however many are made

### Requirement: An overlong query is refused rather than silently truncated

The system SHALL refuse a query longer than a named bound with a 400 status, because the
embedding model reads only a fixed number of tokens and silently discards the remainder.
Returning results for the first part of a long query while presenting them as results for
the whole is a claim the system cannot support.

The bound SHALL be a named setting, and SHALL be small enough that accepted input fits
within what the configured model actually reads.

#### Scenario: An overlong query is refused
- **WHEN** a query longer than the configured bound is submitted
- **THEN** the response status is 400
- **AND** the message names the length limit

#### Scenario: An overlong query is never embedded
- **WHEN** an overlong query is refused
- **THEN** no embedding was computed for it

#### Scenario: A query at the bound is accepted
- **WHEN** a query exactly at the configured bound is submitted
- **THEN** the request succeeds

### Requirement: Every rejected parameter names what was wrong

A request refused for a bad parameter SHALL carry a message identifying the offending
parameter, so that a caller can correct it without guessing. This SHALL hold for a
missing or empty query, an unrecognised mode, an overlong query, and an out-of-range page
size.

#### Scenario: A missing query names the query parameter
- **WHEN** a request without a query is refused
- **THEN** the message names the query parameter

#### Scenario: An unknown mode names the mode parameter
- **WHEN** a request with an unrecognised mode is refused
- **THEN** the message names the mode parameter and the value that was rejected

#### Scenario: An out-of-range page size is refused
- **WHEN** a page size beyond the configured maximum is requested
- **THEN** the response is refused or the maximum is applied, consistently and without a
  server error

### Requirement: Errors reveal nothing internal when debugging is off

No error response SHALL disclose a stack trace, a file path, a database identifier, a
setting value or any other internal detail when the application is not in debug mode.
This SHALL hold for the page as well as the API.

#### Scenario: A refused request stays opaque
- **WHEN** any request is refused while debugging is off
- **THEN** the body carries no stack trace and no internal path

#### Scenario: An unexpected failure stays opaque
- **WHEN** an unexpected error occurs while debugging is off
- **THEN** the response carries no stack trace and no internal detail

### Requirement: Operational events reach a configured log

The system SHALL configure logging so that the conditions it already reports — a stale
embedding corpus, an embedding provider that could not be loaded, a degraded hybrid
search — are actually emitted rather than relying on the interpreter's fallback handler.

A search taking longer than a named threshold SHALL be recorded with its elapsed time,
its mode, and its query. Query text SHALL be escaped before it is written, because it is
unvalidated public input and a raw newline in a log record forges a second record.

#### Scenario: Logging is configured
- **WHEN** the project's settings are inspected
- **THEN** a logging configuration is present that emits the search application's
  warnings

#### Scenario: A slow search is recorded
- **WHEN** a search takes longer than the configured threshold
- **THEN** a record is written carrying the elapsed time, the ranking mode and the query

#### Scenario: A fast search is not recorded
- **WHEN** a search completes within the threshold
- **THEN** no slow-search record is written

#### Scenario: A query cannot forge a log record
- **WHEN** a query containing newline or control characters is logged
- **THEN** those characters are escaped rather than written literally

### Requirement: The page offers navigation that preserves the search

The search page SHALL let a reader move between pages of results, and SHALL carry the
query and the chosen ranking mode across that movement, so that paging does not silently
reset the search.

#### Scenario: Navigation preserves the query and mode
- **WHEN** a reader moves to the next page of results
- **THEN** the same query and the same ranking mode are still in effect

#### Scenario: Navigation is absent when there is one page
- **WHEN** the results fit on a single page
- **THEN** no page navigation is offered

#### Scenario: A page number is not reflected back as markup
- **WHEN** the page is requested with a `page` value containing HTML
- **THEN** the submitted value does not appear in the body as executable markup

### Requirement: The hardening is fully testable offline

No test of this capability SHALL perform a network request or load a real embedding
model. Tests SHALL cover each refusal — missing query, unknown mode, overlong query,
unusable page — and SHALL establish that exceeding a rate yields a 429 on both the API
and the page.

#### Scenario: The tests load no model and make no network request
- **WHEN** the project's tests are run
- **THEN** the hardening tests contact no external service and load no embedding model

#### Scenario: Each refusal is covered
- **WHEN** the hardening tests are inspected
- **THEN** they cover a missing query, an unrecognised mode, an overlong query and an
  unusable page parameter

#### Scenario: Throttling is covered on both surfaces
- **WHEN** the hardening tests are inspected
- **THEN** they establish that exceeding a rate returns 429 from the API and from the
  page

#### Scenario: Opaque errors are covered
- **WHEN** the hardening tests are inspected
- **THEN** at least one asserts that no internal detail appears in an error response
  while debugging is off
