# semantic-search Specification

## Purpose
Provide semantic retrieval over embedded HEP papers while keeping embedding concerns at the provider boundary and HTTP availability decisions at the view boundary.

## Requirements


### Requirement: A natural-language query is answered by vector similarity

The system SHALL rank papers by the cosine distance between a stored paper embedding
and an embedding of the caller's query, so that a paper can be found by what it is
about rather than by the words it happens to use. The query SHALL be embedded with the
same provider and model that produced the corpus.

#### Scenario: The nearest vector ranks first
- **WHEN** a semantic search is performed and several papers carry embeddings
- **THEN** the paper whose embedding is nearest the query vector is returned first
- **AND** the remaining papers follow in order of increasing distance

#### Scenario: The query is embedded with the corpus provider
- **WHEN** a semantic search is performed
- **THEN** the query is embedded through the configured provider registry rather than
  by importing an embedding implementation directly

#### Scenario: A paraphrase finds papers keyword search misses
- **WHEN** a query is submitted that describes a paper's subject without sharing any
  distinctive term with its title or abstract
- **THEN** semantic mode returns that paper
- **AND** keyword mode for the same query does not


### Requirement: Only embeddings from the configured model are eligible

Semantic ranking SHALL consider only papers whose stored embedding was produced by the
model the system is currently configured to use, because vectors from different models
occupy unrelated spaces and comparing them yields a confident but meaningless ranking.
Papers carrying no embedding SHALL be excluded rather than crashing or occupying result
positions.

#### Scenario: A paper with no embedding is excluded
- **WHEN** the corpus contains papers with and without embeddings
- **THEN** only papers carrying an embedding appear in the results
- **AND** no error is raised

#### Scenario: A paper embedded by a different model is excluded
- **WHEN** the corpus contains papers whose recorded embedding model differs from the
  configured one
- **THEN** those papers are absent from the results

#### Scenario: Unembedded papers do not fill a short result set
- **WHEN** fewer papers carry a compatible embedding than the configured result cap
- **THEN** the results contain only those compatible papers
- **AND** no paper lacking an embedding is returned


### Requirement: Ordering is performed by the database, using the vector index

The ordering SHALL be expressed as a distance operation the database evaluates, and
SHALL NOT be produced by loading candidate rows into the application and sorting them.
The query plan SHALL show the approximate-nearest-neighbour index being used. Ordering
SHALL be deterministic for a repeated query against unchanged data.

#### Scenario: Rows are not sorted in the application
- **WHEN** the semantic ranking implementation is inspected
- **THEN** the ordering is expressed as a database distance ordering
- **AND** no candidate rows are sorted in Python

#### Scenario: The plan uses the vector index
- **WHEN** the query plan for a semantic search over the ingested corpus is examined
- **THEN** it shows the vector index being scanned rather than a sequential scan of the
  papers table

#### Scenario: Ordering is stable for a repeated query
- **WHEN** the same semantic query is issued twice against unchanged data
- **THEN** the same papers are returned in the same order


### Requirement: Semantic ranking is a function over a vector, callable without HTTP

The semantic ranking SHALL be implemented as a callable that takes a query vector and a
result bound and returns matching papers, and SHALL NOT accept query text, load an
embedding model, construct a provider, or reference the HTTP layer. It SHALL return a
lazily-evaluated query so that a later hybrid ranker can compose it.

#### Scenario: Ranking is exercised with a hand-written vector
- **WHEN** the semantic ranking callable is invoked with a vector and a bound
- **THEN** it returns matching papers
- **AND** no embedding model was loaded and no request object was involved

#### Scenario: The ranker does not embed text
- **WHEN** the semantic ranking callable is inspected
- **THEN** it accepts a vector rather than text
- **AND** it does not call the embedding provider

#### Scenario: The embedding space is named by the caller
- **WHEN** the semantic ranking callable is invoked
- **THEN** it requires the name of the embedding space its vector came from
- **AND** it assumes no default, because the configured model name and the provider's
  model name need not agree

#### Scenario: The result is composable
- **WHEN** the semantic ranking callable returns
- **THEN** its result can be further filtered or ordered before being evaluated


### Requirement: An unusable semantic corpus is refused, an empty one is not

The system SHALL distinguish a corpus that is empty from a corpus that cannot serve
semantic search. When no papers exist at all, a semantic request SHALL succeed with an
empty result list, because nothing is wrong. When papers exist but none carries an
embedding compatible with the configured model, the request SHALL be refused with a 503
status and a message naming the operator action that resolves it, because the caller
asked for semantic search and the system cannot perform it.

The embedding provider's dependencies are an optional extra, so a default installation
can reach a semantic request without being able to embed at all. That SHALL be treated
as the same class of operator-fixable outage as an unembedded corpus: a 503 naming the
cause, never an unhandled error.

The decision SHALL be made by the HTTP layer. The ranking callable SHALL return an empty
result and SHALL NOT raise, so that a later hybrid ranker can tolerate the same condition
by falling back to keyword ranking instead of catching an exception.

#### Scenario: An empty corpus succeeds with no results
- **WHEN** a semantic search is performed and no papers exist
- **THEN** the response status is 200
- **AND** the result list is empty

