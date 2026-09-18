## Purpose

The search page presents ranked papers so that a physicist can assess relevance quickly.
This capability owns presentation concerns: excerpts and highlighting, result metadata,
external links, method attribution, author truncation, responsive layout, and the
user-facing reporting of what was retrieved and how long it took.

It deliberately does not own every behaviour of the page. Retrieval mode semantics,
degradation behaviour, navigation state preservation and operational limits remain with
the capabilities that specify them: that an unqualified search means hybrid and that
hybrid degradation is announced belong to `hybrid-search`; that semantic mode is
reachable and its outage is reported belongs to `semantic-search`; that navigation
preserves the query and mode, and that the page is throttled, belong to `api-hardening`.
Their absence here is a boundary, not a gap.

## Requirements

### Requirement: The page presents enough of a paper to judge it

The search page SHALL present each result with the paper's title, its authors, its date,
its citation count, a publication identifier and an excerpt of its abstract, so that a
reader can assess relevance without opening the paper.

Author lists SHALL be truncated to a readable prefix with the full count stated, because
collaboration papers in the corpus carry thousands of authors and an untruncated list
would displace every other result on the page.

The publication identifier SHALL fall back through the sources the corpus actually
carries — journal reference, else arXiv identifier, else DOI — because a substantial
minority of papers have neither a journal nor an arXiv identifier and would otherwise
show an empty line.

#### Scenario: A result carries the fields needed to judge it
- **WHEN** the page renders a result
- **THEN** it shows the title, authors, date, citation count, a publication identifier
  where one exists, and an abstract excerpt

#### Scenario: A paper with thousands of authors does not swamp the page
- **WHEN** a result's paper has more authors than the display limit
- **THEN** only the leading authors are named
- **AND** the total number of authors is stated

#### Scenario: A preprint without a journal still shows an identifier
- **WHEN** a result's paper has no journal reference
- **THEN** its arXiv identifier is shown if it has one
- **AND** otherwise its DOI is shown if it has one
- **AND** otherwise no publication identifier is shown, with no empty label left behind

#### Scenario: An uncited paper says so
- **WHEN** a result's paper has zero citations
- **THEN** the page states that it has zero citations rather than omitting the count

### Requirement: Every result links out to the sources it came from

The search page SHALL link each result to its INSPIRE record, and SHALL additionally
link to arXiv when the paper has an arXiv identifier. The page is a retrieval aid, not a
destination; a reader who finds the right paper must be able to leave for the authority
immediately.

#### Scenario: Every result reaches INSPIRE
- **WHEN** the page renders a result
- **THEN** it offers a link to that paper's INSPIRE record

#### Scenario: A paper with a preprint reaches arXiv
- **WHEN** a result's paper has an arXiv identifier
- **THEN** the page additionally offers a link to that paper on arXiv

#### Scenario: A paper without a preprint offers no broken link
- **WHEN** a result's paper has no arXiv identifier
- **THEN** no arXiv link is rendered

### Requirement: The excerpt shows why the paper was retrieved

The search page SHALL excerpt each abstract around the terms the query matched, and
SHALL highlight those terms, so that a reader sees the matching passage rather than the
paper's opening sentence.

Matching SHALL be performed with the same text-search configuration that produced the
ranking, so that a highlighted term is a term the ranking actually scored. Highlighting
therefore follows word stems: a query for one inflection highlights the others.

Where the query matched nothing in a paper's text — which is the normal case for a
result found only by semantic similarity — the page SHALL still show an excerpt, without
highlighting and without any error or empty state.

#### Scenario: Matched terms are marked in the excerpt
- **WHEN** a result's abstract contains a term from the query
- **THEN** the excerpt is drawn from around that term
- **AND** the term is visually marked within the excerpt

#### Scenario: Related word forms are marked too
- **WHEN** a query term and an abstract term share a stem but differ in inflection
- **THEN** the abstract term is marked

#### Scenario: A semantically matched paper still shows an excerpt
- **WHEN** a result's abstract contains no term from the query
- **THEN** an excerpt of the abstract is shown with nothing marked
- **AND** no placeholder or error is shown in its place

#### Scenario: Excerpting does not cost an extra query
- **WHEN** a page of results is rendered
- **THEN** the number of database queries is unchanged from a page rendered without
  excerpting

### Requirement: Highlighting can never inject markup

