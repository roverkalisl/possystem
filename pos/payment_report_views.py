"""
POS Payment Report - Continuous Transaction-Level Report
Read-only reporting of individual payment transactions.
"""
from decimal import Decimal
from datetime import datetime
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Sum, Q
from django.shortcuts import render
from django.utils import timezone

from .models import Sale, BankAccount, BankLedgerEntry


def can_view_payment_report(user):
    """Check if user can view payment report."""
    return user.is_superuser or user.is_staff


@login_required
@user_passes_test(can_view_payment_report)
def payment_report(request):
    """
    POS Payment Report - Transaction-level continuous report
    Shows each payment transaction as an individual row.
    """
    # Get filter parameters
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    invoice_no = request.GET.get('invoice_no', '').strip()
    customer = request.GET.get('customer', '').strip()
    payment_method = request.GET.get('payment_method', '').strip()
    bank_account = request.GET.get('bank_account', '').strip()
    search = request.GET.get('search', '').strip()
    page = request.GET.get('page', 1)

    # Set default dates
    today = timezone.now().date()
    if not from_date:
        from_date = (today.replace(day=1) if today.day > 1 else today - timezone.timedelta(days=30))
    else:
        from_date = datetime.strptime(from_date, '%Y-%m-%d').date()

    if not to_date:
        to_date = today
    else:
        to_date = datetime.strptime(to_date, '%Y-%m-%d').date()

    # Ensure valid date range
    if from_date > to_date:
        from_date, to_date = to_date, from_date

    # Build query filters
    transactions = Sale.objects.filter(
        created_at__date__gte=from_date,
        created_at__date__lte=to_date
    ).select_related('customer', 'bank_account').order_by('-created_at')

    # Apply additional filters
    if invoice_no:
        transactions = transactions.filter(invoice_no__icontains=invoice_no)

    if customer:
        transactions = transactions.filter(
            Q(customer_name__icontains=customer) |
            Q(customer__name__icontains=customer)
        )

    if payment_method:
        transactions = transactions.filter(payment_method=payment_method)

    if bank_account:
        transactions = transactions.filter(bank_account_id=bank_account)

    if search:
        transactions = transactions.filter(
            Q(invoice_no__icontains=search) |
            Q(customer_name__icontains=search) |
            Q(bank_transfer_reference__icontains=search)
        )

    # Calculate report totals for filtered records
    totals = transactions.aggregate(
        cash_total=Sum('grand_total', filter=Q(payment_method='cash')),
        card_total=Sum('grand_total', filter=Q(payment_method='card')),
        credit_total=Sum('grand_total', filter=Q(payment_method='credit')),
        transfer_total=Sum('grand_total', filter=Q(payment_method='bank_transfer')),
    )

    cash_total = Decimal(str(totals['cash_total'] or 0))
    card_total = Decimal(str(totals['card_total'] or 0))
    credit_total = Decimal(str(totals['credit_total'] or 0))
    transfer_total = Decimal(str(totals['transfer_total'] or 0))
    grand_total = cash_total + card_total + credit_total + transfer_total

    # Pagination
    paginator = Paginator(transactions, 50)  # 50 rows per page
    try:
        transactions_page = paginator.page(page)
    except PageNotAnInteger:
        transactions_page = paginator.page(1)
    except EmptyPage:
        transactions_page = paginator.page(paginator.num_pages)

    # Get available bank accounts for filter dropdown
    bank_accounts = BankAccount.objects.filter(
        is_active=True,
        is_deleted=False
    ).order_by('bank_name', 'account_name')

    # Get current bank balances
    bank_balances = []
    total_bank_balance = Decimal('0')

    for account in bank_accounts:
        current_balance = account.get_current_balance()
        total_bank_balance += current_balance
        bank_balances.append({
            'account': account,
            'balance': current_balance,
        })

    # Prepare payment methods for filter dropdown
    payment_methods = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('credit', 'Credit'),
        ('bank_transfer', 'Bank Transfer'),
    ]

    context = {
        'from_date': from_date,
        'to_date': to_date,
        'invoice_no': invoice_no,
        'customer': customer,
        'payment_method': payment_method,
        'bank_account': bank_account,
        'search': search,
        'transactions': transactions_page,
        'bank_balances': bank_balances,
        'total_bank_balance': total_bank_balance,
        'cash_total': cash_total,
        'card_total': card_total,
        'credit_total': credit_total,
        'transfer_total': transfer_total,
        'grand_total': grand_total,
        'bank_accounts': bank_accounts,
        'payment_methods': payment_methods,
        'paginator': paginator,
    }

    return render(request, 'pos/payment_report.html', context)
