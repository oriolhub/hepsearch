"""HTTP boundary for search: parses the request, decides what an empty or
impossible result *means*, and builds the response. The rankers in
apps/search/ranking.py stay pure — they return orderings, never status codes.
"""

from __future__ import annotations

import logging
import math
import time

from django.conf import settings
from django.contrib.postgres.search import SearchHeadline, SearchQuery
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.utils.html import escape
from rest_framework.decorators import api_view
from rest_framework.exceptions import Throttled
from rest_framework.request import Request
from rest_framework.response import Response

from apps.embedding.registry import get_provider
from apps.papers.models import SEARCH_CONFIG, Paper

from .health import check_stale_embeddings
from .modes import SearchMode, parse_mode
from .pagination import SearchPagination
from .presentation import HIGHLIGHT_END, HIGHLIGHT_START, render_highlighted_text
from .ranking import reciprocal_rank_fusion, semantic_search
from .ranking import search as keyword_search
from .serializers import PaperSearchResultSerializer
from .throttling import EmbeddingThrottle, KeywordThrottle

logger = logging.getLogger(__name__)

PROVIDER_UNAVAILABLE = "Semantic search is unavailable; the embedding provider could not be loaded."
CORPUS_UNAVAILABLE = "Semantic search is unavailable; run embed_papers to embed the corpus."


def _throttle_for_mode(mode: SearchMode):
    return KeywordThrottle if mode is SearchMode.KEYWORD else EmbeddingThrottle


def _allow_request(request, mode: SearchMode) -> None:
    throttle = _throttle_for_mode(mode)()
    if not throttle.allow_request(request, None):
        raise Throttled(wait=throttle.wait())


def _safe_query_for_log(query: str) -> str:
    return query.encode("unicode_escape").decode("ascii")


def _headline(query: str):
    return SearchHeadline(
        "abstract",
        SearchQuery(query, config=SEARCH_CONFIG, search_type="websearch"),
        config=SEARCH_CONFIG,
        start_sel=HIGHLIGHT_START,
        stop_sel=HIGHLIGHT_END,
        max_fragments=2,
    )


def _rank_with_logging(query: str, mode: SearchMode, *, highlight: bool = False):
    started = time.monotonic()
    result = _ranked_papers(query, mode, highlight=highlight)
    elapsed = time.monotonic() - started
    if elapsed > settings.SEARCH_SLOW_SECONDS:
        logger.warning(
            "Slow search elapsed=%.3fs mode=%s query=%s",
            elapsed,
            mode.value,
            _safe_query_for_log(query),
        )
    return (*result, elapsed)


def _rank(query: str, mode: SearchMode, *, highlight: bool = False) -> list[Paper]:
    if mode is SearchMode.KEYWORD:
        papers = keyword_search(query, settings.SEARCH_RESULT_LIMIT)
        if highlight:
            papers = papers.annotate(headline=_headline(query))
        return list(papers)

    provider = get_provider()
    check_stale_embeddings(provider.model_name)
    vector = provider.embed([query])[0]
    papers = semantic_search(
        Paper.objects.all(),
        vector,
        settings.SEARCH_RESULT_LIMIT,
        model_name=provider.model_name,
    )
    if highlight:
        papers = papers.annotate(headline=_headline(query))
    return list(papers)


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


def _hybrid_rank(query: str, *, highlight: bool = False) -> tuple[list[Paper], str | None]:
    keyword_queryset = keyword_search(query, settings.HYBRID_CANDIDATE_DEPTH)
    if highlight:
        keyword_queryset = keyword_queryset.annotate(headline=_headline(query))
    keyword_papers = list(keyword_queryset)
    try:
        provider = get_provider()
        check_stale_embeddings(provider.model_name)
        vector = provider.embed([query])[0]
        semantic_queryset = semantic_search(
            Paper.objects.all(),
            vector,
            settings.HYBRID_CANDIDATE_DEPTH,
            model_name=provider.model_name,
        )
        if highlight:
            semantic_queryset = semantic_queryset.annotate(headline=_headline(query))
        semantic_papers = list(semantic_queryset)
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


