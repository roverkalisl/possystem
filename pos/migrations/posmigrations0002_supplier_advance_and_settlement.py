from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ("pos", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SupplierAdvance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("advance_no", models.CharField(blank=True, max_length=30, null=True, unique=True)),
                ("advance_date", models.DateField(default=timezone.now)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("payment_method", models.CharField(choices=[("cash", "Cash"), ("card", "Card"), ("bank", "Bank Transfer"), ("cheque", "Cheque")], default="cash", max_length=20)),
                ("note", models.TextField(blank=True, null=True)),
                ("status", models.CharField(choices=[("approved", "Approved"), ("closed", "Closed")], default="approved", max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("advance_gl", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="supplier_advance_gl", to="pos.glmaster")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_supplier_advances", to=settings.AUTH_USER_MODEL)),
                ("paid_from_gl", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="supplier_advance_paid_from", to="pos.glmaster")),
                ("project", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="supplier_advances", to="pos.project")),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="advances", to="pos.supplier")),
            ],
            options={
                "ordering": ["-advance_date", "-id"],
            },
        ),
        migrations.CreateModel(
            name="SupplierSettlement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("settlement_no", models.CharField(blank=True, max_length=30, null=True, unique=True)),
                ("settlement_date", models.DateField(default=timezone.now)),
                ("description", models.CharField(max_length=255)),
                ("actual_amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("advance_applied", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("balance_due", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("excess_advance", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("approval_status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], default="pending", max_length=20)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("approval_note", models.TextField(blank=True, null=True)),
                ("note", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("advance", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="settlements", to="pos.supplieradvance")),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_supplier_settlements", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_supplier_settlements", to=settings.AUTH_USER_MODEL)),
                ("expense_gl", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="supplier_settlement_expense_gl", to="pos.glmaster")),
                ("linked_project_expense", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="supplier_settlements", to="pos.projectexpense")),
                ("project", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="supplier_settlements", to="pos.project")),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="settlements", to="pos.supplier")),
            ],
            options={
                "ordering": ["-settlement_date", "-id"],
            },
        ),
    ]