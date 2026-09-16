## Context

`apps/search/ranking.py` already exposes two independent rankers, both returning lazy
`QuerySet[Paper]` orderings: `search(query, limit)` scores against the stored
`search_vector`, and `semantic_search(queryset, vector, limit, *, model_name)` orders by
`CosineDistance`. HS-011 deliberately left `semantic_search` composable and free of HTTP
concerns so a hybrid ranker could reuse it rather than reimplement it. That has held —
this change adds a fusion function and an orchestration path, and modifies neither
ranker.

The HTTP layer in `apps/search/views.py` already owns the decisions this change
complicates: `_rank` dispatches on mode, `_ranked_papers` converts a missing optional
dependency into an operator-fixable outage rather than a traceback, and
`_empty_semantic_reason` distinguishes an empty corpus from an unembedded one.

Everything below rests on measurements taken against the ingested corpus (5,000 papers,
all embedded with `all-MiniLM-L6-v2`) before implementation. Those numbers are the
reason several of this design's constants differ from the ones the board card assumed.

## Goals / Non-Goals

**Goals:**

- One ranking that serves both exact-token and paraphrase queries, as the default.
- Fusion maths that is a pure function, testable with plain lists of integers.
- No regression for an installation that cannot embed: hybrid must stay useful when
  semantic ranking is unavailable.
- Constants whose values are justified by evidence recorded against this corpus, not by
  citation.
- Exactly two database queries per hybrid request.

**Non-Goals:**

- Per-method weights. Two weights both set to 1.0 are not weights.
- Tuning `hnsw.ef_search`, per-request or globally. This is a ranking change.
- Making identifiers or author names retrievable. Separate concern, see Decision 5.
- Cross-encoder re-ranking, learned weights, labelled relevance judgements, evaluation
  harnesses.

## Decisions

### 1. Reciprocal Rank Fusion over ranked id lists

RRF combines *ranks*, so it needs no normalization between `SearchRank` (roughly 0–1,
tf-idf-ish) and cosine similarity (roughly 0–1, but differently distributed and dense —
every paper has some similarity to every query). Normalizing two incomparable score
scales requires knowing their distributions; comparing positions does not.

`reciprocal_rank_fusion(keyword_ids, semantic_ids) -> list[FusedResult]` takes two lists
of primary keys and returns fused entries carrying the score and the contributing
methods. It touches no model, no queryset and no settings other than the constants.

*Alternative considered:* normalized score fusion (e.g. min-max or z-score per arm).
Rejected — it makes the result sensitive to the score distribution of whichever arm
happens to have a long tail, and cosine similarity's tail is dense by construction.

### 2. `RRF_K = 5`, not the canonical 60

Measured on this corpus, at candidate depth 40, against three queries — an exact token
(`monojet`), a paraphrase (*"measuring the strength of the Higgs coupling to itself"*),
and a mixed query (`ATLAS dark matter monojet search`):

```
  k       exact-token         paraphrase          mixed
          kw#1  sem#1         kw#1  sem#1         kw#1  sem#1
  ---------------------------------------------------------------
   0        2     1             1     2             1     2
   5        3     2             1     2             1     2
  10        3     2             3     4             1     2
  20        3     2             4     5             1     2
  60        3     2             4     5             1     2
```

