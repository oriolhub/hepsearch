"""The embedding seam: one interface between this project and any embedding model.

Nothing outside an implementation of `EmbeddingProvider` may import an embedding
library or contact an embedding vendor (AGENTS.md §3). Swapping the local model for a
hosted API means adding one module here and changing one setting — no caller moves.

This module deliberately imports nothing but the standard library, so that it stays
importable on a machine that never installed the optional embedding dependency.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class BlankTextError(ValueError):
    """Raised when text with no non-whitespace content is submitted for embedding.

    A blank string has no meaning to embed. Returning a zero or arbitrary vector would
    be worse than refusing: a zero vector is equidistant from everything and would make
    a nearest-neighbour query answer with arbitrary papers rather than none.

    Callers at an HTTP boundary reject blank input before reaching a provider — see
    `apps/search/views.py`, which already refuses a blank `q` with 400.
    """


class EmbeddingProvider(Protocol):
    """Turns text into vectors.

    Every implementation must honour the whole of this contract, because vectors from
    different implementations are stored in the same column and compared against each
    other:

    Identity
        `dimension` is the number of components in every returned vector, and must be
        knowable **without loading a model**, so that a cheap system check can compare
        it against `settings.EMBEDDING_DIMENSION`.

        `model_name` identifies the vector *space*, not the implementation. Two
        providers whose vectors are not comparable must never share a name: HS-010
        stores this value beside each vector and HS-011 refuses to compare a stored
        vector against a query embedded in a different space.

    Input
        `embed` takes a sequence of texts and returns one vector per text, **in the same
        order**, so a caller can pair results with its own records by position.

        An empty sequence returns an empty list and must not load a model.

        A text that is empty or only whitespace raises `BlankTextError`.

        Any text containing non-whitespace content returns exactly one vector. The
        contract is defined on non-whitespace *content*, never on whether anything
        survives an implementation's own tokenization — otherwise a bag-of-words
        implementation would reject `"..."` while a transformer accepted it, and a query
        that worked in production would fail in tests.

    Output
        Every vector is L2-normalized. This is a property of the interface, not of one
        implementation, so that stored vectors stay comparable regardless of which
        implementation wrote them, and so a consumer may index them with either the
        cosine or the inner-product operator class. It is not configurable: a switch
        would produce stored vectors whose comparability depended on whatever the
        setting happened to be at write time.
    """

    @property
    def dimension(self) -> int:
        """Components per vector, knowable without loading a model."""
        ...

    @property
    def model_name(self) -> str:
        """Identifier of the vector space these vectors belong to."""
        ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one unit vector per text, in input order."""
        ...


def validate_texts(texts: Sequence[str]) -> None:
    """Enforce the blank-text rule for every implementation.

    A Protocol cannot inherit behaviour to its implementations, so this is the shared
    guard they each call. It raises before any model is touched, which is what lets an
    all-blank batch fail without paying for a model load.
    """
    for index, text in enumerate(texts):
        if not text.strip():
            raise BlankTextError(
                f"text at position {index} is empty or whitespace-only; "
                "reject blank input before embedding it"
            )
