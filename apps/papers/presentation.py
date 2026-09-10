from __future__ import annotations


def excerpt_abstract(abstract: str, max_chars: int) -> str:
    """Return an abstract excerpt cut at a word boundary when it is too long."""
    if len(abstract) <= max_chars:
        return abstract
    cut = abstract[:max_chars]
    last_space = cut.rfind(" ")
    if last_space <= 0:
        return "\u2026"
    cut = cut[:last_space]
    return f"{cut.rstrip()}\u2026"
