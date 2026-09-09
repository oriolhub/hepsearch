# Copilot instructions

**Read [`AGENTS.md`](../AGENTS.md) first.** It is the single source of truth for
this repository: project purpose, stack decisions and their rationale, the app
dependency rule, the verified INSPIRE API contract, every command, and the
conventions. This file only covers what is specific to working through Copilot.

## Working agreement

- **One board card at a time.** `board/backlog/` holds numbered `HS-NNN` cards
  with acceptance criteria. Move the card to `board/in-progress/` with `git mv`
  when you start, to `board/done/` in the same commit that finishes the work.
  Never batch several cards into one commit.
- **Commits:** `HS-NNN: Capitalized imperative title`, ≤72 chars, no trailing
  period, with a body explaining *why*. Tests ship with the code they cover.
- **Do not scaffold ahead.** The repository intentionally contains only docs and
  the board right now. Build each card's slice, verify it, commit it, stop.
- **Ask before adding a dependency, a service, or an abstraction.** If no
  acceptance criterion fails without it, it does not go in. Celery, Redis, a
  separate vector database, and a JS frontend were all considered and rejected —
  see AGENTS.md §2.

## Traps specific to this codebase

- INSPIRE records are far more optional than they look: `dois` and
  `publication_info` are frequently **absent entirely** and ~10% of records have
  **no abstract**. Never index into a possibly-missing list. AGENTS.md §4.2.
- `apps/search` and `apps/ingestion` must never import each other. AGENTS.md §3.
- The embedding dimension (384) is a contract between the provider and the
  `VectorField`. Changing the model is a migration.
- Keyword search is not throwaway — it is half of the final hybrid ranker.
- No test may touch the network or download a model in the default `pytest` run.
- This repo's `commit-msg` hook rejects `Co-authored-by:` trailers (see
  `.github/git-commit-instructions.md`). Never use `git commit --no-verify` to
  force one in — omit the trailer instead. Bypassing the hook skips every other
  check it runs, not just this one.
- Before checking off a task that claims test coverage (an OpenSpec task or a
  board card's AC), confirm each named scenario has a literal corresponding
  test — a passing suite does not mean every claimed scenario is exercised.
  A prior review found a design-required error path that was unreachable dead
  code, shipped with the task marked done.
- Archiving an OpenSpec change is one atomic commit: move the change directory
  into `archive/`, write the synced spec, stage the deletion of the original
  change source — all together. Splitting the deletion into a follow-up commit
  violates the no-commit-fixes-another-commit rule below.
- Docker here is Rancher Desktop, not Docker Desktop. If `docker compose up`
  fails with a daemon/API connection error, the Rancher Desktop VM likely isn't
  running yet — launch it and poll `docker info` until it succeeds (can take
  ~20s+) before retrying compose.

## Environment

Windows host. Use PowerShell syntax and backslash paths. PowerShell's `&&` does
not chain before PowerShell keywords — use `;`.
