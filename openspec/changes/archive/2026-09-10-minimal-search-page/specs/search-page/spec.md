## ADDED Requirements

### Requirement: The corpus is searchable from a web page

The system SHALL serve a page at the site root that presents a search box and a submit
control, so that the corpus is reachable by someone who does not write HTTP requests.
The page SHALL be rendered on the server as HTML and SHALL require no client-side
framework and no build step.

The form SHALL submit by `GET`, carrying the query in a parameter named `q`, so that a
search is a shareable, bookmarkable address and the browser's history and back button
behave as a reader expects.

#### Scenario: The root address serves the page
- **WHEN** a visitor requests the site root
- **THEN** the response status is 200
- **AND** the body is HTML containing a text input for the query and a control to
  submit it

#### Scenario: A search is addressable
- **WHEN** a visitor submits the form with a query
- **THEN** the resulting address carries that query in its query string
- **AND** requesting that address directly reproduces the same results

#### Scenario: The page needs no credentials
- **WHEN** a visitor requests the page without authenticating
- **THEN** the request succeeds

#### Scenario: The page requires no client-side framework
- **WHEN** the delivered page is inspected
- **THEN** it renders its results without executing client-side code

### Requirement: The page reuses the search function rather than reimplementing it

The page SHALL obtain its results by calling the same ranking function the HTTP API
calls. It SHALL NOT contain its own ranking, ordering or matching logic, so that the
page and the API can never disagree about which papers are relevant or in what order.

The page SHALL bound its results using the same named project setting the API uses.

#### Scenario: One ranking, two surfaces
- **WHEN** the same query is submitted to the page and to the API
- **THEN** both report the same papers in the same order

#### Scenario: The page contains no ranking logic
- **WHEN** the page's view is inspected
- **THEN** it delegates matching and ordering to the shared ranking function

#### Scenario: The page honours the shared result cap
- **WHEN** a query matches more papers than the configured cap
- **THEN** the page shows no more results than that cap

#### Scenario: The page does not call itself over HTTP
- **WHEN** the page's view is inspected
- **THEN** it invokes the ranking function directly rather than issuing a request to
  the API

### Requirement: A result on the page is legible at a glance

Each result SHALL show the paper's title as a link to its INSPIRE record, a summary of
its authors, its publication date, and an excerpt of its abstract.

The author summary SHALL name only the leading authors and state the true total when
there are more, so that a paper with thousands of authors occupies the same space as a
paper with two. A paper with no authors SHALL render no author line at all rather than
an empty label or a placeholder.

#### Scenario: A result shows the expected fields
- **WHEN** a query matches a paper
- **THEN** the rendered result shows its title, an author summary, its date and an
  abstract excerpt

#### Scenario: The title links to INSPIRE
- **WHEN** a result's title link is inspected
- **THEN** it addresses the INSPIRE literature record for that paper

#### Scenario: A collaboration paper does not flood the page
- **WHEN** a matched paper has thousands of authors
- **THEN** only the leading names are shown
- **AND** the total number of authors is stated

#### Scenario: A paper with no authors shows no author line
- **WHEN** a matched paper has an empty author list
- **THEN** no author line is rendered
- **AND** the result still shows its title, date and excerpt

#### Scenario: A long abstract is excerpted on the page
- **WHEN** a matched paper's abstract exceeds the excerpt bound
- **THEN** the page shows a bounded excerpt marked as continuing

### Requirement: The page states a date only as precisely as it is known

The corpus stores dates at differing precision. The page SHALL present each date at the
precision actually stored — a year alone, a month and year, or a full date — and SHALL
NOT fill an unknown month or day with a default, because a reader takes a rendered day
and month as a statement of fact about the paper.

#### Scenario: A full date is shown in full
- **WHEN** a matched paper stores a complete date
- **THEN** the page shows that day, month and year

#### Scenario: A year-and-month date shows no day
- **WHEN** a matched paper stores only a year and a month
- **THEN** the page shows that month and year
- **AND** no day appears

#### Scenario: A year-only date shows only the year
- **WHEN** a matched paper stores only a year
- **THEN** the page shows that year alone
- **AND** neither a month nor a day appears

#### Scenario: A missing date renders nothing rather than breaking
- **WHEN** a matched paper stores no date
- **THEN** the result renders without a date
- **AND** the page is still returned successfully

### Requirement: The query a visitor typed survives the round trip

After a search is submitted, the page SHALL redisplay the submitted query in the search
input, so that a visitor can refine what they typed instead of retyping it.

#### Scenario: The query is still in the box
- **WHEN** a visitor submits a query
- **THEN** the rendered page's search input contains that query

#### Scenario: A query that matched nothing is still redisplayed
- **WHEN** a visitor submits a query that matches no paper
- **THEN** the search input still contains that query

### Requirement: An empty submission and an unmatched query are answered differently

A request carrying no query, or a query consisting only of whitespace, SHALL re-render
the page with the search form and no results, and SHALL NOT present an error, because
pressing submit on an empty box is not a mistake worth reporting. This SHALL be
indistinguishable from a first visit to the page.

A request carrying a real query that matches no paper SHALL render an explicit message
saying so, rather than an apparently empty page that leaves the visitor unsure whether
the search ran.

#### Scenario: A first visit shows only the form
- **WHEN** the page is requested with no query
- **THEN** the response status is 200
- **AND** the form is shown with no results and no error

#### Scenario: An empty submission is not an error
- **WHEN** the page is requested with an empty query
- **THEN** the response status is 200
- **AND** no error is shown

#### Scenario: A whitespace-only submission is not an error
- **WHEN** the page is requested with a query of only spaces
- **THEN** the response status is 200
- **AND** no error is shown

#### Scenario: An empty submission is not reported as "no results"
- **WHEN** the page is requested with an empty or whitespace-only query
- **THEN** no "no results" message is shown

#### Scenario: A query matching nothing says so
- **WHEN** a visitor submits a real query that matches no paper
- **THEN** the response status is 200
- **AND** the page states that nothing was found

### Requirement: Text supplied by a visitor is rendered as text

All visitor-supplied text rendered by the page, including the redisplayed query, SHALL
be escaped so that it appears as literal characters and cannot be interpreted as markup
or script by the browser.

#### Scenario: A script tag renders as text
- **WHEN** a visitor submits a query containing `<script>`
- **THEN** the response body does not contain an executable script element from that
  query
- **AND** the query appears as escaped, literal text

#### Scenario: Escaping survives redisplay
- **WHEN** a query containing markup is redisplayed in the search input
- **THEN** it is escaped there as well

#### Scenario: Markup in stored paper text is escaped
- **WHEN** a rendered paper's title or abstract contains characters significant to HTML
- **THEN** they are escaped in the response

### Requirement: The page is covered by tests that need no network

Tests SHALL exercise the page through the request layer and SHALL contact no external
service. They SHALL cover a query rendering the expected paper titles in the HTML, a
query containing `<script>` being escaped, the zero-result message, and an empty
submission producing neither an error nor a zero-result message.

#### Scenario: The page tests make no network request
- **WHEN** the project's tests are run
- **THEN** the page tests contact no external service

#### Scenario: Rendered titles are asserted
- **WHEN** the page tests are inspected
- **THEN** at least one submits a query and asserts the expected paper titles appear in
  the HTML

#### Scenario: Escaping is asserted
- **WHEN** the page tests are inspected
- **THEN** at least one submits a query containing `<script>` and asserts it is escaped
