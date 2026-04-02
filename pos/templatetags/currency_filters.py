from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()

@register.filter
def money(value):
    try:
        if value in (None, ""):
            value = Decimal("0")
        value = Decimal(str(value))
        return f"{value:,.2f}"
    except (InvalidOperation, ValueError, TypeError):
        return "0.00"