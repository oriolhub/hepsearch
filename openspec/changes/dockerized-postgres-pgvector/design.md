## Context

HS-001 established a verified Python toolchain. Nothing else can proceed without
a database: HS-003 needs a target for `migrate`, HS-004 needs somewhere to apply
migrations, HS-007 needs PostgreSQL full-text search, and HS-010 needs the
`vector` extension.

AGENTS.md §2 fixes the shape: Compose runs **only** the database, and Django runs
on the host under `uv` for a fast edit-reload loop. That single constraint drives
most of what follows — in particular, it means the environment contract is
written from the host's point of view, because the client of this database is a
host process.

Exploration was grounded in a throwaway spike against the real image rather than
in documentation. The spike measured six things, three of which the board did not
know:

| Probe | Result |
|---|---|
| `server_version` | `17.11 (Debian 17.11-1.pgdg13+2)` |
| `vector` available / creatable | `0.8.6`, `CREATE EXTENSION` succeeds |
| encoding / collate / ctype / provider | `UTF8` / `C.UTF-8` / `C.UTF-8` / `c` |
| `default_text_search_config` | `pg_catalog.english` — **unaffected by C.UTF-8** |
| `vector` trusted / superuser | **`f` / `t`** — untrusted, superuser-only |
| `/dev/shm` | **64 MB** — the container default |

The host runs Rancher Desktop (`docker` 29.5.3-rd, Compose v5.1.4), not Docker
Desktop, and that engine additionally hosts a k3s cluster and two unrelated
Compose projects. Ports 5432 and 5433 are both free and no PostgreSQL is
installed on the host — there is also no `psql` client on the host, so every
database probe must run through `docker compose exec`.

## Goals / Non-Goals

**Goals:**

- One command starts a PostgreSQL that already has `vector` available, with no
  host-side installation and no custom image build.
- Exactly one representation of the database credentials, shared by Compose now
  and Django from HS-003.
- Container and volume identity that does not depend on the repository directory
  name, which is currently `python` and scheduled to be renamed.
- Choices that are expensive to change later — encoding, collation, shared
  memory — made deliberately now rather than discovered under a failing index
  build.
- Every claim in the card verified by a command whose output is recorded in the
  commit body.

**Non-Goals:**

- Any Django settings, database driver or connection code (HS-003).
- Installing `vector` for application use; that is a migration at HS-010. This
  change only proves the image *can* install it.
- Containerising the application (a permanent non-goal, AGENTS.md §2).
- Production-grade role separation, TLS, backups, or tuning beyond the one
  setting a later card is known to need.
- Renaming the repository directory — a separate commit, because it invalidates
  the working directory of every running shell.

## Decisions

### D1: Single `POSTGRES_*` contract; Django assembles the DSN at HS-003

**Why:** HS-002 and HS-003 as written specified two spellings of one truth —
`POSTGRES_*` for Compose, `DATABASE_URL` for `django-environ`. The PostgreSQL
entrypoint reads only `POSTGRES_*`; `django-environ`'s `db_url()` wants a URL.
Neither derives the other, and `.env` has no interpolation both tools honour
(Compose expands `${VAR}` for its own use; `django-environ` does not expand at
all). Storing both means the password exists twice and drifts on first change.

**Chosen:** `.env` carries `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`,
`POSTGRES_HOST`, `POSTGRES_PORT`. Compose consumes them; HS-003's `settings.py`
assembles Django's `DATABASES` dict from the same five values.

**Alternatives rejected:** *Both variables* — matches the cards as written but
guarantees drift. *`DATABASE_URL` as the source, parsed for Compose* — requires
shell-parsing a URL inside `compose.yaml`, which is grotesque and fragile.

**Cost:** amends one line of HS-003. Nothing is implemented against the old
criterion, so this is the cheapest moment it will ever be.

### D2: The environment contract is written from the host's point of view

**Why:** Django runs on the host, so "host" and "port" mean *how the host reaches
the database*, not how the container configures itself. The container always
listens on 5432; only the published port varies.

**Chosen:** `POSTGRES_HOST=localhost` and `POSTGRES_PORT=5433` are host-side
facts, used for the host half of the port mapping and later by `settings.py`.
They are deliberately **not** listed under the service's `environment:` block —
only `POSTGRES_DB`, `POSTGRES_USER` and `POSTGRES_PASSWORD` are, because those
are what the image entrypoint consumes. `5432` appears exactly once in the whole
file, as the container side of the mapping.

**Alternatives rejected:** *`DB_*` prefixes* would make the boundary obvious but
require a translation layer in `compose.yaml` and diverge from the names every
PostgreSQL image tutorial uses. *Mixed prefixes encoding the boundary* is
self-documenting but reads as inconsistency. A comment in `.env.example`
achieves the same clarity for free.

