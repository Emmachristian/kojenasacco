# loans/modal_views.py 

"""
Modal views for loan actions using centralized utilities from core.utils

All modal responses use the standardized create_sweetalert_response() helper
from core.utils, ensuring consistency across the entire application.
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods

# Import the centralized response helpers
from core.utils import (
    create_sweetalert_response,
    create_success_response,
    create_error_response,
    create_warning_response,
    create_info_response
)

from .models import (
    LoanProduct,
    LoanApplication,
    Loan,
    LoanPayment,
    LoanGuarantor,
    LoanCollateral
)

from .forms import (
    LoanApplicationApprovalForm,
    PaymentReversalForm,
    CollateralVerificationForm,
)

import logging
logger = logging.getLogger(__name__)


# =============================================================================
# LOAN APPLICATION APPROVAL
# =============================================================================

@login_required
@require_http_methods(["GET"])
def loan_application_approve_modal(request, pk):
    """Load approval form in modal"""
    application = get_object_or_404(LoanApplication, pk=pk)
    
    # Pre-fill form with application data
    initial = {
        'approved_amount': application.amount_requested,
        'approved_term': application.term_months,
        'approved_interest_rate': application.loan_product.interest_rate,
    }
    form = LoanApplicationApprovalForm(initial=initial)
    
    return render(request, 'loans/modals/approve_application.html', {
        'application': application,
        'form': form,
    })


@login_required
@require_http_methods(["POST"])
def loan_application_approve_submit(request, pk):
    """Process approval form submission"""
    application = get_object_or_404(LoanApplication, pk=pk)
    form = LoanApplicationApprovalForm(request.POST)
    
    if not form.is_valid():
        # Return form with errors (keep modal open)
        return render(request, 'loans/modals/approve_application.html', {
            'application': application,
            'form': form,
        })
    
    decision = form.cleaned_data['decision']
    
    # Process based on decision
    if decision == 'APPROVE':
        success, message = application.approve(
            approved_amount=form.cleaned_data.get('approved_amount'),
            approved_term=form.cleaned_data.get('approved_term'),
            approved_rate=form.cleaned_data.get('approved_interest_rate')
        )
        alert_type = 'success' if success else 'error'
        title = 'Application Approved' if success else 'Approval Failed'
        
    elif decision == 'REJECT':
        success, message = application.reject(
            form.cleaned_data['rejection_reason']
        )
        alert_type = 'success' if success else 'error'
        title = 'Application Rejected' if success else 'Rejection Failed'
        
    else:
        return create_error_response(
            message="Invalid decision selected",
            title='Invalid Action'
        )
    
    if not success:
        # Show error and keep modal open for correction
        return render(request, 'loans/modals/approve_application.html', {
            'application': application,
            'form': form,
            'error_message': message,
        })
    
    # Success! Return updated content
    application.refresh_from_db()
    
    updated_html = render_to_string(
        'loans/applications/_application_card.html',
        {'application': application},
        request=request
    )
    
    return create_sweetalert_response(
        html_content=updated_html,
        message=message,
        alert_type=alert_type,
        title=title,
        close_modal=True
    )


# =============================================================================
# LOAN PRODUCT DELETION
# =============================================================================

@login_required
@require_http_methods(["GET"])
def loan_product_delete_modal(request, pk):
    """Load delete confirmation modal"""
    product = get_object_or_404(LoanProduct, pk=pk)
    
    # Check if deletion is allowed
    has_applications = product.loanapplication_set.exists()
    has_loans = product.loan_set.exists()
    can_delete = not (has_applications or has_loans)
    
    return render(request, 'loans/modals/delete_product.html', {
        'product': product,
        'can_delete': can_delete,
        'has_applications': has_applications,
        'has_loans': has_loans,
    })


@login_required
@require_http_methods(["DELETE", "POST"])
def loan_product_delete_submit(request, pk):
    """Process product deletion"""
    product = get_object_or_404(LoanProduct, pk=pk)
    
    # Verify can delete
    if product.loanapplication_set.exists() or product.loan_set.exists():
        return create_error_response(
            message=f"Cannot delete '{product.name}' because it has associated applications or loans.",
            title='Cannot Delete'
        )
    
    product_name = product.name
    product.delete()
    
    # Return success (row will be removed by HTMX)
    return create_success_response(
        html_content='',  # No content needed - HTMX removes the row
        message=f"Product '{product_name}' has been deleted successfully.",
        title='Product Deleted'
    )


# =============================================================================
# PAYMENT REVERSAL
# =============================================================================

@login_required
@require_http_methods(["GET"])
def loan_payment_reverse_modal(request, pk):
    """Load payment reversal modal"""
    payment = get_object_or_404(LoanPayment, pk=pk)
    
    # Check if already reversed
    if payment.is_reversed:
        return render(request, 'loans/modals/payment_already_reversed.html', {
            'payment': payment,
        })
    
    form = PaymentReversalForm()
    
    return render(request, 'loans/modals/reverse_payment.html', {
        'payment': payment,
        'form': form,
    })


@login_required
@require_http_methods(["POST"])
def loan_payment_reverse_submit(request, pk):
    """Process payment reversal"""
    payment = get_object_or_404(LoanPayment, pk=pk)
    form = PaymentReversalForm(request.POST)
    
    if not form.is_valid():
        return render(request, 'loans/modals/reverse_payment.html', {
            'payment': payment,
            'form': form,
        })
    
    reason = form.cleaned_data['reversal_reason']
    success, message = payment.reverse(reason)
    
    if not success:
        return render(request, 'loans/modals/reverse_payment.html', {
            'payment': payment,
            'form': form,
            'error_message': message,
        })
    
    # Success! Return updated payment
    payment.refresh_from_db()
    
    updated_html = render_to_string(
        'loans/payments/_payment_row.html',
        {'payment': payment},
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=message,
        title='Payment Reversed'
    )


# =============================================================================
# GUARANTOR APPROVAL
# =============================================================================

@login_required
@require_http_methods(["GET"])
def loan_guarantor_approve_modal(request, pk):
    """Load guarantor approval confirmation"""
    guarantor = get_object_or_404(LoanGuarantor, pk=pk)
    
    return render(request, 'loans/modals/approve_guarantor.html', {
        'guarantor': guarantor,
    })


@login_required
@require_http_methods(["POST"])
def loan_guarantor_approve_submit(request, pk):
    """Process guarantor approval"""
    guarantor = get_object_or_404(LoanGuarantor, pk=pk)
    
    success, message = guarantor.approve()
    
    if not success:
        return create_error_response(
            message=message,
            title='Approval Failed'
        )
    
    # Success! Return updated guarantor
    guarantor.refresh_from_db()
    
    updated_html = render_to_string(
        'loans/guarantors/_guarantor_card.html',
        {'guarantor': guarantor},
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=message,
        title='Guarantor Approved'
    )


# =============================================================================
# GUARANTOR REJECTION
# =============================================================================

@login_required
@require_http_methods(["GET"])
def loan_guarantor_reject_modal(request, pk):
    """Load guarantor rejection modal"""
    guarantor = get_object_or_404(LoanGuarantor, pk=pk)
    
    return render(request, 'loans/modals/reject_guarantor.html', {
        'guarantor': guarantor,
    })


@login_required
@require_http_methods(["POST"])
def loan_guarantor_reject_submit(request, pk):
    """Process guarantor rejection"""
    guarantor = get_object_or_404(LoanGuarantor, pk=pk)
    reason = request.POST.get('reason', '').strip()
    
    if not reason:
        return render(request, 'loans/modals/reject_guarantor.html', {
            'guarantor': guarantor,
            'error_message': 'Rejection reason is required',
        })
    
    success, message = guarantor.reject(reason)
    
    if not success:
        return render(request, 'loans/modals/reject_guarantor.html', {
            'guarantor': guarantor,
            'error_message': message,
        })
    
    # Success! Return updated guarantor
    guarantor.refresh_from_db()
    
    updated_html = render_to_string(
        'loans/guarantors/_guarantor_card.html',
        {'guarantor': guarantor},
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=message,
        title='Guarantor Rejected'
    )


# =============================================================================
# COLLATERAL VERIFICATION
# =============================================================================

@login_required
@require_http_methods(["GET"])
def loan_collateral_verify_modal(request, pk):
    """Load collateral verification modal"""
    collateral = get_object_or_404(LoanCollateral, pk=pk)
    form = CollateralVerificationForm()
    
    return render(request, 'loans/modals/verify_collateral.html', {
        'collateral': collateral,
        'form': form,
    })


@login_required
@require_http_methods(["POST"])
def loan_collateral_verify_submit(request, pk):
    """Process collateral verification"""
    collateral = get_object_or_404(LoanCollateral, pk=pk)
    form = CollateralVerificationForm(request.POST)
    
    if not form.is_valid():
        return render(request, 'loans/modals/verify_collateral.html', {
            'collateral': collateral,
            'form': form,
        })
    
    notes = form.cleaned_data.get('verification_notes')
    success, message = collateral.verify(notes)
    
    if not success:
        return render(request, 'loans/modals/verify_collateral.html', {
            'collateral': collateral,
            'form': form,
            'error_message': message,
        })
    
    # Success! Return updated collateral
    collateral.refresh_from_db()
    
    updated_html = render_to_string(
        'loans/collaterals/_collateral_card.html',
        {'collateral': collateral},
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=message,
        title='Collateral Verified'
    )


