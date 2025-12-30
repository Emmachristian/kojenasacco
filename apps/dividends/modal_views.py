# dividends/modal_views.py
"""
HTMX Modal Actions for Dividends Module.

This module handles all modal-based interactions for the dividends system,
providing AJAX endpoints for actions like approvals, cancellations, and confirmations.
All views return HTMX-compatible responses for seamless UI updates.
"""

from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.template.loader import render_to_string
from django.utils import timezone
from django.db import transaction
from django.http import JsonResponse
import logging

from .models import (
    DividendPeriod, 
    MemberDividend, 
    DividendRate, 
    DividendDisbursement, 
    DividendPayment, 
    DividendPreference
)
from core.utils import (
    create_success_response, 
    create_error_response, 
    create_redirect_response
)

logger = logging.getLogger(__name__)


# =============================================================================
# DIVIDEND PERIOD MODAL ACTIONS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def period_approve_modal(request, pk):
    """Display approval confirmation modal for dividend period."""
    period = get_object_or_404(
        DividendPeriod.objects.select_related('financial_period'), 
        pk=pk
    )
    
    context = {
        'period': period
    }
    
    return render(
        request, 
        'dividends/periods/modals/_approve_modal.html', 
        context
    )


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def period_approve_submit(request, pk):
    """
    Process period approval request.
    Returns updated period card HTML on success.
    """
    period = get_object_or_404(DividendPeriod, pk=pk)
    
    try:
        success, message = period.approve()
        
        if success:
            # Render updated period card
            updated_html = render_to_string(
                'dividends/periods/_period_card.html', 
                {'period': period}, 
                request=request
            )
            return create_success_response(
                updated_html, 
                message, 
                'Period Approved'
            )
        
        return create_error_response(message, 'Approval Failed')
        
    except Exception as e:
        logger.error(f"Period approval error for period {pk}: {e}", exc_info=True)
        return create_error_response(
            f"An unexpected error occurred: {str(e)}", 
            'Approval Failed'
        )


@login_required
@require_http_methods(["GET"])
def period_cancel_modal(request, pk):
    """Display cancellation confirmation modal for dividend period."""
    period = get_object_or_404(
        DividendPeriod.objects.select_related('financial_period'), 
        pk=pk
    )
    
    # Check if period can be cancelled
    can_cancel = period.status not in ['CANCELLED', 'COMPLETED']
    
    context = {
        'period': period,
        'can_cancel': can_cancel
    }
    
    return render(
        request, 
        'dividends/periods/modals/_cancel_modal.html', 
        context
    )

@login_required
@require_http_methods(["POST"])
@transaction.atomic
def period_cancel_submit(request, pk):
    """
    Process period cancellation request.
    Returns updated period card HTML on success.
    """
    period = get_object_or_404(DividendPeriod, pk=pk)
    
    # Validate cancellation is allowed
    if period.status == 'CANCELLED':
        return create_error_response(
            "This period has already been cancelled", 
            'Already Cancelled'
        )
    
    if period.status == 'COMPLETED':
        return create_error_response(
            "Cannot cancel a completed period", 
            'Cancellation Not Allowed'
        )
    
    try:
        period.status = 'CANCELLED'
        period.cancelled_at = timezone.now()
        period.cancelled_by = request.user
        period.save()
        
        # Render updated period card
        updated_html = render_to_string(
            'dividends/periods/_period_card.html', 
            {'period': period}, 
            request=request
        )
        
        return create_success_response(
            updated_html, 
            f"Period '{period.name}' has been cancelled", 
            'Period Cancelled'
        )
        
    except Exception as e:
        logger.error(f"Period cancellation error for period {pk}: {e}", exc_info=True)
        return create_error_response(
            f"An unexpected error occurred: {str(e)}", 
            'Cancellation Failed'
        )


