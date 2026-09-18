"""Ranking: turns a user's query text into papers ordered by relevance.

Pure over a queryset — takes no request, builds no response, and performs no
excerpting, date completion or link construction, so it is testable without HTTP and
composable with a future hybrid ranker (HS-012) instead of being reimplemented by it.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import ExpressionWrapper, F, FloatField, QuerySet, Value
from pgvector.django import CosineDistance

from apps.papers.models import SEARCH_CONFIG, Paper


@dataclass(frozen=True)
class FusedResult:
    paper_id: int
    score: float
    methods: tuple[str, ...]


def reciprocal_rank_fusion(keyword_ids: list[int], semantic_ids: list[int]) -> list[FusedResult]:
    scores: dict[int, tuple[float, set[str]]] = {}
    for ids, method in ((keyword_ids, "keyword"), (semantic_ids, "semantic")):
        for rank, paper_id in enumerate(ids, start=1):
            score, methods = scores.get(paper_id, (0.0, set()))
            methods.add(method)
            scores[paper_id] = (score + 1 / (settings.RRF_K + rank), methods)

    return [
        FusedResult(
            paper_id,
            score,
            tuple(method for method in ("keyword", "semantic") if method in methods),
        )
        for paper_id, (score, methods) in sorted(
            scores.items(), key=lambda item: (-item[1][0], item[0])
        )
    ]


def search(query: str, limit: int) -> QuerySet[Paper]:
    """Return up to `limit` papers matching `query`, best relevance first.

    `query` is parsed with the "websearch" search type, which never raises regardless
    of punctuation and understands quoted phrases, `-exclusion` and `or`. Relevance is
    scored against the stored `search_vector` column rather than rebuilding a vector
    per row, so ranking can never disagree with what the index actually covers.
    """
    search_query = SearchQuery(query, config=SEARCH_CONFIG, search_type="websearch")
    return (
        Paper.objects.filter(search_vector=search_query)
        .defer("embedding", "search_vector")
        .annotate(score=SearchRank(F("search_vector"), search_query))
        .order_by("-score", "-inspire_id")[:limit]
    )


def semantic_search(
    queryset: QuerySet[Paper],
    vector: list[float],
    limit: int,
    *,
    model_name: str,
) -> QuerySet[Paper]:
    """Return papers nearest to `vector`, using only one embedding space.

    `model_name` is required and has no default on purpose: it is the identity of the
    vector space the caller's `vector` came from, which is the provider's
    `model_name` and not necessarily `settings.EMBEDDING_MODEL` (the fake provider
    reports `fake-bow-384` while the setting still names the real model). Defaulting
    it would silently match zero rows rather than fail.

    The embedding and search_vector columns are deferred: they are large, and nothing
    downstream of ranking reads them. The distance expression still references
    `embedding` server-side, so the vector index is unaffected.
    """
    limit = min(limit, settings.HYBRID_CANDIDATE_DEPTH)
    distance = CosineDistance("embedding", vector)
    similarity = ExpressionWrapper(Value(1.0) - distance, output_field=FloatField())
    return (
        queryset.filter(embedding__isnull=False, embedding_model=model_name)
        .defer("embedding", "search_vector")
        .annotate(distance=distance, score=similarity)
        .order_by("distance", "-inspire_id")[:limit]
    )
