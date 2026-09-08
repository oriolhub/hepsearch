## Context

`apps/ingestion` is the only place in this system permitted to know that INSPIRE's
JSON field names exist (`AGENTS.md §3`). Everything downstream — HS-006's writes,
HS-009's embeddings, HS-007's ranking — consumes whatever shape this client produces,
so the rules encoded here are long-lived.

The card's requirements were checked against the live API rather than against prose.

### The spike

11 read-only calls to `https://inspirehep.net/api/literature`, throttled, with a
descriptive `User-Agent`. `q=higgs boson` reports **29,128 hits**. Two slices were
sampled because they behave very differently: `mostcited` (large collaborations,
published) and `mostrecent` (preprints).

| Observation | Measured | Drives |
|---|---|---|
| **Dotted sub-field selection works** | `fields=...,authors.full_name,...` returns author objects containing only `full_name` | **D3** |
| Payload with `authors` | 3,451,087 bytes for 5 most-cited records | **D3** |
| Payload with `authors.full_name` | 219,784 bytes — **6.4%**; one record carried 2,932 authors | **D3** |
| Bytes per record, sub-selected | 9,225 (size=25) → 15,073 (size=250) on `mostrecent` | **D4** |
| **Result window is exactly 10,000** | `size=1000&page=10` (`from=9000`) → 200; `page=11` (`from=10000`) → **400** | **D6** |
| Records with **more than one abstract** | **166 / 500 (33%)**, max 3 | **D9** |
| Multi-abstract records where *no* entry has a `source` | **0** | **D9** |
| Multi-abstract records where the variants are the **same length** | **16** | **D9** |
| Abstract `source` values | arXiv 254, Elsevier 115, *absent* 115, APS 83, Springer 59, IOP 15, and a long tail (`Elsevier B.V.`, `Oxford Journals`, `submitter`, `WSP`, …) | **D9** |
| Records with no abstract | 11 / 500 (2.2%) on `mostcited` | **D8** |
| `dois` absent / multiple | 31 absent, **62 with >1** (max 3) | **D10** |
| `publication_info` absent / multiple | 27 absent, **65 with >1** (max 3); 7 have entries but **no `journal_title` anywhere** | **D10** |
| **`arxiv_eprints` absent** | **146 / 500 (29%)** | **D10** |
| `arxiv_eprints[0]` present but missing `categories` | **0** | **D10** |
| arXiv id shapes | `1207.7214` and `hep-ph/0603175`; **125 / 354 (35%) old-style** | **D11** |
| Ordering stability | Two identical requests returned records *and* abstracts in identical order | **D9** |

Three of these contradict or extend the documented contract: dotted sub-fields and
the 10,000 window are absent from `AGENTS.md §4.1`, and §4.2's "Usually" for
`arxiv_eprints` understates a 29% absence rate. The slice dependence is itself worth
recording — `dois` was absent on 44/50 `mostrecent` records in the HS-004 spike versus
31/500 here.

## Goals / Non-Goals

**Goals:**
- Fetch a bounded slice of INSPIRE literature without hammering the API and without
  downloading gigabytes we discard.
- Translate deeply-optional external JSON into `Paper` instances, or decline to,
  with every "which value wins" rule stated once and covered by a test.
- Be fully testable offline: no test opens a socket.

**Non-Goals:**
- Writing to the database, batching, progress output, `--dry-run`, or idempotence —
  all HS-006. This module holds no `Paper.objects` call.
- Incremental "only new since" sync, scheduling, or a resumable cursor.
- Embeddings (HS-009), search (HS-007), HEPData (`AGENTS.md §4.3`).
- Exhaustive INSPIRE coverage. We map the fields `Paper` has and ignore the other 33.

## Decisions

### D1 — `httpx`, with the retry written by hand

`httpx` is added as a runtime dependency and used through a single `httpx.Client`
that owns the `User-Agent`, the timeout and the connection pool.

What it buys: a timeout that is mandatory rather than forgotten, one object holding
per-request defaults, connection reuse across ~23 sequential requests, and a single
exception hierarchy instead of `urllib`'s `HTTPError`/`URLError` split.

What it explicitly does **not** buy: the retry this card requires.
`httpx.HTTPTransport(retries=N)` retries *connection* establishment only — a 500 or a
429 is a successfully completed HTTP transaction and is never retried by it. The
backoff loop in **D7** is hand-written and would be equally hand-written on any of the
alternatives.

*Alternatives considered:*
- **stdlib `urllib.request`** — genuinely sufficient; the entire spike was written on
  it. Zero new dependencies, which `AGENTS.md §8` prefers. Rejected on ergonomics:
  manual query encoding, manual JSON decode, and a two-exception error model that is
  easy to get subtly wrong under retry.
