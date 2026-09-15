## ADDED Requirements

### Requirement: The vector extension is enabled by a committed migration

The system SHALL enable the PostgreSQL `vector` extension through a committed Django
migration, not through a manual `psql` step or a documented setup instruction. The
migration SHALL be ordered before any migration that creates a column of vector type.

#### Scenario: A fresh database gains the extension by migrating alone
- **WHEN** `migrate` is run against a newly created database volume on which no
  extension has been installed by hand
- **THEN** the migration completes without error
- **AND** the `vector` extension is present in the database afterwards
- **AND** no manual `psql` step was required

#### Scenario: The extension exists before it is used
- **WHEN** the migration graph is inspected
- **THEN** the migration enabling the extension is an ancestor of the migration adding
  the vector column

#### Scenario: The privilege requirement is recorded
- **WHEN** the migration is read
- **THEN** it states that `vector` is an untrusted extension requiring a superuser
- **AND** it states what an operator must do when the application role is not a
  superuser

### Requirement: The stored vector's width is the configured dimension, frozen by a migration

The width of the embedding column SHALL equal `settings.EMBEDDING_DIMENSION` at the time
the migration is generated. The system SHALL NOT read a provider to determine it, so that
generating migrations never depends on a loadable embedding model.

Once migrated, the column width is the binding contract: changing the setting afterwards
SHALL NOT alter the column, and the system SHALL treat the resulting disagreement as an
error rather than a silent inconsistency.

#### Scenario: The column is created at the configured width
- **WHEN** the migrations are applied with the shipped configuration
- **THEN** the embedding column's declared dimension equals `settings.EMBEDDING_DIMENSION`

#### Scenario: Generating migrations does not load a model
- **WHEN** `makemigrations` is run in an environment where the embedding model cannot be
  loaded or downloaded
- **THEN** the command succeeds

#### Scenario: No model change is left unmigrated
- **WHEN** `makemigrations --check --dry-run` is run
- **THEN** it reports that no new migrations are needed

### Requirement: An approximate-nearest-neighbour index ships with the schema

The system SHALL create an ANN index over the embedding column in a committed migration,
using the cosine operator class. The choice of index type and its parameters SHALL be
justified in a comment at the point of definition.

#### Scenario: The index is created by migrating
- **WHEN** the migrations are applied to an empty database
- **THEN** an ANN index over the embedding column exists
- **AND** it uses the cosine operator class

#### Scenario: The index type is buildable on an empty table
- **WHEN** the index migration runs against a database containing no papers
- **THEN** it completes without error and without requiring sample data to be present

#### Scenario: The rationale is discoverable
- **WHEN** the index definition is read
- **THEN** a comment explains why this index type was chosen over the alternative
- **AND** explains why the cosine operator class was chosen

### Requirement: An operator can embed the corpus with one command

The system SHALL provide `manage.py embed_papers`, which computes and stores a vector for
every paper that needs one, using the provider configured for the project.

#### Scenario: A corpus without vectors is embedded
- **WHEN** the command is run against a corpus in which no paper has a vector
- **THEN** every paper has a stored vector afterwards
- **AND** each stored vector has the configured dimension

#### Scenario: The stored vector represents the paper's own text
- **WHEN** a paper is embedded
- **THEN** the vector stored is the one the provider returned for that paper's embedding
  text

### Requirement: The command validates provider and schema before touching any paper row

Before modifying any paper, the command SHALL resolve the configured provider and verify
that the provider's declared dimension, the configured dimension setting, and the actual
width of the embedding column all agree. It SHALL then verify the provider by performing
a real embedding call.

If any of these fail, the command SHALL exit with an error having written nothing. A
partially embedded corpus SHALL NOT be a possible outcome of a misconfiguration.

#### Scenario: A misconfigured provider stops the run before any write
- **WHEN** the configured provider cannot be resolved, or its dependencies are not
  installed
- **THEN** the command exits with an error
- **AND** no paper's stored vector has changed

#### Scenario: A provider whose declared dimension disagrees with the setting is rejected
- **WHEN** the provider's declared dimension differs from `settings.EMBEDDING_DIMENSION`
- **THEN** the command exits with an error naming both values
- **AND** no paper's stored vector has changed

#### Scenario: A setting that disagrees with the migrated column is rejected
- **WHEN** `settings.EMBEDDING_DIMENSION` differs from the width of the embedding column
  in the database
- **THEN** the command exits with an error naming both values
- **AND** no paper's stored vector has changed

#### Scenario: Validation is a real embedding call
- **WHEN** the provider resolves and all dimensions agree, but the provider raises when
  asked to embed
- **THEN** the command exits with an error
- **AND** no paper's stored vector has changed

### Requirement: A paper needs embedding when it has no vector or one from another model

The system SHALL treat a paper as needing embedding when it has no stored vector, or when
the model recorded against its stored vector differs from the model the configured
provider identifies itself as. Every write of a vector SHALL record the producing model
and the time of computation.

The recorded model SHALL NOT be null, so that a paper can never become permanently
invisible to this rule.

#### Scenario: A paper with no vector is embedded
- **WHEN** the command runs and a paper has no stored vector
- **THEN** that paper is embedded

#### Scenario: A paper embedded by a different model is re-embedded
- **WHEN** the configured provider identifies a different model than the one recorded
  against a paper's stored vector