(the fused position of each arm's own first pick)

At k=60 the paraphrase query ranked three papers that both arms placed mid-list —
*"Higgs boson couplings at muon collider"*, *"The beauty and charm of Higgs"*,
*"Higgs couplings combination at CMS"*, none of them about self-coupling — above both
arms' on-target first picks. The arithmetic is not subtle:

```
  single hit at rank 1      1/(60+1)             = 0.01639
  dual hit at ranks 15, 20  1/(60+15) + 1/(60+20) = 0.02583   ← wins
```

The reason is structural, not a quirk of these three queries. Cormack et al. derived
k=60 for fusing many *redundant* retrieval systems over deep result lists, where two
systems agreeing is strong evidence. This system fuses **two** arms chosen precisely
because they are **complementary**, over **40** candidates. Here agreement is a weak
signal and top rank is a strong one, so the rank curve must stay steep. Large k flattens
rank differences until only agreement matters.

At k=5, all three queries place both arms' first picks at fused positions 1–2, while
dual hits still lead the exact-token and mixed queries.

*Alternative considered:* k=0, pure `1/rank`. Rejected as brittle — rank 1 scores 1.0
and rank 2 scores 0.5, so a single arm's top pick becomes nearly unbeatable and
agreement stops mattering at all, which defeats the point of fusing.

**Honest limit, and it belongs in the comment beside the constant:** three queries, one
person's relevance judgement, no labelled ground truth. The claim this change is
entitled to make is *"60 was measured to demote both arms' top picks on this corpus; 5
keeps them at fused rank 1–2 across three queries"* — not that 5 is optimal.

### 3. `HYBRID_CANDIDATE_DEPTH = 40`, bounded by the vector index

A pgvector HNSW index scan returns at most `hnsw.ef_search` rows. This deployment never
sets it, so it is the default, 40. Measured:

```
  semantic LIMIT  40  ->  40 rows
  semantic LIMIT 100  ->  40 rows      ← silently truncated
  semantic LIMIT 200  ->  40 rows      ← silently truncated
  SET hnsw.ef_search = 200; LIMIT 100 -> 100 rows
```

Invisible until now only because `SEARCH_RESULT_LIMIT` is 20, comfortably under 40.

Setting the depth to 40 makes the constant tell the truth, keeps a 2× over-fetch for a
20-result page, and costs nothing. The constant carries a comment naming the coupling,
because the obvious future edit — raising it alone — does nothing.

*Alternative considered:* `SET LOCAL hnsw.ef_search` per request to unlock a deeper
pool. Rejected: it adds a statement and a transaction requirement to every hybrid
request, couples the ranking layer to index internals, and widens a pool nobody has
shown is too narrow. Revisit when there is evidence 40 is insufficient.

### 4. Degrade to keyword, do not refuse — and hydrate from what is already loaded

Hybrid becomes the default, so the availability decision changes meaning. Today a
default `uv sync` (no `local-embeddings` extra) reaches `mode=semantic` and correctly
gets a 503. After this change the *same* installation would get a 503 for a bare
`/api/search/?q=higgs` — a plain regression introduced by improving the ranker.

So hybrid runs keyword-only, returns 200, and reports the degradation in the response
and on the page. `mode=semantic` keeps its 503: a caller who explicitly asked for
semantic ranking is owed the failure. The existing `_ranked_papers` and
`_empty_semantic_reason` already produce exactly the two signals this needs.

One consequence of HS-011's design makes the fault signal unambiguous and is worth
writing down, because it contradicts an intuition that cost this design a revision:
**cosine ranking cannot honestly return an empty list on a populated corpus.** It ranks
every eligible row; it does not match a set. So a semantic arm returning zero rows
against a non-empty corpus *is* the fault signal, never a genuine miss.

Fusion then operates on ids, per the requirement that it stay pure, but hydration reuses
the `Paper` instances the two arms already evaluated, keyed by primary key. A third
`filter(pk__in=...)` query would cost a round trip and require rebuilding the order that
was just computed. Two queries per request, no N+1.

### 5. The identifier gap is out of scope, and a separate change

`search_vector` is `title` (weight A) + `abstract` (weight B). It contains no
`arxiv_id`, no `doi`, no author names. Measured:

```
  keyword 'arXiv:2207.00043'                -> 0 hits
  keyword '2207.00043'                      -> 0 hits
  keyword 'portrait of the Higgs boson CMS' -> 1 hit
```

AGENTS.md §3 motivates hybrid partly with *"pure vector search fails on exact tokens —
`ATLAS`, `arXiv:2609.04868`, an author's surname"*. For this corpus only the first is
true: `ATLAS` appears in abstract text, identifiers and surnames do not appear anywhere
in the index. RRF can promote a paper both arms retrieved; it cannot conjure one neither
arm returned. This is a retrieval-coverage gap, not a ranking gap, and fixing it means
changing the generated `search_vector` column — a migration, and a different change.

Consequence for this change: the card's exact-identifier comparison query is replaced by
an exact-token query, with the rationale recorded in the commit body. Running the
identifier query as written would satisfy the criterion vacuously — hybrid is "not worse
than either mode" only because all three are useless — and would teach nobody anything.

### 6. Response shape: `methods` and a fused `score`, nothing more

Each result reports `methods` (`["keyword"]`, `["semantic"]`, or both) and its fused
score. Per-arm ranks stay internal: they are diagnostics, and the one place they are
genuinely needed — the real-corpus comparison — is served by querying each mode directly.

The `keyword-search` spec already establishes that `score` carries the scale of whatever
mode produced it and is not comparable across modes. The RRF scale (~0.2 at k=5) is
another instance of that existing rule, not a new exception.

### 7. The fusion function lives in `ranking.py`

Fewest files. The requirement is that the function be *pure* — no database, no model,
no request — not that its module be import-free. `ranking.py` is where ranking lives,
and a test can call it with two lists of integers without `django_db`.

## Risks / Trade-offs

- **`RRF_K = 5` is justified by three queries and one person's judgement** → The comment
  beside the constant states exactly that and claims no more. The value is a named
  constant precisely so the next person with better evidence can move it. What this
  change does establish firmly is negative and well-supported: 60 is wrong here.

- **A future `hnsw.ef_search` change silently alters ranking** → Raising it widens the
  semantic arm's pool, which changes fused output for every query. The coupling is named
  in a comment at `HYBRID_CANDIDATE_DEPTH`. Accepted rather than defended against; the
  alternative is pinning the GUC per request, rejected in Decision 3.

- **The default mode flip is a breaking change to a public read-only API** → Accepted:
  it is the point of the card, the API is unversioned and pre-release, and keyword
  ranking remains available by naming it. Existing tests asserting the old default are
  updated in the same commit.

- **Degrading silently would be dishonest** → The response carries an explicit
  degradation signal and the page renders a notice, so a keyword-only result set is
  never presented as a hybrid one.

- **Hybrid's benefit over semantic alone is unproven for paraphrase queries** → On the
  paraphrase query, semantic alone was already excellent and fusion's contribution was
  to not ruin it. The demonstrable wins are the exact-token and mixed queries, where the
  dual hit leads. The real-corpus comparison records all three honestly rather than
  claiming a uniform improvement.

- **Two arms run on every default request, where one ran before** → The default request
  now embeds the query (loading the model on first use) and runs two queries instead of
  one. Accepted: it is inherent to hybrid ranking, and the degradation path means an
  installation that cannot embed pays nothing.
