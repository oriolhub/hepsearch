## ADDED Requirements

### Requirement: Two independent rankings are fused by rank, not by score

The system SHALL provide a hybrid ranking that combines the keyword and semantic
rankings by the *position* a paper occupies in each, using Reciprocal Rank Fusion. It
SHALL NOT combine the two rankings' scores, because relevance scoring and cosine
similarity occupy unrelated scales whose distributions would have to be known before
they could be normalized.

A paper found by both rankings SHALL outrank a paper found by only one at a comparable
position. A paper found by only one ranking SHALL still be eligible for the results, so
that neither ranking's exclusive discoveries are lost.

#### Scenario: A paper found by both rankings is promoted
- **WHEN** two papers are fused, one appearing in both ranked lists at a given position
  and one appearing in a single list at the same position
- **THEN** the paper appearing in both is ranked higher

#### Scenario: A paper found by only one ranking survives
- **WHEN** a paper appears in one ranked list and not the other
- **THEN** it is present in the fused results

#### Scenario: Scores from the two rankings are not compared
- **WHEN** the fusion implementation is inspected
- **THEN** it consumes the order of each ranking and not the scores those rankings
  produced

#### Scenario: Ordering is deterministic
- **WHEN** the same two ranked lists are fused twice
- **THEN** the fused order is identical
- **AND** papers whose fused scores are equal are ordered by a stated tie-break rather
  than arbitrarily

### Requirement: Fusion is a pure function over ranked identifier lists

The fusion SHALL be implemented as a function that accepts two ordered sequences of
paper identifiers and returns fused entries. It SHALL NOT query the database, load an
embedding model, read a request, or accept query text, so that its behaviour can be
established with hand-written lists of integers.

#### Scenario: Fusion is exercised with plain lists
- **WHEN** the fusion function is invoked with two lists of integers
- **THEN** it returns fused entries
- **AND** no database connection and no embedding model were required

#### Scenario: An empty list on either side is tolerated
- **WHEN** the fusion function is invoked with one empty sequence and one populated
  sequence
- **THEN** it returns the populated sequence's papers in their original relative order
- **AND** it raises no error

#### Scenario: Two empty lists yield no results
- **WHEN** the fusion function is invoked with two empty sequences
- **THEN** it returns no entries
- **AND** it raises no error

### Requirement: The fusion constant is justified by measurement against the real corpus

The Reciprocal Rank Fusion constant SHALL be a named constant, and its value SHALL be
justified by an observation recorded against the project's ingested corpus rather than
by citation alone, because the constant published for fusing many redundant retrieval
systems over deep result lists was measured to be wrong for fusing two deliberately
complementary rankings over a shallow candidate pool.

The justification SHALL claim no more than the evidence supports. Any per-method
weighting SHALL be omitted until a criterion fails without it.

#### Scenario: The constant is named and explained
- **WHEN** the fusion implementation is inspected
- **THEN** the constant is named rather than written inline at its point of use
- **AND** an accompanying comment states what was measured on this corpus, and does not
  claim the value is optimal

#### Scenario: The canonical value's failure is recorded
- **WHEN** the justification is read
- **THEN** it records that the canonical constant was observed to rank papers both
  rankings placed mid-list above the first pick of each ranking

#### Scenario: No weights are introduced without a failing criterion
- **WHEN** the fusion implementation is inspected
- **THEN** it applies no per-method weight

### Requirement: The candidate pool is bounded by what the vector index can return

Each ranking SHALL contribute a bounded number of candidates to the fusion, and that
bound SHALL be a named constant distinct from the number of results returned to the
caller, because fusion can only promote a paper that at least one ranking retrieved.

The bound SHALL NOT exceed the number of rows the approximate-nearest-neighbour index
will return for a single scan, because a larger bound is silently ineffective. The
constant SHALL carry a comment naming that coupling, so that raising it alone is not
mistaken for widening the pool. The system SHALL NOT alter the index's search parameter
per request.

#### Scenario: The candidate bound is separate from the result limit
- **WHEN** the configuration is inspected
- **THEN** the number of candidates collected per ranking is a constant distinct from
  the number of results returned to the caller

#### Scenario: The bound respects the vector index
- **WHEN** the candidate bound is compared with the approximate-nearest-neighbour
  index's configured scan width
- **THEN** the bound does not exceed it
- **AND** a comment records that exceeding it would have no effect

