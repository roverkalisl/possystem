import json
from decimal import Decimal, InvalidOperation
from datetime import datetime

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .models import Item, Sale, SaleItem, StockTransaction, Category, Supplier, SalesReturn
#from .models import Item, Sale, SaleItem, StockTransaction, Category, Supplier


# 🔐 Owner check
def is_owner(user):
    return user.is_superuser or user.groups.filter(name='Owner').exists()


# 🔐 Login
def login_view(request):
    if request.user.is_authenticated:
        return redirect('pos')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('pos')
        else:
            messages.error(request, 'Invalid username or password')

    return render(request, 'pos/login.html')


# 🔐 Logout
@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


# 🛒 POS Page
@login_required
def pos_page(request):
    query = request.GET.get('q', '').strip()

    items = Item.objects.filter(stock__gt=0).select_related('category').order_by('name')

    if query:
        items = items.filter(
            Q(name__icontains=query) |
            Q(item_code__icontains=query) |
            Q(category__name__icontains=query)
        )

    can_view_monthly = is_owner(request.user)

    return render(request, 'pos/pos.html', {
        'items': items,
        'query': query,
        'can_view_monthly': can_view_monthly,
    })


# 💰 Save Sale
@login_required
def save_sale(request):
    if request.method != "POST":
        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

    try:
        data = json.loads(request.body)

        cart_items = data.get('items', [])

        if not cart_items:
            return JsonResponse({'status': 'error', 'message': 'Cart empty'}, status=400)

        total = Decimal(str(data.get('total', 0)))
        discount = Decimal(str(data.get('discount', 0)))
        grand_total = Decimal(str(data.get('grand_total', 0)))

        payment_method = data.get('payment_method', 'cash')

        received = Decimal(str(data.get('received', 0)))
        balance = Decimal(str(data.get('balance', 0))
        )
        card_last4 = data.get('card_last4')
        cheque_number = data.get('cheque_number')

        invoice_no = f"INV{Sale.objects.count() + 1:05d}"

        sale = Sale.objects.create(
            invoice_no=invoice_no,
            total=total,
            discount=discount,
            grand_total=grand_total,
            payment_method=payment_method,
            received_amount=received,
            balance=balance,
            card_last4=card_last4,
            cheque_number=cheque_number,
            created_by=request.user
        )

        for row in cart_items:
            item = get_object_or_404(Item, id=row['id'])
            qty = int(row['qty'])
            price = Decimal(str(row['price']))

            if item.stock < qty:
                sale.delete()
                return JsonResponse({'status': 'error', 'message': 'Stock error'})

            amount = qty * price

            SaleItem.objects.create(
                sale=sale,
                item=item,
                qty=qty,
                price=price,
                amount=amount
            )

            item.stock -= qty
            item.save()

            StockTransaction.objects.create(
                item=item,
                transaction_type='sale',
                qty=qty
            )

        return JsonResponse({'status': 'success', 'sale_id': sale.id})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


