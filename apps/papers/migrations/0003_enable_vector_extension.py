from django.contrib.postgres.operations import CreateExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("papers", "0002_paper_search_vector_paper_paper_search_vector_gin"),
    ]

    operations = [
        # vector is an untrusted PostgreSQL extension and requires a superuser.
        # A least-privilege deployment must have its DBA install it out of band
        # before applying this migration.
        CreateExtension("vector"),
    ]
