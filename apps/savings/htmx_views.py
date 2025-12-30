# savings/htmx_views.py

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Count, Sum, Avg, F, DecimalField, Case, When, Max, Min
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from datetime import timedelta
from decimal import Decimal
import logging

from .models import (
    SavingsProduct,
    InterestTier,
    SavingsAccount,
    SavingsTransaction,
    InterestCalculation,
    StandingOrder,
    SavingsGoal
)
from core.utils import parse_filters, paginate_queryset, format_money

logger = logging.getLogger(__name__)


# =============================================================================
# SAVINGS PRODUCT SEARCH
# =============================================================================

def savings_product_search(request):
    """HTMX-compatible savings product search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'is_active', 'is_fixed_deposit', 'is_group_product',
        'is_main_account', 'requires_approval', 'interest_calculation_method',
        'interest_posting_frequency', 'allow_overdraft', 'min_interest_rate',
        'max_interest_rate', 'min_balance', 'max_balance'
    ])
    
    query = filters['q']
    is_active = filters['is_active']
    is_fixed_deposit = filters['is_fixed_deposit']
    is_group_product = filters['is_group_product']
    is_main_account = filters['is_main_account']
    requires_approval = filters['requires_approval']
    interest_calculation_method = filters['interest_calculation_method']
    interest_posting_frequency = filters['interest_posting_frequency']
    allow_overdraft = filters['allow_overdraft']
    min_interest_rate = filters['min_interest_rate']
    max_interest_rate = filters['max_interest_rate']
    min_balance = filters['min_balance']
    max_balance = filters['max_balance']
    
    # Build queryset
    products = SavingsProduct.objects.annotate(
        account_count=Count('accounts', distinct=True),
        active_account_count=Count(
            'accounts',
            filter=Q(accounts__status='ACTIVE'),
            distinct=True
        ),
        total_balance=Sum(
            'accounts__current_balance',
            filter=Q(accounts__status__in=['ACTIVE', 'DORMANT'])
        ),
        tier_count=Count('interest_tiers', distinct=True)
    ).order_by('-is_main_account', '-is_active', 'name')
    
    # Apply text search
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(code__icontains=query) |
            Q(description__icontains=query) |
            Q(gl_account_code__icontains=query)
        )
    
    # Apply filters
    if is_active is not None:
        products = products.filter(is_active=(is_active.lower() == 'true'))
    
    if is_fixed_deposit is not None:
        products = products.filter(is_fixed_deposit=(is_fixed_deposit.lower() == 'true'))
    
    if is_group_product is not None:
        products = products.filter(is_group_product=(is_group_product.lower() == 'true'))
    
    if is_main_account is not None:
        products = products.filter(is_main_account=(is_main_account.lower() == 'true'))
    
    if requires_approval is not None:
        products = products.filter(requires_approval=(requires_approval.lower() == 'true'))
    
    if allow_overdraft is not None:
        products = products.filter(allow_overdraft=(allow_overdraft.lower() == 'true'))
    
    if interest_calculation_method:
        products = products.filter(interest_calculation_method=interest_calculation_method)
    
    if interest_posting_frequency:
        products = products.filter(interest_posting_frequency=interest_posting_frequency)
    
    # Interest rate filters
    if min_interest_rate:
        try:
            products = products.filter(interest_rate__gte=Decimal(min_interest_rate))
        except (ValueError, TypeError):
            pass
    
    if max_interest_rate:
        try:
            products = products.filter(interest_rate__lte=Decimal(max_interest_rate))
        except (ValueError, TypeError):
            pass
    
    # Balance filters
    if min_balance:
        try:
            products = products.filter(minimum_opening_balance__gte=Decimal(min_balance))
        except (ValueError, TypeError):
            pass
    
    if max_balance:
        try:
            products = products.filter(minimum_opening_balance__lte=Decimal(max_balance))
        except (ValueError, TypeError):
            pass
    
    # Paginate
    products_page, paginator = paginate_queryset(request, products, per_page=20)
    
    # Calculate stats
    total = products.count()
    
    aggregates = products.aggregate(
        total_accounts=Sum('account_count'),
        total_active_accounts=Sum('active_account_count'),
        total_balance_sum=Sum('total_balance'),
        avg_interest_rate=Avg('interest_rate'),
        min_interest_rate=Min('interest_rate'),
        max_interest_rate=Max('interest_rate')
    )
    
    stats = {
        'total': total,
        'active': products.filter(is_active=True).count(),
        'inactive': products.filter(is_active=False).count(),
        'fixed_deposits': products.filter(is_fixed_deposit=True).count(),
        'regular_savings': products.filter(is_fixed_deposit=False).count(),
        'group_products': products.filter(is_group_product=True).count(),
        'with_overdraft': products.filter(allow_overdraft=True).count(),
        'total_accounts': aggregates['total_accounts'] or 0,
        'total_active_accounts': aggregates['total_active_accounts'] or 0,
        'total_balance': aggregates['total_balance_sum'] or Decimal('0.00'),
        'avg_interest_rate': aggregates['avg_interest_rate'] or Decimal('0.00'),
        'min_interest_rate': aggregates['min_interest_rate'] or Decimal('0.00'),
        'max_interest_rate': aggregates['max_interest_rate'] or Decimal('0.00'),
    }
    
    # Format money in stats
    stats['total_balance_formatted'] = format_money(stats['total_balance'])
    
    return render(request, 'savings/products/_product_results.html', {
        'products_page': products_page,
        'stats': stats,
    })


# =============================================================================
# SAVINGS ACCOUNT SEARCH
# =============================================================================

def savings_account_search(request):
    """HTMX-compatible savings account search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'status', 'savings_product', 'member', 'group',
        'is_fixed_deposit', 'min_balance', 'max_balance',
        'opening_date_from', 'opening_date_to', 'has_overdraft',
        'dormant', 'needs_approval', 'matured'
    ])
    
    query = filters['q']
    status = filters['status']
    savings_product = filters['savings_product']
    member = filters['member']
    group = filters['group']
    is_fixed_deposit = filters['is_fixed_deposit']
    min_balance = filters['min_balance']
    max_balance = filters['max_balance']
    opening_date_from = filters['opening_date_from']
    opening_date_to = filters['opening_date_to']
    has_overdraft = filters['has_overdraft']
    dormant = filters['dormant']
    needs_approval = filters['needs_approval']
    matured = filters['matured']
    
    # Build queryset
    accounts = SavingsAccount.objects.select_related(
        'member',
        'savings_product',
        'group'
    ).annotate(
        transaction_count=Count('transactions', distinct=True),
        last_transaction_date=Max('transactions__transaction_date'),
        total_deposits=Sum(
            'transactions__amount',
            filter=Q(transactions__transaction_type='DEPOSIT')
        ),
        total_withdrawals=Sum(
            'transactions__amount',
            filter=Q(transactions__transaction_type='WITHDRAWAL')
        )
    ).order_by('-opening_date', 'account_number')
    
    # Apply text search
    if query:
        accounts = accounts.filter(
            Q(account_number__icontains=query) |
            Q(member__first_name__icontains=query) |
            Q(member__last_name__icontains=query) |
            Q(member__member_number__icontains=query) |
            Q(savings_product__name__icontains=query) |
            Q(savings_product__code__icontains=query)
        )
    
    # Apply filters
    if status:
        accounts = accounts.filter(status=status)
    
    if savings_product:
        accounts = accounts.filter(savings_product_id=savings_product)
    
    if member:
        accounts = accounts.filter(member_id=member)
    
    if group:
        accounts = accounts.filter(group_id=group)
    
    if is_fixed_deposit is not None:
        accounts = accounts.filter(is_fixed_deposit=(is_fixed_deposit.lower() == 'true'))
    
    # Balance filters
    if min_balance:
        try:
            accounts = accounts.filter(current_balance__gte=Decimal(min_balance))
        except (ValueError, TypeError):
            pass
    
    if max_balance:
        try:
            accounts = accounts.filter(current_balance__lte=Decimal(max_balance))
        except (ValueError, TypeError):
            pass
    
    # Date filters
    if opening_date_from:
        accounts = accounts.filter(opening_date__gte=opening_date_from)
    
    if opening_date_to:
        accounts = accounts.filter(opening_date__lte=opening_date_to)
    
    # Overdraft filter
    if has_overdraft is not None:
        if has_overdraft.lower() == 'true':
            accounts = accounts.filter(overdraft_amount__gt=0)
        else:
            accounts = accounts.filter(overdraft_amount=0)
    
    # Dormant filter
    if dormant and dormant.lower() == 'true':
        accounts = accounts.filter(status='DORMANT')
    
    # Needs approval filter
    if needs_approval and needs_approval.lower() == 'true':
        accounts = accounts.filter(status='PENDING_APPROVAL')
    
    # Matured filter (for fixed deposits)
    if matured is not None:
        today = timezone.now().date()
        if matured.lower() == 'true':
            accounts = accounts.filter(
                is_fixed_deposit=True,
                maturity_date__lte=today
            )
        else:
            accounts = accounts.filter(
                Q(is_fixed_deposit=False) |
                Q(maturity_date__gt=today) |
                Q(maturity_date__isnull=True)
            )
    
    # Paginate
    accounts_page, paginator = paginate_queryset(request, accounts, per_page=20)
    
    # Calculate stats
    total = accounts.count()
    
    aggregates = accounts.aggregate(
        total_balance=Sum('current_balance'),
        total_available=Sum('available_balance'),
        total_hold=Sum('hold_amount'),
        total_overdraft=Sum('overdraft_amount'),
        total_accrued_interest=Sum('accrued_interest'),
        avg_balance=Avg('current_balance')
    )
    
    stats = {
        'total': total,
        'active': accounts.filter(status='ACTIVE').count(),
        'dormant': accounts.filter(status='DORMANT').count(),
        'frozen': accounts.filter(status='FROZEN').count(),
        'closed': accounts.filter(status='CLOSED').count(),
        'pending_approval': accounts.filter(status='PENDING_APPROVAL').count(),
        'fixed_deposits': accounts.filter(is_fixed_deposit=True).count(),
        'regular_savings': accounts.filter(is_fixed_deposit=False).count(),
        'with_overdraft': accounts.filter(overdraft_amount__gt=0).count(),
        'total_balance': aggregates['total_balance'] or Decimal('0.00'),
        'total_available': aggregates['total_available'] or Decimal('0.00'),
        'total_hold': aggregates['total_hold'] or Decimal('0.00'),
        'total_overdraft': aggregates['total_overdraft'] or Decimal('0.00'),
        'total_accrued_interest': aggregates['total_accrued_interest'] or Decimal('0.00'),
        'avg_balance': aggregates['avg_balance'] or Decimal('0.00'),
        'unique_members': accounts.values('member').distinct().count(),
        'unique_products': accounts.values('savings_product').distinct().count(),
    }
    
    # Format money in stats
    stats['total_balance_formatted'] = format_money(stats['total_balance'])
    stats['total_available_formatted'] = format_money(stats['total_available'])
    stats['total_hold_formatted'] = format_money(stats['total_hold'])
    stats['total_overdraft_formatted'] = format_money(stats['total_overdraft'])
    stats['total_accrued_interest_formatted'] = format_money(stats['total_accrued_interest'])
    stats['avg_balance_formatted'] = format_money(stats['avg_balance'])
    
    return render(request, 'savings/accounts/_account_results.html', {
        'accounts_page': accounts_page,
        'stats': stats,
    })


