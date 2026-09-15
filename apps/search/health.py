from __future__ import annotations

import logging
from functools import cache

from apps.papers.models import Paper

logger = logging.getLogger(__name__)


@cache
def check_stale_embeddings(model_name: str) -> int:
    """Count and report embeddings left behind by a model change.

    Cached per `model_name`, so the warning appears once per process for a given
    provider rather than on every search. A process that switches providers mid-run
    (only the test suite does) reports once per model it sees; `reset()` clears it.
    """
    stale_count = (
        Paper.objects.filter(embedding__isnull=False).exclude(embedding_model=model_name).count()
    )
    if stale_count:
        logger.warning("Semantic corpus contains %s stale embeddings", stale_count)
    return stale_count


def reset() -> None:
    check_stale_embeddings.cache_clear()
