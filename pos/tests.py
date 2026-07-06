from decimal import Decimal

from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import (
    Employee,
    GLMaster,
    LabourAllocation,
    PayrollAllocation,
    PayrollAllowance,
    PayrollDeduction,
    PayrollEntry,
    Project,
    SalaryAdvance,
)


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