- **THEN** that paper is re-embedded
- **AND** the newly recorded model is the configured provider's

#### Scenario: A paper embedded by the configured model is left alone
- **WHEN** a paper's recorded model matches the configured provider's
- **THEN** the paper's stored vector is unchanged

#### Scenario: The producing model and time are recorded
- **WHEN** a paper is embedded
- **THEN** the model that produced the vector is stored against it
- **AND** the time at which it was computed is stored against it

### Requirement: A mass recomputation is announced and confirmed

The command SHALL report how many papers need embedding because their recorded model
differs from the configured one, before recomputing any of them. When such papers exist
and the command is running interactively, it SHALL require confirmation before
proceeding, and SHALL offer a flag to skip the confirmation for unattended use.

#### Scenario: Stale embeddings are counted and reported
- **WHEN** the corpus contains papers embedded by a different model
- **THEN** the command reports the number of stale embeddings detected and that the cause
  is a model change

#### Scenario: An interactive run asks before discarding work
- **WHEN** stale embeddings exist and the command is run interactively
- **THEN** the command asks for confirmation before recomputing
- **AND** declining leaves every stored vector unchanged

#### Scenario: An unattended run proceeds without prompting
- **WHEN** stale embeddings exist and the no-input flag is given
- **THEN** the command proceeds without prompting
- **AND** still reports the number of stale embeddings

#### Scenario: A run that cannot be answered fails instead of guessing
- **WHEN** confirmation is required but the command is not running interactively
  and the no-input flag was not given
- **THEN** the command fails with an explanatory error
- **AND** leaves every stored vector unchanged

#### Scenario: A run with nothing stale does not prompt
- **WHEN** every paper needing embedding merely lacks a vector
- **THEN** the command proceeds without asking for confirmation

### Requirement: Re-running the command is safe and says so

Running the command when no paper needs embedding SHALL make no database writes and SHALL
report that there was nothing to do.

#### Scenario: An immediate re-run is a no-op
- **WHEN** the command is run twice in succession with unchanged configuration
- **THEN** the second run embeds nothing
- **AND** reports that no papers needed embedding
- **AND** no stored vector differs from after the first run

### Requirement: An interrupted run resumes without repeating work

Papers SHALL be embedded in batches, each batch written atomically, so that interrupting
the command loses at most the batch in flight. A subsequent run SHALL continue with the
papers that still need embedding and SHALL NOT recompute those already done.

#### Scenario: Work completed before an interruption survives
- **WHEN** the command is interrupted after some batches have been written
- **THEN** the vectors written by the completed batches are still stored

#### Scenario: A resumed run finishes the remainder
- **WHEN** the command is run again after an interruption
- **THEN** it embeds exactly the papers that still need embedding
- **AND** papers embedded before the interruption are not recomputed

#### Scenario: Selecting work never skips a paper
- **WHEN** a run embeds a corpus larger than one batch
- **THEN** every paper that needed embedding when the run started has a vector at the end

### Requirement: Batch size is configurable

The number of papers embedded per batch SHALL be settable from the command line and
SHALL have a sensible default.

#### Scenario: The default batch size is used
- **WHEN** the command is run without a batch size argument
- **THEN** it embeds using its default batch size

#### Scenario: An explicit batch size is honoured
- **WHEN** the command is run with an explicit batch size
- **THEN** papers are embedded in batches of that size

### Requirement: Recomputation can be forced for an unchanged model

The command SHALL offer a flag that recomputes vectors for papers whose recorded model
already matches the configured provider, for use after a provider defect or a dependency
upgrade that changes output without changing the model's name.

#### Scenario: Forcing recomputes papers that are otherwise up to date
- **WHEN** the command is run with the force flag against a corpus whose recorded models
  all match the configured provider
- **THEN** every paper is embedded again
- **AND** the recorded computation time moves

#### Scenario: Forcing is subject to the same confirmation
- **WHEN** the force flag is used interactively
- **THEN** the command asks for confirmation before recomputing

### Requirement: Embedding is not a change to the paper's content

Computing and storing a vector SHALL NOT alter the paper's last-modified timestamp. That
timestamp records when the paper's content last changed; the time of embedding is
recorded separately.

#### Scenario: The last-modified timestamp does not move
- **WHEN** a paper is embedded
- **THEN** its last-modified timestamp is unchanged
- **AND** its embedding time is set

### Requirement: A long run reports progress and a final summary

The command SHALL report progress as it proceeds and SHALL print a final summary stating
how many papers were embedded and how many were skipped as already current.

#### Scenario: A summary closes the run
- **WHEN** a run completes
- **THEN** it prints the number of papers embedded
- **AND** the number that needed no work

### Requirement: The command is fully testable offline

The command's tests SHALL use the deterministic offline provider and SHALL NOT download a
model or contact the network in the default test run.

#### Scenario: The default test run stays offline
- **WHEN** the default test suite runs
- **THEN** the tests for this command pass without network access
- **AND** without loading a real embedding model

#### Scenario: Vectors are asserted, not assumed
- **WHEN** the tests run
- **THEN** they assert that vectors are stored, that a re-run is a no-op, that a model
  change triggers re-embedding, and that forcing recomputes