# =============================================================================
# SAVINGS TRANSACTION SEARCH
# =============================================================================

def savings_transaction_search(request):
    """HTMX-compatible savings transaction search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'transaction_type', 'account', 'member', 'payment_method',
        'min_amount', 'max_amount', 'date_from', 'date_to',
        'is_reversed', 'has_reference', 'financial_period'
    ])
    
    query = filters['q']
    transaction_type = filters['transaction_type']
    account = filters['account']
    member = filters['member']
    payment_method = filters['payment_method']
    min_amount = filters['min_amount']
    max_amount = filters['max_amount']
    date_from = filters['date_from']
    date_to = filters['date_to']
    is_reversed = filters['is_reversed']
    has_reference = filters['has_reference']
    financial_period = filters['financial_period']
    
    # Build queryset
    transactions = SavingsTransaction.objects.select_related(
        'account',
        'account__member',
        'account__savings_product',
        'payment_method',
        'financial_period',
        'linked_account'
    ).order_by('-transaction_date', '-created_at')
    
    # Apply text search
    if query:
        transactions = transactions.filter(
            Q(transaction_id__icontains=query) |
            Q(account__account_number__icontains=query) |
            Q(account__member__first_name__icontains=query) |
            Q(account__member__last_name__icontains=query) |
            Q(reference_number__icontains=query) |
            Q(description__icontains=query)
        )
    
    # Apply filters
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)
    
    if account:
        transactions = transactions.filter(account_id=account)
    
    if member:
        transactions = transactions.filter(account__member_id=member)
    
    if payment_method:
        transactions = transactions.filter(payment_method_id=payment_method)
    
    if financial_period:
        transactions = transactions.filter(financial_period_id=financial_period)
    
    # Amount filters
    if min_amount:
        try:
            transactions = transactions.filter(amount__gte=Decimal(min_amount))
        except (ValueError, TypeError):
            pass
    
    if max_amount:
        try:
            transactions = transactions.filter(amount__lte=Decimal(max_amount))
        except (ValueError, TypeError):
            pass
    
    # Date filters
    if date_from:
        transactions = transactions.filter(transaction_date__gte=date_from)
    
    if date_to:
        transactions = transactions.filter(transaction_date__lte=date_to)
    
    # Reversed filter
    if is_reversed is not None:
        transactions = transactions.filter(is_reversed=(is_reversed.lower() == 'true'))
    
    # Reference filter
    if has_reference is not None:
        if has_reference.lower() == 'true':
            transactions = transactions.exclude(Q(reference_number__isnull=True) | Q(reference_number=''))
        else:
            transactions = transactions.filter(Q(reference_number__isnull=True) | Q(reference_number=''))
    
    # Paginate
    transactions_page, paginator = paginate_queryset(request, transactions, per_page=20)
    
    # Calculate stats
    total = transactions.count()
    
    aggregates = transactions.aggregate(
        total_amount=Sum('amount'),
        total_fees=Sum('fees'),
        total_tax=Sum('tax_amount'),
        avg_amount=Avg('amount')
    )
    
    # Count by transaction type
    type_counts = {}
    for txn_type in SavingsTransaction.TRANSACTION_TYPES:
        count = transactions.filter(transaction_type=txn_type[0]).count()
        if count > 0:
            type_counts[txn_type[1]] = count
    
    stats = {
        'total': total,
        'deposits': transactions.filter(transaction_type='DEPOSIT').count(),
        'withdrawals': transactions.filter(transaction_type='WITHDRAWAL').count(),
        'transfers': transactions.filter(transaction_type__in=['TRANSFER_IN', 'TRANSFER_OUT']).count(),
        'interest': transactions.filter(transaction_type='INTEREST').count(),
        'fees': transactions.filter(transaction_type='FEE').count(),
        'reversed': transactions.filter(is_reversed=True).count(),
        'total_amount': aggregates['total_amount'] or Decimal('0.00'),
        'total_fees': aggregates['total_fees'] or Decimal('0.00'),
        'total_tax': aggregates['total_tax'] or Decimal('0.00'),
        'avg_amount': aggregates['avg_amount'] or Decimal('0.00'),
        'unique_accounts': transactions.values('account').distinct().count(),
        'unique_members': transactions.values('account__member').distinct().count(),
        'type_counts': type_counts,
    }
    
    # Format money in stats
    stats['total_amount_formatted'] = format_money(stats['total_amount'])
    stats['total_fees_formatted'] = format_money(stats['total_fees'])
    stats['total_tax_formatted'] = format_money(stats['total_tax'])
    stats['avg_amount_formatted'] = format_money(stats['avg_amount'])
    
    return render(request, 'savings/transactions/_transaction_results.html', {
        'transactions_page': transactions_page,
        'stats': stats,
    })


# =============================================================================
# INTEREST CALCULATION SEARCH
# =============================================================================

def interest_calculation_search(request):
    """HTMX-compatible interest calculation search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'account', 'member', 'is_posted', 'calculation_method',
        'financial_period', 'date_from', 'date_to',
        'min_interest', 'max_interest', 'posted_date_from', 'posted_date_to'
    ])
    
    query = filters['q']
    account = filters['account']
    member = filters['member']
    is_posted = filters['is_posted']
    calculation_method = filters['calculation_method']
    financial_period = filters['financial_period']
    date_from = filters['date_from']
    date_to = filters['date_to']
    min_interest = filters['min_interest']
    max_interest = filters['max_interest']
    posted_date_from = filters['posted_date_from']
    posted_date_to = filters['posted_date_to']
    
    # Build queryset
    calculations = InterestCalculation.objects.select_related(
        'account',
        'account__member',
        'account__savings_product',
        'financial_period',
        'transaction'
    ).order_by('-calculation_date', '-created_at')
    
    # Apply text search
    if query:
        calculations = calculations.filter(
            Q(account__account_number__icontains=query) |
            Q(account__member__first_name__icontains=query) |
            Q(account__member__last_name__icontains=query) |
            Q(account__member__member_number__icontains=query)
        )
    
    # Apply filters
    if account:
        calculations = calculations.filter(account_id=account)
    
    if member:
        calculations = calculations.filter(account__member_id=member)
    
    if is_posted is not None:
        calculations = calculations.filter(is_posted=(is_posted.lower() == 'true'))
    
    if calculation_method:
        calculations = calculations.filter(calculation_method=calculation_method)
    
    if financial_period:
        calculations = calculations.filter(financial_period_id=financial_period)
    
    # Date filters
    if date_from:
        calculations = calculations.filter(calculation_date__gte=date_from)
    
    if date_to:
        calculations = calculations.filter(calculation_date__lte=date_to)
    
    if posted_date_from:
        calculations = calculations.filter(posted_date__gte=posted_date_from)
    
    if posted_date_to:
        calculations = calculations.filter(posted_date__lte=posted_date_to)
    
    # Interest amount filters
    if min_interest:
        try:
            calculations = calculations.filter(net_interest__gte=Decimal(min_interest))
        except (ValueError, TypeError):
            pass
    
    if max_interest:
        try:
            calculations = calculations.filter(net_interest__lte=Decimal(max_interest))
        except (ValueError, TypeError):
            pass
    
    # Paginate
    calculations_page, paginator = paginate_queryset(request, calculations, per_page=20)
    
    # Calculate stats
    total = calculations.count()
    
    aggregates = calculations.aggregate(
        total_gross=Sum('gross_interest'),
        total_tax=Sum('withholding_tax'),
        total_net=Sum('net_interest'),
        avg_gross=Avg('gross_interest'),
        avg_net=Avg('net_interest'),
        avg_rate=Avg('interest_rate')
    )
    
    stats = {
        'total': total,
        'posted': calculations.filter(is_posted=True).count(),
        'pending': calculations.filter(is_posted=False).count(),
        'total_gross': aggregates['total_gross'] or Decimal('0.00'),
        'total_tax': aggregates['total_tax'] or Decimal('0.00'),
        'total_net': aggregates['total_net'] or Decimal('0.00'),
        'avg_gross': aggregates['avg_gross'] or Decimal('0.00'),
        'avg_net': aggregates['avg_net'] or Decimal('0.00'),
        'avg_rate': aggregates['avg_rate'] or Decimal('0.00'),
        'unique_accounts': calculations.values('account').distinct().count(),
        'unique_members': calculations.values('account__member').distinct().count(),
    }
    
    # Format money in stats
    stats['total_gross_formatted'] = format_money(stats['total_gross'])
    stats['total_tax_formatted'] = format_money(stats['total_tax'])
    stats['total_net_formatted'] = format_money(stats['total_net'])
    stats['avg_gross_formatted'] = format_money(stats['avg_gross'])
    stats['avg_net_formatted'] = format_money(stats['avg_net'])
    
    return render(request, 'savings/interest/_calculation_results.html', {
        'calculations_page': calculations_page,
        'stats': stats,
    })


