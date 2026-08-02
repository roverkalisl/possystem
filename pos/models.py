from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q, Sum
from django.contrib.auth.models import User
from django.utils import timezone


# =========================
# PAYROLL STATUTORY RATES (Sri Lanka)
# =========================
# EPF: employee contributes 8% of gross (deducted from salary),
# employer contributes 12%. ETF: employer contributes 3% (not deducted
# from the employee). Rates are kept here so a single edit updates payroll.
EPF_EMPLOYEE_RATE = Decimal("0.08")
EPF_EMPLOYER_RATE = Decimal("0.12")
ETF_EMPLOYER_RATE = Decimal("0.03")

# Used to derive a daily/hourly rate for monthly-salary employees (who have
# no daily_rate set) so their OT hours can still be priced.
STANDARD_MONTHLY_WORKING_DAYS = Decimal("30")

# Auto-generated payroll deductions (EPF, No Pay, Salary Advance, Safety Supply)
# carry this tag in their description so they can be rebuilt without disturbing
# manually-added deductions (Loan, Other).
AUTO_DEDUCTION_TAG = "[AUTO]"


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

    phone_1 = models.CharField(max_length=30, blank=True, null=True)
    phone_2 = models.CharField(max_length=30, blank=True, null=True)
    phone_3 = models.CharField(max_length=30, blank=True, null=True)

    email = models.EmailField(blank=True, null=True)
    contact_person = models.CharField(max_length=150, blank=True, null=True)

    bank_name = models.CharField(max_length=150, blank=True, null=True)
    bank_branch = models.CharField(max_length=150, blank=True, null=True)
    account_name = models.CharField(max_length=150, blank=True, null=True)
    account_number = models.CharField(max_length=80, blank=True, null=True)

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


class GLCreationLog(models.Model):
    """Log for automatically created GL accounts via imports."""
    gl = models.ForeignKey(GLMaster, on_delete=models.CASCADE, related_name='creation_logs')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("cancelled", "Cancelled"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="approved")
    source = models.CharField(max_length=200, blank=True, null=True)
    note = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        user = self.created_by.username if self.created_by else 'system'
        return f"GL {self.gl.gl_code} created by {user} at {self.created_at:%Y-%m-%d %H:%M}"


class LicenseRenewal(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("expired", "Expired"),
        ("closed", "Closed"),
    ]

    CATEGORY_CHOICES = [
        ("business_registration", "Business Registration"),
        ("trade_license", "Trade License"),
        ("vehicle_revenue_license", "Vehicle Revenue License"),
        ("vehicle_insurance", "Vehicle Insurance"),
        ("environmental_permit", "Environmental Permit"),
        ("contractor_registration", "Contractor Registration"),
        ("tax_registration", "Tax Registration"),
        ("epf_etf_registrations", "EPF / ETF Registrations"),
        ("company_certifications", "Company Certifications"),
        ("other_licenses", "Other Licenses"),
    ]

    description = models.CharField(max_length=255)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    current_renewal_date = models.DateField()
    expire_date = models.DateField()
    next_renewal_date = models.DateField()
    responsible_person = models.ForeignKey(
        "Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="license_renewals"
    )
    remarks = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["next_renewal_date", "expire_date", "description"]

    def __str__(self):
        return self.description

    def save(self, *args, **kwargs):
        if self.status != "closed" and self.expire_date and timezone.localdate() > self.expire_date:
            self.status = "expired"
        super().save(*args, **kwargs)

    @property
    def days_remaining(self):
        if not self.next_renewal_date:
            return None
        return (self.next_renewal_date - timezone.localdate()).days

    @property
    def effective_status(self):
        if self.status == "closed":
            return "closed"
        if self.expire_date and timezone.localdate() > self.expire_date:
            return "expired"
        return "active"


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
        "Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    supplier = models.ForeignKey(
        "Supplier",
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
        "GLMaster",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retail_items"
    )
    cost_gl_account = models.ForeignKey(
        "GLMaster",
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

    REFERENCE_TYPES = [
        ("sale", "Sale Invoice"),
        ("return", "Sales Return"),
        ("po", "Purchase Order"),
        ("manual", "Manual Entry"),
        ("project", "Project Issue"),
    ]

    item = models.ForeignKey(
        "Item",
        on_delete=models.CASCADE,
        related_name="stock_transactions"
    )
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPES)
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    reference_type = models.CharField(max_length=20, choices=REFERENCE_TYPES, blank=True, null=True)
    reference_no = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_transactions"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        ref = f" - {self.reference_no}" if self.reference_no else ""
        return f"{self.item.name} - {self.transaction_type}{ref} - {self.qty}"

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
    customer = models.ForeignKey(
        "Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales"
    )

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
    def returned_amount(self):
        total = Decimal("0")
        for sale_return in self.returns.select_related("sale_item").all():
            qty = Decimal(str(sale_return.qty or 0))
            price = Decimal(str(sale_return.sale_item.price or 0))
            total += qty * price
        return total

    @property
    def credit_balance(self):
        if self.payment_method != "credit":
            return Decimal("0")

        total = Decimal(str(self.grand_total or 0))
        returned = Decimal(str(self.returned_amount or 0))
        recovered = Decimal(str(self.recovered_amount or 0))
        balance = total - returned - recovered
        return balance if balance > 0 else Decimal("0")

    @property
    def credit_status(self):
        if self.payment_method != "credit":
            return "na"

        total = Decimal(str(self.grand_total or 0))
        returned = Decimal(str(self.returned_amount or 0))
        effective_total = total - returned

        if effective_total <= 0:
            return "paid"

        recovered = Decimal(str(self.recovered_amount or 0))
        if recovered <= 0:
            return "unpaid"
        elif recovered < effective_total:
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


class Quotation(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("converted", "Converted"),
    ]

    quotation_no = models.CharField(max_length=50, unique=True, blank=True, null=True)
    date = models.DateField(default=timezone.now)
    valid_until = models.DateField(blank=True, null=True)

    customer_name = models.CharField(max_length=255, blank=True, null=True)
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def save(self, *args, **kwargs):
        if not self.quotation_no:
            last = Quotation.objects.exclude(quotation_no__isnull=True).order_by("-id").first()
            if last and last.quotation_no and str(last.quotation_no).replace("QT", "").isdigit():
                next_no = int(str(last.quotation_no).replace("QT", "")) + 1
                self.quotation_no = f"QT{next_no:06d}"
            else:
                self.quotation_no = "QT000001"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.quotation_no or f"Quotation {self.id}"

    @property
    def sub_total(self):
        total = self.items.aggregate(total=Sum("line_total"))["total"] or Decimal("0")
        return Decimal(str(total))

    @property
    def discount_total(self):
        total = self.items.aggregate(total=Sum("discount"))["total"] or Decimal("0")
        return Decimal(str(total))

    @property
    def grand_total(self):
        return max(Decimal("0"), self.sub_total - self.discount_total)


