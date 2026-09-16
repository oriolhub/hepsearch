"""HTTP boundary for search: parses the request, decides what an empty or
impossible result *means*, and builds the response. The rankers in
apps/search/ranking.py stay pure — they return orderings, never status codes.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.http import HttpResponseBadRequest
from django.shortcuts import render
from django.utils.html import escape
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.embedding.registry import get_provider
from apps.papers.models import Paper

from .health import check_stale_embeddings
from .modes import SearchMode, parse_mode
from .ranking import reciprocal_rank_fusion, semantic_search
from .ranking import search as keyword_search
from .serializers import PaperSearchResultSerializer

logger = logging.getLogger(__name__)

PROVIDER_UNAVAILABLE = "Semantic search is unavailable; the embedding provider could not be loaded."
CORPUS_UNAVAILABLE = "Semantic search is unavailable; run embed_papers to embed the corpus."


def _rank(query: str, mode: SearchMode) -> list[Paper]:
    if mode is SearchMode.KEYWORD:
        return list(keyword_search(query, settings.SEARCH_RESULT_LIMIT))

    provider = get_provider()
    check_stale_embeddings(provider.model_name)
    vector = provider.embed([query])[0]
    return list(
        semantic_search(
            Paper.objects.all(),
            vector,
            settings.SEARCH_RESULT_LIMIT,
            model_name=provider.model_name,
        )
    )


def _degraded_hybrid(keyword_papers: list[Paper], reason: str) -> tuple[list[Paper], str | None]:
    """Serve the keyword ranking alone, naming it, unless the corpus is merely empty.

    `_empty_semantic_reason` is the single place that tells an outage apart from a
    corpus nobody has ingested yet, so both degradation paths ask it rather than
    repeating the predicate in opposite directions. Marking the survivors "keyword"
    here rather than in the view keeps the API and the page agreeing on what a degraded
    result is.
    """
    if _empty_semantic_reason() is None:
        return [], None
    papers = keyword_papers[: settings.SEARCH_RESULT_LIMIT]
    for paper in papers:
        paper.methods = ("keyword",)
    return papers, reason


def _hybrid_rank(query: str) -> tuple[list[Paper], str | None]:
    keyword_papers = list(keyword_search(query, settings.HYBRID_CANDIDATE_DEPTH))
    try:
        provider = get_provider()
        check_stale_embeddings(provider.model_name)
        vector = provider.embed([query])[0]
        semantic_papers = list(
            semantic_search(
                Paper.objects.all(),
                vector,
                settings.HYBRID_CANDIDATE_DEPTH,
                model_name=provider.model_name,
            )
        )
    except ImportError:
        logger.exception("The embedding provider could not be loaded")
        return _degraded_hybrid(keyword_papers, PROVIDER_UNAVAILABLE)

    if not semantic_papers:
        return _degraded_hybrid(keyword_papers, CORPUS_UNAVAILABLE)

    paper_map = {paper.pk: paper for paper in keyword_papers + semantic_papers}
    fused = reciprocal_rank_fusion(
        [paper.pk for paper in keyword_papers],
        [paper.pk for paper in semantic_papers],
    )
    papers = []
    for result in fused[: settings.SEARCH_RESULT_LIMIT]:
        paper = paper_map[result.paper_id]
        paper.score = result.score
        paper.methods = result.methods
        papers.append(paper)
    return papers, None


def _ranked_papers(query: str, mode: SearchMode) -> tuple[list[Paper], str | None]:
    """Rank papers, returning why semantic search could not run rather than raising.

    sentence-transformers is an optional extra (AGENTS.md section 2), so on a default
    `uv sync` the local provider imports fine but raises ImportError the first time it
    is asked to embed. That is an operator-fixable outage, not a crash: it belongs on
    the same 503 surface as an unembedded corpus, not in a 500 traceback.
    """
    if mode is SearchMode.HYBRID:
        return _hybrid_rank(query)
    try:
        return _rank(query, mode), None
    except ImportError:
        logger.exception("The embedding provider could not be loaded")
        return [], PROVIDER_UNAVAILABLE


def _empty_semantic_reason() -> str | None:
    """Why an empty semantic result is a fault, or None if it is a genuine miss.

    A corpus nobody has ingested yet is not broken — it is empty, and 200 with no
    results is the honest answer. Papers that exist but carry no embedding in the
    configured space mean semantic search genuinely cannot operate until an operator
    runs embed_papers.
    """
    if not Paper.objects.exists():
        return None
    return CORPUS_UNAVAILABLE


@api_view(["GET"])
def search(request: Request) -> Response:
    try:
        mode = parse_mode(request.query_params.get("mode"))
    except ValueError as error:
        return Response({"detail": str(error)}, status=400)

    query = request.query_params.get("q", "")
    if not query.strip():
        return Response(
            {"detail": "A non-empty 'q' query parameter is required."},
            status=400,
        )

    papers, unavailable = _ranked_papers(query, mode)
    if mode is SearchMode.SEMANTIC and not papers:
        unavailable = unavailable or _empty_semantic_reason()
        if unavailable:
            return Response({"mode": mode.value, "detail": unavailable}, status=503)
    results = PaperSearchResultSerializer(papers, many=True).data
    body = {"mode": mode.value, "count": len(results), "results": results}
    if mode is SearchMode.HYBRID and unavailable:
        body["degraded"] = True
        body["warning"] = unavailable
    return Response(body)


def search_page(request):
    query = request.GET.get("q", "")
    try:
        mode = parse_mode(request.GET.get("mode"))
    except ValueError as error:
        # escape(): the message quotes the submitted mode, and HttpResponseBadRequest
        # serves text/html without escaping, which browsers render.
        return HttpResponseBadRequest(escape(str(error)))
    has_query = bool(query.strip())
    papers: list[Paper] = []
    unavailable: str | None = None
    degraded: str | None = None
    if has_query:
        papers, unavailable = _ranked_papers(query, mode)
        if mode is SearchMode.HYBRID:
            degraded = unavailable
            unavailable = None
        if mode is SearchMode.SEMANTIC and not papers:
            unavailable = unavailable or _empty_semantic_reason()
    return render(
        request,
        "search/search.html",
        {
            "query": query,
            "papers": papers,
            "has_query": has_query,
            "unavailable": unavailable,
            "degraded": bool(degraded),
            "warning": degraded,
            "no_results": has_query and not papers and not unavailable and not degraded,
            "mode": mode.value,
        },
    )