# =============================================================================
# STANDING ORDER SEARCH
# =============================================================================

def standing_order_search(request):
    """HTMX-compatible standing order search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'status', 'frequency', 'source_account', 'destination_account',
        'member', 'min_amount', 'max_amount', 'start_date_from', 'start_date_to',
        'next_run_date_from', 'next_run_date_to', 'has_end_date'
    ])
    
    query = filters['q']
    status = filters['status']
    frequency = filters['frequency']
    source_account = filters['source_account']
    destination_account = filters['destination_account']
    member = filters['member']
    min_amount = filters['min_amount']
    max_amount = filters['max_amount']
    start_date_from = filters['start_date_from']
    start_date_to = filters['start_date_to']
    next_run_date_from = filters['next_run_date_from']
    next_run_date_to = filters['next_run_date_to']
    has_end_date = filters['has_end_date']
    
    # Build queryset
    orders = StandingOrder.objects.select_related(
        'source_account',
        'source_account__member',
        'destination_account',
        'destination_account__member'
    ).order_by('-next_run_date', 'status')
    
    # Apply text search
    if query:
        orders = orders.filter(
            Q(source_account__account_number__icontains=query) |
            Q(source_account__member__first_name__icontains=query) |
            Q(source_account__member__last_name__icontains=query) |
            Q(destination_account__account_number__icontains=query) |
            Q(description__icontains=query)
        )
    
    # Apply filters
    if status:
        orders = orders.filter(status=status)
    
    if frequency:
        orders = orders.filter(frequency=frequency)
    
    if source_account:
        orders = orders.filter(source_account_id=source_account)
    
    if destination_account:
        orders = orders.filter(destination_account_id=destination_account)
    
    if member:
        orders = orders.filter(source_account__member_id=member)
    
    # Amount filters
    if min_amount:
        try:
            orders = orders.filter(amount__gte=Decimal(min_amount))
        except (ValueError, TypeError):
            pass
    
    if max_amount:
        try:
            orders = orders.filter(amount__lte=Decimal(max_amount))
        except (ValueError, TypeError):
            pass
    
    # Date filters
    if start_date_from:
        orders = orders.filter(start_date__gte=start_date_from)
    
    if start_date_to:
        orders = orders.filter(start_date__lte=start_date_to)
    
    if next_run_date_from:
        orders = orders.filter(next_run_date__gte=next_run_date_from)
    
    if next_run_date_to:
        orders = orders.filter(next_run_date__lte=next_run_date_to)
    
    # End date filter
    if has_end_date is not None:
        if has_end_date.lower() == 'true':
            orders = orders.exclude(end_date__isnull=True)
        else:
            orders = orders.filter(end_date__isnull=True)
    
    # Paginate
    orders_page, paginator = paginate_queryset(request, orders, per_page=20)
    
    # Calculate stats
    total = orders.count()
    
    aggregates = orders.aggregate(
        total_amount=Sum('amount'),
        avg_amount=Avg('amount'),
        total_executions=Sum('execution_count')
    )
    
    # Due today
    today = timezone.now().date()
    due_today = orders.filter(status='ACTIVE', next_run_date=today).count()
    
    stats = {
        'total': total,
        'active': orders.filter(status='ACTIVE').count(),
        'paused': orders.filter(status='PAUSED').count(),
        'completed': orders.filter(status='COMPLETED').count(),
        'failed': orders.filter(status='FAILED').count(),
        'cancelled': orders.filter(status='CANCELLED').count(),
        'pending_approval': orders.filter(status='PENDING_APPROVAL').count(),
        'due_today': due_today,
        'overdue': orders.filter(status='ACTIVE', next_run_date__lt=today).count(),
        'total_amount': aggregates['total_amount'] or Decimal('0.00'),
        'avg_amount': aggregates['avg_amount'] or Decimal('0.00'),
        'total_executions': aggregates['total_executions'] or 0,
        'daily': orders.filter(frequency='DAILY').count(),
        'weekly': orders.filter(frequency='WEEKLY').count(),
        'monthly': orders.filter(frequency='MONTHLY').count(),
        'unique_members': orders.values('source_account__member').distinct().count(),
    }
    
    # Format money in stats
    stats['total_amount_formatted'] = format_money(stats['total_amount'])
    stats['avg_amount_formatted'] = format_money(stats['avg_amount'])
    
    return render(request, 'savings/standing_orders/_order_results.html', {
        'orders_page': orders_page,
        'stats': stats,
    })


# =============================================================================
# SAVINGS GOAL SEARCH
# =============================================================================

def savings_goal_search(request):
    """HTMX-compatible savings goal search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'goal_type', 'account', 'member', 'is_achieved',
        'min_target', 'max_target', 'min_progress', 'max_progress',
        'target_date_from', 'target_date_to', 'near_target', 'overdue'
    ])
    
    query = filters['q']
    goal_type = filters['goal_type']
    account = filters['account']
    member = filters['member']
    is_achieved = filters['is_achieved']
    min_target = filters['min_target']
    max_target = filters['max_target']
    min_progress = filters['min_progress']
    max_progress = filters['max_progress']
    target_date_from = filters['target_date_from']
    target_date_to = filters['target_date_to']
    near_target = filters['near_target']
    overdue = filters['overdue']
    
    # Build queryset
    goals = SavingsGoal.objects.select_related(
        'account',
        'account__member',
        'account__savings_product'
    ).order_by('-is_achieved', 'target_date')
    
    # Apply text search
    if query:
        goals = goals.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(account__account_number__icontains=query) |
            Q(account__member__first_name__icontains=query) |
            Q(account__member__last_name__icontains=query)
        )
    
    # Apply filters
    if goal_type:
        goals = goals.filter(goal_type=goal_type)
    
    if account:
        goals = goals.filter(account_id=account)
    
    if member:
        goals = goals.filter(account__member_id=member)
    
    if is_achieved is not None:
        goals = goals.filter(is_achieved=(is_achieved.lower() == 'true'))
    
    # Target amount filters
    if min_target:
        try:
            goals = goals.filter(target_amount__gte=Decimal(min_target))
        except (ValueError, TypeError):
            pass
    
    if max_target:
        try:
            goals = goals.filter(target_amount__lte=Decimal(max_target))
        except (ValueError, TypeError):
            pass
    
    # Progress filters
    if min_progress:
        try:
            goals = goals.filter(progress_percentage__gte=Decimal(min_progress))
        except (ValueError, TypeError):
            pass
    
    if max_progress:
        try:
            goals = goals.filter(progress_percentage__lte=Decimal(max_progress))
        except (ValueError, TypeError):
            pass
    
    # Date filters
    if target_date_from:
        goals = goals.filter(target_date__gte=target_date_from)
    
    if target_date_to:
        goals = goals.filter(target_date__lte=target_date_to)
    
    # Near target filter (90% or more progress)
    if near_target and near_target.lower() == 'true':
        goals = goals.filter(progress_percentage__gte=90, is_achieved=False)
    
    # Overdue filter
    if overdue and overdue.lower() == 'true':
        today = timezone.now().date()
        goals = goals.filter(target_date__lt=today, is_achieved=False)
    
    # Paginate
    goals_page, paginator = paginate_queryset(request, goals, per_page=20)
    
    # Calculate stats
    total = goals.count()
    
    aggregates = goals.aggregate(
        total_target=Sum('target_amount'),
        total_current=Sum('current_amount'),
        avg_progress=Avg('progress_percentage')
    )
    
    today = timezone.now().date()
    
    stats = {
        'total': total,
        'achieved': goals.filter(is_achieved=True).count(),
        'in_progress': goals.filter(is_achieved=False).count(),
        'near_target': goals.filter(progress_percentage__gte=90, is_achieved=False).count(),
        'overdue': goals.filter(target_date__lt=today, is_achieved=False).count(),
        'total_target': aggregates['total_target'] or Decimal('0.00'),
        'total_current': aggregates['total_current'] or Decimal('0.00'),
        'avg_progress': aggregates['avg_progress'] or Decimal('0.00'),
        'unique_members': goals.values('account__member').distinct().count(),
        'unique_accounts': goals.values('account').distinct().count(),
    }
    
    # Count by goal type
    type_counts = {}
    for gt in SavingsGoal.GOAL_TYPE_CHOICES:
        count = goals.filter(goal_type=gt[0]).count()
        if count > 0:
            type_counts[gt[1]] = count
    
    stats['type_counts'] = type_counts
    
    # Format money in stats
    stats['total_target_formatted'] = format_money(stats['total_target'])
    stats['total_current_formatted'] = format_money(stats['total_current'])
    
    return render(request, 'savings/goals/_goal_results.html', {
        'goals_page': goals_page,
        'stats': stats,
    })


