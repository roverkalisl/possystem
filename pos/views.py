import json
from decimal import Decimal, InvalidOperation
from datetime import datetime

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from django.db import transaction
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import (
    Item, Category, Supplier, GLMaster, Customer,
    Sale, SaleItem, SalesReturn, StockTransaction, SaleRecovery,
    Project, ProjectExpense, ProjectPettyCash,
    ProjectPettyCashExpense, ProjectIncome, Employee,
    ProjectInvoice, ProjectInvoicePayment, ProjectInvoiceItem,
    SupplierAdvance, SupplierSettlement, PurchaseOrder, PurchaseOrderItem
)
# =========================
# HELPERS
# =========================
def get_customer_outstanding(customer):
    total_outstanding = Decimal("0")
    credit_sales = customer.sales.filter(payment_method="credit")

    for sale in credit_sales:
        total_outstanding += Decimal(str(sale.credit_balance or 0))

    return total_outstanding



def generate_purchase_order_no():
    last = PurchaseOrder.objects.exclude(po_no__isnull=True).order_by("-id").first()
    if last and last.po_no and str(last.po_no).replace("PO", "").isdigit():
        return f"PO{int(str(last.po_no).replace('PO', '')) + 1:05d}"
    return "PO00001"

def generate_customer_code():
    last = Customer.objects.order_by("-id").first()
    if not last or not last.customer_code:
        return "CUS0001"
    try:
        return f"CUS{int(last.customer_code.replace('CUS', '')) + 1:04d}"
    except Exception:
        return "CUS0001"

def validate_item_gl_or_message(item):
    if not item.retail_gl_account:
        return f"Retail GL Account missing for item: {item.name}"

    if not item.is_service and not item.cost_gl_account:
        return f"Cost GL Account missing for non-service item: {item.name}"

    return None


def build_item_context(user):
    categories = Category.objects.filter(is_active=True).order_by("name")
    suppliers = Supplier.objects.filter(is_active=True).order_by("name")
    gl_list = GLMaster.objects.filter(is_active=True).order_by("gl_code")
    last_item = Item.objects.order_by("-id").first()
    next_item_code = f"ITM{((last_item.id + 1) if last_item else 1):05d}"

    return {
        "categories": categories,
        "suppliers": suppliers,
        "gl_list": gl_list,
        "next_item_code": next_item_code,
    }

def to_decimal(val):
    try:
        if val is None:
            return Decimal("0")
        return Decimal(str(val).replace(",", "").strip())
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")
    
def generate_supplier_advance_no():
    last = SupplierAdvance.objects.exclude(advance_no__isnull=True).order_by("-id").first()
    if last and last.advance_no and str(last.advance_no).replace("SADV", "").isdigit():
        return f"SADV{int(str(last.advance_no).replace('SADV', '')) + 1:05d}"
    return "SADV00001"


def generate_supplier_settlement_no():
    last = SupplierSettlement.objects.exclude(settlement_no__isnull=True).order_by("-id").first()
    if last and last.settlement_no and str(last.settlement_no).replace("SSET", "").isdigit():
        return f"SSET{int(str(last.settlement_no).replace('SSET', '')) + 1:05d}"
    return "SSET00001"

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
    customers = Customer.objects.filter(is_active=True).order_by("name")

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
        "customers": customers,
        "query": query,
        "show_items": can_manage_items(request.user),
    })

@user_passes_test(can_use_pos)
def save_sale(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)

    try:
        with transaction.atomic():
            data = json.loads(request.body)

            items = data.get("items", [])
            if not items:
                return JsonResponse({"status": "error", "message": "Cart empty"}, status=400)

            extra_discount = to_decimal(data.get("discount"))
            payment_method = (data.get("payment_method") or "cash").strip()
            received_amount = to_decimal(data.get("received"))
            card_last4 = (data.get("card_last4") or "").strip() or None
            cheque_number = (data.get("cheque_number") or "").strip() or None

            customer_name = (data.get("customer_name") or "").strip() or None
            customer_phone = (data.get("customer_phone") or "").strip() or None
            customer_id = data.get("customer_id") or None

            sale_type = (data.get("sale_type") or "retail").strip()
            project_id = data.get("project_id") or None

            if sale_type not in ["retail", "project_issue"]:
                sale_type = "retail"

            if sale_type == "project_issue" and not project_id:
                return JsonResponse({"status": "error", "message": "Project is required for project issue sales."}, status=400)

            project = None
            if project_id:
                project = Project.objects.filter(id=project_id, is_active=True).first()
                if not project and sale_type == "project_issue":
                    return JsonResponse({"status": "error", "message": "Selected project not found."}, status=400)

            customer = None
            if customer_id:
                customer = Customer.objects.filter(id=customer_id, is_active=True).first()
                if not customer:
                    return JsonResponse({"status": "error", "message": "Selected customer not found."}, status=400)

                if not customer_name:
                    customer_name = customer.name
                if not customer_phone:
                    customer_phone = customer.phone

            if payment_method not in ["cash", "card", "credit"]:
                return JsonResponse({"status": "error", "message": "Invalid payment method."}, status=400)

            if payment_method == "card" and not card_last4:
                return JsonResponse({"status": "error", "message": "Card last 4 digits required for card payment."}, status=400)

            if payment_method == "credit" and not cheque_number:
                return JsonResponse({"status": "error", "message": "Cheque / Ref No required for credit sale."}, status=400)

            if payment_method == "credit":
                if not customer:
                    return JsonResponse({"status": "error", "message": "Please select a customer for credit sale."}, status=400)

                if not customer.registration_no:
                    return JsonResponse({
                        "status": "error",
                        "message": f"Customer registration number is required for credit sale. Please update customer: {customer.name}"
                    }, status=400)

            if sale_type == "project_issue" and not customer_name and project:
                customer_name = f"Project - {project.project_id}"

            invoice_no = f"INV{Sale.objects.count() + 1:05d}"
            approval_status = "pending" if sale_type == "project_issue" else "na"

            sale = Sale.objects.create(
                invoice_no=invoice_no,
                total=Decimal("0"),
                discount=extra_discount,
                grand_total=Decimal("0"),
                sale_type=sale_type,
                project=project if sale_type == "project_issue" else None,
                approval_status=approval_status,
                payment_method=payment_method,
                received_amount=received_amount if payment_method == "cash" else None,
                balance=Decimal("0"),
                card_last4=card_last4 if payment_method == "card" else None,
                cheque_number=cheque_number if payment_method == "credit" else None,
                customer=customer,
                customer_name=customer_name,
                customer_phone=customer_phone,
                created_by=request.user,
            )

            calculated_total = Decimal("0")

            for i in items:
                item = Item.objects.get(id=i["id"], is_active=True)

                gl_error = validate_item_gl_or_message(item)
                if gl_error:
                    transaction.set_rollback(True)
                    return JsonResponse({"status": "error", "message": gl_error}, status=400)

                qty = to_decimal(i.get("qty"))
                price = to_decimal(i.get("price"))
                discount = to_decimal(i.get("discount") or 0)

                if qty <= 0:
                    return JsonResponse({"status": "error", "message": f"Invalid qty for item: {item.name}"}, status=400)

                if price < 0:
                    return JsonResponse({"status": "error", "message": f"Invalid price for item: {item.name}"}, status=400)

                if discount < 0:
                    return JsonResponse({"status": "error", "message": f"Invalid discount for item: {item.name}"}, status=400)

                if not item.allow_discount and discount > 0:
                    return JsonResponse({"status": "error", "message": f"Discount not allowed for item: {item.name}"}, status=400)

                allowed_discount = Decimal(str(item.max_discount_value or 0)) * qty
                if discount > allowed_discount:
                    return JsonResponse({
                        "status": "error",
                        "message": f"Discount exceeded for item: {item.name}. Max allowed for {qty} qty is Rs. {allowed_discount}"
                    }, status=400)

                gross_amount = qty * price
                net_amount = gross_amount - discount

                if net_amount < 0:
                    return JsonResponse({"status": "error", "message": f"Net amount cannot be negative for item: {item.name}"}, status=400)

                if not item.is_service:
                    current_stock = Decimal(str(item.stock or 0))
                    if current_stock <= 0:
                        return JsonResponse({"status": "error", "message": f"{item.name} is out of stock."}, status=400)

                    if qty > current_stock:
                        return JsonResponse({
                            "status": "error",
                            "message": f"Not enough stock for {item.name}. Available stock: {current_stock}"
                        }, status=400)

                SaleItem.objects.create(
                    sale=sale,
                    item=item,
                    qty=qty,
                    price=price,
                    discount=discount,
                    amount=gross_amount,
                    net_amount=net_amount,
                )

                calculated_total += net_amount

                if not item.is_service:
                    item.stock = current_stock - qty
                    item.updated_by = request.user
                    item.save()

                    StockTransaction.objects.create(
                        item=item,
                        transaction_type="project_issue" if sale_type == "project_issue" else "sale",
                        qty=qty,
                    )

            final_total = calculated_total
            final_grand_total = final_total - extra_discount

            if final_grand_total < 0:
                transaction.set_rollback(True)
                return JsonResponse({"status": "error", "message": "Grand total cannot be negative."}, status=400)

            if payment_method == "credit" and customer:
                current_outstanding = get_customer_outstanding(customer)
                customer_credit_limit = Decimal(str(customer.credit_limit or 0))

                if (current_outstanding + final_grand_total) > customer_credit_limit:
                    transaction.set_rollback(True)
                    return JsonResponse({
                        "status": "error",
                        "message": f"Credit limit exceeded for {customer.name}. Limit: Rs. {customer_credit_limit:.2f}, Outstanding: Rs. {current_outstanding:.2f}"
                    }, status=400)

            sale.total = final_total
            sale.grand_total = final_grand_total

            if payment_method == "cash":
                sale.received_amount = received_amount
                sale.balance = received_amount - final_grand_total
            elif payment_method == "credit":
                sale.balance = final_grand_total
            else:
                sale.balance = Decimal("0")

            sale.save()

            return JsonResponse({
                "status": "success",
                "sale_id": sale.id,
                "invoice_no": sale.invoice_no,
                "sale_type": sale.sale_type,
                "approval_status": sale.approval_status,
            })

    except Item.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Selected item not found."}, status=404)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)    
