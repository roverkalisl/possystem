#!/usr/bin/env python3
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from pos.models import Item

print(f"\nTotal items in database: {Item.objects.count()}")

if Item.objects.exists():
    print("\nFirst 30 items:")
    for item in Item.objects.all()[:30]:
        print(f"  {item.id}: {item.name} (Code: {item.item_code}, Barcode: {item.barcode})")
else:
    print("No items found in database")

# Also check count in SQL
from django.db import connection
cursor = connection.cursor()
cursor.execute("SELECT COUNT(*) FROM pos_item")
count = cursor.fetchone()[0]
print(f"\nDirect SQL count: {count}")
