#!/usr/bin/env python3
"""Apply banking migrations starting from 0031."""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from django.db import connection
from django.core.management import call_command

print("\n" + "="*80)
print("APPLYING BANKING MIGRATIONS (0031+)")
print("="*80 + "\n")

cursor = connection.cursor()

# Remove 0031+ from migrations table so they can be applied
print("Removing 0031+ migrations from tracking to reapply them...\n")
cursor.execute("DELETE FROM django_migrations WHERE app = 'pos' AND name >= '0031'")

print("Applying migrations 0031 onward...\n")
try:
    call_command('migrate', 'pos', verbosity=2)
    print("\n✓ Migrations applied successfully")
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("VERIFICATION")
print("="*80 + "\n")

cursor.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND name LIKE 'pos_%'
    ORDER BY name
""")
final_tables = [row[0] for row in cursor.fetchall()]

print(f"Final table count: {len(final_tables)}\n")

critical = ['pos_banktransaction', 'pos_bankledgerentry', 'pos_bankaccount']
for table in critical:
    status = "✓" if table in final_tables else "✗"
    print(f"{status} {table}")

print()
