## Context

`apps/ingestion` already has a client that fetches INSPIRE pages, retries transient
failures, throttles politely, and normalizes messy external JSON into unsaved `Paper`
objects. `apps/papers` already has the `Paper` model with a unique `inspire_id` and a
database constraint rejecting an empty abstract. What is missing is the piece that
connects them: a command an operator runs to fill the database.

Constraints that shape the design:

- Ingestion is a batch job, not a request-path concern. AGENTS.md §2 rules out Celery,
  Redis and any broker — this is a synchronous management command.
- A full run is roughly 5,600 fetched records over ~23 API pages with a one-second
  throttle: on the order of ten minutes. Anything that long must report progress and
  must survive being interrupted.
- The command gets re-run constantly during development, so idempotence is the
  property that matters most.
- `apps/ingestion` may import `apps.papers` and must never import `apps.search`.

## Goals / Non-Goals

**Goals:**

- A single command lands a bounded, roughly-5,000-paper corpus from a caller-supplied
  INSPIRE query.
- Running it twice is safe: no duplicate rows, and no write at all for a paper whose
  content has not changed.
- The operator can see what is happening while it runs and what happened when it
  finished.
- The whole command is testable offline against the committed INSPIRE fixture.

**Non-Goals:**

- Embeddings. The vector column is filled by a later card.
- Scheduling, cron, or a daemon.
- Incremental "only what is new since last time" sync. A re-run re-walks the query.
- A stable snapshot of INSPIRE. The corpus is a sample, not a mirror.
- Graceful interrupt handling. See the decision below.

## Decisions

### Compare-then-write, not `ON CONFLICT DO UPDATE`

For each batch the command issues one `SELECT` of the existing rows matching the
batch's INSPIRE ids, compares field by field in Python, and then issues at most one
`bulk_create` for the new papers and one `bulk_update` for the genuinely changed ones.

*Alternative considered:* `bulk_create(update_conflicts=True, unique_fields=["inspire_id"])`,
which is one statement instead of three. Rejected because Postgres' `ON CONFLICT DO
UPDATE` cannot report whether a row actually changed — every matched row looks
updated, and `updated_at` is rewritten on every re-run even when nothing differs. It
also requires an explicit `update_fields` list that must be kept in step with the
model by hand, and `created_at` must be carefully excluded from it or a re-run
rewrites history.

The extra `SELECT` per batch — around 23 queries for a full run — buys an honest
created / updated / unchanged summary, a truthful `updated_at`, and a `--dry-run` that
is the identical loop with the two write calls skipped. That is a good trade at this
scale.

*Trap this introduces:* Django's `bulk_update` does not apply `auto_now`, so the
command must set `updated_at` explicitly on the changed papers and name it among the
updated fields. Left untested, every updated row silently keeps a stale timestamp.

### Comparison is over the fields ingestion owns

A paper counts as changed when any field the client populates differs from the stored
row: title, abstract, authors, categories, arXiv id, DOI, journal, earliest date,
citation count. The identity, `created_at` and `updated_at` are excluded. Deriving the
comparison list from the model's concrete fields minus that exclusion set keeps it from
drifting when the model grows.

Note that `citation_count` moves on almost every real re-run — that is a genuine
change, correctly reported as an update.

### Restart is a plain re-run

There is no checkpoint file and no `--start-page`. An interrupted run is resumed by
running the same command again from the beginning; the idempotent write makes the
already-landed pages cheap in database terms.

*Alternative considered:* persisting the last completed page. Rejected because the
client sorts by most recent, so INSPIRE's pagination shifts as new records are
published — page 12 tomorrow is not page 12 today, and a stored page number would be a
false promise. The cost of the simple approach is re-paying the API walk, which is
acceptable for a job an operator runs occasionally.

The same reasoning accepts that a long run may miss or repeat a record at a page
boundary if INSPIRE ingests a paper mid-run. At a target of "roughly 5,000 papers"
this drift does not matter.

### One batch is one API page, sized by settings

Batch size is a setting (`INGEST_BATCH_SIZE`), defaulting to the client's page size, so
that by default one fetched page is one write batch and one progress line. It is not a
command-line flag: it is an operational tuning knob, not something an operator varies
per run.

### Transactions are per batch, and interrupts are not caught

Each batch's writes are wrapped in a transaction so a batch is all-or-nothing. The run
as a whole is not, because a single run-long transaction would discard every page on
interrupt — exactly the opposite of what restartability needs.

`KeyboardInterrupt` is deliberately not caught. A bare traceback is acceptable: the
batch in flight rolls back, previous batches are committed, and the next run picks up
the remainder. A graceful summary on interrupt would be nicer but is not what makes
restart work.

### Counting the skipped records changes the client's iteration

`normalize` already returns nothing for a record with no usable abstract, but the
iteration helper swallows that outcome, so a caller cannot see how many records were
dropped. Iteration will yield one result per fetched record — a paper or an explicit
nothing — and the command filters and counts.

*Alternative considered:* passing a mutable statistics object into the client for it to
increment. Rejected as a hidden output parameter; making the per-record outcome visible
in the yielded value is more honest and keeps the client free of reporting concerns.

The rule deciding usability stays in `normalize`. Only the visibility of its verdict
moves outward. The consequence is that the caller — not the client — now carries the
obligation never to write an unusable record, which is why the `inspire-client` spec
changes rather than merely gaining a requirement.

### `--dry-run` is a full rehearsal

It performs the same fetch for the same limit and the same comparison, and reports the
same counts, skipping only the two write calls. A fast smoke test is expressed as
`--dry-run --limit 20` rather than by making dry run secretly mean "one page".

### A short corpus is reported, not an error

If the query matches fewer records than requested, or the client stops at the API's
10,000-record deep-pagination ceiling, the command says how many it landed against how
many were asked for and exits successfully. The operator asked for an upper bound, not
a guarantee.

### Tests patch the network at the module seam

The command constructs its own client; there is no injected-client parameter existing
only for tests. Tests replace the client where the command imports it and feed it the
committed fixture. This keeps the production signature free of test scaffolding, per
AGENTS.md §2 on abstractions no acceptance criterion requires.

## Risks / Trade-offs

- **`bulk_update` silently skipping `auto_now`** → `updated_at` is set explicitly and a
  test asserts the timestamp moves for a changed row and does not move for an identical
  one.
- **A ten-minute command looks hung** → a progress line per batch, written to standard
  output through the command's own writer so tests can capture it.
- **Pagination drift under `sort=mostrecent`** → accepted. The corpus is a sample;
  the target of 5,000 is explicitly not a contract.
- **Re-running re-pays the full API walk** → accepted, and mitigated by the write path
  being cheap on the second pass. Adding a checkpoint would be a false promise given
  unstable pagination.
- **A batch that is all-or-nothing can lose up to one page on interrupt** → accepted;
  the next run refetches it.
- **The comparison field list drifting from the model** → derived from the model's
  concrete fields minus an explicit exclusion set, rather than hand-listed.
- **Changing the client's iteration breaks its existing tests** → expected and in
  scope; both modules live in `apps/ingestion` and the spec delta records the change.
