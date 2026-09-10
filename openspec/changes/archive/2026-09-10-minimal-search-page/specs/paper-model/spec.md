## MODIFIED Requirements

### Requirement: Long author lists are summarised for display

The system SHALL provide a display summary of a paper's authors that names the first
few and indicates how many there are in total, so that no interface has to render
thousands of names. The summary SHALL be provided by the model, not duplicated per
consumer.

Names SHALL be separated by a character sequence that does not itself occur inside a
name. INSPIRE supplies each author as `"Last, First"`, so joining with a comma makes the
boundary between two authors indistinguishable from the boundary inside one, and a
summary of five authors reads as ten. The separator SHALL therefore be a semicolon.

The number of leading names SHALL be a parameter with a default, so that a consumer
needing a different density — a dense admin column against a results page — chooses it
at the call site rather than forcing one length on every caller.

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

## ADDED Requirements

### Requirement: A paper presents its date at the precision actually stored

Each `Paper` SHALL expose a human-readable rendering of `earliest_date` that reflects
only the precision stored: a full date renders as a full date, a year and month render
as a month and year, and a year alone renders as a year alone. The rendering SHALL NOT
fabricate an unknown month or day.

This exists on the model, alongside the INSPIRE URL and the author summary, so that
every human-facing consumer derives it once rather than each inventing its own. A
missing date SHALL render as an empty value without raising.

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
marked when it has been shortened, so that the API and the results page abbreviate an
abstract identically rather than each choosing its own rule. The bound SHALL come from
the project's named excerpt setting rather than being written into the model.

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

Each `Paper` SHALL expose an author summary sized for a results listing, so that a
template can render it without passing arguments and every listing agrees on how many
names to show. A paper with no authors SHALL yield an empty value, so that a consumer
can omit the author line entirely rather than render an empty label.

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
