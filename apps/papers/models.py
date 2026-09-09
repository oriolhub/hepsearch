from typing import ClassVar

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models

# The text search configuration used to build the search vector. Named so that the
# retrieval layer (apps/search) and any future hybrid ranker use the identical value
# rather than a repeated literal, and pinned explicitly because to_tsvector() without
# an explicit configuration resolves it at run time, which PostgreSQL refuses inside a
# generated column.
SEARCH_CONFIG = "english"


class Paper(models.Model):
    inspire_id = models.BigIntegerField(unique=True)
    title = models.TextField()
    abstract = models.TextField()
    authors = ArrayField(models.TextField(), default=list, blank=True)
    categories = ArrayField(models.CharField(max_length=32), default=list, blank=True)
    arxiv_id = models.CharField(max_length=64, blank=True, default="")
    doi = models.CharField(max_length=128, blank=True, default="")
    journal = models.CharField(max_length=256, blank=True, default="")
    earliest_date = models.CharField(max_length=10, blank=True, default="")
    citation_count = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Database-maintained full-text search vector over title (weight A) and abstract
    # (weight B). Generated and persisted by PostgreSQL itself, so it can never drift
    # from the text it describes and no writer — including ingestion — has to
    # remember to update it. Weighting title above abstract lives here, in the
    # schema, rather than in any particular query, so every reader ranks the same way.
    search_vector = models.GeneratedField(
        expression=(
            SearchVector("title", config=SEARCH_CONFIG, weight="A")
            + SearchVector("abstract", config=SEARCH_CONFIG, weight="B")
        ),
        output_field=SearchVectorField(),
        db_persist=True,
    )

    class Meta:
        verbose_name = "paper"
        verbose_name_plural = "papers"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=~models.Q(abstract=""),
                name="paper_abstract_not_empty",
            )
        ]
        indexes: ClassVar[list[models.Index]] = [
            GinIndex(fields=["search_vector"], name="paper_search_vector_gin"),
        ]

    def __str__(self) -> str:
        return f"{self.inspire_id}: {self.title[:80]}"

    @property
    def inspire_url(self) -> str:
        return f"https://inspirehep.net/literature/{self.inspire_id}"

    def author_summary(self, max_authors: int = 3) -> str:
        if not self.authors:
            return ""
        if len(self.authors) <= max_authors:
            return ", ".join(self.authors)
        leading = ", ".join(self.authors[:max_authors])
        return f"{leading} et al. ({len(self.authors)})"
