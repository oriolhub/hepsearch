# database-infrastructure Specification

## Purpose
TBD - created by archiving change dockerized-postgres-pgvector. Update Purpose after archive.
## Requirements
### Requirement: Single-command database startup

The project SHALL provide a Docker Compose definition that starts a PostgreSQL
service with the `vector` extension available, without any manual installation,
compilation or configuration step.

#### Scenario: Starting the database from a clean checkout

- **WHEN** a developer runs `docker compose up -d` in the repository root
- **THEN** exactly one service named `db` starts
- **AND** no database software has to be installed on the host

#### Scenario: No environment file present

- **WHEN** `docker compose up -d` is run and no `.env` file exists
- **THEN** the service still starts successfully using the defaults declared in
  `compose.yaml`
- **AND** Compose emits no warning about unset variables

#### Scenario: Stopping the database

- **WHEN** a developer runs `docker compose down`
- **THEN** the container is removed and the named volume is retained

### Requirement: Explicitly pinned database image

The Compose definition SHALL reference a PostgreSQL image that already ships
pgvector, pinned to an explicit immutable-by-convention tag. It SHALL NOT use
`latest`, and SHALL NOT build a custom image.

#### Scenario: Image tag is fully qualified

- **WHEN** the `image:` value of the `db` service is inspected
- **THEN** it names a pgvector-bearing image with an explicit version, PostgreSQL
  major version and base-OS component
- **AND** the tag does not contain `latest`

#### Scenario: PostgreSQL major version is supported by the target framework

- **WHEN** the pinned PostgreSQL major version is compared to the versions
  supported by Django 5.2
- **THEN** it falls inside the supported range

#### Scenario: No Dockerfile is introduced

- **WHEN** the repository is searched for a Dockerfile belonging to the database
- **THEN** none exists

### Requirement: Compose project identity independent of directory name

The Compose definition SHALL declare an explicit project name, so that container
and volume names do not depend on the name of the directory the repository
happens to be checked out into.

#### Scenario: Volume name after startup

- **WHEN** the database has been started and volumes are listed
- **THEN** the volume name is derived from the declared project name, not from
  the enclosing directory name

#### Scenario: Repository directory is renamed

- **WHEN** the repository directory is renamed and the database is started again
- **THEN** Compose reuses the same project, container and volume
- **AND** previously stored data is still present

### Requirement: Single environment contract expressed from the host

Database connection parameters SHALL be defined exactly once, in a single
`POSTGRES_*` variable set expressed from the host's point of view, because the
application runs on the host while only the database is containerised. The
project SHALL NOT define a second, redundant spelling of the same credentials.

#### Scenario: No duplicated credential representation

- **WHEN** `.env.example` is inspected
- **THEN** each credential fact — database name, user, password, host and port —
  appears exactly once
- **AND** no combined connection-URL variable duplicates those values

#### Scenario: Port variable refers to the host port

- **WHEN** the port variable is used in `compose.yaml`
- **THEN** it supplies the host side of the port mapping
- **AND** the container side of the mapping is the fixed PostgreSQL default port

#### Scenario: Host-only variables are not injected into the container

- **WHEN** the `environment:` block of the `db` service is inspected
- **THEN** it passes only the variables the PostgreSQL image entrypoint consumes
- **AND** the host and port variables are absent from it, because they describe
  how the host reaches the container rather than how the container configures
  itself

#### Scenario: Every variable is documented with a working default

- **WHEN** each variable referenced in `compose.yaml` is checked
- **THEN** it is present in `.env.example` with a placeholder value
- **AND** it is referenced with a default-value fallback in `compose.yaml`

### Requirement: Committed environment example, uncommitted environment file

The repository SHALL commit `.env.example` containing placeholder values only,
and SHALL NOT commit `.env`.

#### Scenario: Example file is tracked

- **WHEN** the git index is inspected
- **THEN** `.env.example` is tracked

#### Scenario: Real environment file is ignored

- **WHEN** a `.env` file is created in the repository root
- **THEN** git reports it as ignored rather than untracked

#### Scenario: No real secret is committed

