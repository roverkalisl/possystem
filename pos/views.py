import json
from decimal import Decimal, InvalidOperation
from datetime import datetime

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import Item, Category, Supplier, Sale, SaleItem, StockTransaction


# ================= AUTH =================
def login_view(request):
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username"),
            password=request.POST.get("password")
        )
        if user:
            login(request, user)
            return redirect("pos")
        else:
            messages.error(request, "Invalid login")

    return render(request, "pos/login.html")


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


# ================= POS =================
@login_required
def pos_page(request):
    query = request.GET.get("q", "")

    items = Item.objects.filter(is_service=False, stock__gt=0)

    if query:
        items = items.filter(
            Q(name__icontains=query) |
            Q(item_code__icontains=query)
        )

    return render(request, "pos/pos.html", {
        "items": items,
        "query": query
    })


# ================= SAVE SALE =================
@login_required
def save_sale(request):
    if request.method != "POST":
        return JsonResponse({"status": "error"})

    try:
        data = json.loads(request.body)

        cart = data.get("items", [])
        total = Decimal(str(data.get("total", 0)))
        discount = Decimal(str(data.get("discount", 0)))
        grand_total = Decimal(str(data.get("grand_total", 0)))

        sale = Sale.objects.create(
            invoice_no=f"INV{Sale.objects.count()+1:05d}",
            total=total,
            discount=discount,
            grand_total=grand_total,
            payment_method=data.get("payment_method"),
            received_amount=data.get("received") or 0,
            balance=data.get("balance") or 0,
            card_last4=data.get("card_last4"),
            cheque_number=data.get("cheque_number"),
            created_by=request.user
        )

        for row in cart:
            item = get_object_or_404(Item, id=row["id"])
            qty = int(row["qty"])
            price = Decimal(str(row["price"]))

            SaleItem.objects.create(
                sale=sale,
                item=item,
                qty=qty,
                price=price,
                amount=qty * price
            )

            item.stock -= qty
            item.save()

            StockTransaction.objects.create(
                item=item,
                transaction_type="sale",
                qty=qty
            )

        return JsonResponse({"status": "success", "sale_id": sale.id})

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})


# ================= ADD ITEM =================
@login_required
def add_item(request):
    categories = Category.objects.all()
    suppliers = Supplier.objects.all()

    if request.method == "POST":
        purchase_date = request.POST.get("purchase_date") or None

        parsed_date = None
        if purchase_date:
            parsed_date = datetime.strptime(purchase_date, "%Y-%m-%d").date()

        Item.objects.create(
            item_code=request.POST.get("item_code"),
            name=request.POST.get("name"),
            category_id=request.POST.get("category") or None,
            supplier_id=request.POST.get("supplier") or None,
            unit=request.POST.get("unit"),
            cost_price=request.POST.get("cost_price") or 0,
            selling_price=request.POST.get("selling_price") or 0,
            stock=request.POST.get("stock") or 0,
            purchase_date=parsed_date,
            item_type=request.POST.get("item_type"),
            is_service=request.POST.get("is_service") == "on",
            reorder_level=request.POST.get("reorder_level") or 0,
            warranty_days=request.POST.get("warranty_days") or 0,
            retail_gl=request.POST.get("retail_gl"),
            cost_gl=request.POST.get("cost_gl"),
        )

        messages.success(request, "Item saved")
        return redirect("add_item")

    return render(request, "pos/add_item.html", {
        "categories": categories,
        "suppliers": suppliers
    })

@login_required
def invoice_page(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    return render(request, "pos/invoice.html", {"sale": sale})