- **`requests`** — retry via `HTTPAdapter(max_retries=Retry(...))` is battle-tested,
  but configuring `urllib3.Retry` correctly (which statuses, which methods,
  `respect_retry_after_header`, `raise_on_status`) is arguably more arcane than the
  loop it replaces, and it is the heavier install.

`AGENTS.md §2` maintains an explicit ledger of rejected dependencies; per that file's
own opening rule, the stack table gains an httpx row in the same commit as this code.
The transitive set (httpcore, h11, anyio, certifi, idna, sniffio) is recorded there too.

### D2 — Three seams, because they have three different test strategies

```
   fetch_page()   ────▶   iter_records()   ────▶   normalize()
   ────────────           ──────────────           ───────────
   HTTP, retry,           pagination, limit,       JSON → Paper | None
   throttle               stop conditions          every "which wins" rule
   network                no I/O of its own        PURE
   replaced in tests      driven by a fake         fixture-driven
```

`normalize()` is a pure function and holds every rule that a bug would hide in.
`iter_records()` takes the fetcher as a parameter, so tests drive it with a list of
canned pages and assert stop conditions without mocking a network library. Nothing in
the module references `httpx` outside `fetch_page`.

*Alternative considered:* one class with a `fetch()` method doing all three. Rejected —
it forces every normalization test to construct a client and patch HTTP, and it is how
"no test performs a network request" quietly becomes false.

### D3 — Request `authors.full_name`, not `authors`

The single highest-leverage line in this card. Measured at **6.4%** of the payload
(3,451,087 → 219,784 bytes over 5 records), because an INSPIRE author object carries
`ids`, `affiliations`, `raw_affiliations`, `signature_block`, `uuid`, `record` and
`curated_relation`, and we want one string from each of up to several thousand.

At ~15 KB/record the full ~5,600-record download is ≈ 84 MB. Without sub-selection the
collaboration-heavy end alone runs to gigabytes.

The `fields=` list is exactly what `Paper` needs and nothing else: `control_number`,
`titles`, `abstracts`, `authors.full_name`, `arxiv_eprints`, `dois`,
`publication_info`, `earliest_date`, `citation_count`.

### D4 — Page size defaults to 250; 1000 is the clamp, not the target

The card requires clamping at 1000 so an over-large request cannot produce a 400.
It does not require *using* 1000, and using it is a poor default: a 1000-record page
is a ~15 MB JSON parse on the light slice and roughly twenty times that on
collaboration-heavy pages, all of it held in memory at once.

250 costs ~23 requests for the corpus instead of 6, at ~3.8 MB per page, and shrinks
the amount of work thrown away when a page fails and is retried.

### D5 — `limit` counts records **yielded**, not records fetched

The client keeps paging until it has produced `limit` usable `Paper` instances.

The two cards contradict each other today: HS-006's example is `--limit 5000`, it
claims the database ends with ~5,000 papers, and it says landing 5,000 requires
fetching ~5,600. Those cannot all hold. Putting the arithmetic in the client makes
`--limit` mean what an operator would assume, and removes a magic constant from the
command. HS-006's card is amended accordingly.

*Alternative considered:* `limit` as a fetch budget, leaving the operator to
over-request. Rejected — it exports an implementation detail (the skip rate, which is
slice-dependent: 2.2% on `mostcited`, ~10% claimed overall) into the operator's head.

### D6 — Three stop conditions; the window logs a warning

```
   iter_records(query, limit)
        │
        ├── limit usable records yielded ............ normal
        ├── hits.total exhausted .................... corpus smaller than asked
        └── next page would need from ≥ 10,000 ...... log a WARNING and stop
```

The window is a hard API limit (`page=11` at `size=1000` returns 400), so it must be
detected *before* the request, not by catching the 400 — a 400 is not retryable and
would otherwise surface as the D7 "clear error" for what is a foreseeable condition.

At 250/page a 5,000-record corpus peaks near `from=5,500`, so this only bites above
roughly 9,000 usable records. It stops rather than raising because a short corpus is
usable; HS-006's summary reports the shortfall.

**The warning goes through `logging`, not `print`.** HS-006's card gives stdout to the
management command; a library writing there would interleave with the progress output.

### D7 — Bounded retry on transient failures only

Retried: connection errors, timeouts, 5xx, and 429. Never retried: any other 4xx —
a 400 from a malformed query will not improve on the third attempt.

