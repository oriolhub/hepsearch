from __future__ import annotations

from django.conf import settings
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class SearchPagination(PageNumberPagination):
    """Paginate materialised rankings without issuing count or hydration queries.

    DRF's default envelope drops the search mode and hybrid degradation warning. Keep
    those fields here so pagination cannot make HS-012's degradation silent.
    """

    page_size = settings.SEARCH_PAGE_SIZE
    page_size_query_param = "page_size"
    max_page_size = settings.SEARCH_MAX_PAGE_SIZE
    # Defaults, not decoration: this is the project-wide DEFAULT_PAGINATION_CLASS, so a
    # view that never sets these must still render an envelope instead of raising.
    mode = None
    degraded = False
    warning = None

    def get_paginated_response(self, data):
        body = {
            "count": self.page.paginator.count,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
            "mode": self.mode,
        }
        if self.degraded:
            body["degraded"] = True
            body["warning"] = self.warning
        return Response(body)
