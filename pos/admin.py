# Register your models here.
from django.contrib import admin
from .models import Category, Item, Supplier, UserLog, AuditLog, ProjectTransfer


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