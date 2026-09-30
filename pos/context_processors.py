from .company_context import get_active_company
from .models import Company


def active_company(request):
    """Exposes active_company / switchable_companies to every template."""
    if not getattr(request.user, "is_authenticated", False):
        return {}
    return {
        "active_company": get_active_company(request),
        "switchable_companies": Company.objects.filter(is_active=True).order_by("company_code"),
    }
