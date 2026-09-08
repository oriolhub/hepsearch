from typing import ClassVar

from django.contrib.postgres.fields import ArrayField
from django.db import models


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

    class Meta:
        verbose_name = "paper"
        verbose_name_plural = "papers"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=~models.Q(abstract=""),
                name="paper_abstract_not_empty",
            )
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
