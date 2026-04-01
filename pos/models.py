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
        ('asset', 'Asset'),
        ('liability', 'Liability'),
        ('equity', 'Equity'),
        ('income', 'Income'),
        ('expense', 'Expense'),
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
        ('retail', 'Retail'),
        ('project', 'Project'),
        ('both', 'Both'),
        ('expense', 'Expense'),
    ]

    item_code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)

    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)

    unit = models.CharField(max_length=20, default="pcs")
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock = models.IntegerField(default=0)

    purchase_date = models.DateField(blank=True, null=True)
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES, default='retail')
    is_service = models.BooleanField(default=False)
    reorder_level = models.IntegerField(default=0)
    warranty_days = models.IntegerField(default=0)

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

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class StockTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('opening', 'Opening Stock'),
        ('purchase', 'Purchase'),
        ('sale', 'Sale'),
        ('adjust_plus', 'Adjustment +'),
        ('adjust_minus', 'Adjustment -'),
        ('project_issue', 'Project Issue'),
    ]

    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    qty = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.item.name} - {self.transaction_type}"


class Sale(models.Model):
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('credit', 'Credit'),
    ]

    invoice_no = models.CharField(max_length=50, unique=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')

    received_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True, null=True)
    cheque_number = models.CharField(max_length=50, blank=True, null=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.invoice_no


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="sale_items")
    item = models.ForeignKey(Item, on_delete=models.CASCADE)

    qty = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return self.item.name


class SalesReturn(models.Model):
    RETURN_TYPE_CHOICES = [
        ('refund', 'Refund'),
        ('replace', 'Replace'),
        ('repair', 'Repair'),
    ]

    return_no = models.CharField(max_length=50, unique=True, null=True, blank=True)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, null=True, blank=True)
    sale_item = models.ForeignKey(SaleItem, on_delete=models.CASCADE, null=True, blank=True)
    qty = models.IntegerField(default=1)
    return_type = models.CharField(max_length=20, choices=RETURN_TYPE_CHOICES, default='refund')
    reason = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.return_no or "Return"


class Project(models.Model):
    PROJECT_TYPE_CHOICES = [
        ('BL', 'Building'),
        ('SW', 'Swimming Pool'),
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

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.project_id
class ProjectExpense(models.Model):

    EXPENSE_TYPE_CHOICES = [
        ('inventory', 'Inventory Item'),
        ('direct', 'Direct Item'),
        ('service', 'Service'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    expense_type = models.CharField(max_length=20, choices=EXPENSE_TYPE_CHOICES)

    expense_date = models.DateField(default=timezone.now)

    # inventory item (optional)
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True, blank=True)

    # direct/service description
    description = models.CharField(max_length=255)

    qty = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    # GL MUST
    gl_account = models.ForeignKey(GLMaster, on_delete=models.SET_NULL, null=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-expense_date", "-id"]

    def __str__(self):
        return f"{self.project.project_id} - {self.description}"
    
class ProjectPettyCash(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="petty_cash_headers")
    petty_cash_no = models.CharField(max_length=50, unique=True)
    issue_date = models.DateField(default=timezone.now)
    issued_to = models.CharField(max_length=200)
    amount_issued = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issue_date", "-id"]

    def __str__(self):
        return self.petty_cash_no

    @property
    def total_spent(self):
        total = self.expenses.aggregate(total=models.Sum("amount"))["total"] or 0
        return total

    @property
    def balance(self):
        return self.amount_issued - self.total_spent