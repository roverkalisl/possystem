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

from .models import Sale, BankAccount, BankLedgerEntry


def can_view_payment_summary(user):
    """Check if user can view payment summary."""
    return user.is_superuser or user.is_staff


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

    # Bank Accounts and Balances
    bank_accounts = BankAccount.objects.filter(
        is_active=True,
        is_deleted=False
    ).order_by('bank_name', 'account_name')

    bank_data = []
    total_bank_balance = Decimal('0')

    for account in bank_accounts:
        current_balance = account.get_current_balance()
        total_bank_balance += current_balance

        bank_data.append({
            'account': account,
            'bank_name': account.bank_name,
            'branch': account.branch,
            'account_name': account.account_name,
            'account_number_masked': f"****{account.account_number[-4:]}" if len(account.account_number) > 4 else account.account_number,
            'current_balance': current_balance,
        })

    context = {
        'from_date': from_date,
        'to_date': to_date,
        'date_summary': date_summary,
        'period_totals': period_totals,
        'period_grand_total': period_grand_total,
        'total_bank_balance': total_bank_balance,
        'bank_accounts': bank_data,
    }

    return render(request, 'pos/payment_summary_dashboard.html', context)
