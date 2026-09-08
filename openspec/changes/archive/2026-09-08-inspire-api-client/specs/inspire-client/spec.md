## ADDED Requirements

### Requirement: Records are fetched from the INSPIRE literature API

The system SHALL provide a client in `apps/ingestion` that retrieves literature
records from the INSPIRE-HEP API for a caller-supplied query. The client SHALL live
outside `apps/search` and SHALL NOT import from it.

#### Scenario: A query returns normalized records
- **WHEN** the client is asked for records matching a query with a limit of 10
- **THEN** it returns at most 10 usable records drawn from the API's results

#### Scenario: The ingestion app does not depend on the search app
- **WHEN** the modules in `apps/ingestion` are inspected
- **THEN** none of them imports `apps.search`

### Requirement: Requests are trimmed to the fields the domain needs

Every request SHALL send an explicit field selection covering only the data a `Paper`
stores. The author field SHALL be requested by its `full_name` sub-path rather than in
full, because a full author record carries identifiers, affiliations and internal
metadata that are discarded, and collaboration papers carry thousands of authors.

#### Scenario: The field selection is always sent
- **WHEN** any request is made to the API
- **THEN** it carries a field selection parameter
- **AND** that selection includes the INSPIRE id, title, abstracts, author names,
  arXiv eprints, DOIs, publication info, earliest date and citation count

#### Scenario: Author data is requested by sub-path
- **WHEN** the field selection is inspected
- **THEN** it requests the author name sub-path, not the whole author record

#### Scenario: Author names survive the trimmed request
- **WHEN** a record with many authors is fetched and normalized
- **THEN** every author's name is present on the resulting paper

### Requirement: Requests identify this project and are throttled

Every request SHALL carry a descriptive `User-Agent` identifying this project. The
client SHALL pause between successive requests, and the pause SHALL be configurable so
that tests can disable it.

#### Scenario: Every request is attributable
- **WHEN** any request is made to the API
- **THEN** it carries a `User-Agent` header naming this project

#### Scenario: Successive requests are spaced out
- **WHEN** the client makes more than one request during a single run
- **THEN** it waits the configured delay between them

#### Scenario: The delay is configurable
- **WHEN** the client is configured with a zero delay
- **THEN** it makes its requests without waiting

### Requirement: Page size is bounded by the API's maximum

The API rejects a page size above 1000. The client SHALL clamp any requested page size
to that maximum so that an over-large request can never produce a rejected response.
The default page size SHALL be smaller than the maximum, because a maximum-size page of
collaboration papers is a very large response to hold in memory at once.

#### Scenario: An over-large page size is clamped
- **WHEN** the client is asked to use a page size above 1000
- **THEN** the request is sent with a page size of 1000
- **AND** the API does not reject it

#### Scenario: The default page size is moderate
- **WHEN** the client is used without specifying a page size
- **THEN** it requests substantially fewer than 1000 records per page

### Requirement: Pagination continues until the requested number of usable records

The limit given to the client SHALL count the records it yields, not the records it
fetches. The client SHALL keep requesting further pages until that many usable records
have been produced, so that a caller asking for 5,000 papers receives approximately
5,000 papers rather than 5,000 minus those skipped.

#### Scenario: Skipped records do not reduce the yield
- **WHEN** the client is asked for 10 records and some fetched records are unusable
- **THEN** it continues fetching until 10 usable records have been produced

#### Scenario: Pagination stops once the limit is met
- **WHEN** the requested number of usable records has been produced
- **THEN** no further request is made

#### Scenario: A corpus smaller than the limit ends cleanly
- **WHEN** the query matches fewer records than the limit
- **THEN** the client yields every usable record and stops without error

### Requirement: The API's deep-pagination ceiling is handled, not hit

The API refuses to return results beyond an offset of 10,000 records. The client SHALL
detect that the next page would cross that boundary and stop **before** issuing the
request, rather than allowing the API to reject it. It SHALL record a warning through
the logging system so that the caller can report the shortfall, and SHALL NOT write to
standard output.

#### Scenario: The ceiling stops pagination without an error
- **WHEN** the requested limit cannot be satisfied within the reachable window
- **THEN** the client stops and returns the records it gathered
- **AND** it does not raise

