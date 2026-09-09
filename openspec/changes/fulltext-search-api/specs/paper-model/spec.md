## ADDED Requirements

### Requirement: A paper carries a database-generated full-text search vector

The paper record SHALL carry a full-text search vector derived from its title and
abstract. The vector SHALL be computed and maintained by the database itself, as a
stored generated value, so that it can never drift from the text it describes and so
that no writer is obliged to remember to update it.

The vector SHALL weight the title above the abstract, because a paper whose *title*
names a concept is more about that concept than one that merely mentions it in
passing. That weighting is part of the schema rather than of any particular query, so
that every reader ranks papers the same way.

The text search configuration SHALL be stated explicitly and SHALL be exposed as a
named constant rather than repeated as a literal, because the retrieval layer must use
the identical configuration and a later hybrid ranker will need it too. A vector built
without an explicit configuration cannot be stored or indexed at all, because its
value would depend on a run-time setting.

#### Scenario: The vector is populated without anyone writing it
- **WHEN** a paper is created with a title and an abstract
- **THEN** its search vector is populated
- **AND** no caller supplied a value for it

#### Scenario: Editing the text updates the vector
- **WHEN** a stored paper's title or abstract is changed
- **THEN** its search vector reflects the new text

#### Scenario: Existing papers gain a vector when the schema changes
- **WHEN** the migration introducing the vector is applied to a database that already
  holds papers
- **THEN** every existing paper has a populated search vector
- **AND** no re-ingestion is required

#### Scenario: Title terms are weighted above abstract terms
- **WHEN** the vector of a paper is inspected
- **THEN** terms drawn from its title carry a higher weight than terms drawn from its
  abstract

#### Scenario: The configuration is named, not repeated
- **WHEN** the text search configuration is needed by the model or by a query
- **THEN** both obtain it from a single named constant

#### Scenario: Ingestion is unaffected
- **WHEN** the ingestion writer's set of compared fields is inspected
- **THEN** the search vector is not among them, because ingestion neither supplies nor
  owns it

### Requirement: The search vector is backed by a committed index

The search vector SHALL be covered by an index suited to full-text lookup, and that
index SHALL be created by a committed migration rather than applied by hand, so that
any database built from the migrations is searchable on equal terms.

#### Scenario: The index ships with the schema
- **WHEN** the migrations are applied to an empty database
- **THEN** an index over the search vector exists

#### Scenario: The migration is reversible
- **WHEN** the migration introducing the vector and its index is reversed
- **THEN** the column and the index are removed
- **AND** no paper data is lost, because the vector is derived from text that remains

#### Scenario: A selective term is served by the index
- **WHEN** the query plan is inspected by hand for a term matching a small fraction of
  the corpus
- **THEN** the plan uses the index rather than scanning every row
- **AND** the observed plan is recorded in the commit that introduces it