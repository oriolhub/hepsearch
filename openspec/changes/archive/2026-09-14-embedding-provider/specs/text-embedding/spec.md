## ADDED Requirements

### Requirement: Text becomes vectors through one swappable interface

The system SHALL expose a single embedding interface declaring an `embed` operation over
a sequence of texts, together with the `dimension` and `model_name` of the vectors it
produces. Every consumer that needs a vector SHALL obtain one through this interface.

No module outside the interface's own implementations SHALL import a specific embedding
library or contact a specific embedding vendor. Replacing the local model with a hosted
embedding API SHALL require adding or editing exactly one implementation module, and no
change to any consumer.

#### Scenario: A caller obtains vectors without naming a model
- **WHEN** a consumer embeds text
- **THEN** it does so through the interface
- **AND** it names no embedding library, model or vendor

#### Scenario: Only implementations know the library
- **WHEN** the repository is inspected for imports of the local embedding library
- **THEN** the only module importing it is the local implementation

#### Scenario: The embedding app depends on no other app
- **WHEN** the modules of the embedding app are inspected
- **THEN** none of them imports the papers, ingestion or search apps

### Requirement: The implementation is chosen by configuration, not by import

The implementation SHALL be selected through a named setting holding an import path, and
resolved at run time. No consumer SHALL import a concrete implementation directly,
because doing so would defeat the interface it was given.

The configured default SHALL be the real local implementation rather than any test
double, so that an operator who never touches the setting cannot silently populate a
corpus with vectors that mean nothing.

#### Scenario: The configured implementation is the one used
- **WHEN** the setting names an implementation
- **THEN** the provider obtained by consumers is an instance of that implementation

#### Scenario: Changing the setting changes the implementation
- **WHEN** the setting is changed to name a different implementation
- **THEN** consumers subsequently obtain the new implementation, with no code change

#### Scenario: The default is the real implementation
- **WHEN** the setting is left at its default
- **THEN** the real local implementation is selected

#### Scenario: An unresolvable configuration fails loudly
- **WHEN** the setting names an implementation that cannot be resolved
- **THEN** an error is raised naming the offending configuration
- **AND** no fallback implementation is substituted

### Requirement: A provider is built once per process and loads its model lazily

Obtaining a provider SHALL be cheap and SHALL yield the same instance for the lifetime of
the process, so that a per-request or per-row call cannot repeatedly pay a model's
construction cost.

Constructing a provider SHALL NOT load an embedding model. The model SHALL be loaded on
the first call that actually needs it and SHALL be loaded at most once, even when
concurrent callers request an embedding simultaneously.

The cached provider SHALL be resettable explicitly, so that a test may exercise a
different implementation without a previously cached provider leaking into it.

#### Scenario: Repeated requests share one provider
- **WHEN** a provider is obtained twice in the same process
- **THEN** the same instance is returned both times

#### Scenario: Construction loads no model
- **WHEN** a provider is obtained but nothing is embedded
- **THEN** no embedding model has been loaded

#### Scenario: The model is loaded once
- **WHEN** several texts are embedded across several separate calls
- **THEN** the model was loaded exactly once

#### Scenario: Concurrent first calls load the model once
- **WHEN** two callers embed text simultaneously as the first users of a process
- **THEN** the model is loaded exactly once

#### Scenario: The cache can be reset
- **WHEN** the cached provider is reset and a provider is obtained again
- **THEN** a newly constructed provider is returned

### Requirement: Every vector is unit length

Vectors returned by any implementation SHALL be L2-normalized. This is a property of the
interface rather than of any one implementation, so that stored vectors remain comparable
no matter which implementation wrote them, and so that cosine distance and inner product
are interchangeable for whatever index a consumer later builds over them.

Normalization SHALL NOT be configurable. A switch would produce stored vectors whose
comparability depended on a setting that happened to hold at write time.

#### Scenario: A returned vector has unit length
- **WHEN** any implementation embeds text
- **THEN** each returned vector has a Euclidean norm of 1, within floating-point
  tolerance

#### Scenario: Normalization is not optional
- **WHEN** the interface is inspected
- **THEN** it exposes no option to disable normalization

