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

## Environment

Windows host. Use PowerShell syntax and backslash paths. PowerShell's `&&` does
not chain before PowerShell keywords — use `;`.