# =============================================================================
# QUICK STATS ENDPOINTS
# =============================================================================

@require_http_methods(["GET"])
def savings_product_quick_stats(request):
    """Get quick statistics for savings products"""
    
    aggregates = SavingsProduct.objects.aggregate(
        total_products=Count('id'),
        active_products=Count('id', filter=Q(is_active=True)),
        total_accounts=Count('accounts', distinct=True),
        total_balance=Sum('accounts__current_balance', filter=Q(accounts__status__in=['ACTIVE', 'DORMANT']))
    )
    
    stats = {
        'total_products': aggregates['total_products'] or 0,
        'active_products': aggregates['active_products'] or 0,
        'fixed_deposits': SavingsProduct.objects.filter(is_fixed_deposit=True, is_active=True).count(),
        'regular_savings': SavingsProduct.objects.filter(is_fixed_deposit=False, is_active=True).count(),
        'total_accounts': aggregates['total_accounts'] or 0,
        'total_balance': str(aggregates['total_balance'] or Decimal('0.00')),
        'total_balance_formatted': format_money(aggregates['total_balance'] or Decimal('0.00')),
    }
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def savings_account_quick_stats(request):
    """Get quick statistics for savings accounts"""
    
    aggregates = SavingsAccount.objects.aggregate(
        total_balance=Sum('current_balance'),
        total_available=Sum('available_balance'),
        total_accrued_interest=Sum('accrued_interest'),
        avg_balance=Avg('current_balance')
    )
    
    stats = {
        'total_accounts': SavingsAccount.objects.count(),
        'active': SavingsAccount.objects.filter(status='ACTIVE').count(),
        'dormant': SavingsAccount.objects.filter(status='DORMANT').count(),
        'pending_approval': SavingsAccount.objects.filter(status='PENDING_APPROVAL').count(),
        'total_balance': str(aggregates['total_balance'] or Decimal('0.00')),
        'total_balance_formatted': format_money(aggregates['total_balance'] or Decimal('0.00')),
        'total_available': str(aggregates['total_available'] or Decimal('0.00')),
        'total_available_formatted': format_money(aggregates['total_available'] or Decimal('0.00')),
        'total_accrued_interest': str(aggregates['total_accrued_interest'] or Decimal('0.00')),
        'total_accrued_interest_formatted': format_money(aggregates['total_accrued_interest'] or Decimal('0.00')),
        'avg_balance': str(aggregates['avg_balance'] or Decimal('0.00')),
        'avg_balance_formatted': format_money(aggregates['avg_balance'] or Decimal('0.00')),
    }
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def savings_transaction_quick_stats(request):
    """Get quick statistics for savings transactions"""
    
    today = timezone.now().date()
    
    # Today's transactions
    today_txns = SavingsTransaction.objects.filter(
        transaction_date__date=today,
        is_reversed=False
    )
    
    today_aggregates = today_txns.aggregate(
        total_deposits=Sum('amount', filter=Q(transaction_type='DEPOSIT')),
        total_withdrawals=Sum('amount', filter=Q(transaction_type='WITHDRAWAL')),
        count=Count('id')
    )
    
    # Overall stats
    overall_aggregates = SavingsTransaction.objects.filter(is_reversed=False).aggregate(
        total_deposits=Sum('amount', filter=Q(transaction_type='DEPOSIT')),
        total_withdrawals=Sum('amount', filter=Q(transaction_type='WITHDRAWAL'))
    )
    
    stats = {
        'total_transactions': SavingsTransaction.objects.count(),
        'today_count': today_aggregates['count'] or 0,
        'today_deposits': str(today_aggregates['total_deposits'] or Decimal('0.00')),
        'today_deposits_formatted': format_money(today_aggregates['total_deposits'] or Decimal('0.00')),
        'today_withdrawals': str(today_aggregates['total_withdrawals'] or Decimal('0.00')),
        'today_withdrawals_formatted': format_money(today_aggregates['total_withdrawals'] or Decimal('0.00')),
        'total_deposits': str(overall_aggregates['total_deposits'] or Decimal('0.00')),
        'total_deposits_formatted': format_money(overall_aggregates['total_deposits'] or Decimal('0.00')),
        'total_withdrawals': str(overall_aggregates['total_withdrawals'] or Decimal('0.00')),
        'total_withdrawals_formatted': format_money(overall_aggregates['total_withdrawals'] or Decimal('0.00')),
        'reversed': SavingsTransaction.objects.filter(is_reversed=True).count(),
    }
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def standing_order_quick_stats(request):
    """Get quick statistics for standing orders"""
    
    today = timezone.now().date()
    
    stats = {
        'total_orders': StandingOrder.objects.count(),
        'active': StandingOrder.objects.filter(status='ACTIVE').count(),
        'paused': StandingOrder.objects.filter(status='PAUSED').count(),
        'due_today': StandingOrder.objects.filter(status='ACTIVE', next_run_date=today).count(),
        'overdue': StandingOrder.objects.filter(status='ACTIVE', next_run_date__lt=today).count(),
        'pending_approval': StandingOrder.objects.filter(status='PENDING_APPROVAL').count(),
    }
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def savings_goal_quick_stats(request):
    """Get quick statistics for savings goals"""
    
    today = timezone.now().date()
    
    aggregates = SavingsGoal.objects.aggregate(
        total_target=Sum('target_amount'),
        total_current=Sum('current_amount'),
        avg_progress=Avg('progress_percentage')
    )
    
    stats = {
        'total_goals': SavingsGoal.objects.count(),
        'achieved': SavingsGoal.objects.filter(is_achieved=True).count(),
        'in_progress': SavingsGoal.objects.filter(is_achieved=False).count(),
        'near_target': SavingsGoal.objects.filter(progress_percentage__gte=90, is_achieved=False).count(),
        'overdue': SavingsGoal.objects.filter(target_date__lt=today, is_achieved=False).count(),
        'total_target': str(aggregates['total_target'] or Decimal('0.00')),
        'total_target_formatted': format_money(aggregates['total_target'] or Decimal('0.00')),
        'total_current': str(aggregates['total_current'] or Decimal('0.00')),
        'total_current_formatted': format_money(aggregates['total_current'] or Decimal('0.00')),
        'avg_progress': round(aggregates['avg_progress'] or 0, 2),
    }
    
    return JsonResponse(stats)


