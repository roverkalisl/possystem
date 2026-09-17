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


def code128_svg(value, width=360, height=90):
    value = str(value or "")
    if not value or any(ord(char) < 32 or ord(char) > 126 for char in value):
        raise ValueError("Barcode value must contain printable ASCII characters.")

    codes = [104] + [ord(char) - 32 for char in value]
    codes.append((104 + sum(index * code for index, code in enumerate(codes, start=1))) % 103)
    patterns = [CODE128_PATTERNS[code] for code in codes] + [CODE128_PATTERNS[106]]
    total_modules = sum(sum(int(width) for width in pattern) for pattern in patterns)
    scale = width / total_modules
    x = 0
    bars = []
    for pattern in patterns:
        for index in range(0, len(pattern), 2):
            bar_width = int(pattern[index]) * scale
            if bar_width > 0:
                bars.append(f'<rect x="{x:.2f}" y="0" width="{bar_width:.2f}" height="{height}"/>')
            x += int(pattern[index]) * scale
            if index + 1 < len(pattern):
                x += int(pattern[index + 1]) * scale

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="Barcode {value}">'
        f'<g fill="#000">{"".join(bars)}</g></svg>'
    )