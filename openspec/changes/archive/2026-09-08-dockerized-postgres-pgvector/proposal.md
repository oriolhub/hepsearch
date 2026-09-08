## Why

The project has a verified Python toolchain but no database, so no card past
HS-002 can start: HS-003 needs something to run `migrate` against, HS-004 needs a
place to put migrations, and HS-010 needs the `vector` extension. Installing
PostgreSQL by hand is exactly the per-contributor drift this project exists to
avoid, and pgvector makes hand-installation worse — the extension has to be
compiled or packaged separately.

Exploration also turned up a defect worth fixing before it propagates: HS-002 and
HS-003 currently specify **two different spellings of the same database
credentials** (`POSTGRES_*` for Compose, `DATABASE_URL` for `django-environ`).
Neither tool can derive the other, and `.env` has no interpolation both honour,
so as written the credentials would be stored twice and drift on the first
password change.

## What Changes

- Add `compose.yaml` defining a single `db` service on
  `pgvector/pgvector:0.8.6-pg17-trixie`, an explicitly pinned tag verified by a
  throwaway spike to ship `vector` 0.8.6 on PostgreSQL 17.11.
- Add `.env.example` as the documented environment contract, using a single
  `POSTGRES_*` variable set expressed **from the host's point of view**, because
  Django runs on the host while only the database is containerised.
- Pin the Compose project name to `hepsearch` so volume and container names are
  independent of the repository directory — which still happens to be named
  `python` and is scheduled to be renamed.
- Configure a named volume, a strict `pg_isready` healthcheck with a
  `start_period`, `shm_size: 256mb`, `restart: unless-stopped`, and
  `--encoding=UTF8 --locale=C.UTF-8` at `initdb` time.
- Make every Compose variable use a `${VAR:-default}` fallback, so
  `docker compose up -d` works on a fresh clone with no `.env` present.
- **BREAKING (to a not-yet-written card):** amend HS-003 so Django assembles its
  DSN from `POSTGRES_*` instead of reading `DATABASE_URL`. Nothing is implemented
  against the old criterion yet, so the cost is one line of board text now
  instead of a duplicated-credential bug later.
- Record two facts the spike measured and the board did not know: `vector` is an
  untrusted, superuser-only extension, and a container's default `/dev/shm` is
  64 MB.
- Document `docker compose down -v` in AGENTS.md §5 with an explicit warning that
  it destroys the volume, and with it the extension created during verification.

## Capabilities

### New Capabilities

- `database-infrastructure`: How the local PostgreSQL service is defined,
  configured, started, verified and reset, and how its connection parameters are
  expressed as a single environment contract shared by Docker Compose and (from
  HS-003) Django.

### Modified Capabilities

<!-- None. openspec/specs/ is empty; the python-tooling spec from
     bootstrap-python-tooling has not been archived into main specs yet, and this
     change does not alter any of its requirements. -->

## Impact

**New files:** `compose.yaml`, `.env.example`.

**Amended board cards:**

- `HS-002` — acceptance criteria rewritten against the decisions below; the
  `CREATE EXTENSION` criterion reworded as a *probe* proving the image ships the
  extension, not as the mechanism that installs it.
- `HS-003` — the `DATABASE_URL` criterion replaced by DSN assembly from
  `POSTGRES_*`.
- `HS-010` — footnote that its `CreateExtension` migration succeeds locally only
  because the Compose user is a superuser.
- `AGENTS.md` §5 — add the destructive reset command with its warning.

**Dependencies:** none added. No Python package is installed by this change; the
database driver arrives with Django at HS-003, so HS-002 keeps its
no-automated-test posture and is verified by recorded shell commands.

**Environment:** requires a running container engine. This machine uses Rancher
Desktop, which also hosts a k3s cluster and other Compose projects — reinforcing
both the pinned project name and the non-default host port 5433.

**Deferred:** renaming the repository directory to `hepsearch` is a separate
commit after this change lands, because it invalidates the working directory of
any running shell. Pinning the Compose project name means the rename carries no
data risk.
