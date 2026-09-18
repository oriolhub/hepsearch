from apps.search.presentation import (
    HIGHLIGHT_END,
    HIGHLIGHT_START,
    render_highlighted_text,
)


def test_render_highlighted_text_escapes_text_before_marking():
    rendered = render_highlighted_text(
        f"<script>alert(1)</script> {HIGHLIGHT_START}term{HIGHLIGHT_END}"
    )

    assert rendered == ("&lt;script&gt;alert(1)&lt;/script&gt; <mark>term</mark>")
    assert "<script>" not in rendered


def test_render_highlighted_text_leaves_unmarked_text_escaped():
    assert render_highlighted_text("<b>plain</b>") == "&lt;b&gt;plain&lt;/b&gt;"
