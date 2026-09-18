# HS-015: Document the project for a stranger

**Status:** backlog
**Depends on:** HS-014

## Story

As a newcomer, I want documentation that takes me from a clean clone to a working
search in a few commands, so that I can run and evaluate the project without
asking anyone.

## Context

This card closes the v1 definition of done (AGENTS.md §1), whose final clause is
"with tests and docs".

`AGENTS.md` is the contributor and agent contract; the `README.md` is the
front door for a human evaluating the project. They serve different readers —
the README must not duplicate AGENTS.md, it should link to it.

## Acceptance criteria

- [x] `README.md` explains what the project is and what problem it solves, in a
      paragraph, before any setup instructions
- [x] Prerequisites are listed with versions (Python 3.13, Docker, `uv`)
- [x] A quickstart takes a clean clone to a working search, every command copyable
      and verified in order on a fresh checkout
- [x] The quickstart states the realistic time and disk cost of ingesting and
      embedding 5,000 papers, and the model download size
- [x] API endpoints are documented with a real example request and response
- [x] The search architecture is explained: full-text plus vector, fused by RRF,
      and **why** neither alone suffices
- [x] A concrete example shows a query where semantic search beats keyword search
- [x] The INSPIRE data source is credited with a link and its licensing noted
- [x] Non-goals are stated so readers stop asking for them
- [x] `README.md` links to `AGENTS.md` rather than restating it
- [x] AGENTS.md is reviewed against the finished code, and any decision that
      drifted during implementation is corrected

## Definition of done

- [x] Acceptance criteria met
- [x] The quickstart has been executed verbatim on a clean clone
- [x] `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` pass
- [x] Committed as `HS-015: Document the project for a stranger`
- [x] v1 definition of done is satisfied

## Out of scope

Deployment guides, Kubernetes manifests, a hosted demo, contribution guidelines
for a project with no external contributors.
