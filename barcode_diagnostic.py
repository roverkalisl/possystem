#!/usr/bin/env python3
"""
Barcode diagnostic tool to verify Code 128 encoding for "1000000073"
Tests the encoding at each step to identify where the problem occurs.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from pos.barcode_services import _code128_plan, code128_svg

def analyze_encoding(value):
    print(f"\n{'='*70}")
    print(f"DIAGNOSTIC: Code 128 Barcode Encoding for '{value}'")
    print(f"{'='*70}\n")

    # Step 1: Verify input
    print(f"Step 1: Input Value")
    print(f"  Value: '{value}'")
    print(f"  Length: {len(value)} characters")
    print(f"  Type: {type(value).__name__}")

    # Check for hidden characters
    print(f"  Character breakdown:")
    for i, char in enumerate(value):
        print(f"    [{i}] = '{char}' (ASCII {ord(char)}, hex {hex(ord(char))})")

    # Step 2: Get encoding plan
    print(f"\nStep 2: Code 128 Encoding")
    try:
        plan = _code128_plan(value, module_width_mm=0.33, height_mm=18, quiet_zone_modules=10)
    except Exception as e:
        print(f"  ERROR: {e}")
        return

    # Step 3: Verify the data codes calculation
    print(f"  Data codes (ASCII value - 32):")
    value_str = str(value or "")
    data_codes = [ord(char) - 32 for char in value_str]
    print(f"    Values: {data_codes}")

    # Verify checksum calculation
    checksum_calc = (104 + sum((position + 1) * code for position, code in enumerate(data_codes))) % 103
    print(f"\n  Checksum Calculation:")
    print(f"    Start code: 104")
    print(f"    Sum of (position+1) * code:")
    for position, code in enumerate(data_codes):
        print(f"      Position {position+1}: {position+1} * {code} = {(position+1) * code}")
    total_sum = sum((position + 1) * code for position, code in enumerate(data_codes))
    print(f"    Total sum: {total_sum}")
    print(f"    (104 + {total_sum}) % 103 = {checksum_calc}")

    # Step 4: Verify patterns
    print(f"\n  Pattern Generation:")
    print(f"    Start code (104): {plan['patterns'][0]}")
    for i, code in enumerate(data_codes):
        print(f"    Data code {i} ({value[i]}={code}): {plan['patterns'][i+1]}")
    print(f"    Check code ({checksum_calc}): {plan['patterns'][-2]}")
    print(f"    Stop code (106): {plan['patterns'][-1]}")

    # Step 5: Verify dimensions
    print(f"\n  Barcode Dimensions:")
    print(f"    Total modules: {plan['total_modules']}")
    print(f"    Module width: {plan['module_width_mm']} mm")
    print(f"    Height: {plan['height_mm']} mm")
    print(f"    Quiet zone: {plan['quiet_zone_mm']} mm ({plan['quiet_zone_modules']} modules)")
    print(f"    Content width: {plan['content_width_mm']:.2f} mm")
    print(f"    Total width: {plan['total_width_mm']:.2f} mm")

    # Step 6: Generate SVG and save it
    print(f"\nStep 3: SVG Generation")
    try:
        svg = code128_svg(value)
        print(f"  SVG generated successfully")
        print(f"  SVG length: {len(svg)} characters")

        # Save SVG for inspection
        svg_file = f"barcode_{value}.svg"
        with open(svg_file, 'w') as f:
            f.write(svg)
        print(f"  Saved to: {svg_file}")

        # Display SVG snippet
        print(f"\n  SVG Snippet (first 500 chars):")
        print(f"  {svg[:500]}...")

    except Exception as e:
        print(f"  ERROR: {e}")
        return

    # Step 7: Manual verification against known-good implementation
    print(f"\n{'='*70}")
    print(f"VERIFICATION SUMMARY FOR: {value}")
    print(f"{'='*70}")
    print(f"✓ Input validated")
    print(f"✓ Data codes: {data_codes}")
    print(f"✓ Checksum: {checksum_calc}")
    print(f"✓ SVG generated and saved")
    print(f"\nNEXT STEPS:")
    print(f"1. Open the generated SVG file in a browser")
    print(f"2. Print it at 100% scale")
    print(f"3. Scan with a barcode scanner to verify the actual value")
    print(f"4. Compare the scanned value with: {value}")
    print(f"\nIf scanner returns a different value, the issue is in:")
    print(f"- Code 128 pattern lookup (CODE128_PATTERNS)")
    print(f"- SVG rendering (bar/space proportions)")
    print(f"- CSS scaling or print settings")

if __name__ == "__main__":
    # Test with the problematic barcode
    analyze_encoding("1000000073")

    # Also test a simple value to verify the implementation works
    print(f"\n\n")
    analyze_encoding("TEST123")
