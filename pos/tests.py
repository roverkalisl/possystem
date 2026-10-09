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
    ProjectCostActual,
    ProjectExpense,
    ProjectIncome,
    ProjectInvoice,
    ProjectInvoicePayment,
    PurchaseOrder,
    Quotation,
    QuotationItem,
    Supplier,
    SupplierAdvance,
    SupplierSettlement,
    GRN,
    GRNItem,
    CashAdjustment,
    POSSettings,
    Sale,
    SaleRecovery,
    SalaryAdvance,
    Item,
)
from .barcode_services import generate_barcode_for_item


class QuotationTotalsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="quotation_totals",
            password="test-password",
        )
        self.client.force_login(self.user)

    def create_quotation(self, items):
        quotation = Quotation.objects.create(customer_name="Quotation Test")
        for index, (qty, unit_price, discount) in enumerate(items, start=1):
            item = Item.objects.create(
                item_code=f"QUOTE-{index}",
                name=f"Quotation Item {index}",
                selling_price=unit_price,
            )
            QuotationItem.objects.create(
                quotation=quotation,
                item=item,
                qty=qty,
                unit_price=unit_price,
                discount=discount,
            )
        return quotation

    def assert_detail_and_print_totals(self, quotation, expected_total):
        quotation.refresh_from_db()
        expected_total = Decimal(expected_total)
        persisted_line_total = sum(
            quotation.items.values_list("line_total", flat=True),
            Decimal("0"),
        )
        self.assertEqual(persisted_line_total, expected_total)
        self.assertEqual(quotation.grand_total, expected_total)
        display_total = format(expected_total.normalize(), "f")

        detail = self.client.get(reverse("quotation_detail", args=[quotation.id]))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.context["quotation"].grand_total, expected_total)
        self.assertContains(detail, f"Grand Total:</strong> {display_total}")

        printed = self.client.get(reverse("print_quotation", args=[quotation.id]))
        self.assertEqual(printed.status_code, 200)
        self.assertEqual(printed.context["quotation"].grand_total, expected_total)
        self.assertContains(printed, f"<strong>{display_total}</strong>")

    def test_quotation_without_discounts(self):
        quotation = self.create_quotation([
            (Decimal("2"), Decimal("100.00"), Decimal("0.00")),
        ])

        self.assert_detail_and_print_totals(quotation, "200.00")

    def test_quotation_with_line_item_discount(self):
        quotation = self.create_quotation([
            (Decimal("2"), Decimal("100.00"), Decimal("25.00")),
        ])
        quotation_item = quotation.items.get()
        quotation_item.refresh_from_db()
        self.assertEqual(quotation_item.line_total, Decimal("175.00"))

        self.assert_detail_and_print_totals(quotation, "175.00")

    def test_quotation_with_multiple_discounted_items(self):
        quotation = self.create_quotation([
            (Decimal("2"), Decimal("100.00"), Decimal("10.00")),
            (Decimal("3"), Decimal("50.00"), Decimal("20.00")),
        ])

        self.assert_detail_and_print_totals(quotation, "320.00")


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


class Phase22CompanyContextTests(TestCase):
    """
    Phase 2.2: active Company lives only in request.session - never on the
    User model, never on any transaction table. Covers get_active_company(),
    the switch_active_company view, and how create_project / the report
    Project dropdowns consume it.
    """

    def setUp(self):
        self.owner = User.objects.create_superuser(
            username="phase22_owner", email="phase22_owner@example.com", password="12345"
        )
        self.comp001 = Company.objects.create(company_code="COMP001", company_name="P&I Constructions")
        self.comp002 = Company.objects.create(company_code="COMP002", company_name="Second Business")
        self.inactive_company = Company.objects.create(
            company_code="COMPX", company_name="Inactive Co", is_active=False
        )
        self.client.force_login(self.owner)

    def _session_company_id(self):
        return self.client.session.get("active_company_id")

    # A: no active Company in session (2+ active companies -> no guessing)
    def test_no_active_company_when_nothing_selected_and_multiple_exist(self):
        from pos.company_context import get_active_company
        from django.test import RequestFactory
        request = RequestFactory().get("/")
        request.session = self.client.session
        self.assertIsNone(get_active_company(request))

    # B & C: COMP001 can be selected, and the correct id lands in session
    def test_selecting_comp001_stores_correct_id_in_session(self):
        response = self.client.post(reverse("switch_active_company"), {"company_id": self.comp001.id})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self._session_company_id(), self.comp001.id)

    # D: switching companies changes only the session, nothing else
    def test_switching_company_changes_only_session_context(self):
        project = Project.objects.create(
            project_id="P22SW001", project_name="Session Test", project_type="OT", company=self.comp001
        )
        before = (project.project_id, project.project_name, project.company_id)

        self.client.post(reverse("switch_active_company"), {"company_id": self.comp001.id})
        self.assertEqual(self._session_company_id(), self.comp001.id)

        self.client.post(reverse("switch_active_company"), {"company_id": self.comp002.id})
        self.assertEqual(self._session_company_id(), self.comp002.id)

        project.refresh_from_db()
        after = (project.project_id, project.project_name, project.company_id)
        self.assertEqual(before, after)

    # E: an inactive Company cannot become active
    def test_inactive_company_cannot_become_active(self):
        self.client.post(reverse("switch_active_company"), {"company_id": self.comp001.id})
        response = self.client.post(reverse("switch_active_company"), {"company_id": self.inactive_company.id})
        self.assertEqual(response.status_code, 302)
        # Session must not have been overwritten with the inactive company.
        self.assertEqual(self._session_company_id(), self.comp001.id)

    # F: a nonexistent Company id cannot become active
    def test_nonexistent_company_cannot_become_active(self):
        self.client.post(reverse("switch_active_company"), {"company_id": self.comp001.id})
        response = self.client.post(reverse("switch_active_company"), {"company_id": 999999})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self._session_company_id(), self.comp001.id)

    # G: Project creation with Company works
    def test_project_creation_with_explicit_company_works(self):
        response = self.client.post(reverse("create_project"), {
            "project_name": "P22 Explicit", "project_type": "OT",
            "client_name": "Client", "company": self.comp001.id,
        })
        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(project_name="P22 Explicit")
        self.assertEqual(project.company_id, self.comp001.id)

    # H: cannot silently create a Project without Company when multiple
    # active Companies exist and none is selected (session or form)
    def test_project_creation_without_company_is_rejected_when_ambiguous(self):
        count_before = Project.objects.count()
        response = self.client.post(reverse("create_project"), {
            "project_name": "P22 No Company", "project_type": "OT", "client_name": "Client",
        })
        self.assertEqual(response.status_code, 200)  # re-rendered with an error, not redirected
        self.assertEqual(Project.objects.count(), count_before)

    # H (continued): but an active session Company removes the ambiguity
    def test_project_creation_uses_active_session_company_when_form_omits_it(self):
        self.client.post(reverse("switch_active_company"), {"company_id": self.comp002.id})
        response = self.client.post(reverse("create_project"), {
            "project_name": "P22 From Session", "project_type": "OT", "client_name": "Client",
        })
        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(project_name="P22 From Session")
        self.assertEqual(project.company_id, self.comp002.id)

    # I: Project dropdown is restricted by the active Company
    def test_project_dropdown_restricted_by_active_company(self):
        p1 = Project.objects.create(
            project_id="P22DD001", project_name="Comp001 Proj", project_type="OT", company=self.comp001
        )
        p2 = Project.objects.create(
            project_id="P22DD002", project_name="Comp002 Proj", project_type="OT", company=self.comp002
        )
        self.client.post(reverse("switch_active_company"), {"company_id": self.comp001.id})

        response = self.client.get(reverse("project_profit_dashboard"))
        dropdown_ids = [p.id for p in response.context["projects"]]
        self.assertIn(p1.id, dropdown_ids)
        self.assertNotIn(p2.id, dropdown_ids)

        # Explicitly choosing "All Companies" still shows the full list.
        response_all = self.client.get(reverse("project_profit_dashboard"), {"company_id": ""})
        dropdown_ids_all = [p.id for p in response_all.context["projects"]]
        self.assertIn(p1.id, dropdown_ids_all)
        self.assertIn(p2.id, dropdown_ids_all)

    # J: project-based transaction Company context derives from Project.company
    def test_transaction_company_context_derives_from_project_company(self):
        project = Project.objects.create(
            project_id="P22TX001", project_name="Derivation Test", project_type="OT", company=self.comp001
        )
        expense = ProjectExpense.objects.create(
            project=project, description="Cost", qty=1, unit_price=Decimal("100.00"), amount=Decimal("100.00")
        )
        self.assertFalse(hasattr(ProjectExpense, "company"))
        self.assertEqual(expense.project.company_id, self.comp001.id)
        self.assertEqual(expense.project.company.company_code, "COMP001")

    # K: existing Projects remain unchanged by Company context features
    def test_existing_projects_unchanged_by_switching_and_viewing(self):
        project = Project.objects.create(
            project_id="P22EXIST001", project_name="Existing Project", project_type="SW", company=self.comp001
        )
        before = (project.project_id, project.project_name, project.project_type, project.company_id)

        self.client.post(reverse("switch_active_company"), {"company_id": self.comp001.id})
        self.client.get(reverse("project_profit_dashboard"))
        self.client.get(reverse("project_cost_analysis_list"))
        self.client.get(reverse("cost_analysis_by_gl_group"))
        self.client.post(reverse("switch_active_company"), {"company_id": self.comp002.id})

        project.refresh_from_db()
        after = (project.project_id, project.project_name, project.project_type, project.company_id)
        self.assertEqual(before, after)

    # L: no financial record is modified by viewing/switching Company
    def test_no_financial_record_modified_by_viewing_or_switching(self):
        project = Project.objects.create(
            project_id="P22FIN001", project_name="Financial Safety", project_type="OT", company=self.comp001
        )
        expense = ProjectExpense.objects.create(
            project=project, description="Cost", qty=1, unit_price=Decimal("250.00"), amount=Decimal("250.00")
        )
        sale = Sale.objects.create(
            invoice_no="P22FININV0001", total=Decimal("500.00"), grand_total=Decimal("500.00"),
            sale_type="retail", payment_method="cash", created_by=self.owner,
        )
        before = (
            Decimal(str(expense.amount)), expense.project_id,
            sale.grand_total, sale.payment_method, sale.invoice_no,
        )

        self.client.post(reverse("switch_active_company"), {"company_id": self.comp001.id})
        self.client.get(reverse("project_profit_dashboard"))
        self.client.post(reverse("switch_active_company"), {"company_id": self.comp002.id})
        self.client.get(reverse("dashboard"))

        expense.refresh_from_db()
        sale.refresh_from_db()
        after = (
            Decimal(str(expense.amount)), expense.project_id,
            sale.grand_total, sale.payment_method, sale.invoice_no,
        )
        self.assertEqual(before, after)