#### Scenario: A corpus with no compatible embeddings is refused
- **WHEN** a semantic search is performed, papers exist, and none carries an embedding
  from the configured model
- **THEN** the response status is 503
- **AND** the body explains that the corpus must be embedded

#### Scenario: An unloadable embedding provider is refused, not raised
- **WHEN** a semantic search is performed, papers exist, and the embedding provider
  cannot be loaded because its optional dependency is absent
- **THEN** the response status is 503
- **AND** the body explains that the provider could not be loaded
- **AND** no unhandled error reaches the caller

#### Scenario: A query matching nothing still succeeds
- **WHEN** a semantic search is performed against a compatible corpus
- **THEN** the response status is 200 regardless of how distant the nearest paper is

#### Scenario: The ranker raises nothing for an unusable corpus
- **WHEN** the semantic ranking callable is invoked against a corpus with no compatible
  embeddings
- **THEN** it returns an empty result
- **AND** it raises no exception


### Requirement: Stale embeddings are reported, never silently ranked

A corpus partially embedded by a superseded model SHALL be reported as an operational
condition rather than passing unnoticed, because such a corpus still returns a full page
of plausible results and so cannot be detected from the results themselves. The
condition SHALL be reported through the application log at most once per process, and
SHALL NOT be reported by failing an otherwise serviceable request.

Detection SHALL NOT be implemented as a system check that requires a database, so that
checks and migrations continue to run without a corpus.

#### Scenario: Drift is logged when semantic search first runs
- **WHEN** a semantic search is performed and some papers carry embeddings from a
  different model than the configured one
- **THEN** a warning naming the number of incompatible papers is written to the log

#### Scenario: The report does not repeat on every request
- **WHEN** several semantic searches are performed in one process against a drifted
  corpus
- **THEN** the warning is emitted once

#### Scenario: A drifted corpus still serves its compatible papers
- **WHEN** a semantic search is performed against a corpus where some papers are
  compatible and some are not
- **THEN** the response status is 200
- **AND** the compatible papers are ranked and returned

#### Scenario: Health reporting does not require a database at check time
- **WHEN** the project's system checks are run without a database
- **THEN** they succeed
- **AND** no check queries paper embeddings


### Requirement: The embedding model is loaded lazily, on first use

The embedding model SHALL NOT be loaded when the application starts, when management
commands run, or when the test suite runs, because loading it costs tens of seconds and
almost no command needs it. It SHALL be loaded on the first request that actually
requires a query embedding.

#### Scenario: Starting up loads no model
- **WHEN** the application is started or a management command unrelated to embedding is
  run
- **THEN** no embedding model is loaded

#### Scenario: The first semantic request loads the model
- **WHEN** the first semantic search of a process is performed
- **THEN** the provider is obtained and the query is embedded


### Requirement: Semantic mode is reachable from the demo page

The search page SHALL let a reader choose between keyword and semantic ranking, so that
the capability can be demonstrated without a command-line HTTP client. The chosen mode
SHALL be reflected in the rendered page.

#### Scenario: The page offers a mode choice
- **WHEN** the search page is rendered
- **THEN** it presents a control for choosing between keyword and semantic ranking

#### Scenario: Choosing semantic ranks by similarity
- **WHEN** a reader submits a query on the page with semantic ranking chosen
- **THEN** the page lists papers ranked by similarity to the query

#### Scenario: The page distinguishes an unusable corpus from a genuine miss
- **WHEN** semantic ranking is chosen on the page and the corpus cannot serve it
- **THEN** the page reports that semantic search is unavailable and names the operator
  action that resolves it
- **AND** it does not claim that no results were found


### Requirement: The capability is fully testable offline

No test of this capability SHALL perform a network request or load a real embedding
model. Tests SHALL use the fake provider and hand-written vectors, and SHALL cover the
nearest vector ranking first, papers with a null embedding being excluded, papers from a
different model being excluded, an unknown mode being refused, an empty corpus
succeeding, an incompatible corpus being refused, a drifted corpus still serving its
compatible papers, and an embedding provider that cannot be loaded being refused.

#### Scenario: The tests load no model and make no network request
- **WHEN** the project's tests are run
- **THEN** the semantic search tests contact no external service and load no embedding
  model

#### Scenario: The required cases are covered
- **WHEN** the semantic search tests are inspected
- **THEN** they cover the nearest vector ranking first, a null-embedding paper being
  excluded, a foreign-model paper being excluded, an unknown mode, an empty corpus, a
  corpus with no compatible embeddings, a drifted corpus still serving its compatible
  papers, and an embedding provider that cannot be loaded


### Requirement: The paraphrase advantage is demonstrated against the real corpus

The claim that semantic search finds papers keyword search misses SHALL be demonstrated
against the project's ingested corpus rather than against test fixtures, because it is a
property of a populated corpus and cannot be observed at a handful of rows. The query
used and the results both modes returned SHALL be recorded.

#### Scenario: The corpus is ingested and embedded before the claim is made
- **WHEN** the demonstration is performed
- **THEN** the corpus has been ingested and embedded by the project's management
  commands

#### Scenario: The comparison is recorded
- **WHEN** the demonstration is complete
- **THEN** the exact query, the papers semantic mode returned, and the papers keyword
  mode returned are recorded in the commit body
