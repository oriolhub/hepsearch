# hepsearch

hepsearch is a Django and Django REST Framework application for semantic search
over high-energy-physics literature from [INSPIRE-HEP](https://inspirehep.net/).
It ingests a bounded local corpus of papers, embeds their titles and abstracts,
and ranks papers for natural-language questions instead of requiring the query
to use the paper's exact words.

## Prerequisites

- Python 3.13
- [`uv`](https://docs.astral.sh/uv/)
- Docker with Compose. The reference development machine uses Rancher Desktop.

## Quickstart

From a fresh clone:

```powershell
docker compose up -d --wait
uv sync --extra local-embeddings
Set-Content .env 'SECRET_KEY=local-development-only-change-me'
uv run python manage.py migrate
uv run python manage.py ingest_inspire --query "higgs boson" --limit 5000
uv run python manage.py embed_papers
uv run python manage.py runserver
```

Open <http://127.0.0.1:8000/> and search for a physics question. The ingestion
and embedding commands are batch operations; they populate the local PostgreSQL
database and do not run in the request path.

The reference corpus contains 5,000 papers and occupies 63 MB in PostgreSQL.
Ingestion takes under a minute with the default throttle; embedding downloads
the `all-MiniLM-L6-v2` model (approximately 87 MB in the local Hugging Face
cache). The complete CPU-only Windows virtual environment measured 892 MB.

The first semantic or hybrid search loads the model and took approximately 63
seconds on the reference machine. Warm searches took approximately 0.09 seconds.
The page reports the wall-clock time the request actually took.

## API

The API is read-only and public. Check the application and database with:

```text
GET /api/health/
```

```json
{"database": "ok"}
```

Search with `q` and optionally choose `mode=keyword`, `mode=semantic`, or
`mode=hybrid`:

```text
GET /api/search/?q=higgs%20self-coupling&mode=hybrid
```

The response below is a real response from the local corpus, trimmed to one
result; the pagination link marks the remaining results:

```json
{
  "count": 60,
  "next": "http://127.0.0.1:8000/api/search/?mode=keyword&page=2&page_size=1&q=higgs+self-coupling",
  "previous": null,
  "results": [
    {
      "id": 4079,
      "title": "Optimization of electron identification and measurement of the Higgs boson self-coupling via off-shell decays to four leptons using the CMS detector",
      "authors": ["Petkovic, Andro"],
      "author_count": 1,
      "publication_date": "2026-01-01",
      "abstract_snippet": "Le travail présenté dans cette thèse de doctorat peut être divisé en deux parties principales. ...",
      "inspire_url": "https://inspirehep.net/literature/3202229",
      "score": 1.0,
      "methods": []
    }
  ],
  "mode": "keyword"
}
```

The API reports the number of retrieved candidates, not a count of every
matching paper in the corpus. Semantic retrieval is bounded by the vector
index's single scan, so it can legitimately retrieve fewer papers than keyword
retrieval.

## Why hybrid search?

Keyword and semantic search fail differently:

- Keyword search is strong for exact identifiers such as `ATLAS`,
  `arXiv:2609.04868`, and author names, but it loses on paraphrases.
- Semantic search understands paraphrases, but it can miss exact identifiers
  and other rare tokens.
- Hybrid search fuses both rankings with Reciprocal Rank Fusion because neither
  method is sufficient alone.

For example, the measured query:

```text
why is the Higgs mass so much lighter than the Planck scale
```

returned nothing from keyword ranking. Semantic ranking returned papers
including *An examination of the hierarchy problem beyond the Standard Model*
and *Origin of mass scales in scale-symmetric extension of SM*. The query
describes the hierarchy problem without using the same words as every relevant
title or abstract.

## Data source and reuse

hepsearch credits and retrieves metadata from
[INSPIRE-HEP](https://inspirehep.net/). See the
[INSPIRE terms of use](https://help.inspirehep.net/knowledge-base/terms-of-use/)
for the authoritative conditions. The relevant terms state:

> All of the metadata from the INSPIRE HEP collection may be reused in
> accordance with the CC0 waiver and the following caveats: i) The download of
> email addresses is not permitted. ii) These conditions of re-use of specific
> INSPIRE schema fields are followed: abstracts — If `abstracts.source` is
> "arXiv" or "CERN"; keywords — If `keywords.source` is "author" or absent; if
> `keywords.schema` is "INSPIRE".

Users must also respect copyright and applicable license conditions. The
ingestion code currently records the abstract selected by INSPIRE's response;
the source-audit follow-up is tracked in
[`board/backlog/HS-018-record-abstract-source.md`](board/backlog/HS-018-record-abstract-source.md).

## Out of scope

- LLM answer generation
- Full-text PDF ingestion
- User accounts and personalization
- Mirroring all of INSPIRE

For project decisions, architecture rules, and contributor workflow, see
[`AGENTS.md`](AGENTS.md).
