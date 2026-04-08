from decimal import Decimal
from django.db import models
from django.db.models import Sum
from django.contrib.auth.models import User
from django.utils import timezone


# =========================
# MASTER TABLES
# =========================
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Supplier(models.Model):
    name = models.CharField(max_length=150, unique=True)
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    contact_person = models.CharField(max_length=150, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class GLMaster(models.Model):
    GL_TYPE_CHOICES = [
        ("asset", "Asset"),
        ("liability", "Liability"),
        ("income", "Income"),
        ("expense", "Expense"),
        ("equity", "Equity"),
    ]

    gl_code = models.CharField(max_length=30, unique=True)
    gl_name = models.CharField(max_length=150)
    gl_type = models.CharField(max_length=20, choices=GL_TYPE_CHOICES)
    parent_group = models.CharField(max_length=150, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["gl_code"]

    def __str__(self):
        return f"{self.gl_code} - {self.gl_name}"


# =========================
# ITEMS / STOCK
# =========================
class Item(models.Model):
    ITEM_TYPE_CHOICES = [
        ("retail", "Retail"),
        ("project", "Project"),
        ("service", "Service"),
    ]

    item_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    unit = models.CharField(max_length=30, default="pcs")
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    purchase_date = models.DateField(blank=True, null=True)
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES, default="retail")
    is_service = models.BooleanField(default=False)

    allow_discount = models.BooleanField(default=True)
    max_discount_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    reorder_level = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    warranty_days = models.PositiveIntegerField(default=0)

    retail_gl_account = models.ForeignKey(
        GLMaster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retail_items"
    )
    cost_gl_account = models.ForeignKey(
        GLMaster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cost_items"
    )

    is_active = models.BooleanField(default=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_items"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.item_code} - {self.name}"

class StockTransaction(models.Model):
    TRANSACTION_TYPES = [
        ("sale", "Sale"),
        ("return_in", "Sales Return In"),
        ("project_issue", "Project Issue"),
        ("grn", "Goods Received"),
        ("adjustment_in", "Adjustment In"),
        ("adjustment_out", "Adjustment Out"),
    ]

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="stock_transactions")
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPES)
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.item.name} - {self.transaction_type} - {self.qty}"


# =========================
# POS SALES
# =========================
class Sale(models.Model):
    PAYMENT_METHODS = [
        ("cash", "Cash"),
        ("card", "Card"),
        ("credit", "Credit"),
    ]

    SALE_TYPE_CHOICES = [
        ("retail", "Retail Sale"),
        ("project_issue", "Project Issue"),
    ]

    APPROVAL_STATUS_CHOICES = [
        ("na", "Not Applicable"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    invoice_no = models.CharField(max_length=50, unique=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    sale_type = models.CharField(max_length=20, choices=SALE_TYPE_CHOICES, default="retail")
    project = models.ForeignKey(
        "Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pos_sales"
    )

    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default="na")
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_sales"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    is_posted_to_project_expense = models.BooleanField(default=False)
    approval_note = models.TextField(blank=True, null=True)

    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default="cash")
    received_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True, null=True)
    cheque_number = models.CharField(max_length=50, blank=True, null=True)

    customer_name = models.CharField(max_length=150, blank=True, null=True)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.invoice_no

    @property
    def recovered_amount(self):
        return self.recoveries.filter(is_active=True).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")

    @property
    def credit_balance(self):
        if self.payment_method != "credit":
            return Decimal("0")
        return Decimal(str(self.grand_total or 0)) - Decimal(str(self.recovered_amount or 0))

    @property
    def credit_status(self):
        if self.payment_method != "credit":
            return "na"

        recovered = Decimal(str(self.recovered_amount or 0))
        total = Decimal(str(self.grand_total or 0))

        if recovered <= 0:
            return "unpaid"
        elif recovered < total:
            return "partial"
        return "paid"


class SaleItem(models.Model):
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name="sale_items"
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT
    )

    qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.sale.invoice_no} - {self.item.name}"

class SaleRecovery(models.Model):
    PAYMENT_METHODS = [
        ("cash", "Cash"),
        ("card", "Card"),
        ("cheque", "Cheque"),
        ("bank", "Bank Transfer"),
        ("other", "Other"),
    ]

    receipt_no = models.CharField(max_length=50, unique=True, blank=True, null=True)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="recoveries")
    recovery_date = models.DateField(default=timezone.now)

    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default="cash")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    card_no = models.CharField(max_length=50, blank=True, null=True)
    cheque_no = models.CharField(max_length=50, blank=True, null=True)
    note = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    inactive_at = models.DateTimeField(blank=True, null=True)
    inactive_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inactive_sale_recoveries"
    )
    inactive_reason = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_sale_recoveries"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recovery_date", "-id"]

    def save(self, *args, **kwargs):
        if not self.receipt_no:
            last = SaleRecovery.objects.exclude(receipt_no__isnull=True).order_by("-id").first()
            if last and last.receipt_no and str(last.receipt_no).replace("RCV", "").isdigit():
                next_no = int(str(last.receipt_no).replace("RCV", "")) + 1
                self.receipt_no = f"RCV{next_no:06d}"
            else:
                self.receipt_no = "RCV000001"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.receipt_no or f"Recovery - {self.sale.invoice_no}"

