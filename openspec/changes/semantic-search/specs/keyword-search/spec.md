## MODIFIED Requirements

### Requirement: The corpus is searchable by keyword over HTTP

The system SHALL expose a read-only endpoint at `/api/search/` that accepts a query
string in a `q` parameter and returns matching papers as JSON. The endpoint SHALL be
public and SHALL require no authentication, because the corpus is public literature.

The endpoint SHALL accept an optional `mode` parameter naming the ranking strategy. Its
absence SHALL select keyword ranking, so that existing callers observe no change in the
papers selected, their ordering, or how they are scored. A `mode` the system does not
recognise SHALL be refused with a 400 status and SHALL NOT produce a server error, and
SHALL NOT silently fall back to a different ranking.

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

#### Scenario: An omitted mode ranks by keyword
- **WHEN** a caller requests the search endpoint with no `mode` parameter
- **THEN** the papers returned and their order are those keyword ranking produces

#### Scenario: An unknown mode is refused
- **WHEN** a caller requests the search endpoint with a `mode` the system does not
  recognise
- **THEN** the response status is 400
- **AND** no server error occurs

#### Scenario: A refused mode does not fall back
- **WHEN** a request is refused for an unrecognised mode
- **THEN** no papers are present in the response

#### Scenario: A refused mode is not reflected back as markup
- **WHEN** the search page is requested with an unrecognised `mode` whose value
  contains HTML
- **THEN** the response status is 400
- **AND** the submitted value does not appear in the body as executable markup

### Requirement: Each result carries what a reader needs to judge it

Every result SHALL carry the paper's identifier, its title, a bounded sample of its
authors, the total number of authors, its publication date, an excerpt of its abstract,
a link to the paper's record on INSPIRE, and the score by which it was ranked. The link
SHALL be derived from the paper's INSPIRE identifier rather than stored separately.

The score SHALL be present in every ranking mode, so that a caller reads one response
shape regardless of how the results were ranked. Its scale SHALL be that of the ranking
mode which produced it and SHALL NOT be assumed comparable across modes; the mode is
reported alongside the results.

The author list SHALL be bounded to a small leading sample rather than reproducing every
author, because collaboration papers routinely carry thousands of author names. The
total SHALL be reported alongside the sample. The size of a response SHALL therefore be
bounded by the result cap and author sample, and SHALL NOT depend on the number of
authors in matched papers.

The excerpt SHALL be bounded in length and SHALL indicate when it has been cut short,
so that a caller can tell an abbreviated abstract from a complete one.

#### Scenario: A result carries the expected fields
- **WHEN** a search returns a paper
- **THEN** the result carries its identifier, title, author sample, author total,
  publication date, abstract excerpt, INSPIRE link and score

#### Scenario: Keyword results carry a score
- **WHEN** a keyword search returns papers
- **THEN** each result carries the relevance score by which it was ranked
- **AND** the scores descend with the result order

#### Scenario: Semantic results carry a similarity score
- **WHEN** a semantic search returns papers
- **THEN** each result carries its similarity to the query, derived from the cosine
  distance
- **AND** a similarity below zero is reported as it is rather than raised to zero

#### Scenario: The response names the mode that produced it
- **WHEN** any successful search response is inspected
- **THEN** it reports which ranking mode produced the results

#### Scenario: A collaboration paper's authors are sampled, not reproduced
- **WHEN** a returned paper has thousands of authors
- **THEN** the result carries only the leading sample of them
- **AND** the reported author total is the paper's true number of authors

#### Scenario: A short author list is carried whole
- **WHEN** a returned paper has fewer authors than the sample bound
- **THEN** the result carries all of them
- **AND** the reported author total equals that number

#### Scenario: A paper with no authors reports none
- **WHEN** a returned paper has no authors
- **THEN** the result carries an empty author list
- **AND** the reported author total is zero

#### Scenario: Response size does not depend on author counts
- **WHEN** one query matches papers with thousands of authors and another matches papers
  with a handful
- **THEN** neither response is materially larger than the other on account of authors

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
