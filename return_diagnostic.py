import os
from decimal import Decimal
from django.db.models import Sum

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()

from pos.models import Sale, SaleItem, SalesReturn


def get_returned_qty_for_sale_item(sale_item):
    return sale_item.returns.aggregate(total=Sum('qty'))['total'] or Decimal('0')


def analyze_invoice(invoice_no):
    try:
        sale = Sale.objects.get(invoice_no=invoice_no)
    except Sale.DoesNotExist:
        print(f'Invoice {invoice_no} not found')
        return

    print(f'Invoice {invoice_no}: total={sale.total} grand_total={sale.grand_total} discount={sale.discount}')
    sale_cost = Decimal('0')
    returned_stock_value = Decimal('0')

    for row in sale.sale_items.all():
        sold_qty = Decimal(str(row.qty or 0))
        returned_qty = get_returned_qty_for_sale_item(row)
        available_qty = sold_qty - returned_qty
        unit_net = Decimal(str(row.net_amount or 0)) / sold_qty if sold_qty > 0 else Decimal('0')
        item_cost = Decimal(str(row.item.cost_price or 0))

        if available_qty > 0:
            sale_cost += item_cost * available_qty
        if returned_qty > 0:
            returned_stock_value += item_cost * returned_qty

        print('  item', row.item.name)
        print('    sold_qty', sold_qty)
        print('    returned_qty', returned_qty)
        print('    available_qty', available_qty)
        print('    unit_net', unit_net)
        print('    item_cost', item_cost)
        print('    cogs_for_available', item_cost * available_qty if available_qty > 0 else 0)
        print('    returned_stock_value', item_cost * returned_qty if returned_qty > 0 else 0)

    print('  sale_cost', sale_cost)
    print('  returned_stock_value', returned_stock_value)
    print('  profit', Decimal(str(sale.grand_total or 0)) - sale_cost)
    print('  returns records', list(sale.returns.values('return_no','sale_item_id','qty','created_at')))
    print()


if __name__ == '__main__':
    for invoice_no in ['INV00002', 'INV00003']:
        analyze_invoice(invoice_no)
