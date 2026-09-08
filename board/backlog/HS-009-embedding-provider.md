# HS-009: Add a pluggable embedding provider

**Status:** backlog
**Depends on:** HS-008

## Story

As a developer, I want a single, swappable interface for turning text into
vectors, so that no other part of the codebase depends on a specific embedding
model or vendor.

## Context

AGENTS.md §3: **nothing outside the provider imports `sentence_transformers`.**
Swapping to a hosted embedding API must touch exactly one file.

Default model `all-MiniLM-L6-v2`, **384 dimensions**. The dimension is the
contract between this card and HS-010 — if they drift apart, similarity search
silently breaks or the migration fails.

This card produces vectors in memory only. Storing them is HS-010.

## Acceptance criteria

- [ ] An interface (protocol/ABC) declares `embed(texts: list[str]) -> list[list[float]]`
      and exposes its `dimension`
- [ ] A local implementation wraps `sentence-transformers` with `all-MiniLM-L6-v2`
- [ ] The provider is selected through settings, not imported directly by callers
- [ ] The model is loaded lazily and only once per process, never per call
- [ ] The model name and dimension are settings, documented in `.env.example`
- [ ] `embed` accepts a batch and returns vectors in the same order as the input
- [ ] Embedding an empty list returns an empty list without loading the model
- [ ] A fake/deterministic provider exists for tests
- [ ] Unit tests use the fake and **never download a model**
- [ ] Exactly one test, marked `slow` and excluded from the default run, verifies
      the real provider returns 384-dimensional vectors and that semantically
      similar sentences score higher than unrelated ones
- [ ] The default `uv run pytest` run stays fast and offline
- [ ] The model cache directory is git-ignored

## Definition of done

- [ ] Acceptance criteria met
- [ ] `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .` pass
- [ ] Committed as `HS-009: Add a pluggable embedding provider`

## Out of scope

Storing vectors or the `VectorField` (HS-010), searching with them (HS-011),
chunking (never — abstracts fit in the model's window, AGENTS.md §6).
