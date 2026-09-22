#!/usr/bin/env python3
"""Mark session migration as applied since table already exists."""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from django.db import connection

cursor = connection.cursor()

# Mark sessions migration as applied
cursor.execute(
    "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, datetime('now'))",
    ['sessions', '0001_initial']
)

print("✓ Marked sessions.0001_initial as applied")
