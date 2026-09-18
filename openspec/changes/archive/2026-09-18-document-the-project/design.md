# Design

## D1 — Why documentation gets no capability

OpenSpec specs assert behaviour a test can falsify. A README has none. A requirement
reading "The README SHALL list prerequisites" is verified by opening the README and
seeing prerequisites, which is not verification — it is restatement, and it creates a
second document that must be kept in step with the first.

So HS-015 produces a change with **one delta, to an existing capability**, and that
delta exists because the audit found a genuine gap in specified behaviour — not because
a docs card is expected to produce specs.

The rule this follows: *specs describe what the system does; documentation describes
what the system is.* The first is testable, the second is written.

## D2 — What the audit actually found, and why it narrowed

The working assumption entering this card was that the vector index's scan width lived
only in a `settings.py` comment and needed promoting into the specs. Reading the specs
first showed that to be half wrong:

```
hybrid-search:91   "The candidate pool is bounded by what the vector index can return"
                   ├── the bound is a named constant, distinct from the result limit
                   ├── it SHALL NOT exceed what a single index scan returns
                   └── the scan parameter SHALL NOT be tuned per request
                                                          ── already correct, abstractly

hybrid-search:65   the canonical RRF constant was measured wrong for this corpus
                                                          ── already explains RRF_K

semantic-search    ── nothing about its own ceiling ──▶ the real gap
```

A delta for `hybrid-search` would have duplicated a correct spec. The gap is on the
semantic side, and it is user-visible:

```
query "higgs", SEARCH_RESULT_LIMIT = 60

  keyword   ──▶ 60 retrieved   "Showing 1–20 of 60 retrieved results"
  hybrid    ──▶ 60 retrieved   "Showing 1–20 of 60 retrieved results"
  semantic  ──▶ 40 retrieved   "Showing 1–20 of 40 retrieved results"
                ▲
                └── the index scans 40; asking for 60 changes nothing
```

A reader comparing modes sees two different denominators for one query. That is correct
behaviour with no requirement behind it. The delta states it, states that it is not a
fault, and repeats the existing prohibition on widening the scan per request so the
"fix" is closed off on this side too.

The specs are also deliberately kept free of the literal `40` and of `hnsw.ef_search`.
Those are configuration, and `hybrid-search` already avoids naming them. AGENTS.md §3 is
where the concrete numbers belong, which is what task 2.9 does.

## D3 — The clean-clone run, and the port it collides with

The card requires the quickstart be "executed verbatim on a fresh checkout". That is not
free, and the trap is specific:

```
working repo                          scratch clone
  compose project "hepsearch"           compose project "hepsearch-clean-clone"
  volume  hepsearch_pgdata              volume  hepsearch-clean-clone_pgdata
  host port 5433  ◀───────── COLLIDES ─────────▶  host port 5433
```

A second clone in a differently-named directory gets its own volume because the Compose
file does not pin a project name, so the existing corpus is not at risk. Both bind host
port 5433, so the second `docker compose up` fails unless the first is stopped. The run
therefore costs the working corpus's availability for its duration, and re-ingesting
afterwards costs about a minute plus the embedding pass.

This is why task 5.1 stops the dev container explicitly and task 5.6 restores it, rather
than leaving a newcomer — or a future agent — to discover the collision mid-quickstart.
It also means the run needs the operator present; it is not something to start
unattended.

## D4 — The cold start is reported, not engineered around

Measured on the reference machine:

| | Elapsed |
|---|---|
| First semantic or hybrid search (model load) | ~63 s |
| Subsequent searches | ~0.09 s |

Three options were considered: document it, warm the model at startup, or redefine the
reported timing to exclude the load. The second and third are behaviour changes, and
HS-014 already settled the principle — the page reports the time the reader actually
waited, and *"if the cold start is embarrassing, fix the cold start"* rather than
redefining the metric. Fixing it is a different card with its own acceptance criteria.

A docs card that quietly added a warmup would be shipping unreviewed behaviour under a
documentation commit. The README states the number.

## D5 — Licensing: quote, measure, defer

The INSPIRE terms grant CC0 re-use of metadata subject to per-field caveats, and the
caveat on `abstracts` lands squarely on a project that stores and displays abstracts:
re-use is conditioned on `abstracts.source` being "arXiv" or "CERN".

`apps/ingestion/client.py` prefers an arXiv abstract and otherwise takes the first
usable entry, so the condition is not met for every stored row. A 250-record sample of
the default query, counting the abstract the client would store:

```
  arXiv 89 ─┬─ permitted      97 / 210 stored   46%
  CERN   8 ─┘
  Elsevier 19, AIP 8, CDS 8, SISSA 6, EDP 5, TEL 5, Springer 3,
  APS 3, IOP 3, OSTI 3, WSP 4, Grobid 3, ~30 institutions
            └─ outside       113 / 210 stored   54%
  (40 of 250 carry no abstract and are skipped before storage)
```

Filtering to permitted sources was rejected for this card, and the reason is
arithmetic rather than preference:

```
yield today     0.84  ──▶  5,000 papers needs ~5,950 records    ✓ inside the 10,000 window
yield filtered  0.39  ──▶  5,000 papers needs ~12,900 records   ✗ exceeds it

                             ceiling under a strict filter ≈ 3,880 papers
```

That would put the "5,000-paper corpus" clause of the v1 definition of done out of
reach on the default query — a scope decision far too large to make inside a docs card,
and one that should be made with real data rather than a 250-record sample.

So this card **quotes the terms exactly** and opens `HS-018` to persist
`abstract_source`, which makes the question answerable across the whole corpus. Deciding
what to do about the answer is left to a later card. No legal determination is made or
implied anywhere in the README.

## D6 — README scope against AGENTS.md

The card asks for non-goals in the README (AC-9) and for the README to link to
AGENTS.md rather than restate it (AC-10). These pull in opposite directions, since
AGENTS.md §1 already carries a non-goals list.

Resolution: the README carries a **four-line** list — LLM answer generation, full-text
PDF ingestion, user accounts, mirroring all of INSPIRE — because an evaluator must see
scope without a second click, followed by one link to AGENTS.md for project decisions
and contributor rules. Four lines is not a duplicate of a section; it is a summary with
a pointer, and it is the smallest thing that satisfies both criteria.

## D7 — Deliberately out of scope

- **A `LICENSE` file.** The repository has none, and an evaluator cannot tell whether
  the code may be reused. That is worth fixing, but choosing between MIT and Apache-2.0
  is a decision, not a documentation task, and v1 should not block on it.
- **Reducing the cold start** (see D4).
- **Filtering or re-sourcing abstracts** (see D5, and HS-018).
- **CI.** AGENTS.md §2 lists it as deliberately absent; nothing here changes that.
