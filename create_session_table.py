#!/usr/bin/env python3
"""
Create the django_session table directly.
Minimal intervention - only creates missing table needed for login.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from django.db import connection

print("\n" + "="*80)
print("CREATING DJANGO SESSION TABLE")
print("="*80 + "\n")

cursor = connection.cursor()

# Check if session table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='django_session'")
if cursor.fetchone():
    print("✓ django_session table already exists")
else:
    print("✗ django_session table missing, creating it...\n")

    # Create the session table
    cursor.execute("""
        CREATE TABLE django_session (
            session_key VARCHAR(40) PRIMARY KEY,
            session_data TEXT NOT NULL,
            expire_date DATETIME NOT NULL
        )
    """)

    # Create index on expire_date for session cleanup
    cursor.execute("""
        CREATE INDEX django_session_expire_date_idx ON django_session (expire_date)
    """)

    print("✓ Session table created successfully")

# Verify it exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='django_session'")
if cursor.fetchone():
    print("✓ Verification: django_session table now exists\n")
    print("="*80)
    print("READY TO LOGIN")
    print("="*80 + "\n")
    print("Go to: http://localhost:8000/login/")
    print("Username: __diag_test_user__")
    print("Password: TestPass123\n")
else:
    print("✗ Failed to create session table")
    sys.exit(1)
