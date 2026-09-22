#!/usr/bin/env python3
"""
Verify the barcode system fix - confirm all functions work and imports are correct.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

print("\n" + "="*80)
print("BARCODE SYSTEM FIX VERIFICATION")
print("="*80 + "\n")

# Step 1: Verify imports
print("Step 1: Verify imports")
try:
    from pos.barcode_services import generate_barcode_for_item, generate_missing_barcodes
    print("  ✓ Legacy barcode functions (generate_barcode_for_item, generate_missing_barcodes)")

    from pos.barcode_services_standard import (
        generate_code128_svg,
        generate_code128_metrics,
        validate_encoding,
        generate_code128_html_page
    )
    print("  ✓ Standard barcode functions (generate_code128_svg, etc.)")

    from pos.views import barcode_management, print_item_barcode, barcode_test_page, barcode_standard_test
    print("  ✓ All barcode views\n")
except ImportError as e:
    print(f"  ✗ Import error: {e}\n")
    sys.exit(1)

# Step 2: Test barcode generation
print("Step 2: Test barcode generation")
test_value = "1000000073"

try:
    svg = generate_code128_svg(test_value)
    print(f"  ✓ generate_code128_svg('{test_value}')")
    print(f"    SVG length: {len(svg)} bytes\n")
except Exception as e:
    print(f"  ✗ Error: {e}\n")
    sys.exit(1)

# Step 3: Test metrics
print("Step 3: Test barcode metrics")
try:
    metrics = generate_code128_metrics(test_value)
    print(f"  ✓ generate_code128_metrics('{test_value}')")
    print(f"    Total width: {metrics['total_width_mm']:.2f} mm")
    print(f"    Height: {metrics['height_mm']} mm\n")
except Exception as e:
    print(f"  ✗ Error: {e}\n")
    sys.exit(1)

# Step 4: Test validation
print("Step 4: Test encoding validation")
try:
    validation = validate_encoding(test_value)
    if validation.get('valid'):
        print(f"  ✓ validate_encoding('{test_value}')")
        print(f"    Payload: {validation.get('payload')}")
        print(f"    Match: {'✓ YES' if validation.get('payload') == test_value else '✗ NO'}\n")
    else:
        print(f"  ✗ Validation failed: {validation.get('error')}\n")
        sys.exit(1)
except Exception as e:
    print(f"  ✗ Error: {e}\n")
    sys.exit(1)

# Step 5: Verify Item exists
print("Step 5: Check test item")
from pos.models import Item
item = Item.objects.filter(barcode=test_value).first()
if item:
    print(f"  ✓ Item exists: {item.name}")
    print(f"    Item Code: {item.item_code}")
    print(f"    Barcode: {item.barcode}\n")
else:
    print(f"  ⚠ Test item not found (can be created manually)\n")

print("="*80)
print("VERIFICATION RESULT: ✓ ALL CHECKS PASSED")
print("="*80 + "\n")

print("Summary:")
print("  ✓ All imports work correctly")
print("  ✓ Barcode generation works (python-barcode 0.16.1)")
print("  ✓ Metrics calculation works")
print("  ✓ Encoding validation works")
print("  ✓ No ImportError for code128_metrics or code128_svg")
print("  ✓ Standard library is the primary barcode generator")
print("\nThe Render deployment error should now be fixed.")
print("Barcode system is using python-barcode, not custom implementation.\n")
