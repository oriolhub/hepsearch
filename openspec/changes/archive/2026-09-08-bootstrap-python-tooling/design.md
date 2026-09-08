## Context

hepsearch has an agreed architecture (`AGENTS.md`) and a dependency-ordered board
of 15 cards, but no Python project exists. Every card's definition of done is
expressed in terms of `uv run pytest` and `uv run ruff check .`, so no card is
verifiable until this change lands.

Verified state of the development machine: `uv 0.11.16`, `Python 3.13.1`,
`Docker 29.5.3`, `git 2.55.0`. `ruff` is not installed globally and will be
provided through the dev dependency group.

The layout this tooling must serve is fixed by `AGENTS.md` §3:

```
config/            Django settings package        (created by HS-003)
apps/papers/       domain                          (HS-004)
apps/ingestion/    INSPIRE client + commands       (HS-005, HS-006)
apps/search/       ranking, DRF views, templates   (HS-007+)
tests/             project-level tests             (this change)
```

Nothing in that tree is an installable distribution. That single fact drives most
of the decisions below.

## Goals / Non-Goals

**Goals:**

- A clean checkout reaches a passing test run and a passing lint run with one
  install command.
- The environment resolves identically on any machine (locked versions, pinned
  interpreter).
- Configuration choices that would otherwise be discovered by failure — package
  mode, import path — are made explicitly and recorded.
- Lint rules that protect later cards are enabled *now*, while there is no code
  to retrofit them onto.
- The board stops containing acceptance criteria that cannot be verified when
  their card is worked.

**Non-Goals:**

- Django, DRF, or any settings module. That is HS-003.
- Any database or `DATABASE_URL`. That is HS-002.
- `.env` / `.env.example` handling — deliberately handed to HS-002 and HS-003,
  which are the first cards that actually read an environment variable.
- CI. A recorded non-goal for v1 in `AGENTS.md` §2.
- Type checking with `mypy`. Not chosen; may be reconsidered if the domain grows
  complex enough to earn it.
- Coverage measurement and thresholds. A coverage number with no consumer is
  ceremony.

## Decisions

### D1: Application mode — `[tool.uv] package = false`, no build backend

**Why:** `uv` treats a `pyproject.toml` containing a `[build-system]` as a
distributable project and attempts to build and install it into the environment.
It would look for a `hepsearch/` importable package. Our code lives in `apps/`
and `config/`, so the build fails.

*Alternatives considered:*

| Option | Verdict |
|---|---|
| `[tool.uv] package = false` | **Chosen.** One line, explicit, self-documenting |
| Omit `[build-system]` entirely | Works, but relies on inference — a future contributor adding a build backend silently breaks `uv sync` |
| Create a real `hepsearch/` package and a `src/` layout | Solves a distribution problem we do not have. A Django project is deployed by checkout, not by `pip install` |

Both the explicit flag *and* the absence of a build backend are specified, so the
intent survives a future edit.

### D2: Import resolution — `pytest`'s `pythonpath = ["."]`

**Why:** D1 means nothing is installed, so `from apps.papers.models import Paper`
has no import path. This surfaces at HS-004, four cards away, as a
`ModuleNotFoundError` that looks like a broken test rather than a missing
configuration line.

*Alternatives considered:*

| Option | Verdict |
|---|---|
| `pythonpath = ["."]` in `[tool.pytest.ini_options]` | **Chosen.** Declarative, one line, native since pytest 7 |
| A root `conftest.py` inserting into `sys.path` | Executable configuration; the exact `sys.path` hack the `RUF`/`B` rule sets discourage |
| `importmode = "importlib"` with namespace packages | Solves a different problem (duplicate basenames) and has subtler failure modes |

Explicitly forbidden by the spec: any `sys.path` manipulation inside a test file
or `conftest.py`.

### D3: `pytest-django` is installed now, configured later

**Why:** The board card as written was circular. `pytest-django` needs
`DJANGO_SETTINGS_MODULE`; that module is created by HS-003; HS-003 transitively
depends on HS-001.

```
   HS-001 ──needs settings──▶ HS-003 ──▶ HS-002 ──▶ HS-001     ✗ cycle
```

Installing the dependency is harmless — unconfigured, `pytest-django` collects
normally and does nothing. Configuring it is what requires Django. Splitting
install from configuration cuts the cycle without merging two cards.

*Alternatives considered:* install plain `pytest` only and add `pytest-django` at
HS-003 (equally correct, but churns `pyproject.toml` twice); pull Django into
this change (dissolves the card boundary and makes this change unverifiable
without a database).

A comment in the pytest configuration records *why* `DJANGO_SETTINGS_MODULE` is
absent, so its absence reads as a decision rather than an oversight.

### D4: Ruff rule set `E4, E7, E9, F, I, UP, B, DJ, RUF` at width 100

**Why:** Ruff's default selection is `E4, E7, E9, F` — pyflakes plus a few
pycodestyle errors. It catches unused imports and undefined names, and misses
unsorted imports, mutable default arguments, and Django modelling mistakes.

`DJ` (flake8-django) is the load-bearing addition. HS-004 must model a `Paper`
whose fields are almost all optional, because INSPIRE's `dois` and
`publication_info` are frequently absent entirely (`AGENTS.md` §4.2). `DJ001`
flags `null=True` on string-based fields — precisely the mistake that data shape
invites.

Enabling rules now is nearly free. Retrofitting them across 15 cards of existing
code is a day of noise.

Width 100 over the default 88: Django ORM chains and DRF class definitions wrap
badly at 88, and wrapped code is harder to scan than slightly long code.

*Alternative considered:* `select = ["ALL"]` with an ignore list. Rejected —
it makes every ruff upgrade a potential build break, and the ignore list becomes
larger than the select list.

