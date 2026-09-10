"""Resolves and caches the configured embedding provider.

Two layers of laziness live here, and they answer different questions:

    which object?              when is the model loaded?
    ─────────────              ────────────────────────
    get_provider()             provider.embed([...])
      resolves the setting       the provider's own concern; see local.py
      and caches the instance

Constructing a provider is cheap and loads no model, so calling `get_provider()` in a
system check or at the top of a management command costs nothing.
"""

from __future__ import annotations

import threading
from functools import cache

from django.conf import settings
from django.utils.module_loading import import_string

from apps.embedding.protocol import EmbeddingProvider

# Every entry point serializes on this, so exactly one provider is ever constructed even
# if two threads race into the first call. An uncontended lock costs far less than the
# embedding work that follows it.
_lock = threading.Lock()


@cache
def _construct_provider() -> EmbeddingProvider:
    provider_class = import_string(settings.EMBEDDING_PROVIDER)
    return provider_class()


def get_provider() -> EmbeddingProvider:
    """Return the configured provider, constructing it at most once per process.

    An unresolvable or invalid `EMBEDDING_PROVIDER` propagates. No fallback provider is
    substituted: silently embedding with something other than what was configured is
    how a corpus ends up full of vectors nobody can account for.
    """
    with _lock:
        return _construct_provider()


def reset() -> None:
    """Discard the cached provider.

    Explicit rather than implicit, so a test that points `EMBEDDING_PROVIDER` somewhere
    else does not have to hope a process-global cache notices. The root `conftest.py`
    calls this around every test so no provider leaks between them.
    """
    with _lock:
        _construct_provider.cache_clear()
