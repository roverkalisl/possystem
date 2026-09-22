#!/usr/bin/env python3
"""
Safely add the barcode field to the Item table without running full migrations.
This is a targeted fix for the missing column issue.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from django.db import connection

print("\n" + "="*80)
print("Adding barcode column to pos_item table")
print("="*80 + "\n")

cursor = connection.cursor()

# Check if the column already exists
cursor.execute("PRAGMA table_info(pos_item);")
columns = {col[1]: col for col in cursor.fetchall()}

if 'barcode' in columns:
    print("✓ barcode column already exists in pos_item table")
else:
    print("✗ barcode column does NOT exist, adding it now...\n")

    try:
        # Add the barcode column
        # Note: SQLite doesn't allow adding UNIQUE to existing tables with data,
        # so we add as nullable text. The model definition enforces uniqueness.
        cursor.execute("""
            ALTER TABLE pos_item
            ADD COLUMN barcode varchar(80) NULL
        """)
        print("✓ Successfully added barcode column (varchar(80), NULL)")
        print("  - max_length: 80")
        print("  - allow_null: True")
        print("  - blank: True")
        print("  - unique: enforced by model and code logic")

    except Exception as e:
        print(f"✗ Error adding barcode column: {e}")
        sys.exit(1)

# Verify the column was added
cursor.execute("PRAGMA table_info(pos_item);")
columns = {col[1]: col for col in cursor.fetchall()}

if 'barcode' in columns:
    print("\n✓ Verification successful: barcode column now exists")
    barcode_info = columns['barcode']
    print(f"  Column index: {barcode_info[0]}")
    print(f"  Name: {barcode_info[1]}")
    print(f"  Type: {barcode_info[2]}")
else:
    print("\n✗ Verification failed: barcode column still missing")
    sys.exit(1)