# =============================================================================
# ACCOUNT-SPECIFIC STATS
# =============================================================================

@require_http_methods(["GET"])
def account_detail_stats(request, account_id):
    """Get detailed statistics for a specific savings account"""
    
    account = get_object_or_404(SavingsAccount, id=account_id)
    
    transactions = account.transactions.filter(is_reversed=False)
    
    aggregates = transactions.aggregate(
        total_deposits=Sum('amount', filter=Q(transaction_type='DEPOSIT')),
        total_withdrawals=Sum('amount', filter=Q(transaction_type='WITHDRAWAL')),
        total_interest=Sum('amount', filter=Q(transaction_type='INTEREST')),
        total_fees=Sum('fees'),
        transaction_count=Count('id')
    )
    
    stats = {
        'account_number': account.account_number,
        'account_status': account.get_status_display(),
        'current_balance': str(account.current_balance),
        'current_balance_formatted': format_money(account.current_balance),
        'available_balance': str(account.available_balance),
        'available_balance_formatted': format_money(account.available_balance),
        'accrued_interest': str(account.accrued_interest),
        'accrued_interest_formatted': format_money(account.accrued_interest),
        'transaction_count': aggregates['transaction_count'] or 0,
        'total_deposits': str(aggregates['total_deposits'] or Decimal('0.00')),
        'total_deposits_formatted': format_money(aggregates['total_deposits'] or Decimal('0.00')),
        'total_withdrawals': str(aggregates['total_withdrawals'] or Decimal('0.00')),
        'total_withdrawals_formatted': format_money(aggregates['total_withdrawals'] or Decimal('0.00')),
        'total_interest': str(aggregates['total_interest'] or Decimal('0.00')),
        'total_interest_formatted': format_money(aggregates['total_interest'] or Decimal('0.00')),
        'total_fees': str(aggregates['total_fees'] or Decimal('0.00')),
        'total_fees_formatted': format_money(aggregates['total_fees'] or Decimal('0.00')),
        'goal_count': account.savings_goals.count(),
        'standing_order_count': account.standing_orders_out.filter(status='ACTIVE').count(),
    }
    
    return JsonResponse(stats)

