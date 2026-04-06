import json
from decimal import Decimal, InvalidOperation
from datetime import datetime

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import (
    Item, Category, Supplier, GLMaster,
    Sale, SaleItem, SalesReturn, StockTransaction,
    Project, ProjectExpense, ProjectPettyCash,
    ProjectPettyCashExpense, ProjectIncome, Employee,
    ProjectInvoice, ProjectInvoicePayment, ProjectInvoiceItem,
    SaleRecovery
)

# =========================
# HELPERS
# =========================
def to_decimal(val):
    try:
        if val is None:
            return Decimal("0")
        return Decimal(str(val).replace(",", "").strip())
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def is_owner(user):
    return user.is_superuser or user.groups.filter(name__iexact="Owner").exists()


def is_manager(user):
    return user.groups.filter(name__iexact="Manager").exists()


def is_clerk(user):
    return user.groups.filter(name__iexact="Clerk").exists()


def is_cashier(user):
    return user.groups.filter(name__iexact="Cashier").exists()


def can_add_expenses(user):
    return is_owner(user) or is_cashier(user)


def can_use_pos(user):
    return is_owner(user) or is_cashier(user)


def can_use_income(user):
    return is_owner(user) or is_cashier(user)


def can_use_project(user):
    return is_owner(user) or is_manager(user) or is_clerk(user) or is_cashier(user)


def can_use_gl(user):
    return is_owner(user)


def can_manage_items(user):
    return is_owner(user) or is_manager(user) or is_clerk(user)



def generate_project_id(project_type):
    year = timezone.now().year
    last = Project.objects.filter(project_type=project_type).order_by("-id").first()
    num = int(last.project_id[-3:]) + 1 if last else 1
    return f"PRO{year}{project_type}{num:03d}"


def generate_next_item_code():
    last_item = Item.objects.order_by("-id").first()
    if not last_item or not last_item.item_code:
        return "1000000000"
    try:
        return str(int(str(last_item.item_code).strip()) + 1)
    except Exception:
        return "1000000000"


def generate_petty_cash_expense_no():
    last = ProjectPettyCashExpense.objects.exclude(expense_no__isnull=True).order_by("-id").first()
    if last and last.expense_no and str(last.expense_no).isdigit():
        return str(int(last.expense_no) + 1)
    return "400000"


def generate_project_expense_no():
    last = ProjectExpense.objects.exclude(expense_no__isnull=True).order_by("-id").first()
    if last and last.expense_no and str(last.expense_no).isdigit():
        return str(int(last.expense_no) + 1)
    return "500000"


def mark_inactive(obj, user, reason=""):
    obj.is_active = False
    if hasattr(obj, "inactive_at"):
        obj.inactive_at = timezone.now()
    if hasattr(obj, "inactive_by"):
        obj.inactive_by = user
    if hasattr(obj, "inactive_reason"):
        obj.inactive_reason = reason
    obj.save()


def mark_active(obj):
    obj.is_active = True
    if hasattr(obj, "inactive_at"):
        obj.inactive_at = None
    if hasattr(obj, "inactive_by"):
        obj.inactive_by = None
    if hasattr(obj, "inactive_reason"):
        obj.inactive_reason = ""
    obj.save()


# =========================
# AUTH / DASHBOARD
# =========================
def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("dashboard")
        messages.error(request, "Invalid username or password")

    return render(request, "pos/login.html")


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def dashboard(request):
    return render(request, "pos/dashboard.html", {
        "show_pos": can_use_pos(request.user),
        "show_project": can_use_project(request.user),
        "show_gl": can_use_gl(request.user),
        "show_users": is_owner(request.user),
        "show_items": can_manage_items(request.user),
        "show_employees": is_owner(request.user),
        "is_owner_flag": is_owner(request.user),
    })

# =========================
# USER MANAGEMENT
# =========================
@login_required
@user_passes_test(is_owner)
def user_list(request):
    users = User.objects.all().order_by("username")
    return render(request, "pos/user_list.html", {"users": users})


@login_required
@user_passes_test(is_owner)
def create_user(request):
    roles = Group.objects.all().order_by("name")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        role = request.POST.get("role", "").strip()
        is_active = request.POST.get("is_active") == "on"

        if not username or not password or not role:
            messages.error(request, "Username, password and role are required.")
            return render(request, "pos/create_user.html", {"roles": roles})

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return render(request, "pos/create_user.html", {"roles": roles})

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_active=is_active,
        )

        group = Group.objects.filter(name=role).first()
        if group:
            user.groups.add(group)

        messages.success(request, "User created successfully.")
        return redirect("user_list")

    return render(request, "pos/create_user.html", {"roles": roles})


@login_required
@user_passes_test(is_owner)
def edit_user(request, user_id):
    user_obj = get_object_or_404(User, id=user_id)
    roles = Group.objects.all().order_by("name")
    current_role = user_obj.groups.first()

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        role = request.POST.get("role", "").strip()
        is_active = request.POST.get("is_active") == "on"

        if not username or not role:
            messages.error(request, "Username and role are required.")
            return render(request, "pos/edit_user.html", {
                "user_obj": user_obj,
                "roles": roles,
                "current_role": current_role,
            })

        if User.objects.filter(username=username).exclude(id=user_obj.id).exists():
            messages.error(request, "Username already exists.")
            return render(request, "pos/edit_user.html", {
                "user_obj": user_obj,
                "roles": roles,
                "current_role": current_role,
            })

        user_obj.username = username
        user_obj.first_name = first_name
        user_obj.last_name = last_name
        user_obj.is_active = is_active

        if password:
            user_obj.set_password(password)

        user_obj.save()
        user_obj.groups.clear()

        group = Group.objects.filter(name=role).first()
        if group:
            user_obj.groups.add(group)

        messages.success(request, "User updated successfully.")
        return redirect("user_list")

    return render(request, "pos/edit_user.html", {
        "user_obj": user_obj,
        "roles": roles,
        "current_role": current_role,
    })


