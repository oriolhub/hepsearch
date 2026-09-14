## MODIFIED Requirements

### Requirement: Only genuinely changed papers are written

A stored paper whose incoming content is identical SHALL NOT be written. A stored paper
whose incoming content differs in any field the ingestion populates SHALL be updated to
match. The paper's last-modified timestamp SHALL move when and only when the paper is
actually updated, so that the timestamp remains a truthful record of when the content
last changed.

Ingestion SHALL write only the fields INSPIRE supplies, with one deliberate exception.
Fields that are computed and owned elsewhere in the system — a paper's embedding, the
model that produced it and the time it was computed — SHALL NOT be populated or compared
by ingestion, regardless of how the set of written fields is determined. Re-ingesting an
unchanged paper SHALL therefore leave any stored embedding intact.

The exception is invalidation. When ingestion updates a field the embedding is derived
from, the stored embedding no longer describes the paper, and nothing else in the system
can detect that. Ingestion SHALL therefore clear the stored embedding and its recorded
provenance whenever it updates the paper's title or abstract, so that the paper is
selected for embedding again on the next run. Ingestion SHALL NOT compute a replacement.

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

#### Scenario: A stored embedding survives a re-ingest that changes nothing
- **WHEN** a paper that already has a stored embedding is ingested again with identical
  content
- **THEN** its embedding is unchanged
- **AND** the model recorded against that embedding is unchanged
- **AND** the recorded embedding time is unchanged

#### Scenario: A stored embedding survives a change to fields it is not derived from
- **WHEN** a paper that already has a stored embedding is ingested again with a changed
  citation count, DOI, journal, authors, categories or earliest date
- **THEN** those fields are updated
- **AND** its embedding is still present and unchanged

#### Scenario: A stored embedding is invalidated when its source text changes
- **WHEN** a paper that already has a stored embedding is ingested again with a changed
  title or abstract
- **THEN** the new title or abstract is stored
- **AND** the paper's embedding is cleared
- **AND** the paper is reported as needing embedding by the embedding command

#### Scenario: Ingestion never computes an embedding
- **WHEN** ingestion invalidates a paper's embedding
- **THEN** it does not load an embedding provider or compute a replacement vector
