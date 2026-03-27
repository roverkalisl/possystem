import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Item, Sale, SaleItem, StockTransaction


def is_owner(user):
    return user.is_superuser or user.groups.filter(name='Owner').exists()


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


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


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


@login_required
def save_sale(request):
    if request.method != "POST":
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid request method'
        }, status=400)

    try:
        data = json.loads(request.body)

        cart_items = data.get('items', [])
        if not cart_items:
            return JsonResponse({
                'status': 'error',
                'message': 'Cart is empty'
            }, status=400)

        try:
            total = Decimal(str(data.get('total', 0)))
            discount = Decimal(str(data.get('discount', 0)))
            grand_total = Decimal(str(data.get('grand_total', 0)))
        except InvalidOperation:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid total values'
            }, status=400)

        payment_method = (data.get('payment_method') or 'cash').strip()

        received_raw = data.get('received', 0)
        balance_raw = data.get('balance', 0)
        card_last4 = (data.get('card_last4') or '').strip()
        cheque_number = (data.get('cheque_number') or '').strip()

        try:
            received = Decimal(str(received_raw or 0))
            balance = Decimal(str(balance_raw or 0))
        except InvalidOperation:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid payment values'
            }, status=400)

        if total < 0 or discount < 0 or grand_total < 0:
            return JsonResponse({
                'status': 'error',
                'message': 'Amounts cannot be negative'
            }, status=400)

        if payment_method == 'cash' and received < grand_total:
            return JsonResponse({
                'status': 'error',
                'message': 'Received amount is less than grand total'
            }, status=400)

        if payment_method == 'card':
            if len(card_last4) != 4 or not card_last4.isdigit():
                return JsonResponse({
                    'status': 'error',
                    'message': 'Enter valid card last 4 digits'
                }, status=400)

        if payment_method == 'credit' and cheque_number == '':
            return JsonResponse({
                'status': 'error',
                'message': 'Enter cheque number'
            }, status=400)

        sale_count = Sale.objects.count() + 1
        invoice_no = f"INV{sale_count:05d}"

        sale = Sale.objects.create(
            invoice_no=invoice_no,
            total=total,
            discount=discount,
            grand_total=grand_total,
            payment_method=payment_method,
            received_amount=received if payment_method == 'cash' else None,
            balance=balance if payment_method == 'cash' else None,
            card_last4=card_last4 if payment_method == 'card' else None,
            cheque_number=cheque_number if payment_method == 'credit' else None,
            created_by=request.user
        )

        for row in cart_items:
            item_id = row.get('id')
            qty = int(row.get('qty', 0))
            price = Decimal(str(row.get('price', 0)))

            item = get_object_or_404(Item, id=item_id)

            if qty <= 0:
                sale.delete()
                return JsonResponse({
                    'status': 'error',
                    'message': f'Invalid quantity for {item.name}'
                }, status=400)

            if item.stock < qty:
                sale.delete()
                return JsonResponse({
                    'status': 'error',
                    'message': f'Not enough stock for {item.name}'
                }, status=400)

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

        return JsonResponse({
            'status': 'success',
            'sale_id': sale.id
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
def invoice_page(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    return render(request, 'pos/invoice.html', {'sale': sale})


@login_required
def daily_report(request):
    today = timezone.localdate()

    sales = Sale.objects.filter(
        created_at__date=today
    ).select_related('created_by').order_by('-id')

    summary = sales.aggregate(
        total_sales=Sum('grand_total'),
        total_discount=Sum('discount')
    )

    return render(request, 'pos/daily_report.html', {
        'sales': sales,
        'today': today,
        'summary': summary
    })


@login_required
@user_passes_test(is_owner)
def monthly_report(request):
    today = timezone.localdate()

    try:
        year = int(request.GET.get('year', today.year))
    except ValueError:
        year = today.year

    try:
        month = int(request.GET.get('month', today.month))
    except ValueError:
        month = today.month

    sales = Sale.objects.filter(
        created_at__year=year,
        created_at__month=month
    ).select_related('created_by').order_by('-id')

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
    def add_item(request):
    categories = Category.objects.all()

    if request.method == "POST":
        item_code = request.POST.get('item_code')
        name = request.POST.get('name')
        category_id = request.POST.get('category')
        cost_price = request.POST.get('cost_price')
        selling_price = request.POST.get('selling_price')
        stock = request.POST.get('stock')
        warranty_days = request.POST.get('warranty_days')

        category = Category.objects.get(id=category_id)

        Item.objects.create(
            item_code=item_code,
            name=name,
            category=category,
            cost_price=cost_price,
            selling_price=selling_price,
            stock=stock,
            warranty_days=warranty_days or 0
        )

        return redirect('pos')

    return render(request, 'pos/add_item.html', {
        'categories': categories
    })
    