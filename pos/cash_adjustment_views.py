"""
Cash Adjustment Views - Manual Cash Balance Adjustments
Read-only for historical records, controlled workflow for new adjustments.
"""
from decimal import Decimal
from datetime import datetime
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages

from .models import CashAdjustment
from .payment_summary_views import (
    COUNTED_ADJUSTMENT_STATUSES,
    get_cash_balance_breakdown,
    get_current_cash_balance,
)


def can_manage_cash_adjustment(user):
    """Check if user can create/approve cash adjustments."""
    return user.is_superuser or user.is_staff


def generate_adjustment_reference():
    """Generate unique reference like CA-20260922-0001"""
    today = timezone.now().date()
    date_str = today.strftime('%Y%m%d')

    # Find last adjustment for today
    last_adj = CashAdjustment.objects.filter(
        reference__startswith=f'CA-{date_str}'
    ).order_by('id').last()

    if last_adj:
        # Extract sequence number and increment
        seq = int(last_adj.reference.split('-')[-1]) + 1
    else:
        seq = 1

    return f'CA-{date_str}-{seq:04d}'


@login_required
@user_passes_test(can_manage_cash_adjustment)
def cash_adjustment_list(request):
    """List all cash adjustments with approval status."""
    adjustments = CashAdjustment.objects.all()

    # Filter by status if requested
    status_filter = request.GET.get('status', '')
    if status_filter:
        adjustments = adjustments.filter(approval_status=status_filter)

    cash_breakdown = get_cash_balance_breakdown()

    context = {
        'adjustments': adjustments,
        'current_cash': cash_breakdown['balance'],
        'cash_breakdown': cash_breakdown,
        'status_filter': status_filter,
    }

    return render(request, 'pos/cash_adjustment_list.html', context)


@login_required
@user_passes_test(can_manage_cash_adjustment)
def create_cash_adjustment(request):
    """Create a new cash adjustment (Draft status)."""
    current_cash = get_current_cash_balance()

    if request.method == 'POST':
        adjustment_date = request.POST.get('adjustment_date')
        adjustment_type = request.POST.get('adjustment_type')
        amount = request.POST.get('amount')
        reason = request.POST.get('reason')

        try:
            adjustment = CashAdjustment.objects.create(
                adjustment_date=adjustment_date,
                adjustment_type=adjustment_type,
                amount=Decimal(amount),
                reason=reason,
                reference=generate_adjustment_reference(),
                approval_status='pending',
                created_by=request.user,
            )
            messages.success(request, f'Cash adjustment {adjustment.reference} created successfully.')
            return redirect('cash_adjustment_detail', pk=adjustment.id)
        except Exception as e:
            messages.error(request, f'Error creating adjustment: {str(e)}')

    context = {
        'current_cash': current_cash,
    }

    return render(request, 'pos/cash_adjustment_form.html', context)


@login_required
@user_passes_test(can_manage_cash_adjustment)
def cash_adjustment_detail(request, pk):
    """View cash adjustment details and approve/post."""
    adjustment = get_object_or_404(CashAdjustment, pk=pk)
    current_cash = get_current_cash_balance()

    # Approved/posted adjustments are already inside current_cash
    if adjustment.approval_status in COUNTED_ADJUSTMENT_STATUSES:
        preview_cash = current_cash
    elif adjustment.adjustment_type == 'cash_increase':
        preview_cash = current_cash + adjustment.amount
    else:
        preview_cash = current_cash - adjustment.amount

    context = {
        'adjustment': adjustment,
        'current_cash': current_cash,
        'preview_cash': preview_cash,
    }

    return render(request, 'pos/cash_adjustment_detail.html', context)


@login_required
@user_passes_test(can_manage_cash_adjustment)
def approve_cash_adjustment(request, pk):
    """Approve a cash adjustment (Pending → Approved)."""
    adjustment = get_object_or_404(CashAdjustment, pk=pk)

    if adjustment.approval_status != 'pending':
        messages.error(request, 'Only pending adjustments can be approved.')
        return redirect('cash_adjustment_detail', pk=pk)

    adjustment.approval_status = 'approved'
    adjustment.approved_by = request.user
    adjustment.approved_at = timezone.now()
    adjustment.save()

    messages.success(request, f'Cash adjustment {adjustment.reference} approved.')
    return redirect('cash_adjustment_detail', pk=pk)


@login_required
@user_passes_test(can_manage_cash_adjustment)
def post_cash_adjustment(request, pk):
    """Post a cash adjustment (Approved → Posted)."""
    adjustment = get_object_or_404(CashAdjustment, pk=pk)

    if adjustment.approval_status != 'approved':
        messages.error(request, 'Only approved adjustments can be posted.')
        return redirect('cash_adjustment_detail', pk=pk)

    adjustment.approval_status = 'posted'
    adjustment.posted_at = timezone.now()
    adjustment.save()

    messages.success(request, f'Cash adjustment {adjustment.reference} posted successfully.')
    return redirect('cash_adjustment_detail', pk=pk)
