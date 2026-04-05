from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Supplier(models.Model):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class GLMaster(models.Model):
    GL_TYPE_CHOICES = [
        ("asset", "Asset"),
        ("liability", "Liability"),
        ("equity", "Equity"),
        ("income", "Income"),
        ("expense", "Expense"),
    ]

    gl_code = models.CharField(max_length=50, unique=True)
    gl_name = models.CharField(max_length=200)
    gl_type = models.CharField(max_length=20, choices=GL_TYPE_CHOICES)
    parent_group = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["gl_code"]

    def __str__(self):
        return f"{self.gl_code} - {self.gl_name}"


class Item(models.Model):
    ITEM_TYPE_CHOICES = [
        ("retail", "Retail"),
        ("project", "Project"),
        ("both", "Both"),
        ("expense", "Expense"),
    ]

    item_code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)

    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)

    unit = models.CharField(max_length=20, default="pcs")
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    purchase_date = models.DateField(blank=True, null=True)
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES, default="retail")
    is_service = models.BooleanField(default=False)
    reorder_level = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    warranty_days = models.IntegerField(default=0)

    retail_gl_account = models.ForeignKey(
        GLMaster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retail_items",
    )
    cost_gl_account = models.ForeignKey(
        GLMaster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cost_items",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_items"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class StockTransaction(models.Model):
    TRANSACTION_TYPES = [
        ("opening", "Opening Stock"),
        ("purchase", "Purchase"),
        ("sale", "Sale"),
        ("adjust_plus", "Adjustment +"),
        ("adjust_minus", "Adjustment -"),
        ("project_issue", "Project Issue"),
        ("return_in", "Return In"),
    ]

    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.item.name} - {self.transaction_type}"


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
    project = models.ForeignKey("Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="pos_sales")

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

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="sale_items")
    item = models.ForeignKey(Item, on_delete=models.CASCADE)

    qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return self.item.name


class SalesReturn(models.Model):
    RETURN_TYPE_CHOICES = [
        ("refund", "Refund"),
        ("replace", "Replace"),
        ("repair", "Repair"),
    ]

    return_no = models.CharField(max_length=50, unique=True, null=True, blank=True)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, null=True, blank=True)
    sale_item = models.ForeignKey(SaleItem, on_delete=models.CASCADE, null=True, blank=True)
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    return_type = models.CharField(max_length=20, choices=RETURN_TYPE_CHOICES, default="refund")
    reason = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.return_no or "Return"


class Project(models.Model):
    PROJECT_TYPE_CHOICES = [
        ("BL", "Building"),
        ("SW", "Swimming Pool"),
        ("RS", "Retail Shop"),
    ]

    project_id = models.CharField(max_length=50, unique=True)
    project_name = models.CharField(max_length=200)
    project_type = models.CharField(max_length=10, choices=PROJECT_TYPE_CHOICES)

    client_name = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True, null=True)

    estimated_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, default="active")

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_projects"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.project_id

    @property
    def total_expense(self):
        direct = self.expenses.filter(is_active=True).aggregate(total=models.Sum("amount"))["total"] or Decimal("0")
        petty = ProjectPettyCashExpense.objects.filter(project=self, is_active=True).aggregate(total=models.Sum("amount"))["total"] or Decimal("0")
        return Decimal(direct) + Decimal(petty)

    @property
    def total_income(self):
        total = self.incomes.aggregate(total=models.Sum("amount"))["total"] or Decimal("0")
        return Decimal(total)

    @property
    def profit(self):
        return self.total_income - self.total_expense


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
        "Sale",
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
    
class Employee(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_profile"
    )
    emp_no = models.CharField(max_length=20, unique=True, blank=True, null=True)
    full_name = models.CharField(max_length=150)
    designation = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    tel = models.CharField(max_length=20, blank=True, null=True)
    petty_cash_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["emp_no"]

    def __str__(self):
        return f"{self.emp_no} - {self.full_name}"

    def save(self, *args, **kwargs):
        if not self.emp_no:
            last = Employee.objects.exclude(emp_no__isnull=True).order_by("-id").first()
            if last and last.emp_no and last.emp_no.startswith("EMP"):
                try:
                    last_no = int(last.emp_no.replace("EMP", ""))
                    self.emp_no = f"EMP{last_no + 1:06d}"
                except ValueError:
                    self.emp_no = "EMP000001"
            else:
                self.emp_no = "EMP000001"
        super().save(*args, **kwargs)

    @property
    def petty_cash_outstanding(self):
        issued = self.petty_cashes.filter(is_active=True).aggregate(total=models.Sum("amount_issued"))["total"] or Decimal("0")
        spent = ProjectPettyCashExpense.objects.filter(
            petty_cash__employee=self,
            is_active=True
        ).aggregate(total=models.Sum("amount"))["total"] or Decimal("0")
        return Decimal(issued) - Decimal(spent)

    @property
    def available_petty_cash_limit(self):
        return Decimal(self.petty_cash_limit) - Decimal(self.petty_cash_outstanding)