#### Scenario: The shortfall is recorded
- **WHEN** the client stops because of the ceiling
- **THEN** it emits a warning through the logging system

#### Scenario: The rejected request is never made
- **WHEN** the client stops because of the ceiling
- **THEN** no request is issued for a page beyond the reachable window

#### Scenario: The client does not write to standard output
- **WHEN** the client runs for any reason
- **THEN** it prints nothing to standard output

### Requirement: Transient failures are retried, permanent ones are not

The client SHALL retry timeouts, connection failures, server errors and rate-limit
responses a bounded number of times before giving up. It SHALL NOT retry other client
errors, which will not succeed on repetition. When a rate-limit response specifies how
long to wait, the client SHALL honour that; otherwise it SHALL back off progressively.
After exhausting its attempts the client SHALL raise an error that identifies what
failed.

#### Scenario: A server error is retried and then succeeds
- **WHEN** a request fails with a server error and the retry succeeds
- **THEN** the client returns the successful response
- **AND** the caller observes no error

#### Scenario: A timeout is retried
- **WHEN** a request times out and a later attempt succeeds
- **THEN** the client returns the successful response

#### Scenario: A rate-limit response is honoured
- **WHEN** the API responds that the rate limit is exceeded and states a wait time
- **THEN** the client waits at least that long before retrying

#### Scenario: Backoff grows between attempts
- **WHEN** repeated attempts fail without a stated wait time
- **THEN** each successive wait is longer than the previous one

#### Scenario: A malformed request is not retried
- **WHEN** a request fails with a client error that is not a rate limit
- **THEN** the client does not retry
- **AND** it raises immediately

#### Scenario: Exhausted retries raise a clear error
- **WHEN** every permitted attempt fails
- **THEN** the client raises an error identifying the request and the failure

### Requirement: A record without a usable abstract is skipped

Normalization SHALL decline to produce a paper for any record that has no abstract, an
empty abstract list, or only empty abstract text, and SHALL skip such records rather
than raising. A paper with no abstract cannot be embedded, would pollute search
results, and is rejected by the database.

#### Scenario: A record with no abstract field is skipped
- **WHEN** a record without any abstracts is normalized
- **THEN** no paper is produced
- **AND** no error is raised

#### Scenario: A record with an empty abstract list is skipped
- **WHEN** a record whose abstract list is empty is normalized
- **THEN** no paper is produced

#### Scenario: A record whose only abstract text is empty is skipped
- **WHEN** a record's sole abstract entry has empty text
- **THEN** no paper is produced

#### Scenario: Skipped records never reach the database layer
- **WHEN** the client yields records for a query
- **THEN** every yielded paper has a non-empty abstract, so that a bulk write cannot be
  rejected by the database's abstract constraint

### Requirement: Abstract selection is deterministic and documented

The client SHALL apply a single documented rule when a record carries more than one
abstract — a third of them do — and SHALL choose the same one every time the same record
is processed, so that re-ingesting a paper does not needlessly mark it as changed. The
rule SHALL prefer the author-supplied arXiv abstract when one is present, and SHALL fall
back to the first entry that has text. Source comparison SHALL be case-insensitive.

#### Scenario: The arXiv abstract wins when present
- **WHEN** a record carries both a publisher abstract and an arXiv-sourced abstract
- **THEN** the arXiv one is selected, regardless of their order in the record

#### Scenario: Source matching ignores letter case
- **WHEN** a record's arXiv abstract declares its source with different capitalisation
- **THEN** it is still recognised and selected

#### Scenario: Without an arXiv abstract the first usable one wins
- **WHEN** a record carries several abstracts and none is arXiv-sourced
- **THEN** the first entry with non-empty text is selected

#### Scenario: Entries without a source are still usable
- **WHEN** a record's abstracts include entries that declare no source at all
- **THEN** normalization succeeds and selects an abstract without raising

#### Scenario: Selection is repeatable
- **WHEN** the same record is normalized twice
- **THEN** the same abstract is selected both times

