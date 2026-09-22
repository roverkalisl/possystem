#!/usr/bin/env python3
"""Create missing pos tables by running migrations without fake."""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from django.db import connection
from django.core.management import call_command

print("\n" + "="*80)
print("CREATING MISSING POS TABLES")
print("="*80 + "\n")

# First, clear the pos migrations from django_migrations table
cursor = connection.cursor()

cursor.execute("DELETE FROM django_migrations WHERE app = 'pos'")
print("✓ Cleared pos migrations from tracking table\n")

# Also clear sessions since we created it manually
cursor.execute("DELETE FROM django_migrations WHERE app = 'sessions'")
print("✓ Cleared sessions migration from tracking table\n")

print("Now running migrations to create tables...\n")

# Run pos migrations
try:
    call_command('migrate', 'pos', verbosity=2)
    print("\n✓ pos migrations applied successfully")
except Exception as e:
    print(f"\n✗ Error: {e}")

print("\nVerifying tables...\n")

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'pos_%' ORDER BY name;")
tables = [row[0] for row in cursor.fetchall()]

print(f"pos tables found: {len(tables)}")
for table in tables:
    print(f"  • {table}")

# Check for critical missing tables
critical = ['pos_banktransaction', 'pos_item', 'pos_sale', 'pos_saleitem']
missing = [t for t in critical if t not in tables]

if missing:
    print(f"\n⚠ Missing critical tables: {missing}")
else:
    print("\n✓ All critical tables exist")