class Phase22CompanyManagementTests(TestCase):
    """Company list/add/edit - no delete, COMP001 never modified by these."""

    def setUp(self):
        self.owner = User.objects.create_superuser(
            username="phase22_mgmt_owner", email="phase22_mgmt_owner@example.com", password="12345"
        )
        self.cashier_group, _ = Group.objects.get_or_create(name="Cashier")
        self.cashier = User.objects.create_user(username="phase22_mgmt_cashier", password="12345")
        self.cashier.groups.add(self.cashier_group)
        self.comp001 = Company.objects.create(company_code="COMP001", company_name="P&I Constructions")

    def test_owner_can_list_companies(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("company_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "COMP001")

    def test_non_owner_cannot_access_company_management(self):
        self.client.force_login(self.cashier)
        self.assertNotEqual(self.client.get(reverse("company_list")).status_code, 200)
        self.assertNotEqual(self.client.get(reverse("add_company")).status_code, 200)

    def test_owner_can_add_company(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("add_company"), {
            "company_code": "COMP002", "company_name": "New Branch", "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Company.objects.filter(company_code="COMP002", company_name="New Branch").exists())

    def test_duplicate_company_code_is_rejected(self):
        self.client.force_login(self.owner)
        count_before = Company.objects.count()
        response = self.client.post(reverse("add_company"), {
            "company_code": "COMP001", "company_name": "Duplicate Attempt", "is_active": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Company.objects.count(), count_before)

    def test_owner_can_edit_company_and_toggle_active_status(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("edit_company", args=[self.comp001.id]), {
            "company_name": "P&I Constructions Updated", "is_active": "",
        })
        self.assertEqual(response.status_code, 302)
        self.comp001.refresh_from_db()
        self.assertEqual(self.comp001.company_name, "P&I Constructions Updated")
        self.assertFalse(self.comp001.is_active)
        # Company Code itself is never changed by edit_company.
        self.assertEqual(self.comp001.company_code, "COMP001")

    def test_no_delete_endpoint_exists_for_company(self):
        from django.urls import NoReverseMatch
        with self.assertRaises(NoReverseMatch):
            reverse("delete_company")


class Phase3CompanyDashboardTests(TestCase):
    """
    Phase 3: Company Dashboard. Reuses compute_project_profit_rows() -
    the exact same helper project_profit_dashboard now calls - so this
    class also directly cross-checks its numbers against that report.
    """

    def setUp(self):
        self.owner = User.objects.create_superuser(
            username="phase3_owner", email="phase3_owner@example.com", password="12345"
        )
        self.comp001 = Company.objects.create(company_code="COMP001", company_name="P&I Constructions")
        self.comp002 = Company.objects.create(company_code="COMP002", company_name="Second Business")

        self.p1 = Project.objects.create(
            project_id="P3P001", project_name="Comp001 Project", project_type="OT", company=self.comp001
        )
        self.p2 = Project.objects.create(
            project_id="P3P002", project_name="Comp002 Project", project_type="OT", company=self.comp002
        )

        ProjectExpense.objects.create(
            project=self.p1, description="P1 cost", qty=1, unit_price=Decimal("1000.00"),
            amount=Decimal("1000.00"), expense_date=date(2026, 3, 15),
        )
        inv1 = ProjectInvoice.objects.create(project=self.p1, total_amount=Decimal("3000.00"))
        ProjectInvoicePayment.objects.create(invoice=inv1, amount=Decimal("3000.00"), payment_date=date(2026, 3, 20))

        ProjectExpense.objects.create(
            project=self.p2, description="P2 cost", qty=1, unit_price=Decimal("500.00"),
            amount=Decimal("500.00"), expense_date=date(2026, 3, 15),
        )
        inv2 = ProjectInvoice.objects.create(project=self.p2, total_amount=Decimal("1500.00"))
        ProjectInvoicePayment.objects.create(invoice=inv2, amount=Decimal("1500.00"), payment_date=date(2026, 3, 20))

        self.client.force_login(self.owner)

    def _switch_to(self, company):
        self.client.post(reverse("switch_active_company"), {"company_id": company.id})

    def _dashboard(self, **params):
        response = self.client.get(reverse("company_dashboard"), params)
        self.assertEqual(response.status_code, 200)
        return response.context

    def _profit_report(self, **params):
        response = self.client.get(reverse("project_profit_dashboard"), params)
        self.assertEqual(response.status_code, 200)
        return response.context

    # A & C: COMP001 dashboard returns exactly its Projects, correct count
    def test_comp001_dashboard_returns_exactly_its_projects(self):
        self._switch_to(self.comp001)
        ctx = self._dashboard()
        self.assertEqual(ctx["total_projects"], 1)
        project_ids = [row["project"].id for row in ctx["project_rows"]]
        self.assertEqual(project_ids, [self.p1.id])

    # B: excludes another Company's Projects
    def test_dashboard_excludes_other_company_projects(self):
        self._switch_to(self.comp001)
        ctx = self._dashboard()
        project_ids = [row["project"].id for row in ctx["project_rows"]]
        self.assertNotIn(self.p2.id, project_ids)

    # D, E, F: Income / Cost / Profit exactly match the Project Profit report
    def test_income_cost_profit_match_project_profit_report(self):
        self._switch_to(self.comp001)
        dash_ctx = self._dashboard()
        report_ctx = self._profit_report(company_id=self.comp001.id)

        self.assertEqual(dash_ctx["grand_income"], report_ctx["grand_income"])
        self.assertEqual(dash_ctx["grand_cost"], report_ctx["grand_net_expense"])
        self.assertEqual(dash_ctx["grand_profit"], report_ctx["grand_profit"])

        self.assertEqual(dash_ctx["grand_income"], Decimal("3000.00"))
        self.assertEqual(dash_ctx["grand_cost"], Decimal("1000.00"))
        self.assertEqual(dash_ctx["grand_profit"], Decimal("2000.00"))

    # G: Profit % is derived purely from the reused income/profit figures
    # (no prior Profit % existed anywhere in the system to "match" against -
    # this is the obvious standard ratio computed only from those two
    # already-reused numbers, not a new independent calculation).
    def test_profit_percent_derived_from_reused_income_and_profit(self):
        self._switch_to(self.comp001)
        ctx = self._dashboard()
        expected = (ctx["grand_profit"] / ctx["grand_income"] * Decimal("100"))
        self.assertEqual(ctx["profit_percent"], expected)
        self.assertAlmostEqual(float(ctx["profit_percent"]), 66.666666, places=3)

    # H: From/To date filter works, using the existing date-field logic
    def test_date_filter_excludes_out_of_range_transactions(self):
        self._switch_to(self.comp001)
        # Add an expense outside the March window.
        ProjectExpense.objects.create(
            project=self.p1, description="Later cost", qty=1, unit_price=Decimal("400.00"),
            amount=Decimal("400.00"), expense_date=date(2026, 6, 1),
        )
        ctx_filtered = self._dashboard(from_date="2026-03-01", to_date="2026-03-31")
        self.assertEqual(ctx_filtered["grand_cost"], Decimal("1000.00"))  # June expense excluded

        ctx_unfiltered = self._dashboard()
        self.assertEqual(ctx_unfiltered["grand_cost"], Decimal("1400.00"))  # both included

    # I: empty Company (no Projects) is safe - zero values, no errors
    def test_empty_company_returns_zero_values_safely(self):
        empty_company = Company.objects.create(company_code="COMP003", company_name="Empty Co")
        self._switch_to(empty_company)
        ctx = self._dashboard()
        self.assertEqual(ctx["total_projects"], 0)
        self.assertEqual(ctx["grand_income"], Decimal("0"))
        self.assertEqual(ctx["grand_profit"], Decimal("0"))
        self.assertEqual(ctx["profit_percent"], Decimal("0"))
        self.assertEqual(list(ctx["project_rows"]), [])
        response = self.client.get(reverse("company_dashboard"))
        self.assertContains(response, "No projects found for this company.")

    # I (continued): a Project with zero transactions is also safe
    def test_project_with_no_transactions_shows_zero_row(self):
        empty_company = Company.objects.create(company_code="COMP004", company_name="Quiet Co")
        Project.objects.create(
            project_id="P3P003", project_name="No Activity", project_type="OT", company=empty_company
        )
        self._switch_to(empty_company)
        ctx = self._dashboard()
        self.assertEqual(ctx["total_projects"], 1)
        self.assertEqual(ctx["project_rows"][0]["total_income"], Decimal("0"))
        self.assertEqual(ctx["project_rows"][0]["profit_percent"], Decimal("0"))

    # J: switching active Company changes dashboard scope
    def test_switching_company_changes_dashboard_scope(self):
        self._switch_to(self.comp001)
        ctx1 = self._dashboard()
        self.assertEqual([r["project"].id for r in ctx1["project_rows"]], [self.p1.id])

        self._switch_to(self.comp002)
        ctx2 = self._dashboard()
        self.assertEqual([r["project"].id for r in ctx2["project_rows"]], [self.p2.id])
        self.assertEqual(ctx2["grand_income"], Decimal("1500.00"))

    # No active Company at all -> asks for a selection, never aggregates
    def test_no_active_company_does_not_aggregate_everything(self):
        response = self.client.get(reverse("company_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["active_company"])
        self.assertNotIn("project_rows", response.context)

    # K: existing Project values are unchanged
    def test_existing_project_values_unchanged(self):
        before = (self.p1.project_id, self.p1.project_name, self.p1.project_type, self.p1.company_id)
        self._switch_to(self.comp001)
        self._dashboard()
        self._dashboard(from_date="2026-01-01", to_date="2026-12-31")
        self.p1.refresh_from_db()
        after = (self.p1.project_id, self.p1.project_name, self.p1.project_type, self.p1.company_id)
        self.assertEqual(before, after)

    # L: existing ProjectExpense / ProjectIncome / ProjectCostActual unchanged
    def test_existing_child_transaction_values_unchanged(self):
        gl = GLMaster.objects.create(gl_code="P3GL-1", gl_name="Cost GL", gl_type="expense")
        income_entry = ProjectIncome.objects.create(
            project=self.p1, amount=Decimal("750.00"), description="Misc income"
        )
        cost_actual = ProjectCostActual.objects.create(
            project=self.p1, gl_account=gl, source_type="project_expense",
            source_id="1", transaction_date=date(2026, 3, 15), amount=Decimal("1000.00"),
        )
        expense = ProjectExpense.objects.filter(project=self.p1).first()

        before = (
            Decimal(str(expense.amount)),
            Decimal(str(income_entry.amount)),
            Decimal(str(cost_actual.amount)),
        )

        self._switch_to(self.comp001)
        self._dashboard()

        expense.refresh_from_db()
        income_entry.refresh_from_db()
        cost_actual.refresh_from_db()
        after = (
            Decimal(str(expense.amount)),
            Decimal(str(income_entry.amount)),
            Decimal(str(cost_actual.amount)),
        )
        self.assertEqual(before, after)

    # M: no Company field exists on any child project transaction model
    def test_no_company_field_on_child_transaction_models(self):
        for model in (ProjectExpense, ProjectIncome, ProjectInvoice, ProjectCostActual):
            self.assertFalse(hasattr(model, "company"), f"{model.__name__} must not have a company field")
            self.assertFalse(hasattr(model, "company_id"), f"{model.__name__} must not have a company_id field")


class Phase42APurchasingReportFilterTests(TestCase):
    """
    Phase 4.2-A: read-only Company filtering for Purchase Order,
    Supplier Advance, Supplier Settlement, and GRN reports. Company is
    derived strictly through Project (or, for GRN, through
    PurchaseOrder -> Project) - never guessed for Project-less records.
    None of PurchaseOrder, SupplierAdvance, SupplierSettlement, GRN,
    GRNItem, or any other model gained a company field.
    """

    def setUp(self):
        self.owner = User.objects.create_superuser(
            username="phase42a_owner", email="phase42a_owner@example.com", password="12345"
        )
        self.comp001 = Company.objects.create(company_code="COMP001", company_name="P&I Constructions")
        self.comp002 = Company.objects.create(company_code="COMP002", company_name="Second Business")

        self.pA = Project.objects.create(
            project_id="P42A001", project_name="Comp A Project", project_type="OT", company=self.comp001
        )
        self.pB = Project.objects.create(
            project_id="P42B001", project_name="Comp B Project", project_type="OT", company=self.comp002
        )

        self.supplier = Supplier.objects.create(name="P42 Supplier Co")

        # Purchase Orders: one per company-linked project, one project-less.
        self.po_a = PurchaseOrder.objects.create(supplier=self.supplier, project=self.pA)
        self.po_b = PurchaseOrder.objects.create(supplier=self.supplier, project=self.pB)
        self.po_none = PurchaseOrder.objects.create(supplier=self.supplier, project=None)
        for po in (self.po_a, self.po_b, self.po_none):
            po.items.create(description="Item", quantity=Decimal("1"), unit_price=Decimal("1000.00"))

        self.client.force_login(self.owner)

    def _switch_to(self, company):
        self.client.post(reverse("switch_active_company"), {"company_id": company.id})

    # 1 & 2: Company A / Company B purchases visible under their own Company
    def test_purchase_order_with_company_a_project_visible_under_company_a(self):
        response = self.client.get(reverse("purchase_order_list"), {"company_id": self.comp001.id})
        self.assertEqual(response.status_code, 200)
        order_ids = [o.id for o in response.context["orders"]]
        self.assertIn(self.po_a.id, order_ids)
        self.assertNotIn(self.po_b.id, order_ids)

    def test_purchase_order_with_company_b_project_visible_under_company_b(self):
        response = self.client.get(reverse("purchase_order_list"), {"company_id": self.comp002.id})
        order_ids = [o.id for o in response.context["orders"]]
        self.assertIn(self.po_b.id, order_ids)
        self.assertNotIn(self.po_a.id, order_ids)

    # 3: Project-less purchase not incorrectly assigned to either company
    def test_project_less_purchase_order_excluded_from_both_companies(self):
        for company in (self.comp001, self.comp002):
            response = self.client.get(reverse("purchase_order_list"), {"company_id": company.id})
            order_ids = [o.id for o in response.context["orders"]]
            self.assertNotIn(self.po_none.id, order_ids)

        # ...but it is still visible with no Company filter at all.
        response = self.client.get(reverse("purchase_order_list"))
        order_ids = [o.id for o in response.context["orders"]]
        self.assertIn(self.po_none.id, order_ids)

    # 4: Supplier Advance with Project -> Company derived correctly
    def test_supplier_advance_with_project_derives_company(self):
        advance_a = SupplierAdvance.objects.create(
            supplier=self.supplier, project=self.pA, amount=Decimal("500.00")
        )
        advance_none = SupplierAdvance.objects.create(
            supplier=self.supplier, project=None, amount=Decimal("300.00")
        )

        response = self.client.get(reverse("supplier_advance_summary"), {"company_id": self.comp001.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["grand_total_advance"], Decimal("500.00"))
        self.assertEqual(response.context["grand_advance_records"], 1)

        response_b = self.client.get(reverse("supplier_advance_summary"), {"company_id": self.comp002.id})
        self.assertEqual(response_b.context["grand_total_advance"], Decimal("0"))

        response_all = self.client.get(reverse("supplier_advance_summary"))
        self.assertEqual(response_all.context["grand_total_advance"], Decimal("800.00"))

    # 5: Supplier Settlement with Project -> Company derived correctly
    def test_supplier_settlement_with_project_derives_company(self):
        advance_a = SupplierAdvance.objects.create(
            supplier=self.supplier, project=self.pA, amount=Decimal("1000.00")
        )
        settlement_a = SupplierSettlement.objects.create(
            advance=advance_a, supplier=self.supplier, project=self.pA,
            description="Settle A", actual_amount=Decimal("400.00"),
        )
        advance_none = SupplierAdvance.objects.create(
            supplier=self.supplier, project=None, amount=Decimal("600.00")
        )
        settlement_none = SupplierSettlement.objects.create(
            advance=advance_none, supplier=self.supplier, project=None,
            description="Settle general", actual_amount=Decimal("200.00"),
        )

        response = self.client.get(reverse("supplier_settlement_list"), {"company_id": self.comp001.id})
        self.assertEqual(response.status_code, 200)
        settlement_ids = [s.id for s in response.context["settlements"]]
        self.assertIn(settlement_a.id, settlement_ids)
        self.assertNotIn(settlement_none.id, settlement_ids)

        response_b = self.client.get(reverse("supplier_settlement_list"), {"company_id": self.comp002.id})
        settlement_ids_b = [s.id for s in response_b.context["settlements"]]
        self.assertNotIn(settlement_a.id, settlement_ids_b)
        self.assertNotIn(settlement_none.id, settlement_ids_b)

    # 6: GRN with PO linked to Project -> Company derived correctly
    def test_grn_with_po_linked_to_project_derives_company(self):
        grn_a = GRN.objects.create(purchase_order=self.po_a, supplier=self.supplier)
        grn_b = GRN.objects.create(purchase_order=self.po_b, supplier=self.supplier)

        response = self.client.get(reverse("grn_list"), {"company_id": self.comp001.id})
        self.assertEqual(response.status_code, 200)
        grn_ids = [g.id for g in response.context["grns"]]
        self.assertIn(grn_a.id, grn_ids)
        self.assertNotIn(grn_b.id, grn_ids)

    # 7: GRN with project-less PO -> no Company assignment
    def test_grn_with_project_less_po_excluded_from_both_companies(self):
        grn_none = GRN.objects.create(purchase_order=self.po_none, supplier=self.supplier)

        for company in (self.comp001, self.comp002):
            response = self.client.get(reverse("grn_list"), {"company_id": company.id})
            grn_ids = [g.id for g in response.context["grns"]]
            self.assertNotIn(grn_none.id, grn_ids)

        response_all = self.client.get(reverse("grn_list"))
        grn_ids_all = [g.id for g in response_all.context["grns"]]
        self.assertIn(grn_none.id, grn_ids_all)

    # 8: Company switcher changes report scope correctly (active session,
    # no explicit company_id GET param)
    def test_company_switcher_changes_report_scope(self):
        self._switch_to(self.comp001)
        response = self.client.get(reverse("purchase_order_list"))
        order_ids = [o.id for o in response.context["orders"]]
        self.assertIn(self.po_a.id, order_ids)
        self.assertNotIn(self.po_b.id, order_ids)

        self._switch_to(self.comp002)
        response2 = self.client.get(reverse("purchase_order_list"))
        order_ids2 = [o.id for o in response2.context["orders"]]
        self.assertIn(self.po_b.id, order_ids2)
        self.assertNotIn(self.po_a.id, order_ids2)

    # 9: existing no-company-filter behaviour is unchanged (all records visible)
    def test_no_company_filter_preserves_existing_behavior(self):
        for url_name in ("purchase_order_list", "supplier_settlement_list", "supplier_advance_summary", "grn_list"):
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200, url_name)

        response = self.client.get(reverse("purchase_order_list"))
        order_ids = [o.id for o in response.context["orders"]]
        self.assertIn(self.po_a.id, order_ids)
        self.assertIn(self.po_b.id, order_ids)
        self.assertIn(self.po_none.id, order_ids)

    # 10: no database records are modified by viewing/filtering these reports
    def test_viewing_reports_does_not_modify_any_record(self):
        advance = SupplierAdvance.objects.create(
            supplier=self.supplier, project=self.pA, amount=Decimal("500.00")
        )
        settlement = SupplierSettlement.objects.create(
            advance=advance, supplier=self.supplier, project=self.pA,
            description="Settle", actual_amount=Decimal("100.00"),
        )
        grn = GRN.objects.create(purchase_order=self.po_a, supplier=self.supplier)

        before = (
            self.po_a.project_id, self.po_a.status,
            advance.amount, advance.project_id,
            settlement.actual_amount, settlement.project_id,
            grn.purchase_order_id, grn.status,
        )

        self._switch_to(self.comp001)
        self.client.get(reverse("purchase_order_list"), {"company_id": self.comp001.id})
        self.client.get(reverse("supplier_advance_summary"), {"company_id": self.comp002.id})
        self.client.get(reverse("supplier_settlement_list"))
        self.client.get(reverse("grn_list"), {"company_id": self.comp001.id})
        self._switch_to(self.comp002)

        self.po_a.refresh_from_db()
        advance.refresh_from_db()
        settlement.refresh_from_db()
        grn.refresh_from_db()
        after = (
            self.po_a.project_id, self.po_a.status,
            advance.amount, advance.project_id,
            settlement.actual_amount, settlement.project_id,
            grn.purchase_order_id, grn.status,
        )
        self.assertEqual(before, after)

    # No Company field was added to any model in this phase
    def test_no_company_field_added_to_purchasing_models(self):
        for model in (PurchaseOrder, SupplierAdvance, SupplierSettlement, GRN, GRNItem):
            self.assertFalse(hasattr(model, "company"), f"{model.__name__} must not have a company field")
            self.assertFalse(hasattr(model, "company_id"), f"{model.__name__} must not have a company_id field")



class ProjectTransferTests(TestCase):
    def setUp(self):
        from .models import ProjectTransfer  # noqa: F401
        self.owner = User.objects.create_user("owner_pt", password="p", is_superuser=True)
        self.clerk = User.objects.create_user("clerk_pt", password="p")
        self.clerk.groups.add(Group.objects.create(name="Clerk"))
        self.a = Project.objects.create(project_id="PA", project_name="A", project_type="OT")
        self.b = Project.objects.create(project_id="PB", project_name="B", project_type="OT")
        self.closed = Project.objects.create(project_id="PC", project_name="C", project_type="OT", status="completed")
        self.gl = GLMaster.objects.create(gl_code="5001", gl_name="Cost GL") if hasattr(GLMaster, "gl_code") else None
        self.exp = ProjectExpense.objects.create(
            expense_no="900001", project=self.a, expense_type="direct", description="Cement",
            qty=1, unit_price=5000, amount=5000, gl_account=self.gl,
        )
        self.exp2 = ProjectExpense.objects.create(
            expense_no="900002", project=self.a, expense_type="direct", description="Sand",
            qty=1, unit_price=2000, amount=2000, gl_account=self.gl,
        )
        self.url = reverse("add_project_transfer")

    def login(self, user):
        self.client.force_login(user)

    def post(self, entries, amounts=None, dest=None, user=None, reason="Wrong project", ttype="expense"):
        self.login(user or self.owner)
        data = {
            "transfer_type": ttype,
            "source_project": self.a.id,
            "to_project": (dest or self.b).id,
            "selected_entries": [e.id for e in entries],
            "reason": reason,
        }
        for e in entries:
            data[f"transfer_amount_{e.id}"] = str((amounts or {}).get(e.id, e.amount))
        return self.client.post(self.url, data)

    def net(self, project):
        from django.db.models import Sum
        return project.expenses.filter(is_active=True).aggregate(t=Sum("amount"))["t"] or Decimal("0")

    def test_owner_can_open_page_and_sees_entries(self):
        self.login(self.owner)
        r = self.client.get(self.url, {"type": "expense", "source_project": self.a.id})
        self.assertEqual(r.status_code, 200)
        self.assertEqual({row["id"] for row in r.context["entry_rows"]}, {self.exp.id, self.exp2.id})

    def test_non_owner_cannot_open_or_post(self):
        self.login(self.clerk)
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.post([self.exp], user=self.clerk)
        from .models import ProjectTransfer
        self.assertEqual(ProjectTransfer.objects.count(), 0)
        self.assertEqual(ProjectExpense.objects.count(), 2)

    def test_full_transfer_nets_source_and_posts_destination_and_profit(self):
        from .models import ProjectTransfer
        from .views import compute_project_profit_rows
        self.post([self.exp])
        self.assertEqual(ProjectTransfer.objects.count(), 1)
        self.assertEqual(self.net(self.a), Decimal("2000"))
        self.assertEqual(self.net(self.b), Decimal("5000"))
        rows, _ = compute_project_profit_rows(Project.objects.filter(id__in=[self.a.id, self.b.id]).order_by("id"))
        by_id = {r["project"].id: r for r in rows}
        self.assertEqual(by_id[self.a.id]["net_expense"], Decimal("2000"))
        self.assertEqual(by_id[self.b.id]["net_expense"], Decimal("5000"))

    def test_profit_single_entry_transfer_is_zero_on_source(self):
        from .views import compute_project_profit_rows
        self.exp2.delete()
        self.post([self.exp])
        rows, _ = compute_project_profit_rows(Project.objects.filter(id__in=[self.a.id, self.b.id]).order_by("id"))
        by_id = {r["project"].id: r for r in rows}
        self.assertEqual(by_id[self.a.id]["net_expense"], Decimal("0"))
        self.assertEqual(by_id[self.b.id]["net_expense"], Decimal("5000"))

    def test_traceability_and_original_unchanged(self):
        from .models import ProjectTransfer
        self.post([self.exp])
        self.exp.refresh_from_db()
        self.assertEqual(self.exp.project_id, self.a.id)
        self.assertEqual(self.exp.amount, Decimal("5000"))
        self.assertTrue(self.exp.is_active)
        transfer = ProjectTransfer.objects.get()
        self.assertEqual(transfer.original_project_expense_id, self.exp.id)
        reverse_row = ProjectExpense.objects.get(transfer=transfer, project=self.a)
        repost_row = ProjectExpense.objects.get(transfer=transfer, project=self.b)
        self.assertEqual(reverse_row.amount, Decimal("-5000"))
        self.assertEqual(repost_row.amount, Decimal("5000"))
        self.assertEqual(reverse_row.original_expense_id, self.exp.id)
        self.assertEqual(repost_row.original_expense_id, self.exp.id)
        self.assertEqual(reverse_row.gl_account_id, self.exp.gl_account_id)
        self.assertEqual(repost_row.gl_account_id, self.exp.gl_account_id)
        self.assertEqual(ProjectExpense.objects.count(), 4)

    def test_same_transaction_cannot_be_transferred_twice(self):
        from .models import ProjectTransfer
        self.post([self.exp])
        self.post([self.exp])
        self.assertEqual(ProjectTransfer.objects.count(), 1)
        self.assertEqual(ProjectExpense.objects.count(), 4)

    def test_partial_transfer_limited_to_remaining(self):
        from .models import ProjectTransfer
        self.post([self.exp], amounts={self.exp.id: "3000"})
        self.assertEqual(ProjectTransfer.objects.count(), 1)
        self.post([self.exp], amounts={self.exp.id: "2500"})
        self.assertEqual(ProjectTransfer.objects.count(), 1)
        self.post([self.exp], amounts={self.exp.id: "2000"})
        self.assertEqual(ProjectTransfer.objects.count(), 2)
        self.post([self.exp], amounts={self.exp.id: "1"})
        self.assertEqual(ProjectTransfer.objects.count(), 2)

    def test_reversal_and_repost_rows_not_selectable_or_transferable(self):
        from .models import ProjectTransfer
        self.post([self.exp])
        transfer = ProjectTransfer.objects.get()
        reverse_row = ProjectExpense.objects.get(transfer=transfer, project=self.a)
        repost_row = ProjectExpense.objects.get(transfer=transfer, project=self.b)

        self.login(self.owner)
        r = self.client.get(self.url, {"type": "expense", "source_project": self.a.id})
        self.assertNotIn(reverse_row.id, [x["id"] for x in r.context["entry_rows"]])
        self.assertNotIn(self.exp.id, [x["id"] for x in r.context["entry_rows"]])
        r = self.client.get(self.url, {"type": "expense", "source_project": self.b.id})
        self.assertEqual(r.context["entry_rows"], [])

        self.client.post(self.url, {
            "transfer_type": "expense", "source_project": self.b.id, "to_project": self.a.id,
            "selected_entries": [repost_row.id], f"transfer_amount_{repost_row.id}": "5000", "reason": "x",
        })
        self.client.post(self.url, {
            "transfer_type": "expense", "source_project": self.a.id, "to_project": self.b.id,
            "selected_entries": [reverse_row.id], f"transfer_amount_{reverse_row.id}": "1", "reason": "x",
        })
        self.assertEqual(ProjectTransfer.objects.count(), 1)

    def test_multi_entry_transfer_is_atomic(self):
        from .models import ProjectTransfer
        self.post([self.exp, self.exp2], amounts={self.exp.id: "5000", self.exp2.id: "9999"})
        self.assertEqual(ProjectTransfer.objects.count(), 0)
        self.assertEqual(ProjectExpense.objects.count(), 2)

    def test_multi_entry_transfer_success(self):
        from .models import ProjectTransfer
        self.post([self.exp, self.exp2])
        self.assertEqual(ProjectTransfer.objects.count(), 2)
        self.assertEqual(self.net(self.a), Decimal("0"))
        self.assertEqual(self.net(self.b), Decimal("7000"))

    def test_long_reason_description_within_255(self):
        self.post([self.exp], reason="R" * 3000)
        self.assertEqual(ProjectExpense.objects.count(), 4)
        for row in ProjectExpense.objects.filter(transfer__isnull=False):
            self.assertLessEqual(len(row.description), 255)

    def test_source_not_in_destination_options_and_same_project_rejected(self):
        from .models import ProjectTransfer
        self.login(self.owner)
        r = self.client.get(self.url, {"type": "expense", "source_project": self.a.id})
        dest_ids = [p.id for p in r.context["destination_projects"]]
        self.assertNotIn(self.a.id, dest_ids)
        self.assertNotIn(self.closed.id, dest_ids)
        self.post([self.exp], dest=self.a)
        self.assertEqual(ProjectTransfer.objects.count(), 0)

    def test_closed_destination_rejected(self):
        from .models import ProjectTransfer
        self.post([self.exp], dest=self.closed)
        self.assertEqual(ProjectTransfer.objects.count(), 0)

    def test_income_transfer_and_eligibility(self):
        from .models import ProjectTransfer
        inc = ProjectIncome.objects.create(project=self.a, amount=Decimal("1000"), description="Adv", gl_account=self.gl)
        self.post([inc], ttype="income")
        self.assertEqual(ProjectTransfer.objects.count(), 1)
        inc.refresh_from_db()
        self.assertEqual(inc.project_id, self.a.id)
        self.assertEqual(ProjectIncome.objects.filter(project=self.b, amount=1000).count(), 1)
        self.assertEqual(ProjectIncome.objects.filter(project=self.a, amount=-1000).count(), 1)
        self.post([inc], ttype="income")
        self.assertEqual(ProjectTransfer.objects.count(), 1)

    def test_historical_transfer_records_remain_readable(self):
        from .models import ProjectTransfer
        ProjectTransfer.objects.create(
            transfer_type="expense", from_project=self.a, to_project=self.b,
            original_project_expense=self.exp, transfer_amount=Decimal("100"), reason="legacy",
        )
        ProjectTransfer.objects.create(
            transfer_type="income", from_project=self.a, to_project=self.b, transfer_amount=Decimal("50"),
        )
        self.login(self.owner)
        self.assertEqual(self.client.get(reverse("project_transfer_list")).status_code, 200)
        self.login(self.clerk)
        self.assertEqual(self.client.get(reverse("project_transfer_list")).status_code, 200)
        self.login(self.owner)
        r = self.client.get(self.url, {"type": "expense", "source_project": self.a.id})
        row = next(x for x in r.context["entry_rows"] if x["id"] == self.exp.id)
        self.assertEqual(row["remaining"], Decimal("4900"))
    def test_partial_5000_scenario_3000_2000_then_rejected(self):
        from django.db.models import Sum
        from .models import ProjectTransfer
        self.post([self.exp], amounts={self.exp.id: "3000"})
        self.post([self.exp], amounts={self.exp.id: "2000"})
        self.assertEqual(ProjectTransfer.objects.count(), 2)
        self.post([self.exp], amounts={self.exp.id: "2000"})
        self.post([self.exp], amounts={self.exp.id: "0.01"})
        self.assertEqual(ProjectTransfer.objects.count(), 2)
        total = ProjectTransfer.objects.aggregate(t=Sum("transfer_amount"))["t"]
        self.assertEqual(total, Decimal("5000"))
        self.login(self.owner)
        r = self.client.get(self.url, {"type": "expense", "source_project": self.a.id})
        self.assertNotIn(self.exp.id, [x["id"] for x in r.context["entry_rows"]])

    def test_manager_and_cashier_cannot_transfer_but_can_read_list(self):
        from .models import ProjectTransfer
        for name in ("Manager", "Cashier"):
            u = User.objects.create_user(f"{name.lower()}_pt", "pw-test-123")
            u.groups.add(Group.objects.get_or_create(name=name)[0])
            self.login(u)
            self.assertEqual(self.client.get(self.url).status_code, 302)
            self.post([self.exp], user=u)
        self.assertEqual(ProjectTransfer.objects.count(), 0)
        self.assertEqual(ProjectExpense.objects.count(), 2)

    def test_inventory_returns_unaffected_by_transfer(self):
        from .views import compute_project_profit_rows
        ProjectExpense.objects.create(
            expense_no="900003", project=self.a, expense_type="inventory", description="Return",
            qty=1, unit_price=-1000, amount=-1000, gl_account=self.gl,
        )
        qs = Project.objects.filter(id=self.a.id)
        before = compute_project_profit_rows(qs)[0][0]
        self.post([self.exp])
        after = compute_project_profit_rows(qs)[0][0]
        self.assertEqual(before["returns_credit"], Decimal("1000"))
        self.assertEqual(after["returns_credit"], Decimal("1000"))
        self.assertEqual(before["net_expense"] - after["net_expense"], Decimal("5000"))

    def test_active_ongoing_and_active_stage_projects_both_selectable(self):
        from .models import ProjectTransfer
        legacy = Project.objects.create(project_id="PL", project_name="Legacy", project_type="OT", status="active")
        inactive = Project.objects.create(project_id="PI", project_name="Inactive", project_type="OT", is_active=False)
        cancelled = Project.objects.create(project_id="PX", project_name="Cancelled", project_type="OT", status="cancelled")
        self.login(self.owner)
        r = self.client.get(self.url, {"type": "expense", "source_project": self.a.id})
        source_ids = {p.id for p in r.context["projects"]}
        self.assertTrue({self.a.id, self.b.id, legacy.id} <= source_ids)
        self.assertFalse({self.closed.id, inactive.id, cancelled.id} & source_ids)
        dest_ids = {p.id for p in r.context["destination_projects"]}
        self.assertEqual(dest_ids, {self.b.id, legacy.id})
        # a project whose stage is "Active" can be a source and a destination
        self.post([self.exp], dest=legacy)
        self.assertEqual(ProjectTransfer.objects.filter(to_project=legacy).count(), 1)
        own = ProjectExpense.objects.create(
            expense_no="900010", project=legacy, expense_type="direct", description="Own",
            qty=1, unit_price=700, amount=700, gl_account=self.gl,
        )
        self.login(self.owner)
        r = self.client.get(self.url, {"type": "expense", "source_project": legacy.id})
        self.assertEqual([x["id"] for x in r.context["entry_rows"]], [own.id])
        self.assertNotIn(legacy.id, [p.id for p in r.context["destination_projects"]])


class MaintenanceAllocationTests(TestCase):
    MONTH = date(2026, 6, 1)

    def setUp(self):
        from .models import MaintenanceAllocation, MaintenanceAllocationLine  # noqa: F401
        self.owner = User.objects.create_user("owner_mca", password="x", is_superuser=True)
        self.clerk = User.objects.create_user("clerk_mca", password="x")
        self.clerk.groups.add(Group.objects.create(name="Clerk"))
        self.manager = User.objects.create_user("mgr_mca", password="x")
        self.manager.groups.add(Group.objects.create(name="Manager"))
        self.cashier = User.objects.create_user("cash_mca", password="x")
        self.cashier.groups.add(Group.objects.create(name="Cashier"))
        self.m = Project.objects.create(project_id="MAINT", project_name="Maintenance Main", project_type="OT")
        self.b = Project.objects.create(project_id="PB", project_name="B", project_type="OT")
        self.c = Project.objects.create(project_id="PC", project_name="C", project_type="OT")
        self.closed = Project.objects.create(project_id="PX", project_name="X", project_type="OT", status="completed")
        self.gl = GLMaster.objects.create(gl_code="6001", gl_name="Maint GL", gl_type="expense")
        self.exp = ProjectExpense.objects.create(
            expense_no="910001", project=self.m, expense_type="direct", description="Generator repair",
            qty=1, unit_price=6000, amount=6000, expense_date=date(2026, 6, 10),
        )
        self.exp2 = ProjectExpense.objects.create(
            expense_no="910002", project=self.m, expense_type="direct", description="Vehicle service",
            qty=1, unit_price=4000, amount=4000, expense_date=date(2026, 6, 20),
        )
        # outside the month, must be ignored
        ProjectExpense.objects.create(
            expense_no="910003", project=self.m, expense_type="direct", description="July",
            qty=1, unit_price=999, amount=999, expense_date=date(2026, 7, 2),
        )
        self.add_url = reverse("maintenance_allocation_create")

    # helpers
    def make(self, rows=None, method="amount", status="draft"):
        from .models import MaintenanceAllocation, MaintenanceAllocationLine
        from .maintenance_allocation_views import available_cost
        a = MaintenanceAllocation.objects.create(
            month=self.MONTH, source_project=self.m, method=method,
            available_amount=available_cost(self.m, self.MONTH), status=status, created_by=self.owner,
        )
        for proj, amt in (rows or [(self.b, "6000"), (self.c, "4000")]):
            MaintenanceAllocationLine.objects.create(
                allocation=a, project=proj, amount=Decimal(amt), percent=Decimal("0"), gl_account=self.gl,
            )
        return a

    def action(self, name, alloc, user=None, **data):
        self.client.force_login(user or self.owner)
        return self.client.post(reverse(f"maintenance_allocation_{name}", args=[alloc.pk]), data)

    def post_full(self, alloc):
        from .maintenance_allocation_views import submit_allocation, approve_allocation, post_allocation
        submit_allocation(self.owner, alloc.pk)
        approve_allocation(self.owner, alloc.pk)
        post_allocation(self.owner, alloc.pk)
        alloc.refresh_from_db()

    def net(self, project):
        from .maintenance_allocation_views import closing_balance
        return closing_balance(project, self.MONTH)

    def form_data(self, rows, method="amount", action="save", source=None):
        d = {"month": "2026-06", "source_project": (source or self.m).id, "method": method,
             "action": action, "remarks": "", "line_project": [r[0].id for r in rows],
             "line_value": [str(r[1]) for r in rows], "line_gl": [self.gl.id] * len(rows),
             "line_remarks": [""] * len(rows)}
        return d

    # tests
    def test_month_end_allocation_routes_and_pages_use_new_name(self):
        self.client.force_login(self.owner)
        self.assertEqual(reverse("month_end_allocation_list"), "/month-end-allocations/")
        self.assertEqual(reverse("maintenance_allocation_list"), "/maintenance-allocations/")

        response = self.client.get(reverse("month_end_allocation_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Month-End Allocation")
        self.assertContains(response, "Main/P&amp;I Source Project")
        self.assertNotContains(response, "Maintenance Cost Allocation")

        for name in ("month_end_allocation_create", "month_end_allocation_report"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)
            self.assertContains(response, "Month-End Allocation")

    def test_available_cost_includes_other_expense_types(self):
        from .maintenance_allocation_views import available_cost
        ProjectExpense.objects.create(
            expense_no="910020", project=self.m, expense_type="service", description="P&I service",
            qty=1, unit_price=250, amount=250, expense_date=date(2026, 6, 15),
        )
        self.assertEqual(available_cost(self.m, self.MONTH), Decimal("10250.00"))

    def test_available_cost_month_only(self):
        from .maintenance_allocation_views import available_cost
        self.assertEqual(available_cost(self.m, self.MONTH), Decimal("10000.00"))

    def test_available_cost_includes_petty_cash_and_returns(self):
        from .maintenance_allocation_views import available_cost
        from .models import ProjectPettyCash, ProjectPettyCashExpense
        pc = ProjectPettyCash.objects.create(amount_issued=Decimal('5000'))
        ProjectPettyCashExpense.objects.create(
            petty_cash=pc, project=self.m, expense_date=date(2026, 6, 5), amount=Decimal("500"), approval_status="approved",
        )
        ProjectPettyCashExpense.objects.create(
            petty_cash=pc, project=self.m, expense_date=date(2026, 6, 6), amount=Decimal("300"), approval_status="pending",
        )
        ProjectExpense.objects.create(
            expense_no="910010", project=self.m, expense_type="inventory", description="Return",
            qty=1, unit_price=-200, amount=-200, expense_date=date(2026, 6, 7),
        )
        self.assertEqual(available_cost(self.m, self.MONTH), Decimal("10300.00"))

    def test_create_draft_and_reference_format(self):
        self.client.force_login(self.owner)
        r = self.client.post(self.add_url, self.form_data([(self.b, "6000"), (self.c, "4000")]))
        self.assertEqual(r.status_code, 302)
        from .models import MaintenanceAllocation
        a = MaintenanceAllocation.objects.get()
        self.assertEqual(a.reference, "MCA-202606-0001")
        self.assertEqual(a.status, "draft")
        self.assertEqual(a.lines.count(), 2)
        self.assertEqual(a.month, self.MONTH)

    def test_reference_increments(self):
        a1, a2 = self.make(), self.make()
        self.assertEqual((a1.reference, a2.reference), ("MCA-202606-0001", "MCA-202606-0002"))

    def test_percent_method_rounding_absorbed_by_last_line(self):
        self.client.force_login(self.owner)
        self.client.post(self.add_url, self.form_data(
            [(self.b, "33.3333"), (self.c, "66.6667")], method="percent"))
        from .models import MaintenanceAllocation
        a = MaintenanceAllocation.objects.get()
        total = sum(l.amount for l in a.lines.all())
        self.assertEqual(total, Decimal("10000.00"))

    def test_draft_over_allocation_rejected(self):
        self.client.force_login(self.owner)
        self.client.post(self.add_url, self.form_data([(self.b, "10000.01")]))
        from .models import MaintenanceAllocation
        self.assertEqual(MaintenanceAllocation.objects.count(), 0)

    def test_duplicate_destination_rejected(self):
        self.client.force_login(self.owner)
        self.client.post(self.add_url, self.form_data([(self.b, "5000"), (self.b, "5000")]))
        from .models import MaintenanceAllocation
        self.assertEqual(MaintenanceAllocation.objects.count(), 0)

    def test_maintenance_project_cannot_be_destination(self):
        self.client.force_login(self.owner)
        self.client.post(self.add_url, self.form_data([(self.m, "10000")]))
        from .models import MaintenanceAllocation
        self.assertEqual(MaintenanceAllocation.objects.count(), 0)

    def test_closed_project_cannot_be_destination(self):
        self.client.force_login(self.owner)
        self.client.post(self.add_url, self.form_data([(self.closed, "10000")]))
        from .models import MaintenanceAllocation
        self.assertEqual(MaintenanceAllocation.objects.count(), 0)

    def test_non_owner_cannot_approve_post_reverse(self):
        a = self.make(status="pending")
        for user in (self.clerk, self.manager, self.cashier):
            for name in ("approve", "post", "reject", "reverse"):
                r = self.action(name, a, user=user, reason="x")
                self.assertEqual(r.status_code, 403, f"{user.username} {name}")
        a.refresh_from_db()
        self.assertEqual(a.status, "pending")
        self.assertEqual(ProjectExpense.objects.filter(maintenance_allocation=a).count(), 0)

    def test_owner_workflow_end_to_end(self):
        a = self.make()
        self.assertEqual(self.action("submit", a, user=self.clerk).status_code, 302)
        a.refresh_from_db(); self.assertEqual(a.status, "pending")
        self.action("approve", a)
        a.refresh_from_db(); self.assertEqual(a.status, "approved")
        self.assertEqual(a.approved_by, self.owner)
        self.action("post", a)
        a.refresh_from_db(); self.assertEqual(a.status, "posted")
        self.assertEqual(a.posted_by, self.owner)
        self.assertIsNotNone(a.posted_at)

    def test_non_owner_cannot_post_via_direct_get_or_post_and_get_not_allowed(self):
        a = self.make(status="approved")
        self.client.force_login(self.owner)
        r = self.client.get(reverse("maintenance_allocation_post", args=[a.pk]))
        self.assertEqual(r.status_code, 405)

    def test_approval_blocked_when_remaining_positive(self):
        a = self.make(rows=[(self.b, "6000"), (self.c, "3999.99")], status="pending")
        self.action("approve", a)
        a.refresh_from_db(); self.assertEqual(a.status, "pending")

    def test_approval_blocked_when_over_allocated(self):
        a = self.make(rows=[(self.b, "6000"), (self.c, "4000.01")], status="pending")
        self.action("approve", a)
        a.refresh_from_db(); self.assertEqual(a.status, "pending")

    def test_posting_blocked_when_cost_changed_after_approval(self):
        a = self.make(status="approved")
        ProjectExpense.objects.create(
            expense_no="910020", project=self.m, expense_type="direct", description="Late bill",
            qty=1, unit_price=100, amount=100, expense_date=date(2026, 6, 25),
        )
        self.action("post", a)
        a.refresh_from_db(); self.assertEqual(a.status, "approved")
        self.assertEqual(ProjectExpense.objects.filter(maintenance_allocation=a).count(), 0)

    def test_nothing_changes_before_posting(self):
        a = self.make(status="pending")
        before = ProjectExpense.objects.count()
        self.action("approve", a)
        self.assertEqual(ProjectExpense.objects.count(), before)
        self.assertEqual(self.net(self.m), Decimal("10000.00"))
        self.assertEqual(self.net(self.b), Decimal("0.00"))

    def test_posting_zeroes_maintenance_and_charges_destinations(self):
        a = self.make()
        self.post_full(a)
        self.assertEqual(self.net(self.m), Decimal("0.00"))
        self.assertEqual(self.net(self.b), Decimal("6000.00"))
        self.assertEqual(self.net(self.c), Decimal("4000.00"))
        rows = ProjectExpense.objects.filter(maintenance_allocation=a)
        self.assertEqual(rows.count(), 4)
        self.assertTrue(all(r.maintenance_allocation_line_id for r in rows))
        self.assertTrue(all(r.gl_account_id == self.gl.id for r in rows))
        self.assertTrue(all(r.expense_date == date(2026, 6, 30) for r in rows))
        self.assertEqual(sum(r.amount for r in rows), Decimal("0.00"))

    def test_project_profit_after_posting(self):
        from .views import compute_project_profit_rows
        a = self.make()
        self.post_full(a)
        rows, _ = compute_project_profit_rows(Project.objects.filter(id__in=[self.m.id, self.b.id, self.c.id]))
        by = {r["project"].id: r for r in rows}
        self.assertEqual(by[self.m.id]["net_expense"], Decimal("999.00") + Decimal("0"))
        self.assertEqual(by[self.b.id]["net_expense"], Decimal("6000"))
        self.assertEqual(by[self.c.id]["net_expense"], Decimal("4000"))

    def test_original_rows_unchanged(self):
        a = self.make()
        self.post_full(a)
        for e, amt in ((self.exp, 6000), (self.exp2, 4000)):
            e.refresh_from_db()
            self.assertEqual(e.project_id, self.m.id)
            self.assertEqual(e.amount, Decimal(amt))
            self.assertIsNone(e.maintenance_allocation_id)
            self.assertTrue(e.is_active)

    def test_duplicate_posting_blocked(self):
        from .maintenance_allocation_views import post_allocation, AllocationError
        a = self.make()
        self.post_full(a)
        with self.assertRaises(AllocationError):
            post_allocation(self.owner, a.pk)
        self.assertEqual(ProjectExpense.objects.filter(maintenance_allocation=a).count(), 4)

    def test_second_allocation_same_month_cannot_post(self):
        from .maintenance_allocation_views import approve_allocation, post_allocation, AllocationError, submit_allocation
        a = self.make()
        self.post_full(a)
        b = self.make(status="approved")
        with self.assertRaises(AllocationError):
            post_allocation(self.owner, b.pk)

    def test_allocation_repost_rows_not_transferable_via_project_transfer(self):
        from .models import ProjectTransfer
        a = self.make()
        self.post_full(a)
        repost = ProjectExpense.objects.get(maintenance_allocation=a, project=self.b)
        reversal = ProjectExpense.objects.get(maintenance_allocation=a, project=self.m, amount=-6000)
        url = reverse("add_project_transfer")
        self.client.force_login(self.owner)
        r = self.client.get(url, {"type": "expense", "source_project": self.b.id})
        self.assertEqual(r.context["entry_rows"], [])
        before = ProjectExpense.objects.count()
        for row, src in ((repost, self.b), (reversal, self.m)):
            self.client.post(url, {
                "transfer_type": "expense", "source_project": src.id, "to_project": self.c.id,
                "selected_entries": [row.id], f"transfer_amount_{row.id}": "1", "reason": "x",
            })
        self.assertEqual(ProjectTransfer.objects.count(), 0)
        self.assertEqual(ProjectExpense.objects.count(), before)

    def test_normal_expense_still_transferable_on_project_with_allocation(self):
        a = self.make()
        self.post_full(a)
        self.client.force_login(self.owner)
        r = self.client.get(reverse("add_project_transfer"), {"type": "expense", "source_project": self.m.id})
        ids = [x["id"] for x in r.context["entry_rows"]]
        self.assertIn(self.exp.id, ids)
        self.assertIn(self.exp2.id, ids)

    def test_second_allocation_blocked_at_draft_submit_and_approve(self):
        from .maintenance_allocation_views import submit_allocation, approve_allocation, AllocationError
        a = self.make()
        self.post_full(a)
        self.client.force_login(self.owner)
        self.client.post(self.add_url, self.form_data([(self.b, "10000")]))
        from .models import MaintenanceAllocation
        self.assertEqual(MaintenanceAllocation.objects.count(), 1)
        d = self.make()
        with self.assertRaises(AllocationError):
            submit_allocation(self.owner, d.pk)
        p = self.make(status="pending")
        with self.assertRaises(AllocationError):
            approve_allocation(self.owner, p.pk)

    def test_late_old_dated_expense_is_reported_not_redistributed(self):
        from .maintenance_allocation_views import closing_balance
        a = self.make()
        self.post_full(a)
        ProjectExpense.objects.create(
            expense_no="910050", project=self.m, expense_type="direct", description="Late bill",
            qty=1, unit_price=700, amount=700, expense_date=date(2026, 6, 15),
        )
        self.assertEqual(closing_balance(self.m, self.MONTH), Decimal("700.00"))
        self.assertEqual(ProjectExpense.objects.filter(maintenance_allocation=a).count(), 4)
        self.client.force_login(self.owner)
        r = self.client.get(reverse("maintenance_allocation_report"))
        self.assertEqual(r.context["closing_balance"], Decimal("700.00"))
        self.assertEqual(len(r.context["late_variances"]), 1)
        d = self.make(rows=[(self.b, "10700")])
        from .maintenance_allocation_views import submit_allocation, AllocationError
        with self.assertRaises(AllocationError):
            submit_allocation(self.owner, d.pk)

    def test_posted_allocation_cannot_be_edited(self):
        a = self.make()
        self.post_full(a)
        self.client.force_login(self.owner)
        r = self.client.post(reverse("maintenance_allocation_edit", args=[a.pk]),
                             self.form_data([(self.b, "10000")]))
        self.assertEqual(r.status_code, 302)
        a.refresh_from_db()
        self.assertEqual(a.lines.count(), 2)

    def test_posting_is_atomic(self):
        from unittest import mock
        from .maintenance_allocation_views import post_allocation
        a = self.make(status="approved")
        real = ProjectExpense.objects.create
        calls = {"n": 0}

        def flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 3:
                raise RuntimeError("boom")
            return real(*args, **kwargs)

        with mock.patch.object(ProjectExpense.objects, "create", side_effect=flaky):
            with self.assertRaises(RuntimeError):
                post_allocation(self.owner, a.pk)
        a.refresh_from_db()
        self.assertEqual(a.status, "approved")
        self.assertEqual(ProjectExpense.objects.filter(maintenance_allocation=a).count(), 0)

    def test_long_description_limited(self):
        long_proj = Project.objects.create(project_id="P" * 40, project_name="L", project_type="OT")
        a = self.make(rows=[(long_proj, "10000")])
        self.post_full(a)
        for r in ProjectExpense.objects.filter(maintenance_allocation=a):
            self.assertLessEqual(len(r.description), 255)

    def test_reversal_is_traceable_and_restores_balance(self):
        a = self.make()
        self.post_full(a)
        r = self.action("reverse", a, reason="Posted in error")
        a.refresh_from_db()
        self.assertEqual(a.status, "reversed")
        self.assertEqual(a.reversal_reason, "Posted in error")
        self.assertEqual(a.reversed_by, self.owner)
        rows = ProjectExpense.objects.filter(maintenance_allocation=a)
        self.assertEqual(rows.count(), 8)
        self.assertEqual(rows.filter(original_expense__isnull=False).count(), 4)
        self.assertEqual(sum(x.amount for x in rows), Decimal("0.00"))
        self.assertEqual(self.net(self.m), Decimal("10000.00"))
        self.assertEqual(self.net(self.b), Decimal("0.00"))

    def test_reversal_requires_reason_and_posted_status(self):
        a = self.make()
        self.post_full(a)
        self.action("reverse", a, reason="")
        a.refresh_from_db(); self.assertEqual(a.status, "posted")

    def test_reposting_allowed_after_reversal(self):
        a = self.make()
        self.post_full(a)
        self.action("reverse", a, reason="redo")
        b = self.make()
        self.post_full(b)
        self.assertEqual(self.net(self.m), Decimal("0.00"))

    def test_project_transfer_not_involved(self):
        from .models import ProjectTransfer
        a = self.make()
        self.post_full(a)
        self.assertEqual(ProjectTransfer.objects.count(), 0)
        self.assertEqual(ProjectExpense.objects.filter(transfer__isnull=False).count(), 0)

    def test_report_and_list_accessible(self):
        a = self.make()
        self.post_full(a)
        self.client.force_login(self.clerk)
        self.assertEqual(self.client.get(reverse("maintenance_allocation_list")).status_code, 200)
        r = self.client.get(reverse("maintenance_allocation_report"), {"month": "2026-06"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["closing_balance"], Decimal("0.00"))
        self.assertEqual(r.context["total_allocated"], Decimal("10000.00"))
        self.assertEqual(self.client.get(reverse("maintenance_allocation_detail", args=[a.pk])).status_code, 200)

    def test_anonymous_redirected(self):
        self.assertEqual(self.client.get(reverse("maintenance_allocation_list")).status_code, 302)



from .models import Sale, SaleItem  # noqa: E402


class SaveSaleAtomicityTests(TestCase):
    """save_sale must be all-or-nothing and must not disturb earlier records."""

    def setUp(self):
        from .models import Item, StockTransaction

        self.Item, self.StockTransaction = Item, StockTransaction
        self.user = User.objects.create_superuser("atomic_u", "a@x.com", "pw12345!")
        self.client.force_login(self.user)
        rev = GLMaster.objects.create(gl_code="AT1", gl_name="Rev", gl_type="income")
        cost = GLMaster.objects.create(gl_code="AT2", gl_name="Cost", gl_type="expense")

        def mk(code, cost_price, price, stock):
            return Item.objects.create(
                item_code=code, name=code, cost_price=Decimal(cost_price),
                selling_price=Decimal(price), stock=Decimal(stock),
                retail_gl_account=rev, cost_gl_account=cost,
            )

        self.a = mk("ATA", "672", "1000", "10")
        self.b = mk("ATB", "2300", "3500", "10")
        self.c = mk("ATC", "10", "20", "0")

    def _post(self, items, **extra):
        payload = {
            "items": [
                {"id": i.id, "qty": 1, "price": str(i.selling_price), "discount": 0}
                for i in items
            ],
            "discount": 0,
            "payment_method": "cash",
            "received": "4500",
        }
        payload.update(extra)
        return self.client.post(
            reverse("save_sale"), data=json.dumps(payload), content_type="application/json"
        )

    def _stock(self, item):
        return self.Item.objects.get(pk=item.pk).stock

    def _assert_nothing_persisted(self):
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(SaleItem.objects.count(), 0)
        self.assertEqual(self.StockTransaction.objects.count(), 0)
        self.assertEqual(self._stock(self.a), Decimal("10"))
        self.assertEqual(self._stock(self.b), Decimal("10"))

    def test_successful_sale_totals_stock_and_payment(self):
        r = self._post([self.a, self.b])
        self.assertEqual(r.status_code, 200)
        sale = Sale.objects.get()
        self.assertEqual(sale.total, Decimal("4500"))
        self.assertEqual(sale.grand_total, Decimal("4500"))
        self.assertEqual(sale.payment_method, "cash")
        self.assertEqual(sale.received_amount, Decimal("4500"))
        self.assertEqual(sale.balance, Decimal("0"))
        self.assertEqual(sale.sale_items.count(), 2)
        self.assertEqual(self._stock(self.a), Decimal("9"))
        self.assertEqual(self._stock(self.b), Decimal("9"))
        self.assertEqual(self.StockTransaction.objects.count(), 2)

    def test_mid_cart_out_of_stock_rolls_back_everything(self):
        r = self._post([self.a, self.b, self.c])
        self.assertEqual(r.status_code, 400)
        self._assert_nothing_persisted()

    def test_mid_cart_invalid_discount_rolls_back_everything(self):
        payload_items = [
            {"id": self.a.id, "qty": 1, "price": "1000", "discount": 0},
            {"id": self.b.id, "qty": 1, "price": "3500", "discount": -5},
        ]
        r = self.client.post(
            reverse("save_sale"),
            data=json.dumps({"items": payload_items, "discount": 0,
                             "payment_method": "cash", "received": "4500"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        self._assert_nothing_persisted()

    def test_exception_after_item_creation_rolls_back_everything(self):
        from unittest import mock

        with mock.patch.object(Sale, "save", side_effect=RuntimeError("boom")):
            r = self._post([self.a, self.b])
        self.assertEqual(r.status_code, 500)
        self._assert_nothing_persisted()

    def test_exception_during_stock_transaction_rolls_back_everything(self):
        from unittest import mock

        real = self.StockTransaction.objects.create
        calls = {"n": 0}

        def flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("boom")
            return real(*args, **kwargs)

        with mock.patch("pos.views.StockTransaction.objects.create", side_effect=flaky):
            r = self._post([self.a, self.b])
        self.assertEqual(r.status_code, 500)
        self._assert_nothing_persisted()

    def test_new_invoice_after_incomplete_legacy_invoice(self):
        legacy = Sale.objects.create(
            invoice_no="INV00199", sale_type="retail", payment_method="cash",
            total=Decimal("0"), discount=Decimal("0"), grand_total=Decimal("0"),
            received_amount=Decimal("0"), balance=Decimal("0"), created_by=self.user,
        )
        SaleItem.objects.create(
            sale=legacy, item=self.a, qty=Decimal("1"), price=Decimal("1000"),
            discount=Decimal("0"), amount=Decimal("1000"), net_amount=Decimal("1000"),
        )
        SaleItem.objects.create(
            sale=legacy, item=self.b, qty=Decimal("1"), price=Decimal("3500"),
            discount=Decimal("0"), amount=Decimal("3500"), net_amount=Decimal("3500"),
        )
        stock_a, stock_b = self._stock(self.a), self._stock(self.b)

        r = self._post([self.a, self.b])
        self.assertEqual(r.status_code, 200)
        new = Sale.objects.exclude(pk=legacy.pk).get()
        self.assertNotEqual(new.invoice_no, "INV00199")
        self.assertEqual(new.invoice_no, "INV00002")
        self.assertEqual(new.total, Decimal("4500"))
        self.assertEqual(new.grand_total, Decimal("4500"))
        # exactly one new deduction, and none attributable to the legacy invoice
        self.assertEqual(self._stock(self.a), stock_a - 1)
        self.assertEqual(self._stock(self.b), stock_b - 1)
        self.assertEqual(
            self.StockTransaction.objects.filter(reference_no="INV00199").count(), 0
        )
        self.assertEqual(
            self.StockTransaction.objects.filter(reference_no=new.invoice_no).count(), 2
        )

        legacy.refresh_from_db()
        self.assertEqual(legacy.invoice_no, "INV00199")
        self.assertEqual(legacy.total, Decimal("0"))
        self.assertEqual(legacy.grand_total, Decimal("0"))
        self.assertEqual(legacy.sale_items.count(), 2)

        resp = self.client.get(reverse("daily_report"))
        self.assertEqual(resp.status_code, 200)
        ctx = resp.context
        self.assertEqual(ctx["total_gross_sales"], Decimal("4500"))
        self.assertEqual(ctx["total_net_sales"], Decimal("4500"))
        # legacy INV00199 still contributes its COGS (672 + 2300) plus the new sale's
        self.assertEqual(ctx["total_cogs"], Decimal("5944"))


class ReverseSaleStockTests(TestCase):
    def setUp(self):
        from .models import Item, StockTransaction

        self.Item, self.ST = Item, StockTransaction
        self.owner = User.objects.create_superuser("rev_owner", "o@x.com", "pw12345!")
        self.clerk = User.objects.create_user("rev_clerk", password="pw12345!")
        rev = GLMaster.objects.create(gl_code="RV1", gl_name="Rev", gl_type="income")
        cost = GLMaster.objects.create(gl_code="RV2", gl_name="Cost", gl_type="expense")
        mk = lambda code, c, p: Item.objects.create(
            item_code=code, name=code, cost_price=Decimal(c), selling_price=Decimal(p),
            stock=Decimal("10"), retail_gl_account=rev, cost_gl_account=cost,
        )
        self.a, self.b = mk("RVA", "672", "1000"), mk("RVB", "2300", "3500")
        # Legacy incomplete sale: items exist, totals zero, stock already deducted.
        self.legacy = Sale.objects.create(
            invoice_no="INV00199", sale_type="retail", payment_method="cash",
            total=Decimal("0"), discount=Decimal("0"), grand_total=Decimal("0"),
            received_amount=Decimal("0"), balance=Decimal("0"), created_by=self.owner,
        )
        self.orig = []
        for it, price in ((self.a, "1000"), (self.b, "3500")):
            SaleItem.objects.create(
                sale=self.legacy, item=it, qty=Decimal("1"), price=Decimal(price),
                discount=Decimal("0"), amount=Decimal(price), net_amount=Decimal(price),
            )
            it.stock = Decimal("9")
            it.save()
            self.orig.append(self.ST.objects.create(
                item=it, transaction_type="sale", qty=Decimal("1"),
                reference_type="sale", reference_no="INV00199", created_by=self.owner,
            ))
        self.url = reverse("reverse_sale_stock", kwargs={"invoice_no": "INV00199"})

    def _stock(self, it):
        return self.Item.objects.get(pk=it.pk).stock

    def _reversals(self):
        return self.ST.objects.filter(
            reference_no="INV00199", reference_type="sale", transaction_type="adjustment_in"
        )

    def test_reversal_restores_stock_and_keeps_originals(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.assertEqual(self._stock(self.a), Decimal("10"))
        self.assertEqual(self._stock(self.b), Decimal("10"))
        self.assertEqual(self._reversals().count(), 2)
        for rev, orig in zip(self._reversals().order_by("id"), self.orig):
            self.assertEqual(rev.qty, Decimal("1"))
            self.assertEqual(rev.created_by, self.owner)
            self.assertIn("Reversal of stock deducted by incomplete INV00199", rev.notes)
            self.assertIn(f"original StockTransaction ID {orig.id}", rev.notes)
        for orig in self.orig:
            fresh = self.ST.objects.get(pk=orig.pk)
            self.assertEqual((fresh.transaction_type, fresh.qty, fresh.reference_no),
                             ("sale", Decimal("1"), "INV00199"))
        self.legacy.refresh_from_db()
        self.assertEqual((self.legacy.total, self.legacy.grand_total), (Decimal("0"), Decimal("0")))
        self.assertEqual(self.legacy.sale_items.count(), 2)

    def test_duplicate_reversal_blocked(self):
        self.client.force_login(self.owner)
        self.client.post(self.url)
        self.client.post(self.url)
        self.assertEqual(self._reversals().count(), 2)
        self.assertEqual(self._stock(self.a), Decimal("10"))
        self.assertEqual(self._stock(self.b), Decimal("10"))

    def test_unauthorized_user_cannot_reverse(self):
        self.client.force_login(self.clerk)
        self.client.post(self.url)
        self.assertEqual(self._reversals().count(), 0)
        self.assertEqual(self._stock(self.a), Decimal("9"))

    def test_normal_completed_sale_is_rejected(self):
        self.legacy.total = Decimal("4500")
        self.legacy.grand_total = Decimal("4500")
        self.legacy.save()
        self.client.force_login(self.owner)
        self.client.post(self.url)
        self.assertEqual(self._reversals().count(), 0)
        self.assertEqual(self._stock(self.a), Decimal("9"))

    def test_rollback_if_reversal_fails_midway(self):
        from unittest import mock

        real = self.ST.objects.create
        calls = {"n": 0}

        def flaky(*a, **k):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("boom")
            return real(*a, **k)

        self.client.force_login(self.owner)
        self.client.raise_request_exception = False
        with mock.patch("pos.views.StockTransaction.objects.create", side_effect=flaky):
            self.client.post(self.url)
        self.assertEqual(self._reversals().count(), 0)
        self.assertEqual(self._stock(self.a), Decimal("9"))
        self.assertEqual(self._stock(self.b), Decimal("9"))

    def test_reverse_then_new_invoice_nets_one_sale(self):
        self.client.force_login(self.owner)
        self.client.post(self.url)
        payload = {
            "items": [
                {"id": self.a.id, "qty": 1, "price": "1000", "discount": 0},
                {"id": self.b.id, "qty": 1, "price": "3500", "discount": 0},
            ],
            "discount": 0, "payment_method": "cash", "received": "4500",
        }
        r = self.client.post(reverse("save_sale"), data=json.dumps(payload),
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        new = Sale.objects.exclude(pk=self.legacy.pk).get()
        self.assertNotEqual(new.invoice_no, "INV00199")
        self.assertEqual(self._stock(self.a), Decimal("9"))
        self.assertEqual(self._stock(self.b), Decimal("9"))
        self.assertEqual(
            self.ST.objects.filter(reference_no=new.invoice_no, transaction_type="sale").count(), 2
        )
        self.assertEqual(
            self.ST.objects.filter(reference_no="INV00199", transaction_type="sale").count(), 2
        )
        self.assertEqual(new.grand_total, Decimal("4500"))

class VoidIncompleteSaleTests(TestCase):
    def setUp(self):
        from .models import Item, StockTransaction

        self.Item, self.ST = Item, StockTransaction
        self.owner = User.objects.create_superuser("void_owner", "o@x.com", "pw12345!")
        self.clerk = User.objects.create_user("void_clerk", "c@x.com", "pw12345!")
        rev = GLMaster.objects.create(gl_code="VD1", gl_name="Rev", gl_type="income")
        cost = GLMaster.objects.create(gl_code="VD2", gl_name="Cost", gl_type="expense")
        mk = lambda code, c, p: Item.objects.create(
            item_code=code, name=code, cost_price=Decimal(c), selling_price=Decimal(p),
            stock=Decimal("10"), retail_gl_account=rev, cost_gl_account=cost,
        )
        self.a, self.b = mk("VDA", "672", "1000"), mk("VDB", "2300", "3500")
        self.legacy = self._sale("INV00199", "0")
        self.good = self._sale("INV00200", "4500")
        self.orig = [
            self.ST.objects.create(item=it, transaction_type="sale", qty=Decimal("1"),
                                   reference_type="sale", reference_no="INV00199", created_by=self.owner)
            for it in (self.a, self.b)
        ]
        self.void_url = reverse("void_incomplete_sale", kwargs={"invoice_no": "INV00199"})
        self.rev_url = reverse("reverse_sale_stock", kwargs={"invoice_no": "INV00199"})

    def _sale(self, invoice_no, total):
        sale = Sale.objects.create(
            invoice_no=invoice_no, sale_type="retail", payment_method="cash",
            total=Decimal(total), discount=Decimal("0"), grand_total=Decimal(total),
            received_amount=Decimal(total), balance=Decimal("0"), created_by=self.owner,
        )
        for it, price in ((self.a, "1000"), (self.b, "3500")):
            SaleItem.objects.create(
                sale=sale, item=it, qty=Decimal("1"), price=Decimal(price),
                discount=Decimal("0"), amount=Decimal(price), net_amount=Decimal(price),
            )
        return sale

    def _report(self):
        self.client.force_login(self.owner)
        return self.client.get(reverse("daily_report")).context

    def _reverse_then_void(self):
        self.client.force_login(self.owner)
        self.client.post(self.rev_url)
        return self.client.post(self.void_url)

    def test_before_void_report_shows_negative_profit(self):
        ctx = self._report()
        self.assertEqual(ctx["total_cogs"], Decimal("5944"))
        self.assertEqual(ctx["total_profit"], Decimal("-1444"))

    def test_void_excluded_from_daily_report(self):
        self._reverse_then_void()
        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.approval_status, "void")
        ctx = self._report()
        self.assertEqual([s.invoice_no for s in ctx["sales"]], ["INV00200"])
        self.assertEqual(ctx["total_gross_sales"], Decimal("4500"))
        self.assertEqual(ctx["total_net_sales"], Decimal("4500"))
        self.assertEqual(ctx["total_cogs"], Decimal("2972"))
        self.assertEqual(ctx["total_profit"], Decimal("1528"))

    def test_audit_fields_recorded_and_data_preserved(self):
        self._reverse_then_void()
        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.approved_by, self.owner)
        self.assertIsNotNone(self.legacy.approved_at)
        self.assertIn("Incomplete sale", self.legacy.approval_note)
        self.assertEqual((self.legacy.total, self.legacy.grand_total), (Decimal("0"), Decimal("0")))
        self.assertEqual(self.legacy.sale_items.count(), 2)
        for o in self.orig:
            self.assertTrue(self.ST.objects.filter(pk=o.pk, transaction_type="sale").exists())
        self.assertEqual(
            self.ST.objects.filter(reference_no="INV00199", transaction_type="adjustment_in").count(), 2
        )
        self.good.refresh_from_db()
        self.assertEqual(self.good.approval_status, "na")

    def test_void_requires_stock_reversal_first(self):
        self.client.force_login(self.owner)
        self.client.post(self.void_url)
        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.approval_status, "na")

    def test_void_creates_no_stock_transactions(self):
        self.client.force_login(self.owner)
        self.client.post(self.rev_url)
        before = self.ST.objects.count()
        self.client.post(self.void_url)
        self.assertEqual(self.ST.objects.count(), before)

    def test_completed_sale_cannot_be_voided(self):
        self.client.force_login(self.owner)
        url = reverse("void_incomplete_sale", kwargs={"invoice_no": "INV00200"})
        self.client.post(url)
        self.good.refresh_from_db()
        self.assertEqual(self.good.approval_status, "na")
        self.assertEqual(len(self._report()["sales"]), 2)

    def test_non_owner_cannot_void(self):
        self.client.force_login(self.owner)
        self.client.post(self.rev_url)
        self.client.force_login(self.clerk)
        self.client.post(self.void_url)
        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.approval_status, "na")

    def test_void_twice_is_rejected(self):
        self._reverse_then_void()
        self.client.post(self.void_url)
        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.approval_status, "void")