class QuotationItem(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)

    item_code = models.CharField(max_length=80, blank=True, null=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit = models.CharField(max_length=30, blank=True, null=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ["id"]

    def save(self, *args, **kwargs):
        # populate item fields for consistency
        if self.item:
            if not self.item_code:
                self.item_code = self.item.item_code
            if not self.description:
                self.description = self.item.name
            if not self.unit:
                self.unit = self.item.unit
            # default price to item's selling_price unless overridden
            if not self.unit_price or Decimal(str(self.unit_price)) == Decimal("0"):
                self.unit_price = self.item.selling_price

        qty = Decimal(str(self.qty or 0))
        price = Decimal(str(self.unit_price or 0))
        disc = Decimal(str(self.discount or 0))
        self.line_total = max(Decimal("0"), qty * price - disc)
        super().save(*args, **kwargs)

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
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("cancelled", "Cancelled"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="approved")

    class Meta:
        ordering = ["-created_at", "-id"]

    @property
    def return_invoice_id(self):
        return self.sale.invoice_no if self.sale else ""

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

    default_labour_gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name="projects_using_as_labour_gl")
    default_cost_gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name="projects_using_as_cost_gl")
    default_supervisor = models.ForeignKey("Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="supervised_projects")

    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_projects")
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="updated_projects")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"{self.project_id} - {self.project_name}"


class SalaryAdvance(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    employee = models.ForeignKey("Employee", on_delete=models.CASCADE, related_name="salary_advances")
    advance_date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    reason = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    deduction_month = models.DateField(blank=True, null=True)
    deducted_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_salary_advances")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-advance_date", "-id"]

    @property
    def remaining_balance(self):
        return Decimal(str(self.amount or 0)) - Decimal(str(self.deducted_amount or 0))

    def __str__(self):
        return f"Advance {self.id} - {self.employee}"


class PayrollSettings(models.Model):
    """Company-wide default GL accounts for payroll (Salary Payable, Bank/Cash,
    EPF, ETF). Singleton — only one row is meant to exist; managed via admin
    (Owner/staff-only) since these are administrator-level defaults."""

    default_salary_payable_gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    default_bank_gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    default_epf_expense_gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    default_epf_payable_gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    default_etf_expense_gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    default_etf_payable_gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Payroll Settings"
        verbose_name_plural = "Payroll Settings"

    @classmethod
    def get_solo(cls):
        obj = cls.objects.first()
        if obj is None:
            obj = cls.objects.create()
        return obj

    def __str__(self):
        return "Payroll Settings"


