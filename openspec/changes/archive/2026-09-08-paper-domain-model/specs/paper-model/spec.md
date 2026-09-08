## ADDED Requirements

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
