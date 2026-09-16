# Register your models here.
from django.contrib import admin
from .models import (
    Category,
    Item,
    Supplier,
    UserLog,
    AuditLog,
    ProjectTransfer,
    LicenseRenewal,
    Quotation,
    QuotationItem,
    ProjectBudget,
    ProjectBudgetLine,
    ProjectCostActual,
    Employee,
    LabourAllocation,
    PayrollEntry,
    PayrollAllowance,
    PayrollDeduction,
    PayrollAllocation,
    PayrollProjectCostEntry,
    PayrollGLEntry,
    SalaryAdvance,
    SafetyItemIssue,
    Attendance,
    PayrollSettings,
    BackupSettings,
    BackupRecord,
    RestoreLog,
    BankAccount,
    BankTransaction,
    BankLedgerEntry,
    BankGLEntry,
)


# Logging Models
@admin.register(UserLog)
class UserLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'timestamp', 'ip_address']
    list_filter = ['action', 'timestamp', 'user']
    search_fields = ['user__username', 'ip_address']
    readonly_fields = ['timestamp', 'user', 'action', 'ip_address']
    ordering = ['-timestamp']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'model_name', 'object_display', 'timestamp']
    list_filter = ['action', 'model_name', 'timestamp', 'user']
    search_fields = ['object_display', 'user__username', 'model_name']
    readonly_fields = ['timestamp', 'user', 'action', 'model_name', 'object_id']
    ordering = ['-timestamp']


@admin.register(ProjectTransfer)
class ProjectTransferAdmin(admin.ModelAdmin):
    list_display = ['transfer_no', 'transfer_type', 'from_project', 'to_project', 'transfer_amount', 'transfer_date', 'created_by', 'approved_by']
    list_filter = ['transfer_type', 'transfer_date', 'created_by', 'approved_by']
    search_fields = ['transfer_no', 'from_project__project_id', 'to_project__project_id', 'reason']
    readonly_fields = ['transfer_no', 'created_at', 'approved_at']
    fieldsets = (
        ('Transfer Information', {
            'fields': ('transfer_no', 'transfer_type', 'transfer_date', 'transfer_amount')
        }),
        ('Project Details', {
            'fields': ('from_project', 'to_project', 'original_project_expense', 'original_project_income')
        }),
        ('Audit Trail', {
            'fields': ('created_by', 'created_at', 'approved_by', 'approved_at')
        }),
        ('Notes', {
            'fields': ('reason', 'notes')
        }),
    )
    ordering = ['-transfer_date', '-id']


admin.site.register(Category)
admin.site.register(Item)
admin.site.register(Supplier)
admin.site.register(BankAccount)
admin.site.register(BankTransaction)
admin.site.register(BankLedgerEntry)
admin.site.register(BankGLEntry)


@admin.register(LicenseRenewal)
class LicenseRenewalAdmin(admin.ModelAdmin):
    list_display = ['description', 'category', 'reference_number', 'expire_date', 'next_renewal_date', 'status', 'responsible_person']
    list_filter = ['category', 'status', 'expire_date', 'next_renewal_date']
    search_fields = ['description', 'reference_number', 'remarks']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-next_renewal_date', '-expire_date']


class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 1


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ['quotation_no', 'date', 'customer_name', 'status', 'created_by']
    list_filter = ['status', 'date']
    search_fields = ['quotation_no', 'customer_name', 'contact_person']
    inlines = [QuotationItemInline]
    readonly_fields = ['quotation_no', 'created_at']


# =========================
# PROJECT COST ANALYSIS ADMIN
# =========================
class ProjectBudgetLineInline(admin.TabularInline):
    model = ProjectBudgetLine
    extra = 1
    fields = ['gl_account', 'budget_amount']