@login_required
@require_http_methods(["GET"])
def period_delete_modal(request, pk):
    """Display deletion confirmation modal for dividend period."""
    period = get_object_or_404(
        DividendPeriod.objects.prefetch_related('member_dividends'), 
        pk=pk
    )
    
    # Check if period can be deleted
    can_delete = period.member_dividends.count() == 0
    
    context = {
        'period': period,
        'can_delete': can_delete,
        'dependent_count': period.member_dividends.count()
    }
    
    return render(
        request, 
        'dividends/periods/modals/_delete_modal.html', 
        context
    )


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def period_delete_submit(request, pk):
    """
    Process period deletion request.
    Only allows deletion if no member dividends exist.
    """
    period = get_object_or_404(DividendPeriod, pk=pk)
    
    # Validate deletion is allowed
    if period.member_dividends.exists():
        return create_error_response(
            "Cannot delete period with existing member dividends", 
            'Delete Failed'
        )
    
    try:
        period_name = period.name
        period.delete()
        
        return create_redirect_response(
            '/dividends/periods/', 
            f"Period '{period_name}' has been deleted", 
            'Period Deleted'
        )
        
    except Exception as e:
        logger.error(f"Period deletion error for period {pk}: {e}", exc_info=True)
        return create_error_response(
            f"An unexpected error occurred: {str(e)}", 
            'Delete Failed'
        )


# =============================================================================
# DIVIDEND RATE MODAL ACTIONS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def rate_delete_modal(request, pk):
    """Display deletion confirmation modal for dividend rate."""
    rate = get_object_or_404(
        DividendRate.objects.select_related('dividend_period'), 
        pk=pk
    )
    
    context = {
        'rate': rate
    }
    
    return render(
        request, 
        'dividends/rates/modals/_delete_modal.html', 
        context
    )


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def rate_delete_submit(request, pk):
    """Process rate deletion request."""
    rate = get_object_or_404(DividendRate, pk=pk)
    
    try:
        rate_name = rate.tier_name
        rate.delete()
        
        return create_success_response(
            '', 
            f"Rate '{rate_name}' has been deleted", 
            'Rate Deleted'
        )
        
    except Exception as e:
        logger.error(f"Rate deletion error for rate {pk}: {e}", exc_info=True)
        return create_error_response(
            f"An unexpected error occurred: {str(e)}", 
            'Delete Failed'
        )


@login_required
@require_http_methods(["GET"])
def rate_activate_modal(request, pk):
    """Display activation confirmation modal for dividend rate."""
    rate = get_object_or_404(
        DividendRate.objects.select_related('dividend_period'), 
        pk=pk
    )
    
    context = {
        'rate': rate
    }
    
    return render(
        request, 
        'dividends/rates/modals/_activate_modal.html', 
        context
    )


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def rate_activate_submit(request, pk):
    """
    Process rate activation request.
    Returns updated rate card HTML on success.
    """
    rate = get_object_or_404(DividendRate, pk=pk)
    
    try:
        rate.is_active = True
        rate.activated_at = timezone.now()
        rate.activated_by = request.user
        rate.save()
        
        # Render updated rate card
        updated_html = render_to_string(
            'dividends/rates/_rate_card.html', 
            {'rate': rate}, 
            request=request
        )
        
        return create_success_response(
            updated_html, 
            f"Rate '{rate.tier_name}' has been activated", 
            'Rate Activated'
        )
        
    except Exception as e:
        logger.error(f"Rate activation error for rate {pk}: {e}", exc_info=True)
        return create_error_response(
            f"An unexpected error occurred: {str(e)}", 
            'Activation Failed'
        )