# =========================
# POS
# =========================
@user_passes_test(can_use_pos)
def pos_page(request):
    query = request.GET.get("q", "").strip()
    items = Item.objects.filter(is_active=True).select_related("category").order_by("name")
    projects = Project.objects.filter(is_active=True).order_by("-id")
    categories = Category.objects.all().order_by("name")

    if query:
        items = items.filter(
            Q(name__icontains=query) |
            Q(item_code__icontains=query) |
            Q(category__name__icontains=query)
        )

    return render(request, "pos/pos.html", {
        "items": items,
        "projects": projects,
        "categories": categories,
        "query": query,
        "show_items": can_manage_items(request.user),
    })


@user_passes_test(can_use_pos)
def invoice_page(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    return render(request, "pos/invoice.html", {"sale": sale})


# =========================
# SALES RETURN
# =========================
@user_passes_test(can_use_pos)
def sales_return(request):
    sales = Sale.objects.all().order_by("-id")

    if request.method == "POST":
        sale_id = request.POST.get("sale")
        sale_item_id = request.POST.get("sale_item")
        qty = to_decimal(request.POST.get("qty"))
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
            item.updated_by = request.user
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
            "price": str(row.price),
        })

    return JsonResponse({"items": data})


@user_passes_test(can_use_pos)
def return_receipt(request, return_id):
    r = get_object_or_404(SalesReturn, id=return_id)
    return render(request, "pos/return_receipt.html", {"r": r})


# =========================
# ITEM MANAGEMENT
# =========================
@user_passes_test(can_manage_items)
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
                    "next_item_code": generate_next_item_code(),
                })

        try:
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
                updated_by=request.user,
            )
            messages.success(request, "Item added successfully")
            return redirect("add_item")
        except Exception as e:
            messages.error(request, f"Error saving item: {str(e)}")

    return render(request, "pos/add_item.html", {
        "categories": categories,
        "suppliers": suppliers,
        "gl_list": gl_list,
        "next_item_code": generate_next_item_code(),
    })


@user_passes_test(can_manage_items)
def item_list(request):
    query = request.GET.get("q", "").strip()

    items = Item.objects.filter(is_active=True).select_related(
        "category", "supplier", "retail_gl_account", "cost_gl_account"
    ).order_by("-id")

    if query:
        items = items.filter(
            Q(name__icontains=query) |
            Q(item_code__icontains=query)
        )

    low_stock_items = Item.objects.filter(is_active=True, stock__lte=F("reorder_level")).order_by("name")

    return render(request, "pos/item_list.html", {
        "items": items,
        "query": query,
        "low_stock_items": low_stock_items,
    })


@user_passes_test(can_manage_items)
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
        item.updated_by = request.user

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


