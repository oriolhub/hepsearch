# HS-002: Run PostgreSQL with pgvector via Docker Compose

**Status:** done
**Depends on:** HS-001
**OpenSpec change:** `dockerized-postgres-pgvector`

## Story

As a developer, I want a one-command local PostgreSQL with the `vector`
extension available, so that I never have to install or configure a database by
hand and every contributor gets an identical one.

## Context

Compose runs **only the database**; Django runs on the host through `uv` for a
fast edit-reload loop (AGENTS.md §2). That single constraint shapes the
environment contract: `POSTGRES_HOST` and `POSTGRES_PORT` describe how a *host*
process reaches the container, so they are host-side facts and are deliberately
not injected into it.

Use an image that already ships pgvector (the `pgvector/pgvector` images) rather
than building a custom one — installing the extension by hand is exactly the
kind of work this card exists to avoid.

The extension must be *available* here; the `VectorField` and the index that use
it arrive in HS-010. **`vector` is an untrusted, superuser-only extension**
(`pg_available_extension_versions` reports `trusted = f, superuser = t`). It
installs cleanly here only because the Compose entrypoint makes `POSTGRES_USER` a
superuser. That is invisible locally and would be the first thing to break in any
environment with a least-privilege application role — see the note on HS-010.

This card also fixes a defect found while exploring it: HS-002 and HS-003
specified two different spellings of the same credentials (`POSTGRES_*` versus
`DATABASE_URL`). Neither tool can derive the other, so HS-003 was amended to
assemble Django's DSN from the `POSTGRES_*` set.

Decisions and their alternatives are recorded in
`openspec/changes/dockerized-postgres-pgvector/design.md`.

## Acceptance criteria

### Environment contract

- [x] **This card creates `.env.example`** — it is the first card that introduces
      an environment variable, so ownership moved here from HS-001, where the AC
      was unverifiable
- [x] `.env.example` declares exactly five variables: `POSTGRES_DB`,
      `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`
- [x] There is **no** `DATABASE_URL` — every credential fact appears exactly once
- [x] `POSTGRES_HOST` and `POSTGRES_PORT` are documented as host-side facts and
      do not appear in the service's `environment:` block
- [x] `.env.example` is committed with placeholder values and never real secrets;
      `.env` itself stays git-ignored and uncommitted

### Compose service

- [x] `compose.yaml` defines a single `db` service using a Postgres image with
      pgvector preinstalled, pinned to an explicit tag (never `latest`) —
      `pgvector/pgvector:0.8.6-pg17-trixie`
- [x] A top-level `name: hepsearch` pins the project, so container and volume
      names do not depend on the checkout directory name
- [x] No Dockerfile is introduced
- [x] Every variable is referenced as `${VAR:-default}`, so `docker compose up -d`
      succeeds on a fresh clone with **no `.env` file at all**
- [x] `POSTGRES_INITDB_ARGS` sets `--encoding=UTF8 --locale=C.UTF-8`
- [x] `shm_size` is raised above the 64 MB container default, for HS-010's index
      build
- [x] `restart: unless-stopped` is set
- [x] A named volume persists data across `docker compose down` / `up`
- [x] The host port is 5433, avoiding a collision with a local Postgres on 5432

### Healthcheck

- [x] A healthcheck using `pg_isready` reports the service healthy
- [x] It names both the user and the database, so it cannot pass against the
      default `postgres` database
- [x] It probes over **TCP** (`-h 127.0.0.1`), because the temporary server the
      entrypoint runs during `initdb` listens on the Unix socket only — a
      socket-based probe can report healthy against a server about to shut down
- [x] `interval`, `timeout`, `retries` and `start_period` are all explicit, with
      `start_period` set from a measured cold boot rather than guessed

### Extension verification

- [x] `docker compose up -d` then connecting and running
      `CREATE EXTENSION IF NOT EXISTS vector;` succeeds
- [x] `SELECT extversion FROM pg_extension WHERE extname = 'vector';` returns a row
- [x] **This is a probe, not the mechanism.** It proves the image ships the
      extension. The extension is installed for application use by a Django
      migration in HS-010, which is mandatory regardless, because Django builds a
      fresh test database for every test run
- [x] `docker compose down -v` is demonstrated to destroy the installed
      extension while leaving it *available* to install again

### Database configuration

- [x] Encoding is UTF-8 and collation/ctype are `C.UTF-8`
- [x] `default_text_search_config` is verified to still be `pg_catalog.english`,
      so the locale choice does not compromise HS-007's full-text search
- [x] `/dev/shm` inside the running container measures above 64 MB

## Definition of done

- [x] Acceptance criteria met
- [x] `uv run ruff check .` and `uv run ruff format --check .` both pass
- [x] `uv run pytest` still passes
- [x] The verification commands are recorded in the commit body
- [x] Committed as `HS-002: Run PostgreSQL with pgvector via Docker Compose`

## Out of scope

Django database settings (HS-003), migrations (HS-004), the vector column and
its index (HS-010), containerising the app itself (never — see AGENTS.md §2).
No automated test: a real one needs a database driver, which arrives with Django
at HS-003, whose `/api/health/` test is the first genuine automated proof that
the database is reachable.