class PayrollEntry(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("paid", "Paid"),
        ("rejected", "Rejected"),
    ]
    SALARY_PERIOD_CHOICES = [
        ("monthly", "Monthly"),
        ("weekly", "Weekly"),
    ]

    employee = models.ForeignKey("Employee", on_delete=models.CASCADE, related_name="payroll_entries")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="payroll_entries")
    supervisor = models.ForeignKey("Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="supervised_payroll_entries")
    department = models.CharField(max_length=100, blank=True, null=True)
    employee_category = models.CharField(max_length=100, blank=True, null=True)
    designation = models.CharField(max_length=100, blank=True, null=True)
    salary_period = models.CharField(max_length=20, choices=SALARY_PERIOD_CHOICES, default="monthly")
    salary_month = models.DateField(blank=True, null=True)
    basic_salary = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    working_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    present_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    leave_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    no_pay_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    holiday_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    ot_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    ot_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gross_salary = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=10, choices=[("cash", "Cash"), ("bank", "Bank")], default="bank")
    labour_gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name="payroll_labour_entries")
    salary_payable_gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name="payroll_payable_entries")
    bank_gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name="payroll_bank_entries")
    epf_expense_gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name="payroll_epf_expense_entries")
    epf_payable_gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name="payroll_epf_payable_entries")
    etf_expense_gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name="payroll_etf_expense_entries")
    etf_payable_gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name="payroll_etf_payable_entries")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    description = models.TextField(blank=True, null=True)
    payslip_no = models.CharField(max_length=30, blank=True, null=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_payroll_entries")
    approval_date = models.DateTimeField(blank=True, null=True)
    paid_on = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_payroll_entries")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def save(self, *args, **kwargs):
        if self.status == "approved" and not self.payslip_no:
            self.ensure_payslip_no()
        super().save(*args, **kwargs)

    def ensure_payslip_no(self):
        if self.payslip_no:
            return self.payslip_no

        today = timezone.now()
        prefix = f"PS-{today.strftime('%Y')}-{today.strftime('%m')}-"
        last = PayrollEntry.objects.exclude(payslip_no__isnull=True).filter(payslip_no__startswith=prefix).order_by("-id").first()
        if last and last.payslip_no:
            try:
                sequence = int(str(last.payslip_no).split("-")[-1])
                self.payslip_no = f"{prefix}{sequence + 1:05d}"
            except ValueError:
                self.payslip_no = f"{prefix}00001"
        else:
            self.payslip_no = f"{prefix}00001"
        return self.payslip_no

    def __str__(self):
        return f"Payroll {self.id} - {self.employee}"

    def clean(self):
        super().clean()
        if self.project is None and not self.allocations.exists():
            raise ValidationError({"project": "A project must be selected before payroll can be approved."})

    def approve(self, approved_by):
        if not self.project and not self.allocations.exists():
            raise ValidationError("A project must be selected before payroll can be approved.")

        if self.status == "approved":
            return self

        # Self-healing: make sure gross/auto-deductions reflect the final state
        # (e.g. allowances added after the last Process run) before locking in.
        self.recompute_gross()
        self.rebuild_auto_deductions()

        self.ensure_payslip_no()

        total_allocated = self.allocations.aggregate(total=models.Sum("amount"))["total"] or Decimal("0")
        if self.allocations.exists() and Decimal(str(total_allocated)) != Decimal(str(self.gross_salary)):
            raise ValidationError("Payroll allocations must total the gross salary amount.")

        with transaction.atomic():
            self.status = "approved"
            self.approved_by = approved_by
            self.approval_date = timezone.now()
            self.save(update_fields=["status", "approved_by", "approval_date", "payslip_no", "updated_at"])

            self.project_cost_entries.all().delete()
            self.gl_entries.all().delete()

            if not self.allocations.exists() and self.project:
                PayrollAllocation.objects.create(payroll_entry=self, project=self.project, amount=self.gross_salary)

            for allocation in self.allocations.select_related("project").all():
                if allocation.project and allocation.amount:
                    PayrollProjectCostEntry.objects.create(
                        payroll_entry=self,
                        project=allocation.project,
                        amount=allocation.amount,
                        gl_account=allocation.project.default_cost_gl_account or self.labour_gl_account,
                        description=f"Payroll labour cost for {self.employee.full_name}",
                    )

            if self.labour_gl_account and self.salary_payable_gl_account:
                PayrollGLEntry.objects.create(
                    payroll_entry=self,
                    entry_type="approval",
                    gl_account=self.labour_gl_account,
                    direction="debit",
                    amount=self.gross_salary,
                    description="Payroll labour cost approved",
                )
                PayrollGLEntry.objects.create(
                    payroll_entry=self,
                    entry_type="approval",
                    gl_account=self.salary_payable_gl_account,
                    direction="credit",
                    amount=self.gross_salary,
                    description="Payroll salary payable created",
                )

            self._post_employee_epf_gl()
            self._post_employer_statutory_gl()
            self._apply_deduction_balances()

        return self

    def _post_employee_epf_gl(self):
        """Post the employee's own EPF 8% deduction: Debit Salary Payable / Credit EPF Payable."""
        if not (self.epf_payable_gl_account and self.salary_payable_gl_account):
            return

        amount = self.epf_amount
        if amount <= 0:
            return

        PayrollGLEntry.objects.create(
            payroll_entry=self,
            entry_type="approval",
            gl_account=self.salary_payable_gl_account,
            direction="debit",
            amount=amount,
            description="Employee EPF 8% deduction",
        )
        PayrollGLEntry.objects.create(
            payroll_entry=self,
            entry_type="approval",
            gl_account=self.epf_payable_gl_account,
            direction="credit",
            amount=amount,
            description="Employee EPF payable created",
        )

    def _post_employer_statutory_gl(self):
        """Post employer EPF (12%) and ETF (3%) as debit expense / credit payable."""
        if not (self.employee and self.employee.epf_etf_applicable):
            return

        gross = Decimal(str(self.gross_salary or 0))
        statutory = [
            (EPF_EMPLOYER_RATE, self.epf_expense_gl_account, self.epf_payable_gl_account, "Employer EPF"),
            (ETF_EMPLOYER_RATE, self.etf_expense_gl_account, self.etf_payable_gl_account, "Employer ETF"),
        ]
        for rate, expense_gl, payable_gl, label in statutory:
            if not (expense_gl and payable_gl):
                continue
            amount = (gross * rate).quantize(Decimal("0.01"))
            if amount <= 0:
                continue
            PayrollGLEntry.objects.create(
                payroll_entry=self,
                entry_type="approval",
                gl_account=expense_gl,
                direction="debit",
                amount=amount,
                description=f"{label} contribution expense",
            )
            PayrollGLEntry.objects.create(
                payroll_entry=self,
                entry_type="approval",
                gl_account=payable_gl,
                direction="credit",
                amount=amount,
                description=f"{label} payable created",
            )

    def _apply_deduction_balances(self):
        """Update salary-advance balances and safety-item status for deductions on this month."""
        if not (self.employee and self.salary_month):
            return

        month = self.salary_month
        advances = SalaryAdvance.objects.filter(
            employee=self.employee,
            status="approved",
            deduction_month__year=month.year,
            deduction_month__month=month.month,
        )
        for advance in advances:
            remaining = advance.remaining_balance
            if remaining > 0:
                advance.deducted_amount = Decimal(str(advance.deducted_amount or 0)) + remaining
                advance.save(update_fields=["deducted_amount", "updated_at"])

        SafetyItemIssue.objects.filter(
            employee=self.employee,
            deduct_from_salary=True,
            status="pending",
            deduction_month__year=month.year,
            deduction_month__month=month.month,
        ).update(status="deducted")

    def pay(self, paid_by=None):
        if self.status != "approved":
            raise ValidationError("Only approved payroll can be paid.")
        if not self.bank_gl_account:
            raise ValidationError("A bank or cash GL account is required to pay salary.")

        with transaction.atomic():
            self.status = "paid"
            self.paid_on = timezone.now()
            self.save(update_fields=["status", "paid_on", "updated_at"])

            PayrollGLEntry.objects.create(
                payroll_entry=self,
                entry_type="payment",
                gl_account=self.salary_payable_gl_account,
                direction="debit",
                amount=self.net_salary,
                description="Salary payable settled",
            )
            PayrollGLEntry.objects.create(
                payroll_entry=self,
                entry_type="payment",
                gl_account=self.bank_gl_account,
                direction="credit",
                amount=self.net_salary,
                description="Salary paid to employee",
            )

        return self

    @property
    def is_printable(self):
        return self.status in {"approved", "paid"}

    @property
    def total_allowances(self):
        return self.allowances.aggregate(total=models.Sum("amount"))["total"] or Decimal("0")

    @property
    def total_deductions(self):
        return self.deductions.aggregate(total=models.Sum("amount"))["total"] or Decimal("0")

    @property
    def ot_amount(self):
        return (Decimal(str(self.ot_hours or 0)) * Decimal(str(self.ot_rate or 0))).quantize(Decimal("0.01"))

    @property
    def salary_advance_deduction(self):
        return self._deduction_total("salary", "advance")

    @property
    def loan_deduction(self):
        return self._deduction_total("loan")

    @property
    def no_pay_deduction(self):
        return self._deduction_total("no pay")

    @property
    def epf_amount(self):
        return self._deduction_total("epf")

    @property
    def employer_epf_amount(self):
        if not (self.employee and self.employee.epf_etf_applicable):
            return Decimal("0")
        return (Decimal(str(self.gross_salary or 0)) * EPF_EMPLOYER_RATE).quantize(Decimal("0.01"))

    @property
    def employer_etf_amount(self):
        if not (self.employee and self.employee.epf_etf_applicable):
            return Decimal("0")
        return (Decimal(str(self.gross_salary or 0)) * ETF_EMPLOYER_RATE).quantize(Decimal("0.01"))

    @property
    def other_deductions(self):
        return (
            self.total_deductions
            - self.salary_advance_deduction
            - self.loan_deduction
            - self.no_pay_deduction
            - self.epf_amount
        )

    def _deduction_total(self, *keywords):
        query = Q()
        for keyword in keywords:
            query |= Q(deduction_type__icontains=keyword)
        return self.deductions.filter(query).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    @property
    def net_salary(self):
        return Decimal(str(self.gross_salary or 0)) - Decimal(str(self.total_deductions or 0))

    def recompute_gross(self):
        """gross_salary = Basic + OT + Allowances (Total/Gross Earnings). Saves the field."""
        self.gross_salary = (
            Decimal(str(self.basic_salary or 0))
            + self.ot_amount
            + Decimal(str(self.total_allowances or 0))
        ).quantize(Decimal("0.01"))
        self.save()
        return self.gross_salary

    def rebuild_auto_deductions(self):
        """Rebuild [AUTO]-tagged deductions (EPF, No Pay, Salary Advance, Safety Supply)
        from compute_payroll_preview() — the single formula authority — leaving any
        manually-added deductions (Loan, Other) untouched."""
        if not (self.employee and self.salary_month):
            return

        preview = compute_payroll_preview(self.employee, self.project, self.salary_month, payroll_entry=self)

        self.deductions.filter(description__startswith=AUTO_DEDUCTION_TAG).delete()

        if preview["epf_employee"] > 0:
            PayrollDeduction.objects.create(
                payroll_entry=self,
                deduction_type="EPF",
                amount=preview["epf_employee"],
                description=f"{AUTO_DEDUCTION_TAG} Employee EPF 8%",
            )

        if preview["no_pay_deduction"] > 0:
            PayrollDeduction.objects.create(
                payroll_entry=self,
                deduction_type="No Pay Deduction",
                amount=preview["no_pay_deduction"],
                description=f"{AUTO_DEDUCTION_TAG} {preview['no_pay_days']} no-pay day(s)",
            )

        for item in preview["salary_advance_items"]:
            PayrollDeduction.objects.create(
                payroll_entry=self,
                deduction_type="Salary Advance",
                amount=item["amount"],
                description=f"{AUTO_DEDUCTION_TAG} Salary advance #{item['id']}",
            )

        for item in preview["safety_supply_items"]:
            PayrollDeduction.objects.create(
                payroll_entry=self,
                deduction_type="Safety Supply",
                amount=item["amount"],
                description=f"{AUTO_DEDUCTION_TAG} {item['name']}",
            )


class PayrollAllowance(models.Model):
    payroll_entry = models.ForeignKey(PayrollEntry, on_delete=models.CASCADE, related_name="allowances")
    allowance_name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    description = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]


