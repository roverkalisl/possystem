# Register your models here.
from django.contrib import admin
from .models import Category, Item, Supplier, UserLog, AuditLog


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


admin.site.register(Category)
admin.site.register(Item)
admin.site.register(Supplier)