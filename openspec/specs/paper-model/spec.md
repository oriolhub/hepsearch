# paper-model Specification

## Purpose
TBD - created by archiving change paper-domain-model. Update Purpose after archive.
## Requirements
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

### Requirement: Paper record and its natural key

The system SHALL provide a `Paper` model in `apps/papers` representing one INSPIRE-HEP
literature record. Each `Paper` SHALL carry `inspire_id`, INSPIRE's `control_number`,
as a unique indexed integer field. The model SHALL use Django's default surrogate
primary key; `inspire_id` SHALL NOT be the primary key.

#### Scenario: A paper is stored and retrieved by its INSPIRE id
- **WHEN** a `Paper` is created with `inspire_id=1234567`, a title and an abstract
- **THEN** it is persisted
- **AND** `Paper.objects.get(inspire_id=1234567)` returns it
- **AND** its `pk` is a database-generated integer distinct from `inspire_id`

#### Scenario: Two papers cannot share an INSPIRE id
- **WHEN** a second `Paper` is saved with an `inspire_id` that already exists
- **THEN** the database SHALL reject it with an `IntegrityError`
- **AND** the first paper SHALL remain unchanged

#### Scenario: The natural key is indexed for upsert
- **WHEN** the model's `inspire_id` field is inspected
- **THEN** it SHALL be declared unique, so that ingestion can upsert on it without a
  full table scan

### Requirement: Every paper has a non-empty abstract, enforced by the database

The system SHALL enforce, with a database `CheckConstraint`, that a `Paper`'s abstract
is never the empty string. This invariant SHALL NOT depend on application-level
validation, because a paper without an abstract cannot be embedded and would pollute
search results.

#### Scenario: A paper with an empty abstract is rejected
- **WHEN** a `Paper` is saved with `abstract=""`
- **THEN** the database SHALL reject it with an `IntegrityError`

#### Scenario: The constraint survives paths that skip model validation
- **WHEN** a `Paper` with an empty abstract is written by a path that does not call
  `full_clean()`, such as `bulk_create()` or a raw insert
- **THEN** it SHALL still be rejected by the database

#### Scenario: A paper with an abstract is accepted
- **WHEN** a `Paper` is saved with a non-empty abstract
- **THEN** it is persisted without error

### Requirement: Unbounded text fields for externally supplied prose

`title` and `abstract` SHALL be stored as unbounded text, with no `max_length`, because
INSPIRE publishes no bound on either and a guessed limit would fail at ingestion time.
Both SHALL be required.

#### Scenario: A long title is stored intact
- **WHEN** a `Paper` is saved with a title of 300 characters
- **THEN** the stored title equals the supplied title exactly, with no truncation

#### Scenario: A long abstract is stored intact
- **WHEN** a `Paper` is saved with an abstract of 6,000 characters
- **THEN** the stored abstract equals the supplied abstract exactly, with no truncation

### Requirement: Optional metadata is present but absence-tolerant

The system SHALL store `arxiv_id`, `doi`, `journal` and `earliest_date` as optional
strings, and `citation_count` as an optional integer. Absent string values SHALL be
represented by the empty string and SHALL NOT be nullable, in line with the repository's
enabled `DJ001` lint rule. `citation_count` SHALL be nullable, so that "no citation
count was supplied" is distinguishable from a genuine count of zero.

#### Scenario: A preprint with no DOI, journal or citation count is stored
- **WHEN** a `Paper` is saved with only `inspire_id`, `title` and `abstract` supplied
- **THEN** it is persisted
- **AND** `doi`, `journal`, `arxiv_id` and `earliest_date` are each `""`
- **AND** `citation_count` is `None`
- **AND** `authors` and `categories` are each an empty list

#### Scenario: A cited paper distinguishes zero from unknown
- **WHEN** one `Paper` is saved with `citation_count=0` and another with
  `citation_count=None`
- **THEN** the two values are stored and read back distinctly

#### Scenario: No string field permits NULL
- **WHEN** the model's character and text fields are inspected
- **THEN** none of them SHALL declare `null=True`

### Requirement: Dates are stored exactly as INSPIRE supplies them

The system SHALL store the record's earliest known date in a field named
`earliest_date`, as a string holding INSPIRE's ISO-8601 prefix verbatim. The system
SHALL NOT pad a partial date to a full date, and SHALL NOT name this field
`publication_date`, because the measured value disagrees with the publication year for
a substantial minority of records.

