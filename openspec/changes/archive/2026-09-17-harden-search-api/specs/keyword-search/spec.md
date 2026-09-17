## MODIFIED Requirements

### Requirement: The response is an object, not a bare list

The response body SHALL be an object carrying the results under a named key alongside
a count, rather than a bare array. This shape was chosen so that pagination could be
added without breaking callers, and it now carries that pagination.

The reported count SHALL be the number of results retrievable for the query within the
configured retrieval bound, not the number carried in the body. A response therefore
reports a count larger than its own result list on every page but the last. The body
SHALL also carry indicators for the next and previous pages.

#### Scenario: The body is an object
- **WHEN** any successful search response is inspected
- **THEN** the body is a JSON object rather than an array

#### Scenario: The count reports what is retrievable, not what is carried
- **WHEN** a query retrieves more results than fit on one page
- **THEN** the reported count is the total retrievable within the bound
- **AND** the result list carries at most one page of them

#### Scenario: The count matches the results on a single page
- **WHEN** a query retrieves fewer results than the page size
- **THEN** the reported count equals the number of results carried

#### Scenario: An empty result set keeps the same shape
- **WHEN** a query matches nothing
- **THEN** the body is still an object carrying a count of zero and an empty list
- **AND** it indicates that no next or previous page exists

### Requirement: The number of results is capped by a named setting

The number of results retrieved SHALL be bounded, and the bound SHALL be a named
project setting rather than a number written into the query, so that it can be changed
without editing code. The cap SHALL bound the work the database performs, not merely
trim the response after the fact.

The response SHALL be bounded separately, by a page size that is its own named setting.
The retrieval bound governs how deep the ranking reaches; the page size governs how much
of that reach any one response carries.

#### Scenario: A broad query is capped
- **WHEN** a query matches more papers than the configured retrieval bound
- **THEN** the number of results retrievable across all pages equals that bound

#### Scenario: A response is capped by the page size
- **WHEN** a query retrieves more results than the configured page size
- **THEN** the number of results carried in one response equals the page size

#### Scenario: The cap is configurable
- **WHEN** the configured retrieval bound is changed
- **THEN** the number of results retrievable changes accordingly, with no code change

#### Scenario: The cap is not a literal in the query
- **WHEN** the search implementation is inspected
- **THEN** the bound is read from the named setting

#### Scenario: A narrow query is not padded
- **WHEN** a query matches fewer papers than the bound
- **THEN** only the matching papers are returned
