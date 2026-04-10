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
            name="PurchaseOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("po_no", models.CharField(blank=True, max_length=30, null=True, unique=True)),
                ("po_date", models.DateField(default=timezone.now)),
                ("order_type", models.CharField(
                    choices=[("item", "Item"), ("service", "Service"), ("rental", "Rental"), ("other", "Other")],
                    default="service",
                    max_length=20
                )),
                ("description", models.CharField(max_length=255)),
                ("qty", models.DecimalField(decimal_places=2, default=1, max_digits=12)),
                ("rate", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("estimated_amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("status", models.CharField(
                    choices=[("draft", "Draft"), ("approved", "Approved"), ("partially_used", "Partially Used"), ("closed", "Closed")],
                    default="draft",
                    max_length=20
                )),
                ("note", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="created_purchase_orders",
                    to=settings.AUTH_USER_MODEL
                )),
                ("project", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="purchase_orders",
                    to="pos.project"
                )),
                ("supplier", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="purchase_orders",
                    to="pos.supplier"
                )),
            ],
            options={
                "ordering": ["-po_date", "-id"],
            },
        ),
    ]