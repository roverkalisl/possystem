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


@register.filter
def profit_per_unit(cost_price, selling_price):
    """Calculate profit per unit (selling_price - cost_price)"""
    try:
        cost = Decimal(str(cost_price)) if cost_price else Decimal("0")
        selling = Decimal(str(selling_price)) if selling_price else Decimal("0")
        return selling - cost
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


@register.filter
def stock_value(cost_price, stock):
    """Calculate total stock value (cost_price * stock)"""
    try:
        cost = Decimal(str(cost_price)) if cost_price else Decimal("0")
        qty = Decimal(str(stock)) if stock else Decimal("0")
        return cost * qty
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


@register.filter
def mul(value, arg):
    """Multiply two numbers"""
    try:
        return Decimal(str(value)) * Decimal(str(arg))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


@register.filter
def subtract(value, arg):
    """Subtract two numbers (value - arg)"""
    try:
        return Decimal(str(value)) - Decimal(str(arg))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")