@admin.register(ProjectBudget)
class ProjectBudgetAdmin(admin.ModelAdmin):
    list_display = ['project', 'budget_date', 'status', 'total_budget_amount', 'created_by', 'created_at']
    list_filter = ['status', 'budget_date', 'created_at']
    search_fields = ['project__project_id', 'project__project_name']
    readonly_fields = ['total_budget_amount', 'created_at', 'updated_at']
    inlines = [ProjectBudgetLineInline]
    fieldsets = (
        ('Project Budget', {
            'fields': ('project', 'budget_date', 'status', 'total_budget_amount')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Audit Trail', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProjectBudgetLine)
class ProjectBudgetLineAdmin(admin.ModelAdmin):
    list_display = ['budget', 'gl_account', 'budget_amount']
    list_filter = ['budget__project', 'gl_account__gl_code']
    search_fields = ['budget__project__project_id', 'gl_account__gl_code', 'gl_account__gl_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ProjectCostActual)
class ProjectCostActualAdmin(admin.ModelAdmin):
    list_display = ['project', 'gl_account', 'source_type', 'transaction_date', 'amount', 'reference_no']
    list_filter = ['project', 'source_type', 'transaction_date', 'gl_account']
    search_fields = ['project__project_id', 'gl_account__gl_code', 'reference_no', 'description']
    readonly_fields = ['created_at']


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['emp_no', 'full_name', 'designation', 'department', 'employment_type', 'is_active']
    list_filter = ['is_active', 'employment_type', 'department']
    search_fields = ['emp_no', 'full_name', 'nic', 'designation', 'department']


@admin.register(LabourAllocation)
class LabourAllocationAdmin(admin.ModelAdmin):
    list_display = ['employee', 'date', 'project', 'work_type', 'working_hours', 'ot_hours', 'attendance_status']
    list_filter = ['date', 'project', 'attendance_status', 'work_type']
    search_fields = ['employee__full_name', 'project__project_id', 'project__project_name', 'remarks']


@admin.register(PayrollEntry)
class PayrollEntryAdmin(admin.ModelAdmin):
    list_display = ['id', 'employee', 'project', 'department', 'gross_salary', 'status', 'created_by', 'created_at']
    list_filter = ['status', 'salary_period', 'department', 'employee_category', 'project']
    search_fields = ['employee__full_name', 'project__project_id', 'project__project_name', 'department']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(SalaryAdvance)
class SalaryAdvanceAdmin(admin.ModelAdmin):
    list_display = ['employee', 'advance_date', 'amount', 'deducted_amount', 'remaining_balance', 'deduction_month', 'status', 'approved_by']
    list_filter = ['status', 'advance_date', 'deduction_month']
    search_fields = ['employee__full_name', 'reason']


@admin.register(SafetyItemIssue)
class SafetyItemIssueAdmin(admin.ModelAdmin):
    list_display = ['employee', 'safety_item', 'issue_date', 'quantity', 'item_value', 'total_value', 'deduction_month', 'deduct_from_salary', 'status']
    list_filter = ['status', 'deduct_from_salary', 'issue_date', 'deduction_month']
    search_fields = ['employee__full_name', 'safety_item']


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['employee', 'date', 'project', 'status', 'remarks']
    list_filter = ['status', 'date']
    search_fields = ['employee__full_name']


@admin.register(PayrollAllowance)
class PayrollAllowanceAdmin(admin.ModelAdmin):
    list_display = ['payroll_entry', 'allowance_name', 'amount']
    search_fields = ['payroll_entry__employee__full_name', 'allowance_name']


@admin.register(PayrollDeduction)
class PayrollDeductionAdmin(admin.ModelAdmin):
    list_display = ['payroll_entry', 'deduction_type', 'amount']
    search_fields = ['payroll_entry__employee__full_name', 'deduction_type']


@admin.register(PayrollAllocation)
class PayrollAllocationAdmin(admin.ModelAdmin):
    list_display = ['payroll_entry', 'project', 'amount', 'created_at']
    list_filter = ['project', 'created_at']
    search_fields = ['payroll_entry__employee__full_name', 'project__project_id']


@admin.register(PayrollProjectCostEntry)
class PayrollProjectCostEntryAdmin(admin.ModelAdmin):
    list_display = ['payroll_entry', 'project', 'amount', 'gl_account', 'created_at']
    list_filter = ['project', 'gl_account', 'created_at']
    search_fields = ['payroll_entry__employee__full_name', 'project__project_id']


@admin.register(PayrollGLEntry)
class PayrollGLEntryAdmin(admin.ModelAdmin):
    list_display = ['payroll_entry', 'entry_type', 'gl_account', 'direction', 'amount', 'created_at']
    list_filter = ['entry_type', 'direction', 'gl_account', 'created_at']
    search_fields = ['payroll_entry__employee__full_name', 'description']


@admin.register(PayrollSettings)
class PayrollSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'default_salary_payable_gl_account', 'default_bank_gl_account',
        'default_epf_expense_gl_account', 'default_epf_payable_gl_account',
        'default_etf_expense_gl_account', 'default_etf_payable_gl_account',
        'updated_at',
    ]

    def has_add_permission(self, request):
        # Singleton: only one PayrollSettings row should ever exist.
        return not PayrollSettings.objects.exists()


@admin.register(BackupSettings)
class BackupSettingsAdmin(admin.ModelAdmin):
    list_display = ['frequency', 'backup_time', 'retention_count', 'auto_backup_enabled', 'storage_location', 'updated_at']

    def has_add_permission(self, request):
        # Singleton: only one BackupSettings row should ever exist.
        return not BackupSettings.objects.exists()


@admin.register(BackupRecord)
class BackupRecordAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'backup_type', 'status', 'db_engine', 'file_size', 'started_at', 'completed_at', 'initiated_by']
    list_filter = ['status', 'backup_type', 'db_engine', 'started_at']
    search_fields = ['file_name', 'initiated_by__username']
    readonly_fields = ['file_name', 'file_path', 'file_size', 'db_engine', 'started_at', 'completed_at']


@admin.register(RestoreLog)
class RestoreLogAdmin(admin.ModelAdmin):
    list_display = ['backup_record', 'status', 'initiated_by', 'started_at', 'completed_at']
    list_filter = ['status', 'started_at']
    readonly_fields = ['backup_record', 'pre_restore_backup', 'started_at', 'completed_at']