@user_passes_test(can_use_pos)
def invoice_page(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    return render(request, "pos/invoice.html", {"sale": sale})


# =========================
# CREDIT RECOVERY
# =========================
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
            item.stock = Decimal(str(item.stock or 0)) + qty
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
    context = build_item_context(request.user)

    if request.method == "POST":
        purchase_date = request.POST.get("purchase_date") or None
        retail_gl_account_id = request.POST.get("retail_gl_account") or None
        cost_gl_account_id = request.POST.get("cost_gl_account") or None
        is_service = request.POST.get("is_service") == "on"

        if not retail_gl_account_id:
            messages.error(request, "Retail GL Account is required.")
            return render(request, "pos/add_item.html", context)

        if not is_service and not cost_gl_account_id:
            messages.error(request, "Cost GL Account is required for non-service items.")
            return render(request, "pos/add_item.html", context)

        Item.objects.create(
            item_code=request.POST.get("item_code"),
            name=request.POST.get("name"),
            category_id=request.POST.get("category") or None,
            supplier_id=request.POST.get("supplier") or None,
            unit=request.POST.get("unit") or "pcs",
            cost_price=request.POST.get("cost_price") or 0,
            selling_price=request.POST.get("selling_price") or 0,
            stock=request.POST.get("stock") or 0,
            purchase_date=purchase_date,
            item_type=request.POST.get("item_type") or "retail",
            is_service=is_service,
            allow_discount=request.POST.get("allow_discount") == "on",
            max_discount_value=request.POST.get("max_discount_value") or 0,
            reorder_level=request.POST.get("reorder_level") or 0,
            warranty_days=request.POST.get("warranty_days") or 0,
            retail_gl_account_id=retail_gl_account_id,
            cost_gl_account_id=cost_gl_account_id,
            updated_by=request.user,
        )
        messages.success(request, "Item added successfully.")
        return redirect("item_list")

    return render(request, "pos/add_item.html", context)


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

    low_stock_items = Item.objects.filter(
        is_active=True,
        stock__lte=F("reorder_level")
    ).order_by("name")

    return render(request, "pos/item_list.html", {
        "items": items,
        "query": query,
        "low_stock_items": low_stock_items,
    })

@user_passes_test(can_manage_items)
def edit_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    context = build_item_context(request.user)
    context["item"] = item

    if request.method == "POST":
        retail_gl_account_id = request.POST.get("retail_gl_account") or None
        cost_gl_account_id = request.POST.get("cost_gl_account") or None
        is_service = request.POST.get("is_service") == "on"

        if not retail_gl_account_id:
            messages.error(request, "Retail GL Account is required.")
            return render(request, "pos/edit_item.html", context)

        if not is_service and not cost_gl_account_id:
            messages.error(request, "Cost GL Account is required for non-service items.")
            return render(request, "pos/edit_item.html", context)

        item.item_code = request.POST.get("item_code")
        item.name = request.POST.get("name")
        item.category_id = request.POST.get("category") or None
        item.supplier_id = request.POST.get("supplier") or None
        item.unit = request.POST.get("unit") or "pcs"
        item.cost_price = request.POST.get("cost_price") or 0
        item.selling_price = request.POST.get("selling_price") or 0
        item.stock = request.POST.get("stock") or 0
        item.purchase_date = request.POST.get("purchase_date") or None
        item.item_type = request.POST.get("item_type") or "retail"
        item.is_service = is_service
        item.allow_discount = request.POST.get("allow_discount") == "on"
        item.max_discount_value = request.POST.get("max_discount_value") or 0
        item.reorder_level = request.POST.get("reorder_level") or 0
        item.warranty_days = request.POST.get("warranty_days") or 0
        item.retail_gl_account_id = retail_gl_account_id
        item.cost_gl_account_id = cost_gl_account_id
        item.updated_by = request.user
        item.save()

        messages.success(request, "Item updated successfully.")
        return redirect("item_list")

    return render(request, "pos/edit_item.html", context)
    
@user_passes_test(can_manage_items)
def get_item_details(request, item_id):
    item = get_object_or_404(Item, id=item_id, is_active=True)

    return JsonResponse({
        "id": item.id,
        "item_code": item.item_code,
        "name": item.name,
        "cost_price": str(item.cost_price or 0),
        "selling_price": str(item.selling_price or 0),
        "stock": str(item.stock or 0),
        "unit": item.unit or "",
        "category": item.category.name if item.category else "",
        "supplier": item.supplier.name if item.supplier else "",
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
            sale_cost += Decimal(str(row.item.cost_price or 0)) * Decimal(str(row.qty or 0))

        sale.sale_cost = sale_cost
        sale.sale_profit = Decimal(str(sale.grand_total or 0)) - sale_cost

        total_sales += Decimal(str(sale.grand_total or 0))
        total_cost += sale_cost
        total_discount += Decimal(str(sale.discount or 0))

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
# PROJECTS
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


# =========================
# PROJECT EXPENSES
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

        context = {
            "projects": projects,
            "expense_gls": expense_gls,
        }

        if not project_id:
            messages.error(request, "Project is required.")
            return render(request, "pos/add_project_expense.html", context)

        if not description:
            messages.error(request, "Description is required.")
            return render(request, "pos/add_project_expense.html", context)

        if not gl_account_id:
            messages.error(request, "GL Account is required.")
            return render(request, "pos/add_project_expense.html", context)

        if amount <= 0:
            messages.error(request, "Amount must be greater than 0.")
            return render(request, "pos/add_project_expense.html", context)

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

        messages.success(request, f"Saved successfully. Expense No: {expense.expense_no}")
        return redirect("project_expense_list")

    return render(request, "pos/add_project_expense.html", {
        "projects": projects,
        "expense_gls": expense_gls,
    })

@user_passes_test(is_owner)
def edit_project_expense(request, expense_id):
    expense = get_object_or_404(ProjectExpense, id=expense_id)
    projects = Project.objects.filter(is_active=True).order_by("-id")
    expense_gls = GLMaster.objects.filter(gl_type="expense", is_active=True).order_by("gl_code")
    items = Item.objects.filter(is_active=True).order_by("name")

    context = {
        "expense": expense,
        "projects": projects,
        "expense_gls": expense_gls,
        "items": items,
    }

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
            return render(request, "pos/edit_project_expense.html", context)

        if not expense.description:
            messages.error(request, "Description is required.")
            return render(request, "pos/edit_project_expense.html", context)

        if not expense.gl_account_id:
            messages.error(request, "GL Account is required.")
            return render(request, "pos/edit_project_expense.html", context)

        if expense.amount <= 0:
            messages.error(request, "Amount must be greater than 0.")
            return render(request, "pos/edit_project_expense.html", context)

        expense.save()
        messages.success(request, "Project expense updated successfully.")
        return redirect("project_expense_list")

    return render(request, "pos/edit_project_expense.html", context)


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
    petty_cash_qs = ProjectPettyCash.objects.filter(is_active=True).select_related(
        "employee", "user", "created_by"
    ).order_by("-issue_date", "-id")

    petty_cashes = []

    for row in petty_cash_qs:
        approved_limit = Decimal(str(row.employee.petty_cash_limit or 0)) if row.employee else Decimal("0")
        total_issued = Decimal(str(row.amount_issued or 0))
        total_spent = Decimal(str(row.total_spent or 0))
        total_balance = Decimal(str(row.balance or 0))

        reimbursement_required = approved_limit - total_balance
        if reimbursement_required < 0:
            reimbursement_required = Decimal("0")

        petty_cashes.append({
            "obj": row,
            "approved_limit": approved_limit,
            "total_issued": total_issued,
            "total_spent": total_spent,
            "total_balance": total_balance,
            "reimbursement_required": reimbursement_required,
        })

    return render(request, "pos/petty_cash_list.html", {
        "petty_cashes": petty_cashes,
        "is_owner": is_owner(request.user),
    })

@user_passes_test(can_use_project)
def petty_cash_ledger_report(request):
    employee_id = request.GET.get("employee") or ""
    petty_cash_id = request.GET.get("petty_cash") or ""
    date_from = request.GET.get("date_from") or ""
    date_to = request.GET.get("date_to") or ""
    status_filter = request.GET.get("status") or "all"

    employees = Employee.objects.filter(is_active=True).order_by("emp_no")
    petty_cash_records = ProjectPettyCash.objects.filter(is_active=True).select_related("employee").order_by("-issue_date", "-id")

    ledger_rows = []

    petty_cash_qs = ProjectPettyCash.objects.filter(is_active=True).select_related("employee").order_by("issue_date", "id")

    if employee_id:
        petty_cash_qs = petty_cash_qs.filter(employee_id=employee_id)

    if petty_cash_id:
        petty_cash_qs = petty_cash_qs.filter(id=petty_cash_id)

    if date_from:
        petty_cash_qs = petty_cash_qs.filter(issue_date__gte=date_from)

    if date_to:
        petty_cash_qs = petty_cash_qs.filter(issue_date__lte=date_to)

    for pc in petty_cash_qs:
        expenses = pc.expenses.filter(is_active=True).select_related("project", "gl_account").order_by("expense_date", "id")

        if status_filter in ["pending", "approved", "rejected"]:
            expenses = expenses.filter(approval_status=status_filter)

        if date_from:
            expenses = expenses.filter(expense_date__gte=date_from)

        if date_to:
            expenses = expenses.filter(expense_date__lte=date_to)

        running_balance = Decimal("0")

        # reimbursement / issue row
        running_balance += Decimal(str(pc.amount_issued or 0))
        ledger_rows.append({
            "row_type": "issue",
            "date": pc.issue_date,
            "ref_no": pc.petty_cash_no,
            "petty_cash_no": pc.petty_cash_no,
            "employee": pc.employee,
            "project": None,
            "gl_name": "",
            "description": pc.note or "Petty cash issued",
            "bill_no": "",
            "reimbursement_amount": Decimal(str(pc.amount_issued or 0)),
            "expense_amount": Decimal("0"),
            "balance": running_balance,
            "status": "issued",
        })

        for exp in expenses:
            running_balance -= Decimal(str(exp.amount or 0))
            ledger_rows.append({
                "row_type": "expense",
                "date": exp.expense_date,
                "ref_no": exp.expense_no,
                "petty_cash_no": pc.petty_cash_no,
                "employee": pc.employee,
                "project": exp.project,
                "gl_name": exp.gl_account.gl_name if exp.gl_account else "",
                "description": exp.description or "",
                "bill_no": exp.bill_no or "",
                "reimbursement_amount": Decimal("0"),
                "expense_amount": Decimal(str(exp.amount or 0)),
                "balance": running_balance,
                "status": exp.approval_status,
            })

    total_reimbursement = sum((row["reimbursement_amount"] for row in ledger_rows), Decimal("0"))
    total_expense = sum((row["expense_amount"] for row in ledger_rows), Decimal("0"))
    closing_balance = total_reimbursement - total_expense

    return render(request, "pos/petty_cash_ledger_report.html", {
        "ledger_rows": ledger_rows,
        "employees": employees,
        "petty_cash_records": petty_cash_records,
        "selected_employee": employee_id,
        "selected_petty_cash": petty_cash_id,
        "date_from": date_from,
        "date_to": date_to,
        "status_filter": status_filter,
        "total_reimbursement": total_reimbursement,
        "total_expense": total_expense,
        "closing_balance": closing_balance,
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
        "project", "gl_account", "created_by", "approved_by"
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

        #if amount > petty_cash.balance:
         #   messages.error(request, "Expense exceeds petty cash balance.")
         #   return render(request, "pos/add_petty_cash_expense.html", {
           #     "petty_cash": petty_cash,
            #    "projects": projects,
             #   "expense_gls": expense_gls,
           # })

        approval_status = "approved" if is_owner(request.user) else "pending"

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
            approval_status=approval_status,
            approved_by=request.user if approval_status == "approved" else None,
            approved_at=timezone.now() if approval_status == "approved" else None,
            created_by=request.user,
        )

        if approval_status == "approved":
            messages.success(request, f"Saved and approved successfully. Expense No: {expense.expense_no}")
        else:
            messages.success(request, f"Saved successfully and waiting for owner approval. Expense No: {expense.expense_no}")

        return redirect("petty_cash_detail", petty_cash_id=petty_cash.id)

    return render(request, "pos/add_petty_cash_expense.html", {
        "petty_cash": petty_cash,
        "projects": projects,
        "expense_gls": expense_gls,
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
# PETTY CASH APPROVALS
# =========================
@user_passes_test(is_owner)
def petty_cash_expense_approvals(request):
    status_filter = request.GET.get("status", "pending").strip()

    expenses = ProjectPettyCashExpense.objects.filter(
        is_active=True
    ).select_related(
        "petty_cash", "project", "gl_account", "created_by", "approved_by"
    ).order_by("-expense_date", "-id")

    if status_filter in ["pending", "approved", "rejected"]:
        expenses = expenses.filter(approval_status=status_filter)

    return render(request, "pos/petty_cash_expense_approvals.html", {
        "expenses": expenses,
        "status_filter": status_filter,
    })


@user_passes_test(is_owner)
def approve_petty_cash_expense(request, expense_id):
    expense = get_object_or_404(ProjectPettyCashExpense, id=expense_id, is_active=True)

    if expense.approval_status == "approved":
        messages.warning(request, "This petty cash expense is already approved.")
        return redirect("petty_cash_expense_approvals")

    expense.approval_status = "approved"
    expense.approved_by = request.user
    expense.approved_at = timezone.now()
    expense.save()

    messages.success(request, f"Expense {expense.expense_no} approved successfully.")
    return redirect("petty_cash_expense_approvals")


@user_passes_test(is_owner)
def reject_petty_cash_expense(request, expense_id):
    expense = get_object_or_404(ProjectPettyCashExpense, id=expense_id, is_active=True)

    if expense.approval_status == "approved":
        messages.error(request, "Approved expense cannot be rejected.")
        return redirect("petty_cash_expense_approvals")

    expense.approval_status = "rejected"
    expense.approved_by = request.user
    expense.approved_at = timezone.now()
    expense.approval_note = "Rejected by owner"
    expense.save()

    messages.success(request, f"Expense {expense.expense_no} rejected.")
    return redirect("petty_cash_expense_approvals")


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


@user_passes_test(can_use_pos)
def add_project_income(request):
    projects = Project.objects.filter(is_active=True).order_by("-id")
    gl_list = GLMaster.objects.filter(is_active=True).order_by("gl_code")

    if request.method == "POST":
        project_id = request.POST.get("project") or None
        income_date = request.POST.get("income_date") or timezone.now().date()
        description = (request.POST.get("description") or "").strip() or None
        amount = Decimal(request.POST.get("amount") or 0)
        gl_account_id = request.POST.get("gl_account") or None

        if not project_id:
            messages.error(request, "Project is required.")
        elif not gl_account_id:
            messages.error(request, "GL Account is required.")
        elif amount <= 0:
            messages.error(request, "Amount must be greater than 0.")
        else:
            ProjectIncome.objects.create(
                project_id=project_id,
                income_date=income_date,
                description=description,
                amount=amount,
                gl_account_id=gl_account_id,
                created_by=request.user,
            )
            messages.success(request, "Project income added successfully.")
            return redirect("project_income_list")

    return render(request, "project/add_project_income.html", {
        "projects": projects,
        "gl_list": gl_list,
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
            is_active=True,
            approval_status="approved"
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
    invoices = ProjectInvoice.objects.filter(is_active=True).select_related(
        "project", "created_by"
    ).order_by("-invoice_date", "-id")

    project_id = request.GET.get("project")
    if project_id:
        invoices = invoices.filter(project_id=project_id)

    projects = Project.objects.filter(is_active=True).order_by("-id")

    return render(request, "pos/project_invoice_list.html", {
        "invoices": invoices,
        "projects": projects,
        "selected_project": project_id,
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
        id=invoice_id,
        is_active=True
    )

    invoice_items = invoice.items.all()
    payments = invoice.payments.filter(is_active=True).select_related("created_by").order_by("-payment_date", "-id")

    return render(request, "pos/project_invoice_detail.html", {
        "invoice": invoice,
        "invoice_items": invoice_items,
        "payments": payments,
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


# =========================
# PROJECT ISSUE APPROVALS
# =========================
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


# =========================
# AMOUNT IN WORDS / PRINT RECEIPT
# =========================
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

@user_passes_test(can_add_expenses)
def add_petty_cash_expense_entry(request):
    employees = Employee.objects.filter(is_active=True).order_by("emp_no")
    projects = Project.objects.filter(is_active=True).order_by("-id")
    expense_gls = GLMaster.objects.filter(gl_type="expense", is_active=True).order_by("gl_code")

    selected_employee = request.GET.get("employee") or request.POST.get("employee") or None
    petty_cash = None
    summary = None

    if selected_employee:
        petty_cash = ProjectPettyCash.objects.filter(
            employee_id=selected_employee,
            is_active=True
        ).order_by("-issue_date", "-id").first()

        employee = Employee.objects.filter(id=selected_employee, is_active=True).first()
        if employee:
            approved_limit = Decimal(str(employee.petty_cash_limit or 0))
            total_issued = employee.petty_cash_records.filter(is_active=True).aggregate(
                total=Sum("amount_issued")
            )["total"] or Decimal("0")

            total_spent = ProjectPettyCashExpense.objects.filter(
                petty_cash__employee=employee,
                petty_cash__is_active=True,
                is_active=True,
                approval_status__in=["pending", "approved"]
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

            total_balance = Decimal(str(total_issued)) - Decimal(str(total_spent))
            reimbursement_required = approved_limit - total_balance
            if reimbursement_required < 0:
                reimbursement_required = Decimal("0")

            summary = {
                "approved_limit": approved_limit,
                "total_issued": Decimal(str(total_issued)),
                "total_spent": Decimal(str(total_spent)),
                "total_balance": total_balance,
                "reimbursement_required": reimbursement_required,
            }

    if request.method == "POST":
        if not selected_employee:
            messages.error(request, "Employee is required.")
        elif not petty_cash:
            messages.error(request, "No active petty cash found for selected employee.")
        else:
            project_id = request.POST.get("project") or None
            expense_date = request.POST.get("expense_date") or timezone.now().date()
            description = (request.POST.get("description") or "").strip()
            gl_account_id = request.POST.get("gl_account") or None
            bill_no = (request.POST.get("bill_no") or "").strip() or None
            bill_date = request.POST.get("bill_date") or None
            amount = to_decimal(request.POST.get("amount"))
            note = (request.POST.get("note") or "").strip() or None

            if not project_id:
                messages.error(request, "Project is required.")
            elif not description:
                messages.error(request, "Description is required.")
            elif not gl_account_id:
                messages.error(request, "GL Account is required.")
            elif amount <= 0:
                messages.error(request, "Amount must be greater than 0.")
            else:
                approval_status = "approved" if is_owner(request.user) else "pending"

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
                    approval_status=approval_status,
                    approved_by=request.user if approval_status == "approved" else None,
                    approved_at=timezone.now() if approval_status == "approved" else None,
                    created_by=request.user,
                )

                if approval_status == "approved":
                    messages.success(request, f"Saved and approved successfully. Expense No: {expense.expense_no}")
                else:
                    messages.success(request, f"Saved successfully and waiting for owner approval. Expense No: {expense.expense_no}")

                return redirect("petty_cash_expense_list")

    return render(request, "pos/add_petty_cash_expense_entry.html", {
        "employees": employees,
        "projects": projects,
        "expense_gls": expense_gls,
        "selected_employee": selected_employee,
        "petty_cash": petty_cash,
        "summary": summary,
    })

@user_passes_test(can_use_project)
def petty_cash_expense_list(request):
    employee_id = request.GET.get("employee")
    project_id = request.GET.get("project")
    status_filter = request.GET.get("status", "").strip()

    expenses = ProjectPettyCashExpense.objects.filter(
        is_active=True
    ).select_related(
        "petty_cash",
        "petty_cash__employee",
        "project",
        "gl_account",
        "created_by",
        "approved_by"
    ).order_by("-expense_date", "-id")

    if employee_id:
        expenses = expenses.filter(petty_cash__employee_id=employee_id)

    if project_id:
        expenses = expenses.filter(project_id=project_id)

    if status_filter in ["pending", "approved", "rejected"]:
        expenses = expenses.filter(approval_status=status_filter)

    employees = Employee.objects.filter(is_active=True).order_by("emp_no")
    projects = Project.objects.filter(is_active=True).order_by("-id")
    total_amount = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    return render(request, "pos/petty_cash_expense_list.html", {
        "expenses": expenses,
        "employees": employees,
        "projects": projects,
        "selected_employee": employee_id,
        "selected_project": project_id,
        "status_filter": status_filter,
        "total_amount": total_amount,
        "is_owner": is_owner(request.user),
    })
@user_passes_test(can_use_pos)
def customer_list(request):
    query = request.GET.get("q", "").strip()

    customers = Customer.objects.filter(is_active=True).select_related(
        "receivable_gl_account"
    ).order_by("name")

    if query:
        customers = customers.filter(
            Q(name__icontains=query) |
            Q(customer_code__icontains=query) |
            Q(phone__icontains=query) |
            Q(email__icontains=query)
        )

    return render(request, "pos/customer_list.html", {
        "customers": customers,
        "query": query,
    })


@user_passes_test(can_use_pos)
def add_customer(request):
    gl_list = GLMaster.objects.filter(is_active=True).order_by("gl_code")
    next_customer_code = generate_customer_code()

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        phone = (request.POST.get("phone") or "").strip()
        email = (request.POST.get("email") or "").strip()
        address = (request.POST.get("address") or "").strip()
        credit_limit = to_decimal(request.POST.get("credit_limit") or 0)
        receivable_gl_account_id = request.POST.get("receivable_gl_account") or None

        if not name:
            messages.error(request, "Customer name is required.")
            return render(request, "pos/add_customer.html", {
                "gl_list": gl_list,
                "next_customer_code": next_customer_code,
            })

        Customer.objects.create(
            customer_code=next_customer_code,
            name=name,
            phone=phone or None,
            email=email or None,
            address=address or None,
            credit_limit=credit_limit,
            receivable_gl_account_id=receivable_gl_account_id,
            is_active=True,
        )

        messages.success(request, "Customer added successfully.")
        return redirect("customer_list")

    return render(request, "pos/add_customer.html", {
        "gl_list": gl_list,
        "next_customer_code": next_customer_code,
    })


@user_passes_test(can_use_pos)
def edit_customer(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    gl_list = GLMaster.objects.filter(is_active=True).order_by("gl_code")

    if request.method == "POST":
        customer.name = (request.POST.get("name") or "").strip()
        customer.phone = (request.POST.get("phone") or "").strip() or None
        customer.email = (request.POST.get("email") or "").strip() or None
        customer.address = (request.POST.get("address") or "").strip() or None
        customer.credit_limit = to_decimal(request.POST.get("credit_limit") or 0)
        customer.receivable_gl_account_id = request.POST.get("receivable_gl_account") or None

        if not customer.name:
            messages.error(request, "Customer name is required.")
            return render(request, "pos/edit_customer.html", {
                "customer": customer,
                "gl_list": gl_list,
            })

        customer.save()
        messages.success(request, "Customer updated successfully.")
        return redirect("customer_list")

    return render(request, "pos/edit_customer.html", {
        "customer": customer,
        "gl_list": gl_list,
    })

@user_passes_test(can_manage_items)
def supplier_list(request):
    query = request.GET.get("q", "").strip()

    suppliers = Supplier.objects.filter(is_active=True).order_by("name")

    if query:
        suppliers = suppliers.filter(
            Q(name__icontains=query) |
            Q(phone_1__icontains=query) |
            Q(phone_2__icontains=query) |
            Q(phone_3__icontains=query) |
            Q(email__icontains=query) |
            Q(contact_person__icontains=query) |
            Q(bank_name__icontains=query) |
            Q(account_number__icontains=query)
        )

    return render(request, "pos/supplier_list.html", {
        "suppliers": suppliers,
        "query": query,
    })

@user_passes_test(can_manage_items)
def add_supplier(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        address = (request.POST.get("address") or "").strip()
        phone_1 = (request.POST.get("phone_1") or "").strip()
        phone_2 = (request.POST.get("phone_2") or "").strip()
        phone_3 = (request.POST.get("phone_3") or "").strip()
        email = (request.POST.get("email") or "").strip()
        contact_person = (request.POST.get("contact_person") or "").strip()

        bank_name = (request.POST.get("bank_name") or "").strip()
        bank_branch = (request.POST.get("bank_branch") or "").strip()
        account_name = (request.POST.get("account_name") or "").strip()
        account_number = (request.POST.get("account_number") or "").strip()

        if not name:
            messages.error(request, "Supplier name is required.")
            return render(request, "pos/add_supplier.html")

        if Supplier.objects.filter(name__iexact=name).exists():
            messages.error(request, "Supplier already exists.")
            return render(request, "pos/add_supplier.html")

        Supplier.objects.create(
            name=name,
            address=address or None,
            phone_1=phone_1 or None,
            phone_2=phone_2 or None,
            phone_3=phone_3 or None,
            email=email or None,
            contact_person=contact_person or None,
            bank_name=bank_name or None,
            bank_branch=bank_branch or None,
            account_name=account_name or None,
            account_number=account_number or None,
            is_active=True,
        )

        messages.success(request, "Supplier added successfully.")
        return redirect("supplier_list")

    return render(request, "pos/add_supplier.html")

@user_passes_test(can_manage_items)
def edit_supplier(request, supplier_id):
    supplier = get_object_or_404(Supplier, id=supplier_id)

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        address = (request.POST.get("address") or "").strip()
        phone_1 = (request.POST.get("phone_1") or "").strip()
        phone_2 = (request.POST.get("phone_2") or "").strip()
        phone_3 = (request.POST.get("phone_3") or "").strip()
        email = (request.POST.get("email") or "").strip()
        contact_person = (request.POST.get("contact_person") or "").strip()

        bank_name = (request.POST.get("bank_name") or "").strip()
        bank_branch = (request.POST.get("bank_branch") or "").strip()
        account_name = (request.POST.get("account_name") or "").strip()
        account_number = (request.POST.get("account_number") or "").strip()

        is_active = request.POST.get("is_active") == "on"

        if not name:
            messages.error(request, "Supplier name is required.")
            return render(request, "pos/edit_supplier.html", {"supplier": supplier})

        if Supplier.objects.filter(name__iexact=name).exclude(id=supplier.id).exists():
            messages.error(request, "Another supplier with this name already exists.")
            return render(request, "pos/edit_supplier.html", {"supplier": supplier})

        supplier.name = name
        supplier.address = address or None
        supplier.phone_1 = phone_1 or None
        supplier.phone_2 = phone_2 or None
        supplier.phone_3 = phone_3 or None
        supplier.email = email or None
        supplier.contact_person = contact_person or None
        supplier.bank_name = bank_name or None
        supplier.bank_branch = bank_branch or None
        supplier.account_name = account_name or None
        supplier.account_number = account_number or None
        supplier.is_active = is_active
        supplier.save()

        messages.success(request, "Supplier updated successfully.")
        return redirect("supplier_list")

    return render(request, "pos/edit_supplier.html", {"supplier": supplier})
@user_passes_test(can_use_project)
def supplier_advance_list(request):
    query = request.GET.get("q", "").strip()

    advances = SupplierAdvance.objects.filter(is_active=True).select_related(
        "supplier", "project", "paid_from_gl", "advance_gl", "created_by"
    ).order_by("-advance_date", "-id")

    if query:
        advances = advances.filter(
            Q(advance_no__icontains=query) |
            Q(supplier__name__icontains=query) |
            Q(project__project_id__icontains=query) |
            Q(project__project_name__icontains=query)
        )

    return render(request, "pos/supplier_advance_list.html", {
        "advances": advances,
        "query": query,
        "is_owner": is_owner(request.user),
    })
@user_passes_test(can_use_project)
def add_supplier_advance(request):
    suppliers = Supplier.objects.filter(is_active=True).order_by("name")
    projects = Project.objects.filter(is_active=True).order_by("-id")
    gl_list = GLMaster.objects.filter(is_active=True).order_by("gl_code")
    purchase_orders = PurchaseOrder.objects.select_related("supplier", "project").order_by("-po_date", "-id")
    next_advance_no = generate_supplier_advance_no()

    context = {
        "suppliers": suppliers,
        "projects": projects,
        "gl_list": gl_list,
        "purchase_orders": purchase_orders,
        "next_advance_no": next_advance_no,
    }

    if request.method == "POST":
        po_id = request.POST.get("po") or None
        supplier_id = request.POST.get("supplier") or None
        project_id = request.POST.get("project") or None
        advance_date = request.POST.get("advance_date") or timezone.localdate()
        amount = to_decimal(request.POST.get("amount") or 0)
        payment_method = request.POST.get("payment_method") or "cash"
        paid_from_gl_id = request.POST.get("paid_from_gl") or None
        advance_gl_id = request.POST.get("advance_gl") or None
        note = (request.POST.get("note") or "").strip()

        if po_id:
            po = PurchaseOrder.objects.filter(id=po_id).first()
            if po:
                supplier_id = po.supplier_id
                project_id = po.project_id

        if not supplier_id:
            messages.error(request, "Supplier is required.")
            return render(request, "pos/add_supplier_advance.html", context)

        if amount <= 0:
            messages.error(request, "Amount must be greater than 0.")
            return render(request, "pos/add_supplier_advance.html", context)

        if not paid_from_gl_id:
            messages.error(request, "Paid From GL is required.")
            return render(request, "pos/add_supplier_advance.html", context)

        if not advance_gl_id:
            messages.error(request, "Advance GL is required.")
            return render(request, "pos/add_supplier_advance.html", context)

        SupplierAdvance.objects.create(
            advance_no=next_advance_no,
            po_id=po_id,
            supplier_id=supplier_id,
            project_id=project_id,
            advance_date=advance_date,
            amount=amount,
            payment_method=payment_method,
            paid_from_gl_id=paid_from_gl_id,
            advance_gl_id=advance_gl_id,
            note=note,
            status="approved",
            created_by=request.user,
        )

        messages.success(request, "Supplier advance saved successfully.")
        return redirect("supplier_advance_list")

    return render(request, "pos/add_supplier_advance.html", context)

@user_passes_test(can_use_project)
def add_supplier_settlement_from_advance(request, advance_id):
    advance = get_object_or_404(
        SupplierAdvance.objects.select_related("supplier", "project"),
        id=advance_id,
        is_active=True
    )

    expense_gls = GLMaster.objects.filter(gl_type="expense", is_active=True).order_by("gl_code")
    next_settlement_no = generate_supplier_settlement_no()

    context = {
        "advance": advance,
        "expense_gls": expense_gls,
        "next_settlement_no": next_settlement_no,
    }

    if request.method == "POST":
        settlement_date = request.POST.get("settlement_date") or timezone.localdate()
        description = (request.POST.get("description") or "").strip()
        actual_amount = to_decimal(request.POST.get("actual_amount") or 0)
        expense_gl_id = request.POST.get("expense_gl") or None
        note = (request.POST.get("note") or "").strip()

        if advance.balance_amount <= 0:
            messages.error(request, "This advance has no available balance.")
            return redirect("supplier_advance_list")

        if not description:
            messages.error(request, "Description is required.")
            return render(request, "pos/add_supplier_settlement.html", context)

        if actual_amount <= 0:
            messages.error(request, "Actual amount must be greater than 0.")
            return render(request, "pos/add_supplier_settlement.html", context)

        if not expense_gl_id:
            messages.error(request, "Expense GL is required.")
            return render(request, "pos/add_supplier_settlement.html", context)

        available_balance = Decimal(str(advance.balance_amount or 0))
        advance_applied = available_balance if actual_amount >= available_balance else actual_amount
        balance_due = actual_amount - advance_applied if actual_amount > advance_applied else Decimal("0")
        excess_advance = available_balance - actual_amount if available_balance > actual_amount else Decimal("0")

        SupplierSettlement.objects.create(
            settlement_no=next_settlement_no,
            advance=advance,
            supplier=advance.supplier,
            project=advance.project,
            settlement_date=settlement_date,
            description=description,
            actual_amount=actual_amount,
            advance_applied=advance_applied,
            balance_due=balance_due,
            excess_advance=excess_advance,
            expense_gl_id=expense_gl_id,
            approval_status="pending",
            note=note,
            created_by=request.user,
        )

        messages.success(request, "Settlement submitted for approval.")
        return redirect("supplier_settlement_list")

    return render(request, "pos/add_supplier_settlement.html", context)


@user_passes_test(is_owner)
def approve_supplier_settlement(request, settlement_id):
    settlement = get_object_or_404(
        SupplierSettlement.objects.select_related("advance", "project", "expense_gl", "supplier"),
        id=settlement_id
    )

    if settlement.approval_status == "approved":
        messages.warning(request, "Settlement already approved.")
        return redirect("supplier_settlement_list")

    with transaction.atomic():
        linked_project_expense = None

        if settlement.project:
            linked_project_expense = ProjectExpense.objects.create(
                expense_no=generate_project_expense_no(),
                project=settlement.project,
                expense_type="service",
                expense_date=settlement.settlement_date,
                description=f"Supplier Settlement - {settlement.supplier.name} - {settlement.description}",
                qty=1,
                unit_price=settlement.actual_amount,
                amount=settlement.actual_amount,
                gl_account=settlement.expense_gl,
                created_by=request.user,
            )

        settlement.approval_status = "approved"
        settlement.approved_by = request.user
        settlement.approved_at = timezone.now()
        settlement.linked_project_expense = linked_project_expense
        settlement.save()

        if settlement.advance and settlement.advance.balance_amount <= 0:
            settlement.advance.status = "closed"
            settlement.advance.save()

    messages.success(request, "Settlement approved and posted to Project Expenses.")
    return redirect("supplier_settlement_list")

@user_passes_test(is_owner)
def reject_supplier_settlement(request, settlement_id):
    settlement = get_object_or_404(SupplierSettlement, id=settlement_id)

    if settlement.approval_status == "approved":
        messages.error(request, "Approved settlement cannot be rejected.")
        return redirect("supplier_settlement_list")

    note = (request.POST.get("approval_note") or "").strip() if request.method == "POST" else ""

    settlement.approval_status = "rejected"
    settlement.approval_note = note
    settlement.approved_by = request.user
    settlement.approved_at = timezone.now()
    settlement.save()

    messages.success(request, "Settlement rejected.")
    return redirect("supplier_settlement_list")

@user_passes_test(can_use_project)
def purchase_order_list(request):
    query = request.GET.get("q", "").strip()

    orders = PurchaseOrder.objects.select_related(
        "supplier", "project", "created_by"
    ).prefetch_related("items").order_by("-po_date", "-id")

    if query:
        orders = orders.filter(
            Q(po_no__icontains=query) |
            Q(supplier__name__icontains=query) |
            Q(project__project_id__icontains=query) |
            Q(project__project_name__icontains=query) |
            Q(buyer_company_name__icontains=query)
        )

    return render(request, "pos/purchase_order_list.html", {
        "orders": orders,
        "query": query,
        "is_owner": is_owner(request.user),
    })

@user_passes_test(can_use_project)
def add_purchase_order(request):
    suppliers = Supplier.objects.filter(is_active=True).order_by("name")
    projects = Project.objects.filter(is_active=True).order_by("-id")
    next_po_no = generate_purchase_order_no()

    context = {
        "suppliers": suppliers,
        "projects": projects,
        "next_po_no": next_po_no,
    }

    if request.method == "POST":
        po_date = request.POST.get("po_date") or timezone.localdate()
        delivery_date_required = request.POST.get("delivery_date_required") or None

        supplier_id = request.POST.get("supplier") or None
        project_id = request.POST.get("project") or None

        buyer_company_name = (request.POST.get("buyer_company_name") or "").strip()
        buyer_address = (request.POST.get("buyer_address") or "").strip()
        buyer_contact_person = (request.POST.get("buyer_contact_person") or "").strip()
        buyer_phone = (request.POST.get("buyer_phone") or "").strip()
        buyer_email = (request.POST.get("buyer_email") or "").strip()

        supplier_address = (request.POST.get("supplier_address") or "").strip()
        supplier_contact_details = (request.POST.get("supplier_contact_details") or "").strip()

        payment_method = request.POST.get("payment_method") or "bank"
        payment_period = (request.POST.get("payment_period") or "").strip()

        delivery_location = (request.POST.get("delivery_location") or "").strip()
        delivery_method = (request.POST.get("delivery_method") or "").strip()
        special_instructions = (request.POST.get("special_instructions") or "").strip()

        terms_and_conditions = (request.POST.get("terms_and_conditions") or "").strip()
        warranty_details = (request.POST.get("warranty_details") or "").strip()
        return_policy = (request.POST.get("return_policy") or "").strip()
        penalties_conditions = (request.POST.get("penalties_conditions") or "").strip()

        authorized_person_name = (request.POST.get("authorized_person_name") or "").strip()
        signature_text = (request.POST.get("signature_text") or "").strip()
        status = request.POST.get("status") or "draft"
        note = (request.POST.get("note") or "").strip()

        descriptions = request.POST.getlist("item_description[]")
        quantities = request.POST.getlist("item_qty[]")
        unit_prices = request.POST.getlist("item_price[]")

        if not supplier_id:
            messages.error(request, "Supplier is required.")
            return render(request, "pos/add_purchase_order.html", context)

        cleaned_rows = []
        row_count = max(len(descriptions), len(quantities), len(unit_prices))

        for i in range(row_count):
            desc = (descriptions[i] if i < len(descriptions) else "").strip()
            qty = to_decimal(quantities[i] if i < len(quantities) else 0)
            price = to_decimal(unit_prices[i] if i < len(unit_prices) else 0)

            if not desc and qty <= 0 and price <= 0:
                continue

            if not desc:
                messages.error(request, f"Item description is required for row {i+1}.")
                return render(request, "pos/add_purchase_order.html", context)

            if qty <= 0:
                messages.error(request, f"Qty must be greater than 0 for row {i+1}.")
                return render(request, "pos/add_purchase_order.html", context)

            if price < 0:
                messages.error(request, f"Price cannot be negative for row {i+1}.")
                return render(request, "pos/add_purchase_order.html", context)

            cleaned_rows.append({
                "description": desc,
                "quantity": qty,
                "unit_price": price,
            })

        if not cleaned_rows:
            messages.error(request, "At least one PO item is required.")
            return render(request, "pos/add_purchase_order.html", context)

        with transaction.atomic():
            po = PurchaseOrder.objects.create(
                po_no=next_po_no,
                po_date=po_date,
                delivery_date_required=delivery_date_required,
                supplier_id=supplier_id,
                project_id=project_id,
                buyer_company_name=buyer_company_name or None,
                buyer_address=buyer_address or None,
                buyer_contact_person=buyer_contact_person or None,
                buyer_phone=buyer_phone or None,
                buyer_email=buyer_email or None,
                supplier_address=supplier_address or None,
                supplier_contact_details=supplier_contact_details or None,
                payment_method=payment_method,
                payment_period=payment_period or None,
                delivery_location=delivery_location or None,
                delivery_method=delivery_method or None,
                special_instructions=special_instructions or None,
                terms_and_conditions=terms_and_conditions or None,
                warranty_details=warranty_details or None,
                return_policy=return_policy or None,
                penalties_conditions=penalties_conditions or None,
                authorized_person_name=authorized_person_name or None,
                signature_text=signature_text or None,
                status=status,
                note=note or None,
                created_by=request.user,
            )

            for row in cleaned_rows:
                PurchaseOrderItem.objects.create(
                    purchase_order=po,
                    description=row["description"],
                    quantity=row["quantity"],
                    unit_price=row["unit_price"],
                )

        messages.success(request, "Purchase Order created successfully.")
        return redirect("purchase_order_list")

    return render(request, "pos/add_purchase_order.html", context)

@user_passes_test(can_use_project)
def edit_purchase_order(request, po_id):
    order = get_object_or_404(PurchaseOrder.objects.prefetch_related("items"), id=po_id)
    suppliers = Supplier.objects.filter(is_active=True).order_by("name")
    projects = Project.objects.filter(is_active=True).order_by("-id")

    context = {
        "order": order,
        "suppliers": suppliers,
        "projects": projects,
    }

    if request.method == "POST":
        order.po_date = request.POST.get("po_date") or order.po_date
        order.delivery_date_required = request.POST.get("delivery_date_required") or None
        order.supplier_id = request.POST.get("supplier") or None
        order.project_id = request.POST.get("project") or None

        order.buyer_company_name = (request.POST.get("buyer_company_name") or "").strip() or None
        order.buyer_address = (request.POST.get("buyer_address") or "").strip() or None
        order.buyer_contact_person = (request.POST.get("buyer_contact_person") or "").strip() or None
        order.buyer_phone = (request.POST.get("buyer_phone") or "").strip() or None
        order.buyer_email = (request.POST.get("buyer_email") or "").strip() or None

        order.supplier_address = (request.POST.get("supplier_address") or "").strip() or None
        order.supplier_contact_details = (request.POST.get("supplier_contact_details") or "").strip() or None

        order.payment_method = request.POST.get("payment_method") or "bank"
        order.payment_period = (request.POST.get("payment_period") or "").strip() or None

        order.delivery_location = (request.POST.get("delivery_location") or "").strip() or None
        order.delivery_method = (request.POST.get("delivery_method") or "").strip() or None
        order.special_instructions = (request.POST.get("special_instructions") or "").strip() or None

        order.terms_and_conditions = (request.POST.get("terms_and_conditions") or "").strip() or None
        order.warranty_details = (request.POST.get("warranty_details") or "").strip() or None
        order.return_policy = (request.POST.get("return_policy") or "").strip() or None
        order.penalties_conditions = (request.POST.get("penalties_conditions") or "").strip() or None

        order.authorized_person_name = (request.POST.get("authorized_person_name") or "").strip() or None
        order.signature_text = (request.POST.get("signature_text") or "").strip() or None
        order.status = request.POST.get("status") or "draft"
        order.note = (request.POST.get("note") or "").strip() or None

        if not order.supplier_id:
            messages.error(request, "Supplier is required.")
            return render(request, "pos/edit_purchase_order.html", context)

        descriptions = request.POST.getlist("item_description[]")
        quantities = request.POST.getlist("item_qty[]")
        unit_prices = request.POST.getlist("item_price[]")

        cleaned_rows = []
        row_count = max(len(descriptions), len(quantities), len(unit_prices))

        for i in range(row_count):
            desc = (descriptions[i] if i < len(descriptions) else "").strip()
            qty = to_decimal(quantities[i] if i < len(quantities) else 0)
            price = to_decimal(unit_prices[i] if i < len(unit_prices) else 0)

            if not desc and qty <= 0 and price <= 0:
                continue

            if not desc:
                messages.error(request, f"Item description is required for row {i+1}.")
                return render(request, "pos/edit_purchase_order.html", context)

            if qty <= 0:
                messages.error(request, f"Qty must be greater than 0 for row {i+1}.")
                return render(request, "pos/edit_purchase_order.html", context)

            if price < 0:
                messages.error(request, f"Price cannot be negative for row {i+1}.")
                return render(request, "pos/edit_purchase_order.html", context)

            cleaned_rows.append({
                "description": desc,
                "quantity": qty,
                "unit_price": price,
            })

        if not cleaned_rows:
            messages.error(request, "At least one PO item is required.")
            return render(request, "pos/edit_purchase_order.html", context)

        with transaction.atomic():
            order.save()
            order.items.all().delete()

            for row in cleaned_rows:
                PurchaseOrderItem.objects.create(
                    purchase_order=order,
                    description=row["description"],
                    quantity=row["quantity"],
                    unit_price=row["unit_price"],
                )

        messages.success(request, "Purchase Order updated successfully.")
        return redirect("purchase_order_list")

    return render(request, "pos/edit_purchase_order.html", context)

@user_passes_test(can_use_project)
def purchase_order_data(request, po_id):
    po = get_object_or_404(
        PurchaseOrder.objects.select_related("supplier", "project"),
        id=po_id
    )

    supplier = po.supplier

    amount_value = getattr(po, "estimated_amount", Decimal("0"))

    supplier_phone = ""
    for field_name in ["phone_1", "phone_2", "phone_3", "phone"]:
        value = getattr(supplier, field_name, None)
        if value:
            supplier_phone = value
            break

    return JsonResponse({
        "id": po.id,
        "po_no": po.po_no,
        "supplier_id": po.supplier_id,
        "supplier_name": supplier.name,
        "supplier_address": getattr(po, "supplier_address", "") or getattr(supplier, "address", "") or "",
        "supplier_contact_details": getattr(po, "supplier_contact_details", "") or supplier_phone or "",
        "project_id": po.project_id or "",
        "project_name": po.project.project_name if po.project else "",
        "project_code": po.project.project_id if po.project else "",
        "buyer_company_name": getattr(po, "buyer_company_name", "") or "",
        "buyer_contact_person": getattr(po, "buyer_contact_person", "") or "",
        "buyer_phone": getattr(po, "buyer_phone", "") or "",
        "delivery_location": getattr(po, "delivery_location", "") or "",
        "delivery_method": getattr(po, "delivery_method", "") or "",
        "payment_period": getattr(po, "payment_period", "") or "",
        "amount": str(amount_value or 0),
        "note": po.note or "",
    })

@user_passes_test(can_use_project)
def supplier_settlement_list(request):
    query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    supplier_id = request.GET.get("supplier", "").strip()

    suppliers = Supplier.objects.filter(is_active=True).order_by("name")

    settlements = SupplierSettlement.objects.select_related(
        "advance", "supplier", "project", "expense_gl",
        "linked_project_expense", "created_by", "approved_by"
    ).order_by("-settlement_date", "-id")

    if query:
        settlements = settlements.filter(
            Q(settlement_no__icontains=query) |
            Q(supplier__name__icontains=query) |
            Q(project__project_id__icontains=query) |
            Q(project__project_name__icontains=query) |
            Q(description__icontains=query)
        )

    if status_filter in ["pending", "approved", "rejected"]:
        settlements = settlements.filter(approval_status=status_filter)

    if supplier_id:
        settlements = settlements.filter(supplier_id=supplier_id)

    summary_suppliers = suppliers
    if supplier_id:
        summary_suppliers = summary_suppliers.filter(id=supplier_id)

    supplier_summary = []

    grand_total_advance = Decimal("0")
    grand_approved_applied = Decimal("0")
    grand_available_advance = Decimal("0")
    grand_pending_actual = Decimal("0")
    grand_approved_balance_due = Decimal("0")
    grand_pending_balance_due = Decimal("0")

    for sup in summary_suppliers:
        advances_qs = sup.advances.filter(is_active=True)
        settlements_qs = sup.settlements.all()

        total_advance = advances_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")

        approved_applied = settlements_qs.filter(
            approval_status="approved"
        ).aggregate(total=Sum("advance_applied"))["total"] or Decimal("0")

        pending_actual = settlements_qs.filter(
            approval_status="pending"
        ).aggregate(total=Sum("actual_amount"))["total"] or Decimal("0")

        approved_balance_due = settlements_qs.filter(
            approval_status="approved"
        ).aggregate(total=Sum("balance_due"))["total"] or Decimal("0")

        pending_balance_due = settlements_qs.filter(
            approval_status="pending"
        ).aggregate(total=Sum("balance_due"))["total"] or Decimal("0")

        available_advance = total_advance - approved_applied

        supplier_summary.append({
            "supplier": sup,
            "total_advance": total_advance,
            "approved_applied": approved_applied,
            "available_advance": available_advance,
            "pending_actual": pending_actual,
            "approved_balance_due": approved_balance_due,
            "pending_balance_due": pending_balance_due,
        })

        grand_total_advance += total_advance
        grand_approved_applied += approved_applied
        grand_available_advance += available_advance
        grand_pending_actual += pending_actual
        grand_approved_balance_due += approved_balance_due
        grand_pending_balance_due += pending_balance_due

    return render(request, "pos/supplier_settlement_list.html", {
        "settlements": settlements,
        "suppliers": suppliers,
        "query": query,
        "status_filter": status_filter,
        "selected_supplier": supplier_id,
        "is_owner": is_owner(request.user),
        "supplier_summary": supplier_summary,
        "grand_total_advance": grand_total_advance,
        "grand_approved_applied": grand_approved_applied,
        "grand_available_advance": grand_available_advance,
        "grand_pending_actual": grand_pending_actual,
        "grand_approved_balance_due": grand_approved_balance_due,
        "grand_pending_balance_due": grand_pending_balance_due,
    })
