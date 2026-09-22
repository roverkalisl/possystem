#!/usr/bin/env python3
"""Create a test item for A4 label testing."""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from pos.models import Item, Category, GLMaster
from decimal import Decimal

print("\n" + "="*80)
print("CREATE TEST ITEM FOR A4 LABEL TESTING")
print("="*80 + "\n")

# Get or create category
category, _ = Category.objects.get_or_create(
    name="Test Items",
    defaults={"description": "Items for testing", "is_active": True}
)
print(f"✓ Category: {category.name}\n")

# Get GL accounts (need at least one for retail)
gl_retail = GLMaster.objects.filter(gl_type="income").first()
if not gl_retail:
    print("⚠ No income GL account found, creating one...\n")
    gl_retail = GLMaster.objects.create(
        gl_code="1000",
        gl_name="Sales Income",
        gl_type="income",
        is_active=True
    )
    print(f"✓ Created GL account: {gl_retail.gl_name}\n")

# Check if test item already exists
item = Item.objects.filter(item_code="1000000073").first()

if item:
    print(f"✓ Item already exists: {item.name}")
    print(f"  Item Code: {item.item_code}")
    print(f"  Barcode: {item.barcode}")
    print(f"  Selling Price: {item.selling_price}\n")
else:
    print("✗ Test item not found, creating one...\n")

    # Create the test item
    item = Item.objects.create(
        item_code="1000000073",
        name="Safety Life Jacket Vest, size C",
        category=category,
        unit="piece",
        cost_price=Decimal("450.00"),
        selling_price=Decimal("650.00"),
        item_type="retail",
        is_service=False,
        allow_discount=True,
        retail_gl_account=gl_retail,
        is_active=True
    )

    # Assign barcode (same as item code)
    item.barcode = item.item_code
    item.save()

    print(f"✓ Item created successfully")
    print(f"  ID: {item.id}")
    print(f"  Name: {item.name}")
    print(f"  Item Code: {item.item_code}")
    print(f"  Barcode: {item.barcode}")
    print(f"  Selling Price: {item.selling_price}\n")

print("="*80)
print("NEXT STEPS")
print("="*80 + "\n")
print("1. Log in to: http://localhost:8000/login/")
print("   Username: __diag_test_user__")
print("   Password: TestPass123\n")
print("2. Navigate to item management")
print("3. Find or create item with code: 1000000073")
print("4. Print A4 label (1 label) via print_item_barcode view")
print("5. Print at 100% scale")
print("6. Scan the barcode")
print("7. Expected result: 1000000073\n")
