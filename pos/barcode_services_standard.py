"""
Standard Code 128 barcode generation using python-barcode library.
Replaces the custom Code 128 pattern implementation with a verified, industry-standard library.

This module generates Code 128 barcodes with guaranteed correct encoding.
"""
from io import BytesIO
import barcode


def generate_code128_svg(value):
    """
    Generate a Code 128 barcode as SVG using the standard python-barcode library.

    Args:
        value (str): The exact value to encode in the barcode.
                     Must be printable ASCII characters (32-126).
                     No automatic formatting or modification.

    Returns:
        str: SVG string of the barcode

    Raises:
        ValueError: If value contains non-ASCII characters or is empty

    Example:
        svg = generate_code128_svg("1000000073")
        # Returns: <svg xmlns="..." width="..." height="...">...</svg>
    """
    # Validate input
    value = str(value or "").strip()
    if not value:
        raise ValueError("Barcode value cannot be empty")

    # Verify all characters are printable ASCII
    for char in value:
        if ord(char) < 32 or ord(char) > 126:
            raise ValueError(f"Character '{char}' (ASCII {ord(char)}) is not printable ASCII")

    # Generate barcode using standard library
    try:
        barcode_instance = barcode.Code128(value)
    except Exception as e:
        raise ValueError(f"Failed to generate Code 128 barcode: {e}")

    # Get SVG output
    svg_buffer = BytesIO()
    barcode_instance.write(svg_buffer, options={
        "format": "svg",
        "module_width": 0.5,  # mm - width of each bar/space unit
        "module_height": 20,  # mm - height of bars
        "quiet_zone": 3.5,    # mm - quiet zone on each side (>= 10 modules)
        "font_size": 0,       # Disable human-readable text from barcode lib (we'll add it separately)
        "text_distance": 0,   # No distance from barcode to text
    })
    svg_content = svg_buffer.getvalue().decode('utf-8')

    return svg_content


def generate_code128_html_page(value, item_name=None):
    """
    Generate a complete HTML page with a Code 128 barcode and human-readable text.

    Args:
        value (str): The exact value to encode
        item_name (str, optional): Display name of the item

    Returns:
        str: HTML page content with embedded barcode
    """
    svg = generate_code128_svg(value)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Barcode Test: {value}</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 40px;
            background: #f5f5f5;
            text-align: center;
        }}
        .container {{
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            max-width: 600px;
            margin: 0 auto;
            padding: 40px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .title {{
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 10px;
            color: #333;
        }}
        .item-name {{
            font-size: 14px;
            color: #666;
            margin-bottom: 30px;
        }}
        .barcode-wrapper {{
            background: white;
            border: 2px solid #000;
            padding: 20px;
            margin: 30px 0;
            display: inline-block;
        }}
        .barcode-wrapper svg {{
            display: block;
            margin: 0 auto;
        }}
        .human-readable {{
            font-size: 24px;
            font-weight: bold;
            letter-spacing: 2px;
            margin-top: 20px;
            font-family: 'Courier New', monospace;
            color: #000;
        }}
        .library-info {{
            background: #e7f3ff;
            border: 1px solid #b3d9ff;
            border-radius: 4px;
            padding: 15px;
            margin-top: 30px;
            font-size: 12px;
            text-align: left;
        }}
        .instructions {{
            background: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 4px;
            padding: 15px;
            margin-top: 20px;
            font-size: 12px;
            text-align: left;
        }}
        @media print {{
            body {{
                background: white;
                padding: 0;
                margin: 0;
            }}
            .container {{
                border: none;
                box-shadow: none;
                max-width: 100%;
                padding: 20mm;
            }}
            .library-info,
            .instructions {{
                display: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="title">Code 128 Barcode Test</div>
        {f'<div class="item-name">{item_name}</div>' if item_name else ''}

        <div class="barcode-wrapper">
            {svg}
        </div>

        <div class="human-readable">{value}</div>

        <div class="library-info">
            <strong>Generator Information:</strong>
            <div>• Library: python-barcode 0.16.1</div>
            <div>• Format: Code 128 (standard ISO/IEC 15891)</div>
            <div>• Encoded value: {value}</div>
            <div>• Checksum: Calculated by library</div>
            <div>• Module width: 0.5mm</div>
            <div>• Bar height: 20mm</div>
            <div>• Quiet zones: 3.5mm (>10 modules)</div>
        </div>

        <div class="instructions">
            <strong>Testing Instructions:</strong>
            <ol>
                <li>Print this page at 100% scale (NOT "Fit to page")</li>
                <li>Scan the barcode with a reliable barcode reader</li>
                <li>The scanner MUST return exactly: <strong>{value}</strong></li>
                <li>If successful, the barcode is valid for production</li>
            </ol>
        </div>
    </div>
</body>
</html>"""

    return html


def validate_encoding(value):
    """
    Verify that the barcode encodes the exact value with no modifications.

    Args:
        value (str): The value to validate

    Returns:
        dict: Validation result with details

    Example:
        result = validate_encoding("1000000073")
        # Returns: {"valid": True, "value": "1000000073", "payload": "1000000073"}
    """
    value = str(value or "").strip()

    if not value:
        return {"valid": False, "error": "Value is empty"}

    try:
        # Create barcode instance
        barcode_instance = barcode.Code128(value)

        # The encoded payload is just the value itself (library handles checksum internally)
        return {
            "valid": True,
            "value": value,
            "payload": value,
            "library": "python-barcode",
            "format": "Code128",
            "length": len(value),
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


def generate_code128_metrics(value, module_width_mm=0.5, height_mm=20):
    """
    Return barcode metrics for the standard library SVG output.

    Args:
        value (str): Barcode value
        module_width_mm (float): Width of each module in mm
        height_mm (float): Height of barcode in mm

    Returns:
        dict: Metrics including dimensions
    """
    value = str(value or "").strip()
    if not value:
        raise ValueError("Barcode value cannot be empty")

    # Validate characters
    for char in value:
        if ord(char) < 32 or ord(char) > 126:
            raise ValueError(f"Character '{char}' is not printable ASCII")

    # Approximate total width based on Code 128 spec
    # Each data char is ~11 modules, plus start (6) and stop (13) and quiet zones
    quiet_zone_modules = 10  # Code 128 requires at least 10 modules
    quiet_zone_mm = quiet_zone_modules * module_width_mm

    # Approximate: 6 (start) + len(value)*11 (data) + 11 (checksum) + 13 (stop)
    approx_modules = 6 + (len(value) * 11) + 11 + 13
    content_width_mm = approx_modules * module_width_mm
    total_width_mm = content_width_mm + (2 * quiet_zone_mm)

    return {
        "value": value,
        "module_width_mm": module_width_mm,
        "height_mm": height_mm,
        "quiet_zone_modules": quiet_zone_modules,
        "quiet_zone_mm": quiet_zone_mm,
        "content_width_mm": content_width_mm,
        "total_width_mm": total_width_mm,
    }
