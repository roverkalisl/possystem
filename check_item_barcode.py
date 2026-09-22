#!/usr/bin/env python3
"""
Check the actual item 'Safety Life Jacket Vest' and its barcode.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from pos.models import Item
from pos.barcode_services import code128_svg, _code128_plan

# Find the item
items = Item.objects.filter(name__icontains="Life Jacket").all()

print(f"\n{'='*80}")
print(f"Searching for Life Jacket items...")
print(f"{'='*80}\n")

if not items.exists():
    print("No items found with 'Life Jacket' in the name.")
    print("\nLet me try searching for 'Safety':")
    items = Item.objects.filter(name__icontains="Safety").all()

if not items.exists():
    print("No items found. Searching all items to find matching code...")
    items = Item.objects.filter(item_code="1000000073").all()

if not items.exists():
    print("No items with code 1000000073 found.")
    print("\nAll items:")
    for item in Item.objects.all()[:20]:
        print(f"  {item.id}: {item.name} (Code: {item.item_code}, Barcode: {item.barcode})")
else:
    for item in items:
        print(f"Found Item:")
        print(f"  ID: {item.id}")
        print(f"  Name: {item.name}")
        print(f"  Item Code: {item.item_code}")
        print(f"  Barcode: {item.barcode}")
        print(f"  Selling Price: {item.selling_price}")
        print(f"  Stock: {item.stock}")

        if item.barcode:
            print(f"\n  Barcode Details:")

            # Check for hidden characters in barcode
            print(f"    Barcode value: '{item.barcode}'")
            print(f"    Length: {len(item.barcode)}")
            print(f"    Character breakdown:")
            for i, char in enumerate(item.barcode):
                print(f"      [{i}] = '{char}' (ASCII {ord(char)}, hex {hex(ord(char))})")

            # Generate and check SVG
            try:
                svg = code128_svg(item.barcode)
                print(f"\n    SVG generation: ✓ Success")
                print(f"    SVG length: {len(svg)} characters")

                # Get plan details
                plan = _code128_plan(item.barcode, 0.33, 18, 10)
                print(f"\n    Barcode Encoding Details:")
                print(f"      Total modules: {plan['total_modules']}")
                print(f"      Content width: {plan['content_width_mm']:.2f} mm")
                print(f"      Total width: {plan['total_width_mm']:.2f} mm")

                # Save the SVG
                svg_file = f"barcode_item_{item.id}_{item.item_code}.svg"
                with open(svg_file, 'w') as f:
                    f.write(svg)
                print(f"      SVG saved to: {svg_file}")

            except Exception as e:
                print(f"\n    SVG generation: ✗ Error: {e}")
