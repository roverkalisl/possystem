from decimal import Decimal
from datetime import datetime

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import (
    Item, Category, Supplier,
    Sale, SaleItem, StockTransaction,
    SalesReturn
)

# ===============================
# AUTH
# ===============================

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            return redirect("pos")
        else:
            messages.error(request, "Invalid username or password")

    return render(request, "pos/login.html")


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


# ===============================
# POS PAGE
# ===============================

@login_required
def pos_page(request):
    items = Item.objects.filter(is_service=False).order_by("name")
    return render(request, "pos/pos.html", {"items": items})


# ===============================
# SAVE SALE
# ===============================

@login_required
def save_sale(request):
    if request.method == "POST":
        items = request.POST.getlist("items[]")
        qtys = request.POST.getlist("qtys[]")
        prices = request.POST.getlist("prices[]")

        payment_method = request.POST.get("payment_method", "cash")
        discount = Decimal(request.POST.get("discount") or 0)

        total = Decimal("0.00")

        sale = Sale.objects.create(
            payment_method=payment_method,
            discount=discount,
            created_by=request.user
        )

        for i in range(len(items)):
            item = get_object_or_404(Item, id=items[i])
            qty = int(qtys[i])
            price = Decimal(prices[i])

            SaleItem.objects.create(
                sale=sale,
                item=item,
                qty=qty,
                price=price
            )

            total += price * qty

            if not item.is_service:
                item.stock -= qty
                item.save()

                StockTransaction.objects.create(
                    item=item,
                    transaction_type="sale",
                    qty=qty
                )

        sale.total = total
        sale.grand_total = total - discount
        sale.save()

        return JsonResponse({"sale_id": sale.id})

    return JsonResponse({"error": "Invalid request"})


# ===============================
# INVOICE
# ===============================

@login_required
def invoice_page(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    return render(request, "pos/invoice.html", {"sale": sale})


# ===============================
# ADD ITEM
# ===============================

@login_required
def add_item(request):
    categories = Category.objects.all()
    suppliers = Supplier.objects.all()

    if request.method == "POST":
        item = Item.objects.create(
            item_code=request.POST.get("item_code"),
            name=request.POST.get("name"),
            category_id=request.POST.get("category") or None,
            supplier_id=request.POST.get("supplier") or None,
            unit=request.POST.get("unit", "pcs"),
            cost_price=request.POST.get("cost_price") or 0,
            selling_price=request.POST.get("selling_price") or 0,
            stock=request.POST.get("stock") or 0,
            item_type=request.POST.get("item_type", "retail"),
            is_service=request.POST.get("is_service") == "on",
            reorder_level=request.POST.get("reorder_level") or 0,
            warranty_days=request.POST.get("warranty_days") or 0,
            retail_gl=request.POST.get("retail_gl") or None,
            cost_gl=request.POST.get("cost_gl") or None,
        )

        messages.success(request, "Item added successfully")
        return redirect("add_item")

    return render(request, "pos/add_item.html", {
        "categories": categories,
        "suppliers": suppliers
    })


# ===============================
# ITEM LIST
# ===============================

@login_required
def item_list(request):
    query = request.GET.get("q", "")

    items = Item.objects.select_related("category", "supplier")

    if query:
        items = items.filter(
            Q(name__icontains=query) |
            Q(item_code__icontains=query)
        )

    low_stock_items = Item.objects.filter(stock__lte=F("reorder_level"))

    return render(request, "pos/item_list.html", {
        "items": items,
        "query": query,
        "low_stock_items": low_stock_items
    })


# ===============================
# EDIT ITEM
# ===============================

@login_required
def edit_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    categories = Category.objects.all()
    suppliers = Supplier.objects.all()

    if request.method == "POST":
        item.item_code = request.POST.get("item_code")
        item.name = request.POST.get("name")
        item.category_id = request.POST.get("category") or None
        item.supplier_id = request.POST.get("supplier") or None
        item.unit = request.POST.get("unit")
        item.cost_price = request.POST.get("cost_price") or 0
        item.selling_price = request.POST.get("selling_price") or 0
        item.stock = request.POST.get("stock") or 0
        item.reorder_level = request.POST.get("reorder_level") or 0
        item.warranty_days = request.POST.get("warranty_days") or 0
        item.retail_gl = request.POST.get("retail_gl") or None
        item.cost_gl = request.POST.get("cost_gl") or None
        item.save()

        messages.success(request, "Item updated")
        return redirect("item_list")

    return render(request, "pos/edit_item.html", {
        "item": item,
        "categories": categories,
        "suppliers": suppliers
    })


# ===============================
# STOCK HISTORY
# ===============================

@login_required
def stock_history(request):
    rows = StockTransaction.objects.select_related("item").order_by("-created_at")
    return render(request, "pos/stock_history.html", {"rows": rows})


# ===============================
# DAILY REPORT
# ===============================

@login_required
def daily_report(request):
    today = timezone.localdate()

    sales = Sale.objects.filter(created_at__date=today).prefetch_related("sale_items__item")

    total_sales = Decimal("0")
    total_cost = Decimal("0")

    for sale in sales:
        cost = Decimal("0")
        for row in sale.sale_items.all():
            cost += row.item.cost_price * row.qty

        sale.sale_cost = cost
        sale.sale_profit = sale.grand_total - cost

        total_sales += sale.grand_total
        total_cost += cost

    return render(request, "pos/daily_report.html", {
        "sales": sales,
        "total_sales": total_sales,
        "total_cost": total_cost,
        "total_profit": total_sales - total_cost
    })


# ===============================
# MONTHLY REPORT
# ===============================

@login_required
def monthly_report(request):
    sales = Sale.objects.all()
    total = sales.aggregate(total=Sum("grand_total"))["total"] or 0

    return render(request, "pos/monthly_report.html", {
        "sales": sales,
        "total": total
    })


# ===============================
# SALES RETURN
# ===============================

@login_required
def get_sale_items(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)

    data = []
    for row in sale.sale_items.all():
        data.append({
            "sale_item_id": row.id,
            "item_name": row.item.name,
            "qty": row.qty
        })

    return JsonResponse({"items": data})


@login_required
def sales_return(request):
    sales = Sale.objects.all().order_by("-id")

    if request.method == "POST":
        sale_id = request.POST.get("sale")
        sale_item_id = request.POST.get("sale_item")
        qty = int(request.POST.get("qty"))

        sale_item = get_object_or_404(SaleItem, id=sale_item_id)

        SalesReturn.objects.create(
            sale_id=sale_id,
            sale_item=sale_item,
            qty=qty,
            created_by=request.user
        )

        item = sale_item.item
        item.stock += qty
        item.save()

        return redirect("return_receipt", return_id=1)

    return render(request, "pos/sales_return.html", {"sales": sales})


@login_required
def return_receipt(request, return_id):
    r = get_object_or_404(SalesReturn, id=return_id)
    return render(request, "pos/return_receipt.html", {"r": r})