#!/usr/bin/env python3
"""
Reset the password for the existing superuser account.
Local testing only - safe operation, no data loss.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from django.contrib.auth.models import User

print("\n" + "="*80)
print("SUPERUSER PASSWORD RESET")
print("="*80 + "\n")

# Get the superuser
try:
    admin = User.objects.get(username='__diag_test_user__')
    print(f"Found superuser: {admin.username}")
    print(f"Email: {admin.email or '(none)'}\n")
except User.DoesNotExist:
    print("ERROR: Superuser '__diag_test_user__' not found")
    sys.exit(1)

# Set temporary password
temp_password = "TestPass123"
admin.set_password(temp_password)
admin.save()

print("✓ Password reset successfully\n")
print("="*80)
print("LOGIN CREDENTIALS (LOCAL TESTING ONLY)")
print("="*80 + "\n")
print(f"Username: __diag_test_user__")
print(f"Password: {temp_password}\n")
print("="*80)
print("NEXT STEPS")
print("="*80 + "\n")
print("1. Go to: http://localhost:8000/login/")
print("2. Enter credentials above")
print("3. Click Login")
print("4. After login, access: http://localhost:8000/barcode/test/standard/1000000073/\n")