class ProjectPettyCash(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="petty_cash_received")

    employee = models.ForeignKey(
        "Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="petty_cashes"
    )

    petty_cash_no = models.CharField(max_length=50, unique=True)
    issue_date = models.DateField(default=timezone.now)
    amount_issued = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="petty_cash_created")
    created_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)
    inactive_at = models.DateTimeField(null=True, blank=True)
    inactive_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inactive_petty_cash_records"
    )
    inactive_reason = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issue_date", "-id"]

    def __str__(self):
        return self.petty_cash_no

    @property
    def total_spent(self):
        total = self.expenses.filter(is_active=True).aggregate(total=models.Sum("amount"))["total"]
        return Decimal(total or 0)

    @property
    def balance(self):
        return Decimal(self.amount_issued or 0) - Decimal(self.total_spent or 0)


class ProjectPettyCashExpense(models.Model):
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

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)
    inactive_at = models.DateTimeField(null=True, blank=True)
    inactive_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inactive_petty_cash_expenses"
    )
    inactive_reason = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-expense_date", "-id"]

    def __str__(self):
        return self.expense_no or f"{self.petty_cash.petty_cash_no} - {self.description}"


class ProjectIncome(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="incomes")
    income_date = models.DateField(default=timezone.now)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-income_date", "-id"]

    def __str__(self):
        return f"{self.project.project_id} - {self.amount}"


class ProjectInvoice(models.Model):
    INVOICE_TYPE_CHOICES = [
        ("advance", "Advance"),
        ("installment", "Installment"),
        ("final", "Final Payment"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("unpaid", "Unpaid"),
        ("partial", "Partial"),
        ("paid", "Paid"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="project_invoices")

    invoice_no = models.CharField(max_length=50, unique=True, blank=True, null=True)
    invoice_date = models.DateField(default=timezone.now)

    bill_to_name = models.CharField(max_length=200, blank=True, null=True)
    bill_to_address = models.TextField(blank=True, null=True)

    invoice_type = models.CharField(max_length=20, choices=INVOICE_TYPE_CHOICES, default="advance")
    description = models.CharField(max_length=255)

    qty = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    item_code = models.CharField(max_length=50, blank=True, null=True)
    price_each = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="unpaid")

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

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_project_invoices"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-invoice_date", "-id"]

    def __str__(self):
        return self.invoice_no or f"{self.project.project_id} - {self.description}"

    def save(self, *args, **kwargs):
        if not self.invoice_no:
            last = ProjectInvoice.objects.exclude(invoice_no__isnull=True).order_by("-id").first()
            if last and last.invoice_no and str(last.invoice_no).replace("PINV", "").isdigit():
                next_no = int(str(last.invoice_no).replace("PINV", "")) + 1
                self.invoice_no = f"PINV{next_no:06d}"
            else:
                self.invoice_no = "PINV000001"

        if not self.total_amount or self.total_amount == 0:
            self.total_amount = Decimal(self.qty or 0) * Decimal(self.price_each or 0)

        paid_total = Decimal("0")
        if self.pk:
            paid_total = self.payments.filter(is_active=True).aggregate(
                total=models.Sum("amount")
            )["total"] or Decimal("0")

        self.paid_amount = Decimal(paid_total)
        self.balance_amount = Decimal(self.total_amount or 0) - Decimal(paid_total)

        if paid_total <= 0:
            self.status = "unpaid"
        elif Decimal(paid_total) < Decimal(self.total_amount or 0):
            self.status = "partial"
        else:
            self.status = "paid"
            self.balance_amount = Decimal("0")

        super().save(*args, **kwargs)
        
class ProjectInvoiceItem(models.Model):
    invoice = models.ForeignKey(ProjectInvoice, on_delete=models.CASCADE, related_name="items")
    item_code = models.CharField(max_length=50, blank=True, null=True)
    description = models.CharField(max_length=255)
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    price_each = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.invoice.invoice_no} - {self.description}"

    def save(self, *args, **kwargs):
        self.amount = Decimal(str(self.qty or 0)) * Decimal(str(self.price_each or 0))
        super().save(*args, **kwargs)    

class ProjectInvoicePayment(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ("advance", "Advance"),
        ("installment", "Installment"),
        ("final", "Final Payment"),
        ("other", "Other"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("card", "Card"),
        ("cheque", "Cheque"),
    ]

    invoice = models.ForeignKey(ProjectInvoice, on_delete=models.CASCADE, related_name="payments")
    receipt_no = models.CharField(max_length=50, unique=True, blank=True, null=True)
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

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_project_invoice_payments")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-id"]

    def __str__(self):
        return self.receipt_no or f"{self.invoice.invoice_no} - {self.amount}"

    def save(self, *args, **kwargs):
        if not self.receipt_no:
            last = ProjectInvoicePayment.objects.exclude(receipt_no__isnull=True).order_by("-id").first()
            if last and last.receipt_no and str(last.receipt_no).replace("PREC", "").isdigit():
                next_no = int(str(last.receipt_no).replace("PREC", "")) + 1
                self.receipt_no = f"PREC{next_no:06d}"
            else:
                self.receipt_no = "PREC000001"

        super().save(*args, **kwargs)
        self.invoice.save()