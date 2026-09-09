## Why

The INSPIRE client can fetch and normalize records, but nothing writes them to the
database — the corpus is still empty, so there is nothing to search and every search
card that follows is blocked. An operator needs a single command that fills the
database with a bounded slice of INSPIRE papers and that is safe to re-run, because
during development this command gets run over and over.

## What Changes

- Add an `ingest_inspire` management command in `apps/ingestion` that walks the
  INSPIRE client's output and writes `Paper` rows.
- `--query` defaults to the Higgs boson corpus but is a parameter, not a constant.
  `--limit` counts usable papers landed, not records fetched.
- Writes are batched and idempotent. Each batch reads the existing rows for its
  INSPIRE ids, then partitions into created / updated / unchanged and issues one
  `bulk_create` and one `bulk_update`. A row whose content is identical is left
  untouched, including its `updated_at` timestamp.
- Re-running after an interruption starts from the first page again and lets the
  idempotent write absorb the work already done. There is no checkpoint.
- Add `--dry-run`, which performs the full fetch for the given limit and reports what
  would be written without writing anything.
- Report progress once per batch and a final summary of fetched, skipped, created,
  updated and unchanged counts. A short corpus is reported, not an error.
- **BREAKING** (internal to `apps/ingestion`): the client's record iteration yields a
  paper *or* nothing for each fetched record, instead of silently dropping the
  unusable ones. Without this the command cannot count what it skipped. The rule that
  decides usability does not move; only the visibility of the outcome does.

## Capabilities

### New Capabilities
- `corpus-ingestion`: the operator-facing command that turns INSPIRE records into
  `Paper` rows — its parameters, its idempotent batched write behaviour, its
  reporting, its dry run, and its restartability.

### Modified Capabilities
- `inspire-client`: record iteration becomes observable. The requirement that skipped
  records never reach the database layer is restated — the guarantee moves from "the
  client never yields an unusable record" to "the client marks a record as unusable
  and its caller must not write it".

## Impact

- New: `apps/ingestion/management/commands/ingest_inspire.py` and its tests.
- Changed: `apps/ingestion/client.py` record iteration, and the client tests that
  assert on what iteration yields.
- Changed: settings gain a batch-size knob for the write path.
- `apps/papers` is unchanged — no migration, no model change. The `Paper` model and
  its non-empty-abstract constraint are already what this command needs.
- No new dependency. No change to `apps/search`, which must not import this app.
- Board card: HS-006.
