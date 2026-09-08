# HS-004: Model the Paper domain entity

**Status:** done
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

*Spike Amendment:* Field `publication_date` was renamed to `earliest_date` because 72%
of INSPIRE dates are partial prefixes (`YYYY` or `YYYY-MM`), and 42% disagree on the year
with publication_info. String fields use `blank=True, default=""` per repository ruff
rule DJ001.

## Acceptance criteria

- [x] `Paper` lives in `apps/papers/models.py`
- [x] `inspire_id` is a unique, indexed, non-null integer — the natural key
- [x] `title` is non-null
- [x] `abstract` is non-null, enforced by a database `CheckConstraint` that rejects empty strings
- [x] `authors`, `arxiv_id`, `doi`, `journal`, `earliest_date`,
      `citation_count`, `categories` are all optional/blankable (`blank=True, default=""` for strings)
- [x] A property or method returns the canonical INSPIRE URL
      `https://inspirehep.net/literature/<inspire_id>`
- [x] `created_at` / `updated_at` timestamps exist
- [x] `__str__` returns something readable in the admin and in shell output
- [x] The model is registered in the Django admin with search on title and
      `inspire_id`, and list columns worth looking at
- [x] A migration is generated and applies cleanly
- [x] Tests cover: creating a paper, the INSPIRE URL property, and that a second
      paper with a duplicate `inspire_id` raises an integrity error

## Definition of done

- [x] Acceptance criteria met
- [x] `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` pass
- [x] Committed as `HS-004: Model the Paper domain entity`

## Out of scope

The embedding vector column (HS-010) — pgvector is not imported here. Any
INSPIRE-specific parsing (HS-005/HS-006). Search indexes (HS-007).
