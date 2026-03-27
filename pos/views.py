import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .models import Item, Sale, SaleItem, StockTransaction, Category


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

    sales = Sale.objects.filter(created_at__date=today)

    summary = sales.aggregate(
        total_sales=Sum('grand_total'),
        total_discount=Sum('discount')
    )

    return render(request, 'pos/daily_report.html', {
        'sales': sales,
        'today': today,
        'summary': summary
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
    categories = Category.objects.all()

    if request.method == "POST":
        item_code = request.POST.get('item_code')
        name = request.POST.get('name')
        category_id = request.POST.get('category')
        cost_price = request.POST.get('cost_price') or 0
        selling_price = request.POST.get('selling_price') or 0
        stock = request.POST.get('stock') or 0
        warranty_days = request.POST.get('warranty_days') or 0

        # 🔥 SAFE CATEGORY (no crash)
        category = Category.objects.filter(id=category_id).first()

        Item.objects.create(
            item_code=item_code,
            name=name,
            category=category,
            cost_price=cost_price,
            selling_price=selling_price,
            stock=stock,
            warranty_days=warranty_days
        )

        return redirect('pos')

    return render(request, 'pos/add_item.html', {
        'categories': categories
    })