@user_passes_test(can_manage_items)
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
    today = timezone.localdate()

    try:
        year = int(request.GET.get("year", today.year))
    except (TypeError, ValueError):
        year = today.year

    try:
        month = int(request.GET.get("month", today.month))
    except (TypeError, ValueError):
        month = today.month

    sales = Sale.objects.filter(
        created_at__year=year,
        created_at__month=month
    ).prefetch_related("sale_items__item").order_by("-created_at")

    total_sales = Decimal("0")
    total_discount = Decimal("0")
    total_cost = Decimal("0")
    total_profit = Decimal("0")

    for sale in sales:
        sale_cost = Decimal("0")

        for row in sale.sale_items.all():
            item_cost = Decimal(str(row.item.cost_price or 0))
            qty = Decimal(str(row.qty or 0))
            sale_cost += item_cost * qty

        sale.sale_cost = sale_cost
        sale.sale_profit = Decimal(str(sale.grand_total or 0)) - sale_cost

        total_sales += Decimal(str(sale.grand_total or 0))
        total_discount += Decimal(str(sale.discount or 0))
        total_cost += sale_cost
        total_profit += sale.sale_profit

    summary = {
        "total_sales": total_sales,
        "total_discount": total_discount,
        "total_cost": total_cost,
        "total_profit": total_profit,
    }

    return render(request, "pos/monthly_report.html", {
        "sales": sales,
        "year": year,
        "month": month,
        "summary": summary,
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
@user_passes_test(can_use_project)
def project_list(request):
    projects = Project.objects.filter(is_active=True).order_by("-id")
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
            updated_by=request.user,
        )

        messages.success(request, "Project created successfully")
        return redirect("project_list")

    return render(request, "pos/create_project.html")


# =========================
# PROJECT EXPENSE
# =========================
@user_passes_test(can_use_project)
def project_expense_list(request):
    expenses = ProjectExpense.objects.filter(is_active=True).select_related(
        "project", "gl_account", "item", "created_by"
    ).order_by("-expense_date", "-id")

    project_id = request.GET.get("project")
    if project_id:
        expenses = expenses.filter(project_id=project_id)

    projects = Project.objects.filter(is_active=True).order_by("-id")

    return render(request, "pos/project_expense_list.html", {
        "expenses": expenses,
        "projects": projects,
        "selected_project": project_id,
        "is_owner": is_owner(request.user),
    })

@user_passes_test(can_add_expenses)
def add_project_expense(request):
    projects = Project.objects.filter(is_active=True).order_by("-id")
    expense_gls = GLMaster.objects.filter(gl_type="expense", is_active=True).order_by("gl_code")
    items = Item.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        project_id = request.POST.get("project")
        expense_type = request.POST.get("expense_type") or "direct"
        expense_date = request.POST.get("expense_date") or timezone.now().date()
        description = (request.POST.get("description") or "").strip()
        qty = to_decimal(request.POST.get("qty") or 1)
        unit_price = to_decimal(request.POST.get("unit_price") or 0)
        amount = to_decimal(request.POST.get("amount") or 0)
        gl_account_id = request.POST.get("gl_account") or None
        item_id = request.POST.get("item") or None

        if not project_id:
            messages.error(request, "Project is required.")
            return render(request, "pos/add_project_expense.html", {
                "projects": projects,
                "expense_gls": expense_gls,
                "items": items,
            })

        if not description:
            messages.error(request, "Description is required.")
            return render(request, "pos/add_project_expense.html", {
                "projects": projects,
                "expense_gls": expense_gls,
                "items": items,
            })

        if amount <= 0:
            messages.error(request, "Amount must be greater than 0.")
            return render(request, "pos/add_project_expense.html", {
                "projects": projects,
                "expense_gls": expense_gls,
                "items": items,
            })

        expense = ProjectExpense.objects.create(
            expense_no=generate_project_expense_no(),
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
            item = Item.objects.get(id=item_id, is_active=True)
            item.stock = Decimal(item.stock) - qty
            item.updated_by = request.user
            item.save()

            StockTransaction.objects.create(
                item=item,
                transaction_type="project_issue",
                qty=qty,
            )

        messages.success(request, f"Saved successfully. Expense No: {expense.expense_no}")
        return redirect("project_expense_list")

    return render(request, "pos/add_project_expense.html", {
        "projects": projects,
        "expense_gls": expense_gls,
        "items": items,
    })


@user_passes_test(is_owner)
def delete_project_expense(request, expense_id):
    expense = get_object_or_404(ProjectExpense, id=expense_id)
    mark_inactive(expense, request.user, "Deactivated by owner")
    messages.success(request, "Project expense deactivated successfully.")
    return redirect("project_expense_list")


# =========================
# PETTY CASH
# =========================
@user_passes_test(can_use_project)
def petty_cash_list(request):
    petty_cashes = ProjectPettyCash.objects.filter(is_active=True).order_by("-issue_date", "-id")

    return render(request, "pos/petty_cash_list.html", {
        "petty_cashes": petty_cashes,
        "is_owner": is_owner(request.user),
    })


@user_passes_test(can_use_project)
def add_petty_cash(request):
    employees = Employee.objects.filter(is_active=True).order_by("emp_no")

    if request.method == "POST":
        employee_id = request.POST.get("employee") or None
        issue_date = request.POST.get("issue_date") or timezone.now().date()
        amount_issued = to_decimal(request.POST.get("amount_issued"))
        note = (request.POST.get("note") or "").strip()

        if not employee_id:
            messages.error(request, "Employee is required.")
            return render(request, "pos/add_petty_cash.html", {
                "employees": employees,
            })

        if amount_issued <= 0:
            messages.error(request, "Amount must be greater than 0.")
            return render(request, "pos/add_petty_cash.html", {
                "employees": employees,
            })

        employee = get_object_or_404(Employee, id=employee_id, is_active=True)

        petty_cash_no = f"PC{ProjectPettyCash.objects.count() + 1:05d}"

        petty_cash = ProjectPettyCash.objects.create(
            employee=employee,
            user=employee.user if employee.user else request.user,
            petty_cash_no=petty_cash_no,
            issue_date=issue_date,
            amount_issued=amount_issued,
            note=note,
            created_by=request.user,
        )

        employee.refresh_from_db()
        new_outstanding = employee.petty_cash_outstanding

        if Decimal(str(new_outstanding)) > Decimal(str(employee.petty_cash_limit or 0)):
            messages.warning(
                request,
                f"Petty Cash saved successfully. No: {petty_cash.petty_cash_no} "
                f"| Warning: Employee outstanding balance is over the limit. "
                f"Limit: {employee.petty_cash_limit} | Outstanding: {new_outstanding}"
            )
        else:
            messages.success(request, f"Petty Cash saved successfully. No: {petty_cash.petty_cash_no}")

        return redirect("petty_cash_list")

    return render(request, "pos/add_petty_cash.html", {
        "employees": employees,
    })

@user_passes_test(can_use_project)
def petty_cash_detail(request, petty_cash_id):
    petty_cash = get_object_or_404(
        ProjectPettyCash.objects.select_related("employee", "user", "created_by"),
        id=petty_cash_id,
        is_active=True
    )
    expenses = petty_cash.expenses.filter(is_active=True).select_related(
        "project", "gl_account", "created_by"
    ).order_by("-expense_date", "-id")

    return render(request, "pos/petty_cash_detail.html", {
        "petty_cash": petty_cash,
        "expenses": expenses,
        "is_owner": is_owner(request.user),
    })


@user_passes_test(can_add_expenses)
def add_petty_cash_expense(request, petty_cash_id):
    petty_cash = get_object_or_404(ProjectPettyCash, id=petty_cash_id, is_active=True)
    projects = Project.objects.filter(is_active=True).order_by("-id")
    expense_gls = GLMaster.objects.filter(gl_type="expense", is_active=True).order_by("gl_code")

    if request.method == "POST":
        project_id = request.POST.get("project")
        expense_date = request.POST.get("expense_date") or timezone.now().date()
        description = (request.POST.get("description") or "").strip()
        gl_account_id = request.POST.get("gl_account") or None
        bill_no = (request.POST.get("bill_no") or "").strip()
        bill_date = request.POST.get("bill_date") or None
        amount = to_decimal(request.POST.get("amount"))
        note = (request.POST.get("note") or "").strip()

        if not project_id:
            messages.error(request, "Project is required.")
            return render(request, "pos/add_petty_cash_expense.html", {
                "petty_cash": petty_cash,
                "projects": projects,
                "expense_gls": expense_gls,
            })

        if not description:
            messages.error(request, "Description is required.")
            return render(request, "pos/add_petty_cash_expense.html", {
                "petty_cash": petty_cash,
                "projects": projects,
                "expense_gls": expense_gls,
            })

        if amount <= 0:
            messages.error(request, "Amount must be greater than 0.")
            return render(request, "pos/add_petty_cash_expense.html", {
                "petty_cash": petty_cash,
                "projects": projects,
                "expense_gls": expense_gls,
            })

        if amount > petty_cash.balance:
            messages.error(request, "Expense exceeds petty cash balance.")
            return render(request, "pos/add_petty_cash_expense.html", {
                "petty_cash": petty_cash,
                "projects": projects,
                "expense_gls": expense_gls,
            })

        expense = ProjectPettyCashExpense.objects.create(
            expense_no=generate_petty_cash_expense_no(),
            petty_cash=petty_cash,
            project_id=project_id,
            expense_date=expense_date,
            description=description,
            gl_account_id=gl_account_id,
            bill_no=bill_no,
            bill_date=bill_date or None,
            amount=amount,
            note=note,
            created_by=request.user,
        )

        messages.success(request, f"Saved successfully. Expense No: {expense.expense_no}")
        return redirect("petty_cash_detail", petty_cash_id=petty_cash.id)

    return render(request, "pos/add_petty_cash_expense.html", {
        "petty_cash": petty_cash,
        "projects": projects,
        "expense_gls": expense_gls,
    })


@user_passes_test(is_owner)
def delete_petty_cash(request, petty_cash_id):
    petty_cash = get_object_or_404(ProjectPettyCash, id=petty_cash_id)
    mark_inactive(petty_cash, request.user, "Deactivated by owner")
    messages.success(request, "Petty cash deactivated successfully.")
    return redirect("petty_cash_list")


@user_passes_test(is_owner)
def delete_petty_cash_expense(request, expense_id):
    expense = get_object_or_404(ProjectPettyCashExpense, id=expense_id)
    petty_cash_id = expense.petty_cash.id
    mark_inactive(expense, request.user, "Deactivated by owner")
    messages.success(request, "Petty cash expense deactivated successfully.")
    return redirect("petty_cash_detail", petty_cash_id=petty_cash_id)


# =========================
# PROJECT INCOME
# =========================
@user_passes_test(can_use_project)
def project_income_list(request):
    incomes = ProjectIncome.objects.select_related("project", "gl_account", "created_by").order_by("-income_date", "-id")
    projects = Project.objects.filter(is_active=True).order_by("-id")

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
    projects = Project.objects.filter(is_active=True).order_by("-id")
    income_gls = GLMaster.objects.filter(gl_type="income", is_active=True).order_by("gl_code")

    if request.method == "POST":
        project_id = request.POST.get("project")
        income_date = request.POST.get("income_date") or timezone.now().date()
        description = request.POST.get("description", "").strip()
        amount = to_decimal(request.POST.get("amount"))
        gl_account_id = request.POST.get("gl_account") or None

        if not project_id or amount <= 0:
            messages.error(request, "Project and valid Amount are required.")
            return redirect("add_project_income")

        ProjectIncome.objects.create(
            project_id=project_id,
            income_date=income_date,
            description=description,
            amount=amount,
            gl_account_id=gl_account_id,
            created_by=request.user,
        )

        messages.success(request, "Income added successfully.")
        return redirect("project_income_list")

    return render(request, "pos/add_project_income.html", {
        "projects": projects,
        "income_gls": income_gls,
    })


# =========================
# PROJECT PROFIT
# =========================
@user_passes_test(can_use_project)
def project_profit_dashboard(request):
    projects = Project.objects.filter(is_active=True).order_by("-created_at")
    project_rows = []

    for project in projects:
        direct_expense = project.expenses.filter(is_active=True).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")

        petty_cash_expense = ProjectPettyCashExpense.objects.filter(
            project=project,
            is_active=True
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        total_income = ProjectInvoicePayment.objects.filter(
            invoice__project=project,
            invoice__is_active=True,
            is_active=True
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        total_expense = Decimal(str(direct_expense)) + Decimal(str(petty_cash_expense))
        profit = Decimal(str(total_income)) - total_expense

        project_rows.append({
            "project": project,
            "total_income": Decimal(str(total_income)),
            "direct_expense": Decimal(str(direct_expense)),
            "petty_cash_expense": Decimal(str(petty_cash_expense)),
            "total_expense": total_expense,
            "profit": profit,
        })

    grand_income = sum((row["total_income"] for row in project_rows), Decimal("0"))
    grand_direct_expense = sum((row["direct_expense"] for row in project_rows), Decimal("0"))
    grand_petty_cash = sum((row["petty_cash_expense"] for row in project_rows), Decimal("0"))
    grand_total_expense = sum((row["total_expense"] for row in project_rows), Decimal("0"))
    grand_profit = sum((row["profit"] for row in project_rows), Decimal("0"))

    return render(request, "pos/project_profit_dashboard.html", {
        "project_rows": project_rows,
        "grand_income": grand_income,
        "grand_direct_expense": grand_direct_expense,
        "grand_petty_cash": grand_petty_cash,
        "grand_total_expense": grand_total_expense,
        "grand_profit": grand_profit,
    })

# =========================
# EMPLOYEES
# =========================
@user_passes_test(is_owner)
def employee_list(request):
    employees = Employee.objects.select_related("user").order_by("emp_no")
    return render(request, "pos/employee_list.html", {
        "employees": employees,
    })


@user_passes_test(is_owner)
def add_employee(request):
    users = User.objects.filter(is_active=True).order_by("username")

    if request.method == "POST":
        user_id = request.POST.get("user") or None
        full_name = (request.POST.get("full_name") or "").strip()
        designation = (request.POST.get("designation") or "").strip()
        address = (request.POST.get("address") or "").strip()
        tel = (request.POST.get("tel") or "").strip()
        petty_cash_limit = to_decimal(request.POST.get("petty_cash_limit"))
        is_active = request.POST.get("is_active") == "on"

        if not full_name:
            messages.error(request, "Employee name is required.")
            return render(request, "pos/add_employee.html", {"users": users})

        Employee.objects.create(
            user_id=user_id if user_id else None,
            full_name=full_name,
            designation=designation,
            address=address,
            tel=tel,
            petty_cash_limit=petty_cash_limit,
            is_active=is_active,
        )

        messages.success(request, "Employee created successfully.")
        return redirect("employee_list")

    return render(request, "pos/add_employee.html", {
        "users": users,
    })


@user_passes_test(is_owner)
def edit_employee(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    users = User.objects.filter(is_active=True).order_by("username")

    if request.method == "POST":
        user_id = request.POST.get("user") or None
        full_name = (request.POST.get("full_name") or "").strip()
        designation = (request.POST.get("designation") or "").strip()
        address = (request.POST.get("address") or "").strip()
        tel = (request.POST.get("tel") or "").strip()
        petty_cash_limit = to_decimal(request.POST.get("petty_cash_limit"))
        is_active = request.POST.get("is_active") == "on"

        if not full_name:
            messages.error(request, "Employee name is required.")
            return render(request, "pos/edit_employee.html", {
                "employee": employee,
                "users": users,
            })

        employee.user_id = user_id if user_id else None
        employee.full_name = full_name
        employee.designation = designation
        employee.address = address
        employee.tel = tel
        employee.petty_cash_limit = petty_cash_limit
        employee.is_active = is_active
        employee.save()

        messages.success(request, "Employee updated successfully.")
        return redirect("employee_list")

    return render(request, "pos/edit_employee.html", {
        "employee": employee,
        "users": users,
    })


# =========================
# PROJECT INVOICE / PAYMENTS
# =========================
@user_passes_test(can_use_income)
def project_invoice_list(request):
    project_id = request.GET.get("project")
    show_inactive = request.GET.get("show_inactive") == "1"

    invoices = ProjectInvoice.objects.select_related(
        "project", "created_by"
    ).order_by("-invoice_date", "-id")

    if not show_inactive:
        invoices = invoices.filter(is_active=True)

    if project_id:
        invoices = invoices.filter(project_id=project_id)

    projects = Project.objects.filter(is_active=True).order_by("-id")

    return render(request, "pos/project_invoice_list.html", {
        "invoices": invoices,
        "projects": projects,
        "selected_project": project_id,
        "show_inactive": show_inactive,
        "is_owner": is_owner(request.user),
    })
@user_passes_test(can_use_income)
def add_project_invoice(request):
    projects = Project.objects.filter(is_active=True).order_by("-id")
    items = Item.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        project_id = request.POST.get("project")
        invoice_date = request.POST.get("invoice_date") or timezone.now().date()
        bill_to_name = (request.POST.get("bill_to_name") or "").strip()
        bill_to_address = (request.POST.get("bill_to_address") or "").strip()
        invoice_type = request.POST.get("invoice_type") or "advance"
        note = (request.POST.get("note") or "").strip()

        item_codes = request.POST.getlist("item_code[]")
        descriptions = request.POST.getlist("description[]")
        qtys = request.POST.getlist("qty[]")
        prices = request.POST.getlist("price_each[]")

        if not project_id:
            messages.error(request, "Project is required.")
            return render(request, "pos/add_project_invoice.html", {
                "projects": projects,
                "items": items,
            })

        cleaned_rows = []
        total_amount = Decimal("0")

        row_count = max(len(descriptions), len(qtys), len(prices), len(item_codes))

        for i in range(row_count):
            item_code = (item_codes[i] if i < len(item_codes) else "").strip()
            description = (descriptions[i] if i < len(descriptions) else "").strip()
            qty = to_decimal(qtys[i] if i < len(qtys) else 0)
            price_each = to_decimal(prices[i] if i < len(prices) else 0)

            if not item_code and not description and qty <= 0 and price_each <= 0:
                continue

            if not description:
                messages.error(request, f"Description is required for row {i+1}.")
                return render(request, "pos/add_project_invoice.html", {
                    "projects": projects,
                    "items": items,
                })

            if qty <= 0:
                messages.error(request, f"Qty must be greater than 0 in row {i+1}.")
                return render(request, "pos/add_project_invoice.html", {
                    "projects": projects,
                    "items": items,
                })

            if price_each < 0:
                messages.error(request, f"Price cannot be negative in row {i+1}.")
                return render(request, "pos/add_project_invoice.html", {
                    "projects": projects,
                    "items": items,
                })

            amount = qty * price_each
            total_amount += amount

            cleaned_rows.append({
                "item_code": item_code or None,
                "description": description,
                "qty": qty,
                "price_each": price_each,
                "amount": amount,
            })

        if not cleaned_rows:
            messages.error(request, "At least one invoice item is required.")
            return render(request, "pos/add_project_invoice.html", {
                "projects": projects,
                "items": items,
            })

        first_description = cleaned_rows[0]["description"]

        invoice = ProjectInvoice.objects.create(
            project_id=project_id,
            invoice_date=invoice_date,
            bill_to_name=bill_to_name,
            bill_to_address=bill_to_address,
            invoice_type=invoice_type,
            description=first_description,
            qty=Decimal("1.00"),
            price_each=total_amount,
            total_amount=total_amount,
            note=note,
            created_by=request.user,
        )

        for row in cleaned_rows:
            ProjectInvoiceItem.objects.create(
                invoice=invoice,
                item_code=row["item_code"],
                description=row["description"],
                qty=row["qty"],
                price_each=row["price_each"],
                amount=row["amount"],
            )

        invoice.save()

        messages.success(request, f"Invoice created successfully. Invoice No: {invoice.invoice_no}")
        return redirect("print_project_invoice", invoice_id=invoice.id)

    return render(request, "pos/add_project_invoice.html", {
        "projects": projects,
        "items": items,
    })

@user_passes_test(can_use_income)
def project_invoice_detail(request, invoice_id):
    invoice = get_object_or_404(
        ProjectInvoice.objects.select_related("project", "created_by"),
        id=invoice_id
    )

    show_inactive = request.GET.get("show_inactive") == "1"

    invoice_items = invoice.items.all()

    payments = invoice.payments.select_related("created_by").order_by("-payment_date", "-id")
    if not show_inactive:
        payments = payments.filter(is_active=True)

    return render(request, "pos/project_invoice_detail.html", {
        "invoice": invoice,
        "invoice_items": invoice_items,
        "payments": payments,
        "show_inactive": show_inactive,
        "is_owner": is_owner(request.user),
    })
@user_passes_test(can_use_income)
def add_project_invoice_payment(request, invoice_id):
    invoice = get_object_or_404(ProjectInvoice, id=invoice_id)

    if request.method == "POST":
        try:
            payment_date = request.POST.get("payment_date") or timezone.now().date()
            payment_type = request.POST.get("payment_type") or "advance"
            payment_method = request.POST.get("payment_method") or "cash"
            amount = to_decimal(request.POST.get("amount"))
            card_no = (request.POST.get("card_no") or "").strip()
            cheque_no = (request.POST.get("cheque_no") or "").strip()
            note = (request.POST.get("note") or "").strip()

            if amount <= 0:
                messages.error(request, "Amount must be greater than 0.")
                return render(request, "pos/add_project_invoice_payment.html", {
                    "invoice": invoice,
                })

            if amount > invoice.balance_amount:
                messages.error(request, "Payment exceeds invoice balance.")
                return render(request, "pos/add_project_invoice_payment.html", {
                    "invoice": invoice,
                })

            if payment_method == "card" and not card_no:
                messages.error(request, "Card No is required for card payments.")
                return render(request, "pos/add_project_invoice_payment.html", {
                    "invoice": invoice,
                })

            if payment_method == "cheque" and not cheque_no:
                messages.error(request, "Cheque No is required for cheque payments.")
                return render(request, "pos/add_project_invoice_payment.html", {
                    "invoice": invoice,
                })

            payment = ProjectInvoicePayment.objects.create(
                invoice=invoice,
                payment_date=payment_date,
                payment_type=payment_type,
                payment_method=payment_method,
                card_no=card_no if payment_method == "card" else None,
                cheque_no=cheque_no if payment_method == "cheque" else None,
                amount=amount,
                note=note,
                created_by=request.user,
            )

            invoice.save()

            messages.success(request, "Payment added successfully.")
            return redirect("print_project_payment_receipt", payment_id=payment.id)

        except Exception as e:
            messages.error(request, f"Error saving payment: {str(e)}")
            return render(request, "pos/add_project_invoice_payment.html", {
                "invoice": invoice,
            })

    return render(request, "pos/add_project_invoice_payment.html", {
        "invoice": invoice,
    })

@user_passes_test(is_owner)
def delete_project_invoice_payment(request, payment_id):
    payment = get_object_or_404(ProjectInvoicePayment, id=payment_id)
    invoice_id = payment.invoice.id
    mark_inactive(payment, request.user, "Deactivated by owner")
    payment.invoice.save()
    messages.success(request, "Invoice payment deactivated successfully.")
    return redirect("project_invoice_detail", invoice_id=invoice_id)


@user_passes_test(is_owner)
def delete_project_invoice(request, invoice_id):
    invoice = get_object_or_404(ProjectInvoice, id=invoice_id)
    mark_inactive(invoice, request.user, "Deactivated by owner")
    messages.success(request, "Project invoice deactivated successfully.")
    return redirect("project_invoice_list")


@user_passes_test(can_use_income)
def print_project_invoice(request, invoice_id):
    invoice = get_object_or_404(
        ProjectInvoice.objects.select_related("project", "created_by"),
        id=invoice_id,
        is_active=True
    )
    invoice_items = invoice.items.all()

    return render(request, "pos/print_project_invoice.html", {
        "invoice": invoice,
        "invoice_items": invoice_items,
    })

@user_passes_test(is_owner)
def edit_xxx(request, id):
    obj = get_object_or_404(Model, id=id)
    if request.method == "POST":
        # fields update
        # updated_by = request.user  (if model has it)
        obj.save()
        messages.success(request, "Updated successfully.")
        return redirect("list_page")
    return render(request, "pos/edit_xxx.html", {"obj": obj})

@user_passes_test(is_owner)
def edit_project(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    project_types = Project.PROJECT_TYPE_CHOICES

    if request.method == "POST":
        project.project_name = (request.POST.get("project_name") or "").strip()
        project.project_type = request.POST.get("project_type") or project.project_type
        project.client_name = (request.POST.get("client_name") or "").strip()
        project.location = (request.POST.get("location") or "").strip()
        project.estimated_value = to_decimal(request.POST.get("estimated_value"))
        project.status = request.POST.get("status") or project.status
        project.updated_by = request.user
        project.save()

        messages.success(request, "Project updated successfully.")
        return redirect("project_list")

    return render(request, "pos/edit_project.html", {
        "project": project,
        "project_types": project_types,
    })


@user_passes_test(is_owner)
def edit_petty_cash(request, petty_cash_id):
    petty_cash = get_object_or_404(ProjectPettyCash, id=petty_cash_id)
    employees = Employee.objects.filter(is_active=True).order_by("emp_no")

    if request.method == "POST":
        employee_id = request.POST.get("employee") or None
        issue_date = request.POST.get("issue_date") or timezone.now().date()
        amount_issued = to_decimal(request.POST.get("amount_issued"))
        note = (request.POST.get("note") or "").strip()

        if not employee_id:
            messages.error(request, "Employee is required.")
            return render(request, "pos/edit_petty_cash.html", {
                "petty_cash": petty_cash,
                "employees": employees,
            })

        if amount_issued <= 0:
            messages.error(request, "Amount must be greater than 0.")
            return render(request, "pos/edit_petty_cash.html", {
                "petty_cash": petty_cash,
                "employees": employees,
            })

        employee = get_object_or_404(Employee, id=employee_id, is_active=True)

        petty_cash.employee = employee
        petty_cash.user = employee.user if employee.user else petty_cash.user
        petty_cash.issue_date = issue_date
        petty_cash.amount_issued = amount_issued
        petty_cash.note = note
        petty_cash.save()

        employee.refresh_from_db()
        new_outstanding = employee.petty_cash_outstanding

        if Decimal(str(new_outstanding)) > Decimal(str(employee.petty_cash_limit or 0)):
            messages.warning(
                request,
                f"Petty cash updated successfully. "
                f"Warning: Employee outstanding balance is over the limit. "
                f"Limit: {employee.petty_cash_limit} | Outstanding: {new_outstanding}"
            )
        else:
            messages.success(request, "Petty cash updated successfully.")

        return redirect("petty_cash_list")

    return render(request, "pos/edit_petty_cash.html", {
        "petty_cash": petty_cash,
        "employees": employees,
    })

@user_passes_test(is_owner)
def edit_project_expense(request, expense_id):
    expense = get_object_or_404(ProjectExpense, id=expense_id)
    projects = Project.objects.filter(is_active=True).order_by("-id")
    expense_gls = GLMaster.objects.filter(gl_type="expense", is_active=True).order_by("gl_code")
    items = Item.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        expense.project_id = request.POST.get("project") or expense.project_id
        expense.expense_type = request.POST.get("expense_type") or expense.expense_type
        expense.expense_date = request.POST.get("expense_date") or expense.expense_date
        expense.description = (request.POST.get("description") or "").strip()
        expense.qty = to_decimal(request.POST.get("qty") or 1)
        expense.unit_price = to_decimal(request.POST.get("unit_price") or 0)
        expense.amount = to_decimal(request.POST.get("amount") or 0)
        expense.gl_account_id = request.POST.get("gl_account") or None
        expense.item_id = request.POST.get("item") or None

        if not expense.project_id:
            messages.error(request, "Project is required.")
            return render(request, "pos/edit_project_expense.html", {
                "expense": expense,
                "projects": projects,
                "expense_gls": expense_gls,
                "items": items,
            })

        if not expense.description:
            messages.error(request, "Description is required.")
            return render(request, "pos/edit_project_expense.html", {
                "expense": expense,
                "projects": projects,
                "expense_gls": expense_gls,
                "items": items,
            })

        if expense.amount <= 0:
            messages.error(request, "Amount must be greater than 0.")
            return render(request, "pos/edit_project_expense.html", {
                "expense": expense,
                "projects": projects,
                "expense_gls": expense_gls,
                "items": items,
            })

        expense.save()
        messages.success(request, "Project expense updated successfully.")
        return redirect("project_expense_list")

    return render(request, "pos/edit_project_expense.html", {
        "expense": expense,
        "projects": projects,
        "expense_gls": expense_gls,
        "items": items,
    })
def number_to_words(n):
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
    teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen",
             "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def words_under_1000(num):
        result = ""

        if num >= 100:
            result += ones[num // 100] + " Hundred "
            num %= 100

        if 10 <= num <= 19:
            result += teens[num - 10] + " "
        else:
            if num >= 20:
                result += tens[num // 10] + " "
                num %= 10
            if num > 0:
                result += ones[num] + " "

        return result.strip()

    if n == 0:
        return "Zero"

    parts = []

    billions = n // 1000000000
    if billions:
        parts.append(words_under_1000(billions) + " Billion")
        n %= 1000000000

    millions = n // 1000000
    if millions:
        parts.append(words_under_1000(millions) + " Million")
        n %= 1000000

    thousands = n // 1000
    if thousands:
        parts.append(words_under_1000(thousands) + " Thousand")
        n %= 1000

    if n:
        parts.append(words_under_1000(n))

    return " ".join(parts).strip()


def amount_to_words(amount):
    amount = Decimal(str(amount or 0)).quantize(Decimal("0.01"))
    rupees = int(amount)
    cents = int((amount - Decimal(rupees)) * 100)

    words = number_to_words(rupees) + " Rupees"
    if cents > 0:
        words += " and " + number_to_words(cents) + " Cents"
    words += " Only"

    return words

@user_passes_test(can_use_income)
def print_project_payment_receipt(request, payment_id):
    payment = get_object_or_404(
        ProjectInvoicePayment.objects.select_related(
            "invoice",
            "invoice__project",
            "created_by"
        ),
        id=payment_id
    )

    invoice = payment.invoice
    amount_in_words = amount_to_words(payment.amount)

    return render(request, "pos/print_project_payment_receipt.html", {
        "payment": payment,
        "invoice": invoice,
        "amount_in_words": amount_in_words,
    })

@user_passes_test(is_owner)
def project_issue_approval_list(request):
    status_filter = request.GET.get("status", "pending").strip()

    sales = Sale.objects.filter(
        sale_type="project_issue"
    ).select_related(
        "project", "created_by", "approved_by"
    ).prefetch_related(
        "sale_items__item"
    ).order_by("-created_at")

    if status_filter in ["pending", "approved", "rejected"]:
        sales = sales.filter(approval_status=status_filter)

    return render(request, "pos/project_issue_approval_list.html", {
        "sales": sales,
        "status_filter": status_filter,
    })

@user_passes_test(is_owner)
def approve_project_issue(request, sale_id):
    sale = get_object_or_404(
        Sale.objects.select_related("project", "created_by").prefetch_related("sale_items__item"),
        id=sale_id,
        sale_type="project_issue"
    )

    if not sale.project:
        messages.error(request, "Project not found for this issue.")
        return redirect("project_issue_approval_list")

    if sale.is_posted_to_project_expense:
        messages.warning(request, "This project issue is already posted.")
        return redirect("project_issue_approval_list")

    if sale.approval_status == "approved":
        messages.warning(request, "This project issue is already approved.")
        return redirect("project_issue_approval_list")

    for row in sale.sale_items.all():
        ProjectExpense.objects.create(
            expense_no=generate_project_expense_no(),
            project=sale.project,
            expense_type="inventory",
            expense_date=timezone.localdate(sale.created_at),
            item=row.item,
            description=f"POS Issue - {sale.invoice_no} - {row.item.name}",
            qty=row.qty,
            unit_price=row.price,
            amount=row.amount,
            gl_account=row.item.cost_gl_account if row.item and row.item.cost_gl_account else None,
            created_by=sale.created_by,
            source_sale=sale,
        )

    sale.approval_status = "approved"
    sale.approved_by = request.user
    sale.approved_at = timezone.now()
    sale.is_posted_to_project_expense = True
    sale.save()

    messages.success(request, f"Project issue {sale.invoice_no} approved successfully.")
    return redirect("project_issue_approval_list")

@user_passes_test(is_owner)
def reject_project_issue(request, sale_id):
    sale = get_object_or_404(
        Sale,
        id=sale_id,
        sale_type="project_issue"
    )

    if sale.approval_status == "approved":
        messages.error(request, "Approved issue cannot be rejected.")
        return redirect("project_issue_approval_list")

    sale.approval_status = "rejected"
    sale.approved_by = request.user
    sale.approved_at = timezone.now()
    sale.approval_note = "Rejected by owner"
    sale.save()

    messages.success(request, f"Project issue {sale.invoice_no} rejected.")
    return redirect("project_issue_approval_list")

@user_passes_test(can_use_pos)
def credit_sales_list(request):
    status_filter = request.GET.get("status", "unpaid").strip()
    query = request.GET.get("q", "").strip()

    sales = Sale.objects.filter(payment_method="credit").select_related(
        "created_by", "project"
    ).order_by("-created_at")

    if query:
        sales = sales.filter(
            Q(invoice_no__icontains=query) |
            Q(customer_name__icontains=query) |
            Q(project__project_id__icontains=query) |
            Q(project__project_name__icontains=query)
        )

    filtered_sales = []
    for sale in sales:
        status = sale.credit_status
        if status_filter == "all" or status == status_filter:
            filtered_sales.append(sale)

    return render(request, "pos/credit_sales_list.html", {
        "sales": filtered_sales,
        "status_filter": status_filter,
        "query": query,
    })

@user_passes_test(can_use_pos)
def add_sale_recovery(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id, payment_method="credit")

    if sale.credit_status == "paid":
        messages.warning(request, "This credit sale is already fully paid.")
        return redirect("credit_sales_list")

    if request.method == "POST":
        recovery_date = request.POST.get("recovery_date") or timezone.localdate()
        payment_method = request.POST.get("payment_method") or "cash"
        amount = to_decimal(request.POST.get("amount"))
        card_no = (request.POST.get("card_no") or "").strip()
        cheque_no = (request.POST.get("cheque_no") or "").strip()
        note = (request.POST.get("note") or "").strip()

        if amount <= 0:
            messages.error(request, "Amount must be greater than 0.")
            return render(request, "pos/add_sale_recovery.html", {"sale": sale})

        if amount > sale.credit_balance:
            messages.error(request, "Recovery amount exceeds balance.")
            return render(request, "pos/add_sale_recovery.html", {"sale": sale})

        if payment_method == "card" and not card_no:
            messages.error(request, "Card No is required for card payments.")
            return render(request, "pos/add_sale_recovery.html", {"sale": sale})

        if payment_method == "cheque" and not cheque_no:
            messages.error(request, "Cheque No is required for cheque payments.")
            return render(request, "pos/add_sale_recovery.html", {"sale": sale})

        recovery = SaleRecovery.objects.create(
            sale=sale,
            recovery_date=recovery_date,
            payment_method=payment_method,
            amount=amount,
            card_no=card_no if payment_method == "card" else None,
            cheque_no=cheque_no if payment_method == "cheque" else None,
            note=note,
            created_by=request.user,
        )

        messages.success(request, "Recovery added successfully.")
        return redirect("print_sale_recovery_receipt", recovery_id=recovery.id)

    return render(request, "pos/add_sale_recovery.html", {
        "sale": sale,
    })

@user_passes_test(can_use_pos)
def print_sale_recovery_receipt(request, recovery_id):
    recovery = get_object_or_404(
        SaleRecovery.objects.select_related("sale", "sale__project", "created_by"),
        id=recovery_id
    )

    return render(request, "pos/print_sale_recovery_receipt.html", {
        "recovery": recovery,
        "sale": recovery.sale,
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

        total = to_decimal(data.get("total"))
        discount = to_decimal(data.get("discount"))
        grand_total = to_decimal(data.get("grand_total"))

        payment_method = data.get("payment_method", "cash")
        received_amount = to_decimal(data.get("received"))
        balance = to_decimal(data.get("balance"))
        card_last4 = data.get("card_last4") or None
        cheque_number = data.get("cheque_number") or None

        customer_name = (data.get("customer_name") or "").strip() or None
        customer_phone = (data.get("customer_phone") or "").strip() or None

        sale_type = (data.get("sale_type") or "retail").strip()
        project_id = data.get("project_id") or None

        if sale_type not in ["retail", "project_issue"]:
            sale_type = "retail"

        if sale_type == "project_issue" and not project_id:
            return JsonResponse({
                "status": "error",
                "message": "Project is required for project issue sales."
            }, status=400)

        project = None
        if project_id:
            project = Project.objects.filter(id=project_id, is_active=True).first()
            if not project and sale_type == "project_issue":
                return JsonResponse({
                    "status": "error",
                    "message": "Selected project not found."
                }, status=400)

        invoice_no = f"INV{Sale.objects.count() + 1:05d}"

        if sale_type == "project_issue":
            approval_status = "pending"
            if not customer_name and project:
                customer_name = f"Project - {project.project_id}"
        else:
            approval_status = "na"

        sale = Sale.objects.create(
            invoice_no=invoice_no,
            total=total,
            discount=discount,
            grand_total=grand_total,
            sale_type=sale_type,
            project=project if sale_type == "project_issue" else None,
            approval_status=approval_status,
            payment_method=payment_method,
            received_amount=received_amount if payment_method == "cash" else None,
            balance=balance if payment_method in ["cash", "credit"] else None,
            card_last4=card_last4 if payment_method == "card" else None,
            cheque_number=cheque_number if payment_method == "credit" else None,
            customer_name=customer_name,
            customer_phone=customer_phone,
            created_by=request.user,
        )

        for i in items:
            item = Item.objects.get(id=i["id"], is_active=True)
            qty = to_decimal(i.get("qty"))
            price = to_decimal(i.get("price"))
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
                item.updated_by = request.user
                item.save()

                StockTransaction.objects.create(
                    item=item,
                    transaction_type="sale",
                    qty=qty,
                )

        return JsonResponse({
            "status": "success",
            "sale_id": sale.id,
            "invoice_no": sale.invoice_no,
            "sale_type": sale.sale_type,
            "approval_status": sale.approval_status,
        })

    except Item.DoesNotExist:
        return JsonResponse({
            "status": "error",
            "message": "Selected item not found."
        }, status=404)

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)