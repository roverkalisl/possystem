import json
from decimal import Decimal, InvalidOperation
from datetime import datetime

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import (
    Item, Category, Supplier, GLMaster,
    Sale, SaleItem, SalesReturn, StockTransaction,
    Project, ProjectExpense, ProjectPettyCash,
    ProjectPettyCashExpense, ProjectIncome
)


# =========================
# ROLE HELPERS
# =========================
def is_owner(user):
    return user.is_superuser or user.groups.filter(name="Owner").exists()


def is_manager(user):
    return user.groups.filter(name="Manager").exists()


def is_clerk(user):
    return user.groups.filter(name="Clerk").exists()


def is_cashier(user):
    return user.groups.filter(name="Cashier").exists()


def can_use_pos(user):
    return is_owner(user) or is_cashier(user)


def can_use_project(user):
    return is_owner(user) or is_manager(user) or is_clerk(user)


def can_use_gl(user):
    return is_owner(user)


# =========================
# DASHBOARD / AUTH
# =========================
@login_required
def dashboard(request):
    return render(request, "pos/dashboard.html", {
        "show_pos": can_use_pos(request.user),
        "show_project": can_use_project(request.user),
        "show_gl": can_use_gl(request.user),
    })


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username"),
            password=request.POST.get("password"),
        )
        if user:
            login(request, user)
            return redirect("dashboard")
        messages.error(request, "Invalid login")

    return render(request, "pos/login.html")


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


# =========================
# POS
# =========================
@user_passes_test(can_use_pos)
def pos_page(request):
    query = request.GET.get("q", "").strip()
    items = Item.objects.all().select_related("category").order_by("name")

    if query:
        items = items.filter(
            Q(name__icontains=query) |
            Q(item_code__icontains=query) |
            Q(category__name__icontains=query)
        )

    return render(request, "pos/pos.html", {
        "items": items,
        "query": query,
    })


@user_passes_test(can_use_pos)
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
            created_by=request.user,
        )

        for i in items:
            item = Item.objects.get(id=i["id"])
            qty = Decimal(str(i["qty"]))
            price = Decimal(str(i["price"]))
            amount = qty * price

            SaleItem.objects.create(
                sale=sale,
                item=item,
                qty=qty,
                price=price,
                amount=amount,
            )

            if not item.is_service:
                item.stock = Decimal(item.stock) - qty
                item.save()

                StockTransaction.objects.create(
                    item=item,
                    transaction_type="sale",
                    qty=qty,
                )

        return JsonResponse({"status": "success", "sale_id": sale.id})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@user_passes_test(can_use_pos)
def invoice_page(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    return render(request, "pos/invoice.html", {"sale": sale})


@user_passes_test(can_use_pos)
def sales_return(request):
    sales = Sale.objects.all().order_by("-id")

    if request.method == "POST":
        sale_id = request.POST.get("sale")
        sale_item_id = request.POST.get("sale_item")
        qty = Decimal(str(request.POST.get("qty") or 0))
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
            created_by=request.user,
        )

        item = sale_item.item
        if not item.is_service:
            item.stock = Decimal(item.stock) + qty
            item.save()

            StockTransaction.objects.create(
                item=item,
                transaction_type="return_in",
                qty=qty,
            )

        return redirect("return_receipt", return_id=r.id)

    return render(request, "pos/sales_return.html", {"sales": sales})


@user_passes_test(can_use_pos)
def get_sale_items(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    data = []
    for row in sale.sale_items.all():
        data.append({
            "sale_item_id": row.id,
            "item_name": row.item.name,
            "qty": str(row.qty),
        })
    return JsonResponse({"items": data})


@user_passes_test(can_use_pos)
def return_receipt(request, return_id):
    r = get_object_or_404(SalesReturn, id=return_id)
    return render(request, "pos/return_receipt.html", {"r": r})


# =========================
# ITEM MANAGEMENT
# =========================
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
        "low_stock_items": low_stock_items,
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
        "gl_list": gl_list,
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

    total_sales = Decimal("0")
    total_cost = Decimal("0")
    total_discount = Decimal("0")

    for sale in sales:
        sale_cost = Decimal("0")
        for row in sale.sale_items.all():
            sale_cost += Decimal(str(row.item.cost_price)) * Decimal(str(row.qty))
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
        "total_profit": total_sales - total_cost,
    })


@login_required
def monthly_report(request):
    sales = Sale.objects.all().order_by("-created_at")
    total = sales.aggregate(total=Sum("grand_total"))["total"] or 0

    return render(request, "pos/monthly_report.html", {
        "sales": sales,
        "total": total,
    })


# =========================
# GL MASTER
# =========================
@user_passes_test(can_use_gl)
def gl_list(request):
    gls = GLMaster.objects.all().order_by("gl_code")
    return render(request, "pos/gl_list.html", {"gl_accounts": gls})


