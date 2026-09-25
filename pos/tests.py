from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import (
    BankAccount,
    BankTransaction,
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
    ProjectInvoice,
    ProjectInvoicePayment,
    CashAdjustment,
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

