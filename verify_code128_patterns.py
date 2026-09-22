#!/usr/bin/env python3
"""
Verify CODE128_PATTERNS against the official Code 128 specification.
This ensures the barcode library has correct encoding patterns.
"""

# Official Code 128 patterns from specification (Subset B - default, printable ASCII)
# Each pattern is a sequence of bars and spaces (1 = bar, 0 = space), encoded as a string
OFFICIAL_CODE128_PATTERNS = (
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

# From the actual codebase
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from pos.barcode_services import CODE128_PATTERNS

def verify_patterns():
    print("\n" + "="*80)
    print("CODE 128 PATTERN VERIFICATION")
    print("="*80 + "\n")

    print(f"Pattern table size in code: {len(CODE128_PATTERNS)}")
    print(f"Expected size: {len(OFFICIAL_CODE128_PATTERNS)}")

    if len(CODE128_PATTERNS) != len(OFFICIAL_CODE128_PATTERNS):
        print(f"❌ MISMATCH: Pattern table has {len(CODE128_PATTERNS)} entries, expected {len(OFFICIAL_CODE128_PATTERNS)}")
    else:
        print(f"✓ Pattern table size matches")

    # Compare each pattern
    mismatches = []
    for i, (code_pattern, official_pattern) in enumerate(zip(CODE128_PATTERNS, OFFICIAL_CODE128_PATTERNS)):
        if code_pattern != official_pattern:
            mismatches.append((i, code_pattern, official_pattern))

    if mismatches:
        print(f"\n❌ Found {len(mismatches)} PATTERN MISMATCHES:\n")
        for idx, code_pat, official_pat in mismatches:
            char = chr(idx + 32) if 32 <= idx + 32 <= 126 else "?"
            print(f"  Index {idx} (char '{char}'):")
            print(f"    Code:     {code_pat}")
            print(f"    Official: {official_pat}")
    else:
        print(f"\n✓ All {len(CODE128_PATTERNS)} patterns match the official specification!")

    # Additional verification: Check special codes
    print(f"\n" + "="*80)
    print("SPECIAL CODES VERIFICATION")
    print("="*80 + "\n")

    # Code 104 = START CODE B (should be 211214)
    print(f"START CODE (104): {CODE128_PATTERNS[104]}")
    print(f"  Expected: 211214")
    print(f"  {'✓' if CODE128_PATTERNS[104] == '211214' else '❌'}")

    # Code 106 = STOP CODE
    print(f"\nSTOP CODE (106): {CODE128_PATTERNS[106]}")
    print(f"  Expected: 2331112")
    print(f"  {'✓' if CODE128_PATTERNS[106] == '2331112' else '❌'}")

    # Verify that patterns have correct bar count
    print(f"\n" + "="*80)
    print("BAR/SPACE PATTERN ANALYSIS")
    print("="*80 + "\n")

    bar_counts = {}
    for i, pattern in enumerate(CODE128_PATTERNS):
        bar_count = sum(int(module) for module in pattern)
        if bar_count not in bar_counts:
            bar_counts[bar_count] = []
        bar_counts[bar_count].append(i)

    print("Distribution of bar counts in patterns:")
    for bar_count in sorted(bar_counts.keys()):
        indices = bar_counts[bar_count]
        print(f"  {bar_count} bars: {len(indices)} patterns")
        if len(indices) <= 5:
            print(f"    Indices: {indices}")

if __name__ == "__main__":
    verify_patterns()
