"""The real embedding provider, wrapping sentence-transformers.

This is the **only** module in the repository that imports `sentence_transformers`
(AGENTS.md §3). It imports it inside `_load_model` rather than at module level, because
the library is an optional dependency: a plain `uv sync` does not install it, and every
other command — `migrate`, `check`, the whole default test suite — must keep working on
such a machine. The absence surfaces only when something genuinely embeds, and says
which extra to install.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence
from typing import Any

from django.conf import settings

from apps.embedding.protocol import validate_texts

logger = logging.getLogger(__name__)

EXTRA_HINT = "uv sync --extra local-embeddings"

# Declared dimensions, owned by this implementation rather than configured separately.
# A provider cannot ask a model its width without loading it, and the system check must
# never load a model, so the width has to be knowable statically. Adding a model here is
# deliberately a code edit: it is the moment to remember that changing the model is a
# migration (AGENTS.md §6), because HS-010's vector column is built from this number.
MODEL_DIMENSIONS = {
    "all-MiniLM-L6-v2": 384,
    "all-MiniLM-L12-v2": 384,
    "all-mpnet-base-v2": 768,
}


def _embedding_dimension(model: Any) -> int:
    """Ask a loaded model how wide its vectors are, across library versions.

    sentence-transformers 6 renamed `get_sentence_embedding_dimension` to
    `get_embedding_dimension` and warns on the old name. We declare `>=3.0`, so both
    have to work — and this value guards the declaration in MODEL_DIMENSIONS, which is
    exactly the check we do not want silently skipped by an AttributeError.
    """
    accessor = getattr(model, "get_embedding_dimension", None)
    if accessor is None:
        accessor = model.get_sentence_embedding_dimension
    return accessor()


class LocalEmbeddingProvider:
    """Embeds with a locally-run sentence-transformers model."""

    def __init__(self) -> None:
        self._model_name = settings.EMBEDDING_MODEL
        if self._model_name not in MODEL_DIMENSIONS:
            known = ", ".join(sorted(MODEL_DIMENSIONS))
            raise ValueError(
                f"EMBEDDING_MODEL={self._model_name!r} has no declared dimension. "
                f"Known models: {known}. Add it to MODEL_DIMENSIONS in "
                "apps/embedding/local.py — a guessed dimension would corrupt the "
                "vector column."
            )
        self._dimension = MODEL_DIMENSIONS[self._model_name]
        self._model: Any | None = None
        self._lock = threading.Lock()

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        # Before the model, so an empty batch costs nothing and an all-blank batch fails
        # without paying for a load.
        if not texts:
            return []
        validate_texts(texts)

        model = self._load_model()
        vectors = model.encode(
            list(texts),
            # The interface promises unit vectors, so this is not optional. It also
            # matches what all-MiniLM-L6-v2 is trained for.
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        # Plain lists keep numpy out of the interface and are what psycopg/pgvector
        # want from HS-010 onwards.
        return [[float(component) for component in vector] for vector in vectors]

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        # Double-checked under the lock: without it two threads racing into the first
        # embed would each load the model and briefly double resident memory.
        with self._lock:
            if self._model is None:
                self._model = self._build_model()
        return self._model

    def _build_model(self) -> Any:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                f"sentence-transformers is not installed, so {self._model_name!r} "
                f"cannot be loaded. Install the optional dependency: {EXTRA_HINT}"
            ) from exc

        logger.info("Loading embedding model %s", self._model_name)
        model = SentenceTransformer(self._model_name)

        actual = _embedding_dimension(model)
        if actual != self._dimension:
            raise ValueError(
                f"Model {self._model_name!r} produces {actual}-dimensional vectors, "
                f"but {self._dimension} was declared. Correct MODEL_DIMENSIONS in "
                "apps/embedding/local.py; emitting vectors of an unexpected width "
                "would break the stored vector column."
            )
        return model
