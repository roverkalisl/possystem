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

from .models import (
    Item, Category, Supplier,
    Sale, SaleItem, StockTransaction,
    SalesReturn, GLMaster
)


# =========================================
# HELPERS
# =========================================
def is_owner(user):
    return user.is_superuser or user.groups.filter(name='Owner').exists()


# =========================================
# AUTH
# =========================================
def login_view(request):
    if request.user.is_authenticated:
        return redirect("pos")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

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


# =========================================
# POS
# =========================================
@login_required
def pos_page(request):
    query = request.GET.get("q", "").strip()

    items = Item.objects.filter(is_service=False).select_related("category").order_by("name")

    if query:
        items = items.filter(
            Q(name__icontains=query) |
            Q(item_code__icontains=query) |
            Q(category__name__icontains=query)
        )

    return render(request, "pos/pos.html", {
        "items": items,
        "query": query,
        "can_view_monthly": is_owner(request.user),
    })


@login_required
def save_sale(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request method"}, status=400)

    try:
        data = json.loads(request.body)

        cart = data.get("items", [])
        if not cart:
            return JsonResponse({"status": "error", "message": "Cart is empty"}, status=400)

        try:
            total = Decimal(str(data.get("total", 0)))
            discount = Decimal(str(data.get("discount", 0)))
            grand_total = Decimal(str(data.get("grand_total", 0)))
        except InvalidOperation:
            return JsonResponse({"status": "error", "message": "Invalid totals"}, status=400)

        payment_method = (data.get("payment_method") or "cash").strip()
        received_amount = Decimal(str(data.get("received") or 0))
        balance = Decimal(str(data.get("balance") or 0))
        card_last4 = (data.get("card_last4") or "").strip()
        cheque_number = (data.get("cheque_number") or "").strip()

        if payment_method == "cash" and received_amount < grand_total:
            return JsonResponse({"status": "error", "message": "Received amount is less than grand total"}, status=400)

        if payment_method == "card" and len(card_last4) != 4:
            return JsonResponse({"status": "error", "message": "Enter card last 4 digits"}, status=400)

        if payment_method == "credit" and cheque_number == "":
            return JsonResponse({"status": "error", "message": "Enter cheque number"}, status=400)

        invoice_no = f"INV{Sale.objects.count() + 1:05d}"

        sale = Sale.objects.create(
            invoice_no=invoice_no,
            total=total,
            discount=discount,
            grand_total=grand_total,
            payment_method=payment_method,
            received_amount=received_amount if payment_method == "cash" else None,
            balance=balance if payment_method == "cash" else None,
            card_last4=card_last4 if payment_method == "card" else None,
            cheque_number=cheque_number if payment_method == "credit" else None,
            created_by=request.user
        )

        for row in cart:
            item = get_object_or_404(Item, id=row["id"])
            qty = int(row["qty"])
            price = Decimal(str(row["price"]))
            amount = qty * price

            if qty <= 0:
                sale.delete()
                return JsonResponse({"status": "error", "message": f"Invalid qty for {item.name}"}, status=400)

            if not item.is_service and item.stock < qty:
                sale.delete()
                return JsonResponse({"status": "error", "message": f"Not enough stock for {item.name}"}, status=400)

            SaleItem.objects.create(
                sale=sale,
                item=item,
                qty=qty,
                price=price,
                amount=amount
            )

            if not item.is_service:
                item.stock -= qty
                item.save()

                StockTransaction.objects.create(
                    item=item,
                    transaction_type="sale",
                    qty=qty
                )

        return JsonResponse({"status": "success", "sale_id": sale.id})

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required
def invoice_page(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    return render(request, "pos/invoice.html", {"sale": sale})


# =========================================
# ITEM MANAGEMENT
# =========================================
@login_required
def add_item(request):
    categories = Category.objects.all().order_by("name")
    suppliers = Supplier.objects.all().order_by("name")
    gl_list = GLMaster.objects.filter(is_active=True).order_by("gl_code")

    if request.method == "POST":
        purchase_date = request.POST.get("purchase_date") or None
        parsed_purchase_date = None

        if purchase_date:
            try:
                parsed_purchase_date = datetime.strptime(purchase_date, "%Y-%m-%d").date()
            except ValueError:
                messages.error(request, "Invalid purchase date")
                return render(request, "pos/add_item.html", {
                    "categories": categories,
                    "suppliers": suppliers,
                    "gl_list": gl_list,
                })

        retail_gl_account_id = request.POST.get("retail_gl_account") or None
        cost_gl_account_id = request.POST.get("cost_gl_account") or None

        retail_gl_obj = GLMaster.objects.filter(id=retail_gl_account_id).first() if retail_gl_account_id else None
        cost_gl_obj = GLMaster.objects.filter(id=cost_gl_account_id).first() if cost_gl_account_id else None

        Item.objects.create(
            item_code=request.POST.get("item_code", "").strip(),
            name=request.POST.get("name", "").strip(),
            category_id=request.POST.get("category") or None,
            supplier_id=request.POST.get("supplier") or None,
            unit=request.POST.get("unit", "pcs").strip(),
            cost_price=request.POST.get("cost_price") or 0,
            selling_price=request.POST.get("selling_price") or 0,
            stock=request.POST.get("stock") or 0,
            purchase_date=parsed_purchase_date,
            item_type=request.POST.get("item_type", "retail"),
            is_service=request.POST.get("is_service") == "on",
            reorder_level=request.POST.get("reorder_level") or 0,
            warranty_days=request.POST.get("warranty_days") or 0,

            retail_gl=retail_gl_obj.gl_code if retail_gl_obj else None,
            cost_gl=cost_gl_obj.gl_code if cost_gl_obj else None,

            retail_gl_account_id=retail_gl_account_id,
            cost_gl_account_id=cost_gl_account_id,
        )

        messages.success(request, "Item added successfully")
        return redirect("add_item")

    return render(request, "pos/add_item.html", {
        "categories": categories,
        "suppliers": suppliers,
        "gl_list": gl_list,
    })


@login_required
def item_list(request):
    query = request.GET.get("q", "").strip()

    items = Item.objects.select_related(
        "category", "supplier", "retail_gl_account", "cost_gl_account"
    ).order_by("-id")

    if query:
        items = items.filter(
            Q(name__icontains=query) |
            Q(item_code__icontains=query)
        )

    low_stock_items = Item.objects.filter(stock__lte=F("reorder_level")).order_by("name")

    return render(request, "pos/item_list.html", {
        "items": items,
        "query": query,
        "low_stock_items": low_stock_items
    })


@login_required
def edit_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    categories = Category.objects.all().order_by("name")
    suppliers = Supplier.objects.all().order_by("name")
    gl_list = GLMaster.objects.filter(is_active=True).order_by("gl_code")

    if request.method == "POST":
        item.item_code = request.POST.get("item_code", "").strip()
        item.name = request.POST.get("name", "").strip()
        item.category_id = request.POST.get("category") or None
        item.supplier_id = request.POST.get("supplier") or None
        item.unit = request.POST.get("unit", "pcs").strip()
        item.cost_price = request.POST.get("cost_price") or 0
        item.selling_price = request.POST.get("selling_price") or 0
        item.stock = request.POST.get("stock") or 0
        item.item_type = request.POST.get("item_type", "retail")
        item.is_service = request.POST.get("is_service") == "on"
        item.reorder_level = request.POST.get("reorder_level") or 0
        item.warranty_days = request.POST.get("warranty_days") or 0

        retail_gl_account_id = request.POST.get("retail_gl_account") or None
        cost_gl_account_id = request.POST.get("cost_gl_account") or None

        retail_gl_obj = GLMaster.objects.filter(id=retail_gl_account_id).first() if retail_gl_account_id else None
        cost_gl_obj = GLMaster.objects.filter(id=cost_gl_account_id).first() if cost_gl_account_id else None

        item.retail_gl_account_id = retail_gl_account_id
        item.cost_gl_account_id = cost_gl_account_id

        item.retail_gl = retail_gl_obj.gl_code if retail_gl_obj else None
        item.cost_gl = cost_gl_obj.gl_code if cost_gl_obj else None

        purchase_date = request.POST.get("purchase_date") or None
        if purchase_date:
            try:
                item.purchase_date = datetime.strptime(purchase_date, "%Y-%m-%d").date()
            except ValueError:
                messages.error(request, "Invalid purchase date")
                return redirect("edit_item", item_id=item.id)
        else:
            item.purchase_date = None

        item.save()
        messages.success(request, "Item updated successfully")
        return redirect("item_list")

    return render(request, "pos/edit_item.html", {
        "item": item,
        "categories": categories,
        "suppliers": suppliers,
        "gl_list": gl_list,
    })


@login_required
def stock_history(request):
    rows = StockTransaction.objects.select_related("item").order_by("-created_at")
    return render(request, "pos/stock_history.html", {"rows": rows})


# =========================================
# REPORTS
# =========================================
@login_required
def daily_report(request):
    today = timezone.localdate()

    sales = Sale.objects.filter(created_at__date=today).prefetch_related("sale_items__item")

    total_sales = Decimal("0")
    total_cost = Decimal("0")
    total_discount = Decimal("0")

    for sale in sales:
        sale_cost = Decimal("0")
        for row in sale.sale_items.all():
            sale_cost += row.item.cost_price * row.qty

        sale.sale_cost = sale_cost
        sale.sale_profit = sale.grand_total - sale_cost

        total_sales += sale.grand_total
        total_cost += sale_cost
        total_discount += sale.discount

    return render(request, "pos/daily_report.html", {
        "sales": sales,
        "today": today,
        "total_sales": total_sales,
        "total_cost": total_cost,
        "total_discount": total_discount,
        "total_profit": total_sales - total_cost
    })


@login_required
def monthly_report(request):
    sales = Sale.objects.all().order_by("-created_at")
    total = sales.aggregate(total=Sum("grand_total"))["total"] or 0

    return render(request, "pos/monthly_report.html", {
        "sales": sales,
        "total": total
    })


# =========================================
# SALES RETURN
# =========================================
@login_required
def get_sale_items(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)

    data = []
    for row in sale.sale_items.all():
        data.append({
            "sale_item_id": row.id,
            "item_name": row.item.name,
            "item_code": row.item.item_code,
            "qty": row.qty,
            "price": str(row.price),
        })

    return JsonResponse({"items": data})


@login_required
def sales_return(request):
    sales = Sale.objects.all().order_by("-id")

    if request.method == "POST":
        sale_id = request.POST.get("sale")
        sale_item_id = request.POST.get("sale_item")
        qty = int(request.POST.get("qty") or 0)
        return_type = request.POST.get("return_type", "refund")
        reason = request.POST.get("reason", "").strip()

        sale_item = get_object_or_404(SaleItem, id=sale_item_id)

        if qty <= 0:
            messages.error(request, "Invalid return qty")
            return redirect("sales_return")

        if qty > sale_item.qty:
            messages.error(request, "Return qty exceeds sold qty")
            return redirect("sales_return")

        return_no = f"RET{SalesReturn.objects.count() + 1:05d}"

        r = SalesReturn.objects.create(
            return_no=return_no,
            sale_id=sale_id,
            sale_item=sale_item,
            qty=qty,
            return_type=return_type,
            reason=reason,
            created_by=request.user
        )

        item = sale_item.item
        if not item.is_service:
            item.stock += qty
            item.save()

            StockTransaction.objects.create(
                item=item,
                transaction_type="adjust_plus",
                qty=qty
            )

        return redirect("return_receipt", return_id=r.id)

    return render(request, "pos/sales_return.html", {"sales": sales})


@login_required
def return_receipt(request, return_id):
    r = get_object_or_404(SalesReturn, id=return_id)
    return render(request, "pos/return_receipt.html", {"r": r})


# =========================================
# GL MASTER
# =========================================
@login_required
def gl_list(request):
    query = request.GET.get("q", "").strip()

    gl_accounts = GLMaster.objects.all().order_by("gl_code")

    if query:
        gl_accounts = gl_accounts.filter(
            Q(gl_code__icontains=query) |
            Q(gl_name__icontains=query) |
            Q(gl_type__icontains=query) |
            Q(parent_group__icontains=query)
        )

    return render(request, "pos/gl_list.html", {
        "gl_accounts": gl_accounts,
        "query": query
    })


@login_required
def add_gl(request):
    if request.method == "POST":
        gl_code = request.POST.get("gl_code", "").strip()
        gl_name = request.POST.get("gl_name", "").strip()
        gl_type = request.POST.get("gl_type", "").strip()
        parent_group = request.POST.get("parent_group", "").strip()
        description = request.POST.get("description", "").strip()
        is_active = request.POST.get("is_active") == "on"

        if not gl_code or not gl_name or not gl_type:
            messages.error(request, "GL Code, Name and Type are required.")
            return redirect("add_gl")

        if GLMaster.objects.filter(gl_code=gl_code).exists():
            messages.error(request, "GL Code already exists.")
            return redirect("add_gl")

        GLMaster.objects.create(
            gl_code=gl_code,
            gl_name=gl_name,
            gl_type=gl_type,
            parent_group=parent_group,
            description=description,
            is_active=is_active
        )

        messages.success(request, "GL account added successfully.")
        return redirect("gl_list")

    return render(request, "pos/add_gl.html")


@login_required
def edit_gl(request, gl_id):
    gl = get_object_or_404(GLMaster, id=gl_id)

    if request.method == "POST":
        gl_code = request.POST.get("gl_code", "").strip()
        gl_name = request.POST.get("gl_name", "").strip()
        gl_type = request.POST.get("gl_type", "").strip()
        parent_group = request.POST.get("parent_group", "").strip()
        description = request.POST.get("description", "").strip()
        is_active = request.POST.get("is_active") == "on"

        if not gl_code or not gl_name or not gl_type:
            messages.error(request, "GL Code, Name and Type are required.")
            return redirect("edit_gl", gl_id=gl.id)

        duplicate = GLMaster.objects.filter(gl_code=gl_code).exclude(id=gl.id).exists()
        if duplicate:
            messages.error(request, "Another GL account already uses this code.")
            return redirect("edit_gl", gl_id=gl.id)

        gl.gl_code = gl_code
        gl.gl_name = gl_name
        gl.gl_type = gl_type
        gl.parent_group = parent_group
        gl.description = description
        gl.is_active = is_active
        gl.save()

        messages.success(request, "GL account updated successfully.")
        return redirect("gl_list")

    return render(request, "pos/edit_gl.html", {
        "gl": gl
    })