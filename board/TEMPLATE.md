# HS-NNN: <Title in imperative mood>

**Status:** backlog | in-progress | done
**Depends on:** HS-NNN, HS-NNN (or: nothing)

## Story

As a <role>, I want <capability>, so that <benefit>.

## Context

Why this card exists now, and anything a future reader needs that is not obvious
from the codebase. Link to the relevant AGENTS.md section rather than repeating it.

## Acceptance criteria

- [ ] Written so someone who has never seen the code can verify it
- [ ] Each one independently checkable
- [ ] Includes the failure/edge case, not just the happy path

## Definition of done

- [ ] Acceptance criteria met
- [ ] Tests written and passing (`uv run pytest`)
- [ ] `uv run ruff check .` clean
- [ ] `uv run ruff format --check .` clean
- [ ] AGENTS.md updated if a decision changed
- [ ] Committed as `HS-NNN: <title>` with the card moved to `board/done/`

## Out of scope

What this card deliberately does not do, and which card does it instead.
