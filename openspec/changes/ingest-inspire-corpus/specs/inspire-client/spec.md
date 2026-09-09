## MODIFIED Requirements

### Requirement: A record without a usable abstract is skipped

Normalization SHALL decline to produce a paper for any record that has no abstract, an
empty abstract list, or only empty abstract text, and SHALL skip such records rather
than raising. A paper with no abstract cannot be embedded, would pollute search
results, and is rejected by the database.

Record iteration SHALL make that verdict visible to its caller rather than silently
dropping the record: it SHALL produce one result per fetched record, either a paper or
an explicit indication that the record was unusable, so that a caller can count how
many records were skipped and report it. The rule deciding usability SHALL remain in
normalization; only the visibility of its outcome moves to the caller. Consequently the
obligation not to write an unusable record SHALL rest with the caller, which SHALL
filter these results before any database write.

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

#### Scenario: Every paper the client produces has an abstract
- **WHEN** the client iterates records for a query
- **THEN** every paper among the results has a non-empty abstract, so that a caller
  writing only the papers cannot be rejected by the database's abstract constraint

#### Scenario: An unusable record is visible to the caller
- **WHEN** the client iterates records and one of them has no usable abstract
- **THEN** the caller receives a result for that record indicating it produced no paper
- **AND** the caller can therefore count it as skipped

#### Scenario: Every fetched record produces exactly one result
- **WHEN** the client iterates a page of records of which some are unusable
- **THEN** the caller receives one result per fetched record, papers and skips together
