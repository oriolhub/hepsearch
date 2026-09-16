## 1. Board and mode vocabulary

- [x] 1.1 `git mv board/backlog/HS-011-semantic-search.md board/in-progress/` and set its status to `in-progress`
- [x] 1.2 Add a `SearchMode` enum to `apps/search` with `KEYWORD` and `SEMANTIC` members, leaving room for HS-012's `HYBRID`, and a parser that maps an absent value to `KEYWORD` and an unrecognised value to a refusal the view can turn into a 400
- [x] 1.3 Test the parser directly: absent selects keyword, a known name selects its mode, an unknown name is refused, and the refusal carries no ranking result

## 2. Make the keyword ranker's score mode-agnostic

- [x] 2.1 Rename the `rank` annotation in `apps/search/ranking.py` to `score`, updating the ordering clause in the same edit
- [x] 2.2 Confirm the existing keyword ordering tests still pass, since they are what catches a half-finished rename
- [x] 2.3 Add `score` to `PaperSearchResultSerializer`, reading the common annotated attribute rather than branching on mode
- [x] 2.4 Add `mode` to the response envelope alongside `count` and `results`
- [x] 2.5 Test that a keyword response carries a score per result, that the scores descend with the result order, and that the response names its mode

## 3. The semantic ranker

- [x] 3.1 Add `semantic_search(queryset, vector, limit)` to `apps/search/ranking.py`, filtering on `embedding__isnull=False` and `embedding_model` equal to the configured provider's `model_name`
- [x] 3.2 Annotate `score` as `1 - CosineDistance("embedding", vector)` and order by distance ascending with `-inspire_id` as the deterministic tiebreak, then slice to `limit` so the bound reaches the database
- [x] 3.3 Keep the callable free of the provider, the HTTP layer and any model loading — it accepts a vector, never text, and raises nothing when the corpus is unusable
- [x] 3.4 Test with hand-written vectors that the nearest vector ranks first and the rest follow by increasing distance
- [x] 3.5 Test that a paper with a null embedding is excluded, including the case where fewer compatible papers exist than the result cap — the case where nulls would otherwise surface
- [x] 3.6 Test that a paper whose `embedding_model` differs from the configured one is excluded
- [x] 3.7 Test that the callable returns an empty result and raises nothing when no compatible papers exist
- [x] 3.8 Test that repeating the same query against unchanged data returns the same papers in the same order

## 4. Corpus health reporting

- [x] 4.1 Add `apps/search/health.py` exposing a once-per-process staleness probe that counts papers embedded by a model other than the configured one and emits `logger.warning` when the count is non-zero
- [x] 4.2 Give the memo an explicit `reset()` and call it from the root `conftest.py` alongside `registry.reset()`, so no test inherits another test's probe state
- [x] 4.3 Test that a drifted corpus logs a warning naming the count, that a clean corpus logs nothing, and that several searches in one process warn only once
- [x] 4.4 Confirm `manage.py check` still runs without a database and that no system check queries embeddings

## 5. The HTTP layer

- [x] 5.1 Parse and validate `mode` in `apps/search/views.py` before any other work, refusing an unknown value with 400
- [x] 5.2 On semantic mode, run the health probe, obtain the provider through `apps.embedding.registry.get_provider()`, embed the query, and pass the vector to `semantic_search`
- [x] 5.3 When semantic results are empty, distinguish the two states: no papers at all returns 200 with an empty list; papers exist with no compatible embedding returns 503 naming `embed_papers` as the operator action
- [x] 5.4 Leave the keyword path's selection, ordering and ranking untouched
- [x] 5.5 Test the 400 for an unknown mode, the 200-with-empty-list for an empty corpus, and the 503 for a populated but incompatible corpus
- [x] 5.6 Test that a semantic response carries a similarity per result and that a negative similarity is reported unclamped
- [x] 5.7 Test that the keyword path returns the same papers in the same order as before this change

## 6. The demo page

- [x] 6.1 Add a minimal mode selector to the search template, defaulting to keyword and preserving the chosen mode in the rendered page
- [x] 6.2 Have `search_page` honour the selector through the same parser the API uses, so the two cannot disagree
- [x] 6.3 Test that the page renders the selector and that submitting with semantic chosen lists papers ranked by similarity

## 7. Verify against the real corpus

- [x] 7.1 Run `docker compose up -d --wait`, then `uv run python manage.py ingest_inspire --query "higgs boson" --limit 5000` and `uv run python manage.py embed_papers`
- [x] 7.2 Capture `EXPLAIN` for the semantic ranking query against the populated corpus and confirm the HNSW index is scanned rather than the papers table, without forcing the planner
- [x] 7.3 Choose a paraphrased query sharing no distinctive term with its target papers, run it in both modes, and record the exact query and both result lists
- [x] 7.4 Note the observed first-request model-load cost so the lazy-loading trade-off is documented from measurement rather than assumption

## 8. Documentation and gates

- [x] 8.1 Document in the design record the accepted ANN under-fetch limitation, the lazy model load, and the unverified thread-safety assumption
- [x] 8.2 Update `AGENTS.md` if any command or convention changed, in the same commit as the behaviour
- [x] 8.3 Confirm every acceptance criterion on the card has a literal corresponding test, not merely a passing suite
- [x] 8.4 Run `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .`
- [x] 8.5 Tick the card's checkboxes to match reality, `git mv` it to `board/done/`, and commit as `HS-011: Add semantic search` with the paraphrase comparison in the body

## 9. Review remediation

Raised by review of the implementation commit, before the change is archived.

- [x] 9.1 Escape the unrecognised `mode` value the search page reflects into its 400 body, and test that submitted markup is not served back executable
- [x] 9.2 Make `semantic_search`'s `model_name` a required argument and drop its `settings.EMBEDDING_MODEL` fallback, which named a different vector space than the provider's and silently matched nothing
- [x] 9.3 Route an embedding provider that cannot be loaded to the 503 surface instead of letting `ImportError` escape as a 500, since the provider's dependency is an optional extra
- [x] 9.4 Give the demo page an unavailable state so an unusable corpus is not rendered as "No results found."
- [x] 9.5 Test that keyword scores descend with the result order, over enough papers for the order to mean something
- [x] 9.6 Test that a drifted corpus still serves its compatible papers
- [x] 9.7 Defer the `embedding` and `search_vector` columns in both rankers, neither of which any consumer reads
- [x] 9.8 Record the new behaviour in the delta specs and re-run `openspec validate --strict`
