from django.db import models
from django.contrib.auth.models import User


# ==============================
# CATEGORY
# ==============================
class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


# ==============================
# SUPPLIER
# ==============================
class Supplier(models.Model):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


# ==============================
# ITEM
# ==============================
class Item(models.Model):
    ITEM_TYPE_CHOICES = [
        ('retail', 'Retail'),
        ('project', 'Project'),
        ('both', 'Both'),
        ('expense', 'Expense'),
    ]

    item_code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    unit = models.CharField(max_length=20, default="pcs")

    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    stock = models.IntegerField(default=0)

    purchase_date = models.DateField(blank=True, null=True)

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES, default='retail')

    is_service = models.BooleanField(default=False)

    reorder_level = models.IntegerField(default=0)

    warranty_days = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# ==============================
# STOCK TRANSACTIONS
# ==============================
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

    def __str__(self):
        return f"{self.item.name} - {self.transaction_type}"


# ==============================
# SALE
# ==============================
class Sale(models.Model):
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('credit', 'Credit'),
    ]

    invoice_no = models.CharField(max_length=50, unique=True)

    total = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2)

    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)

    received_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    card_last4 = models.CharField(max_length=4, blank=True, null=True)
    cheque_number = models.CharField(max_length=50, blank=True, null=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.invoice_no


# ==============================
# SALE ITEM
# ==============================
class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="sale_items")
    item = models.ForeignKey(Item, on_delete=models.CASCADE)

    qty = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return self.item.name


# ==============================
# PURCHASE
# ==============================
class Purchase(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    date = models.DateField()
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"Purchase - {self.id}"


# ==============================
# PURCHASE ITEM
# ==============================
class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)

    qty = models.IntegerField()
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return self.item.name
    
class SalesReturn(models.Model):
    RETURN_TYPE_CHOICES = [
        ('refund', 'Refund'),
        ('replace', 'Replace'),
        ('repair', 'Repair'),
    ]

    return_no = models.CharField(max_length=50, unique=True)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE)
    sale_item = models.ForeignKey(SaleItem, on_delete=models.CASCADE)
    qty = models.IntegerField(default=1)
    return_type = models.CharField(max_length=20, choices=RETURN_TYPE_CHOICES, default='refund')
    reason = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.return_no