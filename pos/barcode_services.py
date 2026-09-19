from django.db import IntegrityError, transaction

from .models import Item


CODE128_PATTERNS = (
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213",
    "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132",
    "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211",
    "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
    "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331",
    "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
    "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214",
    "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
    "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
    "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141",
    "114131", "311141", "411131", "211412", "211214", "211232", "2331112",
)


def generate_barcode_for_item(item_id):
    with transaction.atomic():
        item = Item.objects.select_for_update().get(id=item_id)
        if item.barcode:
            return item, False

        barcode = str(item.item_code or "").strip()
        if not barcode:
            raise ValueError("Item code is required to generate a barcode.")
        if Item.objects.filter(barcode=barcode).exclude(id=item.id).exists():
            raise ValueError("The item code is already used as another item's barcode.")

        item.barcode = barcode
        try:
            item.save(update_fields=["barcode"])
        except IntegrityError as exc:
            raise ValueError("The barcode is already assigned to another item.") from exc
        return item, True


def generate_missing_barcodes():
    result = {"processed": 0, "generated": 0, "skipped": 0, "errors": []}
    item_ids = Item.objects.filter(barcode__isnull=True).values_list("id", flat=True)
    for item_id in item_ids.iterator():
        result["processed"] += 1
        try:
            _, created = generate_barcode_for_item(item_id)
        except (Item.DoesNotExist, ValueError) as exc:
            result["errors"].append(str(exc))
        else:
            result["generated" if created else "skipped"] += 1
    return result


def _code128_plan(value, module_width_mm, height_mm, quiet_zone_modules):
    """Compute the Code 128 (subset B) bar layout shared by rendering and diagnostics."""
    value = str(value or "")
    if not value or any(ord(char) < 32 or ord(char) > 126 for char in value):
        raise ValueError("Barcode value must contain printable ASCII characters.")

    data_codes = [ord(char) - 32 for char in value]
    # Checksum = start code value + sum(position * code value), position 1-indexed over data chars only.
    checksum = (104 + sum((position + 1) * code for position, code in enumerate(data_codes))) % 103
    codes = [104] + data_codes + [checksum]
    patterns = [CODE128_PATTERNS[code] for code in codes] + [CODE128_PATTERNS[106]]

    total_modules = sum(sum(int(module) for module in pattern) for pattern in patterns)
    quiet_zone_mm = quiet_zone_modules * module_width_mm
    content_width_mm = total_modules * module_width_mm
    total_width_mm = content_width_mm + (2 * quiet_zone_mm)

    return {
        "value": value,
        "patterns": patterns,
        "total_modules": total_modules,
        "module_width_mm": module_width_mm,
        "height_mm": height_mm,
        "quiet_zone_modules": quiet_zone_modules,
        "quiet_zone_mm": quiet_zone_mm,
        "content_width_mm": content_width_mm,
        "total_width_mm": total_width_mm,
    }


def code128_metrics(value, module_width_mm=0.33, height_mm=18, quiet_zone_modules=10):
    """Return the physical dimensions (mm) of the Code 128 barcode for `value` without rendering it."""
    plan = _code128_plan(value, module_width_mm, height_mm, quiet_zone_modules)
    plan.pop("patterns")
    return plan


def code128_svg(value, module_width_mm=0.33, height_mm=18, quiet_zone_modules=10):
    """Render a scanner-readable Code 128 (subset B) barcode as an SVG string.

    Dimensions are expressed in millimetres so the barcode keeps its true
    proportions no matter how the browser renders or prints the page, and a
    quiet zone (min. 10 modules) is reserved on both sides as required by the
    Code 128 spec for reliable decoding.
    """
    plan = _code128_plan(value, module_width_mm, height_mm, quiet_zone_modules)
    value = plan["value"]
    total_width_mm = plan["total_width_mm"]

    x = plan["quiet_zone_mm"]
    bars = []
    for pattern in plan["patterns"]:
        is_bar = True
        for module in pattern:
            bar_width = int(module) * module_width_mm
            if is_bar and bar_width > 0:
                bars.append(f'<rect x="{x:.3f}" y="0" width="{bar_width:.3f}" height="{height_mm}"/>')
            x += bar_width
            is_bar = not is_bar

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_width_mm:.3f}mm" height="{height_mm}mm" '
        f'viewBox="0 0 {total_width_mm:.3f} {height_mm}" preserveAspectRatio="xMidYMid meet" '
        f'shape-rendering="crispEdges" role="img" aria-label="Barcode {value}">'
        f'<rect x="0" y="0" width="{total_width_mm:.3f}" height="{height_mm}" fill="#fff"/>'
        f'<g fill="#000">{"".join(bars)}</g></svg>'
    )