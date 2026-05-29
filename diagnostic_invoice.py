#!/usr/bin/env python
"""
Diagnostic script to analyze invoice INV00041 return calculations
"""
import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from pos.models import Sale, SaleItem, SalesReturn
from django.db.models import Sum

# Find the invoice
invoice_no = 'INV00041'
try:
    sale = Sale.objects.get(invoice_no=invoice_no)
except Sale.DoesNotExist:
    print(f"Invoice {invoice_no} not found!")
    exit(1)

print(f"\n{'='*80}")
print(f"INVOICE DIAGNOSTIC REPORT: {invoice_no}")
print(f"{'='*80}")

print(f"\nBasic Info:")
print(f"  Sale ID: {sale.id}")
print(f"  Invoice No: {sale.invoice_no}")
print(f"  Created At: {sale.created_at}")
print(f"  Created By: {sale.created_by}")
print(f"  Total: {sale.total}")
print(f"  Discount: {sale.discount}")
print(f"  Grand Total: {sale.grand_total}")

print(f"\n{'='*80}")
print(f"SALE ITEMS ANALYSIS:")
print(f"{'='*80}")

total_gross = Decimal("0")
total_returns = Decimal("0")
total_cogs = Decimal("0")
total_returned_stock_value = Decimal("0")

for idx, sale_item in enumerate(sale.sale_items.all(), 1):
    print(f"\n--- Item #{idx} ---")
    print(f"Item Code: {sale_item.item.item_code}")
    print(f"Item Name: {sale_item.item.name}")
    print(f"Cost Price: {sale_item.item.cost_price}")
    print(f"Sale Price: {sale_item.price}")
    print(f"Qty Sold: {sale_item.qty}")
    print(f"Amount: {sale_item.amount}")
    print(f"Net Amount: {sale_item.net_amount}")
    
    # Get returns
    returns = SalesReturn.objects.filter(sale_item=sale_item)
    total_returned_qty = returns.aggregate(total=Sum("qty"))["total"] or Decimal("0")
    
    print(f"\nReturn Analysis:")
    print(f"  Total Returns for this item: {len(returns)}")
    print(f"  Total Returned Qty: {total_returned_qty}")
    
    if len(returns) > 0:
        print(f"\n  Return Details:")
        for i, ret in enumerate(returns, 1):
            print(f"    Return #{i}:")
            print(f"      Return No: {ret.return_no}")
            print(f"      Qty: {ret.qty}")
            print(f"      Created At: {ret.created_at}")
            print(f"      Return Type: {ret.return_type}")
            if ret.reason:
                print(f"      Reason: {ret.reason}")
    
    # Calculate values
    sold_qty = Decimal(str(sale_item.qty or 0))
    returned_qty = total_returned_qty
    available_qty = sold_qty - returned_qty
    
    print(f"\nCalculations:")
    print(f"  Sold Qty: {sold_qty}")
    print(f"  Returned Qty: {returned_qty}")
    print(f"  Available Qty: {available_qty}")
    
    if sold_qty > 0:
        unit_net = Decimal(str(sale_item.net_amount or 0)) / sold_qty
        print(f"  Unit Net Price: {unit_net}")
        
        # COGS calculation
        item_cost = Decimal(str(sale_item.item.cost_price or 0))
        if available_qty > 0:
            item_cogs = item_cost * available_qty
            print(f"  COGS (for available qty): {item_cogs}")
            total_cogs += item_cogs
        
        # Returned stock value
        if returned_qty > 0:
            returned_stock_value = item_cost * returned_qty
            print(f"  Returned Stock Value (cost * returned_qty): {returned_stock_value}")
            total_returned_stock_value += returned_stock_value
        
        # Gross sale amount
        gross_sale_amount = unit_net * sold_qty
        print(f"  Gross Sale Amount: {gross_sale_amount}")
        total_gross += gross_sale_amount
        
        # Return amount (selling price)
        return_amount = unit_net * returned_qty
        print(f"  Return Amount (selling price): {return_amount}")
        total_returns += return_amount

print(f"\n{'='*80}")
print(f"SUMMARY CALCULATIONS:")
print(f"{'='*80}")
print(f"Total Gross Sales: {total_gross}")
print(f"Total Returns (selling price): {total_returns}")
print(f"Total Net Sales: {sale.grand_total}")
print(f"Total COGS: {total_cogs}")
print(f"Total Returned Stock Value: {total_returned_stock_value}")
print(f"Total Profit: {sale.grand_total - total_cogs}")

print(f"\n{'='*80}")
print(f"EXPECTED vs REPORTED (from daily/monthly report):")
print(f"{'='*80}")
print(f"Net Sale Expected: {sale.grand_total}")
print(f"COGS Expected: {total_cogs}")
print(f"Profit Expected: {sale.grand_total - total_cogs}")
print(f"Returned Stock Value Expected: {total_returned_stock_value}")

print(f"\n{'='*80}")
print(f"POTENTIAL ISSUES TO CHECK:")
print(f"{'='*80}")

# Check for duplicate returns
print(f"\n1. Checking for duplicate returns:")
for sale_item in sale.sale_items.all():
    returns = SalesReturn.objects.filter(sale_item=sale_item)
    if len(returns) > 1:
        print(f"   WARNING: Sale Item '{sale_item.item.name}' has {len(returns)} returns")
        for ret in returns:
            print(f"     - {ret.return_no}: qty={ret.qty}, created={ret.created_at}")

# Check if returned_qty > sold_qty
print(f"\n2. Checking if returned_qty exceeds sold_qty:")
for sale_item in sale.sale_items.all():
    sold_qty = Decimal(str(sale_item.qty or 0))
    returned_qty = SalesReturn.objects.filter(sale_item=sale_item).aggregate(total=Sum("qty"))["total"] or Decimal("0")
    if returned_qty > sold_qty:
        print(f"   ERROR: Sale Item '{sale_item.item.name}' has returned_qty ({returned_qty}) > sold_qty ({sold_qty})")

# Check if returns are being included multiple times
print(f"\n3. Checking overall return count for invoice:")
all_returns_for_sale = SalesReturn.objects.filter(sale=sale)
print(f"   Total returns for this invoice: {len(all_returns_for_sale)}")
for ret in all_returns_for_sale:
    print(f"     - {ret.return_no}: item={ret.sale_item.item.name}, qty={ret.qty}")

print(f"\n{'='*80}\n")
