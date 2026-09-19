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
    Shows payment method breakdown and bank balances
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
    )

    # Payment method breakdown using aggregation
    payment_summary = sales.values('payment_method').annotate(
        total=Sum('grand_total'),
        count=Count('id')
    ).order_by('payment_method')

    # Prepare summary by payment method
    cash_sales = Decimal('0')
    card_sales = Decimal('0')
    credit_sales = Decimal('0')
    bank_transfer_sales = Decimal('0')

    for summary in payment_summary:
        amount = Decimal(str(summary['total'] or 0))
        if summary['payment_method'] == 'cash':
            cash_sales = amount
        elif summary['payment_method'] == 'card':
            card_sales = amount
        elif summary['payment_method'] == 'credit':
            credit_sales = amount
        elif summary['payment_method'] == 'bank_transfer':
            bank_transfer_sales = amount

    total_sales = cash_sales + card_sales + credit_sales + bank_transfer_sales

    # Get payment transactions for table (limit to recent 100)
    transactions = sales.select_related(
        'customer', 'bank_account'
    ).order_by('-created_at')[:100]

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

        # Get ledger entries for the account in the date range
        ledger_entries = BankLedgerEntry.objects.filter(
            bank_account=account,
            entry_date__gte=from_date,
            entry_date__lte=to_date
        )

        deposits = Decimal(str(
            ledger_entries.filter(
                transaction_type__in=['deposit', 'transfer_in']
            ).aggregate(
                total=Sum('debit')
            )['total'] or 0
        ))

        withdrawals = Decimal(str(
            ledger_entries.filter(
                transaction_type__in=['withdrawal', 'cheque', 'bank_transfer']
            ).aggregate(
                total=Sum('credit')
            )['total'] or 0
        ))

        bank_data.append({
            'account': account,
            'bank_name': account.bank_name,
            'branch': account.branch,
            'account_name': account.account_name,
            'account_number_masked': f"****{account.account_number[-4:]}" if len(account.account_number) > 4 else account.account_number,
            'current_balance': current_balance,
            'deposits': deposits,
            'withdrawals': withdrawals,
        })

    context = {
        'from_date': from_date,
        'to_date': to_date,
        'cash_sales': cash_sales,
        'card_sales': card_sales,
        'credit_sales': credit_sales,
        'bank_transfer_sales': bank_transfer_sales,
        'total_sales': total_sales,
        'total_bank_balance': total_bank_balance,
        'bank_accounts': bank_data,
        'transactions': transactions,
        'payment_summary': payment_summary,
    }

    return render(request, 'pos/payment_summary_dashboard.html', context)