Backoff honours `Retry-After` when the response carries it, and otherwise uses
exponential backoff with jitter. Jitter matters less for a single sequential client
than for a fleet, but it is one call and it stops a retry storm from synchronising
with whatever else is hitting the API. After a bounded number of attempts the client
raises an error naming the URL, the final status and the attempts made.

The throttle between *successful* requests is separate from backoff and is
configurable, per the card. `AGENTS.md §4.1` notes the API returns no rate-limit
headers, which is the reason to be conservative rather than a reason to relax.

### D8 — `normalize()` returns an unsaved `Paper`, or `None`

`apps/ingestion` importing `apps.papers.models` is explicitly permitted
(`AGENTS.md §3`). Returning model instances means Django checks the field names,
HS-006 can hand them straight to `bulk_create(update_conflicts=...)`, and there is no
third schema to keep in sync with the model.

Instantiating a model neither touches nor needs a database, so normalization tests
stay in the fast `pytest -m "not django_db"` lane.

**The interlock that makes this safe:** `Paper(abstract="")` constructs happily and
only fails at the database, where HS-004's `CheckConstraint` lives — and in a bulk
insert **one violating row aborts the entire batch**, not just that row. So
`normalize()` returning `None` for an unusable record is not a convenience; it is the
guarantee HS-006 relies on. It gets an explicit test.

*Alternatives considered:* plain `dict`s (zero coupling, but pushes an unchecked
key-to-field mapping into HS-006) and a frozen dataclass (an explicit contract, and a
third definition of the same fields to maintain).

### D9 — Abstract selection: first arXiv-sourced entry, else first non-empty

Rule, documented in a comment at the point of use:

1. the first entry whose `source` case-insensitively equals `arxiv` and whose `value`
   is non-empty;
2. otherwise the first entry with a non-empty `value`;
3. otherwise the record is unusable — return `None`.

**33% of measured records carry more than one abstract**, so this is a common path,
not an edge case. The observed length pairs — `[895, 962]`, `[1371, 1370]`,
`[2041, 1569]` — show the variants are lightly-edited versions of the same prose.

That reframes the requirement: *which* variant wins barely affects embedding quality;
what matters is that a re-ingest picks the **same** one, or `updated_at` churns and
HS-010's embeddings are needlessly invalidated. The goal is stability, not correctness.

*Alternatives considered:*
- **Longest wins** — appealing (most signal for the embedder) but **not deterministic**:
  16 of the 166 multi-abstract records have variants of identical length.
- **First in list, unconditionally** — the spike found ordering stable across two
  identical requests, so this works in practice, but it relies on an undocumented
  property of INSPIRE's response rather than on the data itself.
- Preferring arXiv was previously feared unworkable because 115 abstract entries carry
  no `source` at all. The measurement resolves it: **zero** multi-abstract records have
  *all* their entries unsourced, so rule 1 or rule 2 always resolves, and the unsourced
  entries live almost entirely in single-abstract records where selection is trivial.

Case-insensitive comparison is deliberate: the observed vocabulary is inconsistent
(`Elsevier` and `Elsevier B.V.`, `Oxford Journals` and `Oxford University Press`), so
assuming exact casing for `arXiv` is a gamble with no upside.

### D10 — Absent-tolerant field mapping; first entry wins

Every optional field is read through a guard that tolerates the key being **absent
entirely**, not merely null. `AGENTS.md §4.2` is blunt about this and the measurements
agree: `arxiv_eprints` is missing on **29%** of most-cited records.

| Target | Source | Guard |
|---|---|---|
| `inspire_id` | `control_number` | required |
| `title` | `titles[0].title` | required |
| `abstract` | see **D9** | required, else skip |
| `authors` | `authors[].full_name` | missing → `[]`; entries lacking `full_name` dropped |
| `arxiv_id` | `arxiv_eprints[0].value` | missing → `""` |
| `categories` | `arxiv_eprints[0].categories` | **double index**, outer guard first |
| `doi` | `dois[0].value` | missing → `""`; 62/500 have several |
| `journal` | `publication_info[*].journal_title`, first present | 7/500 have entries but no title anywhere |
| `earliest_date` | `earliest_date` | verbatim, never padded (HS-004 D2) |
| `citation_count` | `citation_count` | missing → `None` |

Where several entries exist — 62 records with multiple DOIs, 65 with multiple
`publication_info` — **the first is taken**, extending HS-004's precedent of storing
what the source gave us rather than adjudicating between versions. `journal` is the one
exception to strict first-wins: it scans for the first entry that actually has a
`journal_title`, because an entry without one carries no journal information at all.

