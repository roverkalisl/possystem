#!/usr/bin/env python3
"""Check if Django core tables exist."""
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

print("\nDatabase tables:")
for table in tables:
    print(f"  • {table}")

print("\n" + "="*80)
print("REQUIRED DJANGO TABLES CHECK")
print("="*80 + "\n")

required = {
    'auth_user': 'User authentication',
    'auth_permission': 'Permissions',
    'auth_group': 'User groups',
    'django_session': 'Session storage',
    'django_admin_log': 'Admin action log',
    'django_content_type': 'Content types',
}

for table, description in required.items():
    status = "✓" if table in tables else "✗"
    print(f"{status} {table:30} ({description})")

if 'auth_user' not in tables:
    print("\n⚠ Auth tables missing! Creating them...\n")
    os.system("python manage.py migrate auth --run-syncdb")
    os.system("python manage.py migrate contenttypes --run-syncdb")
    os.system("python manage.py migrate admin --run-syncdb")
