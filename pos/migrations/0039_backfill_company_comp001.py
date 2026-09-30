# Multi-Company Phase 1 data migration.
#
# Safety notes:
# - Idempotent: uses get_or_create for the Company row and only updates
#   Project rows where company is currently NULL, so re-running this
#   migration (or running it a second time after a partial deploy) is safe
#   and will not duplicate COMP001 or overwrite an already-mapped project.
# - Non-destructive: touches only the new `company_id` column. No other
#   field on Project is read or written. No other table is touched.
# - Explicit, not a blind bulk update: the company_code/company_name are
#   fixed, verified values (not guessed), and the queryset is scoped to
#   company__isnull=True rather than Project.objects.all().
# - Reverse migration intentionally does not delete the Company row or
#   null out the mapped projects, to avoid ever destroying data via a
#   migration rollback; it is a documented no-op.
from django.db import migrations

COMPANY_CODE = "COMP001"
COMPANY_NAME = "P&I Constructions"


def backfill_company(apps, schema_editor):
    Company = apps.get_model("pos", "Company")
    Project = apps.get_model("pos", "Project")

    company, _ = Company.objects.get_or_create(
        company_code=COMPANY_CODE,
        defaults={"company_name": COMPANY_NAME, "is_active": True},
    )

    Project.objects.filter(company__isnull=True).update(company=company)


def reverse_noop(apps, schema_editor):
    # Deliberately not reversed: do not null out Project.company or delete
    # the Company row on a migration rollback. This keeps the migration
    # safe to reverse without risking data loss.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("pos", "0038_company_foundation"),
    ]

    operations = [
        migrations.RunPython(backfill_company, reverse_noop),
    ]
