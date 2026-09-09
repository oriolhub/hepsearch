## ADDED Requirements

### Requirement: An operator can fill the corpus with one command

The system SHALL provide a management command in `apps/ingestion` that fetches INSPIRE
records for a query and stores them as papers. The command SHALL run synchronously to
completion without a task queue, message broker or background worker, because ingestion
is a batch job an operator runs rather than a request-path concern. The command SHALL
live outside `apps/search` and SHALL NOT import from it.

#### Scenario: A run lands papers in the database
- **WHEN** an operator runs the ingestion command with a query and a limit
- **THEN** papers matching that query are stored in the database
- **AND** the command exits successfully once it has finished

#### Scenario: The command completes without external infrastructure
- **WHEN** the command is run with only the database available
- **THEN** it completes without requiring a broker, worker or scheduler

#### Scenario: The ingestion command does not depend on the search app
- **WHEN** the command's module is inspected
- **THEN** it does not import `apps.search`

### Requirement: The corpus topic and size are parameters, not constants

The query SHALL be supplied on the command line and SHALL default to the project's
Higgs boson corpus, so that a different slice of INSPIRE can be ingested without
editing code. The limit SHALL count the papers landed, not the records fetched, so that
records dropped along the way do not shrink the resulting corpus.

#### Scenario: A caller-supplied query is used
- **WHEN** the command is run with a query other than the default
- **THEN** the records fetched are those matching the supplied query

#### Scenario: The default query needs no arguments
- **WHEN** the command is run without a query
- **THEN** it ingests the project's default corpus topic

#### Scenario: The topic is not hardcoded in the fetching logic
- **WHEN** the command's source is inspected
- **THEN** the default topic appears as a default value that a caller can override

#### Scenario: The limit counts landed papers
- **WHEN** the command is run with a limit and some fetched records are unusable
- **THEN** it continues fetching until the limit of usable papers is reached, rather
  than stopping short by the number skipped

### Requirement: Records without a usable abstract are skipped and counted

The command SHALL NOT store a record that has no usable abstract, because such a paper
cannot be embedded, would pollute search results, and is rejected by the database's
non-empty-abstract constraint. It SHALL count each such record so that the operator can
see how many were dropped.

#### Scenario: An abstract-less record is not stored
- **WHEN** a fetched record carries no usable abstract
- **THEN** no paper is stored for it
- **AND** no error is raised

#### Scenario: Every stored paper has an abstract
- **WHEN** a run finishes
- **THEN** every paper it stored has a non-empty abstract

#### Scenario: Skipped records are counted
- **WHEN** a run encounters records without a usable abstract
- **THEN** the number skipped is reported

### Requirement: Running the command twice is safe

The command SHALL identify papers by their INSPIRE id and SHALL update an existing
paper rather than inserting a second one. Running the command a second time over the
same query SHALL leave the number of stored papers unchanged.

#### Scenario: A second run creates no duplicates
- **WHEN** the command is run twice over the same records
- **THEN** the number of stored papers after the second run equals the number after the
  first
- **AND** each INSPIRE id appears exactly once

#### Scenario: An interrupted run is completed by re-running
- **WHEN** a run is interrupted partway through and the same command is run again
- **THEN** the papers stored by the interrupted run are not duplicated
- **AND** the remaining papers are stored

### Requirement: Only genuinely changed papers are written

A stored paper whose incoming content is identical SHALL NOT be written. A stored paper
whose incoming content differs in any field the ingestion populates SHALL be updated to
match. The paper's last-modified timestamp SHALL move when and only when the paper is
actually updated, so that the timestamp remains a truthful record of when the content
last changed.

#### Scenario: An unchanged paper is left alone
- **WHEN** a run re-encounters a paper whose content has not changed
- **THEN** the paper's stored content is unchanged
- **AND** its last-modified timestamp is unchanged

#### Scenario: A changed paper is updated
- **WHEN** a run encounters a paper whose title, abstract, authors, categories, arXiv
  id, DOI, journal, earliest date or citation count differs from the stored row
- **THEN** the stored paper is updated to the incoming values
- **AND** its last-modified timestamp moves

#### Scenario: The creation timestamp survives an update
- **WHEN** a stored paper is updated by a later run
- **THEN** its original creation timestamp is preserved