### D5: Both `ruff check` and `ruff format --check` are gates

**Why:** Linting and formatting are different tools with different failure modes.
If formatting is advisory, it drifts, and every subsequent diff carries
reformatting noise that hides the real change. The code-reviewer agent already
instructs reviewers to run `ruff format --check`; the board's definition of done
did not. This aligns them.

The check variant is specified deliberately: a gate must not mutate the working
tree.

### D6: Dev dependencies via PEP 735 `[dependency-groups]`

**Why:** Native to `uv`, installed by `uv sync` without flags, and keeps
`[project.dependencies]` empty and honest — this change adds no runtime
dependency. When Django lands in HS-003 it goes into the runtime list, and the
split stays meaningful.

*Alternative considered:* `[project.optional-dependencies]`. It is the older
mechanism and semantically means "extras a consumer may install" — but nobody
consumes this project, so the semantics do not fit.

### D7: A surviving smoke test, not a placeholder

**Why:** `pytest` exits with status **5** when it collects nothing, so "the test
harness works" cannot be demonstrated by an empty suite. The card's original
`assert True` would be deleted at HS-004, meaning the work is thrown away.

`tests/test_environment.py` instead asserts the two things this change actually
guarantees: the interpreter is ≥ 3.13, and the repository root is importable.
Those assertions stay true and stay useful for the life of the project — and if
D1 or D2 is ever broken by a future edit, this test is what catches it.

### D8: `tests/` at the root, plus `apps/<app>/tests/` later

**Why:** `apps/` does not exist yet, so the smoke test needs a home that is not
a temporary one. Project-level concerns (environment, configuration) are not
app-level concerns and should not be filed under an arbitrary app.
`testpaths = ["tests", "apps"]` covers both without either excluding the other.

### D9: `.gitattributes` normalizing to LF

**Why:** The HS-000 commit emitted 28 "LF will be replaced by CRLF" warnings.
Without a declared policy, line endings depend on each machine's `core.autocrlf`,
which eventually produces a whole-file diff that reviews as a rewrite.

### D10: Board amendments ship with this change

**Why:** Three board defects were found while exploring the card, and a fix that
leaves the board wrong would let the same defects be re-implemented later:

1. HS-001's `.env.example` criterion is unverifiable — at that point the project
   reads zero environment variables. Ownership moves to HS-002, which is the
   first card to introduce one.
2. HS-001's `.gitignore` criterion is already satisfied by the HS-000 commit. It
   becomes a verification step, so nobody re-creates the file.
3. `ruff format --check` (D5) must appear in every card's definition of done and
   in `board/TEMPLATE.md`, or HS-001 becomes the only card that enforces it.

Documentation and the code it describes change together, in one commit.

### D11: `[tool.ruff] include` scoped to project source only (discovered during implementation)

**Why:** Not anticipated in the original design. Running `uv run ruff format .`
on the whole repository reformatted fenced Python code blocks embedded inside
vendored Markdown files under `.agents/skills/` — `ruff format` rewrites code
fences inside `.md` files by default, not just `.py` files. That is undesirable:
those files are vendored third-party assets, not this project's source, and
should not be touched by this project's formatter.

**Fix:** Added an explicit `include` allowlist to `[tool.ruff]` —
`["*.py", "*.pyi", "tests/**/*.py", "apps/**/*.py", "config/**/*.py"]` — so ruff
only ever looks at this project's own Python source. A side effect: with an
`include` list, ruff prints `warning: No Python files found under the given
path(s)` until `apps/` and `config/` actually contain `.py` files, which is
expected and benign at this stage.

**Alternative rejected:** An `exclude` list naming every vendored doc directory
would be longer, more fragile (breaks silently if a new vendored directory is
added later), and still wouldn't stop ruff from touching a future Markdown file
containing a Python fence anywhere else in the repo.

## Risks / Trade-offs

**Enabling `DJ` rules before any Django code exists** → `DJ` rules are inert
until models appear, so there is no cost now and no retrofit later. If a rule
proves wrong for this codebase at HS-004, it is a one-line `ignore` with a
comment explaining why.

**Width 100 diverges from the ecosystem default of 88** → Contained: the width is
declared in `pyproject.toml` and enforced by `ruff format`, so no contributor
needs to know or remember it.

**`pytest-django` installed but unconfigured could confuse a future reader** →
Mitigated by D3's required comment, and asserted by a spec scenario that
collection must succeed with no `DJANGO_SETTINGS_MODULE` anywhere.

**`pythonpath = ["."]` makes anything at the repository root importable** →
Accepted. It is the standard Django-project posture; `manage.py` will do the same
thing at HS-003. The alternative is packaging ceremony with no consumer.

**The committed `uv.lock` will churn as later cards add dependencies** → Intended.
That churn is the audit trail of what each card introduced.

**Torch enters the lockfile at HS-009 and `uv sync` slows down** → Accepted
knowingly. A dry run confirmed `sentence-transformers 6.0.1` and `torch 2.14.0`
resolve on Python 3.13/Windows; on Windows the PyPI wheel is the CPU build, so
the size is tolerable. This would need revisiting if the project ever runs on
Linux, where the PyPI wheel bundles CUDA.

**Renaming the repository folder to `hepsearch`** → Out of scope for this change.
It moves the working directory and any IDE project reference, so it should be a
deliberate standalone step rather than being folded into this commit.

## Open Questions

- Does `mypy` earn its place once `apps/papers` and the ranking code exist? Defer
  the decision to after HS-012, when there is real code to judge.
- Should `pytest` run with `--strict-markers` from the start? Cheap to add, and it
  would prevent the `slow` marker planned for HS-009 from being silently
  misspelled. Leaning yes; not blocking.
