# HS-018: Record the source of each stored abstract

**Status:** backlog
**Depends on:** HS-006

## Story

As a maintainer, I want to know which source each stored abstract came from, so
that the project can answer whether its corpus falls within INSPIRE's stated
conditions for re-using abstracts.

## Context

INSPIRE's [terms of use](https://help.inspirehep.net/knowledge-base/terms-of-use/)
clause 5 grants re-use of INSPIRE metadata under the CC0 waiver *subject to
per-field caveats*. For the `abstracts` field the stated condition is:

> If `abstracts.source` is "arXiv" or "CERN"

`apps/ingestion/client.py` (`_abstract`) prefers the first arXiv-sourced abstract
but **falls back to the first usable entry regardless of source**. A 250-record
sample of the default `higgs boson` query, counting the abstract the client would
actually store, found:

| Source of stored abstract | Share of stored records |
|---|---|
| arXiv or CERN | ~46% |
| Elsevier, AIP, CDS, SISSA, Springer, APS, IOP, ~30 institutions | ~54% |

(16% of sampled records carry no abstract at all and are skipped by `normalize`,
so they never become rows.)

`Paper` does not persist the abstract's source, so **the question is currently
unanswerable without re-querying INSPIRE**. This card records the fact. It
deliberately does not act on it.

Filtering ingestion to permitted sources was considered and rejected *for now*:
the yield would drop from ~84% to ~39% of fetched records, and against INSPIRE's
hard 10,000-record result window (AGENTS.md §4.1) that caps the corpus near 3,880
papers — which would break the "5,000-paper corpus" clause of the v1 definition of
done (AGENTS.md §1). That trade deserves its own decision, made with this field's
data in hand rather than from a sample.

## Acceptance criteria

- [ ] `Paper` has an `abstract_source` field holding the `source` of the abstract
      that was stored, blank when INSPIRE supplied none, with a committed migration
- [ ] `ingest_inspire` populates `abstract_source` from the same `abstracts` entry
      whose `value` it stored — the two can never describe different entries
- [ ] Re-running `ingest_inspire` over an already-ingested corpus backfills
      `abstract_source` without creating duplicate rows and without touching any
      embedding, verified by a test
- [ ] A record whose chosen abstract has no `source` key stores a blank
      `abstract_source` rather than failing, verified against the committed fixture
- [ ] The distribution is answerable with one documented ORM query, stated in the
      card's closing comment or in AGENTS.md §4.2 — no reporting command is added
- [ ] Tests run against the committed INSPIRE fixture and touch no network

## Definition of done

- [ ] Acceptance criteria met
- [ ] Tests written and passing (`uv run pytest`)
- [ ] `uv run ruff check .` clean
- [ ] `uv run ruff format --check .` clean
- [ ] AGENTS.md §4.2 records the measured source distribution and the re-use caveat
- [ ] Committed as `HS-018: Record the source of each stored abstract` with the card
      moved to `board/done/`

## Out of scope

Filtering, excluding or re-licensing any abstract; changing which abstract
`_abstract` chooses; a reporting management command; any legal determination.
Deciding what to do with the answer is a later card, opened once this field has
been populated across the real corpus.

## Note for whoever picks this up

Adding this column will fail
`apps/ingestion/tests/test_writer.py::test_compare_fields_includes_the_fields_ingestion_populates`,
which pins `writer.py`'s derived `COMPARE_FIELDS` to exactly the nine fields INSPIRE
owns. That failure is the guard working as intended: it forces a deliberate decision
about who owns the new column. Here the answer is that ingestion *does* own
`abstract_source` — unlike `embedding` — so add it to the expected set rather than to
`_EXCLUDED_FIELDS`, and confirm a re-ingest still leaves embeddings untouched.
