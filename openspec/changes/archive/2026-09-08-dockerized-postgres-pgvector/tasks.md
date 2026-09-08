## 1. Preflight

- [x] 1.1 Confirm the container engine is running (`docker info` reports a
      `ServerVersion`); start Rancher Desktop first if it is not
- [x] 1.2 Confirm nothing on the host or in another container is bound to the
      chosen host port 5433 (D5)
- [x] 1.3 Confirm `pgvector/pgvector:0.8.6-pg17-trixie` is present locally or
      pullable (D3)

## 2. Environment contract

- [x] 2.1 Create `.env.example` declaring exactly `POSTGRES_DB`,
      `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST` and `POSTGRES_PORT`
      (D1)
- [x] 2.2 Set `POSTGRES_HOST=localhost` and `POSTGRES_PORT=5433`, and add a
      comment stating these are host-side facts not passed into the container
      (D2, D5)
- [x] 2.3 Use placeholder values only; confirm no value is a credential for any
      system beyond the developer's machine
- [x] 2.4 Add a comment recording that Django assembles its `DATABASES` settings
      from these five variables at HS-003, and that no `DATABASE_URL` exists by
      design (D1)
- [x] 2.5 Verify `.gitignore` already ignores `.env` and that `.env.example` is
      not caught by that rule

## 3. Compose definition

- [x] 3.1 Create `compose.yaml` with a top-level `name: hepsearch` (D4)
- [x] 3.2 Define a single `db` service pinned to
      `pgvector/pgvector:0.8.6-pg17-trixie`, with no `build:` stanza (D3)
- [x] 3.3 Pass only `POSTGRES_DB`, `POSTGRES_USER` and `POSTGRES_PASSWORD` in
      `environment:`; confirm `POSTGRES_HOST` and `POSTGRES_PORT` are absent
      from it (D2)
- [x] 3.4 Add `POSTGRES_INITDB_ARGS: "--encoding=UTF8 --locale=C.UTF-8"` (D8)
- [x] 3.5 Map ports as `"${POSTGRES_PORT:-5433}:5432"`, confirming `5432`
      appears exactly once in the file (D2, D5)
- [x] 3.6 Give every variable reference a `${VAR:-default}` fallback so the
      service starts with no `.env` present (D6)
- [x] 3.7 Attach a named volume for `/var/lib/postgresql/data` and declare it
      under a top-level `volumes:` key
- [x] 3.8 Add `shm_size: 256mb` with a comment naming HS-010's ANN index build
      as the reason (D9)
- [x] 3.9 Add `restart: unless-stopped`
- [x] 3.10 Add a healthcheck running `pg_isready` with both `-U` and `-d`, plus
      explicit `interval`, `timeout`, `retries` and `start_period` (D7)
- [x] 3.11 Run `docker compose config` and confirm it renders without warnings
      or unset-variable errors

## 4. Bring-up and healthcheck verification

- [x] 4.1 Run `docker compose up -d` with no `.env` file present and confirm it
      succeeds with no unset-variable warning (D6)
- [x] 4.2 Time how long the service takes to report healthy, and set
      `start_period` from the observed value with headroom rather than a
      guessed number (D7, named risk)
- [x] 4.3 Confirm `docker compose ps` reports the service as healthy
- [x] 4.4 Confirm the created volume and container names derive from `hepsearch`
      and not from the `python` directory name (D4)

## 5. Database verification probes

- [x] 5.1 Query encoding, collation, ctype and locale provider; confirm UTF-8
      and `C.UTF-8` (D8)
- [x] 5.2 Query `default_text_search_config` and confirm it is
      `pg_catalog.english`, proving the locale choice does not compromise HS-007
- [x] 5.3 Query `pg_available_extensions` for `vector` and confirm a version is
      offered
- [x] 5.4 Run `CREATE EXTENSION IF NOT EXISTS vector;` and confirm it succeeds
- [x] 5.5 Run `SELECT extversion FROM pg_extension WHERE extname = 'vector';`
      and confirm a row is returned
- [x] 5.6 Measure `/dev/shm` inside the container and confirm it exceeds the
      64 MB default (D9)
- [x] 5.7 Capture the exact commands and their output for the commit body

## 6. Persistence verification

- [x] 6.1 Write a marker table or row into the application database
- [x] 6.2 Run `docker compose down`, then `docker compose up -d`, and confirm
      the marker survived
- [x] 6.3 Run `docker compose down -v`, start again, and confirm the database is
      re-initialised empty and the `vector` extension is gone — the concrete
      demonstration that the probe is not the mechanism (D10)
- [x] 6.4 Leave the environment in a working state (`up -d`, extension recreated
      if desired) before committing

## 7. Board and documentation amendments

- [x] 7.1 Rewrite HS-002's acceptance criteria against D2–D10: pinned tag,
      project name, initdb locale, shm size, restart policy, strict healthcheck,
      host port 5433, and zero-`.env` startup
- [x] 7.2 Reword HS-002's `CREATE EXTENSION` criterion explicitly as a probe
      proving image capability, and state that HS-010's migration is the
      mechanism (D10)
- [x] 7.3 Add the superuser constraint to HS-002's Context section (D12)
- [x] 7.4 Update HS-002's `.env.example` criteria to describe the five-variable
      host-perspective contract (D1, D2)
- [x] 7.5 Amend HS-003's environment criterion: replace `DATABASE_URL` with DSN
      assembly from the `POSTGRES_*` variables (D1)
- [x] 7.6 Add a note to HS-010 that its `CreateExtension` migration succeeds
      locally only because the Compose user is a superuser, since `vector` is
      untrusted (D12)
- [x] 7.7 Add `docker compose down -v` to AGENTS.md §5 with an explicit warning
      that it destroys the volume, the data and the probed extension
- [x] 7.8 Confirm AGENTS.md §2's "Compose for Postgres only" claim still matches
      what was built

## 8. Finish

- [x] 8.1 `git mv` the HS-002 card from `board/backlog/` to `board/in-progress/`
      at the start of implementation and to `board/done/` in the final commit
- [x] 8.2 Tick every acceptance-criterion checkbox on the HS-002 card to reflect
      reality, and set its status to done
- [x] 8.3 Run `uv run ruff check .` and `uv run ruff format --check .` and
      confirm both still pass (no Python changed, but the gate is the gate)
- [x] 8.4 Run `uv run pytest` and confirm the HS-001 smoke tests still pass
- [x] 8.5 Confirm `.env` is absent or ignored and that no secret is staged
- [x] 8.6 Commit as `HS-002: Run PostgreSQL with pgvector via Docker Compose`,
      recording the verification commands and their output in the body
- [x] 8.7 Mark all tasks complete and note that the directory rename is the next
      standalone commit, requiring a session restart (D11)
