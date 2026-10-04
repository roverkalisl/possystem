from django.db import migrations


class Migration(migrations.Migration):
    """PurchaseOrder (and the supplier advance/settlement models) are already
    created by 0001_initial. This migration originally re-created PurchaseOrder,
    which fails on any fresh database (including the test database) with
    'table "pos_purchaseorder" already exists'. It is kept as a no-op so the
    migration graph and existing django_migrations records stay valid."""

    dependencies = [
        ("pos", "0001_initial"),
    ]

    operations = []