#### Scenario: A year-only date is preserved
- **WHEN** a `Paper` is saved with `earliest_date="2014"`
- **THEN** reading it back yields exactly `"2014"`, not `"2014-01-01"`

#### Scenario: A year-month date is preserved
- **WHEN** a `Paper` is saved with `earliest_date="2012-07"`
- **THEN** reading it back yields exactly `"2012-07"`

#### Scenario: A full date is preserved
- **WHEN** a `Paper` is saved with `earliest_date="2016-10-25"`
- **THEN** reading it back yields exactly `"2016-10-25"`

#### Scenario: A missing date is empty, not fabricated
- **WHEN** a `Paper` is saved with no date supplied
- **THEN** `earliest_date` is `""`

### Requirement: All authors and categories are retained as lists

The system SHALL store every author name supplied for a paper, as an ordered list, with
no cap. It SHALL likewise store the paper's arXiv subject categories as a list of short
identifiers. Neither list SHALL be nullable; absence is an empty list.

#### Scenario: A collaboration paper with thousands of authors is stored whole
- **WHEN** a `Paper` is saved with 5,200 author names
- **THEN** all 5,200 names are persisted
- **AND** reading the paper back returns them in the order supplied

#### Scenario: Categories are stored as a list
- **WHEN** a `Paper` is saved with `categories=["hep-ph", "hep-ex"]`
- **THEN** reading it back returns that list

#### Scenario: List fields default to empty, not shared
- **WHEN** two `Paper` instances are created without supplying `authors`
- **AND** a name is appended to the first instance's list
- **THEN** the second instance's `authors` is still empty

### Requirement: A paper links back to its INSPIRE record

Each `Paper` SHALL expose the canonical INSPIRE URL for the record, derived from
`inspire_id`. The URL SHALL be available from the model itself so that the admin, the
API and the results page share one derivation.

#### Scenario: The INSPIRE URL is derived from the natural key
- **WHEN** a `Paper` with `inspire_id=1234567` is asked for its INSPIRE URL
- **THEN** it returns `https://inspirehep.net/literature/1234567`
- **AND** the URL is built from `inspire_id`, never from the surrogate primary key

### Requirement: Long author lists are summarised for display

The system SHALL provide a display summary of a paper's authors that names the first
few and indicates how many there are in total, so that no interface has to render
thousands of names. The summary SHALL be provided by the model, not duplicated per
consumer.

Names SHALL be separated by a semicolon because INSPIRE supplies names as
`"Last, First"`, making comma-separated author boundaries ambiguous. The number of
leading names SHALL be a parameter with a default, so each consumer can choose its
density at the call site.

#### Scenario: A short author list is shown in full
- **WHEN** a paper with two authors is summarised
- **THEN** both names appear
- **AND** no total count is appended

#### Scenario: A long author list is truncated with a total
- **WHEN** a paper with 2,881 authors is summarised
- **THEN** only the leading names appear
- **AND** the summary indicates the full total of 2,881

#### Scenario: A paper with no authors summarises safely
- **WHEN** a paper with an empty author list is summarised
- **THEN** it returns an empty or placeholder string without raising

#### Scenario: Author boundaries are unambiguous
- **WHEN** a paper whose authors are stored as `"Last, First"` is summarised
- **THEN** the separator between two authors is distinguishable from the comma inside a
  single author's name

#### Scenario: The number of names is chosen by the caller
- **WHEN** a consumer asks for a summary of a given number of leading names
- **THEN** at most that many names appear
- **AND** a consumer that asks for no particular number receives the default

### Requirement: A paper presents its date at the precision actually stored

Each `Paper` SHALL expose a human-readable rendering of `earliest_date` that reflects
only the precision stored: a full date renders as a full date, a year and month render
as a month and year, and a year alone renders as a year alone. The rendering SHALL NOT
fabricate an unknown month or day. A missing date SHALL render as an empty value without
raising.

#### Scenario: A full date renders in full
- **WHEN** a paper stores `earliest_date="2016-10-25"`
- **THEN** its display date names that day, month and year

