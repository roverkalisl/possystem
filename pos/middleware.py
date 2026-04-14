"""
Middleware for logging user login and logout activity
"""
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import AnonymousUser
from pos.models import UserLog


def get_client_ip(request):
    """Extract client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip


class UserActivityMiddleware(MiddlewareMixin):
    """Track user login/logout activity"""
    
    def process_request(self, request):
        # Store the current user in session before the request is processed
        request.user_before = getattr(request, 'user', None)
        return None
    
    def process_response(self, request, response):
        """Log user login/logout by comparing user before and after request"""
        
        user_before = getattr(request, 'user_before', None)
        user_after = getattr(request, 'user', None)
        
        # Skip if no user information available
        if isinstance(user_before, AnonymousUser) and isinstance(user_after, AnonymousUser):
            return response
        
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Detect login (transition from anonymous to authenticated)
        if isinstance(user_before, AnonymousUser) and not isinstance(user_after, AnonymousUser):
            try:
                UserLog.objects.create(
                    user=user_after,
                    action='login',
                    ip_address=ip_address,
                    user_agent=user_agent
                )
            except Exception:
                pass
        
        # Detect logout (transition from authenticated to anonymous)
        elif not isinstance(user_before, AnonymousUser) and isinstance(user_after, AnonymousUser):
            try:
                UserLog.objects.create(
                    user=user_before,
                    action='logout',
                    ip_address=ip_address,
                    user_agent=user_agent
                )
            except Exception:
                pass
        
        return response