#### Scenario: The index search parameter is not tuned per request
- **WHEN** the statements issued for a hybrid request are inspected
- **THEN** none of them alters the index's search parameter

### Requirement: A hybrid request costs one query per ranking and no more

A hybrid request SHALL evaluate each underlying ranking once. It SHALL NOT issue a
further query to re-load the papers it has already retrieved, and SHALL NOT issue a
query per result. The papers presented SHALL be taken from the rows the two rankings
already returned.

Beyond the rankings themselves, a hybrid request SHALL issue no query other than the
corpus-health count that semantic ranking already requires, which is cached for the life
of the process and so is not paid per request.

Neither ranking SHALL load the embedding or the stored search vector columns, which are
large and which nothing downstream of ranking reads.

#### Scenario: One query per ranking serves a hybrid request
- **WHEN** a hybrid search is performed
- **THEN** the number of database queries issued is the number of rankings that ran,
  plus the cached corpus-health count
- **AND** no additional query is issued to fetch the fused papers

#### Scenario: No query is issued per result
- **WHEN** a hybrid search returns many papers
- **THEN** the number of queries does not grow with the number of results

#### Scenario: Large columns are not loaded
- **WHEN** the queries issued by a hybrid search are inspected
- **THEN** neither the embedding column nor the stored search vector column is selected

### Requirement: Hybrid degrades to keyword ranking when semantic ranking cannot run

A system that cannot embed SHALL still answer a hybrid request, because hybrid ranking
is what a caller who names no mode receives. When semantic ranking is unavailable — its
optional dependency is absent, or no paper carries an embedding from the configured
model — a hybrid request SHALL return the keyword ranking's results with a 200 status
and SHALL report that it was degraded.

A request that names semantic ranking explicitly SHALL continue to be refused with a 503
status, because that caller asked for something the system cannot do.

The degradation SHALL be visible. The system SHALL NOT present keyword-only results as
though both rankings had contributed.

A degradation SHALL leave a trace beyond the response. The system SHALL record a
provider outage, and SHALL report embeddings left behind by a model change, on the
hybrid path exactly as it does on the semantic path, because hybrid is what an
unqualified request receives and a fault that only ever answers 200 would otherwise go
unnoticed.

#### Scenario: A missing embedding dependency degrades rather than refuses
- **WHEN** a hybrid search is performed and the embedding provider cannot be loaded
- **THEN** the response status is 200
- **AND** the keyword ranking's papers are returned
- **AND** the response reports that the results were degraded and why

#### Scenario: An unembedded corpus degrades rather than refuses
- **WHEN** a hybrid search is performed, papers exist, and none carries an embedding
  from the configured model
- **THEN** the response status is 200
- **AND** the keyword ranking's papers are returned
- **AND** the response reports that the results were degraded and why

#### Scenario: Explicit semantic ranking is still refused
- **WHEN** a search naming semantic ranking is performed and semantic ranking cannot run
- **THEN** the response status is 503

#### Scenario: Degradation is never silent
- **WHEN** a hybrid search returns keyword-only results because semantic ranking could
  not run
- **THEN** the response distinguishes those results from results both rankings produced

#### Scenario: A genuinely empty corpus is not a degradation
- **WHEN** a hybrid search is performed and no papers exist at all
- **THEN** the response status is 200
- **AND** the results are empty
- **AND** no degradation is reported

#### Scenario: A degraded hybrid request is recorded
- **WHEN** a hybrid search degrades because the embedding provider could not be loaded
- **THEN** the failure is recorded in the application log

#### Scenario: Stale embeddings are reported on the hybrid path
- **WHEN** a hybrid search runs against a corpus holding embeddings from a retired model
- **THEN** the drift is reported as it is for an explicit semantic search

### Requirement: Each result reports which rankings found it

Every hybrid result SHALL name the ranking or rankings that retrieved it, alongside its
fused score, so that a reader can tell an exact-term match from a semantic one and can
see which papers both rankings agreed on.

The per-ranking positions that produced the fused score SHALL NOT be part of the
response, because they are internal diagnostics and each ranking can be queried directly
when they are wanted. The fused score SHALL carry the fusion's own scale and SHALL NOT
be assumed comparable with the scores of either underlying ranking.

#### Scenario: A result found by both rankings says so
- **WHEN** a hybrid result is inspected for a paper both rankings retrieved
- **THEN** it names both rankings