# =============================================================================
# AJAX/API VIEWS FOR DYNAMIC DATA
# =============================================================================

@require_http_methods(["GET"])
def get_account_balance(request, pk):
    """Get current account balance - AJAX endpoint"""
    account = get_object_or_404(SavingsAccount, pk=pk)
    
    return JsonResponse({
        'account_number': account.account_number,
        'current_balance': float(account.current_balance),
        'available_balance': float(account.available_balance),
        'formatted_current': format_money(account.current_balance),
        'formatted_available': format_money(account.available_balance),
    })


@require_http_methods(["GET"])
def validate_withdrawal_ajax(request):
    """Validate withdrawal amount - AJAX endpoint"""
    account_id = request.GET.get('account_id')
    amount = request.GET.get('amount')
    
    if not account_id or not amount:
        return JsonResponse({'valid': False, 'message': 'Missing parameters'})
    
    try:
        account = SavingsAccount.objects.get(pk=account_id)
        amount_decimal = Decimal(amount)
        
        from .utils import validate_withdrawal
        is_valid, message = validate_withdrawal(account, amount_decimal)
        
        return JsonResponse({
            'valid': is_valid,
            'message': message
        })
    except (SavingsAccount.DoesNotExist, ValueError, Decimal.InvalidOperation):
        return JsonResponse({'valid': False, 'message': 'Invalid request'})