class PayrollDeduction(models.Model):
    payroll_entry = models.ForeignKey(PayrollEntry, on_delete=models.CASCADE, related_name="deductions")
    deduction_type = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    description = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]


class PayrollAllocation(models.Model):
    payroll_entry = models.ForeignKey(PayrollEntry, on_delete=models.CASCADE, related_name="allocations")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="payroll_allocations")
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    description = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.project} - {self.amount}"


class PayrollProjectCostEntry(models.Model):
    payroll_entry = models.ForeignKey(PayrollEntry, on_delete=models.CASCADE, related_name="project_cost_entries")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="payroll_cost_entries")
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name="payroll_cost_entries")
    description = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.project} - {self.amount}"


class PayrollGLEntry(models.Model):
    ENTRY_TYPE_CHOICES = [
        ("approval", "Approval"),
        ("payment", "Payment"),
    ]
    DIRECTION_CHOICES = [
        ("debit", "Debit"),
        ("credit", "Credit"),
    ]

    payroll_entry = models.ForeignKey(PayrollEntry, on_delete=models.CASCADE, related_name="gl_entries")
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPE_CHOICES, default="approval")
    gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name="payroll_gl_entries")
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    description = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.direction.upper()} {self.amount}"


def compute_payroll_preview(employee, project=None, salary_month=None, payroll_entry=None, ot_hours_override=None):
    """Pure calculation, no persistence. The single formula authority for both the
    live JSON preview endpoint (used before a PayrollEntry exists) and for what
    PayrollEntry.rebuild_auto_deductions()/recompute_gross() actually save — so the
    live summary panel and the saved record can never drift apart.

    `payroll_entry`, if given (editing an existing draft), supplies already-saved
    allowances so the gross/EPF figures reflect them; for a brand-new entry there
    are no allowances yet, which is accurate.

    `ot_hours_override`, if given, replaces the auto-totaled OT hours in the
    returned figures — used only for the live "what-if" preview when a privileged
    user is manually adjusting OT Hours; the caller is responsible for checking
    override permission before passing this.
    """
    result = {
        "working_days": Decimal("0"),
        "present_days": Decimal("0"),
        "leave_days": Decimal("0"),
        "no_pay_days": Decimal("0"),
        "holiday_days": Decimal("0"),
        "ot_hours": Decimal("0"),
        "ot_rate": Decimal("0"),
        "ot_amount": Decimal("0"),
        "basic_salary": Decimal("0"),
        "no_pay_deduction": Decimal("0"),
        "salary_advance_total": Decimal("0"),
        "salary_advance_items": [],
        "safety_supply_total": Decimal("0"),
        "safety_supply_items": [],
        "total_allowances": Decimal("0"),
        "gross_salary": Decimal("0"),
        "epf_employee": Decimal("0"),
        "employer_epf": Decimal("0"),
        "employer_etf": Decimal("0"),
        "total_auto_deductions": Decimal("0"),
        "net_salary_preview": Decimal("0"),
    }
    if not employee or not salary_month:
        return result

    year, month = salary_month.year, salary_month.month

    attendance = Attendance.objects.filter(employee=employee, date__year=year, date__month=month)
    working_days = sum((Attendance.day_value(a.status) for a in attendance), Decimal("0"))
    present_days = attendance.filter(status__in=["present", "late"]).count()
    leave_days = attendance.filter(status="leave").count()
    no_pay_days = attendance.filter(status="absent").count()
    holiday_days = attendance.filter(status="holiday").count()

    ot_hours = LabourAllocation.objects.filter(
        employee=employee, date__year=year, date__month=month
    ).aggregate(total=Sum("ot_hours"))["total"] or Decimal("0")
    ot_hours = Decimal(str(ot_hours))
    if ot_hours_override is not None:
        ot_hours = Decimal(str(ot_hours_override))
    ot_rate = employee.hourly_ot_rate
    ot_amount = (ot_hours * ot_rate).quantize(Decimal("0.01"))

    is_daily = employee.salary_type == "daily" or employee.employment_type == "daily_labour"
    if is_daily:
        basic_salary = (employee.effective_daily_rate * working_days).quantize(Decimal("0.01"))
        no_pay_deduction = Decimal("0")
    else:
        basic_salary = Decimal(str(employee.basic_salary or 0))
        no_pay_deduction = (Decimal(str(no_pay_days)) * employee.effective_daily_rate).quantize(Decimal("0.01"))

    total_allowances = payroll_entry.total_allowances if payroll_entry else Decimal("0")
    gross_salary = (basic_salary + ot_amount + total_allowances).quantize(Decimal("0.01"))

    epf_employee = Decimal("0")
    employer_epf = Decimal("0")
    employer_etf = Decimal("0")
    if employee.epf_etf_applicable:
        epf_employee = (gross_salary * EPF_EMPLOYEE_RATE).quantize(Decimal("0.01"))
        employer_epf = (gross_salary * EPF_EMPLOYER_RATE).quantize(Decimal("0.01"))
        employer_etf = (gross_salary * ETF_EMPLOYER_RATE).quantize(Decimal("0.01"))

    advances = SalaryAdvance.objects.filter(
        employee=employee, status="approved",
        deduction_month__year=year, deduction_month__month=month,
    )
    salary_advance_items = []
    salary_advance_total = Decimal("0")
    for advance in advances:
        balance = advance.remaining_balance
        if balance > 0:
            salary_advance_items.append({"id": advance.id, "amount": balance})
            salary_advance_total += balance

    safety_issues = SafetyItemIssue.objects.filter(
        employee=employee, deduct_from_salary=True, status="pending",
        deduction_month__year=year, deduction_month__month=month,
    )
    safety_supply_items = []
    safety_supply_total = Decimal("0")
    for issue in safety_issues:
        if issue.total_value and issue.total_value > 0:
            safety_supply_items.append({"id": issue.id, "name": issue.safety_item, "amount": issue.total_value})
            safety_supply_total += issue.total_value

    total_auto_deductions = epf_employee + no_pay_deduction + salary_advance_total + safety_supply_total

    result.update({
        "working_days": working_days,
        "present_days": Decimal(str(present_days)),
        "leave_days": Decimal(str(leave_days)),
        "no_pay_days": Decimal(str(no_pay_days)),
        "holiday_days": Decimal(str(holiday_days)),
        "ot_hours": ot_hours,
        "ot_rate": ot_rate,
        "ot_amount": ot_amount,
        "basic_salary": basic_salary,
        "no_pay_deduction": no_pay_deduction,
        "salary_advance_total": salary_advance_total,
        "salary_advance_items": salary_advance_items,
        "safety_supply_total": safety_supply_total,
        "safety_supply_items": safety_supply_items,
        "total_allowances": total_allowances,
        "gross_salary": gross_salary,
        "epf_employee": epf_employee,
        "employer_epf": employer_epf,
        "employer_etf": employer_etf,
        "total_auto_deductions": total_auto_deductions,
        "net_salary_preview": gross_salary - total_auto_deductions,
    })
    return result


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
    transfer = models.ForeignKey(
        "ProjectTransfer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_expense_entries"
    )
    original_expense = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfer_adjustments"
    )
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
    transfer = models.ForeignKey(
        "ProjectTransfer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_income_entries"
    )
    original_income = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfer_adjustments"
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-income_date", "-id"]

    def __str__(self):
        return f"{self.project.project_id} - {self.amount}"


