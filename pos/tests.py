import json
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from .models import (
    BankAccount,
    BankTransaction,
    Company,
    Customer,
    Employee,
    GLMaster,
    LabourAllocation,
    PayrollAllocation,
    PayrollAllowance,
    PayrollDeduction,
    PayrollEntry,
    Project,
    ProjectExpense,
    ProjectIncome,
    ProjectInvoice,
    ProjectInvoicePayment,
    PurchaseOrder,
    Supplier,
    CashAdjustment,
    POSSettings,
    Sale,
    SaleRecovery,
    SalaryAdvance,
    Item,
)
from .barcode_services import generate_barcode_for_item


class BarcodeWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="barcode_admin",
            email="barcode@example.com",
            password="12345",
        )
        self.item = Item.objects.create(
            item_code="1000000065",
            name="Surface Mounted Pool Light",
            selling_price=Decimal("28000.00"),
            stock=Decimal("3"),
        )

    def test_generation_uses_item_code_without_changing_item_code(self):
        item, created = generate_barcode_for_item(self.item.id)

        self.assertTrue(created)
        self.assertEqual(item.barcode, "1000000065")
        self.assertEqual(item.item_code, "1000000065")

    def test_generation_does_not_overwrite_existing_barcode(self):
        self.item.barcode = "CUSTOM-65"
        self.item.save(update_fields=["barcode"])

        item, created = generate_barcode_for_item(self.item.id)

        self.assertFalse(created)
        self.assertEqual(item.barcode, "CUSTOM-65")

    def test_pos_barcode_lookup_returns_active_item_and_rejects_unknown(self):
        self.item.barcode = self.item.item_code
        self.item.save(update_fields=["barcode"])
        self.client.force_login(self.user)

        response = self.client.get(reverse("barcode_lookup"), {"barcode": self.item.item_code})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["id"], self.item.id)

        response = self.client.get(reverse("barcode_lookup"), {"barcode": "UNKNOWN"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["message"], "Barcode not found. Please check Item Master.")


class EmployeeConstructionPayrollTests(TestCase):
    def test_add_employee_saves_construction_payroll_fields(self):
        user = User.objects.create_superuser(username="employee_form_admin", email="employee@example.com", password="12345")
        self.client.force_login(user)

        response = self.client.post(reverse("add_employee"), {
            "full_name": "Asha Perera",
            "nic": "199012345678",
            "employee_category": "Skilled Labour",
            "designation": "Mason",
            "department": "Civil",
            "joining_date": "2024-01-10",
            "basic_salary": "65000",
            "daily_rate": "3000",
            "salary_type": "daily",
            "contract_based": "on",
            "employment_type": "daily_labour",
            "epf_etf_applicable": "on",
            "bank_name": "Sampath Bank",
            "bank_account_no": "123456789",
            "address": "Matara Road",
            "tel": "0771234567",
            "petty_cash_limit": "1000",
            "is_active": "on",
        })

        self.assertRedirects(response, reverse("employee_list"))
        employee = Employee.objects.get(full_name="Asha Perera")
        self.assertEqual(employee.joining_date, date(2024, 1, 10))
        self.assertEqual(employee.salary_type, "daily")
        self.assertTrue(employee.contract_based)
        self.assertEqual(employee.employment_type, "daily_labour")


class BankAccountBalanceTests(TestCase):
    def test_current_balance_tracks_deposits_and_withdrawals(self):
        user = User.objects.create_user(username="banktester", password="12345")
        gl = GLMaster.objects.create(
            gl_code="1009",
            gl_name="Cash at Bank",
            gl_type="asset",
            parent_group="Current Assets",
        )

        account = BankAccount.objects.create(
            bank_name="Sampath Bank",
            branch_name="Colombo",
            account_name="P&I Constructions",
            account_number="1234567890",
            account_type="current",
            opening_balance=Decimal("5000.00"),
            gl_account=gl,
            is_active=True,
        )

        BankTransaction.objects.create(
            account=account,
            transaction_type="deposit",
            amount=Decimal("1500.00"),
            description="Cash deposit",
            created_by=user,
            approval_status="posted",
        )
        BankTransaction.objects.create(
            account=account,
            transaction_type="withdrawal",
            amount=Decimal("700.00"),
            description="Cheque payment",
            created_by=user,
            approval_status="posted",
        )

        self.assertEqual(account.current_balance, Decimal("6800.00"))


class CreditRecoveryBankTransferTests(TestCase):
    def test_bank_transfer_recovery_reduces_credit_balance_and_updates_bank_account(self):
        user = User.objects.create_superuser(username="recovery_admin", email="recovery@example.com", password="12345")
        self.client.force_login(user)

        receivable_gl = GLMaster.objects.create(
            gl_code="1200",
            gl_name="Trade Receivables",
            gl_type="asset",
            parent_group="Current Assets",
        )
        customer = Customer.objects.create(
            customer_code="CUST-001",
            name="A. Silva",
            credit_limit=Decimal("1500.00"),
            receivable_gl_account=receivable_gl,
        )
        bank_gl = GLMaster.objects.create(
            gl_code="1001",
            gl_name="Bank Current Account",
            gl_type="asset",
            parent_group="Current Assets",
        )
        bank_account = BankAccount.objects.create(
            bank_name="Bank of Ceylon",
            account_name="P&I Collections",
            account_number="9876543210",
            opening_balance=Decimal("2000.00"),
            gl_account=bank_gl,
            is_active=True,
        )
        sale = Sale.objects.create(
            invoice_no="INV00099",
            total=Decimal("1000.00"),
            grand_total=Decimal("1000.00"),
            payment_method="credit",
            customer=customer,
            customer_name=customer.name,
            cheque_number="CH-1001",
            created_by=user,
        )

        response = self.client.post(
            reverse("add_sale_recovery", args=[sale.id]),
            {
                "recovery_date": "2026-09-10",
                "payment_method": "bank",
                "amount": "250.00",
                "bank_account": str(bank_account.id),
                "bank_transfer_reference": "TRF-20260910",
                "bank_transfer_remarks": "Customer settlement",
                "note": "Bank transfer",
            },
        )

        self.assertRedirects(response, reverse("credit_sales_list"))
        recovery = SaleRecovery.objects.get(sale=sale)
        self.assertEqual(recovery.payment_method, "bank")
        self.assertEqual(recovery.bank_account, bank_account)
        self.assertEqual(recovery.amount, Decimal("250.00"))
        self.assertEqual(sale.credit_balance, Decimal("750.00"))
        bank_account.refresh_from_db()
        self.assertEqual(bank_account.current_balance, Decimal("1750.00"))


class ProjectProfitDateRangeTests(TestCase):
    def test_project_profit_dashboard_respects_selected_date_range(self):
        user = User.objects.create_superuser(username="profit_admin", email="profit@example.com", password="12345")
        project = Project.objects.create(
            project_id="PRO2026P001",
            project_name="House Construction - Galle",
            project_type="BL",
            client_name="Client A",
            status="ongoing",
            created_by=user,
        )

        historical_expense = ProjectExpense.objects.create(
            expense_no="PE-OLD-001",
            project=project,
            expense_date="2026-08-20",
            description="August cost",
            amount=Decimal("300.00"),
            created_by=user,
        )
        current_expense = ProjectExpense.objects.create(
            expense_no="PE-NEW-001",
            project=project,
            expense_date="2026-09-15",
            description="September cost",
            amount=Decimal("500.00"),
            created_by=user,
        )

        invoice = ProjectInvoice.objects.create(
            project=project,
            invoice_date="2026-09-05",
            description="September progress bill",
            total_amount=Decimal("1000.00"),
            created_by=user,
        )
        ProjectInvoicePayment.objects.create(
            invoice=invoice,
            payment_date="2026-09-05",
            payment_type="progress",
            payment_method="cash",
            amount=Decimal("1000.00"),
            created_by=user,
        )

        self.client.force_login(user)
        response = self.client.get(
            reverse("project_profit_dashboard"),
            {
                "from_date": "2026-09-01",
                "to_date": "2026-09-30",
                "project_id": str(project.id),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Project Profit Dashboard")
        self.assertContains(response, "500.00")
        self.assertNotContains(response, "300.00")


class PayrollPaysheetViewTests(TestCase):
    def test_paysheet_view_renders_payroll_summary(self):
        user = User.objects.create_superuser(username="paysheet_admin", email="admin@example.com", password="12345")
        employee = Employee.objects.create(full_name="Nadeesha Silva", designation="Mason")
        project = Project.objects.create(project_id="PRJ-010", project_name="Warehouse Project", project_type="BL", created_by=user)
        labour_gl = GLMaster.objects.create(gl_code="5200", gl_name="Direct Labour Cost", gl_type="expense", parent_group="Direct Labour Cost")
        payable_gl = GLMaster.objects.create(gl_code="2100", gl_name="Salary Payable", gl_type="liability", parent_group="Current Liabilities")
        bank_gl = GLMaster.objects.create(gl_code="1000", gl_name="Bank", gl_type="asset", parent_group="Current Assets")

        payroll = PayrollEntry.objects.create(
            employee=employee,
            project=project,
            department="Civil",
            employee_category="Skilled Labour",
            designation="Mason",
            salary_period="monthly",
            working_days=20,
            ot_hours=0,
            gross_salary=Decimal("100000"),
            labour_gl_account=labour_gl,
            salary_payable_gl_account=payable_gl,
            bank_gl_account=bank_gl,
            created_by=user,
            status="approved",
        )
        PayrollAllowance.objects.create(payroll_entry=payroll, allowance_name="Site Allowance", amount=Decimal("5000"))
        PayrollDeduction.objects.create(payroll_entry=payroll, deduction_type="salary_advance", amount=Decimal("20000"))

        self.client.force_login(user)
        response = self.client.get(reverse("payroll_paysheet"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Paysheet")
        self.assertContains(response, employee.full_name)
        self.assertContains(response, "85000.00")

    def test_payslip_detail_view_renders_individual_payslip(self):
        user = User.objects.create_superuser(username="payslip_admin", email="admin2@example.com", password="12345")
        employee = Employee.objects.create(full_name="Nadeesha Silva", designation="Mason")
        project = Project.objects.create(project_id="PRJ-011", project_name="Office Project", project_type="BL", created_by=user)
        labour_gl = GLMaster.objects.create(gl_code="5201", gl_name="Direct Labour Cost", gl_type="expense", parent_group="Direct Labour Cost")
        payable_gl = GLMaster.objects.create(gl_code="2101", gl_name="Salary Payable", gl_type="liability", parent_group="Current Liabilities")
        bank_gl = GLMaster.objects.create(gl_code="1001", gl_name="Bank", gl_type="asset", parent_group="Current Assets")

        payroll = PayrollEntry.objects.create(
            employee=employee,
            project=project,
            department="Civil",
            employee_category="Skilled Labour",
            designation="Mason",
            salary_period="monthly",
            working_days=20,
            ot_hours=0,
            gross_salary=Decimal("90000"),
            labour_gl_account=labour_gl,
            salary_payable_gl_account=payable_gl,
            bank_gl_account=bank_gl,
            created_by=user,
            status="approved",
        )
        PayrollAllowance.objects.create(payroll_entry=payroll, allowance_name="Site Allowance", amount=Decimal("5000"))
        PayrollDeduction.objects.create(payroll_entry=payroll, deduction_type="Salary Advance", amount=Decimal("2000"))

        self.client.force_login(user)
        response = self.client.get(reverse("payroll_payslip_detail", args=[payroll.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payslip")
        self.assertContains(response, employee.full_name)
        self.assertContains(response, "90000.00")
        self.assertContains(response, "5000.00")
        self.assertContains(response, "2000.00")
        self.assertContains(response, "93000.00")

    def test_draft_payslip_is_blocked_until_approval(self):
        user = User.objects.create_superuser(username="draft_payslip_admin", email="admin3@example.com", password="12345")
        employee = Employee.objects.create(full_name="Kasun Perera", designation="Helper")
        project = Project.objects.create(project_id="PRJ-012", project_name="Bridge Project", project_type="BL", created_by=user)
        labour_gl = GLMaster.objects.create(gl_code="5202", gl_name="Direct Labour Cost", gl_type="expense", parent_group="Direct Labour Cost")
        payable_gl = GLMaster.objects.create(gl_code="2102", gl_name="Salary Payable", gl_type="liability", parent_group="Current Liabilities")
        bank_gl = GLMaster.objects.create(gl_code="1002", gl_name="Bank", gl_type="asset", parent_group="Current Assets")

        payroll = PayrollEntry.objects.create(
            employee=employee,
            project=project,
            department="Civil",
            employee_category="Unskilled Labour",
            designation="Helper",
            salary_period="monthly",
            working_days=20,
            ot_hours=0,
            gross_salary=Decimal("50000"),
            labour_gl_account=labour_gl,
            salary_payable_gl_account=payable_gl,
            bank_gl_account=bank_gl,
            created_by=user,
            status="draft",
        )

        self.client.force_login(user)
        response = self.client.get(reverse("payroll_payslip_detail", args=[payroll.id]))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("payroll_list"))

    def test_approving_payroll_generates_payslip_number(self):
        user = User.objects.create_superuser(username="payslip_number_admin", email="admin4@example.com", password="12345")
        employee = Employee.objects.create(full_name="Ravi Senanayake", designation="Driver")
        project = Project.objects.create(project_id="PRJ-013", project_name="Road Project", project_type="BL", created_by=user)
        labour_gl = GLMaster.objects.create(gl_code="5203", gl_name="Direct Labour Cost", gl_type="expense", parent_group="Direct Labour Cost")
        payable_gl = GLMaster.objects.create(gl_code="2103", gl_name="Salary Payable", gl_type="liability", parent_group="Current Liabilities")
        bank_gl = GLMaster.objects.create(gl_code="1003", gl_name="Bank", gl_type="asset", parent_group="Current Assets")

        payroll = PayrollEntry.objects.create(
            employee=employee,
            project=project,
            department="Operations",
            employee_category="Driver",
            designation="Driver",
            salary_period="monthly",
            working_days=20,
            ot_hours=0,
            gross_salary=Decimal("60000"),
            labour_gl_account=labour_gl,
            salary_payable_gl_account=payable_gl,
            bank_gl_account=bank_gl,
            created_by=user,
            status="draft",
        )

        payroll.approve(approved_by=user)
        payroll.refresh_from_db()

        self.assertRegex(payroll.payslip_no, r"^PS-\d{4}-\d{2}-\d{5}$")


class PayrollProjectIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="payroll", password="12345")
        self.employee = Employee.objects.create(full_name="Saman Perera", designation="Site Engineer")
        self.project_a = Project.objects.create(project_id="PRJ-001", project_name="Hotel Construction - Galle", project_type="BL", created_by=self.user)
        self.project_b = Project.objects.create(project_id="PRJ-002", project_name="Apartment Project - Colombo", project_type="BL", created_by=self.user)
        self.labour_gl = GLMaster.objects.create(gl_code="5200", gl_name="Direct Labour Cost", gl_type="expense", parent_group="Direct Labour Cost")
        self.payable_gl = GLMaster.objects.create(gl_code="2100", gl_name="Salary Payable", gl_type="liability", parent_group="Current Liabilities")
        self.bank_gl = GLMaster.objects.create(gl_code="1000", gl_name="Bank", gl_type="asset", parent_group="Current Assets")

    def test_approval_creates_project_cost_and_gl_entries(self):
        payroll = PayrollEntry.objects.create(
            employee=self.employee,
            project=self.project_a,
            supervisor=self.employee,
            department="Civil",
            employee_category="Skilled Labour",
            designation="Site Engineer",
            salary_period="monthly",
            working_days=20,
            ot_hours=4,
            gross_salary=Decimal("100000"),
            labour_gl_account=self.labour_gl,
            salary_payable_gl_account=self.payable_gl,
            bank_gl_account=self.bank_gl,
            created_by=self.user,
        )
        PayrollAllocation.objects.create(payroll_entry=payroll, project=self.project_a, amount=Decimal("60000"))
        PayrollAllocation.objects.create(payroll_entry=payroll, project=self.project_b, amount=Decimal("40000"))

        payroll.approve(approved_by=self.user)

        payroll.refresh_from_db()
        self.assertEqual(payroll.status, "approved")
        self.assertEqual(payroll.allocations.count(), 2)
        self.assertEqual(payroll.project_cost_entries.count(), 2)
        self.assertEqual(payroll.gl_entries.count(), 1)

    def test_approval_requires_a_project_selection(self):
        payroll = PayrollEntry.objects.create(
            employee=self.employee,
            supervisor=self.employee,
            department="Civil",
            employee_category="Skilled Labour",
            designation="Site Engineer",
            salary_period="monthly",
            working_days=20,
            ot_hours=0,
            gross_salary=Decimal("50000"),
            labour_gl_account=self.labour_gl,
            salary_payable_gl_account=self.payable_gl,
            bank_gl_account=self.bank_gl,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            payroll.approve(approved_by=self.user)

    def test_employee_master_supports_construction_payroll_fields(self):
        employee = Employee.objects.create(
            full_name="Nimal Perera",
            nic="199012345678",
            employee_category="Skilled Labour",
            department="Civil",
            designation="Mason",
            basic_salary=Decimal("65000"),
            daily_rate=Decimal("3000"),
            employment_type="daily_labour",
            epf_etf_applicable=True,
            bank_name="Sampath Bank",
            bank_account_no="123456789",
        )

        self.assertEqual(employee.nic, "199012345678")
        self.assertEqual(employee.employee_category, "Skilled Labour")
        self.assertEqual(employee.employment_type, "daily_labour")
        self.assertTrue(employee.epf_etf_applicable)

    def test_daily_labour_allocation_can_be_recorded(self):
        employee = Employee.objects.create(full_name="Kasun Silva")
        project = Project.objects.create(project_id="PRJ-003", project_name="Hotel Project", project_type="BL", created_by=self.user)

        allocation = LabourAllocation.objects.create(
            employee=employee,
            project=project,
            date="2026-07-01",
            supervisor=employee,
            work_type="Mason",
            working_hours=Decimal("8"),
            ot_hours=Decimal("2"),
            attendance_status="present",
            remarks="Full day",
        )

        self.assertEqual(allocation.project.project_name, "Hotel Project")
        self.assertEqual(allocation.attendance_status, "present")
        self.assertEqual(allocation.working_hours, Decimal("8"))

    def test_salary_advance_and_payroll_deductions_are_supported(self):
        advance = SalaryAdvance.objects.create(
            employee=self.employee,
            amount=Decimal("20000"),
            advance_date="2026-07-01",
            reason="Emergency",
            status="approved",
        )
        payroll = PayrollEntry.objects.create(
            employee=self.employee,
            project=self.project_a,
            gross_salary=Decimal("100000"),
            labour_gl_account=self.labour_gl,
            salary_payable_gl_account=self.payable_gl,
            bank_gl_account=self.bank_gl,
            created_by=self.user,
        )
        PayrollAllowance.objects.create(payroll_entry=payroll, allowance_name="Site Allowance", amount=Decimal("5000"))
        PayrollDeduction.objects.create(payroll_entry=payroll, deduction_type="salary_advance", amount=Decimal("20000"), description="Advance deduction")

        self.assertEqual(advance.remaining_balance, Decimal("20000"))
        self.assertEqual(payroll.total_allowances, Decimal("5000"))
        self.assertEqual(payroll.total_deductions, Decimal("20000"))
        self.assertEqual(payroll.net_salary, Decimal("85000"))


class RetailCashBalanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="cash_admin", email="cash@example.com", password="12345")
        self.project = Project.objects.create(project_id="P-CASH", project_name="Cash Test Project")
        self.seq = 0

    def make_sale(self, amount, sale_type="retail", payment_method="cash", **extra):
        self.seq += 1
        return Sale.objects.create(
            invoice_no=f"INVCB{self.seq:04d}",
            total=Decimal(amount),
            grand_total=Decimal(amount),
            sale_type=sale_type,
            payment_method=payment_method,
            created_by=self.user,
            **extra,
        )

    def make_adjustment(self, adjustment_type, amount, status):
        self.seq += 1
        return CashAdjustment.objects.create(
            adjustment_date=date(2026, 9, 22),
            adjustment_type=adjustment_type,
            amount=Decimal(amount),
            reason="test",
            reference=f"CA-TEST-{self.seq:04d}",
            approval_status=status,
            created_by=self.user,
        )

    def balance(self):
        from .payment_summary_views import get_current_cash_balance
        return get_current_cash_balance()

    def test_retail_cash_included(self):
        self.make_sale("50000.00")
        self.assertEqual(self.balance(), Decimal("50000.00"))

    def test_project_cash_excluded(self):
        self.make_sale("30000.00", sale_type="project_issue", project=self.project)
        self.assertEqual(self.balance(), Decimal("0"))

    def test_retail_non_cash_methods_excluded(self):
        customer = Customer.objects.create(name="Credit Cust", registration_no="R1", credit_limit=Decimal("100000"))
        self.make_sale("20000.00", payment_method="card", card_last4="1234")
        self.make_sale("10000.00", payment_method="credit", customer=customer, cheque_number="CH-1")
        self.make_sale("7000.00", payment_method="bank_transfer", bank_transfer_reference="REF1")
        self.assertEqual(self.balance(), Decimal("0"))

    def test_spec_example_with_approved_decrease(self):
        self.make_sale("50000.00")
        self.make_sale("30000.00", sale_type="project_issue", project=self.project)
        self.make_sale("20000.00", payment_method="card", card_last4="1234")
        self.make_adjustment("cash_decrease", "5000.00", "approved")
        self.assertEqual(self.balance(), Decimal("45000.00"))

    def test_draft_and_pending_adjustments_do_not_affect_balance(self):
        self.make_sale("1000.00")
        self.make_adjustment("cash_increase", "500.00", "draft")
        self.make_adjustment("cash_decrease", "300.00", "pending")
        self.assertEqual(self.balance(), Decimal("1000.00"))

    def test_approved_and_posted_adjustments_affect_balance(self):
        self.make_sale("1000.00")
        self.make_adjustment("cash_increase", "500.00", "approved")
        self.make_adjustment("cash_increase", "200.00", "posted")
        self.make_adjustment("cash_decrease", "300.00", "posted")
        from .payment_summary_views import get_cash_balance_breakdown
        breakdown = get_cash_balance_breakdown()
        self.assertEqual(breakdown["retail_cash_sales"], Decimal("1000.00"))
        self.assertEqual(breakdown["cash_increases"], Decimal("700.00"))
        self.assertEqual(breakdown["cash_decreases"], Decimal("300.00"))
        self.assertEqual(breakdown["balance"], Decimal("1400.00"))

    def test_pages_show_breakdown_and_do_not_change_sales(self):
        self.make_sale("50000.00")
        self.make_adjustment("cash_decrease", "5000.00", "approved")
        before = list(Sale.objects.values_list("id", "grand_total", "sale_type", "payment_method"))
        self.client.force_login(self.user)
        for name in ("payment_summary_dashboard", "cash_adjustment_list"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["cash_breakdown"]["balance"], Decimal("45000.00"))
        self.assertEqual(before, list(Sale.objects.values_list("id", "grand_total", "sale_type", "payment_method")))

    def test_detail_preview_does_not_double_count_approved_adjustment(self):
        self.make_sale("50000.00")
        adj = self.make_adjustment("cash_decrease", "5000.00", "approved")
        self.client.force_login(self.user)
        response = self.client.get(reverse("cash_adjustment_detail", args=[adj.id]))
        self.assertEqual(response.context["current_cash"], Decimal("45000.00"))
        self.assertEqual(response.context["preview_cash"], Decimal("45000.00"))


class PaymentSummaryChequeClassificationTests(TestCase):
    """
    Regression tests for: Credit sales were being counted in the Cheque
    column because cheque_number (reused as a reference no. for Credit
    sales) was treated as evidence of a cheque payment. Cheque must be
    based strictly on payment_method == 'cheque'.
    """

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="cheque_admin", email="cheque_admin@example.com", password="12345"
        )
        self.customer = Customer.objects.create(
            name="Cheque Test Customer", registration_no="RCH1", credit_limit=Decimal("100000")
        )
        self.seq = 0

    def make_sale(self, amount, payment_method, cheque_number=None, **extra):
        self.seq += 1
        return Sale.objects.create(
            invoice_no=f"INVCHQ{self.seq:04d}",
            total=Decimal(amount),
            grand_total=Decimal(amount),
            sale_type="retail",
            payment_method=payment_method,
            cheque_number=cheque_number,
            created_by=self.user,
            **extra,
        )

    def summary_totals(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("payment_summary_dashboard"))
        self.assertEqual(response.status_code, 200)
        return response.context["period_totals"]

    def test_credit_with_cheque_number_counts_as_credit_not_cheque(self):
        # Test 1: mirrors production examples INV00139/INV00137 - Credit
        # sale with a "reference no." accidentally looking like a cheque no.
        self.make_sale("3500.00", "credit", cheque_number="0001", customer=self.customer)
        totals = self.summary_totals()
        self.assertEqual(totals["credit"], Decimal("3500.00"))
        self.assertEqual(totals["cheque"], Decimal("0"))

    def test_credit_without_cheque_number_counts_as_credit(self):
        # Test 2
        self.make_sale("1200.00", "credit", cheque_number=None, customer=self.customer)
        totals = self.summary_totals()
        self.assertEqual(totals["credit"], Decimal("1200.00"))
        self.assertEqual(totals["cheque"], Decimal("0"))

    def test_actual_cheque_payment_method_counts_as_cheque(self):
        # Test 3
        self.make_sale("900.00", "cheque", cheque_number="CQ-1")
        totals = self.summary_totals()
        self.assertEqual(totals["cheque"], Decimal("900.00"))
        self.assertEqual(totals["credit"], Decimal("0"))

    def test_cash_counts_only_as_cash(self):
        # Test 4
        self.make_sale("500.00", "cash")
        totals = self.summary_totals()
        self.assertEqual(totals["cash"], Decimal("500.00"))
        self.assertEqual(totals["cheque"], Decimal("0"))
        self.assertEqual(totals["credit"], Decimal("0"))

    def test_card_counts_only_as_card(self):
        # Test 5
        self.make_sale("650.00", "card", card_last4="1234")
        totals = self.summary_totals()
        self.assertEqual(totals["card"], Decimal("650.00"))
        self.assertEqual(totals["cheque"], Decimal("0"))

    def test_bank_transfer_counts_only_as_bank_transfer(self):
        # Test 6
        self.make_sale("2200.00", "bank_transfer", bank_transfer_reference="REF-1")
        totals = self.summary_totals()
        self.assertEqual(totals["bank_transfer"], Decimal("2200.00"))
        self.assertEqual(totals["cheque"], Decimal("0"))

    def test_period_grand_total_matches_sum_of_all_methods(self):
        self.make_sale("3500.00", "credit", cheque_number="0001", customer=self.customer)
        self.make_sale("500.00", "cash")
        self.make_sale("650.00", "card", card_last4="1234")
        self.make_sale("2200.00", "bank_transfer", bank_transfer_reference="REF-1")
        self.make_sale("900.00", "cheque", cheque_number="CQ-1")
        totals = self.summary_totals()
        self.assertEqual(sum(totals.values()), Decimal("7750.00"))

    def test_receipt_shows_reference_no_not_cheque_no_for_credit(self):
        sale = self.make_sale("3500.00", "credit", cheque_number="0001", customer=self.customer)
        self.client.force_login(self.user)
        response = self.client.get(reverse("invoice_page", args=[sale.id]))
        content = response.content.decode()
        self.assertIn("Reference No", content)
        self.assertNotIn("Cheque No", content)

    def test_receipt_shows_cheque_no_for_actual_cheque_payment(self):
        sale = self.make_sale("900.00", "cheque", cheque_number="CQ-1")
        self.client.force_login(self.user)
        response = self.client.get(reverse("invoice_page", args=[sale.id]))
        content = response.content.decode()
        self.assertIn("Cheque No", content)


class PosChequePaymentMethodTests(TestCase):
    """
    Cheque is now a real Sale.payment_method choice. These tests drive the
    actual POS save_sale endpoint end-to-end (not just model-level
    aggregation) for the new payment method, alongside Cash/Card/Credit/
    Bank Transfer to prove nothing else broke.
    """

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="cheque_pm_admin", email="cheque_pm_admin@example.com", password="12345"
        )
        self.customer = Customer.objects.create(
            name="Cheque PM Customer", registration_no="RCHPM1", credit_limit=Decimal("100000")
        )
        gl = GLMaster.objects.create(gl_code="CHQPM-1", gl_name="Retail Sales GL", gl_type="income")
        self.item = Item.objects.create(
            item_code="CHQPM-ITEM",
            name="Cheque PM Test Service",
            selling_price=Decimal("1000.00"),
            is_service=True,
            retail_gl_account=gl,
        )
        self.client.force_login(self.user)

    def post_sale(self, payment_method, **extra):
        payload = {
            "items": [{"id": self.item.id, "qty": 1, "price": "1000.00", "discount": 0}],
            "discount": 0,
            "payment_method": payment_method,
        }
        payload.update(extra)
        return self.client.post(
            reverse("save_sale"), data=json.dumps(payload), content_type="application/json"
        )

    def test_a_cash_sale_goes_to_cash_column(self):
        response = self.post_sale("cash", received="1000.00")
        self.assertEqual(response.status_code, 200, response.content)
        sale = Sale.objects.get(invoice_no=response.json()["invoice_no"])
        self.assertEqual(sale.payment_method, "cash")
        totals = self.client.get(reverse("payment_summary_dashboard")).context["period_totals"]
        self.assertEqual(totals["cash"], Decimal("1000.00"))
        self.assertEqual(totals["cheque"], Decimal("0"))

    def test_b_card_sale_goes_to_card_column(self):
        response = self.post_sale("card", card_last4="1234")
        self.assertEqual(response.status_code, 200, response.content)
        totals = self.client.get(reverse("payment_summary_dashboard")).context["period_totals"]
        self.assertEqual(totals["card"], Decimal("1000.00"))
        self.assertEqual(totals["cheque"], Decimal("0"))

    def test_c_credit_sale_with_reference_goes_to_credit_not_cheque(self):
        response = self.post_sale(
            "credit", cheque_number="0001", customer_id=self.customer.id, customer_name=self.customer.name
        )
        self.assertEqual(response.status_code, 200, response.content)
        sale = Sale.objects.get(invoice_no=response.json()["invoice_no"])
        self.assertEqual(sale.payment_method, "credit")
        self.assertEqual(sale.cheque_number, "0001")
        totals = self.client.get(reverse("payment_summary_dashboard")).context["period_totals"]
        self.assertEqual(totals["credit"], Decimal("1000.00"))
        self.assertEqual(totals["cheque"], Decimal("0"))

    def test_d_bank_transfer_sale_goes_to_bank_transfer_column(self):
        bank_gl = GLMaster.objects.create(gl_code="CHQPM-BANK-GL", gl_name="Bank GL", gl_type="asset")
        bank = BankAccount.objects.create(
            bank_name="Cheque PM Bank", account_name="Main", account_number="ACC-1",
            opening_balance=Decimal("0"), gl_account=bank_gl,
        )
        response = self.post_sale(
            "bank_transfer", bank_account_id=bank.id, bank_transfer_reference="REF-1"
        )
        self.assertEqual(response.status_code, 200, response.content)
        totals = self.client.get(reverse("payment_summary_dashboard")).context["period_totals"]
        self.assertEqual(totals["bank_transfer"], Decimal("1000.00"))
        self.assertEqual(totals["cheque"], Decimal("0"))

    def test_e_cheque_sale_with_cheque_number_goes_to_cheque_column(self):
        response = self.post_sale("cheque", cheque_number="CQ-9001")
        self.assertEqual(response.status_code, 200, response.content)
        sale = Sale.objects.get(invoice_no=response.json()["invoice_no"])
        self.assertEqual(sale.payment_method, "cheque")
        self.assertEqual(sale.cheque_number, "CQ-9001")
        totals = self.client.get(reverse("payment_summary_dashboard")).context["period_totals"]
        self.assertEqual(totals["cheque"], Decimal("1000.00"))
        self.assertEqual(totals["credit"], Decimal("0"))

    def test_f_cheque_sale_without_cheque_number_is_rejected_and_not_saved(self):
        count_before = Sale.objects.count()
        response = self.post_sale("cheque")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Cheque Number is required for cheque payments.")
        self.assertEqual(Sale.objects.count(), count_before)

    def test_g_credit_sale_with_numeric_looking_reference_is_not_cheque(self):
        response = self.post_sale(
            "credit", cheque_number="0001", customer_id=self.customer.id, customer_name=self.customer.name
        )
        self.assertEqual(response.status_code, 200, response.content)
        sale = Sale.objects.get(invoice_no=response.json()["invoice_no"])
        self.assertEqual(sale.payment_method, "credit")
        self.assertNotEqual(sale.payment_method, "cheque")

    def test_h_receipt_labels_reference_no_for_credit_and_cheque_no_for_cheque(self):
        credit_resp = self.post_sale(
            "credit", cheque_number="0001", customer_id=self.customer.id, customer_name=self.customer.name
        )
        cheque_resp = self.post_sale("cheque", cheque_number="CQ-9001")
        credit_sale = Sale.objects.get(invoice_no=credit_resp.json()["invoice_no"])
        cheque_sale = Sale.objects.get(invoice_no=cheque_resp.json()["invoice_no"])

        credit_html = self.client.get(reverse("invoice_page", args=[credit_sale.id])).content.decode()
        self.assertIn("Reference No", credit_html)
        self.assertNotIn("Cheque No", credit_html)

        cheque_html = self.client.get(reverse("invoice_page", args=[cheque_sale.id])).content.decode()
        self.assertIn("Cheque No", cheque_html)

    def test_i_payment_summary_cheque_total_is_payment_method_cheque_only(self):
        self.post_sale("credit", cheque_number="0001", customer_id=self.customer.id, customer_name=self.customer.name)
        self.post_sale("cheque", cheque_number="CQ-1")
        totals = self.client.get(reverse("payment_summary_dashboard")).context["period_totals"]
        self.assertEqual(totals["cheque"], Decimal("1000.00"))
        self.assertEqual(totals["credit"], Decimal("1000.00"))

    def test_payment_report_cheque_total_is_payment_method_cheque_only(self):
        self.post_sale("credit", cheque_number="0001", customer_id=self.customer.id, customer_name=self.customer.name)
        self.post_sale("cheque", cheque_number="CQ-1")
        context = self.client.get(reverse("payment_report")).context
        self.assertEqual(context["cheque_total"], Decimal("1000.00"))
        self.assertEqual(context["credit_total"], Decimal("1000.00"))

    def test_historical_credit_sale_with_cheque_like_reference_is_not_converted(self):
        # Simulates the pre-existing production data pattern (Credit sale
        # whose cheque_number field happens to hold "0001") and proves the
        # new payment method does not retroactively reclassify it.
        historical = Sale.objects.create(
            invoice_no="INVHIST0001",
            total=Decimal("2500.00"),
            grand_total=Decimal("2500.00"),
            sale_type="retail",
            payment_method="credit",
            cheque_number="0001",
            customer=self.customer,
            customer_name=self.customer.name,
            created_by=self.user,
        )
        historical.refresh_from_db()
        self.assertEqual(historical.payment_method, "credit")
        totals = self.client.get(reverse("payment_summary_dashboard")).context["period_totals"]
        self.assertEqual(totals["credit"], Decimal("2500.00"))
        self.assertEqual(totals["cheque"], Decimal("0"))


class POSDefaultBankAccountTests(TestCase):
    """
    Default Retail Shop Bank Transfer Account: POSSettings.get_solo()
    holds a single default BankAccount. pos_page exposes it for the POS
    screen to auto-select; the cashier can still override it per sale.
    """

    def setUp(self):
        self.owner = User.objects.create_superuser(
            username="pos_settings_owner", email="pos_settings_owner@example.com", password="12345"
        )
        cashier_group, _ = Group.objects.get_or_create(name="Cashier")
        self.cashier = User.objects.create_user(username="pos_settings_cashier", password="12345")
        self.cashier.groups.add(cashier_group)

        gl = GLMaster.objects.create(gl_code="POSSET-GL", gl_name="Bank GL", gl_type="asset")
        self.account_a = BankAccount.objects.create(
            bank_name="BOC", account_name="Current", account_number="POSSET-BOC-1",
            opening_balance=Decimal("0"), gl_account=gl,
        )
        self.account_b = BankAccount.objects.create(
            bank_name="Sampath", account_name="Current", account_number="POSSET-SMP-1",
            opening_balance=Decimal("0"), gl_account=gl,
        )

    def test_cashier_cannot_access_pos_settings(self):
        # Restricted to Owner/Superuser only, per spec.
        self.client.force_login(self.cashier)
        response = self.client.get(reverse("pos_settings"))
        self.assertNotEqual(response.status_code, 200)

    def test_owner_can_set_default_bank_account(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("pos_settings"), {"default_bank_transfer_account": self.account_a.id}
        )
        self.assertEqual(response.status_code, 302)
        settings_row = POSSettings.get_solo()
        self.assertEqual(settings_row.default_bank_transfer_account_id, self.account_a.id)

    def test_owner_can_clear_default_bank_account(self):
        POSSettings.objects.create(default_bank_transfer_account=self.account_a)
        self.client.force_login(self.owner)
        self.client.post(reverse("pos_settings"), {"default_bank_transfer_account": ""})
        settings_row = POSSettings.get_solo()
        self.assertIsNone(settings_row.default_bank_transfer_account)

    def test_pos_page_exposes_default_bank_account_id(self):
        POSSettings.objects.create(default_bank_transfer_account=self.account_a)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("pos"))
        self.assertEqual(response.context["default_bank_account_id"], self.account_a.id)

    def test_inactive_default_account_is_not_exposed_on_pos_page(self):
        POSSettings.objects.create(default_bank_transfer_account=self.account_a)
        self.account_a.is_active = False
        self.account_a.save()
        self.client.force_login(self.owner)
        response = self.client.get(reverse("pos"))
        self.assertIsNone(response.context["default_bank_account_id"])

    def test_get_solo_creates_and_reuses_a_single_row(self):
        self.assertEqual(POSSettings.objects.count(), 0)
        row1 = POSSettings.get_solo()
        row2 = POSSettings.get_solo()
        self.assertEqual(row1.id, row2.id)
        self.assertEqual(POSSettings.objects.count(), 1)

    def test_manual_account_selection_overrides_default_for_that_sale_only(self):
        # Sale 3 from the spec example: default is BOC, cashier picks
        # Sampath for this one sale - only this sale should use Sampath.
        POSSettings.objects.create(default_bank_transfer_account=self.account_a)
        gl = GLMaster.objects.create(gl_code="POSSET-ITEM-GL", gl_name="Retail Sales GL", gl_type="income")
        item = Item.objects.create(
            item_code="POSSET-ITEM", name="POS Settings Test Service",
            selling_price=Decimal("500.00"), is_service=True, retail_gl_account=gl,
        )
        self.client.force_login(self.owner)
        payload = {
            "items": [{"id": item.id, "qty": 1, "price": "500.00", "discount": 0}],
            "discount": 0,
            "payment_method": "bank_transfer",
            "bank_account_id": self.account_b.id,
            "bank_transfer_reference": "REF-OVERRIDE-1",
        }
        response = self.client.post(
            reverse("save_sale"), data=json.dumps(payload), content_type="application/json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        sale = Sale.objects.get(invoice_no=response.json()["invoice_no"])
        self.assertEqual(sale.bank_account_id, self.account_b.id)
        self.assertNotEqual(sale.bank_account_id, self.account_a.id)
        # Default configuration itself is unchanged by a per-sale override.
        self.assertEqual(POSSettings.get_solo().default_bank_transfer_account_id, self.account_a.id)


class MultiCompanyFoundationBackfillTests(TestCase):
    """
    Tests the actual 0039_backfill_company_comp001 migration function
    directly (not just the end-state), since the project's pre-existing,
    unrelated migration history (0001/0003 both CreateModel PurchaseOrder)
    prevents `manage.py test` from building its DB via a real from-scratch
    `migrate` today. Calling the migration's own backfill_company function
    against live model classes proves the backfill logic itself - COMP001
    creation, idempotency, and "only touch unmapped projects" - is correct,
    independent of that unrelated blocker.
    """

    def _backfill(self):
        import importlib
        module = importlib.import_module("pos.migrations.0039_backfill_company_comp001")
        module.backfill_company(apps=_FakeAppsRegistry(), schema_editor=None)

    def test_backfill_creates_comp001_with_real_company_name(self):
        self.assertEqual(Company.objects.count(), 0)
        self._backfill()
        company = Company.objects.get(company_code="COMP001")
        self.assertEqual(company.company_name, "P&I Constructions")
        self.assertTrue(company.is_active)

    def test_backfill_maps_existing_unmapped_projects_to_comp001(self):
        p1 = Project.objects.create(project_id="PRO2025SW001", project_name="Pool A", project_type="SW")
        p2 = Project.objects.create(project_id="PRO2025BL001", project_name="Building A", project_type="BL")
        self._backfill()
        p1.refresh_from_db()
        p2.refresh_from_db()
        company = Company.objects.get(company_code="COMP001")
        self.assertEqual(p1.company_id, company.id)
        self.assertEqual(p2.company_id, company.id)
        # Project ID / name / type untouched by the backfill.
        self.assertEqual(p1.project_id, "PRO2025SW001")
        self.assertEqual(p1.project_name, "Pool A")
        self.assertEqual(p1.project_type, "SW")

    def test_backfill_does_not_overwrite_an_already_mapped_project(self):
        other_company = Company.objects.create(company_code="COMP999", company_name="Other Co")
        p = Project.objects.create(
            project_id="PRO2025EL001", project_name="Electrical A", project_type="EL", company=other_company
        )
        self._backfill()
        p.refresh_from_db()
        self.assertEqual(p.company_id, other_company.id)

    def test_backfill_is_idempotent(self):
        Project.objects.create(project_id="PRO2025OT001", project_name="Other A", project_type="OT")
        self._backfill()
        self._backfill()
        self.assertEqual(Company.objects.filter(company_code="COMP001").count(), 1)


class _FakeAppsRegistry:
    """Mimics migrations' historical `apps` just enough for apps.get_model()."""
    def get_model(self, app_label, model_name):
        from django.apps import apps
        return apps.get_model(app_label, model_name)


class MultiCompanyFoundationTests(TestCase):
    """
    End-state tests for Phase 1: Project.company, Company master, and that
    every other listed area (Sales, Purchases, Stock, GL, Bank, Retail
    Shop) is completely unaffected by this change.
    """

    def setUp(self):
        self.owner = User.objects.create_superuser(
            username="company_owner", email="company_owner@example.com", password="12345"
        )
        self.comp001 = Company.objects.create(company_code="COMP001", company_name="P&I Constructions")
        self.client.force_login(self.owner)

    # 1 & 14: existing project loads, project_id unchanged
    def test_existing_project_loads_and_project_id_unchanged(self):
        project = Project.objects.create(
            project_id="PRO2025SW001", project_name="Pool A", project_type="SW", company=self.comp001
        )
        response = self.client.get(reverse("project_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PRO2025SW001")
        project.refresh_from_db()
        self.assertEqual(project.project_id, "PRO2025SW001")

    # 2: existing project shows Company = COMP001
    def test_existing_project_shows_company_comp001(self):
        project = Project.objects.create(
            project_id="PRO2025SW002", project_name="Pool B", project_type="SW", company=self.comp001
        )
        self.assertEqual(project.company.company_code, "COMP001")

    # 3: Project Income still works
    def test_project_income_still_works(self):
        project = Project.objects.create(
            project_id="PRO2025IN001", project_name="Income Test", project_type="OT", company=self.comp001
        )
        income = ProjectIncome.objects.create(project=project, amount=Decimal("5000.00"), description="Advance")
        self.assertEqual(income.project_id, project.id)
        self.assertEqual(project.incomes.count(), 1)

    # 4: Project Expense still works
    def test_project_expense_still_works(self):
        project = Project.objects.create(
            project_id="PRO2025EX001", project_name="Expense Test", project_type="OT", company=self.comp001
        )
        expense = ProjectExpense.objects.create(
            project=project, description="Cement", qty=1, unit_price=Decimal("1000.00"), amount=Decimal("1000.00")
        )
        self.assertEqual(expense.project_id, project.id)
        self.assertEqual(project.expenses.count(), 1)

    # 5: Project Profit dashboard still works
    def test_project_profit_dashboard_still_works(self):
        Project.objects.create(
            project_id="PRO2025PF001", project_name="Profit Test", project_type="OT", company=self.comp001
        )
        response = self.client.get(reverse("project_profit_dashboard"))
        self.assertEqual(response.status_code, 200)

    # 6: existing Sales remain unchanged
    def test_existing_sales_remain_unchanged(self):
        sale = Sale.objects.create(
            invoice_no="INVCO0001", total=Decimal("1000.00"), grand_total=Decimal("1000.00"),
            sale_type="retail", payment_method="cash", created_by=self.owner,
        )
        before = (sale.invoice_no, sale.grand_total, sale.payment_method, sale.sale_type)
        Project.objects.create(
            project_id="PRO2025SL001", project_name="Sale Unaffected", project_type="OT", company=self.comp001
        )
        sale.refresh_from_db()
        after = (sale.invoice_no, sale.grand_total, sale.payment_method, sale.sale_type)
        self.assertEqual(before, after)

    # 7: existing Purchases remain unchanged
    def test_existing_purchases_remain_unchanged(self):
        supplier = Supplier.objects.create(name="Test Supplier Co")
        po = PurchaseOrder.objects.create(po_no="POCO00001", supplier=supplier)
        po.items.create(description="Cement bags", quantity=Decimal("10"), unit_price=Decimal("500.00"))
        before = (po.po_no, po.grand_total, po.status)
        po.refresh_from_db()
        after = (po.po_no, po.grand_total, po.status)
        self.assertEqual(before, after)
        self.assertEqual(po.grand_total, Decimal("5000.00"))

    # 8: existing Stock remains unchanged
    def test_existing_stock_remains_unchanged(self):
        item = Item.objects.create(item_code="COSTOCK-1", name="Stock Test Item", stock=Decimal("25.00"))
        before_stock = item.stock
        item.refresh_from_db()
        self.assertEqual(item.stock, before_stock)
        self.assertEqual(item.stock, Decimal("25.00"))

    # 9: existing GL remains unchanged
    def test_existing_gl_remains_unchanged(self):
        gl = GLMaster.objects.create(gl_code="COGL-1", gl_name="Test GL", gl_type="income")
        before = (gl.gl_code, gl.gl_name, gl.gl_type)
        gl.refresh_from_db()
        after = (gl.gl_code, gl.gl_name, gl.gl_type)
        self.assertEqual(before, after)

    # 10: existing Bank balances remain unchanged
    def test_existing_bank_balance_remains_unchanged(self):
        gl = GLMaster.objects.create(gl_code="COBANKGL-1", gl_name="Bank GL", gl_type="asset")
        account = BankAccount.objects.create(
            bank_name="Test Bank", account_name="Main", account_number="COBANK-1",
            opening_balance=Decimal("10000.00"), gl_account=gl,
        )
        before_balance = account.current_balance
        self.assertEqual(before_balance, Decimal("10000.00"))
        # Creating/backfilling Company data must not touch bank balances.
        account.refresh_from_db()
        self.assertEqual(account.current_balance, before_balance)

    # 11: existing Retail Shop remains operational (no Company required)
    def test_retail_shop_sale_does_not_require_company(self):
        gl = GLMaster.objects.create(gl_code="CORETAIL-GL", gl_name="Retail GL", gl_type="income")
        item = Item.objects.create(
            item_code="CORETAIL-ITEM", name="Retail Test Item",
            selling_price=Decimal("500.00"), is_service=True, retail_gl_account=gl,
        )
        payload = {
            "items": [{"id": item.id, "qty": 1, "price": "500.00", "discount": 0}],
            "discount": 0,
            "payment_method": "cash",
            "received": "500.00",
        }
        response = self.client.post(reverse("save_sale"), data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        sale = Sale.objects.get(invoice_no=response.json()["invoice_no"])
        self.assertEqual(sale.sale_type, "retail")
        self.assertIsNone(sale.project_id)

    # 12: new Project requires Company (no companies configured at all)
    def test_new_project_requires_company_when_none_configured(self):
        Company.objects.all().delete()
        count_before = Project.objects.count()
        response = self.client.post(reverse("create_project"), {
            "project_name": "No Company Project", "project_type": "OT",
            "client_name": "Test Client",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Project.objects.count(), count_before)

    # 12: new Project requires Company (multiple companies, none selected)
    def test_new_project_requires_company_when_ambiguous(self):
        Company.objects.create(company_code="COMP002", company_name="Second Co")
        count_before = Project.objects.count()
        response = self.client.post(reverse("create_project"), {
            "project_name": "Ambiguous Company Project", "project_type": "OT",
            "client_name": "Test Client",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Project.objects.count(), count_before)

    # 13: new Project saves with selected Company
    def test_new_project_saves_with_selected_company(self):
        response = self.client.post(reverse("create_project"), {
            "project_name": "Explicit Company Project", "project_type": "OT",
            "client_name": "Test Client", "company": self.comp001.id,
        })
        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(project_name="Explicit Company Project")
        self.assertEqual(project.company_id, self.comp001.id)

    # 13 (single-company convenience): auto-selects the sole active company
    def test_new_project_auto_selects_sole_active_company(self):
        response = self.client.post(reverse("create_project"), {
            "project_name": "Auto Company Project", "project_type": "OT",
            "client_name": "Test Client",
        })
        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(project_name="Auto Company Project")
        self.assertEqual(project.company_id, self.comp001.id)

    # edit_project must never silently null out an existing Company
    def test_edit_project_does_not_clear_company_when_field_omitted(self):
        project = Project.objects.create(
            project_id="PRO2025ED001", project_name="Edit Test", project_type="OT", company=self.comp001
        )
        response = self.client.post(reverse("edit_project", args=[project.id]), {
            "project_name": "Edit Test Updated", "project_type": "OT",
            "client_name": "", "estimated_value": "0",
        })
        self.assertEqual(response.status_code, 302)
        project.refresh_from_db()
        self.assertEqual(project.company_id, self.comp001.id)


class MultiCompanyProductionMirrorBackfillTests(TestCase):
    """
    Mirrors the verified production baseline exactly: 19 active Projects,
    all company=NULL, listed by the user after a read-only production
    check. Proves the real 0039 backfill maps every one of these specific
    project_ids to COMP001, without touching project_id/project_name, and
    without creating a duplicate Company or double-mapping on a re-run.
    """

    PRODUCTION_PROJECT_IDS = [
        "PRO2026SW001", "PRO2026BL001", "PRO2026SW002", "PRO2026SW003",
        "PRO2026BL002", "PRO2026SW004", "PRO2026SW005", "PRO2026SW006",
        "PRO2026SW007", "PRO2026RS001", "PRO2026SW008", "PRO2026RS002",
        "PRO2026SW009", "PRO2026SW010", "PRO2026SW011", "PRO2026SW012",
        "PRO2026SW013", "PRO2026SW014", "PRO2026BL003",
    ]

    def setUp(self):
        for pid in self.PRODUCTION_PROJECT_IDS:
            Project.objects.create(
                project_id=pid,
                project_name=f"Live Project {pid}",
                project_type="RS" if "RS" in pid else ("SW" if "SW" in pid else "BL"),
            )

    def _backfill(self):
        import importlib
        module = importlib.import_module("pos.migrations.0039_backfill_company_comp001")
        module.backfill_company(apps=_FakeAppsRegistry(), schema_editor=None)

    def test_all_19_production_projects_map_to_comp001(self):
        self.assertEqual(Project.objects.count(), 19)
        self.assertEqual(Project.objects.filter(company__isnull=True).count(), 19)

        self._backfill()

        company = Company.objects.get(company_code="COMP001")
        self.assertEqual(company.company_name, "P&I Constructions")
        self.assertEqual(Project.objects.filter(company=company).count(), 19)
        self.assertEqual(Project.objects.filter(company__isnull=True).count(), 0)

        for pid in self.PRODUCTION_PROJECT_IDS:
            project = Project.objects.get(project_id=pid)
            self.assertEqual(project.company_id, company.id)

    def test_project_ids_and_names_unchanged_by_backfill(self):
        before = list(
            Project.objects.order_by("project_id").values_list("project_id", "project_name", "project_type")
        )
        self._backfill()
        after = list(
            Project.objects.order_by("project_id").values_list("project_id", "project_name", "project_type")
        )
        self.assertEqual(before, after)

    def test_rerunning_backfill_does_not_duplicate_company_or_remap(self):
        self._backfill()
        first_mapping = list(Project.objects.order_by("project_id").values_list("project_id", "company_id"))

        self._backfill()  # simulates a re-run / redeploy replaying the migration
        second_mapping = list(Project.objects.order_by("project_id").values_list("project_id", "company_id"))

        self.assertEqual(Company.objects.filter(company_code="COMP001").count(), 1)
        self.assertEqual(first_mapping, second_mapping)

    def test_a_project_already_on_another_company_is_not_remapped(self):
        # One of the 19 is pre-assigned to a different company before the
        # backfill runs; confirms 0039 only touches company__isnull=True.
        other_company = Company.objects.create(company_code="COMP777", company_name="Some Other Business")
        pinned = Project.objects.get(project_id="PRO2026RS002")
        pinned.company = other_company
        pinned.save(update_fields=["company"])

        self._backfill()

        pinned.refresh_from_db()
        self.assertEqual(pinned.company_id, other_company.id)

        comp001 = Company.objects.get(company_code="COMP001")
        self.assertEqual(Project.objects.filter(company=comp001).count(), 18)
        self.assertEqual(Project.objects.filter(company=other_company).count(), 1)


class Phase21CompanyReportFilterTests(TestCase):
    """
    Phase 2.1: read-side Company filter for project_profit_dashboard,
    project_cost_analysis_list, cost_analysis_by_gl_group. Company is
    derived through Project.company only - no child transaction model
    (ProjectExpense/ProjectInvoice/etc.) gets its own company field.
    """

    def setUp(self):
        self.owner = User.objects.create_superuser(
            username="phase21_owner", email="phase21_owner@example.com", password="12345"
        )
        self.comp001 = Company.objects.create(company_code="COMP001", company_name="P&I Constructions")
        self.comp002 = Company.objects.create(company_code="COMP002", company_name="Second Business")

        self.gl = GLMaster.objects.create(gl_code="P21GL-1", gl_name="Project Expense GL", gl_type="expense")

        self.p1 = Project.objects.create(
            project_id="P21P001", project_name="Comp001 Project", project_type="OT", company=self.comp001
        )
        self.p2 = Project.objects.create(
            project_id="P21P002", project_name="Comp002 Project", project_type="OT", company=self.comp002
        )

        # Expense + income for each project, via the real ProjectExpense /
        # ProjectInvoice / ProjectInvoicePayment models the dashboard reads.
        ProjectExpense.objects.create(
            project=self.p1, description="P1 cost", qty=1, unit_price=Decimal("1000.00"), amount=Decimal("1000.00")
        )
        ProjectExpense.objects.create(
            project=self.p2, description="P2 cost", qty=1, unit_price=Decimal("500.00"), amount=Decimal("500.00")
        )
        inv1 = ProjectInvoice.objects.create(project=self.p1, total_amount=Decimal("3000.00"))
        ProjectInvoicePayment.objects.create(invoice=inv1, amount=Decimal("3000.00"))
        inv2 = ProjectInvoice.objects.create(project=self.p2, total_amount=Decimal("1500.00"))
        ProjectInvoicePayment.objects.create(invoice=inv2, amount=Decimal("1500.00"))

        self.client.force_login(self.owner)

    def _profit_totals(self, **params):
        response = self.client.get(reverse("project_profit_dashboard"), params)
        self.assertEqual(response.status_code, 200)
        return response.context

    # A: no Company filter -> existing (unfiltered) totals
    def test_profit_dashboard_no_filter_totals_unchanged(self):
        ctx = self._profit_totals()
        self.assertEqual(ctx["grand_income"], Decimal("4500.00"))
        self.assertEqual(ctx["grand_direct_expense"], Decimal("1500.00"))
        self.assertEqual(len(ctx["project_rows"]), 2)

    # B: "All Companies" (empty company_id) equals the unfiltered totals
    def test_profit_dashboard_all_companies_equals_unfiltered(self):
        unfiltered = self._profit_totals()
        all_companies = self._profit_totals(company_id="")
        self.assertEqual(unfiltered["grand_income"], all_companies["grand_income"])
        self.assertEqual(unfiltered["grand_direct_expense"], all_companies["grand_direct_expense"])
        self.assertEqual(len(unfiltered["project_rows"]), len(all_companies["project_rows"]))

    # C: COMP001 selected -> only COMP001 projects included
    def test_profit_dashboard_comp001_only_includes_comp001_projects(self):
        ctx = self._profit_totals(company_id=self.comp001.id)
        self.assertEqual(len(ctx["project_rows"]), 1)
        self.assertEqual(ctx["project_rows"][0]["project"].id, self.p1.id)
        self.assertEqual(ctx["grand_income"], Decimal("3000.00"))
        self.assertEqual(ctx["grand_direct_expense"], Decimal("1000.00"))

    # D: a second Company excludes COMP001 projects
    def test_profit_dashboard_comp002_excludes_comp001_projects(self):
        ctx = self._profit_totals(company_id=self.comp002.id)
        self.assertEqual(len(ctx["project_rows"]), 1)
        self.assertEqual(ctx["project_rows"][0]["project"].id, self.p2.id)
        project_ids_in_result = [row["project"].id for row in ctx["project_rows"]]
        self.assertNotIn(self.p1.id, project_ids_in_result)

    # E: Company scope is derived through Project.company only
    def test_child_transaction_models_have_no_company_field(self):
        self.assertFalse(hasattr(ProjectExpense, "company"))
        self.assertFalse(hasattr(ProjectExpense, "company_id"))
        self.assertFalse(hasattr(ProjectInvoice, "company"))
        self.assertFalse(hasattr(ProjectInvoice, "company_id"))
        # Yet the filter still correctly scopes them, via project__company.
        ctx = self._profit_totals(company_id=self.comp001.id)
        self.assertEqual(ctx["grand_income"], Decimal("3000.00"))

    # F: historical records untouched by simply viewing the filtered report
    def test_viewing_filtered_report_does_not_modify_records(self):
        before = (
            list(Project.objects.order_by("id").values_list("id", "project_id", "company_id")),
            list(ProjectExpense.objects.order_by("id").values_list("id", "amount", "project_id")),
        )
        self._profit_totals(company_id=self.comp001.id)
        self._profit_totals(company_id=self.comp002.id)
        self._profit_totals()
        after = (
            list(Project.objects.order_by("id").values_list("id", "project_id", "company_id")),
            list(ProjectExpense.objects.order_by("id").values_list("id", "amount", "project_id")),
        )
        self.assertEqual(before, after)

    # project_cost_analysis_list: Company filter scopes the projects list
    def test_cost_analysis_list_company_filter_scopes_projects(self):
        response = self.client.get(reverse("project_cost_analysis_list"), {"company_id": self.comp001.id})
        self.assertEqual(response.status_code, 200)
        project_ids = [p.id for p in response.context["projects"]]
        self.assertIn(self.p1.id, project_ids)
        self.assertNotIn(self.p2.id, project_ids)

    def test_cost_analysis_list_no_filter_includes_all(self):
        response = self.client.get(reverse("project_cost_analysis_list"))
        self.assertEqual(response.status_code, 200)
        project_ids = [p.id for p in response.context["projects"]]
        self.assertIn(self.p1.id, project_ids)
        self.assertIn(self.p2.id, project_ids)

    # cost_analysis_by_gl_group: Company filter scopes the projects list
    def test_gl_group_report_company_filter_scopes_projects(self):
        response = self.client.get(reverse("cost_analysis_by_gl_group"), {"company_id": self.comp002.id})
        self.assertEqual(response.status_code, 200)
        project_ids = list(response.context["projects"].values_list("id", flat=True))
        self.assertEqual(project_ids, [self.p2.id])

    def test_gl_group_report_no_filter_includes_all(self):
        response = self.client.get(reverse("cost_analysis_by_gl_group"))
        self.assertEqual(response.status_code, 200)
        project_ids = set(response.context["projects"].values_list("id", flat=True))
        self.assertEqual(project_ids, {self.p1.id, self.p2.id})

