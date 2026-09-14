from django.contrib import admin

from apps.papers.models import Paper


@admin.register(Paper)
class PaperAdmin(admin.ModelAdmin):
    list_display = (
        "inspire_id",
        "title",
        "author_summary",
        "earliest_date",
        "citation_count",
    )
    search_fields = ("title", "abstract", "inspire_id")
    readonly_fields = ("created_at", "updated_at", "embedding", "embedding_model", "embedded_at")