#### Scenario: An empty preferred entry does not win
- **WHEN** a record's arXiv-sourced entry has empty text and another entry has text
- **THEN** the entry with text is selected

### Requirement: Absent fields never crash normalization

Every field except the INSPIRE id, the title and the abstract SHALL be treated as
possibly absent — not merely empty, but with the key missing from the record entirely.
Normalization SHALL never index into a list that may not exist.

#### Scenario: A preprint with almost nothing is normalized
- **WHEN** a record with no DOIs, no publication info and no arXiv eprints is normalized
- **THEN** a paper is produced
- **AND** its DOI, journal and arXiv id are empty strings
- **AND** its categories are an empty list

#### Scenario: A record with no authors is normalized
- **WHEN** a record with no author list is normalized
- **THEN** a paper is produced with an empty author list

#### Scenario: A record with no citation count is normalized
- **WHEN** a record without a citation count is normalized
- **THEN** a paper is produced whose citation count is unset, rather than zero

#### Scenario: Categories are reached through a guarded path
- **WHEN** a record has no arXiv eprints
- **THEN** normalization produces empty categories without attempting to read the
  categories of a non-existent eprint

#### Scenario: Publication info without a journal title is tolerated
- **WHEN** a record has publication info entries but none names a journal
- **THEN** a paper is produced with an empty journal

### Requirement: When several values exist, selection is defined

The client SHALL apply a stated rule rather than assuming a single value, and SHALL
store what the source supplied rather than reformatting it. Records commonly carry
several DOIs and several publication-info entries.

#### Scenario: The first DOI is stored
- **WHEN** a record carries more than one DOI
- **THEN** the first is stored

#### Scenario: The first publication entry naming a journal is used
- **WHEN** a record carries several publication-info entries and only a later one names
  a journal
- **THEN** that journal title is stored

#### Scenario: The arXiv identifier is stored as supplied
- **WHEN** a record carries a modern-style arXiv identifier
- **THEN** it is stored exactly as supplied, without an added prefix

#### Scenario: Legacy arXiv identifiers are stored as supplied
- **WHEN** a record carries a legacy-style arXiv identifier containing a slash
- **THEN** it is stored exactly as supplied

#### Scenario: The earliest date is stored as supplied
- **WHEN** a record's earliest date is a partial date such as a year or a year and month
- **THEN** it is stored exactly as supplied, with no day or month invented

### Requirement: Normalized records are ready for the database layer

Normalization SHALL produce objects that the ingestion command can write without
further mapping, so that field names are validated by the domain model rather than
duplicated in a second schema. Producing them SHALL NOT require a database.

#### Scenario: A normalized record carries the domain fields
- **WHEN** a record is normalized
- **THEN** the result exposes the INSPIRE id, title, abstract, authors, arXiv id, DOI,
  journal, earliest date, citation count and categories

#### Scenario: The INSPIRE id comes from the stable control number
- **WHEN** a record is normalized
- **THEN** its INSPIRE id is the record's control number

#### Scenario: Normalization needs no database
- **WHEN** normalization is exercised
- **THEN** it completes without any database connection

### Requirement: The client is fully testable offline

No test for this capability SHALL perform a network request. Tests SHALL exercise
normalization against a committed fixture of real INSPIRE responses, and SHALL exercise
pagination and retry by supplying canned responses rather than by contacting the API.

#### Scenario: The test suite makes no network request
- **WHEN** the project's tests are run
- **THEN** no request is made to the INSPIRE API

#### Scenario: The fixture contains the cases that break naive code
- **WHEN** the committed fixture is inspected
- **THEN** it contains a record with no abstract
- **AND** a record with neither a DOI nor publication info
- **AND** a record carrying several abstracts from different sources
- **AND** a record with no arXiv eprints at all
- **AND** a record with a legacy-style arXiv identifier
- **AND** a record carrying several DOIs

#### Scenario: The fixture is real data
- **WHEN** the committed fixture is inspected
- **THEN** it holds responses captured from the live API, not hand-invented payloads

#### Scenario: Pagination is tested without a network
- **WHEN** pagination behaviour is tested
- **THEN** the fetching step is supplied by the test rather than contacting the API