@login_required
@require_http_methods(["GET"])
def rate_deactivate_modal(request, pk):
    """Display deactivation confirmation modal for dividend rate."""
    rate = get_object_or_404(
        DividendRate.objects.select_related('dividend_period'), 
        pk=pk
    )
    
    context = {
        'rate': rate
    }
    
    return render(
        request, 
        'dividends/rates/modals/_deactivate_modal.html', 
        context
    )


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def rate_deactivate_submit(request, pk):
    """
    Process rate deactivation request.
    Returns updated rate card HTML on success.
    """
    rate = get_object_or_404(DividendRate, pk=pk)
    
    try:
        rate.is_active = False
        rate.deactivated_at = timezone.now()
        rate.deactivated_by = request.user
        rate.save()
        
        # Render updated rate card
        updated_html = render_to_string(
            'dividends/rates/_rate_card.html', 
            {'rate': rate}, 
            request=request
        )
        
        return create_success_response(
            updated_html, 
            f"Rate '{rate.tier_name}' has been deactivated", 
            'Rate Deactivated'
        )
        
    except Exception as e:
        logger.error(f"Rate deactivation error for rate {pk}: {e}", exc_info=True)
        return create_error_response(
            f"An unexpected error occurred: {str(e)}", 
            'Deactivation Failed'
        )


# =============================================================================
# MEMBER DIVIDEND MODAL ACTIONS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def dividend_approve_modal(request, pk):
    """Display approval confirmation modal for member dividend."""
    dividend = get_object_or_404(
        MemberDividend.objects.select_related(
            'member',
            'dividend_period'
        ), 
        pk=pk
    )
    
    context = {
        'dividend': dividend
    }
    
    return render(
        request, 
        'dividends/members/modals/_approve_modal.html', 
        context
    )


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def dividend_approve_submit(request, pk):
    """
    Process member dividend approval request.
    Returns updated dividend card HTML on success.
    """
    dividend = get_object_or_404(MemberDividend, pk=pk)
    
    try:
        success, message = dividend.approve()
        
        if success:
            # Render updated dividend card
            updated_html = render_to_string(
                'dividends/members/_dividend_card.html', 
                {'dividend': dividend}, 
                request=request
            )
            return create_success_response(
                updated_html, 
                message, 
                'Dividend Approved'
            )
        
        return create_error_response(message, 'Approval Failed')
        
    except Exception as e:
        logger.error(f"Dividend approval error for dividend {pk}: {e}", exc_info=True)
        return create_error_response(
            f"An unexpected error occurred: {str(e)}", 
            'Approval Failed'
        )


@login_required
@require_http_methods(["GET"])
def dividend_cancel_modal(request, pk):
    """Display cancellation confirmation modal for member dividend."""
    dividend = get_object_or_404(
        MemberDividend.objects.select_related(
            'member',
            'dividend_period'
        ), 
        pk=pk
    )
    
    # Check if dividend can be cancelled
    can_cancel = dividend.status not in ['CANCELLED', 'PAID']
    
    context = {
        'dividend': dividend,
        'can_cancel': can_cancel
    }
    
    return render(
        request, 
        'dividends/members/modals/_cancel_modal.html', 
        context
    )


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def dividend_cancel_submit(request, pk):
    """
    Process member dividend cancellation request.
    Returns updated dividend card HTML on success.
    """
    dividend = get_object_or_404(MemberDividend, pk=pk)
    
    # Validate cancellation is allowed
    if dividend.status == 'CANCELLED':
        return create_error_response(
            "This dividend has already been cancelled", 
            'Already Cancelled'
        )
    
    if dividend.status == 'PAID':
        return create_error_response(
            "Cannot cancel a paid dividend", 
            'Cancellation Not Allowed'
        )
    
    try:
        dividend.status = 'CANCELLED'
        dividend.cancelled_at = timezone.now()
        dividend.cancelled_by = request.user
        dividend.save()
        
        # Render updated dividend card
        updated_html = render_to_string(
            'dividends/members/_dividend_card.html', 
            {'dividend': dividend}, 
            request=request
        )
        
        return create_success_response(
            updated_html, 
            "Dividend has been cancelled", 
            'Dividend Cancelled'
        )
        
    except Exception as e:
        logger.error(f"Dividend cancellation error for dividend {pk}: {e}", exc_info=True)
        return create_error_response(
            f"An unexpected error occurred: {str(e)}", 
            'Cancellation Failed'
        )


