## 1. Board and configuration

- [x] 1.1 `git mv board/backlog/HS-006-ingest-command.md board/in-progress/`
- [x] 1.2 Add `INGEST_BATCH_SIZE` to `config/settings.py`, defaulting to the INSPIRE
      page size so one batch is one fetched page
- [x] 1.3 Add a `DEFAULT_INGEST_QUERY` constant for the Higgs boson corpus, used as the
      command's `--query` default

## 2. Make skipped records observable (client change)

- [x] 2.1 Change `iter_records` in `apps/ingestion/client.py` to yield one result per
      fetched record — the `Paper` or `None` — instead of dropping the `None`s
- [x] 2.2 Keep the limit counting only the papers, so a caller asking for N still
      receives N usable papers; the pagination and result-window behaviour is unchanged
- [x] 2.3 Update `InspireClient.iter_papers` to match the new yield type
- [x] 2.4 Update the existing `iter_records` tests to assert one result per fetched
      record, and add a test that an unusable record appears as an explicit skip
- [x] 2.5 Run `uv run pytest apps/ingestion` — the client suite is green before any
      command code is written

## 3. The write path

- [x] 3.1 Create the `apps/ingestion/management/commands/` package
- [x] 3.2 Write a pure function that, given a batch of incoming papers and the matching
      stored rows, partitions them into created / updated / unchanged — no database, no
      network, so it is testable directly
- [x] 3.3 Derive its comparison field list from the `Paper` model's concrete fields
      minus id, `created_at` and `updated_at`, so it cannot drift as the model grows
- [x] 3.4 Test the partition function directly: a new paper, an identical paper, a
      paper differing only in `citation_count`, and a paper differing in a list field
- [x] 3.5 Write the batch writer: one `SELECT` by `inspire_id`, then `bulk_create` for
      the new and `bulk_update` for the changed, inside `transaction.atomic()`
- [x] 3.6 Set `updated_at` explicitly on the changed papers and name it in the
      `bulk_update` fields — `bulk_update` does not apply `auto_now`
- [x] 3.7 Test that an unchanged paper's `updated_at` does not move and a changed
      paper's does

## 4. The command

- [x] 4.1 Add `ingest_inspire` with `--query`, `--limit` and `--dry-run` arguments
- [x] 4.2 Consume the client's results, filtering the papers from the skips and
      counting fetched, skipped, created, updated and unchanged
- [x] 4.3 Group the papers into batches of `settings.INGEST_BATCH_SIZE` and write each
      one; in dry-run mode run the same partition and skip only the two write calls
- [x] 4.4 Write one progress line per batch through `self.stdout.write`
- [x] 4.5 Print the final five-count summary
- [x] 4.6 Report the shortfall and exit 0 when fewer papers were landed than requested
- [x] 4.7 Do not catch `KeyboardInterrupt` — a bare traceback is the accepted behaviour

## 5. Command tests

- [x] 5.1 Add a test module that patches the network at the module seam and serves the
      committed INSPIRE fixture
- [x] 5.2 Test a first run: papers are stored, abstract-less records are skipped and
      counted, every stored paper has an abstract
- [x] 5.3 Test idempotence: run twice, assert the row count is unchanged, each
      `inspire_id` appears once, and the second run reports zero created
- [x] 5.4 Test that a changed incoming record updates the stored row and moves its
      `updated_at`, while an unchanged one moves neither
- [x] 5.5 Test that `created_at` survives an update
- [x] 5.6 Test `--dry-run`: nothing is stored, nothing is modified, and the reported
      created/updated counts match what a real run would do
- [x] 5.7 Test that a corpus smaller than `--limit` reports the shortfall and exits 0
- [x] 5.8 Test that the command module does not import `apps.search`
- [x] 5.9 Capture stdout via `call_command(..., stdout=...)` and assert a progress line
      per batch and the five summary counts

## 6. Real run and close out

- [x] 6.1 `docker compose up -d --wait` and `uv run python manage.py migrate`
- [x] 6.2 Smoke test with `--dry-run --limit 20` against the live API
- [x] 6.3 Run `uv run python manage.py ingest_inspire --query "higgs boson" --limit 5000`
      and record the resulting counts
- [x] 6.4 Re-run the same command and confirm the row count is unchanged and the
      summary reports zero created
- [x] 6.5 `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`
- [x] 6.6 Tick the acceptance criteria and definition of done on the HS-006 card
- [x] 6.7 `git mv board/in-progress/HS-006-ingest-command.md board/done/` and commit
      everything as `HS-006: Ingest a real corpus with a management command`, with the
      real run's counts in the body