#### Scenario: A result found by one ranking names only that one
- **WHEN** a hybrid result is inspected for a paper only one ranking retrieved
- **THEN** it names that ranking alone

#### Scenario: The fused score is reported
- **WHEN** a hybrid result is inspected
- **THEN** it carries the score fusion assigned it

#### Scenario: Per-ranking positions are not exposed
- **WHEN** a hybrid response is inspected
- **THEN** it contains no per-ranking position for any result

### Requirement: Hybrid ranking is the page's default and its degradation is visible

The search page SHALL offer hybrid ranking among its choices and SHALL select it when
the reader has expressed no preference, so that the page and the API agree on what an
unqualified search means.

When hybrid results were degraded to keyword-only, the page SHALL say so, and SHALL NOT
present them as though semantic ranking had contributed.

#### Scenario: The page offers hybrid and selects it by default
- **WHEN** the search page is rendered without a mode
- **THEN** hybrid is among the available choices
- **AND** it is the selected one

#### Scenario: The page ranks by hybrid when no mode is chosen
- **WHEN** a reader submits a query on the page without choosing a mode
- **THEN** the papers listed are those hybrid ranking produces

#### Scenario: The page announces a degraded result set
- **WHEN** the page renders hybrid results that were degraded to keyword-only
- **THEN** it tells the reader that semantic ranking was unavailable
- **AND** it does not claim that no results were found

#### Scenario: A degraded page with no keyword hits does not claim an empty corpus
- **WHEN** hybrid ranking is degraded and the keyword ranking matched nothing
- **THEN** the page reports the degradation
- **AND** it does not claim that no results were found, because nothing was fully
  searched

### Requirement: The capability is fully testable offline

No test of this capability SHALL perform a network request or load a real embedding
model. The fusion function SHALL be covered without a database, including dual-hit
promotion, single-ranking survival, tie handling, and an empty sequence on either side.

Integration tests SHALL establish that hybrid returns results when either ranking alone
returns none, that a hybrid request degrades rather than failing when semantic ranking
cannot run, and that an explicit semantic request still fails in the same circumstances.

#### Scenario: The tests load no model and make no network request
- **WHEN** the project's tests are run
- **THEN** the hybrid ranking tests contact no external service and load no embedding
  model

#### Scenario: The fusion cases are covered without a database
- **WHEN** the fusion tests are inspected
- **THEN** they cover dual-hit promotion, a paper found by one ranking surviving, equal
  fused scores being broken deterministically, and an empty sequence on either side
- **AND** none of them requires a database

#### Scenario: One ranking finding nothing is covered
- **WHEN** the integration tests are inspected
- **THEN** they establish that hybrid returns results when keyword ranking matches
  nothing, and when semantic ranking contributes nothing

#### Scenario: Degradation and refusal are both covered
- **WHEN** the integration tests are inspected
- **THEN** they establish that a hybrid request degrades with a 200 when semantic
  ranking cannot run, and that a semantic request is refused with a 503 in the same
  circumstances

### Requirement: Hybrid ranking is compared against both rankings on the real corpus

The claim that hybrid ranking is not worse than either ranking alone SHALL be
demonstrated against the project's ingested corpus rather than against test fixtures,
because it is a property of a populated corpus and cannot be observed at a handful of
rows. At least three queries SHALL be compared: one exact-term query, one paraphrase,
and one mixing the two. The queries and the papers each mode returned SHALL be recorded.

The comparison SHALL NOT use an exact-identifier query. Identifiers are absent from the
full-text index, so neither ranking retrieves the paper they name, and fusion cannot
rank a paper neither ranking returned. Such a comparison would be satisfied vacuously.
The reason for the substitution SHALL be recorded alongside the comparison.

#### Scenario: The corpus is ingested and embedded before the claim is made
- **WHEN** the comparison is performed
- **THEN** the corpus has been ingested and embedded by the project's management
  commands

#### Scenario: Three query kinds are compared
- **WHEN** the comparison is performed
- **THEN** it covers an exact-term query, a paraphrase, and a query mixing the two

#### Scenario: The comparison is recorded
- **WHEN** the comparison is complete
- **THEN** the exact queries and the papers keyword, semantic and hybrid ranking each
  returned are recorded in the commit body

#### Scenario: The identifier substitution is explained
- **WHEN** the recorded comparison is read
- **THEN** it states that an exact-identifier query was not used, and that identifiers
  are not present in the full-text index