The search page SHALL escape all paper text and all query text before any highlighting
markup is introduced, and SHALL introduce markup only by replacing markers it generated
itself.

The safety of highlighting SHALL NOT depend on any sanitising behaviour of the database,
the template engine's autoescaping of an already-marked-safe string, or the absence of
markup in the corpus. A reader must be unable to cause markup to render by choosing a
query, and an ingested paper must be unable to cause markup to render through its own
text.

#### Scenario: A query containing markup renders as text
- **WHEN** a user searches for a term containing HTML tags, such as a script tag
- **THEN** the page renders that text literally
- **AND** no element from the query is added to the document

#### Scenario: A paper containing markup renders as text
- **WHEN** a result's title or abstract contains HTML tags
- **THEN** the page renders that text literally
- **AND** no element from the paper is added to the document

#### Scenario: Only generated markers become markup
- **WHEN** highlighting is applied
- **THEN** the text is escaped in full first
- **AND** only the system's own highlight markers are afterwards turned into markup

### Requirement: The page states which ranking found each result

The search page SHALL show, for every result and in every search mode, which ranking
method retrieved it.

This is not decoration. Under hybrid ranking roughly half of a page is retrieved by
semantic similarity alone, and those results by definition contain none of the reader's
words and carry no highlighting. Without an attribution they are indistinguishable from
a ranking defect; with one they are the demonstration the system exists to give.

#### Scenario: A hybrid result names its origin
- **WHEN** the page renders a result from a hybrid search
- **THEN** it states whether that result was found by keyword ranking, by semantic
  ranking, or by both

#### Scenario: Attribution is shown in single-mode searches too
- **WHEN** the page renders a result from a keyword-only or semantic-only search
- **THEN** it states the method that found it

#### Scenario: A result with no highlighted terms is explained
- **WHEN** a result was found only by semantic ranking and its excerpt has nothing marked
- **THEN** the page identifies it as semantically matched

### Requirement: The page reports what it retrieved and how long it took

The search page SHALL state how many results were retrieved, which range of them is
being shown, and how long the search took.

The reported total SHALL be the number of results retrieved within the system's
retrieval bound, and SHALL be labelled as such. It SHALL NOT be presented as the number
of papers in the corpus matching the query, which the system does not know and is
forbidden to count.

The reported duration SHALL be the real elapsed time of the search as performed, and
SHALL NOT exclude any work the reader waited for. A search that was slow because a model
had to be loaded is reported as slow.

#### Scenario: The page states its position in the results
- **WHEN** a page of results is rendered
- **THEN** it states which range of retrieved results is shown and how many were
  retrieved in total

#### Scenario: The total is labelled as retrieved, not as matched
- **WHEN** a query matches far more papers than the retrieval bound
- **THEN** the figure shown is the number retrieved
- **AND** it is described in terms of retrieval rather than as a count of matching papers

#### Scenario: The elapsed time is the time the reader waited
- **WHEN** a search takes an unusually long time, including because a model was loaded
  during it
- **THEN** the duration shown reflects that time
- **AND** no faster figure measuring only part of the work is shown instead

### Requirement: A search that finds nothing says what to do next

The search page SHALL, when a search returns no results, state that nothing was found
and suggest rephrasing the query. It SHALL NOT render an empty results area, and SHALL
NOT present the absence of results as an error.

#### Scenario: An unmatched query is explained
- **WHEN** a search returns no results
- **THEN** the page states that no papers were found
- **AND** it suggests rephrasing the query

#### Scenario: An unsearched page is not an empty result
- **WHEN** the page is opened without a query
- **THEN** no zero-result message is shown

### Requirement: The page is readable in a narrow window

The search page SHALL remain readable and usable when the window is too narrow for a
desktop layout: text SHALL NOT be clipped or require horizontal scrolling, and the
search form and mode selector SHALL remain operable.

This SHALL be achieved without JavaScript and without a build step.

#### Scenario: A narrow window reflows rather than clips
- **WHEN** the page is viewed in a narrow window
- **THEN** result text wraps within the available width
- **AND** no horizontal scrolling is needed to read a result

#### Scenario: The form stays usable when narrow
- **WHEN** the page is viewed in a narrow window
- **THEN** the query field and the mode selector remain visible and operable

#### Scenario: No client-side tooling is introduced
- **WHEN** the page's assets are inspected
- **THEN** the layout is achieved with stylesheet rules alone
- **AND** no JavaScript and no build step is required to render the page
