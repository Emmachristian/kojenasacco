# savings/views.py

"""
Savings Management Views

Comprehensive view functions for:
- Savings Products and Configuration
- Savings Accounts and Management
- Savings Transactions (Deposits, Withdrawals, Transfers)
- Interest Calculations and Posting
- Standing Orders and Automated Transfers
- Savings Goals and Tracking
- Reports and Analytics

All views include proper permissions, messaging, and error handling
Uses stats.py for comprehensive statistics and analytics
Uses services.py for ALL business logic
Uses signals.py for automatic number generation
Uses SweetAlert2 for all notifications via Django messages
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg, Prefetch
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from datetime import timedelta, date, datetime
from decimal import Decimal
import logging

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO

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
    SavingsProductForm,
    SavingsProductQuickForm,
    InterestTierForm,
    SavingsAccountForm,
    SavingsAccountQuickOpenForm,
    SavingsAccountApprovalForm,
    SavingsTransactionForm,
    DepositForm,
    WithdrawalForm,
    TransferForm,
    TransactionReversalForm,
    StandingOrderForm,
    SavingsGoalForm,
    BulkInterestCalculationForm,
    BulkInterestPostingForm,
    SavingsReportForm,
    SavingsProductFilterForm,
    SavingsAccountFilterForm,
    SavingsTransactionFilterForm,
    StandingOrderFilterForm,
    SavingsGoalFilterForm,
)

# Import stats functions
from . import stats as savings_stats

# Import services - ONLY import services, not utils
from .services import (
    TransactionService,
    InterestService,
    StandingOrderService,
    AccountService,
)

from members.models import Member
from core.models import PaymentMethod, FiscalPeriod
from core.utils import format_money

logger = logging.getLogger(__name__)


# =============================================================================
# DASHBOARD
# =============================================================================

@login_required
def savings_dashboard(request):
    """Main savings dashboard with overview statistics - USES stats.py"""
    
    try:
        # Use comprehensive overview from stats.py
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)
        
        overview = savings_stats.get_savings_overview(
            date_from=thirty_days_ago,
            date_to=today
        )
        
        # Get additional statistics
        product_stats = savings_stats.get_product_statistics()
        account_stats = savings_stats.get_account_statistics()
        transaction_stats = savings_stats.get_transaction_statistics({
            'date_from': thirty_days_ago,
            'date_to': today
        })
        interest_stats = savings_stats.get_interest_statistics()
        
    except Exception as e:
        logger.error(f"Error getting dashboard statistics: {e}")
        overview = {}
        product_stats = {}
        account_stats = {}
        transaction_stats = {}
        interest_stats = {}
    
    # Get recent activities (limited queries for display)
    recent_accounts = SavingsAccount.objects.select_related(
        'member', 'savings_product'
    ).order_by('-created_at')[:10]
    
    recent_transactions = SavingsTransaction.objects.select_related(
        'account', 'account__member'
    ).order_by('-transaction_date')[:10]
    
    pending_approvals = SavingsAccount.objects.filter(
        status='PENDING_APPROVAL'
    ).select_related('member', 'savings_product').order_by('created_at')[:10]
    
    # Get accounts needing attention
    matured_fixed_deposits = SavingsAccount.objects.filter(
        is_fixed_deposit=True,
        maturity_date__lte=today,
        status='ACTIVE'
    ).select_related('member', 'savings_product').order_by('maturity_date')[:10]
    
    # Get due standing orders
    due_standing_orders = StandingOrder.objects.filter(
        status='ACTIVE',
        next_run_date__lte=today + timedelta(days=7)
    ).select_related('source_account', 'destination_account').order_by('next_run_date')[:10]
    
    # Get pending interest calculations
    pending_interest = InterestCalculation.objects.filter(
        is_posted=False
    ).select_related('account', 'account__member').order_by('-calculation_date')[:10]
    
    context = {
        'overview': overview,
        'product_stats': product_stats,
        'account_stats': account_stats,
        'transaction_stats': transaction_stats,
        'interest_stats': interest_stats,
        'recent_accounts': recent_accounts,
        'recent_transactions': recent_transactions,
        'pending_approvals': pending_approvals,
        'matured_fixed_deposits': matured_fixed_deposits,
        'due_standing_orders': due_standing_orders,
        'pending_interest': pending_interest,
    }
    
    return render(request, 'savings/dashboard.html', context)


# =============================================================================
# SAVINGS PRODUCT VIEWS
# =============================================================================

@login_required
def product_list(request):
    """List all savings products - HTMX loads data on page load"""
    
    # Initialize filter form
    filter_form = SavingsProductFilterForm()
    
    # Get initial stats from stats.py
    try:
        initial_stats = savings_stats.get_product_statistics()
    except Exception as e:
        logger.error(f"Error getting product statistics: {e}")
        initial_stats = {}
    
    context = {
        'filter_form': filter_form,
        'stats': initial_stats,
    }
    
    return render(request, 'savings/products/list.html', context)


@login_required
def product_create(request):
    """Create a new savings product"""
    if request.method == "POST":
        form = SavingsProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            messages.success(
                request,
                f"Savings product '{product.name}' was created successfully",
                extra_tags='sweetalert'
            )
            return redirect("savings:product_detail", pk=product.pk)
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = SavingsProductForm()
    
    context = {
        'form': form,
        'title': 'Create Savings Product',
    }
    return render(request, 'savings/products/form.html', context)


@login_required
def product_edit(request, pk):
    """Edit existing savings product"""
    product = get_object_or_404(SavingsProduct, pk=pk)
    
    if request.method == "POST":
        form = SavingsProductForm(request.POST, instance=product)
        if form.is_valid():
            product = form.save()
            messages.success(
                request,
                f"Savings product '{product.name}' was updated successfully",
                extra_tags='sweetalert'
            )
            return redirect("savings:product_detail", pk=product.pk)
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = SavingsProductForm(instance=product)
    
    context = {
        'form': form,
        'product': product,
        'title': 'Update Savings Product',
    }
    return render(request, 'savings/products/form.html', context)


@login_required
def product_detail(request, pk):
    """View savings product details - USES stats.py"""
    product = get_object_or_404(
        SavingsProduct.objects.prefetch_related(
            'interest_tiers',
            Prefetch(
                'accounts',
                queryset=SavingsAccount.objects.filter(status__in=['ACTIVE', 'DORMANT']).select_related('member')
            )
        ),
        pk=pk
    )
    
    # Get product performance from stats.py
    try:
        performance_data = savings_stats.get_product_performance_breakdown(str(product.id))
        product_performance = performance_data['breakdown'][0] if performance_data['breakdown'] else {}
    except Exception as e:
        logger.error(f"Error getting product performance: {e}")
        product_performance = {}
    
    # Get interest tiers
    interest_tiers = product.interest_tiers.filter(is_active=True).order_by('min_balance')
    
    # Get recent accounts
    recent_accounts = product.accounts.order_by('-opening_date')[:10]
    
    context = {
        'product': product,
        'performance': product_performance,
        'interest_tiers': interest_tiers,
        'recent_accounts': recent_accounts,
    }
    
    return render(request, 'savings/products/detail.html', context)


# =============================================================================
# INTEREST TIER VIEWS
# =============================================================================

@login_required
def tier_create(request, product_pk):
    """Add interest tier to a product"""
    product = get_object_or_404(SavingsProduct, pk=product_pk)
    
    if request.method == 'POST':
        form = InterestTierForm(request.POST)
        if form.is_valid():
            tier = form.save(commit=False)
            tier.savings_product = product
            tier.save()
            messages.success(
                request,
                f"Interest tier '{tier.tier_name}' was added successfully",
                extra_tags='sweetalert'
            )
            return redirect('savings:product_detail', pk=product.pk)
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = InterestTierForm(initial={'savings_product': product})
    
    context = {
        'form': form,
        'product': product,
        'title': f'Add Interest Tier to {product.name}',
    }
    return render(request, 'savings/products/tier_form.html', context)


@login_required
def tier_edit(request, pk):
    """Edit interest tier"""
    tier = get_object_or_404(InterestTier, pk=pk)
    
    if request.method == 'POST':
        form = InterestTierForm(request.POST, instance=tier)
        if form.is_valid():
            tier = form.save()
            messages.success(
                request,
                f"Interest tier '{tier.tier_name}' was updated successfully",
                extra_tags='sweetalert'
            )
            return redirect('savings:product_detail', pk=tier.savings_product.pk)
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = InterestTierForm(instance=tier)
    
    context = {
        'form': form,
        'tier': tier,
        'product': tier.savings_product,
        'title': 'Edit Interest Tier',
    }
    return render(request, 'savings/products/tier_form.html', context)


# =============================================================================
# SAVINGS ACCOUNT VIEWS - ALL USE AccountService
# =============================================================================

@login_required
def account_list(request):
    """List all savings accounts - HTMX loads data on page load"""
    
    # Initialize filter form
    filter_form = SavingsAccountFilterForm()
    
    # Get initial stats from stats.py
    try:
        initial_stats = savings_stats.get_account_statistics()
    except Exception as e:
        logger.error(f"Error getting account statistics: {e}")
        initial_stats = {}
    
    context = {
        'filter_form': filter_form,
        'stats': initial_stats,
    }
    
    return render(request, 'savings/accounts/list.html', context)


@login_required
def account_create(request):
    """Create a new savings account"""
    if request.method == "POST":
        form = SavingsAccountForm(request.POST)
        if form.is_valid():
            # Account number will be auto-generated by signals
            account = form.save()
            
            messages.success(
                request,
                f"Savings account {account.account_number} was created successfully",
                extra_tags='sweetalert'
            )
            return redirect("savings:account_detail", pk=account.pk)
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = SavingsAccountForm()
    
    context = {
        'form': form,
        'title': 'Create Savings Account',
    }
    return render(request, 'savings/accounts/form.html', context)


@login_required
def account_quick_open(request):
    """Quick form to open a savings account with initial deposit - USES AccountService"""
    if request.method == "POST":
        form = SavingsAccountQuickOpenForm(request.POST)
        if form.is_valid():
            # Use AccountService to handle business logic
            success, result = AccountService.open_account(
                member=form.cleaned_data['member'],
                savings_product=form.cleaned_data['savings_product'],
                opening_balance=form.cleaned_data['opening_balance'],
                payment_method=form.cleaned_data['payment_method'],
                reference_number=form.cleaned_data.get('reference_number'),
                description=form.cleaned_data.get('description'),
                is_fixed_deposit=form.cleaned_data.get('is_fixed_deposit', False),
                term_days=form.cleaned_data.get('term_length_days'),
                auto_renew=form.cleaned_data.get('auto_renew', False),
                processed_by=request.user
            )
            
            if success:
                account = result
                messages.success(
                    request,
                    f"Savings account {account.account_number} opened successfully for {account.member.get_full_name()}",
                    extra_tags='sweetalert'
                )
                return redirect("savings:account_detail", pk=account.pk)
            else:
                messages.error(
                    request,
                    f"Error opening account: {result}",
                    extra_tags='sweetalert-error'
                )
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = SavingsAccountQuickOpenForm()
    
    context = {
        'form': form,
        'title': 'Quick Open Savings Account',
    }
    return render(request, 'savings/accounts/quick_open.html', context)


@login_required
def account_edit(request, pk):
    """Edit existing savings account"""
    account = get_object_or_404(SavingsAccount, pk=pk)
    
    if request.method == "POST":
        form = SavingsAccountForm(request.POST, instance=account)
        if form.is_valid():
            account = form.save()
            messages.success(
                request,
                f"Savings account {account.account_number} was updated successfully",
                extra_tags='sweetalert'
            )
            return redirect("savings:account_detail", pk=account.pk)
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = SavingsAccountForm(instance=account)
    
    context = {
        'form': form,
        'account': account,
        'title': 'Update Savings Account',
    }
    return render(request, 'savings/accounts/form.html', context)


@login_required
def account_detail(request, pk):
    """View savings account details - USES AccountService for summary"""
    account = get_object_or_404(
        SavingsAccount.objects.select_related(
            'member',
            'savings_product',
            'group'
        ).prefetch_related(
            'transactions',
            'interest_calculations',
            'savings_goals',
            'standing_orders_out'
        ),
        pk=pk
    )
    
    # Get comprehensive account summary from service
    try:
        account_summary = AccountService.get_account_summary(account)
    except Exception as e:
        logger.error(f"Error getting account summary: {e}")
        account_summary = {}
    
    # Get account data (transactions would be handled by htmx_views)
    transactions = account.transactions.order_by('-transaction_date')[:20]
    
    # Get interest calculations
    interest_calculations = account.interest_calculations.order_by('-calculation_date')[:10]
    
    # Get savings goals
    savings_goals = account.savings_goals.order_by('-is_achieved', 'target_date')
    
    # Get standing orders
    standing_orders = account.standing_orders_out.filter(status='ACTIVE')
    
    context = {
        'account': account,
        'account_summary': account_summary,
        'transactions': transactions,
        'interest_calculations': interest_calculations,
        'savings_goals': savings_goals,
        'standing_orders': standing_orders,
    }
    
    return render(request, 'savings/accounts/detail.html', context)


@login_required
def account_approve(request, pk):
    """Approve pending savings account"""
    account = get_object_or_404(SavingsAccount, pk=pk)
    
    if request.method == 'POST':
        form = SavingsAccountApprovalForm(request.POST)
        if form.is_valid():
            # Use model method for approval (simple operation)
            success, message = account.approve_account()
            
            if success:
                messages.success(request, message, extra_tags='sweetalert')
            else:
                messages.error(request, message, extra_tags='sweetalert-error')
            
            return redirect('savings:account_detail', pk=account.pk)
    else:
        form = SavingsAccountApprovalForm()
    
    context = {
        'form': form,
        'account': account,
        'title': 'Approve Savings Account',
    }
    return render(request, 'savings/accounts/approve.html', context)


@login_required
def account_close(request, pk):
    """Close a savings account - USES AccountService"""
    account = get_object_or_404(SavingsAccount, pk=pk)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', 'Account closure requested')
        
        # Use AccountService to handle business logic
        success, message = AccountService.close_account(
            account=account,
            reason=reason,
            closed_by=request.user
        )
        
        if success:
            messages.success(
                request,
                message,
                extra_tags='sweetalert'
            )
            return redirect('savings:account_list')
        else:
            messages.error(
                request,
                message,
                extra_tags='sweetalert-error'
            )
            return redirect('savings:account_detail', pk=account.pk)
    
    # Check if account can be closed
    from .utils import can_close_account
    can_close, reason = can_close_account(account)
    
    context = {
        'account': account,
        'can_close': can_close,
        'reason': reason,
        'title': 'Close Savings Account',
    }
    return render(request, 'savings/accounts/close.html', context)


@login_required
def account_freeze(request, pk):
    """Freeze a savings account - USES AccountService"""
    account = get_object_or_404(SavingsAccount, pk=pk)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', 'Account freeze requested')
        
        success, message = AccountService.freeze_account(
            account=account,
            reason=reason,
            frozen_by=request.user
        )
        
        if success:
            messages.success(request, message, extra_tags='sweetalert')
        else:
            messages.error(request, message, extra_tags='sweetalert-error')
        
        return redirect('savings:account_detail', pk=account.pk)
    
    context = {
        'account': account,
        'title': 'Freeze Savings Account',
    }
    return render(request, 'savings/accounts/freeze.html', context)


@login_required
def account_unfreeze(request, pk):
    """Unfreeze a savings account - USES AccountService"""
    account = get_object_or_404(SavingsAccount, pk=pk)
    
    if request.method == 'POST':
        success, message = AccountService.unfreeze_account(
            account=account,
            unfrozen_by=request.user
        )
        
        if success:
            messages.success(request, message, extra_tags='sweetalert')
        else:
            messages.error(request, message, extra_tags='sweetalert-error')
        
        return redirect('savings:account_detail', pk=account.pk)
    
    context = {
        'account': account,
        'title': 'Unfreeze Savings Account',
    }
    return render(request, 'savings/accounts/unfreeze.html', context)


# =============================================================================
# TRANSACTION VIEWS - ALL USE TransactionService
# =============================================================================

@login_required
def transaction_list(request):
    """List all savings transactions - HTMX loads data on page load"""
    
    # Initialize filter form
    filter_form = SavingsTransactionFilterForm()
    
    # Get initial stats from stats.py
    try:
        today = timezone.now().date()
        initial_stats = savings_stats.get_transaction_statistics({
            'date_from': today,
            'date_to': today
        })
    except Exception as e:
        logger.error(f"Error getting transaction statistics: {e}")
        initial_stats = {}
    
    context = {
        'filter_form': filter_form,
        'stats': initial_stats,
    }
    
    return render(request, 'savings/transactions/list.html', context)


@login_required
def deposit(request):
    """Quick deposit form - USES TransactionService"""
    if request.method == "POST":
        form = DepositForm(request.POST)
        if form.is_valid():
            # Use TransactionService for business logic
            success, result = TransactionService.process_deposit(
                account=form.cleaned_data['account'],
                amount=form.cleaned_data['amount'],
                payment_method=form.cleaned_data['payment_method'],
                reference_number=form.cleaned_data.get('reference_number'),
                description=form.cleaned_data.get('description'),
                processed_by=request.user
            )
            
            if success:
                transaction = result
                messages.success(
                    request,
                    f"Deposit of {format_money(form.cleaned_data['amount'])} successful. Transaction ID: {transaction.transaction_id}",
                    extra_tags='sweetalert'
                )
                return redirect("savings:account_detail", pk=form.cleaned_data['account'].pk)
            else:
                messages.error(
                    request,
                    f"Deposit failed: {result}",
                    extra_tags='sweetalert-error'
                )
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = DepositForm()
    
    context = {
        'form': form,
        'title': 'Make Deposit',
    }
    return render(request, 'savings/transactions/deposit.html', context)


@login_required
def withdrawal(request):
    """Quick withdrawal form - USES TransactionService"""
    if request.method == "POST":
        form = WithdrawalForm(request.POST)
        if form.is_valid():
            # Use TransactionService for business logic
            success, result = TransactionService.process_withdrawal(
                account=form.cleaned_data['account'],
                amount=form.cleaned_data['amount'],
                payment_method=form.cleaned_data['payment_method'],
                reference_number=form.cleaned_data.get('reference_number'),
                description=form.cleaned_data.get('description'),
                processed_by=request.user
            )
            
            if success:
                transaction = result
                messages.success(
                    request,
                    f"Withdrawal of {format_money(form.cleaned_data['amount'])} successful. Transaction ID: {transaction.transaction_id}",
                    extra_tags='sweetalert'
                )
                return redirect("savings:account_detail", pk=form.cleaned_data['account'].pk)
            else:
                messages.error(
                    request,
                    f"Withdrawal failed: {result}",
                    extra_tags='sweetalert-error'
                )
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = WithdrawalForm()
    
    context = {
        'form': form,
        'title': 'Make Withdrawal',
    }
    return render(request, 'savings/transactions/withdrawal.html', context)


@login_required
def transfer(request):
    """Account transfer form - USES TransactionService"""
    if request.method == "POST":
        form = TransferForm(request.POST)
        if form.is_valid():
            # Use TransactionService for business logic
            success, result = TransactionService.process_transfer(
                source_account=form.cleaned_data['source_account'],
                destination_account=form.cleaned_data['destination_account'],
                amount=form.cleaned_data['amount'],
                description=form.cleaned_data.get('description'),
                processed_by=request.user
            )
            
            if success:
                txn_out, txn_in = result
                messages.success(
                    request,
                    f"Transfer of {format_money(form.cleaned_data['amount'])} successful. Transaction ID: {txn_out.transaction_id}",
                    extra_tags='sweetalert'
                )
                return redirect("savings:account_detail", pk=form.cleaned_data['source_account'].pk)
            else:
                messages.error(
                    request,
                    f"Transfer failed: {result}",
                    extra_tags='sweetalert-error'
                )
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = TransferForm()
    
    context = {
        'form': form,
        'title': 'Transfer Between Accounts',
    }
    return render(request, 'savings/transactions/transfer.html', context)


@login_required
def transaction_detail(request, pk):
    """View transaction details"""
    txn = get_object_or_404(
        SavingsTransaction.objects.select_related(
            'account',
            'account__member',
            'payment_method',
            'linked_account',
            'linked_transaction',
            'financial_period'
        ),
        pk=pk
    )
    
    context = {
        'transaction': txn,
    }
    
    return render(request, 'savings/transactions/detail.html', context)


@login_required
def transaction_reverse(request, pk):
    """Reverse a transaction - USES TransactionService"""
    transaction_obj = get_object_or_404(SavingsTransaction, pk=pk)
    
    if request.method == 'POST':
        form = TransactionReversalForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            
            # Use TransactionService for business logic
            success, result = TransactionService.reverse_transaction(
                transaction=transaction_obj,
                reason=reason,
                reversed_by=request.user
            )
            
            if success:
                messages.success(
                    request,
                    f"Transaction {transaction_obj.transaction_id} reversed successfully",
                    extra_tags='sweetalert'
                )
                return redirect('savings:transaction_detail', pk=transaction_obj.pk)
            else:
                messages.error(
                    request,
                    f"Reversal failed: {result}",
                    extra_tags='sweetalert-error'
                )
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = TransactionReversalForm()
    
    context = {
        'form': form,
        'transaction': transaction_obj,
        'title': 'Reverse Transaction',
    }
    return render(request, 'savings/transactions/reverse.html', context)


# =============================================================================
# STANDING ORDER VIEWS
# =============================================================================

@login_required
def standing_order_list(request):
    """List all standing orders - HTMX loads data on page load"""
    
    # Initialize filter form
    filter_form = StandingOrderFilterForm()
    
    # Get initial stats from stats.py
    try:
        initial_stats = savings_stats.get_standing_order_statistics()
    except Exception as e:
        logger.error(f"Error getting standing order statistics: {e}")
        initial_stats = {}
    
    context = {
        'filter_form': filter_form,
        'stats': initial_stats,
    }
    
    return render(request, 'savings/standing_orders/list.html', context)


@login_required
def standing_order_create(request):
    """Create a new standing order"""
    if request.method == "POST":
        form = StandingOrderForm(request.POST)
        if form.is_valid():
            # Next run date will be set by signal
            order = form.save()
            
            messages.success(
                request,
                "Standing order created successfully",
                extra_tags='sweetalert'
            )
            return redirect("savings:standing_order_detail", pk=order.pk)
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = StandingOrderForm()
    
    context = {
        'form': form,
        'title': 'Create Standing Order',
    }
    return render(request, 'savings/standing_orders/form.html', context)


@login_required
def standing_order_edit(request, pk):
    """Edit standing order"""
    order = get_object_or_404(StandingOrder, pk=pk)
    
    if request.method == "POST":
        form = StandingOrderForm(request.POST, instance=order)
        if form.is_valid():
            order = form.save()
            messages.success(
                request,
                "Standing order updated successfully",
                extra_tags='sweetalert'
            )
            return redirect("savings:standing_order_detail", pk=order.pk)
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = StandingOrderForm(instance=order)
    
    context = {
        'form': form,
        'order': order,
        'title': 'Edit Standing Order',
    }
    return render(request, 'savings/standing_orders/form.html', context)


@login_required
def standing_order_detail(request, pk):
    """View standing order details"""
    order = get_object_or_404(
        StandingOrder.objects.select_related(
            'source_account',
            'source_account__member',
            'destination_account',
            'destination_account__member'
        ),
        pk=pk
    )
    
    context = {
        'order': order,
    }
    
    return render(request, 'savings/standing_orders/detail.html', context)


@login_required
def standing_order_activate(request, pk):
    """Activate a standing order"""
    order = get_object_or_404(StandingOrder, pk=pk)
    
    success, message = order.activate()
    
    if success:
        messages.success(request, message, extra_tags='sweetalert')
    else:
        messages.error(request, message, extra_tags='sweetalert-error')
    
    return redirect('savings:standing_order_detail', pk=order.pk)


@login_required
def standing_order_pause(request, pk):
    """Pause a standing order"""
    order = get_object_or_404(StandingOrder, pk=pk)
    
    success, message = order.pause()
    
    if success:
        messages.success(request, message, extra_tags='sweetalert')
    else:
        messages.error(request, message, extra_tags='sweetalert-error')
    
    return redirect('savings:standing_order_detail', pk=order.pk)


@login_required
def standing_order_resume(request, pk):
    """Resume a paused standing order"""
    order = get_object_or_404(StandingOrder, pk=pk)
    
    success, message = order.resume()
    
    if success:
        messages.success(request, message, extra_tags='sweetalert')
    else:
        messages.error(request, message, extra_tags='sweetalert-error')
    
    return redirect('savings:standing_order_detail', pk=order.pk)


@login_required
def standing_order_execute(request, pk):
    """Manually execute a standing order - USES StandingOrderService"""
    order = get_object_or_404(StandingOrder, pk=pk)
    
    if request.method == 'POST':
        # Use StandingOrderService for business logic
        success, result = StandingOrderService.execute_standing_order(order)
        
        if success:
            messages.success(
                request,
                f"Standing order executed successfully. Transaction ID: {result[0].transaction_id if isinstance(result, tuple) else result.transaction_id}",
                extra_tags='sweetalert'
            )
        else:
            messages.error(
                request,
                f"Execution failed: {result}",
                extra_tags='sweetalert-error'
            )
        
        return redirect('savings:standing_order_detail', pk=order.pk)
    
    context = {
        'order': order,
        'title': 'Execute Standing Order',
    }
    return render(request, 'savings/standing_orders/execute.html', context)


# =============================================================================
# SAVINGS GOAL VIEWS
# =============================================================================

@login_required
def savings_goal_list(request):
    """List all savings goals - HTMX loads data on page load"""
    
    # Initialize filter form
    filter_form = SavingsGoalFilterForm()
    
    # Get initial stats from stats.py
    try:
        initial_stats = savings_stats.get_savings_goal_statistics()
    except Exception as e:
        logger.error(f"Error getting savings goal statistics: {e}")
        initial_stats = {}
    
    context = {
        'filter_form': filter_form,
        'stats': initial_stats,
    }
    
    return render(request, 'savings/goals/list.html', context)


@login_required
def savings_goal_create(request):
    """Create a new savings goal"""
    if request.method == "POST":
        form = SavingsGoalForm(request.POST)
        if form.is_valid():
            # Progress will be calculated by signal
            goal = form.save()
            messages.success(
                request,
                f"Savings goal '{goal.name}' created successfully",
                extra_tags='sweetalert'
            )
            return redirect("savings:goal_detail", pk=goal.pk)
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = SavingsGoalForm()
    
    context = {
        'form': form,
        'title': 'Create Savings Goal',
    }
    return render(request, 'savings/goals/form.html', context)


@login_required
def savings_goal_edit(request, pk):
    """Edit savings goal"""
    goal = get_object_or_404(SavingsGoal, pk=pk)
    
    if request.method == "POST":
        form = SavingsGoalForm(request.POST, instance=goal)
        if form.is_valid():
            goal = form.save()
            messages.success(
                request,
                f"Savings goal '{goal.name}' updated successfully",
                extra_tags='sweetalert'
            )
            return redirect("savings:goal_detail", pk=goal.pk)
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = SavingsGoalForm(instance=goal)
    
    context = {
        'form': form,
        'goal': goal,
        'title': 'Edit Savings Goal',
    }
    return render(request, 'savings/goals/form.html', context)


@login_required
def savings_goal_detail(request, pk):
    """View savings goal details"""
    goal = get_object_or_404(
        SavingsGoal.objects.select_related(
            'account',
            'account__member',
            'account__savings_product'
        ),
        pk=pk
    )
    
    context = {
        'goal': goal,
    }
    
    return render(request, 'savings/goals/detail.html', context)


@login_required
def savings_goal_update_progress(request, pk):
    """Update savings goal progress"""
    goal = get_object_or_404(SavingsGoal, pk=pk)
    
    # Progress will be updated by signal on save
    goal.update_progress()
    
    messages.success(
        request,
        f"Progress updated: {goal.progress_percentage}%",
        extra_tags='sweetalert'
    )
    
    return redirect('savings:goal_detail', pk=goal.pk)


# =============================================================================
# BULK OPERATIONS - ALL USE SERVICES
# =============================================================================

@login_required
def bulk_interest_calculation(request):
    """Bulk calculate interest for accounts - USES InterestService"""
    
    if request.method == "POST":
        form = BulkInterestCalculationForm(request.POST)
        if form.is_valid():
            calculation_date = form.cleaned_data['calculation_date']
            savings_product = form.cleaned_data.get('savings_product')
            
            # Use InterestService for business logic
            results = InterestService.bulk_calculate_interest(
                product=savings_product,
                calculation_date=calculation_date
            )
            
            if results['successful'] > 0:
                messages.success(
                    request,
                    f"Successfully calculated interest for {results['successful']} account(s)" +
                    (f". {results['failed']} failed." if results['failed'] > 0 else ""),
                    extra_tags='sweetalert'
                )
            else:
                messages.warning(
                    request,
                    f"No interest calculated. {results['failed']} error(s) occurred.",
                    extra_tags='sweetalert'
                )
            
            return redirect("savings:dashboard")
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = BulkInterestCalculationForm()
    
    context = {
        'form': form,
        'title': 'Bulk Interest Calculation',
    }
    return render(request, 'savings/bulk_operations/calculate_interest.html', context)


@login_required
def bulk_interest_posting(request):
    """Bulk post calculated interest - USES InterestService"""
    
    if request.method == "POST":
        form = BulkInterestPostingForm(request.POST)
        if form.is_valid():
            posting_date = form.cleaned_data['posting_date']
            period_start = form.cleaned_data.get('period_start')
            period_end = form.cleaned_data.get('period_end')
            
            # Get unposted calculations
            calculations = InterestCalculation.objects.filter(is_posted=False)
            
            if period_start:
                calculations = calculations.filter(calculation_date__gte=period_start)
            if period_end:
                calculations = calculations.filter(calculation_date__lte=period_end)
            
            if not calculations.exists():
                messages.warning(
                    request,
                    "No unposted interest calculations found",
                    extra_tags='sweetalert'
                )
                return redirect("savings:dashboard")
            
            posted_count = 0
            failed_count = 0
            total_interest = Decimal('0.00')
            
            for calc in calculations:
                # Use InterestService for business logic
                success, result = InterestService.post_interest_calculation(
                    calculation=calc,
                    posting_date=posting_date
                )
                
                if success:
                    posted_count += 1
                    total_interest += calc.net_interest
                else:
                    failed_count += 1
                    logger.error(f"Failed to post interest calculation {calc.id}: {result}")
            
            if posted_count > 0:
                messages.success(
                    request,
                    f"Successfully posted interest for {posted_count} account(s). Total: {format_money(total_interest)}" +
                    (f". {failed_count} failed." if failed_count > 0 else ""),
                    extra_tags='sweetalert'
                )
            else:
                messages.error(
                    request,
                    f"Failed to post interest. {failed_count} error(s) occurred.",
                    extra_tags='sweetalert'
                )
            
            return redirect("savings:dashboard")
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = BulkInterestPostingForm()
    
    context = {
        'form': form,
        'title': 'Bulk Interest Posting',
    }
    return render(request, 'savings/bulk_operations/post_interest.html', context)


@login_required
def bulk_standing_order_execution(request):
    """Execute all due standing orders - USES StandingOrderService"""
    
    if request.method == 'POST':
        execution_date = request.POST.get('execution_date')
        if execution_date:
            execution_date = datetime.strptime(execution_date, '%Y-%m-%d').date()
        
        # Use StandingOrderService for business logic
        results = StandingOrderService.execute_due_standing_orders(execution_date)
        
        if results['successful'] > 0:
            messages.success(
                request,
                f"Successfully executed {results['successful']} standing order(s)" +
                (f". {results['failed']} failed." if results['failed'] > 0 else ""),
                extra_tags='sweetalert'
            )
        else:
            messages.warning(
                request,
                f"No standing orders executed. {results['failed']} error(s) occurred.",
                extra_tags='sweetalert'
            )
        
        return redirect("savings:standing_order_list")
    
    # Get due orders for display
    due_orders = StandingOrder.get_due_standing_orders()
    
    context = {
        'due_orders': due_orders,
        'title': 'Execute Due Standing Orders',
    }
    return render(request, 'savings/bulk_operations/execute_standing_orders.html', context)


# =============================================================================
# REPORTS - USE stats.py
# =============================================================================

@login_required
def savings_reports(request):
    """Generate savings reports - USES stats.py"""
    
    if request.method == "POST":
        form = SavingsReportForm(request.POST)
        if form.is_valid():
            report_type = form.cleaned_data['report_type']
            start_date = form.cleaned_data.get('start_date')
            end_date = form.cleaned_data.get('end_date')
            savings_product = form.cleaned_data.get('savings_product')
            report_format = form.cleaned_data.get('format')
            
            # Use stats.py functions based on report type
            try:
                filters = {}
                if start_date:
                    filters['date_from'] = start_date
                if end_date:
                    filters['date_to'] = end_date
                if savings_product:
                    filters['product_id'] = str(savings_product.id)
                
                if report_type == 'ACCOUNT_SUMMARY':
                    data = savings_stats.get_account_statistics(filters)
                elif report_type == 'TRANSACTION_REPORT':
                    data = savings_stats.get_transaction_statistics(filters)
                elif report_type == 'INTEREST_REPORT':
                    data = savings_stats.get_interest_statistics(filters)
                elif report_type == 'PRODUCT_PERFORMANCE':
                    if savings_product:
                        data = savings_stats.get_product_performance_breakdown(str(savings_product.id))
                    else:
                        data = savings_stats.get_product_statistics()
                elif report_type == 'DORMANT_ACCOUNTS':
                    filters['status'] = 'DORMANT'
                    data = savings_stats.get_account_statistics(filters)
                elif report_type == 'STANDING_ORDERS':
                    data = savings_stats.get_standing_order_statistics(filters)
                elif report_type == 'SAVINGS_GOALS':
                    data = savings_stats.get_savings_goal_statistics(filters)
                else:
                    data = savings_stats.get_savings_overview(start_date, end_date)
                
                # For now, just display the data
                # TODO: Implement PDF/Excel/CSV export
                context = {
                    'report_type': report_type,
                    'report_data': data,
                    'start_date': start_date,
                    'end_date': end_date,
                    'savings_product': savings_product,
                    'format': report_format,
                }
                
                return render(request, 'savings/reports/report_view.html', context)
                
            except Exception as e:
                logger.error(f"Error generating report: {e}")
                messages.error(
                    request,
                    f"Error generating report: {str(e)}",
                    extra_tags='sweetalert-error'
                )
                return redirect("savings:reports")
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = SavingsReportForm()
    
    context = {
        'form': form,
        'title': 'Generate Savings Reports',
    }
    return render(request, 'savings/reports/form.html', context)


@login_required
def account_statement(request, pk):
    """Generate account statement - USES utils.py"""
    account = get_object_or_404(SavingsAccount, pk=pk)
    
    # Get date range from request
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date:
        # Default to current month
        today = timezone.now().date()
        start_date = today.replace(day=1)
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    
    if not end_date:
        end_date = timezone.now().date()
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Get transactions for period
    transactions = account.transactions.filter(
        transaction_date__date__gte=start_date,
        transaction_date__date__lte=end_date,
        is_reversed=False
    ).order_by('transaction_date')
    
    # Format statement using utils
    from .utils import format_account_statement
    statement_data = format_account_statement(
        account=account,
        transactions=transactions,
        start_date=start_date,
        end_date=end_date
    )
    
    context = {
        'account': account,
        'statement': statement_data,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'savings/reports/account_statement.html', context)


