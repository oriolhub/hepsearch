## Why

The repository has **no `README.md`**. Someone who finds this project can read
`AGENTS.md` — a contributor and agent contract that opens with an architecture
dependency rule — or nothing. There is no door for a person who simply wants to know
what this is and whether it works.

HS-015 closes the final clause of the v1 definition of done (AGENTS.md §1): *"with
tests and docs"*. It is the last card before v1.

The card also asks for something no previous card has: that `AGENTS.md` be checked
against the finished code. That audit was performed while writing this proposal, and it
found breakage rather than staleness.

| AGENTS.md | Reality |
|---|---|
| `:221` `pytest ...::test_rrf_prefers_dual_hits` | The test does not exist. Fusion tests live in `test_fusion.py` |
| `:222` `pytest -k "rrf and not slow"` | Collects **zero** tests — 251 deselected |
| `:186` "repository currently contains this documentation and the board" | False since HS-003 |
| `:140` "No rate-limit headers are returned" | True, but INSPIRE **publishes** 15 requests per 5 s per IP. Our 1.0 s throttle is 5 per 5 s |
| `:69-75` architecture tree | Omits `config/health.py`, both `presentation.py` modules, and the root `tests/` |
| `:203` "~2 GB with torch" | Measured 892 MB of virtualenv, CPU-only Windows |
| §4.2 "~10% of records have no abstract" | Measured ~16% on a 250-record sample, so the derived "fetch ~5,600" should be ~5,950 |
| §6 API shape | `GET /api/health/` exists and appears in no section |

Two of those are commands that fail if a newcomer pastes them. That is precisely the
failure mode a README is supposed to prevent, present in the document we point people to.

## What Changes

- **A `README.md` is written from zero**: what the project is, prerequisites with
  versions, a quickstart, the API, the architecture, and the non-goals — linking to
  `AGENTS.md` rather than restating it.
- **The quickstart is executed verbatim from a fresh clone** before the card is closed,
  and the date of that run goes in the commit body. Not desk-checked. This is the card
  that closes v1; if any card earns a real end-to-end run, it is this one.
- **Every number in the README is measured, not estimated**: 5,000 papers, 63 MB
  database, ingestion under a minute, ~892 MB virtualenv with the embedding extra.
- **The cold start is documented, not hidden.** The first semantic or hybrid search
  loads the model and took **~63 s** on the reference machine; warm searches take
  ~0.09 s. No behaviour changes to disguise it — that would be a different card.
- **The eight AGENTS.md facts above are corrected**, and the vector index's scan width
  is promoted from a `settings.py` comment to a stated constraint in §3.
- **The INSPIRE terms are quoted, not paraphrased**, including the caveat that lands on
  this project: abstracts are re-usable under CC0 only when `abstracts.source` is
  "arXiv" or "CERN". A 250-record sample found ~54% of stored abstracts outside those
  two. `HS-018` is opened to record the source per paper so the question becomes
  answerable; acting on the answer is deliberately deferred.

### Why keyword search is explained rather than excused

The README's central example is measured, not illustrative:

```
"why is the Higgs mass so much lighter than the Planck scale"

  keyword  ──▶ (nothing)
  semantic ──▶ An examination of the hierarchy problem beyond the Standard Model
               Origin of mass scales in scale-symmetric extension of SM
```

Keyword ranking returns nothing because `websearch` parsing **ANDs** the terms, so any
natural-language question containing an uncommon word matches no paper. The README says
so. The honest framing — keyword and semantic *fail differently*, which is why hybrid
exists — is a stronger story than presenting vector search as magic, and it is the
justification for the ranker the project actually ships.

## Capabilities

### New Capabilities

**None.** A README has no runtime behaviour, and a `documentation` capability asserting
"the README SHALL list prerequisites" would be a spec that mirrors a prose file and can
only be verified by reading it. Documentation is not specified here; it is written.

### Modified Capabilities

- `semantic-search`: gains one requirement. The audit found that the retrieval bound is
  specified only for the fusion side. `hybrid-search` already states that the candidate
  pool "is bounded by what the vector index can return", abstractly and correctly. But
  **a semantic-only search is capped the same way and nothing says so**: asked for the
  configured 60 results it returns 40, and the page therefore reports a different
  retrieved total for semantic than for keyword on the same query. That difference is
  user-visible, is not a fault, and is unspecified.

`hybrid-search` is deliberately **not** modified. Its existing requirements at `:65` and
`:91` already cover the fusion constant and the candidate-pool bound, and restating them
here would duplicate a spec that is already correct.

## Impact

- `README.md` (new) — the front door.
- `compose.yaml` — checkout-specific Compose project names keep a clean-clone
  database volume isolated from the working corpus.
- `AGENTS.md` — eight factual corrections; §3 gains the scan-width constraint; §4.2
  gains the measured abstract-source distribution and the re-use caveat; §6 gains
  `/api/health/`.
- `openspec/specs/semantic-search/spec.md` — one added requirement, via the delta.
- `apps/search/tests/` — a test for the retrieval cap, if none already asserts it.
- `board/backlog/HS-018-record-abstract-source.md` (new) — the deferred licensing
  question, recorded rather than lost.
- **No application behaviour changes.** No new dependency. The cold start, the
  AND-semantics of keyword parsing, and the abstract-source question are all documented
  as they are and left for cards that can properly own them.
