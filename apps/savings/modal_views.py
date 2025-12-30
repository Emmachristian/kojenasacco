# savings/modal_views.py

"""
Savings Modal Action Views

HTMX-powered modal views for savings actions without page refresh.
Each action has two views:
1. _modal (GET) - Loads the modal HTML
2. _submit (POST/DELETE) - Processes the action and returns updated HTML

Uses centralized core.utils response helpers for consistent responses.
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.template.loader import render_to_string
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import logging

from .models import (
    SavingsProduct,
    InterestTier,
    SavingsAccount,
    SavingsTransaction,
    InterestCalculation,
    StandingOrder,
    SavingsGoal,
)

from .forms import (
    TransactionReversalForm,
    SavingsAccountApprovalForm,
)

from core.utils import (
    create_success_response,
    create_error_response,
    create_redirect_response
)

logger = logging.getLogger(__name__)


# =============================================================================
# SAVINGS PRODUCT MODALS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def product_delete_modal(request, pk):
    """Load delete savings product modal"""
    product = get_object_or_404(SavingsProduct, pk=pk)
    
    # Check if product has accounts
    account_count = product.accounts.count()
    active_account_count = product.accounts.filter(status__in=['ACTIVE', 'DORMANT']).count()
    
    context = {
        'product': product,
        'account_count': account_count,
        'active_account_count': active_account_count,
        'can_delete': active_account_count == 0,
    }
    
    return render(request, 'savings/products/modals/_delete_modal.html', context)


@login_required
@require_http_methods(["POST"])
def product_delete_submit(request, pk):
    """Delete savings product"""
    product = get_object_or_404(SavingsProduct, pk=pk)
    
    # Check if product has active accounts
    active_accounts = product.accounts.filter(status__in=['ACTIVE', 'DORMANT']).count()
    
    if active_accounts > 0:
        return create_error_response(
            message=f"Cannot delete product with {active_accounts} active account(s)",
            title='Delete Failed'
        )
    
    try:
        product_name = product.name
        product.delete()
        
        logger.info(f"Savings product {product_name} deleted")
        
        return create_redirect_response(
            redirect_url='/savings/products/',
            message=f"Product '{product_name}' deleted successfully",
            title='Product Deleted'
        )
        
    except Exception as e:
        logger.error(f"Error deleting product: {e}")
        return create_error_response(
            message=f"Error deleting product: {str(e)}",
            title='Delete Failed'
        )


@login_required
@require_http_methods(["GET"])
def product_activate_modal(request, pk):
    """Load activate savings product modal"""
    product = get_object_or_404(SavingsProduct, pk=pk)
    
    context = {
        'product': product,
    }
    
    return render(request, 'savings/products/modals/_activate_modal.html', context)


@login_required
@require_http_methods(["POST"])
def product_activate_submit(request, pk):
    """Activate savings product"""
    product = get_object_or_404(SavingsProduct, pk=pk)
    
    if product.is_active:
        return create_error_response(
            message="Product is already active",
            title='Already Active'
        )
    
    try:
        product.is_active = True
        product.save()
        
        updated_html = render_to_string(
            'savings/products/_product_card.html',
            {'product': product},
            request=request
        )
        
        return create_success_response(
            html_content=updated_html,
            message=f"Product '{product.name}' activated successfully",
            title='Product Activated'
        )
        
    except Exception as e:
        logger.error(f"Error activating product: {e}")
        return create_error_response(
            message=f"Error activating product: {str(e)}",
            title='Activation Failed'
        )


@login_required
@require_http_methods(["GET"])
def product_deactivate_modal(request, pk):
    """Load deactivate savings product modal"""
    product = get_object_or_404(SavingsProduct, pk=pk)
    
    # Check pending accounts
    pending_accounts = product.accounts.filter(status='PENDING_APPROVAL').count()
    
    context = {
        'product': product,
        'pending_accounts': pending_accounts,
    }
    
    return render(request, 'savings/products/modals/_deactivate_modal.html', context)


@login_required
@require_http_methods(["POST"])
def product_deactivate_submit(request, pk):
    """Deactivate savings product"""
    product = get_object_or_404(SavingsProduct, pk=pk)
    
    if not product.is_active:
        return create_error_response(
            message="Product is already inactive",
            title='Already Inactive'
        )
    
    try:
        product.is_active = False
        product.save()
        
        updated_html = render_to_string(
            'savings/products/_product_card.html',
            {'product': product},
            request=request
        )
        
        return create_success_response(
            html_content=updated_html,
            message=f"Product '{product.name}' deactivated successfully",
            title='Product Deactivated'
        )
        
    except Exception as e:
        logger.error(f"Error deactivating product: {e}")
        return create_error_response(
            message=f"Error deactivating product: {str(e)}",
            title='Deactivation Failed'
        )


# =============================================================================
# INTEREST TIER MODALS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def tier_delete_modal(request, pk):
    """Load delete interest tier modal"""
    tier = get_object_or_404(InterestTier, pk=pk)
    
    context = {
        'tier': tier,
        'product': tier.savings_product,
    }
    
    return render(request, 'savings/products/modals/_tier_delete_modal.html', context)


@login_required
@require_http_methods(["POST"])
def tier_delete_submit(request, pk):
    """Delete interest tier"""
    tier = get_object_or_404(InterestTier, pk=pk)
    product = tier.savings_product
    
    try:
        tier_name = tier.tier_name
        tier.delete()
        
        logger.info(f"Interest tier {tier_name} deleted from product {product.name}")
        
        # Return updated tier list
        updated_html = render_to_string(
            'savings/products/_tier_list.html',
            {'product': product},
            request=request
        )
        
        return create_success_response(
            html_content=updated_html,
            message=f"Tier '{tier_name}' deleted successfully",
            title='Tier Deleted'
        )
        
    except Exception as e:
        logger.error(f"Error deleting tier: {e}")
        return create_error_response(
            message=f"Error deleting tier: {str(e)}",
            title='Delete Failed'
        )


@login_required
@require_http_methods(["GET"])
def tier_activate_modal(request, pk):
    """Load activate interest tier modal"""
    tier = get_object_or_404(InterestTier, pk=pk)
    
    context = {
        'tier': tier,
    }
    
    return render(request, 'savings/products/modals/_tier_activate_modal.html', context)


@login_required
@require_http_methods(["POST"])
def tier_activate_submit(request, pk):
    """Activate interest tier"""
    tier = get_object_or_404(InterestTier, pk=pk)
    
    try:
        tier.is_active = True
        tier.save()
        
        updated_html = render_to_string(
            'savings/products/_tier_card.html',
            {'tier': tier},
            request=request
        )
        
        return create_success_response(
            html_content=updated_html,
            message=f"Tier '{tier.tier_name}' activated successfully",
            title='Tier Activated'
        )
        
    except Exception as e:
        logger.error(f"Error activating tier: {e}")
        return create_error_response(
            message=f"Error activating tier: {str(e)}",
            title='Activation Failed'
        )


@login_required
@require_http_methods(["GET"])
def tier_deactivate_modal(request, pk):
    """Load deactivate interest tier modal"""
    tier = get_object_or_404(InterestTier, pk=pk)
    
    context = {
        'tier': tier,
    }
    
    return render(request, 'savings/products/modals/_tier_deactivate_modal.html', context)


@login_required
@require_http_methods(["POST"])
def tier_deactivate_submit(request, pk):
    """Deactivate interest tier"""
    tier = get_object_or_404(InterestTier, pk=pk)
    
    try:
        tier.is_active = False
        tier.save()
        
        updated_html = render_to_string(
            'savings/products/_tier_card.html',
            {'tier': tier},
            request=request
        )
        
        return create_success_response(
            html_content=updated_html,
            message=f"Tier '{tier.tier_name}' deactivated successfully",
            title='Tier Deactivated'
        )
        
    except Exception as e:
        logger.error(f"Error deactivating tier: {e}")
        return create_error_response(
            message=f"Error deactivating tier: {str(e)}",
            title='Deactivation Failed'
        )


# =============================================================================
# SAVINGS ACCOUNT MODALS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def account_approve_modal(request, pk):
    """Load approve savings account modal"""
    account = get_object_or_404(SavingsAccount, pk=pk)
    
    # Check if approvable
    can_approve = account.status == 'PENDING_APPROVAL'
    meets_minimum = account.current_balance >= account.savings_product.minimum_opening_balance
    member_active = account.member.status == 'ACTIVE'
    
    context = {
        'account': account,
        'can_approve': can_approve and meets_minimum and member_active,
        'meets_minimum': meets_minimum,
        'member_active': member_active,
    }
    
    return render(request, 'savings/accounts/modals/_approve_modal.html', context)


@login_required
@require_http_methods(["POST"])
def account_approve_submit(request, pk):
    """Approve savings account"""
    account = get_object_or_404(SavingsAccount, pk=pk)
    
    try:
        success, message = account.approve_account()
        
        if success:
            updated_html = render_to_string(
                'savings/accounts/_account_card.html',
                {'account': account},
                request=request
            )
            
            return create_success_response(
                html_content=updated_html,
                message=message,
                title='Account Approved'
            )
        else:
            return create_error_response(
                message=message,
                title='Approval Failed'
            )
            
    except Exception as e:
        logger.error(f"Error approving account: {e}")
        return create_error_response(
            message=f"Error approving account: {str(e)}",
            title='Approval Failed'
        )


@login_required
@require_http_methods(["GET"])
def account_freeze_modal(request, pk):
    """Load freeze savings account modal"""
    account = get_object_or_404(SavingsAccount, pk=pk)
    
    context = {
        'account': account,
    }
    
    return render(request, 'savings/accounts/modals/_freeze_modal.html', context)


@login_required
@require_http_methods(["POST"])
def account_freeze_submit(request, pk):
    """Freeze savings account"""
    account = get_object_or_404(SavingsAccount, pk=pk)
    
    if account.status == 'FROZEN':
        return create_error_response(
            message="Account is already frozen",
            title='Already Frozen'
        )
    
    if account.status == 'CLOSED':
        return create_error_response(
            message="Cannot freeze closed account",
            title='Cannot Freeze'
        )
    
    try:
        account.status = 'FROZEN'
        account.save()
        
        logger.info(f"Account {account.account_number} frozen")
        
        updated_html = render_to_string(
            'savings/accounts/_account_card.html',
            {'account': account},
            request=request
        )
        
        return create_success_response(
            html_content=updated_html,
            message=f"Account {account.account_number} frozen successfully",
            title='Account Frozen'
        )
        
    except Exception as e:
        logger.error(f"Error freezing account: {e}")
        return create_error_response(
            message=f"Error freezing account: {str(e)}",
            title='Freeze Failed'
        )


@login_required
@require_http_methods(["GET"])
def account_unfreeze_modal(request, pk):
    """Load unfreeze savings account modal"""
    account = get_object_or_404(SavingsAccount, pk=pk)
    
    context = {
        'account': account,
    }
    
    return render(request, 'savings/accounts/modals/_unfreeze_modal.html', context)


@login_required
@require_http_methods(["POST"])
def account_unfreeze_submit(request, pk):
    """Unfreeze savings account"""
    account = get_object_or_404(SavingsAccount, pk=pk)
    
    if account.status != 'FROZEN':
        return create_error_response(
            message="Account is not frozen",
            title='Not Frozen'
        )
    
    try:
        account.status = 'ACTIVE'
        account.save()
        
        logger.info(f"Account {account.account_number} unfrozen")
        
        updated_html = render_to_string(
            'savings/accounts/_account_card.html',
            {'account': account},
            request=request
        )
        
        return create_success_response(
            html_content=updated_html,
            message=f"Account {account.account_number} unfrozen successfully",
            title='Account Unfrozen'
        )
        
    except Exception as e:
        logger.error(f"Error unfreezing account: {e}")
        return create_error_response(
            message=f"Error unfreezing account: {str(e)}",
            title='Unfreeze Failed'
        )


@login_required
@require_http_methods(["GET"])
def account_close_modal(request, pk):
    """Load close savings account modal"""
    account = get_object_or_404(SavingsAccount, pk=pk)
    
    # Check if closeable
    can_close = account.status in ['ACTIVE', 'DORMANT', 'FROZEN']
    has_balance = account.current_balance > 0
    has_holds = account.hold_amount > 0
    has_overdraft = account.overdraft_amount > 0
    
    context = {
        'account': account,
        'can_close': can_close and not has_balance and not has_holds and not has_overdraft,
        'has_balance': has_balance,
        'has_holds': has_holds,
        'has_overdraft': has_overdraft,
    }
    
    return render(request, 'savings/accounts/modals/_close_modal.html', context)


@login_required
@require_http_methods(["POST"])
def account_close_submit(request, pk):
    """Close savings account"""
    account = get_object_or_404(SavingsAccount, pk=pk)
    
    # Validate closure conditions
    if account.status == 'CLOSED':
        return create_error_response(
            message="Account is already closed",
            title='Already Closed'
        )
    
    if account.current_balance > 0:
        return create_error_response(
            message="Account has balance. Withdraw all funds before closing",
            title='Cannot Close'
        )
    
    if account.hold_amount > 0:
        return create_error_response(
            message="Account has holds. Release all holds before closing",
            title='Cannot Close'
        )
    
    if account.overdraft_amount > 0:
        return create_error_response(
            message="Account has overdraft. Clear overdraft before closing",
            title='Cannot Close'
        )
    
    try:
        account.status = 'CLOSED'
        account.closure_date = timezone.now().date()
        account.save()
        
        logger.info(f"Account {account.account_number} closed")
        
        updated_html = render_to_string(
            'savings/accounts/_account_card.html',
            {'account': account},
            request=request
        )
        
        return create_success_response(
            html_content=updated_html,
            message=f"Account {account.account_number} closed successfully",
            title='Account Closed'
        )
        
    except Exception as e:
        logger.error(f"Error closing account: {e}")
        return create_error_response(
            message=f"Error closing account: {str(e)}",
            title='Closure Failed'
        )


# =============================================================================
# TRANSACTION MODALS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def transaction_reverse_modal(request, pk):
    """Load reverse transaction modal"""
    txn = get_object_or_404(SavingsTransaction, pk=pk)
    
    # Check if reversible
    can_reverse = not txn.is_reversed
    
    context = {
        'transaction': txn,
        'can_reverse': can_reverse,
    }
    
    return render(request, 'savings/transactions/modals/_reverse_modal.html', context)


@login_required
@require_http_methods(["POST"])
def transaction_reverse_submit(request, pk):
    """Reverse transaction"""
    txn = get_object_or_404(SavingsTransaction, pk=pk)
    
    if txn.is_reversed:
        return create_error_response(
            message="Transaction is already reversed",
            title='Already Reversed'
        )
    
    # Get reversal reason from form
    reversal_reason = request.POST.get('reversal_reason', '')
    
    if not reversal_reason:
        return create_error_response(
            message="Reversal reason is required",
            title='Reversal Failed'
        )
    
    try:
        with transaction.atomic():
            # Create reversal transaction
            reversal_txn = SavingsTransaction.objects.create(
                account=txn.account,
                transaction_type='REVERSAL',
                amount=txn.amount,
                fees=txn.fees,
                tax_amount=txn.tax_amount,
                payment_method=txn.payment_method,
                description=f"Reversal of {txn.transaction_id}: {reversal_reason}",
                original_transaction=txn,
                transaction_date=timezone.now(),
                running_balance=txn.account.current_balance,
            )
            
            # Update account balance
            if txn.transaction_type in ['DEPOSIT', 'TRANSFER_IN', 'INTEREST']:
                txn.account.current_balance -= txn.amount
            elif txn.transaction_type in ['WITHDRAWAL', 'TRANSFER_OUT']:
                txn.account.current_balance += (txn.amount + txn.fees + txn.tax_amount)
            
            txn.account.update_available_balance()
            
            # Mark original as reversed
            txn.is_reversed = True
            txn.reversal_reason = reversal_reason
            txn.reversal_date = timezone.now()
            txn.save()
            
            logger.info(f"Transaction {txn.transaction_id} reversed")
            
            updated_html = render_to_string(
                'savings/transactions/_transaction_card.html',
                {'transaction': txn},
                request=request
            )
            
            return create_success_response(
                html_content=updated_html,
                message=f"Transaction {txn.transaction_id} reversed successfully",
                title='Transaction Reversed'
            )
            
    except Exception as e:
        logger.error(f"Error reversing transaction: {e}")
        return create_error_response(
            message=f"Error reversing transaction: {str(e)}",
            title='Reversal Failed'
        )


# =============================================================================
# INTEREST CALCULATION MODALS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def interest_post_modal(request, pk):
    """Load post interest modal"""
    calc = get_object_or_404(InterestCalculation, pk=pk)
    
    # Check if postable
    can_post = not calc.is_posted
    
    context = {
        'calculation': calc,
        'can_post': can_post,
    }
    
    return render(request, 'savings/interest/modals/_post_modal.html', context)


@login_required
@require_http_methods(["POST"])
def interest_post_submit(request, pk):
    """Post interest calculation"""
    calc = get_object_or_404(InterestCalculation, pk=pk)
    
    if calc.is_posted:
        return create_error_response(
            message="Interest is already posted",
            title='Already Posted'
        )
    
    try:
        with transaction.atomic():
            # Create interest transaction
            txn = SavingsTransaction.objects.create(
                account=calc.account,
                transaction_type='INTEREST',
                amount=calc.net_interest,
                tax_amount=calc.withholding_tax,
                description=f"Interest for period {calc.period_start_date} to {calc.period_end_date}",
                running_balance=calc.account.current_balance + calc.net_interest,
                transaction_date=timezone.now(),
                post_date=timezone.now().date(),
            )
            
            # Update account balance
            calc.account.current_balance += calc.net_interest
            calc.account.total_interest_earned += calc.net_interest
            calc.account.accrued_interest = Decimal('0.00')
            calc.account.save()
            
            # Mark calculation as posted
            calc.is_posted = True
            calc.posted_date = timezone.now().date()
            calc.transaction = txn
            calc.save()
            
            logger.info(f"Interest calculation {calc.id} posted to account {calc.account.account_number}")
            
            updated_html = render_to_string(
                'savings/interest/_calculation_card.html',
                {'calculation': calc},
                request=request
            )
            
            return create_success_response(
                html_content=updated_html,
                message=f"Interest posted successfully",
                title='Interest Posted'
            )
            
    except Exception as e:
        logger.error(f"Error posting interest: {e}")
        return create_error_response(
            message=f"Error posting interest: {str(e)}",
            title='Posting Failed'
        )


@login_required
@require_http_methods(["GET"])
def interest_delete_modal(request, pk):
    """Load delete interest calculation modal"""
    calc = get_object_or_404(InterestCalculation, pk=pk)
    
    # Can only delete unposted calculations
    can_delete = not calc.is_posted
    
    context = {
        'calculation': calc,
        'can_delete': can_delete,
    }
    
    return render(request, 'savings/interest/modals/_delete_modal.html', context)


@login_required
@require_http_methods(["POST"])
def interest_delete_submit(request, pk):
    """Delete interest calculation"""
    calc = get_object_or_404(InterestCalculation, pk=pk)
    
    if calc.is_posted:
        return create_error_response(
            message="Cannot delete posted interest calculation",
            title='Cannot Delete'
        )
    
    try:
        account_number = calc.account.account_number
        calc.delete()
        
        logger.info(f"Interest calculation deleted for account {account_number}")
        
        return create_success_response(
            message="Interest calculation deleted successfully",
            title='Calculation Deleted'
        )
        
    except Exception as e:
        logger.error(f"Error deleting interest calculation: {e}")
        return create_error_response(
            message=f"Error deleting calculation: {str(e)}",
            title='Delete Failed'
        )


# =============================================================================
# STANDING ORDER MODALS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def standing_order_activate_modal(request, pk):
    """Load activate standing order modal"""
    order = get_object_or_404(StandingOrder, pk=pk)
    
    context = {
        'order': order,
    }
    
    return render(request, 'savings/standing_orders/modals/_activate_modal.html', context)


@login_required
@require_http_methods(["POST"])
def standing_order_activate_submit(request, pk):
    """Activate standing order"""
    order = get_object_or_404(StandingOrder, pk=pk)
    
    try:
        success, message = order.activate()
        
        if success:
            updated_html = render_to_string(
                'savings/standing_orders/_order_card.html',
                {'order': order},
                request=request
            )
            
            return create_success_response(
                html_content=updated_html,
                message=message,
                title='Order Activated'
            )
        else:
            return create_error_response(
                message=message,
                title='Activation Failed'
            )
            
    except Exception as e:
        logger.error(f"Error activating standing order: {e}")
        return create_error_response(
            message=f"Error activating order: {str(e)}",
            title='Activation Failed'
        )


@login_required
@require_http_methods(["GET"])
def standing_order_pause_modal(request, pk):
    """Load pause standing order modal"""
    order = get_object_or_404(StandingOrder, pk=pk)
    
    context = {
        'order': order,
    }
    
    return render(request, 'savings/standing_orders/modals/_pause_modal.html', context)


@login_required
@require_http_methods(["POST"])
def standing_order_pause_submit(request, pk):
    """Pause standing order"""
    order = get_object_or_404(StandingOrder, pk=pk)
    
    try:
        success, message = order.pause()
        
        if success:
            updated_html = render_to_string(
                'savings/standing_orders/_order_card.html',
                {'order': order},
                request=request
            )
            
            return create_success_response(
                html_content=updated_html,
                message=message,
                title='Order Paused'
            )
        else:
            return create_error_response(
                message=message,
                title='Pause Failed'
            )
            
    except Exception as e:
        logger.error(f"Error pausing standing order: {e}")
        return create_error_response(
            message=f"Error pausing order: {str(e)}",
            title='Pause Failed'
        )


@login_required
@require_http_methods(["GET"])
def standing_order_resume_modal(request, pk):
    """Load resume standing order modal"""
    order = get_object_or_404(StandingOrder, pk=pk)
    
    context = {
        'order': order,
    }
    
    return render(request, 'savings/standing_orders/modals/_resume_modal.html', context)


@login_required
@require_http_methods(["POST"])
def standing_order_resume_submit(request, pk):
    """Resume standing order"""
    order = get_object_or_404(StandingOrder, pk=pk)
    
    try:
        success, message = order.resume()
        
        if success:
            updated_html = render_to_string(
                'savings/standing_orders/_order_card.html',
                {'order': order},
                request=request
            )
            
            return create_success_response(
                html_content=updated_html,
                message=message,
                title='Order Resumed'
            )
        else:
            return create_error_response(
                message=message,
                title='Resume Failed'
            )
            
    except Exception as e:
        logger.error(f"Error resuming standing order: {e}")
        return create_error_response(
            message=f"Error resuming order: {str(e)}",
            title='Resume Failed'
        )


@login_required
@require_http_methods(["GET"])
def standing_order_cancel_modal(request, pk):
    """Load cancel standing order modal"""
    order = get_object_or_404(StandingOrder, pk=pk)
    
    context = {
        'order': order,
    }
    
    return render(request, 'savings/standing_orders/modals/_cancel_modal.html', context)


@login_required
@require_http_methods(["POST"])
def standing_order_cancel_submit(request, pk):
    """Cancel standing order"""
    order = get_object_or_404(StandingOrder, pk=pk)
    
    if order.status == 'CANCELLED':
        return create_error_response(
            message="Order is already cancelled",
            title='Already Cancelled'
        )
    
    try:
        order.status = 'CANCELLED'
        order.save()
        
        logger.info(f"Standing order {order.id} cancelled")
        
        updated_html = render_to_string(
            'savings/standing_orders/_order_card.html',
            {'order': order},
            request=request
        )
        
        return create_success_response(
            html_content=updated_html,
            message="Standing order cancelled successfully",
            title='Order Cancelled'
        )
        
    except Exception as e:
        logger.error(f"Error cancelling standing order: {e}")
        return create_error_response(
            message=f"Error cancelling order: {str(e)}",
            title='Cancellation Failed'
        )


# =============================================================================
# SAVINGS GOAL MODALS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def goal_delete_modal(request, pk):
    """Load delete savings goal modal"""
    goal = get_object_or_404(SavingsGoal, pk=pk)
    
    context = {
        'goal': goal,
    }
    
    return render(request, 'savings/goals/modals/_delete_modal.html', context)


@login_required
@require_http_methods(["POST"])
def goal_delete_submit(request, pk):
    """Delete savings goal"""
    goal = get_object_or_404(SavingsGoal, pk=pk)
    
    try:
        goal_name = goal.name
        account = goal.account
        goal.delete()
        
        logger.info(f"Savings goal {goal_name} deleted")
        
        # Return updated goals list for account
        updated_html = render_to_string(
            'savings/goals/_goal_list.html',
            {'account': account},
            request=request
        )
        
        return create_success_response(
            html_content=updated_html,
            message=f"Goal '{goal_name}' deleted successfully",
            title='Goal Deleted'
        )
        
    except Exception as e:
        logger.error(f"Error deleting goal: {e}")
        return create_error_response(
            message=f"Error deleting goal: {str(e)}",
            title='Delete Failed'
        )


@login_required
@require_http_methods(["GET"])
def goal_mark_achieved_modal(request, pk):
    """Load mark goal as achieved modal"""
    goal = get_object_or_404(SavingsGoal, pk=pk)
    
    # Check if can be marked achieved
    can_mark = not goal.is_achieved and goal.current_amount >= goal.target_amount
    
    context = {
        'goal': goal,
        'can_mark': can_mark,
    }
    
    return render(request, 'savings/goals/modals/_mark_achieved_modal.html', context)


@login_required
@require_http_methods(["POST"])
def goal_mark_achieved_submit(request, pk):
    """Mark goal as achieved"""
    goal = get_object_or_404(SavingsGoal, pk=pk)
    
    if goal.is_achieved:
        return create_error_response(
            message="Goal is already marked as achieved",
            title='Already Achieved'
        )
    
    if goal.current_amount < goal.target_amount:
        return create_error_response(
            message="Goal has not reached target amount",
            title='Cannot Mark Achieved'
        )
    
    try:
        goal.is_achieved = True
        goal.achievement_date = timezone.now().date()
        goal.progress_percentage = Decimal('100.00')
        goal.save()
        
        logger.info(f"Savings goal {goal.name} marked as achieved")
        
        updated_html = render_to_string(
            'savings/goals/_goal_card.html',
            {'goal': goal},
            request=request
        )
        
        return create_success_response(
            html_content=updated_html,
            message=f"Congratulations! Goal '{goal.name}' marked as achieved",
            title='Goal Achieved! 🎉'
        )
        
    except Exception as e:
        logger.error(f"Error marking goal as achieved: {e}")
        return create_error_response(
            message=f"Error marking goal: {str(e)}",
            title='Update Failed'
        )