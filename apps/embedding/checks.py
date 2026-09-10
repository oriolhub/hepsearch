"""System checks that catch embedding misconfiguration before it costs anything.

These run on every `manage.py` invocation, which is why they must stay cheap: they may
construct a provider — construction loads no model by design — but they must never
embed. A check that downloaded 90 MB would make `manage.py check` unusable.
"""

from __future__ import annotations

import sys
from typing import Any

from django.conf import settings
from django.core.checks import Error, Warning, register

from apps.embedding import registry
from apps.embedding.fake import FakeEmbeddingProvider


@register()
def check_embedding_dimension(app_configs: Any, **kwargs: Any) -> list[Any]:
    """Verify the configured dimension matches the configured provider.

    `settings.EMBEDDING_DIMENSION` is the schema contract — HS-010 builds its
    `VectorField` from it, and once that migration exists the number is frozen. A
    provider emitting a different width would fail at insert time, one batch into a
    long ingestion run. Catching it here costs a millisecond instead.
    """
    try:
        provider = registry.get_provider()
    except (AttributeError, ImportError, TypeError, ValueError) as exc:
        return [
            Error(
                f"Embedding configuration is invalid: {exc}",
                hint="Set EMBEDDING_PROVIDER and its provider-specific settings correctly.",
                id="embedding.E001",
            )
        ]

    messages: list[Any] = []

    if provider.dimension != settings.EMBEDDING_DIMENSION:
        messages.append(
            Error(
                f"EMBEDDING_DIMENSION is {settings.EMBEDDING_DIMENSION}, but provider "
                f"{settings.EMBEDDING_PROVIDER} produces {provider.dimension}-"
                "dimensional vectors.",
                hint=(
                    "Set EMBEDDING_DIMENSION to the provider's dimension. If vectors "
                    "are already stored, changing the dimension is a migration."
                ),
                id="embedding.E002",
            )
        )

    # Not an error: tests legitimately configure the fake. Silenced under pytest so the
    # suite does not emit a warning nobody can act on — the same "pytest" in sys.modules
    # idiom config/settings.py already uses.
    if isinstance(provider, FakeEmbeddingProvider) and "pytest" not in sys.modules:
        messages.append(
            Warning(
                "EMBEDDING_PROVIDER is the fake provider. Its vectors are hashed word "
                "counts and are not semantically meaningful.",
                hint=(
                    "Set EMBEDDING_PROVIDER to "
                    "apps.embedding.local.LocalEmbeddingProvider for real use."
                ),
                id="embedding.W001",
            )
        )

    return messages
