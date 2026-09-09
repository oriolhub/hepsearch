from django.conf import settings
from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from .ranking import search as rank_papers
from .serializers import PaperSearchResultSerializer


@api_view(["GET"])
def search(request: Request) -> Response:
    query = request.query_params.get("q", "")
    if not query.strip():
        return Response(
            {"detail": "A non-empty 'q' query parameter is required."},
            status=400,
        )

    papers = list(rank_papers(query, settings.SEARCH_RESULT_LIMIT))
    results = PaperSearchResultSerializer(papers, many=True).data
    return Response({"count": len(results), "results": results})


def search_page(request):
    query = request.GET.get("q", "")
    has_query = bool(query.strip())
    papers = list(rank_papers(query, settings.SEARCH_RESULT_LIMIT)) if has_query else []
    return render(
        request,
        "search/search.html",
        {
            "query": query,
            "papers": papers,
            "has_query": has_query,
            "no_results": has_query and not papers,
        },
    )