class SalesReturn(models.Model):
    RETURN_TYPE_CHOICES = [
        ("refund", "Refund"),
        ("exchange", "Exchange"),
    ]

    return_no = models.CharField(max_length=50, unique=True)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="returns")
    sale_item = models.ForeignKey(SaleItem, on_delete=models.CASCADE, related_name="returns")
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    return_type = models.CharField(max_length=20, choices=RETURN_TYPE_CHOICES, default="refund")
    reason = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.return_no
# =========================
# PROJECTS
# =========================
class Project(models.Model):
    PROJECT_TYPE_CHOICES = [
        ("SW", "Swimming Pool"),
        ("BL", "Building"),
        ("EL", "Electrical"),
        ("OT", "Other"),
    ]

    STATUS_CHOICES = [
        ("ongoing", "Ongoing"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    project_id = models.CharField(max_length=30, unique=True)
    project_name = models.CharField(max_length=255)
    project_type = models.CharField(max_length=10, choices=PROJECT_TYPE_CHOICES)
    client_name = models.CharField(max_length=255, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    estimated_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ongoing")

    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_projects")
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="updated_projects")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"{self.project_id} - {self.project_name}"


class ProjectExpense(models.Model):
    EXPENSE_TYPE_CHOICES = [
        ("inventory", "Inventory Item"),
        ("direct", "Direct Item"),
        ("service", "Service"),
    ]

    expense_no = models.CharField(max_length=20, unique=True, blank=True, null=True)

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="expenses")
    expense_type = models.CharField(max_length=20, choices=EXPENSE_TYPE_CHOICES, default="direct")
    expense_date = models.DateField(default=timezone.now)

    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=255)

    qty = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True, blank=True)

    source_sale = models.ForeignKey(
        Sale,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_expense_rows"
    )

    is_active = models.BooleanField(default=True)
    inactive_at = models.DateTimeField(blank=True, null=True)
    inactive_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inactive_project_expenses"
    )
    inactive_reason = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-expense_date", "-id"]

    def __str__(self):
        return self.expense_no or f"{self.project.project_id} - {self.description}"


class ProjectIncome(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="incomes")
    income_date = models.DateField(default=timezone.now)
    description = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-income_date", "-id"]

    def __str__(self):
        return f"{self.project.project_id} - {self.amount}"


# =========================
# EMPLOYEES / PETTY CASH
# =========================
class Employee(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="employee_profile")
    emp_no = models.CharField(max_length=30, unique=True, blank=True, null=True)
    full_name = models.CharField(max_length=255)
    designation = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    tel = models.CharField(max_length=30, blank=True, null=True)
    petty_cash_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["emp_no", "full_name"]

    def save(self, *args, **kwargs):
        if not self.emp_no:
            last = Employee.objects.exclude(emp_no__isnull=True).order_by("-id").first()
            if last and last.emp_no and str(last.emp_no).replace("EMP", "").isdigit():
                next_no = int(str(last.emp_no).replace("EMP", "")) + 1
                self.emp_no = f"EMP{next_no:04d}"
            else:
                self.emp_no = "EMP0001"
        super().save(*args, **kwargs)

    @property
    def petty_cash_outstanding(self):
        total_issued = self.petty_cash_records.filter(is_active=True).aggregate(
            total=Sum("amount_issued")
        )["total"] or Decimal("0")

        total_spent = ProjectPettyCashExpense.objects.filter(
            petty_cash__employee=self,
            petty_cash__is_active=True,
            is_active=True,
            approval_status__in=["pending", "approved"]
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        return Decimal(str(total_issued)) - Decimal(str(total_spent))

    def __str__(self):
        return f"{self.emp_no} - {self.full_name}"


class ProjectPettyCash(models.Model):
    petty_cash_no = models.CharField(max_length=20, unique=True, blank=True, null=True)

    employee = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="petty_cash_records"
    )

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="petty_cash_users"
    )

    issue_date = models.DateField(default=timezone.now)
    amount_issued = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    inactive_at = models.DateTimeField(blank=True, null=True)
    inactive_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inactive_petty_cash_records"
    )
    inactive_reason = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_petty_cash_records"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issue_date", "-id"]

    def __str__(self):
        return self.petty_cash_no or f"Petty Cash {self.id}"

    @property
    def total_spent(self):
        return self.expenses.filter(
            is_active=True,
            approval_status__in=["pending", "approved"]
        ).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")

    @property
    def balance(self):
        return Decimal(str(self.amount_issued or 0)) - Decimal(str(self.total_spent or 0))