### Requirement: Writes are batched and each batch is atomic

The command SHALL write papers in batches rather than issuing a query per paper, and
the batch size SHALL be configurable through project settings without changing code.
Each batch SHALL be written inside a single transaction so that a batch either lands
completely or not at all. The run as a whole SHALL NOT be a single transaction, because
that would discard every completed batch when a run is interrupted.

#### Scenario: A run does not issue a query per paper
- **WHEN** a run stores many papers
- **THEN** the number of write queries is proportional to the number of batches, not to
  the number of papers

#### Scenario: The batch size comes from settings
- **WHEN** the configured batch size is changed
- **THEN** the command groups its writes accordingly, with no code change

#### Scenario: Completed batches survive an interruption
- **WHEN** a run is interrupted after some batches have been written
- **THEN** the papers from the completed batches remain in the database

#### Scenario: An interrupted batch does not land partially
- **WHEN** a batch fails partway through being written
- **THEN** none of that batch's papers are stored

### Requirement: A long run reports progress and a final summary

Because a full run takes many minutes, the command SHALL report progress to standard
output as it proceeds, at least once per batch, and SHALL print a final summary. The
summary SHALL state how many records were fetched, how many were skipped for having no
usable abstract, and how many papers were created, updated and left unchanged.

#### Scenario: Progress appears while the run proceeds
- **WHEN** a run processes more than one batch
- **THEN** it writes progress output for each batch as it goes, rather than only at the
  end

#### Scenario: The final summary reports every outcome
- **WHEN** a run finishes
- **THEN** it prints the number of records fetched, the number skipped for having no
  usable abstract, and the numbers of papers created, updated and unchanged

#### Scenario: A second run reports no work done
- **WHEN** the command is run a second time over unchanged records
- **THEN** the summary reports zero created and every paper unchanged

### Requirement: A dry run reports without writing

The command SHALL offer a dry-run mode that performs the same fetch for the same limit
and reports the same counts it would otherwise report, but stores nothing. It SHALL NOT
silently shorten the run, so that a dry run is a truthful rehearsal of the real one; an
operator wanting a quick check combines the dry run with a small limit.

#### Scenario: A dry run stores nothing
- **WHEN** the command is run in dry-run mode
- **THEN** the number of stored papers is unchanged
- **AND** no stored paper is modified

#### Scenario: A dry run reports what would happen
- **WHEN** the command is run in dry-run mode against records that are partly new and
  partly already stored
- **THEN** it reports how many papers would be created and how many would be updated

#### Scenario: A dry run honours the requested limit
- **WHEN** the command is run in dry-run mode with a limit
- **THEN** it fetches up to that limit rather than stopping after the first batch

### Requirement: A short corpus is reported, not treated as a failure

When fewer papers are available than requested — because the query matches few records,
or because the API's deep-pagination ceiling is reached — the command SHALL report the
shortfall on standard output and SHALL exit successfully.

#### Scenario: A small corpus ends cleanly
- **WHEN** the query matches fewer usable records than the requested limit
- **THEN** the command stores every usable paper it found
- **AND** reports that it landed fewer than requested
- **AND** exits successfully

#### Scenario: The pagination ceiling is reported to the operator
- **WHEN** the run stops early because the API's reachable result window is exhausted
- **THEN** the shortfall is visible in the command's output

### Requirement: The command is fully testable offline

No test of this capability SHALL perform a network request or contact the INSPIRE API.
Tests SHALL exercise the command against the committed fixture of real INSPIRE
responses with the network replaced, and SHALL assert idempotence by running the
command twice.

#### Scenario: The command's tests make no network request
- **WHEN** the project's tests are run
- **THEN** the ingestion command makes no request to the INSPIRE API

#### Scenario: Idempotence is asserted by a second run
- **WHEN** the command's tests run it twice over the same fixture
- **THEN** they assert that the paper count is unchanged and that nothing was created
  by the second run

#### Scenario: The timestamp rule is asserted in both directions
- **WHEN** the command's tests re-run it over one changed record and one unchanged
  record
- **THEN** they assert the changed paper's last-modified timestamp moved
- **AND** the unchanged paper's did not