- **WHEN** the values in `.env.example` are inspected
- **THEN** every value is a local-development placeholder
- **AND** none is a credential for any system outside the developer's machine

### Requirement: Data persists across the ordinary stop/start cycle

The database SHALL store its data in a named volume so that stopping and
restarting the service preserves data, and SHALL only lose data when the volume
is destroyed explicitly.

#### Scenario: Data survives down and up

- **WHEN** data is written, then `docker compose down` is run, then
  `docker compose up -d`
- **THEN** the previously written data is still present

#### Scenario: Data is destroyed only on explicit volume removal

- **WHEN** `docker compose down -v` is run and the service is started again
- **THEN** the database is re-initialised empty

### Requirement: Healthcheck reports readiness of the real server

The `db` service SHALL define a healthcheck that verifies the target database is
reachable as the configured user, and SHALL allow a startup grace period so that
the temporary server the PostgreSQL entrypoint runs during initialisation is not
mistaken for the real one.

#### Scenario: Service becomes healthy

- **WHEN** the service has finished starting
- **THEN** its health status is reported as healthy

#### Scenario: Healthcheck names the user and database

- **WHEN** the healthcheck command is inspected
- **THEN** it passes both the configured user and the configured database name
  rather than relying on defaults

#### Scenario: Startup grace period is configured

- **WHEN** the healthcheck definition is inspected
- **THEN** it declares a start period, an interval, a timeout and a retry count

### Requirement: Database initialised with a deterministic encoding and locale

The database SHALL be initialised with UTF-8 encoding and a deterministic
collation, chosen explicitly rather than inherited from the image default,
because these are fixed at initialisation time and can only be changed by
destroying the volume.

#### Scenario: Encoding and collation are as configured

- **WHEN** the encoding, collation and character type of the application
  database are queried
- **THEN** the encoding is UTF-8
- **AND** the collation and character type match the explicitly configured locale

#### Scenario: Full-text search default is unaffected

- **WHEN** the server's default text search configuration is queried
- **THEN** it is the English configuration, so the chosen locale does not
  compromise the full-text search capability planned for a later card

### Requirement: Shared memory sized for later index builds

The `db` service SHALL declare a shared-memory size larger than the container
default, because approximate-nearest-neighbour index builds and parallel query
execution exhaust the default allocation.

#### Scenario: Shared memory exceeds the container default

- **WHEN** the shared-memory filesystem inside the running container is measured
- **THEN** its size is greater than the 64 MB container default

#### Scenario: The reason is recorded

- **WHEN** the shared-memory setting in `compose.yaml` is read
- **THEN** an adjacent comment names the later card whose index build motivates it

### Requirement: The vector extension is verifiably available

The chosen image SHALL make the `vector` extension installable, and this change
SHALL verify that fact. Verification is a **probe** demonstrating the image's
capability; it is NOT the mechanism by which the extension is installed for
application use, which remains a Django migration in a later card.

#### Scenario: Extension is offered by the server

- **WHEN** the server's available extensions are queried for `vector`
- **THEN** a row is returned reporting an available version

#### Scenario: Extension can be created

- **WHEN** `CREATE EXTENSION IF NOT EXISTS vector;` is executed against the
  application database
- **THEN** the statement succeeds

#### Scenario: Installed version is reportable

- **WHEN** the installed extension version is queried from the system catalogue
- **THEN** a row is returned

#### Scenario: The probe is not load-bearing

- **WHEN** the acceptance criteria and card text are read
- **THEN** they state that the extension is installed for application use by a
  migration in the later pgvector card
- **AND** they warn that destroying the volume removes the probed extension

### Requirement: Privilege requirement of the vector extension is documented

The project SHALL record that `vector` is an untrusted extension requiring
superuser privileges to install, and that the local Compose user is a superuser,
in the place where the card that writes the extension migration will encounter
it.

#### Scenario: Constraint is recorded on the later card

- **WHEN** the board card that adds the extension migration is read
- **THEN** it states that the migration succeeds locally only because the
  Compose-provisioned user holds superuser rights

