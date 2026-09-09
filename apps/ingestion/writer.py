"""Batch write path for ingestion: compare incoming papers against what is stored and
write only what genuinely changed.

Split into a pure comparison step (`diff_batch`, no database) and a thin database step
(`load_existing`, `apply_batch`), so the comparison logic is testable without a
database and `--dry-run` can run the same comparison while skipping only the writes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from apps.papers.models import Paper

# Fields ingestion populates and therefore compares. Derived from the model's concrete
# fields minus identity, bookkeeping and database-generated columns, so this list
# cannot drift silently as the model grows. `search_vector` is reported as concrete by
# get_fields() but is a GeneratedField maintained entirely by PostgreSQL: ingestion
# neither supplies nor owns it, and Django refuses to bulk_update a generated column.
_EXCLUDED_FIELDS = {"id", "inspire_id", "created_at", "updated_at", "search_vector"}
COMPARE_FIELDS = tuple(
    f.name
    for f in Paper._meta.get_fields()
    if getattr(f, "concrete", False) and f.name not in _EXCLUDED_FIELDS
)


@dataclass
class BatchResult:
    created: list[Paper] = field(default_factory=list)
    updated: list[Paper] = field(default_factory=list)
    unchanged: int = 0


def diff_batch(incoming: list[Paper], existing_by_inspire_id: dict[int, Paper]) -> BatchResult:
    """Partition `incoming` papers into created / updated / unchanged against the
    stored rows keyed by `inspire_id`. Papers in `updated` are the *existing* model
    instances mutated in place with the incoming values, ready for `bulk_update`.
    Performs no database access.
    """
    result = BatchResult()
    for paper in incoming:
        existing = existing_by_inspire_id.get(paper.inspire_id)
        if existing is None:
            result.created.append(paper)
            continue
        changed = False
        for field_name in COMPARE_FIELDS:
            new_value = getattr(paper, field_name)
            if getattr(existing, field_name) != new_value:
                setattr(existing, field_name, new_value)
                changed = True
        if changed:
            existing.updated_at = timezone.now()
            result.updated.append(existing)
        else:
            result.unchanged += 1
    return result


def load_existing(inspire_ids: list[int]) -> dict[int, Paper]:
    """One SELECT for the stored rows a batch might touch."""
    rows = Paper.objects.filter(inspire_id__in=inspire_ids)
    return {paper.inspire_id: paper for paper in rows}


def apply_batch(result: BatchResult) -> None:
    """Write a diffed batch. A batch is all-or-nothing; the run as a whole is not, so
    that an interrupted run only loses the batch in flight.
    """
    with transaction.atomic():
        if result.created:
            Paper.objects.bulk_create(result.created)
        if result.updated:
            Paper.objects.bulk_update(result.updated, [*COMPARE_FIELDS, "updated_at"])