class ProjectTransfer(models.Model):
    TRANSFER_TYPE_CHOICES = [
        ("expense", "Expense"),
        ("income", "Income"),
    ]

    transfer_no = models.CharField(max_length=20, unique=True, blank=True, null=True)
    transfer_type = models.CharField(max_length=20, choices=TRANSFER_TYPE_CHOICES)
    from_project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="outgoing_transfers"
    )
    to_project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="incoming_transfers"
    )
    original_project_expense = models.ForeignKey(
        ProjectExpense,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expense_transfers"
    )
    original_project_income = models.ForeignKey(
        ProjectIncome,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="income_transfers"
    )
    transfer_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    transfer_date = models.DateField(default=timezone.now)
    reason = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_project_transfers"
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_project_transfers"
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-transfer_date", "-id"]

    def save(self, *args, **kwargs):
        if not self.transfer_no:
            last = ProjectTransfer.objects.exclude(transfer_no__isnull=True).order_by("-id").first()
            if last and last.transfer_no and str(last.transfer_no).replace("TRF", "").isdigit():
                next_no = int(str(last.transfer_no).replace("TRF", "")) + 1
                self.transfer_no = f"TRF{next_no:06d}"
            else:
                self.transfer_no = "TRF000001"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.transfer_no or f"Transfer {self.id}"


# =========================
# EMPLOYEES / PETTY CASH
# =========================
class Employee(models.Model):
    EMPLOYMENT_TYPE_CHOICES = [
        ("permanent", "Permanent"),
        ("executive", "Executive"),
        ("contract", "Contract"),
        ("daily_labour", "Daily Labour"),
    ]
    SALARY_TYPE_CHOICES = [
        ("monthly", "Monthly"),
        ("daily", "Daily"),
        ("contract", "Contract"),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="employee_profile")
    emp_no = models.CharField(max_length=30, unique=True, blank=True, null=True)
    full_name = models.CharField(max_length=255)
    nic = models.CharField(max_length=20, blank=True, null=True)
    employee_category = models.CharField(max_length=100, blank=True, null=True)
    designation = models.CharField(max_length=100, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    joining_date = models.DateField(blank=True, null=True)
    basic_salary = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    daily_rate = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    ot_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="OT rate per hour. If blank/0, derived from daily/basic rate.")
    salary_type = models.CharField(max_length=20, choices=SALARY_TYPE_CHOICES, default="monthly")
    contract_based = models.BooleanField(default=False)
    employment_type = models.CharField(max_length=30, choices=EMPLOYMENT_TYPE_CHOICES, default="permanent")
    epf_etf_applicable = models.BooleanField(default=True)
    default_project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="default_employees")
    default_supervisor = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="default_supervised_employees")
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    bank_account_no = models.CharField(max_length=50, blank=True, null=True)
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

    @property
    def effective_daily_rate(self):
        """Daily rate to use for OT/day-rate pricing, derived from basic_salary
        for monthly-salary employees who don't have daily_rate set."""
        if self.daily_rate:
            return Decimal(str(self.daily_rate))
        if self.basic_salary:
            return Decimal(str(self.basic_salary)) / STANDARD_MONTHLY_WORKING_DAYS
        return Decimal("0")

    @property
    def hourly_ot_rate(self):
        if self.ot_rate:
            return Decimal(str(self.ot_rate))
        rate = self.effective_daily_rate
        return (rate / Decimal("8")) if rate else Decimal("0")

    @property
    def masked_bank_account_no(self):
        account = (self.bank_account_no or "").strip()
        if not account:
            return "-"
        return f"****{account[-4:]}" if len(account) > 4 else account

    def __str__(self):
        return f"{self.emp_no} - {self.full_name}"


class LabourAllocation(models.Model):
    ATTENDANCE_STATUS_CHOICES = [
        ("present", "Present"),
        ("absent", "Absent"),
        ("half_day", "Half Day"),
        ("leave", "Leave"),
        ("holiday", "Holiday"),
        ("late", "Late"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="labour_allocations")
    date = models.DateField(default=timezone.now)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="labour_allocations")
    supervisor = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name="supervised_labour_allocations")
    work_type = models.CharField(max_length=100, blank=True, null=True)
    working_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    ot_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    daily_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ot_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_labour_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    attendance_status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS_CHOICES, default="present")
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]

    def save(self, *args, **kwargs):
        employee_rate = Decimal(str(self.employee.daily_rate or 0)) if self.employee_id else Decimal("0")
        daily_rate = self.daily_rate or employee_rate
        ot_rate = self.ot_rate or (daily_rate / Decimal("8")) if daily_rate else Decimal("0")
        working_hours = Decimal(str(self.working_hours or 0))
        ot_hours = Decimal(str(self.ot_hours or 0))
        normal_cost = (working_hours / Decimal("8")) * daily_rate if daily_rate else Decimal("0")
        ot_cost = ot_hours * ot_rate if ot_rate else Decimal("0")
        self.daily_rate = daily_rate
        self.ot_rate = ot_rate
        self.total_labour_cost = normal_cost + ot_cost
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee} - {self.project} - {self.date}"


class Attendance(models.Model):
    STATUS_CHOICES = LabourAllocation.ATTENDANCE_STATUS_CHOICES

    # Day value used for payroll working-day totals.
    STATUS_DAY_VALUE = {
        "present": Decimal("1"),
        "late": Decimal("1"),
        "half_day": Decimal("0.5"),
        "absent": Decimal("0"),
        "leave": Decimal("0"),
        "holiday": Decimal("0"),
    }

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField(default=timezone.now)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_records")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="present")
    remarks = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "employee__full_name"]
        unique_together = ("employee", "date")

    @classmethod
    def day_value(cls, status):
        return cls.STATUS_DAY_VALUE.get(status, Decimal("0"))

    @property
    def day_count(self):
        return self.day_value(self.status)

    def __str__(self):
        return f"{self.employee} - {self.date} - {self.status}"


