from decimal import Decimal, InvalidOperation
from django import template
from django.conf import settings

register = template.Library()

@register.filter
def money(value):
    try:
        if value in (None, ""):
            value = Decimal("0")
        value = Decimal(str(value))
        symbol = getattr(settings, 'CURRENCY_SYMBOL', '$')
        return f"{symbol} {value:,.2f}"
    except (InvalidOperation, ValueError, TypeError):
        symbol = getattr(settings, 'CURRENCY_SYMBOL', '$')
        return f"{symbol} 0.00"