## ADDED Requirements

### Requirement: The corpus is searchable by keyword over HTTP

The system SHALL expose a read-only endpoint at `/api/search/` that accepts a query
string in a `q` parameter and returns matching papers as JSON. The endpoint SHALL be
public and SHALL require no authentication, because the corpus is public literature.

#### Scenario: A query returns matching papers
- **WHEN** a caller requests the search endpoint with a query matching stored papers
- **THEN** the response status is 200
- **AND** the body is JSON containing those papers

#### Scenario: The endpoint needs no credentials
- **WHEN** a caller requests the search endpoint without authenticating
- **THEN** the request succeeds

#### Scenario: The search app does not depend on ingestion
- **WHEN** the modules of the search app are inspected
- **THEN** none of them imports the ingestion app

### Requirement: Results are ranked by relevance, with titles outranking abstracts

Results SHALL be ordered by a relevance score rather than by insertion order, date or
identifier. A paper matching in its title SHALL rank above an otherwise comparable
paper matching only in its abstract, because a title states what a paper is about
while an abstract may merely mention a term.

Relevance SHALL be computed from the stored search vector rather than by rebuilding a
vector for each candidate row, so that ranking and indexing cannot disagree.

#### Scenario: Better matches come first
- **WHEN** a query matches several papers to differing degrees
- **THEN** they appear in descending order of relevance

#### Scenario: A title match outranks an abstract-only match
- **WHEN** one paper carries the queried term in its title and another carries it only
  in its abstract
- **THEN** the paper matching in its title is ranked higher

#### Scenario: Ranking reads the stored vector
- **WHEN** the ranking query is inspected
- **THEN** it scores against the stored search vector rather than recomputing one per
  row

#### Scenario: Ordering is stable for a repeated query
- **WHEN** the same query is issued twice against unchanged data
- **THEN** the same papers are returned in the same order

### Requirement: Any user input is safe to submit

Query text SHALL be parsed with a parser that cannot raise on unexpected input, so
that no combination of punctuation, quotation marks, operators or stray characters can
produce a server error. Query text SHALL NOT be interpolated into a raw query
expression.

The parser SHALL honour quoted phrases, term exclusion and alternation, so that a
caller can express an exact-phrase or negated search without additional syntax being
invented for this project.

#### Scenario: Punctuation does not raise
- **WHEN** a query containing punctuation such as quotes, colons, parentheses,
  ampersands or exclamation marks is submitted
- **THEN** the response status is 200
- **AND** no server error occurs

#### Scenario: Unbalanced quotes do not raise
- **WHEN** a query containing a single unmatched quotation mark is submitted
- **THEN** the request succeeds

#### Scenario: A quoted phrase is treated as a phrase
- **WHEN** a caller submits two words wrapped in quotation marks
- **THEN** papers containing that phrase are preferred over papers merely containing
  both words apart

#### Scenario: A term can be excluded
- **WHEN** a caller prefixes a term with a minus sign
- **THEN** papers matching that term are absent from the results

#### Scenario: Raw query text never reaches the database as an expression
- **WHEN** the search implementation is inspected
- **THEN** user text is passed as a parsed query value, not concatenated into a query
  expression

### Requirement: An absent or empty query is rejected, an unmatched one is not

A request that supplies no query SHALL be refused with a 400 status and a message
explaining what was expected. It SHALL NOT return the entire corpus and SHALL NOT
return a server error.

A request that supplies a real query which happens to match nothing SHALL succeed with
an empty result list, because asking a reasonable question and receiving no answer is
not an error.

#### Scenario: A missing query is refused
- **WHEN** the endpoint is requested with no `q` parameter
- **THEN** the response status is 400
- **AND** the body explains that a query is required

#### Scenario: An empty query is refused
- **WHEN** the endpoint is requested with an empty `q`
- **THEN** the response status is 400

#### Scenario: A whitespace-only query is refused
- **WHEN** the endpoint is requested with a `q` consisting only of spaces
- **THEN** the response status is 400

#### Scenario: A refused request does not return the corpus
- **WHEN** a request is refused for lack of a query
- **THEN** no papers are present in the response

#### Scenario: A query matching nothing succeeds
- **WHEN** a query that matches no stored paper is submitted
- **THEN** the response status is 200
- **AND** the result list is empty

#### Scenario: A query of only common words matches nothing without failing
- **WHEN** a query consisting solely of words the parser discards is submitted
- **THEN** the response status is 200
- **AND** the result list is empty

### Requirement: Each result carries what a reader needs to judge it

Every result SHALL carry the paper's identifier, its title, its authors, its
publication date, an excerpt of its abstract, and a link to the paper's record on
INSPIRE. The link SHALL be derived from the paper's INSPIRE identifier rather than
stored separately.

The excerpt SHALL be bounded in length and SHALL indicate when it has been cut short,
so that a caller can tell an abbreviated abstract from a complete one.

