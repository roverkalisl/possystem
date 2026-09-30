"""
Phase 2.2 - Multi-Company context foundation.

The "active Company" is stored in the user's session only
(request.session["active_company_id"]) - not on the User model, not on
any transaction table. get_active_company() is the single place that
resolves it safely.
"""
from .models import Company

ACTIVE_COMPANY_SESSION_KEY = "active_company_id"


def get_active_company(request):
    """
    Returns the currently active Company for this session, or None.

    Resolution order:
    1. A valid, active Company referenced by the session.
    2. If the session has no selection (or the referenced Company is
       missing/inactive), fall back to the sole active Company if
       exactly one exists.
    3. Otherwise None - callers must require an explicit selection.

    A stale session value (deleted/deactivated Company, or a malformed
    id) is cleared rather than left to raise on the next request.
    """
    company_id = request.session.get(ACTIVE_COMPANY_SESSION_KEY)

    if company_id:
        try:
            return Company.objects.get(id=company_id, is_active=True)
        except (Company.DoesNotExist, ValueError, TypeError):
            request.session.pop(ACTIVE_COMPANY_SESSION_KEY, None)

    active_companies = Company.objects.filter(is_active=True)
    if active_companies.count() == 1:
        return active_companies.first()

    return None


def set_active_company(request, company):
    """company may be None to clear the selection (""All Companies")."""
    if company is None:
        request.session.pop(ACTIVE_COMPANY_SESSION_KEY, None)
    else:
        request.session[ACTIVE_COMPANY_SESSION_KEY] = company.id


def resolve_company_filter(request):
    """
    Resolves the company_id filter value for a GET-based report (Phase
    4.2-A). An explicit request.GET["company_id"] takes precedence -
    including an explicit empty value, meaning the user chose "All
    Companies" - otherwise falls back to the active session Company via
    get_active_company(). Returns an int id or None. Read-only: makes no
    session or database writes.
    """
    if "company_id" in request.GET:
        return request.GET.get("company_id") or None
    active_company = get_active_company(request)
    return active_company.id if active_company else None
