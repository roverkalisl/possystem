#!/usr/bin/env python3
"""Create the missing pos_banktransaction table from the model."""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.core.management import call_command

print("\n" + "="*80)
print("CREATING MISSING BANKTRANSACTION TABLE")
print("="*80 + "\n")

cursor = connection.cursor()

# Check if table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pos_banktransaction'")
if cursor.fetchone():
    print("✓ pos_banktransaction table already exists")
else:
    print("✗ pos_banktransaction table missing\n")
    print("Attempting to create via migration 0031...\n")

    # Mark migration 0031 as unapplied and run it
    cursor.execute("DELETE FROM django_migrations WHERE app='pos' AND name='0031_bankaccount_banktransaction_bankledgerentry'")

    try:
        call_command('migrate', 'pos', '0031_bankaccount_banktransaction_bankledgerentry', verbosity=2)
        print("\n✓ Migration 0031 applied")
    except Exception as e:
        print(f"\nError applying migration: {e}")
        print("\nTrying remaining migrations...\n")

        # Try to apply all remaining migrations
        try:
            call_command('migrate', 'pos', verbosity=2)
        except Exception as e2:
            print(f"Error: {e2}")

# Final verification
cursor.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND name LIKE 'pos_%'
    ORDER BY name
""")
tables = [row[0] for row in cursor.fetchall()]

print(f"\n" + "="*80)
print(f"FINAL TABLE COUNT: {len(tables)}")
print("="*80 + "\n")

for table in sorted(tables):
    print(f"  • {table}")

# Check for critical tables
critical = ['pos_banktransaction', 'pos_bankledgerentry', 'pos_bankaccount']
found = [t for t in critical if t in tables]
missing = [t for t in critical if t not in tables]

if missing:
    print(f"\n✗ Still missing: {missing}")
else:
    print(f"\n✓ All banking tables created successfully")