class SafetyItemIssue(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("deducted", "Deducted"),
        ("waived", "Waived"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="safety_item_issues")
    safety_item = models.CharField(max_length=255)
    issue_date = models.DateField(default=timezone.now)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    item_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    deduction_month = models.DateField(blank=True, null=True)
    deduct_from_salary = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    remarks = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issue_date", "-id"]

    def save(self, *args, **kwargs):
        self.total_value = Decimal(str(self.quantity or 0)) * Decimal(str(self.item_value or 0))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee} - {self.safety_item}"


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
        ("payslip", "Payslip"),
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
    
class Customer(models.Model):
    customer_code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    registration_no = models.CharField(max_length=100, blank=True, null=True)
    receivable_gl_account = models.ForeignKey(
        GLMaster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_receivable_accounts"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.registration_no:
            last = Customer.objects.exclude(registration_no__isnull=True).order_by("-id").first()
            if last and last.registration_no and str(last.registration_no).replace("REG", "").isdigit():
                next_no = int(str(last.registration_no).replace("REG", "")) + 1
                self.registration_no = f"REG{next_no:05d}"
            else:
                self.registration_no = "REG00001"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer_code} - {self.name}"

class SupplierAdvance(models.Model):
    PAYMENT_METHODS = [
        ("cash", "Cash"),
        ("card", "Card"),
        ("bank", "Bank Transfer"),
        ("cheque", "Cheque"),
    ]

    STATUS_CHOICES = [
        ("approved", "Approved"),
        ("closed", "Closed"),
    ]

    advance_no = models.CharField(max_length=30, unique=True, blank=True, null=True)
    supplier = models.ForeignKey("Supplier", on_delete=models.PROTECT, related_name="advances")
    project = models.ForeignKey("Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="supplier_advances")
    po = models.ForeignKey(
    "PurchaseOrder",
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="advances"
)
    advance_date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default="cash")
    paid_from_gl = models.ForeignKey(
        "GLMaster",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_advance_paid_from"
    )
    advance_gl = models.ForeignKey(
        "GLMaster",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_advance_gl"
    )

    note = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="approved")
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_supplier_advances"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-advance_date", "-id"]

    def save(self, *args, **kwargs):
        if not self.advance_no:
            last = SupplierAdvance.objects.exclude(advance_no__isnull=True).order_by("-id").first()
            if last and last.advance_no and str(last.advance_no).replace("SADV", "").isdigit():
                next_no = int(str(last.advance_no).replace("SADV", "")) + 1
                self.advance_no = f"SADV{next_no:05d}"
            else:
                self.advance_no = "SADV00001"
        super().save(*args, **kwargs)

    @property
    def settled_amount(self):
        return self.settlements.filter(approval_status="approved").aggregate(
            total=Sum("actual_amount")
        )["total"] or Decimal("0")

    @property
    def pending_settlement_amount(self):
        return self.settlements.filter(approval_status="pending").aggregate(
            total=Sum("actual_amount")
        )["total"] or Decimal("0")

    @property
    def balance_amount(self):
        return Decimal(str(self.amount or 0)) - Decimal(str(self.settled_amount or 0))

    def __str__(self):
        return self.advance_no or f"Supplier Advance {self.id}"


class SupplierSettlement(models.Model):
    APPROVAL_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    settlement_no = models.CharField(max_length=30, unique=True, blank=True, null=True)
    advance = models.ForeignKey(
        "SupplierAdvance",
        on_delete=models.PROTECT,
        related_name="settlements"
    )
    supplier = models.ForeignKey("Supplier", on_delete=models.PROTECT, related_name="settlements")
    project = models.ForeignKey("Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="supplier_settlements")
    grn = models.ForeignKey(
        "GRN",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_settlements"
    )
    settlement_date = models.DateField(default=timezone.now)

    description = models.CharField(max_length=255)
    actual_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    advance_applied = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    excess_advance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    expense_gl = models.ForeignKey(
        "GLMaster",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_settlement_expense_gl"
    )

    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default="pending")
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_supplier_settlements"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_note = models.TextField(blank=True, null=True)

    linked_project_expense = models.ForeignKey(
        "ProjectExpense",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_settlements"
    )

    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_supplier_settlements"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-settlement_date", "-id"]

    def save(self, *args, **kwargs):
        if not self.settlement_no:
            last = SupplierSettlement.objects.exclude(settlement_no__isnull=True).order_by("-id").first()
            if last and last.settlement_no and str(last.settlement_no).replace("SSET", "").isdigit():
                next_no = int(str(last.settlement_no).replace("SSET", "")) + 1
                self.settlement_no = f"SSET{next_no:05d}"
            else:
                self.settlement_no = "SSET00001"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.settlement_no or f"Settlement {self.id}"

class SupplierSettlementAdvanceLink(models.Model):
    settlement = models.ForeignKey(
        "SupplierSettlement",
        on_delete=models.CASCADE,
        related_name="advance_links"
    )
    advance = models.ForeignKey(
        "SupplierAdvance",
        on_delete=models.PROTECT,
        related_name="settlement_links"
    )
    applied_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.settlement.settlement_no} - {self.advance.advance_no}"
    
class PurchaseOrder(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("bank", "Bank Transfer"),
        ("cheque", "Cheque"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("closed", "Closed"),
    ]

    po_no = models.CharField(max_length=30, unique=True, blank=True, null=True)
    po_date = models.DateField(default=timezone.now)
    delivery_date_required = models.DateField(blank=True, null=True)

    buyer_company_name = models.CharField(max_length=200, blank=True, null=True)
    buyer_address = models.TextField(blank=True, null=True)
    buyer_contact_person = models.CharField(max_length=150, blank=True, null=True)
    buyer_phone = models.CharField(max_length=50, blank=True, null=True)
    buyer_email = models.EmailField(blank=True, null=True)

    supplier = models.ForeignKey("Supplier", on_delete=models.PROTECT, related_name="purchase_orders")
    supplier_address = models.TextField(blank=True, null=True)
    supplier_contact_details = models.CharField(max_length=255, blank=True, null=True)

    project = models.ForeignKey("Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_orders")

    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default="bank")
    payment_period = models.CharField(max_length=100, blank=True, null=True)

    delivery_location = models.CharField(max_length=255, blank=True, null=True)
    delivery_method = models.CharField(max_length=100, blank=True, null=True)
    special_instructions = models.TextField(blank=True, null=True)

    terms_and_conditions = models.TextField(blank=True, null=True)
    warranty_details = models.TextField(blank=True, null=True)
    return_policy = models.TextField(blank=True, null=True)
    penalties_conditions = models.TextField(blank=True, null=True)

    authorized_person_name = models.CharField(max_length=150, blank=True, null=True)
    signature_text = models.CharField(max_length=150, blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    note = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_purchase_orders"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-po_date", "-id"]

    def save(self, *args, **kwargs):
        if not self.po_no:
            last = PurchaseOrder.objects.exclude(po_no__isnull=True).order_by("-id").first()
            if last and last.po_no and str(last.po_no).replace("PO", "").isdigit():
                next_no = int(str(last.po_no).replace("PO", "")) + 1
                self.po_no = f"PO{next_no:05d}"
            else:
                self.po_no = "PO00001"
        super().save(*args, **kwargs)

    @property
    def grand_total(self):
        return self.items.aggregate(total=Sum("line_total"))["total"] or Decimal("0")

    def __str__(self):
        return self.po_no or f"PO {self.id}"
    
