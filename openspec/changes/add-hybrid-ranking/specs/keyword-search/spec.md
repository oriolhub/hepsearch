## MODIFIED Requirements

### Requirement: The corpus is searchable by keyword over HTTP

The system SHALL expose a read-only endpoint at `/api/search/` that accepts a query
string in a `q` parameter and returns matching papers as JSON. The endpoint SHALL be
public and SHALL require no authentication, because the corpus is public literature.

The endpoint SHALL accept an optional `mode` parameter naming the ranking strategy. Its
absence SHALL select hybrid ranking, because a caller who expresses no preference is
best served by the ranking that handles both exact terms and paraphrase. Keyword ranking
SHALL remain reachable by naming it explicitly, and its own behaviour — the papers it
selects, their ordering, and how it scores them — SHALL be unchanged by this. A `mode`
the system does not recognise SHALL be refused with a 400 status and SHALL NOT produce a
server error, and SHALL NOT silently fall back to a different ranking.

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

#### Scenario: An omitted mode ranks by hybrid
- **WHEN** a caller requests the search endpoint with no `mode` parameter
- **THEN** the papers returned and their order are those hybrid ranking produces
- **AND** the response names hybrid as the mode that produced them

#### Scenario: Keyword ranking is still reachable by name
- **WHEN** a caller requests the search endpoint naming keyword ranking explicitly
- **THEN** the papers returned, their order and their scores are those keyword ranking
  produced before hybrid ranking existed

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
