# HS-017: Index identifiers and authors for exact lookup

**Status:** backlog
**Depends on:** HS-012

## Story

As a physicist, I want to search by an arXiv identifier, DOI, or author name, so
that exact literature lookups do not depend on those values appearing in a title
or abstract.

## Context

The current generated `search_vector` contains only title and abstract. On the
5,000-paper corpus, `arXiv:2207.00043` and `2207.00043` both return zero keyword
hits, while a title phrase from the same paper does return a hit. Hybrid ranking
cannot recover a paper that neither underlying arm retrieves.

## Acceptance criteria

- [ ] The generated search vector includes `arxiv_id`, `doi`, and author names.
- [ ] Existing title and abstract weighting remains unchanged.
- [ ] Exact arXiv identifiers return the matching paper through keyword mode.
- [ ] Exact DOI values return the matching paper through keyword mode.
- [ ] Author-name queries return papers containing that author.
- [ ] Existing keyword, semantic, and hybrid ranking behavior remains covered by tests.
- [ ] A migration updates the generated search-vector expression safely.

## Definition of done

- [ ] Acceptance criteria met
- [ ] `uv run pytest`, `uv run ruff check .`, and `uv run ruff format --check .` pass
- [ ] Committed as `HS-017: Index identifiers and authors`

## Out of scope

Changing the embedding text, semantic retrieval, fusion constants, or adding a
separate search service.
