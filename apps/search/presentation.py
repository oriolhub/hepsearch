from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe

HIGHLIGHT_START = "HEPSEARCH_HIGHLIGHT_START"
HIGHLIGHT_END = "HEPSEARCH_HIGHLIGHT_END"


def render_highlighted_text(value: str) -> SafeString:
    """Escape all text, then turn only our own headline markers into ``<mark>``."""
    escaped = escape(value)
    return mark_safe(escaped.replace(HIGHLIGHT_START, "<mark>").replace(HIGHLIGHT_END, "</mark>"))
