"""
POS Payment Summary Dashboard
Reporting module for payment methods and bank balances.
Read-only - no modifications to financial data.
"""
from decimal import Decimal
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Count, Q
from django.shortcuts import render
from django.utils import timezone

from .models import Sale, CashAdjustment


def can_view_payment_summary(user):
    """Check if user can view payment summary."""
    return user.is_superuser or user.is_staff


def get_current_cash_balance():
    """Calculate current cash balance from sales + posted adjustments."""
    cash_sales = Sale.objects.filter(
        payment_method='cash'
    ).aggregate(total=Sum('grand_total'))['total'] or Decimal('0')

    adjustments = CashAdjustment.objects.filter(
        approval_status='posted'
    ).aggregate(
        increases=Sum('amount', filter=Q(adjustment_type='cash_increase')),
        decreases=Sum('amount', filter=Q(adjustment_type='cash_decrease'))
    )

    increase_total = Decimal(str(adjustments['increases'] or 0))
    decrease_total = Decimal(str(adjustments['decreases'] or 0))

    return Decimal(str(cash_sales)) + increase_total - decrease_total


@login_required
@user_passes_test(can_view_payment_summary)
def payment_summary_dashboard(request):
    """
    POS Payment Summary Dashboard
    Shows date-wise payment method breakdown and bank balances
    """
    # Get date parameters
    today = timezone.now().date()
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')

    # Default to current month if not specified
    if not from_date:
        from_date = today.replace(day=1)
    else:
        from_date = datetime.strptime(from_date, '%Y-%m-%d').date()

    if not to_date:
        to_date = today
    else:
        to_date = datetime.strptime(to_date, '%Y-%m-%d').date()

    # Ensure valid date range
    if from_date > to_date:
        from_date, to_date = to_date, from_date

    # Filter sales by date range
    sales = Sale.objects.filter(
        created_at__date__gte=from_date,
        created_at__date__lte=to_date
    ).order_by('created_at__date')

    # Date-wise summary - group by date and payment method
    date_wise_data = {}
    period_totals = {
        'cash': Decimal('0'),
        'card': Decimal('0'),
        'credit': Decimal('0'),
        'bank_transfer': Decimal('0'),
        'cheque': Decimal('0'),
    }

    for sale in sales:
        sale_date = sale.created_at.date()
        if sale_date not in date_wise_data:
            date_wise_data[sale_date] = {
                'date': sale_date,
                'cash': Decimal('0'),
                'card': Decimal('0'),
                'credit': Decimal('0'),
                'bank_transfer': Decimal('0'),
                'cheque': Decimal('0'),
            }

        amount = Decimal(str(sale.grand_total or 0))
        payment_method = sale.payment_method

        # Map cheque payments (stored as payment_method or cheque_number field)
        if payment_method == 'cheque' or (payment_method and sale.cheque_number):
            date_wise_data[sale_date]['cheque'] += amount
            period_totals['cheque'] += amount
        elif payment_method in date_wise_data[sale_date]:
            date_wise_data[sale_date][payment_method] += amount
            period_totals[payment_method] += amount

    # Convert to sorted list
    date_summary = []
    for sale_date in sorted(date_wise_data.keys()):
        row = date_wise_data[sale_date]
        daily_total = (
            row['cash'] + row['card'] + row['credit'] +
            row['bank_transfer'] + row['cheque']
        )
        row['total'] = daily_total
        date_summary.append(row)

    # Calculate period grand total
    period_grand_total = sum(period_totals.values())

    # Get current cash balance (includes posted adjustments)
    current_cash = get_current_cash_balance()

    context = {
        'from_date': from_date,
        'to_date': to_date,
        'date_summary': date_summary,
        'period_totals': period_totals,
        'period_grand_total': period_grand_total,
        'current_cash': current_cash,
    }

    return render(request, 'pos/payment_summary_dashboard.html', context)