class ProjectPettyCashExpense(models.Model):
    APPROVAL_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    expense_no = models.CharField(max_length=20, unique=True, blank=True, null=True)
    petty_cash = models.ForeignKey(ProjectPettyCash, on_delete=models.CASCADE, related_name="expenses")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="petty_cash_expenses")
    expense_date = models.DateField(default=timezone.now)

    description = models.CharField(max_length=255)
    gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True, blank=True)

    bill_no = models.CharField(max_length=100, blank=True, null=True)
    bill_date = models.DateField(blank=True, null=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.TextField(blank=True, null=True)

    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default="pending")
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_petty_cash_expenses"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_note = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    inactive_at = models.DateTimeField(blank=True, null=True)
    inactive_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inactive_petty_cash_expenses"
    )
    inactive_reason = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-expense_date", "-id"]

    def __str__(self):
        return self.expense_no or f"{self.petty_cash.petty_cash_no} - {self.description}"


# =========================
# PROJECT INVOICES
# =========================
class ProjectInvoice(models.Model):
    INVOICE_TYPE_CHOICES = [
        ("advance", "Advance"),
        ("progress", "Progress"),
        ("final", "Final"),
        ("other", "Other"),
    ]

    invoice_no = models.CharField(max_length=50, unique=True, blank=True, null=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="invoices")
    invoice_date = models.DateField(default=timezone.now)

    bill_to_name = models.CharField(max_length=255, blank=True, null=True)
    bill_to_address = models.TextField(blank=True, null=True)

    invoice_type = models.CharField(max_length=20, choices=INVOICE_TYPE_CHOICES, default="advance")

    description = models.CharField(max_length=255, blank=True, null=True)
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    price_each = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    note = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    inactive_at = models.DateTimeField(blank=True, null=True)
    inactive_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inactive_project_invoices"
    )
    inactive_reason = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-invoice_date", "-id"]

    def save(self, *args, **kwargs):
        if not self.invoice_no:
            last = ProjectInvoice.objects.exclude(invoice_no__isnull=True).order_by("-id").first()
            if last and last.invoice_no and str(last.invoice_no).replace("PINV", "").isdigit():
                next_no = int(str(last.invoice_no).replace("PINV", "")) + 1
                self.invoice_no = f"PINV{next_no:06d}"
            else:
                self.invoice_no = "PINV000001"
        super().save(*args, **kwargs)

    @property
    def paid_amount(self):
        return self.payments.filter(is_active=True).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")

    @property
    def balance_amount(self):
        return Decimal(str(self.total_amount or 0)) - Decimal(str(self.paid_amount or 0))

    @property
    def payment_status(self):
        paid = Decimal(str(self.paid_amount or 0))
        total = Decimal(str(self.total_amount or 0))
        if paid <= 0:
            return "unpaid"
        elif paid < total:
            return "partial"
        return "paid"

    def __str__(self):
        return self.invoice_no


class ProjectInvoiceItem(models.Model):
    invoice = models.ForeignKey(ProjectInvoice, on_delete=models.CASCADE, related_name="items")
    item_code = models.CharField(max_length=50, blank=True, null=True)
    description = models.CharField(max_length=255)
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    price_each = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["id"]

    def save(self, *args, **kwargs):
        self.amount = Decimal(str(self.qty or 0)) * Decimal(str(self.price_each or 0))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice.invoice_no} - {self.description}"
class ProjectInvoicePayment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("card", "Card"),
        ("cheque", "Cheque"),
        ("bank", "Bank Transfer"),
    ]

    PAYMENT_TYPE_CHOICES = [
        ("advance", "Advance"),
        ("settlement", "Settlement"),
        ("other", "Other"),
    ]

    receipt_no = models.CharField(max_length=50, unique=True, blank=True, null=True)
    invoice = models.ForeignKey(ProjectInvoice, on_delete=models.CASCADE, related_name="payments")
    payment_date = models.DateField(default=timezone.now)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default="advance")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default="cash")

    card_no = models.CharField(max_length=50, blank=True, null=True)
    cheque_no = models.CharField(max_length=50, blank=True, null=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    inactive_at = models.DateTimeField(blank=True, null=True)
    inactive_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inactive_project_invoice_payments"
    )
    inactive_reason = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-id"]

    def save(self, *args, **kwargs):
        if not self.receipt_no:
            last = ProjectInvoicePayment.objects.exclude(receipt_no__isnull=True).order_by("-id").first()
            if last and last.receipt_no and str(last.receipt_no).replace("PRC", "").isdigit():
                next_no = int(str(last.receipt_no).replace("PRC", "")) + 1
                self.receipt_no = f"PRC{next_no:06d}"
            else:
                self.receipt_no = "PRC000001"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.receipt_no
