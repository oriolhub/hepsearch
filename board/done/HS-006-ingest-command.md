# HS-006: Ingest a real corpus with a management command

**Status:** done
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

The HS-005 client treats `--limit` as the number of usable records yielded, so
it absorbs the variable number of abstract-less records fetched along the way.
Landing 5,000 usable papers therefore requests `--limit 5000` directly; the
exact number of API records fetched remains an implementation detail reported by
this command. 5,000 is a target, not a contract — a corpus of 4,800 or 5,300 is
equally acceptable.

## Decisions

Settled before implementation; revisit here rather than in code comments.

- **Resume is weak.** A re-run starts from page 1 and lets the upsert absorb the
  work already done. No checkpoint file, no `--start-page`. `sort=mostrecent`
  means INSPIRE's pagination shifts under a long run, so a stored page number
  would not mean the same thing on the next run anyway. The drift costs a few
  records at the seams and is accepted.
- **Write path is compare-then-write, not `ON CONFLICT`.** For each batch:
  one `SELECT` of the existing rows by `inspire_id`, then partition into
  created / updated / unchanged and issue `bulk_create` and `bulk_update`.
  This is what makes "update only genuine changes" and an honest three-way
  summary fall out for free, and it makes `--dry-run` the same loop with the two
  write calls skipped.
  **Trap:** `bulk_update` does not fire `auto_now`, so `updated_at` must be set
  explicitly and named in the updated fields. Untested, this silently leaves
  stale timestamps on every updated row.
- **Counting the skips.** `iter_records` currently swallows records that
  `normalize` rejects, so the command cannot see them. `iter_records` yields
  `Paper | None` instead; the command filters the `None`s and counts them. The
  skip *policy* stays in `normalize`; only the counting moves outward. This
  changes an HS-005 signature and its tests — expected, both live in
  `apps/ingestion`.
- **Batch size** is `INGEST_BATCH_SIZE` in settings, defaulting to the INSPIRE
  page size (250), so one batch is one API page. Not a CLI flag.
- **Transactions** are per batch. An interrupt loses at most the batch in
  flight, which is fine because the next run redoes it.
- **`KeyboardInterrupt` is not caught.** A bare traceback is acceptable; the
  resume story does not depend on a graceful summary.
- **`--dry-run` honours `--limit`** and performs the full fetch, writing
  nothing. A fast smoke test is `--dry-run --limit 20`.
- **A short corpus is reported, not an error.** If the 10,000-record result
  window or a small corpus delivers fewer papers than `--limit`, say so on
  stdout and exit 0.
- **No injected client.** Tests patch the network at the module seam rather than
  adding a constructor parameter that exists only for tests.

## Acceptance criteria

- [x] `uv run python manage.py ingest_inspire --query "higgs boson" --limit 5000`
      works end to end against the live API
- [x] `--query` defaults to the Higgs boson corpus but is not hardcoded
- [x] Records without an abstract are skipped and counted, not stored
- [x] Upserts on `inspire_id`: running the command twice leaves the row count
      unchanged, updates only fields that genuinely changed, and leaves
      `updated_at` untouched on rows whose content is identical
- [x] Interrupting with Ctrl+C and re-running from the start completes the
      corpus without duplicates
- [x] `--dry-run` performs the full fetch for the given `--limit` and reports
      what would be written without writing anything
- [x] Progress is reported to stdout once per batch as it runs (a silent
      10-minute command is a broken command)
- [x] A final summary prints: fetched, skipped-no-abstract, created, updated,
      unchanged
- [x] When fewer papers than `--limit` are available, the shortfall is reported
      on stdout and the command exits 0
- [x] Writes happen in batches of `settings.INGEST_BATCH_SIZE`, not one query
      per paper
- [x] Tests exercise the command against the HS-005 fixture with the network
      patched out, asserting idempotence by running it twice and asserting that
      `updated_at` moves only for a row whose content actually changed
- [x] After a real run, the database holds ~5,000 papers, all with abstracts

## Definition of done

- [x] Acceptance criteria met
- [x] A real ingestion run has been performed and the resulting count recorded in
      the commit body
- [x] `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` pass
- [x] Committed as `HS-006: Ingest a real corpus with a management command`

## Out of scope

Embeddings (HS-010), scheduling/cron, incremental "only new since" sync,
searching (HS-007).