class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(
        "PurchaseOrder",
        on_delete=models.CASCADE,
        related_name="items"
    )
    item = models.ForeignKey(
        "Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_order_items"
    )
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["id"]

    def save(self, *args, **kwargs):
        self.line_total = Decimal(str(self.quantity or 0)) * Decimal(str(self.unit_price or 0))
        super().save(*args, **kwargs)

    def __str__(self):
        return self.description


class GRN(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("received", "Received"),
        ("inspected", "Inspected"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    grn_no = models.CharField(max_length=30, unique=True, blank=True, null=True)
    grn_date = models.DateField(default=timezone.now)
    received_date = models.DateField(blank=True, null=True)
    
    purchase_order = models.ForeignKey(
        "PurchaseOrder", 
        on_delete=models.PROTECT, 
        related_name="grns"
    )
    supplier = models.ForeignKey(
        "Supplier", 
        on_delete=models.PROTECT, 
        related_name="grns"
    )
    
    delivery_note_no = models.CharField(max_length=50, blank=True, null=True)
    invoice_no = models.CharField(max_length=50, blank=True, null=True)
    vehicle_no = models.CharField(max_length=50, blank=True, null=True)
    
    received_by = models.CharField(max_length=150, blank=True, null=True)
    inspected_by = models.CharField(max_length=150, blank=True, null=True)
    approved_by = models.CharField(max_length=150, blank=True, null=True)
    
    quality_check_passed = models.BooleanField(default=False)
    quality_notes = models.TextField(blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    notes = models.TextField(blank=True, null=True)
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_grns"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-grn_date", "-id"]
        verbose_name = "GRN"
        verbose_name_plural = "GRNs"

    def save(self, *args, **kwargs):
        if not self.grn_no:
            last = GRN.objects.exclude(grn_no__isnull=True).order_by("-id").first()
            if last and last.grn_no and str(last.grn_no).replace("GRN", "").isdigit():
                next_no = int(str(last.grn_no).replace("GRN", "")) + 1
                self.grn_no = f"GRN{next_no:05d}"
            else:
                self.grn_no = "GRN00001"
        super().save(*args, **kwargs)

    @property
    def total_quantity_received(self):
        return self.items.aggregate(total=Sum("quantity_received"))["total"] or Decimal("0")

    @property
    def total_quantity_accepted(self):
        return self.items.aggregate(total=Sum("quantity_accepted"))["total"] or Decimal("0")

    @property
    def total_quantity_rejected(self):
        return self.items.aggregate(total=Sum("quantity_rejected"))["total"] or Decimal("0")

    @property
    def total_value(self):
        return sum(item.line_total for item in self.items.all())

    def __str__(self):
        return self.grn_no or f"GRN {self.id}"


class GRNItem(models.Model):
    QUALITY_CHOICES = [
        ("good", "Good"),
        ("damaged", "Damaged"),
        ("rejected", "Rejected"),
    ]

    ALLOCATION_CHOICES = [
        ("inventory", "Inventory"),
        ("project", "Project"),
        ("asset", "Company Asset"),
    ]

    grn = models.ForeignKey(
        "GRN",
        on_delete=models.CASCADE,
        related_name="items"
    )
    purchase_order_item = models.ForeignKey(
        "PurchaseOrderItem",
        on_delete=models.PROTECT,
        related_name="grn_items"
    )
    item = models.ForeignKey(
        "Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grn_items"
    )
    
    quantity_ordered = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quantity_received = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quantity_accepted = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quantity_rejected = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    allocation_type = models.CharField(max_length=20, choices=ALLOCATION_CHOICES, default="inventory")
    allocation_project = models.ForeignKey(
        "Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grn_allocations"
    )
    company_asset = models.ForeignKey(
        "CompanyAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grn_items"
    )
    
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    quality_status = models.CharField(max_length=20, choices=QUALITY_CHOICES, default="good")
    quality_notes = models.TextField(blank=True, null=True)
    
    batch_no = models.CharField(max_length=50, blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    
    class Meta:
        ordering = ["id"]
        unique_together = ["grn", "purchase_order_item"]

    def save(self, *args, **kwargs):
        self.line_total = Decimal(str(self.quantity_accepted or 0)) * Decimal(str(self.unit_price or 0))
        super().save(*args, **kwargs)

    def __str__(self):
        item_name = self.item.name if self.item else self.purchase_order_item.description
        return f"{self.grn.grn_no} - {item_name}"


class CompanyAsset(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    asset_no = models.CharField(max_length=30, unique=True, blank=True, null=True)
    grn = models.ForeignKey(
        "GRN",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="company_assets"
    )
    grn_item = models.ForeignKey(
        "GRNItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_record"
    )
    purchase_order = models.ForeignKey(
        "PurchaseOrder",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="company_assets"
    )
    supplier = models.ForeignKey(
        "Supplier",
        on_delete=models.PROTECT,
        related_name="company_assets"
    )
    asset_name = models.CharField(max_length=255)
    purchase_date = models.DateField(default=timezone.now)
    purchase_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    serial_number = models.CharField(max_length=150, blank=True, null=True)
    model_number = models.CharField(max_length=150, blank=True, null=True)
    warranty_details = models.TextField(blank=True, null=True)
    responsible_person = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="company_assets"
    )
    remarks = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_company_assets"
    )
    approved_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_company_assets"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-purchase_date", "-id"]

    def save(self, *args, **kwargs):
        if not self.asset_no:
            last = CompanyAsset.objects.exclude(asset_no__isnull=True).order_by("-id").first()
            if last and last.asset_no and str(last.asset_no).replace("ASSET", "").isdigit():
                next_no = int(str(last.asset_no).replace("ASSET", "")) + 1
                self.asset_no = f"ASSET{next_no:06d}"
            else:
                self.asset_no = "ASSET000001"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.asset_no or self.asset_name    



    
    


# =========================
# LOGGING MODELS
# =========================
class UserLog(models.Model):
    """Log for user login/logout activity"""
    
    ACTION_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f'{self.user.username} - {self.action} at {self.timestamp}'


class AuditLog(models.Model):
    """Audit trail for all model changes"""
    
    ACTION_CHOICES = [
        ('create', 'Created'),
        ('update', 'Updated'),
        ('delete', 'Deleted'),
        ('view', 'Viewed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    model_name = models.CharField(max_length=50)
    object_id = models.CharField(max_length=100)
    object_display = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f'{self.action.title()} {self.model_name} by {self.user.username if self.user else "Unknown"}'


# =========================
# PROJECT COST ANALYSIS
# =========================
class ProjectBudget(models.Model):
    """Master budget record for a project"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('archived', 'Archived'),
    ]
    
    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name='budget'
    )
    budget_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    total_budget_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    
    notes = models.TextField(blank=True, null=True)
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_budgets'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Budget - {self.project.project_id}"
    
    def recalculate_total(self):
        """Recalculate total budget from budget lines"""
        total = self.lines.aggregate(Sum('budget_amount'))['budget_amount__sum'] or Decimal('0')
        self.total_budget_amount = total
        self.save()
        return total


class ProjectBudgetLine(models.Model):
    """GL-wise budget breakdown for a project"""
    
    budget = models.ForeignKey(
        ProjectBudget,
        on_delete=models.CASCADE,
        related_name='lines'
    )
    
    gl_account = models.ForeignKey(
        GLMaster,
        on_delete=models.PROTECT,
        related_name='budget_lines'
    )
    
    budget_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['gl_account__gl_code']
        unique_together = ['budget', 'gl_account']
    
    def __str__(self):
        return f"{self.budget.project.project_id} - {self.gl_account.gl_code}"
    
    @property
    def gl_group(self):
        """Get GL group based on GL code range"""
        return self.get_gl_group(self.gl_account.gl_code)
    
    @staticmethod
    def get_gl_group(gl_code):
        """Map GL code to GL Group"""
        try:
            code_num = int(gl_code)
        except (ValueError, TypeError):
            return "Other"
        
        if 5100 <= code_num <= 5199:
            return "Direct Material Cost"
        elif 5200 <= code_num <= 5299:
            return "Direct Labour Cost"
        elif 5300 <= code_num <= 5399:
            return "Plant & Equipment Cost"
        elif 5400 <= code_num <= 5499:
            return "Subcontractor Cost"
        elif 5500 <= code_num <= 5599:
            return "Third Party Service Cost"
        elif 5600 <= code_num <= 5699:
            return "Transportation & Logistics"
        elif 5700 <= code_num <= 5799:
            return "Project-Specific Expenses"
        elif 5800 <= code_num <= 5899:
            return "Variations / Cost Adjustments"
        elif 5900 <= code_num <= 5999:
            return "Retail Operating Expenses"
        elif 6000 <= code_num <= 6099:
            return "Overhead Expenses"
        elif 6100 <= code_num <= 6199:
            return "Selling & Marketing"
        elif 6200 <= code_num <= 6299:
            return "General Expenses"
        elif code_num >= 8000:
            return "Other Expenses"
        else:
            return "Other"


class ProjectCostActual(models.Model):
    """Cache for actual costs - updated by transaction approvals"""
    
    COST_SOURCE_CHOICES = [
        ('project_expense', 'Project Expense'),
        ('petty_cash', 'Petty Cash Expense'),
        ('grn_issue', 'GRN Issue'),
        ('inventory_issue', 'Inventory Issue'),
        ('supplier_settlement', 'Supplier Settlement'),
    ]
    
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='cost_actuals'
    )
    
    gl_account = models.ForeignKey(
        GLMaster,
        on_delete=models.PROTECT,
        related_name='cost_actuals'
    )
    
    source_type = models.CharField(max_length=30, choices=COST_SOURCE_CHOICES)
    source_id = models.CharField(max_length=100)  # ID of source transaction
    
    transaction_date = models.DateField()
    description = models.CharField(max_length=255)
    
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    
    reference_no = models.CharField(max_length=100, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-transaction_date', '-id']
        indexes = [
            models.Index(fields=['project', 'gl_account']),
            models.Index(fields=['project', 'source_type']),
        ]
    
    def __str__(self):
        return f"{self.project.project_id} - {self.gl_account.gl_code} - {self.amount}"


# =========================
# DATABASE BACKUP & RESTORE
# =========================
class BackupSettings(models.Model):
    FREQUENCY_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
    ]
    RETENTION_CHOICES = [
        (7, "Keep Last 7 Backups"),
        (30, "Keep Last 30 Backups"),
        (90, "Keep Last 90 Backups"),
    ]
    STORAGE_CHOICES = [
        ("local", "Local Server"),
        ("google_drive", "Google Drive (Coming soon)"),
        ("other", "Other Cloud Storage (Coming soon)"),
    ]
    WEEKDAY_CHOICES = [
        (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"),
        (4, "Friday"), (5, "Saturday"), (6, "Sunday"),
    ]

    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default="daily")
    backup_time = models.TimeField(default="23:00")
    weekly_day = models.IntegerField(choices=WEEKDAY_CHOICES, default=6)
    monthly_day = models.IntegerField(default=1)
    retention_count = models.IntegerField(choices=RETENTION_CHOICES, default=30)
    auto_backup_enabled = models.BooleanField(default=False)
    storage_location = models.CharField(max_length=20, choices=STORAGE_CHOICES, default="local")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Backup Settings"
        verbose_name_plural = "Backup Settings"

    @classmethod
    def get_solo(cls):
        obj = cls.objects.first()
        if obj is None:
            obj = cls.objects.create()
        return obj

    def __str__(self):
        return "Backup Settings"


class BackupRecord(models.Model):
    BACKUP_TYPE_CHOICES = [
        ("manual", "Manual"),
        ("scheduled", "Scheduled"),
        ("pre_restore", "Pre-Restore Safety Backup"),
    ]
    STATUS_CHOICES = [
        ("in_progress", "In Progress"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]
    DB_ENGINE_CHOICES = [
        ("sqlite", "SQLite"),
        ("postgresql", "PostgreSQL"),
    ]

    backup_type = models.CharField(max_length=20, choices=BACKUP_TYPE_CHOICES, default="manual")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="in_progress")
    file_name = models.CharField(max_length=255, blank=True, null=True)
    file_path = models.CharField(max_length=500, blank=True, null=True)
    file_size = models.BigIntegerField(default=0)
    db_engine = models.CharField(max_length=20, choices=DB_ENGINE_CHOICES, blank=True, null=True)
    storage_location = models.CharField(max_length=20, default="local")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    initiated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="initiated_backups")
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-started_at", "-id"]

    @property
    def duration_seconds(self):
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def file_size_display(self):
        size = self.file_size or 0
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def __str__(self):
        return self.file_name or f"Backup {self.id}"


class RestoreLog(models.Model):
    STATUS_CHOICES = [
        ("in_progress", "In Progress"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    backup_record = models.ForeignKey(BackupRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name="restore_attempts")
    pre_restore_backup = models.ForeignKey(BackupRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    initiated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="initiated_restores")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="in_progress")
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-started_at", "-id"]

    def __str__(self):
        return f"Restore {self.id} - {self.status}"