@user_passes_test(can_use_gl)
def add_gl(request):
    if request.method == "POST":
        GLMaster.objects.create(
            gl_code=request.POST.get("gl_code"),
            gl_name=request.POST.get("gl_name"),
            gl_type=request.POST.get("gl_type"),
            parent_group=request.POST.get("parent_group"),
            description=request.POST.get("description"),
            is_active=True,
        )
        return redirect("gl_list")

    return render(request, "pos/add_gl.html")


# =========================
# PROJECT
# =========================
def generate_project_id(project_type):
    year = timezone.now().year
    last = Project.objects.filter(project_type=project_type).order_by("-id").first()
    num = int(last.project_id[-3:]) + 1 if last else 1
    return f"PRO{year}{project_type}{num:03d}"


@user_passes_test(can_use_project)
def project_list(request):
    projects = Project.objects.all().order_by("-id")
    return render(request, "pos/project_list.html", {"projects": projects})


@user_passes_test(can_use_project)
def create_project(request):
    if not is_owner(request.user):
        messages.error(request, "Only owner can create projects")
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
            created_by=request.user,
        )
        messages.success(request, "Project created successfully")
        return redirect("project_list")

    return render(request, "pos/create_project.html")


# =========================
# PROJECT EXPENSE
# =========================
@user_passes_test(can_use_project)
def project_expense_list(request):
    expenses = ProjectExpense.objects.select_related(
        "project", "gl_account", "item", "created_by"
    ).order_by("-expense_date", "-id")

    project_id = request.GET.get("project")
    if project_id:
        expenses = expenses.filter(project_id=project_id)

    projects = Project.objects.all().order_by("-id")

    return render(request, "pos/project_expense_list.html", {
        "expenses": expenses,
        "projects": projects,
        "selected_project": project_id,
    })


@user_passes_test(can_use_project)
def add_project_expense(request):
    projects = Project.objects.all().order_by("-id")
    expense_gls = GLMaster.objects.filter(gl_type="expense", is_active=True).order_by("gl_code")
    items = Item.objects.all().order_by("name")

    if request.method == "POST":
        expense_type = request.POST.get("expense_type")
        project_id = request.POST.get("project")
        expense_date = request.POST.get("expense_date") or timezone.now().date()
        item_id = request.POST.get("item") or None
        description = request.POST.get("description", "").strip()
        qty = Decimal(str(request.POST.get("qty") or 1))
        unit_price = Decimal(str(request.POST.get("unit_price") or 0))
        amount = Decimal(str(request.POST.get("amount") or 0))
        gl_account_id = request.POST.get("gl_account")

        if not gl_account_id:
            messages.error(request, "GL is required")
            return redirect("add_project_expense")

        if amount <= 0:
            messages.error(request, "Amount must be greater than 0")
            return redirect("add_project_expense")

        expense = ProjectExpense.objects.create(
            project_id=project_id,
            expense_type=expense_type,
            expense_date=expense_date,
            item_id=item_id,
            description=description,
            qty=qty,
            unit_price=unit_price,
            amount=amount,
            gl_account_id=gl_account_id,
            created_by=request.user,
        )

        if expense_type == "inventory" and item_id:
            item = Item.objects.get(id=item_id)
            item.stock = Decimal(item.stock) - qty
            item.save()

            StockTransaction.objects.create(
                item=item,
                transaction_type="project_issue",
                qty=qty,
            )

        messages.success(request, "Expense added")
        return redirect("project_expense_list")

    return render(request, "pos/add_project_expense.html", {
        "projects": projects,
        "expense_gls": expense_gls,
        "items": items,
    })


# =========================
# PROJECT PETTY CASH
# =========================
@user_passes_test(can_use_project)
def petty_cash_list(request):
    petty_cashes = ProjectPettyCash.objects.select_related("project", "created_by").order_by("-issue_date", "-id")
    projects = Project.objects.all().order_by("-id")

    project_id = request.GET.get("project")
    if project_id:
        petty_cashes = petty_cashes.filter(project_id=project_id)

    return render(request, "pos/petty_cash_list.html", {
        "petty_cashes": petty_cashes,
        "projects": projects,
        "selected_project": project_id,
    })


