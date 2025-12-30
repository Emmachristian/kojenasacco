# dividends/views.py - Dividends Module Views
"""
Dividends module views following Django best practices.
Organized by functionality with proper separation of concerns.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg, Prefetch
from django.utils import timezone
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from datetime import timedelta
from decimal import Decimal
import logging

from .models import (
    DividendPeriod, 
    MemberDividend, 
    DividendRate, 
    DividendDisbursement, 
    DividendPayment, 
    DividendPreference
)
from .forms import (
    DividendPeriodForm, 
    DividendPeriodApprovalForm, 
    MemberDividendForm,
    BulkDividendCalculationForm, 
    DividendRateForm, 
    DividendDisbursementForm,
    BatchDisbursementForm, 
    DividendPaymentForm, 
    PaymentConfirmationForm,
    PaymentFailureForm, 
    DividendPreferenceForm, 
    MemberDividendPreferenceForm,
    DividendReportForm, 
    DividendPeriodFilterForm, 
    MemberDividendFilterForm,
    DividendDisbursementFilterForm, 
    DividendPaymentFilterForm
)
from . import stats as dividend_stats
from members.models import Member
from savings.models import SavingsAccount
from core.utils import format_money

logger = logging.getLogger(__name__)


# =============================================================================
# DASHBOARD VIEWS
# =============================================================================

@login_required
def dividends_dashboard(request):
    """
    Main dividends dashboard displaying overview statistics.
    Aggregates data from stats module for comprehensive view.
    """
    try:
        today = timezone.now().date()
        one_year_ago = today - timedelta(days=365)
        
        # Fetch statistics from stats module
        overview = dividend_stats.get_dividend_overview(one_year_ago, today)
        period_stats = dividend_stats.get_dividend_period_statistics()
        member_stats = dividend_stats.get_member_dividend_statistics()
        
    except Exception as e:
        logger.error(f"Dashboard stats error: {e}", exc_info=True)
        overview = {}
        period_stats = {}
        member_stats = {}
    
    # Fetch recent activity data
    recent_periods = DividendPeriod.objects.select_related(
        'financial_period'
    ).order_by('-created_at')[:10]
    
    pending_approvals = DividendPeriod.objects.filter(
        status='CALCULATED', 
        is_approved=False
    ).select_related('financial_period')[:10]
    
    active_disbursements = DividendDisbursement.objects.filter(
        status__in=['PENDING', 'PROCESSING']
    ).select_related('dividend_period')[:10]
    
    context = {
        'overview': overview,
        'period_stats': period_stats,
        'member_stats': member_stats,
        'recent_periods': recent_periods,
        'pending_approvals': pending_approvals,
        'active_disbursements': active_disbursements,
    }
    
    return render(request, 'dividends/dashboard.html', context)


# =============================================================================
# DIVIDEND PERIOD VIEWS
# =============================================================================

@login_required
def period_list(request):
    """
    List all dividend periods with filtering capability.
    HTMX loads paginated data dynamically.
    """
    filter_form = DividendPeriodFilterForm()
    
    try:
        initial_stats = dividend_stats.get_dividend_period_statistics()
    except Exception as e:
        logger.error(f"Period stats error: {e}", exc_info=True)
        initial_stats = {}
    
    context = {
        'filter_form': filter_form,
        'stats': initial_stats
    }
    
    return render(request, 'dividends/periods/list.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def period_create(request):
    """Create new dividend period."""
    if request.method == "POST":
        form = DividendPeriodForm(request.POST)
        
        if form.is_valid():
            try:
                period = form.save()
                messages.success(
                    request, 
                    f"Period '{period.name}' created successfully", 
                    extra_tags='sweetalert'
                )
                return redirect("dividends:period_detail", pk=period.pk)
                
            except Exception as e:
                logger.error(f"Period creation error: {e}", exc_info=True)
                messages.error(
                    request, 
                    "An error occurred while creating the period", 
                    extra_tags='sweetalert-error'
                )
        else:
            messages.error(
                request, 
                "Please correct the errors below", 
                extra_tags='sweetalert-error'
            )
    else:
        form = DividendPeriodForm()
    
    context = {
        'form': form,
        'title': 'Create Dividend Period'
    }
    
    return render(request, 'dividends/periods/form.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def period_edit(request, pk):
    """Edit existing dividend period."""
    period = get_object_or_404(DividendPeriod, pk=pk)
    
    # Check if period can be edited
    if not period.can_be_edited:
        messages.error(
            request, 
            "This period cannot be edited in its current state", 
            extra_tags='sweetalert'
        )
        return redirect("dividends:period_detail", pk=pk)
    
    if request.method == "POST":
        form = DividendPeriodForm(request.POST, instance=period)
        
        if form.is_valid():
            try:
                period = form.save()
                messages.success(
                    request, 
                    f"Period '{period.name}' updated successfully", 
                    extra_tags='sweetalert'
                )
                return redirect("dividends:period_detail", pk=pk)
                
            except Exception as e:
                logger.error(f"Period update error: {e}", exc_info=True)
                messages.error(
                    request, 
                    "An error occurred while updating the period", 
                    extra_tags='sweetalert-error'
                )
        else:
            messages.error(
                request, 
                "Please correct the errors below", 
                extra_tags='sweetalert-error'
            )
    else:
        form = DividendPeriodForm(instance=period)
    
    context = {
        'form': form,
        'period': period,
        'title': 'Edit Dividend Period'
    }
    
    return render(request, 'dividends/periods/form.html', context)


@login_required
def period_detail(request, pk):
    """
    View detailed information about a dividend period.
    Includes performance statistics and related data.
    """
    period = get_object_or_404(
        DividendPeriod.objects.prefetch_related('dividend_rates')
                              .select_related('financial_period'), 
        pk=pk
    )
    
    # Fetch performance data
    try:
        performance_data = dividend_stats.get_dividend_period_performance(str(period.id))
        performance = performance_data['breakdown'][0] if performance_data.get('breakdown') else {}
    except Exception as e:
        logger.error(f"Performance data error: {e}", exc_info=True)
        performance = {}
    
    # Get active dividend rates
    dividend_rates = period.dividend_rates.filter(is_active=True).order_by('min_balance')
    
    # Get recent disbursements
    disbursements = period.disbursements.select_related(
        'dividend_period'
    ).order_by('-disbursement_date')[:10]
    
    context = {
        'period': period,
        'performance': performance,
        'dividend_rates': dividend_rates,
        'disbursements': disbursements,
    }
    
    return render(request, 'dividends/periods/detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def period_approve(request, pk):
    """Approve a calculated dividend period."""
    period = get_object_or_404(DividendPeriod, pk=pk)
    
    if request.method == 'POST':
        form = DividendPeriodApprovalForm(request.POST)
        
        if form.is_valid():
            try:
                success, message = period.approve()
                
                if success:
                    messages.success(request, message, extra_tags='sweetalert')
                else:
                    messages.error(request, message, extra_tags='sweetalert')
                    
                return redirect('dividends:period_detail', pk=pk)
                
            except Exception as e:
                logger.error(f"Period approval error: {e}", exc_info=True)
                messages.error(
                    request, 
                    "An error occurred during approval", 
                    extra_tags='sweetalert'
                )
    else:
        form = DividendPeriodApprovalForm()
    
    context = {
        'form': form,
        'period': period
    }
    
    return render(request, 'dividends/periods/approve.html', context)


# =============================================================================
# DIVIDEND RATE VIEWS
# =============================================================================

@login_required
@require_http_methods(["GET", "POST"])
def rate_create(request, period_pk):
    """Create new dividend rate for a period."""
    period = get_object_or_404(DividendPeriod, pk=period_pk)
    
    if request.method == 'POST':
        form = DividendRateForm(request.POST)
        
        if form.is_valid():
            try:
                rate = form.save(commit=False)
                rate.dividend_period = period
                rate.save()
                
                messages.success(
                    request, 
                    f"Rate '{rate.tier_name}' added successfully", 
                    extra_tags='sweetalert'
                )
                return redirect('dividends:period_detail', pk=period.pk)
                
            except Exception as e:
                logger.error(f"Rate creation error: {e}", exc_info=True)
                messages.error(
                    request, 
                    "An error occurred while creating the rate", 
                    extra_tags='sweetalert-error'
                )
        else:
            messages.error(
                request, 
                "Please correct the errors below", 
                extra_tags='sweetalert-error'
            )
    else:
        form = DividendRateForm(initial={'dividend_period': period})
    
    context = {
        'form': form,
        'period': period,
        'title': 'Add Dividend Rate'
    }
    
    return render(request, 'dividends/rates/form.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def rate_edit(request, pk):
    """Edit existing dividend rate."""
    rate = get_object_or_404(DividendRate.objects.select_related('dividend_period'), pk=pk)
    
    if request.method == 'POST':
        form = DividendRateForm(request.POST, instance=rate)
        
        if form.is_valid():
            try:
                rate = form.save()
                messages.success(
                    request, 
                    f"Rate '{rate.tier_name}' updated successfully", 
                    extra_tags='sweetalert'
                )
                return redirect('dividends:period_detail', pk=rate.dividend_period.pk)
                
            except Exception as e:
                logger.error(f"Rate update error: {e}", exc_info=True)
                messages.error(
                    request, 
                    "An error occurred while updating the rate", 
                    extra_tags='sweetalert-error'
                )
        else:
            messages.error(
                request, 
                "Please correct the errors below", 
                extra_tags='sweetalert-error'
            )
    else:
        form = DividendRateForm(instance=rate)
    
    context = {
        'form': form,
        'rate': rate,
        'title': 'Edit Dividend Rate'
    }
    
    return render(request, 'dividends/rates/form.html', context)


# =============================================================================
# MEMBER DIVIDEND VIEWS
# =============================================================================

@login_required
def member_dividend_list(request):
    """
    List member dividends with filtering capability.
    HTMX loads paginated data dynamically.
    """
    filter_form = MemberDividendFilterForm()
    
    try:
        initial_stats = dividend_stats.get_member_dividend_statistics()
    except Exception as e:
        logger.error(f"Member dividend stats error: {e}", exc_info=True)
        initial_stats = {}
    
    context = {
        'filter_form': filter_form,
        'stats': initial_stats
    }
    
    return render(request, 'dividends/members/list.html', context)


@login_required
def member_dividend_detail(request, pk):
    """View detailed information about a member's dividend."""
    dividend = get_object_or_404(
        MemberDividend.objects.select_related(
            'member',
            'dividend_period',
            'disbursement_account'
        ), 
        pk=pk
    )
    
    # Get payment history
    payments = dividend.payments.select_related(
        'disbursement'
    ).order_by('-payment_date')[:10]
    
    context = {
        'dividend': dividend,
        'payments': payments
    }
    
    return render(request, 'dividends/members/detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def bulk_dividend_calculation(request):
    """
    Calculate dividends for multiple members in a period.
    Uses transaction to ensure data consistency.
    """
    if request.method == "POST":
        form = BulkDividendCalculationForm(request.POST)
        
        if form.is_valid():
            try:
                period = form.cleaned_data['dividend_period']
                recalculate = form.cleaned_data.get('recalculate', False)
                
                # TODO: Implement bulk calculation logic
                # This should be moved to a service layer or model method
                calculated_count = 0
                failed_count = 0
                
                # Example structure:
                # results = period.calculate_member_dividends(recalculate=recalculate)
                # calculated_count = results['success']
                # failed_count = results['failed']
                
                success_message = f"Successfully calculated {calculated_count} dividend(s)"
                if failed_count > 0:
                    success_message += f". {failed_count} calculation(s) failed"
                
                messages.success(request, success_message, extra_tags='sweetalert')
                return redirect("dividends:period_detail", pk=period.pk)
                
            except Exception as e:
                logger.error(f"Bulk calculation error: {e}", exc_info=True)
                messages.error(
                    request, 
                    "An error occurred during bulk calculation", 
                    extra_tags='sweetalert-error'
                )
        else:
            messages.error(
                request, 
                "Please correct the errors below", 
                extra_tags='sweetalert-error'
            )
    else:
        form = BulkDividendCalculationForm()
    
    context = {
        'form': form,
        'title': 'Calculate Dividends'
    }
    
    return render(request, 'dividends/bulk/calculate.html', context)


# =============================================================================
# DISBURSEMENT VIEWS
# =============================================================================

@login_required
def disbursement_list(request):
    """
    List disbursements with filtering capability.
    HTMX loads paginated data dynamically.
    """
    filter_form = DividendDisbursementFilterForm()
    
    try:
        initial_stats = dividend_stats.get_disbursement_statistics()
    except Exception as e:
        logger.error(f"Disbursement stats error: {e}", exc_info=True)
        initial_stats = {}
    
    context = {
        'filter_form': filter_form,
        'stats': initial_stats
    }
    
    return render(request, 'dividends/disbursements/list.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def disbursement_create(request):
    """Create new dividend disbursement."""
    if request.method == "POST":
        form = DividendDisbursementForm(request.POST)
        
        if form.is_valid():
            try:
                disbursement = form.save()
                messages.success(
                    request, 
                    "Disbursement created successfully", 
                    extra_tags='sweetalert'
                )
                return redirect("dividends:disbursement_detail", pk=disbursement.pk)
                
            except Exception as e:
                logger.error(f"Disbursement creation error: {e}", exc_info=True)
                messages.error(
                    request, 
                    "An error occurred while creating the disbursement", 
                    extra_tags='sweetalert-error'
                )
        else:
            messages.error(
                request, 
                "Please correct the errors below", 
                extra_tags='sweetalert-error'
            )
    else:
        form = DividendDisbursementForm()
    
    context = {
        'form': form,
        'title': 'Create Disbursement'
    }
    
    return render(request, 'dividends/disbursements/form.html', context)


@login_required
def disbursement_detail(request, pk):
    """View detailed information about a disbursement."""
    disbursement = get_object_or_404(
        DividendDisbursement.objects.select_related('dividend_period'), 
        pk=pk
    )
    
    # Get recent payments
    payments = disbursement.payments.select_related(
        'member_dividend__member'
    ).order_by('-payment_date')[:20]
    
    context = {
        'disbursement': disbursement,
        'payments': payments
    }
    
    return render(request, 'dividends/disbursements/detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def batch_disbursement(request):
    """
    Create batch disbursement for multiple members.
    Uses transaction to ensure data consistency.
    """
    if request.method == "POST":
        form = BatchDisbursementForm(request.POST)
        
        if form.is_valid():
            try:
                period = form.cleaned_data['dividend_period']
                method = form.cleaned_data['disbursement_method']
                date = form.cleaned_data['disbursement_date']
                
                # TODO: Implement batch disbursement logic
                # This should be moved to a service layer or model method
                # Example: disbursement = period.create_batch_disbursement(method=method, date=date)
                
                messages.success(
                    request, 
                    "Batch disbursement created successfully", 
                    extra_tags='sweetalert'
                )
                return redirect("dividends:period_detail", pk=period.pk)
                
            except Exception as e:
                logger.error(f"Batch disbursement error: {e}", exc_info=True)
                messages.error(
                    request, 
                    "An error occurred during batch disbursement", 
                    extra_tags='sweetalert-error'
                )
        else:
            messages.error(
                request, 
                "Please correct the errors below", 
                extra_tags='sweetalert-error'
            )
    else:
        form = BatchDisbursementForm()
    
    context = {
        'form': form,
        'title': 'Batch Disbursement'
    }
    
    return render(request, 'dividends/bulk/disburse.html', context)


# =============================================================================
# PAYMENT VIEWS
# =============================================================================

@login_required
def payment_list(request):
    """
    List payments with filtering capability.
    HTMX loads paginated data dynamically.
    """
    filter_form = DividendPaymentFilterForm()
    
    try:
        initial_stats = dividend_stats.get_payment_statistics()
    except Exception as e:
        logger.error(f"Payment stats error: {e}", exc_info=True)
        initial_stats = {}
    
    context = {
        'filter_form': filter_form,
        'stats': initial_stats
    }
    
    return render(request, 'dividends/payments/list.html', context)


@login_required
def payment_detail(request, pk):
    """View detailed information about a payment."""
    payment = get_object_or_404(
        DividendPayment.objects.select_related(
            'member_dividend__member',
            'disbursement'
        ), 
        pk=pk
    )
    
    context = {
        'payment': payment
    }
    
    return render(request, 'dividends/payments/detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def payment_confirm(request, pk):
    """
    Confirm payment completion with transaction reference.
    Uses transaction to ensure data consistency.
    """
    payment = get_object_or_404(DividendPayment, pk=pk)
    
    if request.method == 'POST':
        form = PaymentConfirmationForm(request.POST)
        
        if form.is_valid():
            try:
                transaction_id = form.cleaned_data.get('transaction_id')
                success, message = payment.mark_as_completed(transaction_id)
                
                if success:
                    messages.success(request, message, extra_tags='sweetalert')
                else:
                    messages.error(request, message, extra_tags='sweetalert')
                
                return redirect('dividends:payment_detail', pk=pk)
                
            except Exception as e:
                logger.error(f"Payment confirmation error: {e}", exc_info=True)
                messages.error(
                    request, 
                    "An error occurred during payment confirmation", 
                    extra_tags='sweetalert'
                )
    else:
        form = PaymentConfirmationForm()
    
    context = {
        'form': form,
        'payment': payment
    }
    
    return render(request, 'dividends/payments/confirm.html', context)


# =============================================================================
# PREFERENCE VIEWS
# =============================================================================

@login_required
def preference_list(request):
    """List dividend preferences for all members."""
    preferences = DividendPreference.objects.select_related(
        'member',
        'dividend_period',
        'savings_account'
    ).order_by('-is_default', 'member__last_name')[:50]
    
    context = {
        'preferences': preferences
    }
    
    return render(request, 'dividends/preferences/list.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def preference_create(request):
    """Create new dividend preference."""
    if request.method == "POST":
        form = DividendPreferenceForm(request.POST)
        
        if form.is_valid():
            try:
                preference = form.save()
                messages.success(
                    request, 
                    "Preference saved successfully", 
                    extra_tags='sweetalert'
                )
                return redirect("dividends:preference_list")
                
            except Exception as e:
                logger.error(f"Preference creation error: {e}", exc_info=True)
                messages.error(
                    request, 
                    "An error occurred while saving the preference", 
                    extra_tags='sweetalert-error'
                )
        else:
            messages.error(
                request, 
                "Please correct the errors below", 
                extra_tags='sweetalert-error'
            )
    else:
        form = DividendPreferenceForm()
    
    context = {
        'form': form,
        'title': 'Set Dividend Preference'
    }
    
    return render(request, 'dividends/preferences/form.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def preference_edit(request, pk):
    """Edit existing dividend preference."""
    preference = get_object_or_404(
        DividendPreference.objects.select_related('member', 'savings_account'), 
        pk=pk
    )
    
    if request.method == "POST":
        form = DividendPreferenceForm(request.POST, instance=preference)
        
        if form.is_valid():
            try:
                preference = form.save()
                messages.success(
                    request, 
                    "Preference updated successfully", 
                    extra_tags='sweetalert'
                )
                return redirect("dividends:preference_list")
                
            except Exception as e:
                logger.error(f"Preference update error: {e}", exc_info=True)
                messages.error(
                    request, 
                    "An error occurred while updating the preference", 
                    extra_tags='sweetalert-error'
                )
        else:
            messages.error(
                request, 
                "Please correct the errors below", 
                extra_tags='sweetalert-error'
            )
    else:
        form = DividendPreferenceForm(instance=preference)
    
    context = {
        'form': form,
        'preference': preference,
        'title': 'Edit Dividend Preference'
    }
    
    return render(request, 'dividends/preferences/form.html', context)


# =============================================================================
# REPORT VIEWS
# =============================================================================

@login_required
@require_http_methods(["GET", "POST"])
def dividend_reports(request):
    """
    Generate various dividend reports using stats module.
    Supports multiple report types with flexible date ranges.
    """
    if request.method == "POST":
        form = DividendReportForm(request.POST)
        
        if form.is_valid():
            try:
                report_type = form.cleaned_data['report_type']
                period = form.cleaned_data.get('dividend_period')
                start_date = form.cleaned_data.get('start_date')
                end_date = form.cleaned_data.get('end_date')
                
                # Build filter dictionary
                filters = {}
                if period:
                    filters['period_id'] = str(period.id)
                if start_date:
                    filters['date_from'] = start_date
                if end_date:
                    filters['date_to'] = end_date
                
                # Generate report data based on type
                if report_type == 'SUMMARY':
                    data = dividend_stats.get_dividend_overview(start_date, end_date)
                elif report_type == 'BY_PERIOD':
                    data = dividend_stats.get_dividend_period_statistics(filters)
                elif report_type == 'BY_MEMBER':
                    data = dividend_stats.get_member_dividend_statistics(filters)
                elif report_type == 'DISBURSEMENTS':
                    data = dividend_stats.get_disbursement_statistics(filters)
                elif report_type == 'PAYMENTS':
                    data = dividend_stats.get_payment_statistics(filters)
                else:
                    data = {}
                
                context = {
                    'report_type': report_type,
                    'report_data': data,
                    'start_date': start_date,
                    'end_date': end_date,
                    'period': period,
                    'form': form
                }
                
                return render(request, 'dividends/reports/report_view.html', context)
                
            except Exception as e:
                logger.error(f"Report generation error: {e}", exc_info=True)
                messages.error(
                    request, 
                    f"Report generation failed: {str(e)}", 
                    extra_tags='sweetalert'
                )
                return redirect("dividends:reports")
        else:
            messages.error(
                request, 
                "Please correct the errors below", 
                extra_tags='sweetalert-error'
            )
    else:
        form = DividendReportForm()
    
    context = {
        'form': form,
        'title': 'Generate Dividend Reports'
    }
    
    return render(request, 'dividends/reports/form.html', context)


# =============================================================================
# UTILITY FUNCTIONS (Consider moving to services.py)
# =============================================================================

def _get_safe_stats(stats_function, *args, **kwargs):
    """
    Safely fetch statistics with error handling.
    Returns empty dict on error.
    """
    try:
        return stats_function(*args, **kwargs)
    except Exception as e:
        logger.error(f"Stats fetch error in {stats_function.__name__}: {e}", exc_info=True)
        return {}