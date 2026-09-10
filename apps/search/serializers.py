"""Presentation for search results: date completion, abstract excerpting and the
INSPIRE link. Deliberately separate from ranking (apps/search/ranking.py), which
returns bare `Paper` rows with no notion of how they will be displayed.
"""

from __future__ import annotations

import datetime

from django.conf import settings
from rest_framework import serializers

from apps.papers.models import Paper


def complete_date(value: str) -> datetime.date | None:
    """Turn a possibly-partial `earliest_date` string into a real date.

    The corpus stores `""`, `"YYYY"`, `"YYYY-MM"` or `"YYYY-MM-DD"`. A missing month or
    day is padded to the first of the period, so the API always emits one consistent
    shape rather than three. An empty or unparseable value yields `None` rather than a
    fabricated date.
    """
    if not value:
        return None
    parts = value.split("-")
    if len(parts) not in (1, 2, 3) or len(parts[0]) != 4:
        return None
    if any(len(part) != 2 for part in parts[1:]):
        return None
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return datetime.date(year, month, day)
    except (ValueError, IndexError):
        return None


class PaperSearchResultSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    title = serializers.CharField()
    authors = serializers.SerializerMethodField()
    author_count = serializers.SerializerMethodField()
    publication_date = serializers.SerializerMethodField()
    abstract_snippet = serializers.SerializerMethodField()
    inspire_url = serializers.CharField()

    def get_publication_date(self, paper: Paper) -> datetime.date | None:
        return complete_date(paper.earliest_date)

    def get_abstract_snippet(self, paper: Paper) -> str:
        return paper.abstract_snippet

    def get_authors(self, paper: Paper) -> list[str]:
        return paper.authors[: settings.SEARCH_AUTHOR_SAMPLE_SIZE]

    def get_author_count(self, paper: Paper) -> int:
        return len(paper.authors)
