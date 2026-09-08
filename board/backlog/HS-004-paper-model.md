# HS-004: Model the Paper domain entity

**Status:** backlog
**Depends on:** HS-003

## Story

As a developer, I want a `Paper` model that faithfully represents an INSPIRE
literature record, so that ingestion has somewhere to write and search has
something to rank.

## Context

**Read AGENTS.md §4.2 before writing the model.** The INSPIRE payload is far more
optional than it looks: `dois` and `publication_info` are frequently absent
entirely, and ~10% of records have no abstract. Only `control_number` and the
title are dependable.

`apps/papers` is the centre of the dependency graph and must import nothing from
`ingestion` or `search`. It knows nothing about INSPIRE's JSON field names — that
translation belongs to ingestion.

## Acceptance criteria

- [ ] `Paper` lives in `apps/papers/models.py`
- [ ] `inspire_id` is a unique, indexed, non-null integer — the natural key
- [ ] `title` is non-null
- [ ] `abstract` is non-null (papers without one are never stored — see HS-006)
- [ ] `authors`, `arxiv_id`, `doi`, `journal`, `publication_date`,
      `citation_count`, `categories` are all nullable/blankable
- [ ] A property or method returns the canonical INSPIRE URL
      `https://inspirehep.net/literature/<inspire_id>`
- [ ] `created_at` / `updated_at` timestamps exist
- [ ] `__str__` returns something readable in the admin and in shell output
- [ ] The model is registered in the Django admin with search on title and
      `inspire_id`, and list columns worth looking at
- [ ] A migration is generated and applies cleanly
- [ ] Tests cover: creating a paper, the INSPIRE URL property, and that a second
      paper with a duplicate `inspire_id` raises an integrity error

## Definition of done

- [ ] Acceptance criteria met
- [ ] `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` pass
- [ ] Committed as `HS-004: Model the Paper domain entity`

## Out of scope

The embedding vector column (HS-010) — pgvector is not imported here. Any
INSPIRE-specific parsing (HS-005/HS-006). Search indexes (HS-007).
