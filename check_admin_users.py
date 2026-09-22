#!/usr/bin/env python3
"""
Check existing admin/superuser accounts in the database.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from django.contrib.auth.models import User

print("\n" + "="*80)
print("EXISTING USER ACCOUNTS")
print("="*80 + "\n")

users = User.objects.all()
print(f"Total users: {users.count()}\n")

if users.exists():
    print("Users in database:")
    for user in users:
        status = []
        if user.is_superuser:
            status.append("SUPERUSER")
        if user.is_staff:
            status.append("STAFF")
        if user.is_active:
            status.append("ACTIVE")
        else:
            status.append("INACTIVE")

        status_str = " | ".join(status)
        print(f"  • Username: {user.username}")
        print(f"    Email: {user.email}")
        print(f"    Status: {status_str}\n")
else:
    print("No users found in database.\n")

print("="*80)
print("LOGIN INSTRUCTIONS")
print("="*80 + "\n")

if users.filter(is_superuser=True).exists():
    admin = users.filter(is_superuser=True).first()
    print(f"✓ Superuser found: {admin.username}")
    print(f"\nTo log in:")
    print(f"  1. Go to: http://localhost:8000/login/")
    print(f"  2. Username: {admin.username}")
    print(f"  3. Enter your password")
    print(f"  4. Click Login")
    print(f"\nAfter login, access the test page:")
    print(f"  http://localhost:8000/barcode/test/standard/1000000073/\n")
else:
    print("⚠ No superuser found in database.")
    print("\nYou can:")
    print("  1. Create a new superuser with: python manage.py createsuperuser")
    print("  2. Or use Django admin directly: http://localhost:8000/admin/\n")
