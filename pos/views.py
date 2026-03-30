from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum, F
from django.http import JsonResponse

from decimal import Decimal
from datetime import datetime
import json

from .models import (
    Item, Category, Supplier, GLMaster,
    Sale, SaleItem, StockTransaction, SalesReturn,
    Project
)


# =========================
# DASHBOARD
# =========================
@login_required
def dashboard(request):
    return render(request, "pos/dashboard.html")


# =========================
# LOGIN / LOGOUT
# =========================
def login_view(request):
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username"),
            password=request.POST.get("password")
        )

        if user:
            login(request, user)
            return redirect("dashboard")
        else:
            messages.error(request, "Invalid login")

    return render(request, "pos/login.html")


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


# =========================
# POS
# =========================
@login_required
def pos_page(request):
    query = request.GET.get("q", "").strip()

    items = Item.objects.all().order_by("name")

    if query:
        items = items.filter(
            Q(name__icontains=query) |
            Q(item_code__icontains=query)
        )

    return render(request, "pos/pos.html", {
        "items": items,
        "query": query
    })


@login_required
def save_sale(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)

    try:
        data = json.loads(request.body)

        items = data.get("items", [])
        if not items:
            return JsonResponse({"status": "error", "message": "Cart empty"}, status=400)

        total = Decimal(str(data.get("total", 0)))
        discount = Decimal(str(data.get("discount", 0)))
        grand_total = Decimal(str(data.get("grand_total", 0)))

        payment_method = data.get("payment_method", "cash")
        received_amount = Decimal(str(data.get("received") or 0))
        balance = Decimal(str(data.get("balance") or 0))
        card_last4 = data.get("card_last4") or None
        cheque_number = data.get("cheque_number") or None

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

        for i in items:
            item = Item.objects.get(id=i["id"])
            qty = int(i["qty"])
            price = Decimal(str(i["price"]))
            amount = qty * price

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


# =========================
# ITEM
# =========================
@login_required
def add_item(request):
    categories = Category.objects.all().order_by("name")
    suppliers = Supplier.objects.all().order_by("name")
    gl_list = GLMaster.objects.all().order_by("gl_code")

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
                    "gl_list": gl_list
                })

        Item.objects.create(
            item_code=request.POST.get("item_code"),
            name=request.POST.get("name"),
            category_id=request.POST.get("category") or None,
            supplier_id=request.POST.get("supplier") or None,
            unit=request.POST.get("unit") or "pcs",
            cost_price=request.POST.get("cost_price") or 0,
            selling_price=request.POST.get("selling_price") or 0,
            stock=request.POST.get("stock") or 0,
            purchase_date=parsed_purchase_date,
            item_type=request.POST.get("item_type") or "retail",
            is_service=request.POST.get("is_service") == "on",
            reorder_level=request.POST.get("reorder_level") or 0,
            warranty_days=request.POST.get("warranty_days") or 0,
            retail_gl_account_id=request.POST.get("retail_gl_account") or None,
            cost_gl_account_id=request.POST.get("cost_gl_account") or None,
        )

        messages.success(request, "Item added successfully")
        return redirect("item_list")

    return render(request, "pos/add_item.html", {
        "categories": categories,
        "suppliers": suppliers,
        "gl_list": gl_list
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
    gl_list = GLMaster.objects.all().order_by("gl_code")

    if request.method == "POST":
        item.item_code = request.POST.get("item_code", "").strip()
        item.name = request.POST.get("name", "").strip()
        item.category_id = request.POST.get("category") or None
        item.supplier_id = request.POST.get("supplier") or None
        item.unit = request.POST.get("unit") or "pcs"
        item.cost_price = request.POST.get("cost_price") or 0
        item.selling_price = request.POST.get("selling_price") or 0
        item.stock = request.POST.get("stock") or 0
        item.item_type = request.POST.get("item_type") or "retail"
        item.is_service = request.POST.get("is_service") == "on"
        item.reorder_level = request.POST.get("reorder_level") or 0
        item.warranty_days = request.POST.get("warranty_days") or 0
        item.retail_gl_account_id = request.POST.get("retail_gl_account") or None
        item.cost_gl_account_id = request.POST.get("cost_gl_account") or None

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
        "gl_list": gl_list
    })


@login_required
def stock_history(request):
    rows = StockTransaction.objects.select_related("item").order_by("-created_at")
    return render(request, "pos/stock_history.html", {"rows": rows})


# =========================
# REPORTS
# =========================
@login_required
def daily_report(request):
    today = timezone.localdate()

    sales = Sale.objects.filter(created_at__date=today).prefetch_related("sale_items__item")

    total_sales = Decimal("0.00")
    total_cost = Decimal("0.00")
    total_discount = Decimal("0.00")

    for sale in sales:
        sale_cost = Decimal("0.00")
        for row in sale.sale_items.all():
            sale_cost += Decimal(str(row.item.cost_price)) * row.qty

        sale.sale_cost = sale_cost
        sale.sale_profit = Decimal(str(sale.grand_total)) - sale_cost

        total_sales += Decimal(str(sale.grand_total))
        total_cost += sale_cost
        total_discount += Decimal(str(sale.discount))

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


# =========================
# SALES RETURN
# =========================
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
        qty = int(request.POST.get("qty") or 0)
        return_type = request.POST.get("return_type") or "refund"
        reason = request.POST.get("reason") or ""

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


# =========================
# GL
# =========================
@login_required
def gl_list(request):
    gls = GLMaster.objects.all().order_by("gl_code")
    return render(request, "pos/gl_list.html", {"gl_accounts": gls})


# =========================
# PROJECT ID GENERATOR
# =========================
def generate_project_id(project_type):
    year = timezone.now().year
    last = Project.objects.filter(project_type=project_type).order_by("-id").first()

    if last:
        num = int(last.project_id[-3:]) + 1
    else:
        num = 1

    return f"PRO{year}{project_type}{num:03d}"


# =========================
# PROJECT
# =========================
@login_required
def create_project(request):
    if not request.user.is_superuser:
        messages.error(request, "No permission")
        return redirect("dashboard")

    if request.method == "POST":
        project_type = request.POST.get("project_type")

        Project.objects.create(
            project_id=generate_project_id(project_type),
            project_name=request.POST.get("project_name"),
            project_type=project_type,
            client_name=request.POST.get("client_name"),
            location=request.POST.get("location"),
            estimated_value=request.POST.get("estimated_value") or 0,
            created_by=request.user
        )

        messages.success(request, "Project created successfully")
        return redirect("project_list")

    return render(request, "pos/create_project.html")


@login_required
def project_list(request):
    projects = Project.objects.all().order_by("-id")
    return render(request, "pos/project_list.html", {"projects": projects})