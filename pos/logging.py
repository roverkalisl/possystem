"""
User and Audit Logging System
Captures login/logout activity and audit trail for all model changes
"""
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import json


class UserLog(models.Model):
    """Log for user login/logout activity"""
    
    ACTION_CHOICES = [
        ("login", "Login"),
        ("logout", "Logout"),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_logs")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["-timestamp"]),
            models.Index(fields=["user", "-timestamp"]),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.action} at {self.timestamp}"


class AuditLog(models.Model):
    """Audit trail for all model changes"""
    
    ACTION_CHOICES = [
        ("create", "Created"),
        ("update", "Updated"),
        ("delete", "Deleted"),
        ("view", "Viewed"),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Model Information
    model_name = models.CharField(max_length=50)  # e.g., "Sale", "Customer"
    object_id = models.CharField(max_length=100)  # Primary key of the object
    object_display = models.CharField(max_length=255, blank=True)  # Human-readable object name
    
    # IP Address
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Change Details
    old_values = models.JSONField(null=True, blank=True)  # Previous field values
    new_values = models.JSONField(null=True, blank=True)  # New field values
    notes = models.TextField(blank=True, null=True)  # Additional notes
    
    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["-timestamp"]),
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["model_name", "-timestamp"]),
        ]
    
    def __str__(self):
        return f"{self.action.title()} {self.model_name} by {self.user.username if self.user else 'Unknown'} at {self.timestamp}"
    
    def get_changes_display(self):
        """Return human-readable format of changes"""
        if not self.old_values and not self.new_values:
            return "No changes recorded"
        
        changes = []
        if self.action == "create":
            return "Record created with initial values"
        elif self.action == "update":
            new_vals = self.new_values or {}
            old_vals = self.old_values or {}
            for key, new_value in new_vals.items():
                old_value = old_vals.get(key)
                if old_value != new_value:
                    changes.append(f"{key}: {old_value} → {new_value}")
            return " | ".join(changes) if changes else "No changes"
        elif self.action == "delete":
            return "Record deleted"
        
        return str(self.new_values)


def get_client_ip(request):
    """Extract client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request):
    """Extract user agent from request"""
    return request.META.get('HTTP_USER_AGENT', '')


def log_audit(user, action, model_name, object_id, object_display, ip_address=None, old_values=None, new_values=None, notes=None):
    """Create an audit log entry"""
    AuditLog.objects.create(
        user=user,
        action=action,
        model_name=model_name,
        object_id=str(object_id),
        object_display=object_display[:255] if object_display else "",
        ip_address=ip_address,
        old_values=old_values,
        new_values=new_values,
        notes=notes
    )


def serialize_values(instance, fields=None):
    """Convert model instance fields to JSON-serializable dictionary"""
    result = {}
    
    if fields is None:
        fields = [f.name for f in instance._meta.get_fields() 
                 if not f.many_to_one and not f.many_to_many and not f.one_to_many]
    
    for field_name in fields:
        try:
            value = getattr(instance, field_name, None)
            # Convert non-JSON-serializable types
            if isinstance(value, (int, str, float, bool, type(None))):
                result[field_name] = value
            elif isinstance(value, Decimal):
                result[field_name] = float(value)
            elif hasattr(value, 'isoformat'):
                result[field_name] = value.isoformat()
            else:
                result[field_name] = str(value)
        except Exception:
            pass
    
    return result