`categories` is the crash `AGENTS.md §4.2` warns about —
`metadata.get("arxiv_eprints", [{}])[0]` is unsafe. Once `arxiv_eprints` is confirmed
non-empty, `categories` is always present (0 counterexamples in 354 records), so the
outer guard is the whole job. Roughly a third of the corpus will carry empty
`categories`, which is correct: those papers predate arXiv.

### D11 — `arxiv_id` stored verbatim, both shapes

`1207.7214` and `hep-ph/0603175` are stored exactly as INSPIRE returns them; **35% are
old-style**. This mirrors HS-004's `earliest_date` decision — store the source's value,
transform at the edges.

*Consequence for HS-012:* a user pasting `arXiv:2609.04868` will not string-match the
stored `2609.04868`. Stripping an `arXiv:` prefix from the *query* is the search
layer's job, and is easier than un-prefixing every stored value.

### D12 — Configuration through settings, injectable per call

Throttle delay, request timeout, retry budget and default page size are Django
settings with sane defaults, overridable as constructor or call arguments so tests can
set the delay to zero without monkeypatching `sleep`. Any of them exposed as an
environment variable is added to `.env.example` in the same commit.

The base URL is a constant, not a setting — there is no second INSPIRE.

### D13 — The fixture is real, committed, and covers the rules

The card asks for a record with no abstract and one lacking DOI and `publication_info`.
Measurement says that is not enough: it must also carry a **multi-abstract** record
(33% of the corpus), one with **no `arxiv_eprints`** (29%), an **old-style** arXiv id
(35% of those that have one), and one with **multiple DOIs** (12%). Those are precisely
the branches D9 and D10 execute; without them the rules ship untested.

Captured with `authors.full_name`, ~10 real records is roughly a 150 KB committed
fixture. Records are chosen to exercise shapes rather than to include the largest
author list in the corpus — one moderately large collaboration paper proves nothing
chokes without committing a 100 KB single record.

## Risks / Trade-offs

- **A new dependency in a project that tracks its refusals** → `AGENTS.md §2` gains
  httpx and its transitive set explicitly, so the ledger stays honest and the next
  person sees it was a decision, not a drift.
- **Retry is hand-written, so it is ours to get wrong** → It is confined to one
  function with no I/O other than the fetch, and is tested by driving that function
  with canned failures. The alternative (`urllib3.Retry`) is configuration that is
  just as easy to get wrong and harder to inspect.
- **`limit` = yielded makes API cost unpredictable** → Fetch count varies with the
  skip rate (2.2%–10% depending on slice). Accepted: predictable *corpus size* is what
  the operator asked for, and the fetched/skipped counts are reported by HS-006.
- **The 10,000 window caps any single query** → Not a v1 problem (5,600 needed of
  29,128 available) but it is a wall. Growing past it means slicing the query by year
  or category, or `search_after`. Recorded, not solved.
- **Unsaved `Paper` instances couple the client to the model's field names** → That
  coupling is the point; the direction is legal and a schema change should break these
  tests loudly rather than silently mismap.
- **The abstract rule may pick a publisher variant when arXiv is absent** → Accepted.
  The variants differ by tens of characters and the rule is stable, which is the
  property that actually matters.
- **The fixture ages** → INSPIRE could change shape and the fixture would keep passing.
  Accepted for v1; the live path is exercised by HS-006's required real run.

## Migration Plan

Nothing to migrate — this change adds a module and writes no schema. `uv add httpx`
updates `pyproject.toml` and `uv.lock`; `uv sync` is the only step for a contributor.

Rollback is deleting the module and the dependency; nothing else imports it until
HS-006.

## Open Questions

- **OQ1 — the abstract/token-window question inherited from HS-004 is still open.**
  `AGENTS.md §6` claims abstracts sit "comfortably inside the model's 512-token window"
  and uses that to rule out chunking; the HS-004 spike measured a 5,333-character
  abstract (~1,300 tokens). This change stores the text either way. It must be settled
  in HS-009/HS-010, and `AGENTS.md §6` amended there.
- **OQ2 — does the skip rate hold across the whole corpus?** 2.2% of `mostcited`
  records lack an abstract versus the ~10% `AGENTS.md §4.2` claims overall. Under D5
  the client absorbs the difference, so this only affects how many requests a real run
  makes. HS-006's real ingestion run will measure it.
- **OQ3 — is INSPIRE's `abstracts` ordering contractually stable?** Verified stable
  across two identical requests, but that is an observation. D9's rule 1 does not
  depend on it; rule 2 does. If it ever churns, the symptom is `updated_at` churn on
  re-ingest, not wrong data.
