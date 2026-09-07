# HS-002: Run PostgreSQL with pgvector via Docker Compose

**Status:** backlog
**Depends on:** HS-001

## Story

As a developer, I want a one-command local PostgreSQL with the `vector`
extension available, so that I never have to install or configure a database by
hand and every contributor gets an identical one.

## Context

Compose runs **only the database**; Django runs on the host through `uv` for a
fast edit-reload loop (AGENTS.md §2). Use an image that already ships pgvector
(the `pgvector/pgvector` images) rather than building a custom one — installing
the extension by hand is exactly the kind of work this card exists to avoid.

The extension must be *available* here; the `VectorField` and the index that use
it arrive in HS-010.

## Acceptance criteria

- [ ] `compose.yaml` defines a single `db` service using a Postgres image with
      pgvector preinstalled, pinned to an explicit tag (never `latest`)
- [ ] Credentials, database name, and host port come from environment variables
      with sane local defaults, and are documented in `.env.example`
- [ ] A named volume persists data across `docker compose down` / `up`
- [ ] A healthcheck using `pg_isready` reports the service healthy
- [ ] `docker compose up -d` then connecting and running
      `CREATE EXTENSION IF NOT EXISTS vector;` succeeds
- [ ] `SELECT extversion FROM pg_extension WHERE extname = 'vector';` returns a row
- [ ] The chosen host port does not collide with a default local Postgres on
      5432, or the collision is documented in `.env.example`

## Definition of done

- [ ] Acceptance criteria met
- [ ] The verification commands are recorded in the commit body
- [ ] Committed as `HS-002: Run PostgreSQL with pgvector via Docker Compose`

## Out of scope

Django database settings (HS-003), migrations (HS-004), the vector column and
its index (HS-010), containerising the app itself (never — see AGENTS.md §2).
