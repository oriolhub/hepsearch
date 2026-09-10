"""A deterministic, offline embedding provider. NOT FOR REAL USE.

This is a test double that ships as application code so that `EMBEDDING_PROVIDER` can
name it and tests configure it exactly the way an operator would. It must never
populate a real corpus: its vectors are hashed word counts and carry no meaning beyond
"these two texts share words".

That is nevertheless enough to make offline tests assert real behaviour rather than
plumbing. HS-011's "the nearest vector ranks first" and HS-012's rank fusion are only
meaningful if related texts genuinely land near each other, which a random-hash fake
could not deliver.

`manage.py check` warns whenever this provider is configured outside the test suite.
Its `model_name` includes its active dimension, so incompatible fake vector spaces
cannot be mistaken for one another in the database.
"""

from __future__ import annotations

import math
import re
import zlib
from collections.abc import Sequence

from django.conf import settings

from apps.embedding.protocol import validate_texts

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _bucket(token: str, dimension: int) -> int:
    # zlib.crc32, never the builtin hash(): str hashing is randomised per interpreter
    # via PYTHONHASHSEED, so hash() would embed the same abstract differently in two
    # processes. HS-010 writes vectors in one process and HS-011 compares them in
    # another, so cross-process determinism is a correctness requirement, not a nicety.
    return zlib.crc32(token.encode("utf-8")) % dimension


class FakeEmbeddingProvider:
    """Hashed bag-of-words vectors: deterministic, offline, and never meaningful."""

    @property
    def dimension(self) -> int:
        # Follows the configured dimension rather than declaring its own, so the fake is
        # drop-in wherever the real provider would be — including against HS-010's
        # VectorField.
        return settings.EMBEDDING_DIMENSION

    @property
    def model_name(self) -> str:
        return f"fake-bow-{self.dimension}"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        validate_texts(texts)
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        dimension = self.dimension
        vector = [0.0] * dimension
        tokens = _tokenize(text)
        if not tokens:
            # The contract is about non-whitespace content, not about what survives
            # tokenization. "..." is a string a user can type and a transformer embeds
            # happily, so hashing the raw text keeps this provider from being stricter
            # than the real one — and keeps the norm non-zero below.
            tokens = [text.strip()]
        for token in tokens:
            vector[_bucket(token, dimension)] += 1.0
        norm = math.sqrt(sum(component * component for component in vector))
        return [component / norm for component in vector]