### D3: Pin `pgvector/pgvector:0.8.6-pg17-trixie`

**Why:** the image already ships pgvector, so no Dockerfile is needed — building
one is exactly the work this card exists to avoid. PostgreSQL 17 sits squarely
inside Django 5.2's supported range, whereas PostgreSQL 18 postdates Django
5.2's release and is untested against it. The tag names the extension version,
the server major and the base OS, so nothing about it is implicit.

**Alternatives rejected:** *`pg18`* — newest, but buys nothing this project needs
and trades a supported combination for an unverified one. *Digest pinning* —
maximally reproducible but unreadable and annoying to bump, disproportionate for
a local development database. *`latest`* — explicitly forbidden by the card.

### D4: Pin the Compose project name to `hepsearch`

**Why:** Compose derives the project name from the directory, which is currently
`python`. That would produce `python_pgdata` and `python-db-1`, and the planned
directory rename would then orphan the volume — data appearing to vanish. A
top-level `name:` decouples project identity from the filesystem permanently,
including for anyone who clones into a differently-named directory.

**Consequence:** the rename becomes a safe, boring operation that can happen at
any time. This is what allows D11's sequencing.

### D5: Host port 5433, not 5432

**Why:** 5432 is free on this machine, but the machine is not the constraint —
any contributor with a local PostgreSQL install would collide, and this engine
already hosts unrelated projects. 5433 is collision-proof, costs nothing, and is
overridable via `POSTGRES_PORT` anyway.

### D6: Defaults in `compose.yaml`, so `up -d` works with no `.env`

**Why:** the card's promise is "one command". Requiring a `cp .env.example .env`
step first makes it two, and a fresh clone that fails on an unset-variable
warning is a poor first impression.

**Chosen:** every reference uses `${VAR:-default}`. `.env.example` remains the
documentation of what those variables are and stays the thing a developer copies
when they want to change one.

**Accepted trade-off:** a default password lives in a committed file. This is a
local-only development database bound to localhost with a placeholder credential;
it is recorded here as a deliberate decision so it is not later mistaken for a
leaked secret.

### D7: Healthcheck probes over TCP, with a measured start period

**Why:** the PostgreSQL entrypoint starts a *temporary* server during `initdb` to
run initialisation scripts, then shuts it down and starts the real one. A
`pg_isready` that reaches the server over the Unix socket can succeed against
that temporary server, reporting the container healthy while the real server is
still restarting. This matters directly at HS-003, where `manage.py migrate` runs
immediately after `up -d`.

**Corrected during implementation.** This decision originally claimed
`start_period` was the mitigation. That was wrong: `start_period` suppresses
false *negatives* (it stops early failures from counting as retries) and does
nothing whatsoever about the false *positive* described above.

The container log timeline made the real mechanism visible:

```
21.991  PID 48  temp server → listening on Unix socket ONLY
22.015  PID 48  "ready to accept connections"    ┐ 366 ms window
22.381  PID 48  "database system is shut down"   ┘
22.482  PID 1   real server → listening on IPv4 0.0.0.0:5432 + IPv6
22.512  PID 1   "ready to accept connections"
25.935  healthcheck probe #1
```

The temporary server never binds TCP; only the real server does.

**Chosen:** `pg_isready -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"`. The
`-h 127.0.0.1` forces a TCP probe, which cannot observe the temporary server at
all — the false positive is eliminated structurally rather than by hoping the
probe lands after the window closes. Naming the user and database additionally
prevents a false pass against the default `postgres` database. `start_period` is
retained at a measured 10s (cold initdb boot reaches healthy in ~6s here), but
its job is correctly understood as tolerating slow startup, not as correctness.

**Alternative considered:** `psql -c 'SELECT 1'` proves the real server answers
queries and is strictly stronger, but it is slower, noisier in logs, and
requires authentication to succeed. The TCP-scoped `pg_isready` closes the same
gap more cheaply.

### D8: Explicit `--encoding=UTF8 --locale=C.UTF-8` at initdb

**Why:** encoding and collation are fixed at initialisation and can only be
changed by destroying the volume, so inheriting them implicitly from the image is
a decision made by accident. `C.UTF-8` gives deterministic byte-order collation
and faster index behaviour; the alternative, `en_US.utf8`, buys linguistic
sorting this project has no requirement for.

**Verified, not assumed:** the obvious worry is that a `C` locale degrades the
full-text search HS-007 depends on. The spike confirmed
`default_text_search_config` remains `pg_catalog.english` under `C.UTF-8`, and
Django selects the search configuration per query (`SearchVector(config=...)`)
regardless. The concern does not apply.