### Requirement: The input contract is defined on text, not on tokens

`embed` SHALL accept a sequence of texts and SHALL return one vector per text, in the
same order as the input, so that a caller can pair results with its own records by
position.

An empty sequence SHALL return an empty sequence, and SHALL NOT load a model.

A text that is empty or consists only of whitespace SHALL raise an error rather than
yield a vector. A zero or arbitrary vector for blank input is equidistant from
everything and would return meaningless "nearest" results.

Any text containing non-whitespace content SHALL yield exactly one vector. The contract
SHALL be expressed in terms of non-whitespace content rather than in terms of whether
anything survives an implementation's tokenization, so that no implementation is stricter
than another about input a user can actually type.

#### Scenario: Vectors are returned in input order
- **WHEN** several distinct texts are embedded in one call
- **THEN** the result holds one vector per text
- **AND** each vector corresponds to the text at the same position

#### Scenario: An empty batch loads nothing
- **WHEN** an empty sequence is embedded
- **THEN** the result is empty
- **AND** no embedding model was loaded

#### Scenario: Blank text is refused
- **WHEN** a text that is empty or only whitespace is embedded
- **THEN** an error is raised
- **AND** no vector is produced for it

#### Scenario: Punctuation-only text still yields a vector
- **WHEN** a text containing only punctuation is embedded
- **THEN** exactly one unit vector is returned
- **AND** every implementation behaves the same way for that text

### Requirement: The vector dimension is a contract enforced before it can be violated

The vector dimension SHALL be a named project setting, because a stored vector column and
its index are built from that number and a later disagreement would either corrupt writes
or silently compare incomparable spaces.

Each implementation SHALL declare the dimension it produces without loading a model, so
that the declaration can be checked cheaply. A project check SHALL compare the configured
dimension against the configured implementation's declared dimension and SHALL report an
error when they disagree. That check SHALL NOT load an embedding model, because it runs on
every routine command invocation.

An implementation that loads a model SHALL verify the loaded model's true dimension
against its own declaration and SHALL fail rather than emit vectors of an unexpected
width.

#### Scenario: Matching configuration passes the check
- **WHEN** the configured dimension equals the implementation's declared dimension
- **THEN** the project check reports no error

#### Scenario: A mismatch is reported as an error
- **WHEN** the configured dimension differs from the implementation's declared dimension
- **THEN** the project check reports an error identifying both values

#### Scenario: The check is cheap
- **WHEN** the project check runs
- **THEN** no embedding model is loaded

#### Scenario: An unknown model is refused at configuration time
- **WHEN** the local implementation is configured with a model whose dimension it does
  not know
- **THEN** an error is raised
- **AND** no dimension is guessed

#### Scenario: The loaded model is verified against the declaration
- **WHEN** a real model is loaded whose dimension differs from what was declared
- **THEN** an error is raised rather than vectors of the wrong width being returned

### Requirement: A provider identifies the embedding space it produces

Every implementation SHALL expose a `model_name` identifying the vector space it
produces. Two implementations whose vectors are not comparable SHALL NOT share a name,
because consumers record this value alongside stored vectors and later refuse to compare
a stored vector against a query embedded in a different space.

#### Scenario: The real implementation reports its model
- **WHEN** the local implementation is asked for its model name
- **THEN** it returns the configured model's identifier

#### Scenario: A test double is identifiable as one
- **WHEN** the deterministic offline implementation is asked for its model name
- **THEN** the value returned identifies it unmistakably as a test double

#### Scenario: Distinct spaces have distinct names
- **WHEN** two implementations producing incomparable vectors are compared
- **THEN** their model names differ

### Requirement: A deterministic offline implementation exists for testing

The system SHALL provide an implementation that produces vectors without loading a model,
contacting a network or reading any downloaded artifact, so that every consumer of
embeddings can be tested offline and quickly.

Its vectors SHALL be deterministic across processes, not merely within one, because a
vector written by one process is later compared by another.

Texts sharing words SHALL produce vectors that are closer together than texts sharing
none, so that consumers can assert genuine ranking behaviour rather than mere plumbing.

