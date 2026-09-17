import os

import pytest
from django.core.cache import cache

# Keep later test setup safe when pytest-django has already configured Django.
os.environ.setdefault("SECRET_KEY", "test-only-not-for-deployment")


@pytest.fixture(autouse=True)
def _reset_embedding_provider():
    """Keep the cached provider from leaking between tests.

    `apps.embedding.registry` caches its provider for the life of the process, so a test
    that overrides `EMBEDDING_PROVIDER` would otherwise be served whatever an earlier
    test constructed — or leave its own provider behind for the next test. Resetting on
    both sides means neither ordering matters.

    Imported inside the fixture, not at module scope: the registry only reads settings,
    so nothing here can pull in an embedding library.
    """
    from apps.embedding import registry
    from apps.search import health

    registry.reset()
    health.reset()
    cache.clear()
    yield
    registry.reset()
    health.reset()
    cache.clear()