# 🧾 Invoice
@login_required
def invoice_page(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    return render(request, 'pos/invoice.html', {'sale': sale})


# 📊 Daily Report
@login_required
def daily_report(request):
    today = timezone.localdate()

    sales = Sale.objects.filter(
        created_at__date=today
    ).select_related('created_by').prefetch_related('sale_items__item').order_by('-id')

    total_sales = Decimal('0.00')
    total_discount = Decimal('0.00')
    total_cost = Decimal('0.00')

    for sale in sales:
        sale_cost = Decimal('0.00')
        for row in sale.sale_items.all():
            sale_cost += (row.item.cost_price * row.qty)

        sale.sale_cost = sale_cost
        sale.sale_profit = sale.grand_total - sale_cost

        total_sales += sale.grand_total
        total_discount += sale.discount
        total_cost += sale_cost

    total_profit = total_sales - total_cost

    return render(request, 'pos/daily_report.html', {
        'sales': sales,
        'today': today,
        'total_sales': total_sales,
        'total_discount': total_discount,
        'total_cost': total_cost,
        'total_profit': total_profit,
    })


# 📊 Monthly Report
@login_required
@user_passes_test(is_owner)
def monthly_report(request):
    today = timezone.localdate()

    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    sales = Sale.objects.filter(
        created_at__year=year,
        created_at__month=month
    )

    summary = sales.aggregate(
        total_sales=Sum('grand_total'),
        total_discount=Sum('discount')
    )

    return render(request, 'pos/monthly_report.html', {
        'sales': sales,
        'year': year,
        'month': month,
        'summary': summary
    })


# ➕ ADD ITEM PAGE (FIXED)
@login_required
def add_item(request):
    categories = Category.objects.all().order_by('name')
    suppliers = Supplier.objects.all().order_by('name')

    if request.method == "POST":
        item_code = request.POST.get('item_code', '').strip()
        name = request.POST.get('name', '').strip()
        category_id = request.POST.get('category')
        unit = request.POST.get('unit', 'pcs').strip()
        cost_price = request.POST.get('cost_price') or 0
        selling_price = request.POST.get('selling_price') or 0
        stock = request.POST.get('stock') or 0
        purchase_date = request.POST.get('purchase_date') or None
        supplier_id = request.POST.get('supplier') or None
        item_type = request.POST.get('item_type', 'retail')
        is_service = request.POST.get('is_service') == 'on'
        reorder_level = request.POST.get('reorder_level') or 0
        warranty_days = request.POST.get('warranty_days') or 0

        if not item_code or not name:
            messages.error(request, 'Item code and name are required.')
            return render(request, 'pos/add_item.html', {
                'categories': categories,
                'suppliers': suppliers,
            })

        category = Category.objects.filter(id=category_id).first() if category_id else None
        supplier = Supplier.objects.filter(id=supplier_id).first() if supplier_id else None

        parsed_purchase_date = None
        if purchase_date:
            try:
                parsed_purchase_date = datetime.strptime(purchase_date, "%Y-%m-%d").date()
            except ValueError:
                messages.error(request, 'Invalid purchase date.')
                return render(request, 'pos/add_item.html', {
                    'categories': categories,
                    'suppliers': suppliers,
                })

        Item.objects.create(
            item_code=item_code,
            name=name,
            category=category,
            unit=unit,
            cost_price=cost_price,
            selling_price=selling_price,
            stock=stock,
            purchase_date=parsed_purchase_date,
            supplier=supplier,
            item_type=item_type,
            is_service=is_service,
            reorder_level=reorder_level,
            warranty_days=warranty_days,
        )

        messages.success(request, 'Item added successfully.')
        return redirect('add_item')

    return render(request, 'pos/add_item.html', {
        'categories': categories,
        'suppliers': suppliers,
    })
@login_required
def sales_return(request):
    sales = Sale.objects.all().order_by('-id')[:100]

    if request.method == "POST":
        try:
            sale_id = request.POST.get('sale')
            sale_item_id = request.POST.get('sale_item')
            qty = request.POST.get('qty')
            return_type = request.POST.get('return_type')
            reason = request.POST.get('reason', '')

            # 🔴 validation
            if not sale_id or not sale_item_id or not qty:
                messages.error(request, "All fields are required")
                return redirect('sales_return')

            qty = int(qty)

            sale = Sale.objects.filter(id=sale_id).first()
            sale_item = SaleItem.objects.filter(id=sale_item_id).first()

            if not sale or not sale_item:
                messages.error(request, "Invalid sale or item")
                return redirect('sales_return')

            if qty <= 0:
                messages.error(request, "Qty must be greater than 0")
                return redirect('sales_return')

            if qty > sale_item.qty:
                messages.error(request, "Return qty exceeds sold qty")
                return redirect('sales_return')

            # create return
            SalesReturn.objects.create(
                sale=sale,
                sale_item=sale_item,
                qty=qty,
                return_type=return_type,
                reason=reason,
                created_by=request.user
            )

            # stock update
            if not sale_item.item.is_service:
                sale_item.item.stock += qty
                sale_item.item.save()

            messages.success(request, "Return successful")
            return redirect('sales_return')

        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('sales_return')

    return render(request, 'pos/sales_return.html', {
        'sales': sales
    })
def get_sale_items(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)

    items = []
    for row in sale.sale_items.all():
        items.append({
            'sale_item_id': row.id,
            'item_name': row.item.name,
            'item_code': row.item.item_code,
            'qty': row.qty,
            'price': str(row.price),
        })

    return JsonResponse({'items': items})