# =============================================================================
# DISBURSEMENT MODAL ACTIONS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def disbursement_start_modal(request, pk):
    """Display start processing confirmation modal for disbursement."""
    disbursement = get_object_or_404(
        DividendDisbursement.objects.select_related('dividend_period'), 
        pk=pk
    )
    
    context = {
        'disbursement': disbursement
    }
    
    return render(
        request, 
        'dividends/disbursements/modals/_start_modal.html', 
        context
    )


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def disbursement_start_submit(request, pk):
    """
    Process disbursement start request.
    Returns updated disbursement card HTML on success.
    """
    disbursement = get_object_or_404(DividendDisbursement, pk=pk)
    
    try:
        success, message = disbursement.start_processing()
        
        if success:
            # Render updated disbursement card
            updated_html = render_to_string(
                'dividends/disbursements/_disbursement_card.html', 
                {'disbursement': disbursement}, 
                request=request
            )
            return create_success_response(
                updated_html, 
                message, 
                'Disbursement Started'
            )
        
        return create_error_response(message, 'Start Failed')
        
    except Exception as e:
        logger.error(f"Disbursement start error for disbursement {pk}: {e}", exc_info=True)
        return create_error_response(
            f"An unexpected error occurred: {str(e)}", 
            'Start Failed'
        )


@login_required
@require_http_methods(["GET"])
def disbursement_cancel_modal(request, pk):
    """Display cancellation confirmation modal for disbursement."""
    disbursement = get_object_or_404(
        DividendDisbursement.objects.select_related('dividend_period'), 
        pk=pk
    )
    
    # Check if disbursement can be cancelled
    can_cancel = disbursement.status not in ['CANCELLED', 'COMPLETED']
    
    context = {
        'disbursement': disbursement,
        'can_cancel': can_cancel
    }
    
    return render(
        request, 
        'dividends/disbursements/modals/_cancel_modal.html', 
        context
    )


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def disbursement_cancel_submit(request, pk):
    """
    Process disbursement cancellation request.
    Returns updated disbursement card HTML on success.
    """
    disbursement = get_object_or_404(DividendDisbursement, pk=pk)
    
    # Validate cancellation is allowed
    if disbursement.status == 'CANCELLED':
        return create_error_response(
            "This disbursement has already been cancelled", 
            'Already Cancelled'
        )
    
    if disbursement.status == 'COMPLETED':
        return create_error_response(
            "Cannot cancel a completed disbursement", 
            'Cancellation Not Allowed'
        )
    
    try:
        disbursement.status = 'CANCELLED'
        disbursement.cancelled_at = timezone.now()
        disbursement.cancelled_by = request.user
        disbursement.save()
        
        # Render updated disbursement card
        updated_html = render_to_string(
            'dividends/disbursements/_disbursement_card.html', 
            {'disbursement': disbursement}, 
            request=request
        )
        
        return create_success_response(
            updated_html, 
            "Disbursement has been cancelled", 
            'Disbursement Cancelled'
        )
        
    except Exception as e:
        logger.error(f"Disbursement cancellation error for disbursement {pk}: {e}", exc_info=True)
        return create_error_response(
            f"An unexpected error occurred: {str(e)}", 
            'Cancellation Failed'
        )