### D9: `shm_size: 256mb` now, not at HS-010

**Why:** measured, not guessed — `/dev/shm` in the running container is 64 MB.
That is the documented cause of "could not resize shared memory segment" during
parallel query and large index builds, which is precisely what HS-010's ANN index
build does. Setting it is one line today; hitting it at HS-010 is an obscure
debugging session whose error message points nowhere near Compose.

This deliberately overrides the project's default bias toward deferring work: the
fix is one line and the deferral has a known, specific cost.

### D10: `CREATE EXTENSION` here is a probe; the migration at HS-010 is the mechanism

**Why:** an extension created by hand lives in the volume, not in git.
`docker compose down -v` silently removes it. More decisively, Django builds a
**fresh `test_hepsearch` database** for every test run, so a manually created
extension in `hepsearch` does nothing for tests — a migration is unavoidable
regardless of what this card does.

**Chosen:** HS-002 runs `CREATE EXTENSION IF NOT EXISTS vector;` purely to prove
the image ships it, and the card says so in those words. HS-010 already requires
`CreateExtension` "not a manual `psql` step", so no amendment is needed there for
this decision — only for D12.

**Alternative rejected:** an `/docker-entrypoint-initdb.d/` script. It runs only
on first initialisation, so it silently does nothing on an existing volume,
creating a second half-working mechanism competing with the migration.

### D11: The directory rename ships after this change, as its own commit

**Why:** renaming the repository directory invalidates the working directory of
every running process, including the shell driving the implementation. Doing it
mid-change would strand the work.

**Chosen:** implement and commit HS-002 first, then rename as a standalone
commit, then restart the session in the new path. D4's pinned project name means
the volume is named `hepsearch_pgdata` from the very first `up -d`, so the rename
carries no data risk in either order.

### D12: The superuser constraint is recorded on HS-010, not just here

**Why:** the spike measured `vector` as `trusted = f, superuser = t`. It installs
cleanly only because the Compose entrypoint makes `POSTGRES_USER` a superuser.
That is invisible locally and would be the first thing to break anywhere else.

**Chosen:** state it in HS-002's Context, where the decision is made, **and** as a
note on HS-010, where the `CreateExtension` migration is actually written. A risk
recorded only in a design document that gets archived is a risk nobody reads.

## Risks / Trade-offs

**`start_period` was mis-reasoned in the original design** → Found and corrected
during implementation, not left latent. The container log showed a 366 ms window
in which the temporary initdb server reported ready; the first probe happened to
land 3.4 s after it closed. Mitigation is now structural (TCP-scoped probe, D7)
rather than dependent on probe timing.

**`C.UTF-8` is baked in at initdb and needs a volume destroy to change** →
Mitigated by D8's verification that it does not affect full-text search, which
was the only plausible reason to want a different locale. If a linguistic-sorting
requirement ever appears, the corpus is re-ingestible by design.

**A default password sits in a committed file** → Accepted, recorded in D6. The
database binds to localhost, holds only public INSPIRE metadata, and has no
production counterpart in v1.

**`vector` needs superuser, which the local setup silently grants** → Not fixed,
deliberately (a separate application role is production concern-shaped work with
no production to serve). Mitigated by D12: written down where HS-010 will read it.

**HS-002 has no automated test, unlike every other card** → Accepted. A real test
needs a database driver, which means pulling `psycopg` forward from HS-003 to
test a file that is declarative configuration. Mitigation: the verification
commands and their output go in the commit body, and HS-003's `/api/health/` test
is the first genuine automated proof that the database is reachable.

**Compose v5 and a Rancher Desktop engine differ from the more common Docker
Desktop setup** → Low risk; the compose file uses no exotic features. Mitigated by
the fact that every acceptance criterion is executed on this engine before the
card is closed.

## Migration Plan

There is no deployed system and no data to migrate. Rollback is deleting
`compose.yaml` and `.env.example`; `docker compose down -v` removes all created
state. The only ordering constraint is D11: rename the directory after this
change is committed, not before or during.

## Open Questions

- Should `POSTGRES_HOST` exist at all while the only possible value is
  `localhost`? Keeping it means HS-003's settings code has no hardcoded host and
  nothing changes if the database ever moves. Leaning keep; revisit if it is
  still a constant by HS-013.
- Is `restart: unless-stopped` the right default on a shared machine that already
  runs a k3s cluster? It is convenient across reboots but means a background
  container the developer did not consciously start. Chosen as convenient for
  now; trivially reversible.