@require_http_methods(["GET"])
def calculate_withdrawal_fee(request):
    """Calculate withdrawal fee - AJAX endpoint"""
    account_id = request.GET.get('account_id')
    amount = request.GET.get('amount')
    
    if not account_id or not amount:
        return JsonResponse({'fee': 0})
    
    try:
        account = SavingsAccount.objects.get(pk=account_id)
        amount_decimal = Decimal(amount)
        
        fee = account.savings_product.calculate_withdrawal_fee(amount_decimal)
        
        return JsonResponse({
            'fee': float(fee),
            'formatted_fee': format_money(fee),
            'total': float(amount_decimal + fee),
            'formatted_total': format_money(amount_decimal + fee),
        })
    except (SavingsAccount.DoesNotExist, ValueError, Decimal.InvalidOperation):
        return JsonResponse({'fee': 0})


@require_http_methods(["GET"])
def get_product_details(request, pk):
    """Get product details - AJAX endpoint"""
    product = get_object_or_404(SavingsProduct, pk=pk)
    
    return JsonResponse({
        'name': product.name,
        'code': product.code,
        'interest_rate': float(product.interest_rate),
        'minimum_balance': float(product.minimum_balance),
        'minimum_opening_balance': float(product.minimum_opening_balance),
        'minimum_deposit': float(product.minimum_deposit_amount),
        'minimum_withdrawal': float(product.minimum_withdrawal_amount),
        'is_fixed_deposit': product.is_fixed_deposit,
        'requires_approval': product.requires_approval,
    })