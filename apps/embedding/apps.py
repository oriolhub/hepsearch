"""App configuration for the embedding layer.

This app has no models, no views and no migrations, which is unusual enough to need a
reason: **Django only auto-discovers system checks from installed apps**. The dimension
contract in `checks.py` is the whole point of registering here — it compares
`settings.EMBEDDING_DIMENSION` against the configured provider's declared dimension on
every `manage.py` invocation, long before HS-010 freezes that number into a migration.

The app also gives the embedding layer a home that neither `apps.search` nor
`apps.ingestion` owns. Both need to embed text, and AGENTS.md §3 forbids either from
importing the other, so the shared code cannot live in either one.
"""

from __future__ import annotations

from django.apps import AppConfig


class EmbeddingConfig(AppConfig):
    # No default_auto_field: this app has no models, so there is nothing for it to
    # apply to. DEFAULT_AUTO_FIELD in config/settings.py covers the apps that do.
    name = "apps.embedding"

    def ready(self) -> None:
        # Importing registers the system checks with Django's check framework.
        from apps.embedding import checks  # noqa: F401
