#!/usr/bin/env python3
"""
Fix migration state by marking already-applied migrations as faked.
This aligns Django's migration table with actual database state.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader

print("\n" + "="*80)
print("FIXING MIGRATION STATE")
print("="*80 + "\n")

loader = MigrationLoader(None, ignore_no_migrations=True)
executor = MigrationExecutor(connection)

# Get all migrations
all_migrations = loader.disk_migrations

print("Step 1: Check current migration state")
print(f"  Migrations on disk: {len(all_migrations)}\n")

# Mark all pos app migrations as faked (they're already in DB)
print("Step 2: Marking existing pos migrations as faked...\n")

pos_migrations = [
    ('pos', '0001_initial'),
    ('pos', '0003_supplieradvance_suppliersettlement_purchaseorder'),
    ('pos', '0004_rename_phone_supplier_phone_1_and_more'),
    ('pos', '0005_alter_stocktransaction_options_and_more'),
    ('pos', '0006_grn_grnitem'),
    ('pos', '0007_purchaseorderitem_item'),
    ('pos', '0008_alter_grnitem_item'),
    ('pos', '0009_userlog_auditlog'),
    ('pos', '0010_remove_auditlog_pos_auditlog_timestamp_idx_and_more'),
    ('pos', '0011_alter_purchaseorder_status'),
    ('pos', '0012_projectexpense_original_expense_and_more'),
    ('pos', '0013_grnitem_allocation_project_grnitem_allocation_type_and_more'),
    ('pos', '0014_quotation_quotationitem'),
    ('pos', '0015_projectbudget_projectbudgetline_projectcostactual'),
    ('pos', '0016_glcreationlog'),
    ('pos', '0017_license_renewal'),
    ('pos', '0018_payrollentry_payrollallocation_payrollglentry_and_more'),
    ('pos', '0019_employee_bank_account_no_employee_bank_name_and_more'),
    ('pos', '0020_payrollallowance_payrolldeduction_salaryadvance'),
    ('pos', '0021_payrollentry_payslip_no'),
    ('pos', '0022_employee_contract_based_employee_joining_date_and_more'),
    ('pos', '0023_payrollentry_salary_month_and_more'),
    ('pos', '0024_glcreationlog_status'),
    ('pos', '0025_salesreturn_status'),
    ('pos', '0026_payrollentry_epf_expense_gl_account_and_more'),
    ('pos', '0027_employee_default_project_employee_default_supervisor_and_more'),
    ('pos', '0028_backupsettings_backuprecord_restorelog'),
    ('pos', '0029_backuprecord_google_drive_file_id_and_more'),
    ('pos', '0030_backupexecutionlock'),
    ('pos', '0031_bankaccount_banktransaction_bankledgerentry'),
    ('pos', '0032_banktransaction_contra_gl_account_and_more'),
    ('pos', '0033_banktransaction_source_sale_item_barcode_and_more'),
    ('pos', '0034_salerecovery_bank_account_and_more'),
]

cursor = connection.cursor()

for app, migration in pos_migrations:
    try:
        cursor.execute(
            "SELECT 1 FROM django_migrations WHERE app = %s AND name = %s",
            [app, migration]
        )
        if not cursor.fetchone():
            # Insert migration record
            cursor.execute(
                "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, datetime('now'))",
                [app, migration]
            )
            print(f"  ✓ Marked {app}.{migration} as applied")
    except Exception as e:
        print(f"  ! {app}.{migration}: {e}")

print("\n" + "="*80)
print("STEP 3: RUN REMAINING MIGRATIONS")
print("="*80 + "\n")
print("Now run:")
print("  python manage.py migrate\n")
print("This will apply:")
print("  - Django auth, sessions, admin tables")
print("  - Any remaining pos migrations\n")