#### Scenario: A year-and-month date renders without a day
- **WHEN** a paper stores `earliest_date="2012-07"`
- **THEN** its display date names that month and year
- **AND** no day appears

#### Scenario: A year-only date renders as a year
- **WHEN** a paper stores `earliest_date="2014"`
- **THEN** its display date is that year alone
- **AND** neither a month nor a day appears

#### Scenario: A missing date renders empty
- **WHEN** a paper stores `earliest_date=""`
- **THEN** its display date is empty
- **AND** no error is raised

#### Scenario: The stored value is untouched
- **WHEN** a paper's display date has been read
- **THEN** `earliest_date` still holds INSPIRE's original string verbatim

### Requirement: A paper offers a bounded excerpt of its abstract

Each `Paper` SHALL expose a bounded excerpt of its abstract, cut at a word boundary and
marked when it has been shortened, so that the API and results page abbreviate an
abstract identically. The bound SHALL come from the project's named excerpt setting.

#### Scenario: A long abstract is excerpted at a word boundary
- **WHEN** a paper's abstract exceeds the configured bound
- **THEN** its excerpt is no longer than that bound
- **AND** it ends at a word boundary
- **AND** it is marked as continuing

#### Scenario: A short abstract is offered whole
- **WHEN** a paper's abstract is shorter than the configured bound
- **THEN** its excerpt is the entire abstract
- **AND** it is not marked as continuing

#### Scenario: The bound is configurable
- **WHEN** the configured excerpt bound is changed
- **THEN** the length of the excerpt changes accordingly, with no code change

### Requirement: A paper offers a display summary of its authors for result listings

Each `Paper` SHALL expose an author summary sized for a results listing, so a template
can render it without passing arguments and every listing agrees on how many names to
show. A paper with no authors SHALL yield an empty value.

#### Scenario: A listing summary names several leading authors
- **WHEN** a paper with many authors is asked for its listing author summary
- **THEN** more names appear than the bare default used by a dense admin column
- **AND** the true total is stated

#### Scenario: A paper with no authors yields an empty summary
- **WHEN** a paper with an empty author list is asked for its listing author summary
- **THEN** the result is empty
- **AND** no error is raised

#### Scenario: The summary needs no arguments
- **WHEN** a template renders the listing author summary
- **THEN** it obtains it without supplying any argument

### Requirement: Papers are inspectable in the Django admin

The system SHALL register `Paper` in the Django admin with a list view that shows the
paper's identity, date and citation count, a summarised author column, and a search box
covering title, abstract and INSPIRE id. The admin SHALL NOT render full author lists in
the list view.

#### Scenario: The changelist renders for a paper with thousands of authors
- **WHEN** an admin user opens the `Paper` changelist and the corpus contains a paper
  with 5,154 authors
- **THEN** the page renders successfully
- **AND** the author column shows the truncated summary, not every name

#### Scenario: An admin searches for a paper
- **WHEN** an admin user searches the `Paper` changelist by a word from a paper's title
- **THEN** that paper appears in the results

### Requirement: The schema is delivered by a committed migration

The system SHALL ship an initial migration for `apps/papers` that creates the papers
table, its unique index and its check constraint. The committed migrations SHALL be
complete: no model change may remain unmigrated.

#### Scenario: The migration applies to an empty database
- **WHEN** `migrate` is run against a database with no papers table
- **THEN** the migration applies without error
- **AND** the table, the unique index on `inspire_id` and the abstract check constraint
  all exist

#### Scenario: Migrations are idempotent
- **WHEN** `migrate` is run a second time
- **THEN** it reports no work to do

#### Scenario: No model change is left unmigrated
- **WHEN** `makemigrations --check --dry-run` is run
- **THEN** it reports that no new migrations are needed

### Requirement: The domain app remains dependency-free

`apps/papers` SHALL NOT import from `apps/ingestion` or `apps/search`, and SHALL NOT
parse INSPIRE API payloads. Adding the `Paper` model SHALL NOT require changes to the
project's installed applications or settings.

#### Scenario: The domain app imports nothing from its dependants
- **WHEN** the modules in `apps/papers` are inspected
- **THEN** none of them imports `apps.ingestion` or `apps.search`

#### Scenario: No settings change is required
- **WHEN** this change is applied
- **THEN** `config/settings.py` is unmodified
- **AND** the existing health check and test suite continue to pass
