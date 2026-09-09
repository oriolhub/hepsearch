## 1. Schema: the generated search vector

- [x] 1.1 Add a `SEARCH_CONFIG = "english"` constant in `apps/papers` and use it as the
      single source of the text search configuration
- [x] 1.2 Add `search_vector` to `Paper` as a `GeneratedField` with `db_persist=True`,
      whose expression is `setweight(to_tsvector(config, title), 'A') ||
      setweight(to_tsvector(config, abstract), 'B')`, with `output_field=SearchVectorField()`
- [x] 1.3 Pass `config=` explicitly in the expression — without it the expression is
      not immutable and the migration will be rejected by PostgreSQL
- [x] 1.4 Add a `GinIndex` over `search_vector` to `Paper.Meta.indexes`
- [x] 1.5 Generate the migration with `makemigrations` and read it before applying it
- [x] 1.6 Apply the migration against the existing 5,000-row corpus and confirm it
      completes
- [x] 1.7 Verify the reverse migration runs cleanly, then re-apply forward
- [x] 1.8 Confirm `apps/ingestion/writer.py` `COMPARE_FIELDS` still excludes
      `search_vector` — it is derived, not supplied, and must never be compared or written

## 2. Ranking

- [x] 2.1 Create `apps/search/ranking.py` with
      `search(query: str, limit: int) -> QuerySet[Paper]`
- [x] 2.2 Build the query with `SearchQuery(query, search_type="websearch", config=SEARCH_CONFIG)`
- [x] 2.3 Filter on the stored `search_vector` column and annotate rank with
      `SearchRank(F("search_vector"), query)` — do not rebuild a vector per row
- [x] 2.4 Order by descending rank, then by a stable tiebreaker so repeated queries
      return a consistent order
- [x] 2.5 Apply the limit as a queryset slice so the bound reaches the database
- [x] 2.6 Keep the function free of excerpting, date completion and link building

## 3. Settings and routing

- [x] 3.1 Add `SEARCH_RESULT_LIMIT` to `config/settings.py`, default 20, read via
      `env.int` following the `INGEST_BATCH_SIZE` precedent
- [x] 3.2 Add `ABSTRACT_SNIPPET_CHARS` as a named bound for the excerpt
- [x] 3.3 Route `api/search/` in `config/urls.py`
- [x] 3.4 Leave DRF on its defaults — no `REST_FRAMEWORK` block; HS-013 owns hardening

## 4. Serialization and the view

- [x] 4.1 Create `apps/search/serializers.py` exposing id, title, authors,
      `publication_date`, `abstract_snippet` and `inspire_url`
- [x] 4.2 Source `inspire_url` from the existing `Paper.inspire_url` property rather
      than rebuilding the URL
- [x] 4.3 Implement date completion: pad `YYYY` and `YYYY-MM` to the first of the
      period, and emit null when the stored value is empty or unparseable
- [x] 4.4 Implement the excerpt: cut at `ABSTRACT_SNIPPET_CHARS` on a word boundary and
      mark it as truncated; return short abstracts whole and unmarked
- [x] 4.5 Create the view: validate `q` is present and not whitespace-only, returning
      400 with a helpful message otherwise
- [x] 4.6 Return `{"count": n, "results": [...]}`
- [x] 4.7 Confirm the view module imports nothing from `apps.ingestion`

## 5. Tests

- [x] 5.1 Create `apps/search/tests/` with an `__init__.py`
- [x] 5.2 Ranking, called directly with no HTTP: a ranked match returns papers in
      descending relevance
- [x] 5.3 Ranking: a paper matching in the title outranks one matching only in the
      abstract
- [x] 5.4 Ranking: the limit bounds the number of rows returned
- [x] 5.5 Ranking: repeating a query returns the same order
- [x] 5.6 View: a missing `q` returns 400 and no papers
- [x] 5.7 View: an empty `q` returns 400
- [x] 5.8 View: a whitespace-only `q` returns 400
- [x] 5.9 View: a query matching nothing returns 200 with a count of zero
- [x] 5.10 View: a stopword-only query returns 200 with a count of zero, not 400
- [x] 5.11 View: punctuation-heavy and unbalanced-quote queries return 200 and do not raise
- [x] 5.12 View: a quoted phrase prefers the phrase over the loose words
- [x] 5.13 View: a `-excluded` term is absent from the results
- [x] 5.14 Serializer: a result carries every required field, and the INSPIRE URL
      addresses the paper's record
- [x] 5.15 Serializer: full, year-month, year-only and empty dates each render correctly
- [x] 5.16 Serializer: a long abstract is excerpted at a word boundary and marked; a
      short one is returned whole
- [x] 5.17 Model: creating a paper populates `search_vector` without a caller supplying
      it, and editing the title updates it
- [x] 5.18 Confirm no test in the suite makes a network request

## 6. Verify against the real corpus

- [x] 6.1 Run a real query against the ingested 5,000 papers and read the results to
      judge whether they are sensible
- [x] 6.2 Run `EXPLAIN` by hand for a deliberately selective term and confirm the index
      is used; capture the plan for the commit body
- [x] 6.3 Note that a non-selective term such as `higgs` will correctly seq-scan this
      corpus, and do not encode a plan assertion as a test
- [x] 6.4 Record an example query and its top results in the commit body, as the card
      requires

## 7. Board and gates

- [x] 7.1 Note on the HS-007 card that author search is deliberately excluded, and that
      AGENTS.md §3 expects the keyword half to carry author-name queries — an
      inheritance for HS-012
- [x] 7.2 `uv run pytest`
- [x] 7.3 `uv run ruff check .`
- [x] 7.4 `uv run ruff format --check .`
- [x] 7.5 `git mv` the card from `board/backlog/` to `board/done/` in the finishing commit
- [x] 7.6 Commit as `HS-007: Expose keyword search over the corpus`