def _ranked_papers(
    query: str, mode: SearchMode, *, highlight: bool = False
) -> tuple[list[Paper], str | None]:
    """Rank papers, returning why semantic search could not run rather than raising.

    sentence-transformers is an optional extra (AGENTS.md section 2), so on a default
    `uv sync` the local provider imports fine but raises ImportError the first time it
    is asked to embed. That is an operator-fixable outage, not a crash: it belongs on
    the same 503 surface as an unembedded corpus, not in a 500 traceback.
    """
    if mode is SearchMode.HYBRID:
        return _hybrid_rank(query, highlight=highlight)
    try:
        return _rank(query, mode, highlight=highlight), None
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
        return Response({"detail": "Parameter 'q' must be non-empty."}, status=400)
    if len(query) > settings.SEARCH_QUERY_MAX_CHARS:
        return Response(
            {
                "detail": (
                    f"Parameter 'q' must be at most {settings.SEARCH_QUERY_MAX_CHARS} characters."
                )
            },
            status=400,
        )
    raw_page_size = request.query_params.get("page_size")
    if raw_page_size is not None:
        try:
            page_size = int(raw_page_size)
        except ValueError:
            return Response({"detail": "Parameter 'page_size' must be an integer."}, status=400)
        if not 1 <= page_size <= settings.SEARCH_MAX_PAGE_SIZE:
            return Response(
                {
                    "detail": (
                        f"Parameter 'page_size' must be between 1 and "
                        f"{settings.SEARCH_MAX_PAGE_SIZE}."
                    )
                },
                status=400,
            )
    _allow_request(request, mode)

    papers, unavailable, _ = _rank_with_logging(query, mode)
    if mode is SearchMode.SEMANTIC and not papers:
        unavailable = unavailable or _empty_semantic_reason()
        if unavailable:
            return Response({"mode": mode.value, "detail": unavailable}, status=503)
    paginator = SearchPagination()
    paginator.mode = mode.value
    paginator.degraded = mode is SearchMode.HYBRID and bool(unavailable)
    paginator.warning = unavailable
    # Every response goes through the paginator, including an empty one. Returning a
    # hand-built envelope for the empty case dropped the degradation report, which made
    # a provider outage that had left no keyword hits indistinguishable from an honest
    # miss. Paginating first also refuses an unusable page before any serialisation.
    page = paginator.paginate_queryset(papers, request)
    results = PaperSearchResultSerializer(page, many=True).data
    return paginator.get_paginated_response(results)


def search_page(request):
    query = request.GET.get("q", "")
    try:
        mode = parse_mode(request.GET.get("mode"))
    except ValueError as error:
        # escape(): the message quotes the submitted mode, and HttpResponseBadRequest
        # serves text/html without escaping, which browsers render.
        return HttpResponseBadRequest(escape(str(error)))
    has_query = bool(query.strip())
    if len(query) > settings.SEARCH_QUERY_MAX_CHARS:
        return HttpResponseBadRequest(
            f"Parameter 'q' must be at most {settings.SEARCH_QUERY_MAX_CHARS} characters."
        )
    try:
        page_size = int(request.GET.get("page_size", settings.SEARCH_PAGE_SIZE))
    except ValueError:
        return HttpResponseBadRequest("Parameter 'page_size' must be an integer.")
    if not 1 <= page_size <= settings.SEARCH_MAX_PAGE_SIZE:
        return HttpResponseBadRequest(
            f"Parameter 'page_size' must be between 1 and {settings.SEARCH_MAX_PAGE_SIZE}."
        )
    page_number = request.GET.get("page", "1")
    if not page_number.isdigit() or int(page_number) < 1:
        return HttpResponse("Invalid page.", status=404)
    papers: list[Paper] = []
    unavailable: str | None = None
    degraded: str | None = None
    elapsed = 0.0
    page = None
    if has_query:
        # Only a request that ranks is charged the rate. A query-less page load embeds
        # nothing and ranks nothing, so spending an embedding-tier token on it would
        # lock the UI out for a reader who never searched.
        try:
            _allow_request(request, mode)
        except Throttled as error:
            response = HttpResponse("Too many requests; please retry later.", status=429)
            if error.wait is not None:
                response["Retry-After"] = str(math.ceil(error.wait))
            return response
        papers, unavailable, elapsed = _rank_with_logging(query, mode, highlight=True)
        if mode is SearchMode.HYBRID:
            degraded = unavailable
            unavailable = None
        if mode is SearchMode.SEMANTIC and not papers:
            unavailable = unavailable or _empty_semantic_reason()
        try:
            page = Paginator(papers, page_size).page(page_number)
        except (PageNotAnInteger, EmptyPage):
            return HttpResponse("Invalid page.", status=404)
        # Only the papers this page actually renders are decorated: the rankers
        # retrieve far more candidates than a page shows.
        for paper in page.object_list:
            if not getattr(paper, "methods", ()):
                paper.methods = (mode.value,)
            paper.highlighted_abstract = render_highlighted_text(
                getattr(paper, "headline", None) or paper.abstract_snippet
            )
    return render(
        request,
        "search/search.html",
        {
            "query": query,
            "papers": page.object_list if page else [],
            "page_obj": page,
            "has_query": has_query,
            "unavailable": unavailable,
            "degraded": bool(degraded),
            "warning": degraded,
            "no_results": has_query and not papers and not unavailable and not degraded,
            "mode": mode.value,
            "retrieved_count": len(papers),
            "elapsed": elapsed,
        },
    )
