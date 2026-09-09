"""Ranking: turns a user's query text into papers ordered by relevance.

Pure over a queryset — takes no request, builds no response, and performs no
excerpting, date completion or link construction, so it is testable without HTTP and
composable with a future hybrid ranker (HS-012) instead of being reimplemented by it.
"""

from __future__ import annotations

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import F, QuerySet

from apps.papers.models import SEARCH_CONFIG, Paper


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
        .annotate(rank=SearchRank(F("search_vector"), search_query))
        .order_by("-rank", "-inspire_id")[:limit]
    )
