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

- [ ] `README.md` explains what the project is and what problem it solves, in a
      paragraph, before any setup instructions
- [ ] Prerequisites are listed with versions (Python 3.13, Docker, `uv`)
- [ ] A quickstart takes a clean clone to a working search, every command copyable
      and verified in order on a fresh checkout
- [ ] The quickstart states the realistic time and disk cost of ingesting and
      embedding 5,000 papers, and the model download size
- [ ] API endpoints are documented with a real example request and response
- [ ] The search architecture is explained: full-text plus vector, fused by RRF,
      and **why** neither alone suffices
- [ ] A concrete example shows a query where semantic search beats keyword search
- [ ] The INSPIRE data source is credited with a link and its licensing noted
- [ ] Non-goals are stated so readers stop asking for them
- [ ] `README.md` links to `AGENTS.md` rather than restating it
- [ ] AGENTS.md is reviewed against the finished code, and any decision that
      drifted during implementation is corrected

## Definition of done

- [ ] Acceptance criteria met
- [ ] The quickstart has been executed verbatim on a clean clone
- [ ] `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` pass
- [ ] Committed as `HS-015: Document the project for a stranger`
- [ ] v1 definition of done is satisfied

## Out of scope

Deployment guides, Kubernetes manifests, a hosted demo, contribution guidelines
for a project with no external contributors.
