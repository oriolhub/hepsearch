## ADDED Requirements

### Requirement: A paper carries its embedding and the model that produced it

`Paper` SHALL store an optional embedding vector, the name of the model that produced it,
and the time at which it was computed. The vector SHALL be optional, because a paper
exists before it is embedded. The recorded model name SHALL NOT be nullable: it is
compared against the configured provider's model name, and a null would make that
comparison neither true nor false.

#### Scenario: A newly ingested paper has no vector
- **WHEN** a paper is created by ingestion
- **THEN** its embedding is absent
- **AND** its recorded model name is empty rather than null
- **AND** its embedding time is absent

#### Scenario: An embedded paper carries its provenance
- **WHEN** a paper has been embedded
- **THEN** its embedding, the producing model's name and the computation time are all
  readable from the model instance

#### Scenario: The recorded model name is never null
- **WHEN** the papers table is inspected
- **THEN** the column holding the producing model's name rejects null

### Requirement: A paper defines the text that represents it

`Paper` SHALL expose the text used to represent it for embedding, composed of its title
and abstract. This definition SHALL live on the model so that every producer and consumer
of embeddings derives it from one place rather than reconstructing it.

#### Scenario: The embedding text combines title and abstract
- **WHEN** a paper's embedding text is read
- **THEN** it contains the paper's title and its abstract
- **AND** the two are separated so they are not run together as one sentence

#### Scenario: The definition is usable without a database or a provider
- **WHEN** the embedding text of an unsaved paper instance is read
- **THEN** it is produced without a database query and without loading an embedding model

### Requirement: The domain expresses the vector's width as configuration, not as a literal

The embedding field's dimension SHALL be taken from `settings.EMBEDDING_DIMENSION`.
`apps/papers` SHALL NOT import an embedding provider to obtain it, so that the domain app
continues to depend on nothing that must be loaded, downloaded or installed as an extra.

#### Scenario: The domain app imports no provider
- **WHEN** the modules in `apps/papers` are inspected
- **THEN** none of them imports an embedding provider or `sentence_transformers`

#### Scenario: The dimension follows the setting
- **WHEN** the embedding field's declared dimension is inspected
- **THEN** it is the value of `settings.EMBEDDING_DIMENSION`, not a hardcoded number
