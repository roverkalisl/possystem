# Register your models here.
from django.contrib import admin
from .models import Category, Item, Supplier, UserLog, AuditLog, ProjectTransfer
from .models import Quotation, QuotationItem, ProjectBudget, ProjectBudgetLine, ProjectCostActual


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