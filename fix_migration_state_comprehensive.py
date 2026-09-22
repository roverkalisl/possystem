#!/usr/bin/env python3
"""Comprehensively fix migration state to match database reality."""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from django.db import connection
from django.db.migrations.loader import MigrationLoader

print("\n" + "="*80)
print("COMPREHENSIVE MIGRATION FIX")
print("="*80 + "\n")

loader = MigrationLoader(None, ignore_no_migrations=True)

# Get all pos migrations
pos_migrations = sorted([
    (name.split('_')[0], name) for app, name in loader.disk_migrations.keys() if app == 'pos'
], key=lambda x: int(x[0]))

cursor = connection.cursor()

print("Step 1: Clear all pos migrations")
cursor.execute("DELETE FROM django_migrations WHERE app = 'pos'")
print(f"  ✓ Cleared\n")

print("Step 2: Mark migrations 0001-0030 as applied (already in DB)")
for num, migration_name in pos_migrations[:30]:  # First 30 migrations
    cursor.execute(
        "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, datetime('now'))",
        ['pos', migration_name]
    )
    print(f"  ✓ {num}: {migration_name}")

print("\nStep 3: Check which tables exist in DB")
cursor.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND name LIKE 'pos_%'
    ORDER BY name
""")
existing_tables = {row[0] for row in cursor.fetchall()}
print(f"  Found {len(existing_tables)} pos tables\n")

print("Step 4: Determine which migrations to apply")
from pos.models import (
    BankAccount, BankTransaction, BankLedgerEntry,
    SaleRecovery, PIAllocationBatch, PIAllocationLine, PICommonCostEntry
)

# Check if banking tables exist
banking_tables_exist = 'pos_bankaccount' in existing_tables and \
                      'pos_banktransaction' in existing_tables and \
                      'pos_bankledgerentry' in existing_tables

if not banking_tables_exist:
    print("  ✗ Banking tables missing - need to apply migrations 0031+\n")
    print("Step 5: Apply migrations 0031 onward...\n")

    from django.core.management import call_command
    try:
        call_command('migrate', 'pos', verbosity=2)
        print("\n  ✓ Migrations applied successfully")
    except Exception as e:
        print(f"\n  ✗ Error: {e}")
else:
    print("  ✓ All required tables exist\n")
    # Still mark remaining migrations as applied
    print("Step 5: Mark remaining migrations as applied...\n")
    for num, migration_name in pos_migrations[30:]:
        try:
            cursor.execute(
                "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, datetime('now'))",
                ['pos', migration_name]
            )
            print(f"  ✓ {num}: {migration_name}")
        except:
            pass  # Already exists

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
