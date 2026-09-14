import pgvector.django
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("papers", "0004_paper_embedded_at_paper_embedding_and_more"),
    ]

    operations = [
        # HNSW is migration-safe on an empty table; IVFFlat needs training data.
        # Cosine is equivalent to inner product for HS-009's normalized vectors,
        # and makes HS-011's intended distance operator explicit.
        migrations.AddIndex(
            model_name="paper",
            index=pgvector.django.HnswIndex(
                fields=["embedding"],
                name="paper_embedding_hnsw",
                opclasses=["vector_cosine_ops"],
            ),
        ),
    ]