#### Scenario: A result carries the expected fields
- **WHEN** a search returns a paper
- **THEN** the result carries its identifier, title, authors, publication date,
  abstract excerpt and INSPIRE link

#### Scenario: The INSPIRE link addresses the paper's record
- **WHEN** a result's link is inspected
- **THEN** it addresses the INSPIRE literature record for that paper's INSPIRE
  identifier

#### Scenario: A long abstract is excerpted
- **WHEN** a returned paper's abstract is longer than the excerpt bound
- **THEN** the excerpt is no longer than that bound
- **AND** it is marked as continuing

#### Scenario: A short abstract is returned whole
- **WHEN** a returned paper's abstract is shorter than the excerpt bound
- **THEN** the excerpt is the entire abstract
- **AND** it is not marked as continuing

#### Scenario: An excerpt does not cut a word in half
- **WHEN** an abstract is excerpted
- **THEN** the excerpt ends at a word boundary

### Requirement: Partial publication dates are presented as dates

The corpus stores publication dates at differing precision: some papers state a full
date, some only a year and month, and some only a year. The API SHALL present a date
for every paper regardless of the precision stored, filling an unknown month or day
with the first of the period, so that a caller receives one consistent type rather
than three shapes of string.

#### Scenario: A full date is presented unchanged
- **WHEN** a paper stores a complete date
- **THEN** the result reports that date

#### Scenario: A year-and-month date is completed
- **WHEN** a paper stores only a year and a month
- **THEN** the result reports the first day of that month

#### Scenario: A year-only date is completed
- **WHEN** a paper stores only a year
- **THEN** the result reports the first day of that year

#### Scenario: A missing date does not break the result
- **WHEN** a paper stores no date at all
- **THEN** the result reports no date
- **AND** the response is still returned successfully

### Requirement: The number of results is capped by a named setting

The number of results returned SHALL be bounded, and the bound SHALL be a named
project setting rather than a number written into the query, so that it can be changed
without editing code. The cap SHALL bound the work the database performs, not merely
trim the response after the fact.

#### Scenario: A broad query is capped
- **WHEN** a query matches more papers than the configured cap
- **THEN** the number of results returned equals the cap

#### Scenario: The cap is configurable
- **WHEN** the configured cap is changed
- **THEN** the number of results returned changes accordingly, with no code change

#### Scenario: The cap is not a literal in the query
- **WHEN** the search implementation is inspected
- **THEN** the bound is read from the named setting

#### Scenario: A narrow query is not padded
- **WHEN** a query matches fewer papers than the cap
- **THEN** only the matching papers are returned

### Requirement: The response is an object, not a bare list

The response body SHALL be an object carrying the results under a named key alongside
a count, rather than a bare array. This shape is chosen now so that pagination can be
added later without breaking callers.

#### Scenario: The body is an object
- **WHEN** any successful search response is inspected
- **THEN** the body is a JSON object rather than an array

#### Scenario: The count matches the results
- **WHEN** a successful search response is inspected
- **THEN** its reported count equals the number of results it carries

#### Scenario: An empty result set keeps the same shape
- **WHEN** a query matches nothing
- **THEN** the body is still an object carrying a count of zero and an empty list

### Requirement: Ranking is a function, callable without HTTP

The ranking SHALL be implemented as a callable that takes the query text and the
result bound and returns matching papers, without requiring a request, a response or
the HTTP layer. It SHALL return a lazily-evaluated query rather than a materialised
list, so that a later hybrid ranker can combine it with another ranking instead of
reimplementing it.

Presentation concerns — excerpting, date completion and link construction — SHALL NOT
live inside the ranking callable.

#### Scenario: Ranking is exercised directly
- **WHEN** the ranking callable is invoked with query text and a bound
- **THEN** it returns matching papers
- **AND** no request or response object was involved

#### Scenario: The result is composable
- **WHEN** the ranking callable returns
- **THEN** its result can be further filtered or ordered before being evaluated

#### Scenario: Ranking is free of presentation
- **WHEN** the ranking callable is inspected
- **THEN** it performs no excerpting, date completion or link construction

### Requirement: The capability is fully testable offline

No test of this capability SHALL perform a network request or contact any external
service. Tests SHALL build their own papers and SHALL cover a ranked match, a title
match outranking an abstract-only match, a missing query, a query matching nothing,
and a query heavy with punctuation.

#### Scenario: The tests make no network request
- **WHEN** the project's tests are run
- **THEN** the search tests contact no external service

#### Scenario: The required cases are covered
- **WHEN** the search tests are inspected
- **THEN** they cover a ranked match, a title match outranking an abstract-only match,
  a missing query, a query matching nothing, and a punctuation-heavy query

#### Scenario: Ranking is tested without the HTTP layer
- **WHEN** the ranking tests are inspected
- **THEN** at least one exercises the ranking callable directly rather than through a
  request