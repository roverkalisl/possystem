#!/usr/bin/env python3
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from django.db import connection

cursor = connection.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = [row[0] for row in cursor.fetchall()]

print(f"\nTables in database: {len(tables)}")
for table in tables:
    print(f"  - {table}")

# Check if pos_item table exists and has a barcode column
if 'pos_item' in tables:
    print(f"\npos_item table exists. Checking columns:")
    cursor.execute("PRAGMA table_info(pos_item);")
    columns = cursor.fetchall()
    for col in columns:
        col_name = col[1]
        col_type = col[2]
        print(f"  - {col_name} ({col_type})")

    has_barcode = any(col[1] == 'barcode' for col in columns)
    print(f"\n  Barcode column: {'✓ YES' if has_barcode else '✗ NO'}")
else:
    print("\npos_item table does NOT exist")
