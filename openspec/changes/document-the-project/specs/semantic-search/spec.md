## ADDED Requirements

### Requirement: A semantic search returns at most what the vector index will scan

A semantic ranking SHALL return no more papers than the approximate-nearest-neighbour
index returns for a single scan, even when the caller requests a larger bound, and the
system SHALL NOT raise the index's scan width per request to compensate.

The configured result bound exceeds that scan width. A semantic-only search therefore
retrieves fewer papers than a keyword search for the same query, and any surface that
reports how many results were retrieved SHALL be understood to report a smaller figure
in semantic mode. That difference SHALL NOT be reported, logged or handled as a fault,
and SHALL NOT be corrected by widening the scan per request.

This is stated here because `hybrid-search` specifies the bound only for the pool it
fuses. The same ceiling applies to a semantic search that is never fused, where it is
visible to a reader rather than only to the ranker.

#### Scenario: A request for more rows than the index scans is not satisfied in full
- **WHEN** a semantic ranking is asked for more papers than the index will return in a
  single scan
- **THEN** it returns at most the number the index scans
- **AND** no error is raised

#### Scenario: A smaller semantic total is not a fault
- **WHEN** the same query is run in keyword mode and in semantic mode
- **THEN** the semantic mode may report fewer retrieved results
- **AND** the difference is not presented as an error, a degradation or a warning
