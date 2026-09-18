# Tasks

## 1. Start the card

- [x] 1.1 `git mv board/backlog/HS-015-documentation.md board/in-progress/`

## 2. Audit AGENTS.md against the shipped code

Each item was verified against the working tree while this change was written.

- [x] 2.1 `:221` — replace `test_ranking.py::test_rrf_prefers_dual_hits`, which does not
      exist, with a real test id from `apps/search/tests/test_fusion.py`
- [x] 2.2 `:222` — replace `pytest -k "rrf and not slow"`, which collects zero tests,
      with an expression that selects something
- [x] 2.3 `:186` — delete "The repository currently contains this documentation and the
      board", false since HS-003
- [x] 2.4 `:140` — record INSPIRE's published limit of 15 requests per 5 s per IP, and
      that the project's 1.0 s throttle sits at 5 per 5 s, inside it. Keep the existing
      point that no rate-limit headers are returned
- [x] 2.5 `:69-75` — add `config/health.py`, `apps/papers/presentation.py`,
      `apps/search/presentation.py` and the root `tests/` directory to the tree
- [x] 2.6 `:203` — qualify "~2 GB with torch": a CPU-only Windows environment measured
      892 MB of virtualenv. Name the platform the number came from
- [x] 2.7 §4.2 — correct the no-abstract rate from ~10% to the measured ~16%, and the
      derived "fetch ~5,600 to land 5,000" to ~5,950
- [x] 2.8 §4.2 — record the abstract re-use caveat and the measured source
      distribution, cross-referencing HS-018
- [x] 2.9 §3 — promote the vector index's scan width from a `settings.py` comment to a
      stated constraint, with the concrete numbers the specs deliberately omit
- [x] 2.10 §6 — document `GET /api/health/`, which no section currently mentions
- [x] 2.11 Re-read §2's rejected-technology list against what shipped, and confirm no
      other decision drifted during implementation

## 3. The spec gap

- [x] 3.1 Confirm no equivalent requirement exists in `hybrid-search`, whose `:91`
      covers the fusion pool only — a delta there would duplicate a correct spec
- [x] 3.2 Add a test asserting a semantic search asked for more rows than the index
      scans returns the smaller number, if none already asserts it
- [x] 3.3 Confirm each scenario in the delta has a literal corresponding test before
      checking this section off
- [x] 3.4 `openspec validate document-the-project --strict`

## 4. Write the README

- [x] 4.1 Opening paragraph: what the project is and the problem it solves, before any
      setup instruction
- [x] 4.2 Prerequisites with versions: Python 3.13, Docker (Rancher Desktop on this
      host), `uv`
- [x] 4.3 Quickstart, every command copyable, in the order a newcomer runs them
- [x] 4.4 State the measured costs: 5,000 papers, 63 MB database, ingestion under a
      minute, ~892 MB virtualenv with the embedding extra, and the model download
- [x] 4.5 State the cold start honestly — first semantic or hybrid search ~63 s, warm
      ~0.09 s. Do not work around it and do not change behaviour to hide it
- [x] 4.6 Document `GET /api/search/` and `GET /api/health/` with a real request and a
      real response, trimmed to one result with the elision marked
- [x] 4.7 Explain that keyword and semantic **fail differently** — keyword loses on
      paraphrase, semantic loses on exact identifiers — and that hybrid exists because
      neither suffices alone
- [x] 4.8 Show the measured paraphrase example: "why is the Higgs mass so much lighter
      than the Planck scale" returns nothing from keyword ranking and the
      hierarchy-problem literature from semantic ranking
- [x] 4.9 Credit INSPIRE with a link and quote the re-use terms exactly — CC0 with the
      per-field caveats, including the one on abstracts. No paraphrase from memory
- [x] 4.10 A four-line non-goals list, then one link to AGENTS.md for project decisions
      and contributor rules
- [x] 4.11 Check the finished README against AGENTS.md for any section it duplicates
      rather than links to

## 5. Verify on a clean clone

The acceptance criterion this card exists for. **Needs the operator at the keyboard:**
the dev Postgres on port 5433 must be stopped first or the fresh clone cannot bind it.

- [x] 5.1 `docker compose down` in the working repository
- [x] 5.2 Clone the repository into a scratch directory
- [x] 5.3 Execute the README quickstart **verbatim** — copy each command, change
      nothing, and record every command that fails or needs a step the README omits
- [x] 5.4 Confirm the end state: a natural-language query on the page returns ranked
      papers
- [x] 5.5 Fix the README for whatever the run exposed, then re-run the affected steps
- [x] 5.6 Delete the scratch clone, restart the working container and confirm the
      corpus is intact
- [x] 5.7 Record the date of the run — it goes in the commit body

## 6. Gates

- [x] 6.1 `uv run pytest`
- [x] 6.2 `uv run ruff check .`
- [x] 6.3 `uv run ruff format --check .`
- [x] 6.4 `uv run python manage.py check`

## 7. Ship

- [x] 7.1 `git mv board/in-progress/HS-015-documentation.md board/done/` and check off
      the acceptance criteria and definition of done
- [x] 7.2 Commit as `HS-015: Document the project for a stranger`, with a body stating
      the clean-clone run date and listing the AGENTS.md facts corrected
- [x] 7.3 Decide whether `board/backlog/HS-018-record-abstract-source.md` ships in this
      commit or its own; it was discovered by this card's licensing work
- [x] 7.4 Confirm the v1 definition of done in AGENTS.md §1 is satisfied in full