It SHALL honour the same interface contract as any other implementation, including
normalization, ordering, the empty-batch rule and the blank-text rule. Its dimension SHALL
follow the configured dimension, so that it can stand in wherever the real implementation
would.

#### Scenario: The same text always embeds identically
- **WHEN** the same text is embedded in two separate processes
- **THEN** the two vectors are identical

#### Scenario: Related texts are nearer than unrelated ones
- **WHEN** two texts sharing several words and a third sharing none are embedded
- **THEN** the two related texts are closer to each other than either is to the third

#### Scenario: It produces vectors of the configured width
- **WHEN** the configured dimension is changed and text is embedded
- **THEN** the returned vectors have the configured width

#### Scenario: It loads nothing and reaches nowhere
- **WHEN** text is embedded
- **THEN** no model is loaded and no network request is made

### Requirement: Configuring a test double is announced outside tests

The project check SHALL report a warning whenever the offline implementation is the
selected one, so that a misconfiguration is visible on every routine command rather than
discovered after a corpus has been filled with meaningless vectors. The offline
implementation is ordinary application code and can therefore be configured anywhere,
including by accident.

That warning SHALL be suppressed while the test suite is running, since the tests
legitimately select it and permanent warning noise trains readers to ignore warnings.

#### Scenario: Selecting the test double warns
- **WHEN** the offline implementation is configured and a project check runs outside the
  test suite
- **THEN** a warning identifies it as unsuitable for real use

#### Scenario: The real implementation warns about nothing
- **WHEN** the real implementation is configured
- **THEN** no such warning is reported

#### Scenario: The test suite is not warned at
- **WHEN** the test suite runs with the offline implementation configured
- **THEN** no such warning is reported

### Requirement: The heavy embedding dependency is opt-in

The library backing the local implementation SHALL be an optional installation rather
than a default one, because it pulls a machine-learning runtime of a size out of all
proportion to a test suite that never uses it.

The embedding modules SHALL remain importable when that library is absent, so that
routine commands, project checks and the whole default test suite continue to work on a
default installation. The absence SHALL surface only when a real embedding is genuinely
attempted, and SHALL then fail with an error naming the optional installation required.

#### Scenario: A default installation omits the heavy library
- **WHEN** dependencies are installed without the optional selection
- **THEN** the machine-learning runtime is not installed

#### Scenario: Everything still works without it
- **WHEN** the heavy library is absent
- **THEN** routine commands, the project check and the default test suite all succeed

#### Scenario: A real embedding attempt explains what is missing
- **WHEN** the heavy library is absent and a real embedding is attempted
- **THEN** an error is raised naming the optional installation that provides it

### Requirement: The default test run stays fast, offline and model-free

No test in the default run SHALL load an embedding model, download an artifact or make a
network request. Consumers of embeddings SHALL be tested against the deterministic offline
implementation.

Exactly one test SHALL exercise the real implementation, and it SHALL be excluded from the
default run and opted into explicitly. It SHALL guard its optional dependency with
`pytest.importorskip` when it executes, rather than breaking the opted-in run when the
library is absent. The guard SHALL NOT import the library during default-run collection.

That test SHALL confirm that the real model produces vectors of the declared width, and
that two semantically related sentences score higher against each other than either does
against an unrelated one.

#### Scenario: The default run touches no model
- **WHEN** the default test suite is run
- **THEN** no embedding model is loaded, downloaded or requested over the network

#### Scenario: The real-model test is excluded by default
- **WHEN** the default test suite is run
- **THEN** the test exercising the real implementation does not run

#### Scenario: The real-model test can be opted into
- **WHEN** the suite is run with the exclusion lifted and the optional library installed
- **THEN** the real implementation is exercised
- **AND** it returns vectors of the declared width
- **AND** two related sentences score higher against each other than against an unrelated
  one

#### Scenario: An opted-in run survives a missing library
- **WHEN** the slow tests are run on a machine without the optional library
- **THEN** the real-model test is reported as skipped rather than failing
- **AND** default-run collection does not import the optional library