# =============================================================================
# PAYMENT MODAL ACTIONS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def payment_confirm_modal(request, pk):
    """Display confirmation modal for payment."""
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
    
    return render(
        request, 
        'dividends/payments/modals/_confirm_modal.html', 
        context
    )


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def payment_confirm_submit(request, pk):
    """
    Process payment confirmation request.
    Returns updated payment card HTML on success.
    """
    payment = get_object_or_404(DividendPayment, pk=pk)
    transaction_id = request.POST.get('transaction_id', '').strip()
    
    # Validate transaction ID
    if not transaction_id:
        return create_error_response(
            "Transaction ID is required", 
            'Validation Error'
        )
    
    try:
        success, message = payment.mark_as_completed(transaction_id)
        
        if success:
            # Render updated payment card
            updated_html = render_to_string(
                'dividends/payments/_payment_card.html', 
                {'payment': payment}, 
                request=request
            )
            return create_success_response(
                updated_html, 
                message, 
                'Payment Confirmed'
            )
        
        return create_error_response(message, 'Confirmation Failed')
        
    except Exception as e:
        logger.error(f"Payment confirmation error for payment {pk}: {e}", exc_info=True)
        return create_error_response(
            f"An unexpected error occurred: {str(e)}", 
            'Confirmation Failed'
        )


@login_required
@require_http_methods(["GET"])
def payment_fail_modal(request, pk):
    """Display failure confirmation modal for payment."""
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
    
    return render(
        request, 
        'dividends/payments/modals/_fail_modal.html', 
        context
    )


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def payment_fail_submit(request, pk):
    """
    Process payment failure request.
    Returns updated payment card HTML on success.
    """
    payment = get_object_or_404(DividendPayment, pk=pk)
    failure_reason = request.POST.get('failure_reason', '').strip()
    
    # Validate failure reason
    if not failure_reason:
        return create_error_response(
            "Failure reason is required", 
            'Validation Error'
        )
    
    try:
        success, message = payment.mark_as_failed(failure_reason)
        
        if success:
            # Render updated payment card
            updated_html = render_to_string(
                'dividends/payments/_payment_card.html', 
                {'payment': payment}, 
                request=request
            )
            return create_success_response(
                updated_html, 
                message, 
                'Payment Marked as Failed'
            )
        
        return create_error_response(message, 'Update Failed')
        
    except Exception as e:
        logger.error(f"Payment failure marking error for payment {pk}: {e}", exc_info=True)
        return create_error_response(
            f"An unexpected error occurred: {str(e)}", 
            'Update Failed'
        )


# =============================================================================
# PREFERENCE MODAL ACTIONS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def preference_delete_modal(request, pk):
    """Display deletion confirmation modal for dividend preference."""
    preference = get_object_or_404(
        DividendPreference.objects.select_related(
            'member',
            'savings_account',
            'dividend_period'
        ), 
        pk=pk
    )
    
    context = {
        'preference': preference
    }
    
    return render(
        request, 
        'dividends/preferences/modals/_delete_modal.html', 
        context
    )


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def preference_delete_submit(request, pk):
    """Process preference deletion request."""
    preference = get_object_or_404(DividendPreference, pk=pk)
    
    try:
        preference.delete()
        
        return create_success_response(
            '', 
            "Preference has been deleted", 
            'Preference Deleted'
        )
        
    except Exception as e:
        logger.error(f"Preference deletion error for preference {pk}: {e}", exc_info=True)
        return create_error_response(
            f"An unexpected error occurred: {str(e)}", 
            'Delete Failed'
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _validate_action_allowed(instance, action, allowed_statuses):
    """
    Validate if an action is allowed based on current status.
    
    Args:
        instance: Model instance to check
        action: Action being performed (string)
        allowed_statuses: List of statuses that allow the action
        
    Returns:
        tuple: (is_allowed, error_message)
    """
    if instance.status not in allowed_statuses:
        return False, f"Cannot {action} in current status: {instance.get_status_display()}"
    return True, None


def _render_partial(template_name, context, request):
    """
    Helper to render partial template with error handling.
    
    Args:
        template_name: Template to render
        context: Context dictionary
        request: HTTP request object
        
    Returns:
        str: Rendered HTML or empty string on error
    """
    try:
        return render_to_string(template_name, context, request=request)
    except Exception as e:
        logger.error(f"Template rendering error for {template_name}: {e}", exc_info=True)
        return ''