@user_passes_test(can_use_project)
def add_petty_cash(request):
    projects = Project.objects.all().order_by("-id")

    if request.method == "POST":
        project_id = request.POST.get("project")
        issue_date = request.POST.get("issue_date") or timezone.now().date()
        issued_to = request.POST.get("issued_to", "").strip()
        amount_issued = request.POST.get("amount_issued") or 0
        note = request.POST.get("note", "").strip()

        if not project_id or not issued_to:
            messages.error(request, "Project and issued to are required.")
            return render(request, "pos/add_petty_cash.html", {"projects": projects})

        petty_cash_no = f"PC{ProjectPettyCash.objects.count() + 1:05d}"

        ProjectPettyCash.objects.create(
            project_id=project_id,
            petty_cash_no=petty_cash_no,
            issue_date=issue_date,
            issued_to=issued_to,
            amount_issued=amount_issued,
            note=note,
            created_by=request.user,
        )

        messages.success(request, f"Petty cash created: {petty_cash_no}")
        return redirect("petty_cash_list")

    return render(request, "pos/add_petty_cash.html", {"projects": projects})


@user_passes_test(can_use_project)
def petty_cash_detail(request, petty_cash_id):
    petty_cash = get_object_or_404(
        ProjectPettyCash.objects.select_related("project", "created_by"),
        id=petty_cash_id
    )
    expenses = petty_cash.expenses.select_related("gl_account", "created_by").order_by("-expense_date", "-id")

    return render(request, "pos/petty_cash_detail.html", {
        "petty_cash": petty_cash,
        "expenses": expenses,
    })


@user_passes_test(can_use_project)
def add_petty_cash_expense(request, petty_cash_id):
    petty_cash = get_object_or_404(ProjectPettyCash, id=petty_cash_id)
    expense_gls = GLMaster.objects.filter(gl_type="expense", is_active=True).order_by("gl_code")

    if request.method == "POST":
        expense_date = request.POST.get("expense_date") or timezone.now().date()
        description = request.POST.get("description", "").strip()
        gl_account_id = request.POST.get("gl_account") or None
        amount = Decimal(str(request.POST.get("amount") or 0))
        note = request.POST.get("note", "").strip()

        if not description:
            messages.error(request, "Description is required.")
            return render(request, "pos/add_petty_cash_expense.html", {
                "petty_cash": petty_cash,
                "expense_gls": expense_gls,
            })

        if amount <= 0:
            messages.error(request, "Amount must be greater than 0.")
            return render(request, "pos/add_petty_cash_expense.html", {
                "petty_cash": petty_cash,
                "expense_gls": expense_gls,
            })

        if amount > petty_cash.balance:
            messages.error(request, "Expense exceeds petty cash balance.")
            return render(request, "pos/add_petty_cash_expense.html", {
                "petty_cash": petty_cash,
                "expense_gls": expense_gls,
            })

        ProjectPettyCashExpense.objects.create(
            petty_cash=petty_cash,
            expense_date=expense_date,
            description=description,
            gl_account_id=gl_account_id,
            amount=amount,
            note=note,
            created_by=request.user,
        )

        messages.success(request, "Petty cash expense added successfully.")
        return redirect("petty_cash_detail", petty_cash_id=petty_cash.id)

    return render(request, "pos/add_petty_cash_expense.html", {
        "petty_cash": petty_cash,
        "expense_gls": expense_gls,
    })


# =========================
# PROJECT INCOME
# =========================
@user_passes_test(can_use_project)
def project_income_list(request):
    incomes = ProjectIncome.objects.select_related("project", "gl_account", "created_by").order_by("-income_date", "-id")
    projects = Project.objects.all().order_by("-id")

    project_id = request.GET.get("project")
    if project_id:
        incomes = incomes.filter(project_id=project_id)

    return render(request, "pos/project_income_list.html", {
        "incomes": incomes,
        "projects": projects,
        "selected_project": project_id,
    })


@user_passes_test(can_use_project)
def add_project_income(request):
    projects = Project.objects.all().order_by("-id")
    income_gls = GLMaster.objects.filter(gl_type="income", is_active=True).order_by("gl_code")

    if request.method == "POST":
        project_id = request.POST.get("project")
        income_date = request.POST.get("income_date") or timezone.now().date()
        description = request.POST.get("description", "").strip()
        amount = request.POST.get("amount")
        gl_account_id = request.POST.get("gl_account") or None

        if not project_id or not amount:
            messages.error(request, "Project සහ Amount අවශ්‍යයි")
            return redirect("add_project_income")

        ProjectIncome.objects.create(
            project_id=project_id,
            income_date=income_date,
            description=description,
            amount=amount,
            gl_account_id=gl_account_id,
            created_by=request.user,
        )

        messages.success(request, "Income එක සාර්ථකව එකතු කරන ලදී")
        return redirect("project_income_list")

    return render(request, "pos/add_project_income.html", {
        "projects": projects,
        "income_gls": income_gls,
    })


# =========================
# PROJECT PROFIT DASHBOARD
# =========================
@user_passes_test(can_use_project)
def project_profit_dashboard(request):
    projects = Project.objects.all().order_by("-created_at")
    return render(request, "pos/project_profit_dashboard.html", {
        "projects": projects,
    })