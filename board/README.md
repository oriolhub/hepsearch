# Board

A local, file-based task board. Each card is a markdown file.

```
board/backlog/       Not started
board/in-progress/   Active work — keep this to ONE card at a time
board/done/          Finished and committed
```

## Rules

- Cards are named `HS-NNN-short-slug.md` and never renumbered.
- Moving a card is `git mv`, done **in the same commit as the work itself**, so
  the git history and the board never disagree.
- Only one card in `in-progress/` at a time. Baby steps.
- A card is done when every acceptance criterion is verifiably true and the app
  still runs.
- Cards are written as user stories with acceptance criteria so they can be
  lifted into a real tracker later without a rewrite.

## Order

Cards are ordered by dependency, not priority. `HS-007` is the first card that
delivers something a user can actually use; everything before it is scaffolding
that earns its place by making `HS-007` possible.

| Card | Delivers |
|---|---|
| HS-001 | Python tooling and a runnable test suite |
| HS-002 | PostgreSQL with pgvector, running locally |
| HS-003 | A Django project that boots and answers a health check |
| HS-004 | The `Paper` domain model |
| HS-005 | A tested INSPIRE API client |
| HS-006 | A real 5,000-paper corpus in the database |
| HS-007 | **First user value**: keyword search over the corpus via the API |
| HS-008 | A web page a human can actually type into |
| HS-009 | A pluggable embedding provider |
| HS-010 | Vectors stored in Postgres for every paper |
| HS-011 | **The point of the project**: semantic search |
| HS-012 | Hybrid ranking that beats either method alone |
| HS-013 | Throttling, pagination, and honest error handling |
| HS-014 | A search page worth demoing |
| HS-015 | Documentation that lets a stranger run it |
