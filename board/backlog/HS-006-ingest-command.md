# HS-006: Ingest a real corpus with a management command

**Status:** backlog
**Depends on:** HS-005

## Story

As an operator, I want a management command that fills the database with a
bounded slice of INSPIRE papers, so that there is a real corpus to search
against.

## Context

Ingestion is a batch job an operator runs, not a request-path concern — hence a
synchronous management command and no Celery (AGENTS.md §2).

**Idempotence is the critical property.** This command gets re-run constantly
during development and must be safe to interrupt and resume.

Because ~10% of INSPIRE records have no abstract, landing 5,000 usable papers
means fetching roughly 5,600.

## Acceptance criteria

- [ ] `uv run python manage.py ingest_inspire --query "higgs boson" --limit 5000`
      works end to end against the live API
- [ ] `--query` defaults to the Higgs boson corpus but is not hardcoded
- [ ] Records without an abstract are skipped and counted, not stored
- [ ] Upserts on `inspire_id`: running the command twice leaves the row count
      unchanged and updates changed fields
- [ ] Interrupting with Ctrl+C and re-running resumes without duplicates
- [ ] `--dry-run` reports what would be written without writing
- [ ] Progress is reported to stdout as it runs (a silent 10-minute command is a
      broken command)
- [ ] A final summary prints: fetched, skipped-no-abstract, created, updated
- [ ] Writes happen in batches, not one query per paper
- [ ] Tests exercise the command against the HS-005 fixture with the network
      patched out, asserting idempotence by running it twice
- [ ] After a real run, the database holds ~5,000 papers, all with abstracts

## Definition of done

- [ ] Acceptance criteria met
- [ ] A real ingestion run has been performed and the resulting count recorded in
      the commit body
- [ ] `uv run pytest` and `uv run ruff check .` pass
- [ ] Committed as `HS-006: Ingest a real corpus with a management command`

## Out of scope

Embeddings (HS-010), scheduling/cron, incremental "only new since" sync,
searching (HS-007).
