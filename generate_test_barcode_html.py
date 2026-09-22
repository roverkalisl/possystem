#!/usr/bin/env python3
"""
Generate a standalone HTML file with a clean Code 128 barcode for "1000000073"
that can be printed and scanned to verify the implementation.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from pos.barcode_services import code128_svg, code128_metrics

# Test values
test_values = [
    "1000000073",  # The problematic barcode
    "TEST123",     # A simple test
    "123456789012",  # EAN-13 like
]

html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Code 128 Barcode Test</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            padding: 20px;
            background: #f5f5f5;
        }
        .test-section {
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 30px;
            margin: 20px 0;
            page-break-inside: avoid;
        }
        .title {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 20px;
            text-align: center;
        }
        .subtitle {
            font-size: 14px;
            color: #666;
            text-align: center;
            margin-bottom: 20px;
        }
        .barcode-container {
            text-align: center;
            border: 2px solid #000;
            padding: 15px;
            margin: 20px 0;
            background: white;
        }
        .barcode-container svg {
            display: block;
            margin: 0 auto;
            max-width: 100%;
            height: auto;
        }
        .barcode-value {
            font-size: 28px;
            font-weight: bold;
            letter-spacing: 3px;
            margin-top: 15px;
            font-family: 'Courier New', monospace;
            text-align: center;
        }
        .instructions {
            background: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 4px;
            padding: 15px;
            margin: 20px 0;
            font-size: 14px;
        }
        .metrics {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            padding: 15px;
            margin: 20px 0;
            font-size: 12px;
            font-family: 'Courier New', monospace;
        }
        .metrics div {
            margin: 5px 0;
        }
        @media print {
            body {
                background: white;
                margin: 0;
                padding: 0;
            }
            .test-section {
                margin: 10mm 0;
                page-break-inside: avoid;
            }
            .instructions {
                display: none;
            }
            .metrics {
                display: none;
            }
        }
    </style>
</head>
<body>
"""

for value in test_values:
    try:
        svg = code128_svg(value)
        metrics = code128_metrics(value)

        html_content += f"""
    <div class="test-section">
        <div class="title">Code 128 Barcode Test</div>
        <div class="subtitle">Value: {value}</div>

        <div class="instructions">
            <strong>Instructions for Testing:</strong>
            <ol>
                <li>Print this page at 100% scale (no scaling, no "fit to page")</li>
                <li>Use a reliable barcode scanner to scan each barcode</li>
                <li>The scanner MUST return exactly: <strong>{value}</strong></li>
                <li>If it returns something else (e.g., "1000E00033"), note it as a FAIL</li>
                <li>Compare results with known-good barcode scanners</li>
            </ol>
        </div>

        <div class="barcode-container">
            {svg}
        </div>

        <div class="barcode-value">{value}</div>

        <div class="metrics">
            <div><strong>Encoding Details:</strong></div>
            <div>• Barcode type: Code 128 (Subset B)</div>
            <div>• Value length: {len(value)} characters</div>
            <div>• Module width: {metrics['module_width_mm']} mm</div>
            <div>• Total modules: {metrics['total_modules']}</div>
            <div>• Content width: {metrics['content_width_mm']:.2f} mm</div>
            <div>• Total width (with quiet zones): {metrics['total_width_mm']:.2f} mm</div>
            <div>• Bar height: {metrics['height_mm']} mm</div>
            <div>• Quiet zone: {metrics['quiet_zone_mm']:.2f} mm ({metrics['quiet_zone_modules']} modules)</div>
        </div>
    </div>
"""
    except Exception as e:
        html_content += f"""
    <div class="test-section" style="border-color: #dc3545;">
        <div class="title" style="color: #dc3545;">Error Generating Barcode</div>
        <div class="subtitle">Value: {value}</div>
        <p style="color: #dc3545;">Error: {str(e)}</p>
    </div>
"""

html_content += """
    <div class="test-section">
        <div class="title">Troubleshooting Guide</div>
        <p>If the barcode scans correctly, proceed with bulk printing.</p>
        <p>If the barcode scans incorrectly (scanner returns wrong value):</p>
        <ol>
            <li>Verify the barcode rendering - check if bars are clear and distinct</li>
            <li>Test with multiple barcode scanners (different brands/models)</li>
            <li>Check if there's a CSS issue scaling the barcode (should print at true mm size)</li>
            <li>Verify the Code 128 pattern library is correct</li>
            <li>Check if SVG rendering is corrupting the bar/space ratios</li>
            <li>Ensure print settings use 100% scale (not "Fit to page")</li>
        </ol>
    </div>
</body>
</html>
"""

# Write the HTML file
output_file = "barcode_test_suite.html"
with open(output_file, 'w') as f:
    f.write(html_content)

print(f"\n✓ Generated test barcode HTML file: {output_file}")
print(f"\nHow to use:")
print(f"  1. Open {output_file} in a web browser")
print(f"  2. Print each barcode at 100% scale")
print(f"  3. Scan with a barcode scanner")
print(f"  4. Verify each scanner returns the correct value")
print(f"\nThe main test barcode value is: 1000000073")
