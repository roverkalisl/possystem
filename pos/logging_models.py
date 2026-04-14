"""
Add these models to pos/models.py at the end of the file
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


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
    model_name = models.CharField(max_length=50)
    object_id = models.CharField(max_length=100)
    object_display = models.CharField(max_length=255, blank=True)
    
    # IP Address
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Change Details
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["-timestamp"]),
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["model_name", "-timestamp"]),
        ]
    
    def __str__(self):
        return f"{self.action.title()} {self.model_name} by {self.user.username if self.user else 'Unknown'}"
