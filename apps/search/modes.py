from __future__ import annotations

from enum import StrEnum


class SearchMode(StrEnum):
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


def parse_mode(value: str | None) -> SearchMode:
    if value is None:
        return SearchMode.HYBRID
    try:
        return SearchMode(value)
    except ValueError as error:
        raise ValueError(f"Unknown search mode: {value}") from error
