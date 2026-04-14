"""
Views for user logging and audit trail
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse
from django.db.models import Q
from datetime import datetime, timedelta
from django.utils import timezone
from pos.models import UserLog, AuditLog


@login_required
def user_activity_log(request):
    """Display user login/logout activity log"""
    
    # Get filter parameters
    user_filter = request.GET.get('user', '')
    action_filter = request.GET.get('action', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Start with all logs
    logs = UserLog.objects.all()
    
    # Apply filters
    if user_filter:
        logs = logs.filter(user__username__icontains=user_filter)
    
    if action_filter:
        logs = logs.filter(action=action_filter)
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
            logs = logs.filter(timestamp__date__gte=from_date.date())
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d')
            logs = logs.filter(timestamp__date__lte=to_date.date())
        except ValueError:
            pass
    
    # Get summary statistics
    total_logins = logs.filter(action='login').count()
    total_logouts = logs.filter(action='logout').count()
    today_logins = logs.filter(action='login', timestamp__date=timezone.now().date()).count()
    
    # Paginate
    page_num = request.GET.get('page', 1)
    page_size = 50
    start = (int(page_num) - 1) * page_size
    end = start + page_size
    
    logs_page = logs[start:end]
    total_pages = (logs.count() + page_size - 1) // page_size
    
    context = {
        'logs': logs_page,
        'total_logs': logs.count(),
        'total_logins': total_logins,
        'total_logouts': total_logouts,
        'today_logins': today_logins,
        'current_page': int(page_num),
        'total_pages': total_pages,
        'has_filters': bool(user_filter or action_filter or date_from or date_to),
        'filter_user': user_filter,
        'filter_action': action_filter,
        'filter_date_from': date_from,
        'filter_date_to': date_to,
    }
    
    return render(request, 'pos/user_activity_log.html', context)


@login_required
def audit_trail(request):
    """Display audit trail for all model changes"""
    
    # Get filter parameters
    user_filter = request.GET.get('user', '')
    model_filter = request.GET.get('model', '')
    action_filter = request.GET.get('action', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Start with all audit logs
    logs = AuditLog.objects.all()
    
    # Apply filters
    if user_filter:
        logs = logs.filter(user__username__icontains=user_filter)
    
    if model_filter:
        logs = logs.filter(model_name=model_filter)
    
    if action_filter:
        logs = logs.filter(action=action_filter)
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
            logs = logs.filter(timestamp__date__gte=from_date.date())
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d')
            logs = logs.filter(timestamp__date__lte=to_date.date())
        except ValueError:
            pass
    
    # Get summary statistics
    total_creates = logs.filter(action='create').count()
    total_updates = logs.filter(action='update').count()
    total_deletes = logs.filter(action='delete').count()
    today_changes = logs.filter(timestamp__date=timezone.now().date()).count()
    
    # Get unique models
    unique_models = logs.values_list('model_name', flat=True).distinct()
    
    # Paginate
    page_num = request.GET.get('page', 1)
    page_size = 50
    start = (int(page_num) - 1) * page_size
    end = start + page_size
    
    logs_page = logs[start:end]
    total_pages = (logs.count() + page_size - 1) // page_size
    
    context = {
        'logs': logs_page,
        'total_logs': logs.count(),
        'total_creates': total_creates,
        'total_updates': total_updates,
        'total_deletes': total_deletes,
        'today_changes': today_changes,
        'unique_models': sorted(unique_models),
        'current_page': int(page_num),
        'total_pages': total_pages,
        'has_filters': bool(user_filter or model_filter or action_filter or date_from or date_to),
        'filter_user': user_filter,
        'filter_model': model_filter,
        'filter_action': action_filter,
        'filter_date_from': date_from,
        'filter_date_to': date_to,
    }
    
    return render(request, 'pos/audit_trail.html', context)


@login_required
def audit_detail(request, log_id):
    """Display detailed audit log entry"""
    
    log = AuditLog.objects.get(id=log_id)
    
    context = {
        'log': log,
        'changes': log.get_changes_display() if hasattr(log, 'get_changes_display') else 'No changes recorded',
    }
    
    return render(request, 'pos/audit_detail.html', context)
