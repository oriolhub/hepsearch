from __future__ import annotations

from rest_framework.throttling import SimpleRateThrottle


class SearchThrottle(SimpleRateThrottle):
    """Anonymous IP throttle shared by the API and HTML search page."""

    def get_cache_key(self, request, view):
        if getattr(request, "user", None) and request.user.is_authenticated:
            return None
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class KeywordThrottle(SearchThrottle):
    scope = "keyword"


class EmbeddingThrottle(SearchThrottle):
    scope = "embedding"
