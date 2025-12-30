# savings/stats.py

"""
Comprehensive statistics utility functions for Savings models.
Provides detailed analytics for savings products, accounts, transactions,
interest calculations, standing orders, and savings goals.
"""

from django.utils import timezone
from django.db.models import (
    Count, Q, Avg, Sum, Max, Min, F, Case, When,
    IntegerField, FloatField, DecimalField, Value
)
from django.db.models.functions import TruncMonth, TruncYear, TruncWeek, TruncDate, TruncQuarter
from datetime import timedelta, date, datetime
from decimal import Decimal
import logging

from core.utils import format_money, get_base_currency

logger = logging.getLogger(__name__)

# =============================================================================
# SAVINGS PRODUCT STATISTICS
# =============================================================================

def get_product_statistics(filters=None):
    """
    Get comprehensive savings product statistics
    
    Args:
        filters (dict): Optional filters
            - is_active: Filter by active status
            - is_main_account: Filter main account products
            - is_fixed_deposit: Filter fixed deposit products
            - is_group_product: Filter group products
    
    Returns:
        dict: Product statistics
    """
    from .models import SavingsProduct, SavingsAccount
    
    products = SavingsProduct.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('is_active') is not None:
            products = products.filter(is_active=filters['is_active'])
        if filters.get('is_main_account') is not None:
            products = products.filter(is_main_account=filters['is_main_account'])
        if filters.get('is_fixed_deposit') is not None:
            products = products.filter(is_fixed_deposit=filters['is_fixed_deposit'])
        if filters.get('is_group_product') is not None:
            products = products.filter(is_group_product=filters['is_group_product'])
    
    total_products = products.count()
    
    stats = {
        'total_products': total_products,
        'active_products': products.filter(is_active=True).count(),
        'inactive_products': products.filter(is_active=False).count(),
        'main_account_products': products.filter(is_main_account=True).count(),
        'fixed_deposit_products': products.filter(is_fixed_deposit=True).count(),
        'regular_savings_products': products.filter(is_fixed_deposit=False).count(),
        'group_products': products.filter(is_group_product=True).count(),
        'individual_products': products.filter(is_group_product=False).count(),
    }
    
    # Product configuration analysis
    stats['requires_approval'] = products.filter(requires_approval=True).count()
    stats['allows_overdraft'] = products.filter(allow_overdraft=True).count()
    stats['with_gl_account'] = products.filter(gl_account_code__isnull=False).exclude(gl_account_code='').count()
    
    # Interest calculation methods
    interest_methods = products.values('interest_calculation_method').annotate(
        count=Count('id')
    ).order_by('-count')
    
    stats['interest_calculation_methods'] = [
        {
            'method': item['interest_calculation_method'],
            'count': item['count'],
            'percentage': round((item['count'] / total_products * 100) if total_products > 0 else 0, 2)
        }
        for item in interest_methods
    ]
    
    # Interest rates analysis
    interest_stats = products.aggregate(
        avg_rate=Avg('interest_rate'),
        max_rate=Max('interest_rate'),
        min_rate=Min('interest_rate'),
        avg_overdraft_rate=Avg('overdraft_interest_rate'),
    )
    
    stats['interest_rates'] = {
        'average': float(interest_stats['avg_rate'] or 0),
        'maximum': float(interest_stats['max_rate'] or 0),
        'minimum': float(interest_stats['min_rate'] or 0),
        'avg_overdraft': float(interest_stats['avg_overdraft_rate'] or 0),
    }
    
    # Balance requirements analysis
    balance_stats = products.aggregate(
        avg_min_opening=Avg('minimum_opening_balance'),
        avg_min_balance=Avg('minimum_balance'),
        max_min_opening=Max('minimum_opening_balance'),
        max_min_balance=Max('minimum_balance'),
    )
    
    stats['balance_requirements'] = {
        'avg_minimum_opening': float(balance_stats['avg_min_opening'] or 0),
        'avg_minimum_balance': float(balance_stats['avg_min_balance'] or 0),
        'max_minimum_opening': float(balance_stats['max_min_opening'] or 0),
        'max_minimum_balance': float(balance_stats['max_min_balance'] or 0),
    }
    
    # Fee structure analysis
    fee_stats = products.aggregate(
        avg_withdrawal_flat=Avg('withdrawal_fee_flat'),
        avg_withdrawal_pct=Avg('withdrawal_fee_percentage'),
        avg_deposit_flat=Avg('deposit_fee_flat'),
        avg_deposit_pct=Avg('deposit_fee_percentage'),
        avg_maintenance=Avg('account_maintenance_fee'),
    )
    
    stats['fees'] = {
        'avg_withdrawal_flat': float(fee_stats['avg_withdrawal_flat'] or 0),
        'avg_withdrawal_percentage': float(fee_stats['avg_withdrawal_pct'] or 0),
        'avg_deposit_flat': float(fee_stats['avg_deposit_flat'] or 0),
        'avg_deposit_percentage': float(fee_stats['avg_deposit_pct'] or 0),
        'avg_maintenance_fee': float(fee_stats['avg_maintenance'] or 0),
    }
    
    # Products with fees
    stats['products_with_fees'] = {
        'withdrawal_fees': products.filter(
            Q(withdrawal_fee_flat__gt=0) | Q(withdrawal_fee_percentage__gt=0)
        ).count(),
        'deposit_fees': products.filter(
            Q(deposit_fee_flat__gt=0) | Q(deposit_fee_percentage__gt=0)
        ).count(),
        'maintenance_fees': products.filter(account_maintenance_fee__gt=0).count(),
    }
    
    # Account limits per member
    limit_distribution = products.values('maximum_accounts_per_member').annotate(
        count=Count('id')
    ).order_by('maximum_accounts_per_member')
    
    stats['account_limits'] = [
        {
            'limit': item['maximum_accounts_per_member'],
            'product_count': item['count'],
        }
        for item in limit_distribution
    ]
    
    # Fixed deposit terms
    if products.filter(is_fixed_deposit=True).exists():
        fd_stats = products.filter(is_fixed_deposit=True).aggregate(
            avg_min_term=Avg('minimum_term_days'),
            max_min_term=Max('minimum_term_days'),
            avg_penalty=Avg('early_withdrawal_penalty_rate'),
        )
        
        stats['fixed_deposit_terms'] = {
            'avg_minimum_term_days': round(float(fd_stats['avg_min_term'] or 0), 0),
            'max_minimum_term_days': fd_stats['max_min_term'] or 0,
            'avg_early_withdrawal_penalty': float(fd_stats['avg_penalty'] or 0),
        }
    
    # Product usage - accounts per product
    product_usage = products.annotate(
        account_count=Count('accounts'),
        active_account_count=Count('accounts', filter=Q(accounts__status='ACTIVE')),
        total_balance=Sum('accounts__current_balance', filter=Q(accounts__status__in=['ACTIVE', 'DORMANT'])),
    ).order_by('-account_count')
    
    stats['top_products_by_accounts'] = [
        {
            'product_id': str(prod.id),
            'name': prod.name,
            'code': prod.code,
            'account_count': prod.account_count or 0,
            'active_accounts': prod.active_account_count or 0,
            'total_balance': float(prod.total_balance or 0),
            'is_fixed_deposit': prod.is_fixed_deposit,
            'interest_rate': float(prod.interest_rate),
        }
        for prod in product_usage[:10]
    ]
    
    # Product health score
    # Healthy products are active, have accounts, and have GL integration
    healthy_products = products.filter(
        is_active=True,
        gl_account_code__isnull=False
    ).exclude(gl_account_code='').annotate(
        account_count=Count('accounts')
    ).filter(account_count__gt=0)
    
    stats['health_score'] = {
        'healthy_products': healthy_products.count(),
        'health_percentage': round(
            (healthy_products.count() / total_products * 100) if total_products > 0 else 0,
            2
        ),
    }
    
    # Recent activity
    now = timezone.now()
    stats['recent_activity'] = {
        'created_last_7_days': products.filter(created_at__gte=now - timedelta(days=7)).count(),
        'created_last_30_days': products.filter(created_at__gte=now - timedelta(days=30)).count(),
        'updated_last_7_days': products.filter(updated_at__gte=now - timedelta(days=7)).count(),
    }
    
    return stats


def get_product_performance_breakdown(product_id=None):
    """
    Get detailed performance breakdown for savings products
    
    Args:
        product_id: Optional specific product ID
    
    Returns:
        dict: Product performance breakdown
    """
    from .models import SavingsProduct, SavingsAccount, SavingsTransaction
    
    if product_id:
        products = SavingsProduct.objects.filter(id=product_id)
    else:
        products = SavingsProduct.objects.filter(is_active=True)
    
    breakdown = []
    
    for product in products:
        accounts = SavingsAccount.objects.filter(savings_product=product)
        
        # Account statistics
        account_stats = accounts.aggregate(
            total_count=Count('id'),
            active_count=Count('id', filter=Q(status='ACTIVE')),
            dormant_count=Count('id', filter=Q(status='DORMANT')),
            frozen_count=Count('id', filter=Q(status='FROZEN')),
            closed_count=Count('id', filter=Q(status='CLOSED')),
            pending_count=Count('id', filter=Q(status='PENDING_APPROVAL')),
            total_balance=Sum('current_balance', filter=Q(status__in=['ACTIVE', 'DORMANT'])),
            total_available=Sum('available_balance', filter=Q(status__in=['ACTIVE', 'DORMANT'])),
            total_holds=Sum('hold_amount'),
            total_accrued_interest=Sum('accrued_interest'),
            total_interest_earned=Sum('total_interest_earned'),
            avg_balance=Avg('current_balance', filter=Q(status__in=['ACTIVE', 'DORMANT'])),
        )
        
        # Transaction statistics
        transactions = SavingsTransaction.objects.filter(
            account__savings_product=product,
            is_reversed=False
        )
        
        transaction_stats = transactions.aggregate(
            total_transactions=Count('id'),
            total_deposits=Count('id', filter=Q(transaction_type='DEPOSIT')),
            total_withdrawals=Count('id', filter=Q(transaction_type='WITHDRAWAL')),
            deposit_amount=Sum('amount', filter=Q(transaction_type='DEPOSIT')),
            withdrawal_amount=Sum('amount', filter=Q(transaction_type='WITHDRAWAL')),
            total_fees=Sum('fees'),
            total_taxes=Sum('tax_amount'),
        )
        
        # Interest calculations
        from .models import InterestCalculation
        interest_calcs = InterestCalculation.objects.filter(
            account__savings_product=product
        )
        
        interest_stats = interest_calcs.aggregate(
            total_calculations=Count('id'),
            posted_calculations=Count('id', filter=Q(is_posted=True)),
            gross_interest=Sum('gross_interest'),
            withholding_tax=Sum('withholding_tax'),
            net_interest=Sum('net_interest'),
        )
        
        # Fixed deposit specific stats
        fd_stats = None
        if product.is_fixed_deposit:
            fd_accounts = accounts.filter(is_fixed_deposit=True)
            fd_stats = {
                'total_fd_accounts': fd_accounts.count(),
                'matured_accounts': fd_accounts.filter(maturity_date__lte=timezone.now().date()).count(),
                'active_fd_accounts': fd_accounts.filter(status='ACTIVE').count(),
                'total_fd_amount': float(fd_accounts.aggregate(
                    total=Sum('fixed_deposit_amount')
                )['total'] or 0),
                'auto_renew_enabled': fd_accounts.filter(auto_renew=True).count(),
            }
        
        # Calculate averages
        active_account_count = account_stats['active_count'] or 0
        avg_transactions_per_account = (
            transaction_stats['total_transactions'] / active_account_count 
            if active_account_count > 0 else 0
        )
        
        breakdown.append({
            'product_id': str(product.id),
            'product_name': product.name,
            'product_code': product.code,
            'is_fixed_deposit': product.is_fixed_deposit,
            'is_group_product': product.is_group_product,
            'interest_rate': float(product.interest_rate),
            'accounts': {
                'total': account_stats['total_count'] or 0,
                'active': account_stats['active_count'] or 0,
                'dormant': account_stats['dormant_count'] or 0,
                'frozen': account_stats['frozen_count'] or 0,
                'closed': account_stats['closed_count'] or 0,
                'pending_approval': account_stats['pending_count'] or 0,
            },
            'balances': {
                'total_balance': float(account_stats['total_balance'] or 0),
                'total_available': float(account_stats['total_available'] or 0),
                'total_holds': float(account_stats['total_holds'] or 0),
                'avg_balance': float(account_stats['avg_balance'] or 0),
            },
            'interest': {
                'total_accrued': float(account_stats['total_accrued_interest'] or 0),
                'total_earned': float(account_stats['total_interest_earned'] or 0),
                'calculations_count': interest_stats['total_calculations'] or 0,
                'posted_calculations': interest_stats['posted_calculations'] or 0,
                'gross_interest': float(interest_stats['gross_interest'] or 0),
                'withholding_tax': float(interest_stats['withholding_tax'] or 0),
                'net_interest': float(interest_stats['net_interest'] or 0),
            },
            'transactions': {
                'total': transaction_stats['total_transactions'] or 0,
                'deposits': transaction_stats['total_deposits'] or 0,
                'withdrawals': transaction_stats['total_withdrawals'] or 0,
                'deposit_amount': float(transaction_stats['deposit_amount'] or 0),
                'withdrawal_amount': float(transaction_stats['withdrawal_amount'] or 0),
                'total_fees_collected': float(transaction_stats['total_fees'] or 0),
                'total_taxes_collected': float(transaction_stats['total_taxes'] or 0),
                'avg_per_account': round(avg_transactions_per_account, 2),
            },
            'fixed_deposit': fd_stats,
        })
    
    return {
        'products_analyzed': len(breakdown),
        'breakdown': breakdown,
    }


# =============================================================================
# SAVINGS ACCOUNT STATISTICS
# =============================================================================

def get_account_statistics(filters=None):
    """
    Get comprehensive savings account statistics
    
    Args:
        filters (dict): Optional filters
            - status: Filter by account status
            - member_id: Filter by specific member
            - product_id: Filter by specific product
            - is_fixed_deposit: Filter fixed deposit accounts
            - date_from: Filter accounts opened from date
            - date_to: Filter accounts opened to date
    
    Returns:
        dict: Account statistics
    """
    from .models import SavingsAccount
    
    accounts = SavingsAccount.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('status'):
            accounts = accounts.filter(status=filters['status'])
        if filters.get('member_id'):
            accounts = accounts.filter(member_id=filters['member_id'])
        if filters.get('product_id'):
            accounts = accounts.filter(savings_product_id=filters['product_id'])
        if filters.get('is_fixed_deposit') is not None:
            accounts = accounts.filter(is_fixed_deposit=filters['is_fixed_deposit'])
        if filters.get('date_from'):
            accounts = accounts.filter(opening_date__gte=filters['date_from'])
        if filters.get('date_to'):
            accounts = accounts.filter(opening_date__lte=filters['date_to'])
    
    total_accounts = accounts.count()
    
    stats = {
        'total_accounts': total_accounts,
    }
    
    # Status breakdown
    status_breakdown = accounts.values('status').annotate(
        count=Count('id'),
        total_balance=Sum('current_balance'),
    ).order_by('-count')
    
    stats['by_status'] = [
        {
            'status': item['status'],
            'count': item['count'],
            'total_balance': float(item['total_balance'] or 0),
            'percentage': round((item['count'] / total_accounts * 100) if total_accounts > 0 else 0, 2),
        }
        for item in status_breakdown
    ]
    
    # Balance statistics
    balance_stats = accounts.filter(status__in=['ACTIVE', 'DORMANT']).aggregate(
        total_balance=Sum('current_balance'),
        total_available=Sum('available_balance'),
        total_holds=Sum('hold_amount'),
        total_overdraft=Sum('overdraft_amount'),
        total_accrued_interest=Sum('accrued_interest'),
        avg_balance=Avg('current_balance'),
        max_balance=Max('current_balance'),
        min_balance=Min('current_balance'),
    )
    
    stats['balances'] = {
        'total_balance': float(balance_stats['total_balance'] or 0),
        'total_available': float(balance_stats['total_available'] or 0),
        'total_holds': float(balance_stats['total_holds'] or 0),
        'total_overdraft': float(balance_stats['total_overdraft'] or 0),
        'total_accrued_interest': float(balance_stats['total_accrued_interest'] or 0),
        'average_balance': float(balance_stats['avg_balance'] or 0),
        'highest_balance': float(balance_stats['max_balance'] or 0),
        'lowest_balance': float(balance_stats['min_balance'] or 0),
    }
    
    # Balance distribution
    balance_ranges = {
        'below_10k': accounts.filter(current_balance__lt=10000).count(),
        '10k_50k': accounts.filter(current_balance__gte=10000, current_balance__lt=50000).count(),
        '50k_100k': accounts.filter(current_balance__gte=50000, current_balance__lt=100000).count(),
        '100k_500k': accounts.filter(current_balance__gte=100000, current_balance__lt=500000).count(),
        '500k_1m': accounts.filter(current_balance__gte=500000, current_balance__lt=1000000).count(),
        'above_1m': accounts.filter(current_balance__gte=1000000).count(),
    }
    
    stats['balance_distribution'] = balance_ranges
    
    # Interest statistics
    interest_stats = accounts.aggregate(
        total_interest_earned=Sum('total_interest_earned'),
        avg_interest_earned=Avg('total_interest_earned'),
        accounts_with_interest=Count('id', filter=Q(total_interest_earned__gt=0)),
    )
    
    stats['interest'] = {
        'total_earned': float(interest_stats['total_interest_earned'] or 0),
        'average_per_account': float(interest_stats['avg_interest_earned'] or 0),
        'accounts_earning_interest': interest_stats['accounts_with_interest'] or 0,
    }
    
    # Fixed deposit statistics
    fd_accounts = accounts.filter(is_fixed_deposit=True)
    fd_stats = fd_accounts.aggregate(
        total_fd=Count('id'),
        active_fd=Count('id', filter=Q(status='ACTIVE')),
        total_fd_amount=Sum('fixed_deposit_amount'),
        avg_fd_amount=Avg('fixed_deposit_amount'),
        avg_term_days=Avg('term_length_days'),
    )
    
    # Maturity analysis
    today = timezone.now().date()
    maturity_stats = {
        'matured': fd_accounts.filter(maturity_date__lte=today).count(),
        'maturing_30_days': fd_accounts.filter(
            maturity_date__gt=today,
            maturity_date__lte=today + timedelta(days=30)
        ).count(),
        'maturing_90_days': fd_accounts.filter(
            maturity_date__gt=today,
            maturity_date__lte=today + timedelta(days=90)
        ).count(),
        'auto_renew_enabled': fd_accounts.filter(auto_renew=True).count(),
    }
    
    stats['fixed_deposits'] = {
        'total': fd_stats['total_fd'] or 0,
        'active': fd_stats['active_fd'] or 0,
        'total_amount': float(fd_stats['total_fd_amount'] or 0),
        'average_amount': float(fd_stats['avg_fd_amount'] or 0),
        'average_term_days': round(float(fd_stats['avg_term_days'] or 0), 0),
        'maturity': maturity_stats,
    }
    
    # Overdraft statistics
    overdraft_stats = accounts.filter(overdraft_amount__gt=0).aggregate(
        accounts_with_overdraft=Count('id'),
        total_overdraft=Sum('overdraft_amount'),
        avg_overdraft=Avg('overdraft_amount'),
    )
    
    stats['overdrafts'] = {
        'accounts_with_overdraft': overdraft_stats['accounts_with_overdraft'] or 0,
        'total_overdraft_amount': float(overdraft_stats['total_overdraft'] or 0),
        'average_overdraft': float(overdraft_stats['avg_overdraft'] or 0),
    }
    
    # Account age analysis
    active_accounts = accounts.filter(status__in=['ACTIVE', 'DORMANT'])
    age_ranges = {
        'under_6_months': active_accounts.filter(
            opening_date__gte=today - timedelta(days=180)
        ).count(),
        '6_12_months': active_accounts.filter(
            opening_date__gte=today - timedelta(days=365),
            opening_date__lt=today - timedelta(days=180)
        ).count(),
        '1_2_years': active_accounts.filter(
            opening_date__gte=today - timedelta(days=730),
            opening_date__lt=today - timedelta(days=365)
        ).count(),
        '2_5_years': active_accounts.filter(
            opening_date__gte=today - timedelta(days=1825),
            opening_date__lt=today - timedelta(days=730)
        ).count(),
        'over_5_years': active_accounts.filter(
            opening_date__lt=today - timedelta(days=1825)
        ).count(),
    }
    
    stats['account_age_distribution'] = age_ranges
    
    # Dormancy analysis
    dormant_eligible = 0
    for account in active_accounts.filter(status='ACTIVE'):
        if account.is_dormant_eligible:
            dormant_eligible += 1
    
    stats['dormancy'] = {
        'dormant_accounts': accounts.filter(status='DORMANT').count(),
        'eligible_for_dormancy': dormant_eligible,
    }
    
    # Recent activity
    now = timezone.now()
    stats['recent_activity'] = {
        'opened_last_7_days': accounts.filter(opening_date__gte=today - timedelta(days=7)).count(),
        'opened_last_30_days': accounts.filter(opening_date__gte=today - timedelta(days=30)).count(),
        'opened_last_90_days': accounts.filter(opening_date__gte=today - timedelta(days=90)).count(),
        'activated_last_30_days': accounts.filter(
            activated_date__gte=today - timedelta(days=30)
        ).count(),
        'closed_last_30_days': accounts.filter(
            closure_date__gte=today - timedelta(days=30)
        ).count(),
    }
    
    # Top accounts by balance
    top_accounts = accounts.filter(
        status__in=['ACTIVE', 'DORMANT']
    ).order_by('-current_balance')[:10]
    
    stats['top_accounts_by_balance'] = [
        {
            'account_number': acc.account_number,
            'member_name': acc.member.get_full_name(),
            'product_name': acc.savings_product.name,
            'balance': float(acc.current_balance),
            'status': acc.status,
        }
        for acc in top_accounts
    ]
    
    return stats


# =============================================================================
# TRANSACTION STATISTICS
# =============================================================================

def get_transaction_statistics(filters=None):
    """
    Get comprehensive transaction statistics
    
    Args:
        filters (dict): Optional filters
            - transaction_type: Filter by transaction type
            - date_from: Filter transactions from date
            - date_to: Filter transactions to date
            - account_id: Filter by specific account
            - member_id: Filter by member's accounts
            - product_id: Filter by product's accounts
    
    Returns:
        dict: Transaction statistics
    """
    from .models import SavingsTransaction
    
    transactions = SavingsTransaction.objects.filter(is_reversed=False)
    
    # Apply filters
    if filters:
        if filters.get('transaction_type'):
            transactions = transactions.filter(transaction_type=filters['transaction_type'])
        if filters.get('date_from'):
            transactions = transactions.filter(transaction_date__gte=filters['date_from'])
        if filters.get('date_to'):
            transactions = transactions.filter(transaction_date__lte=filters['date_to'])
        if filters.get('account_id'):
            transactions = transactions.filter(account_id=filters['account_id'])
        if filters.get('member_id'):
            transactions = transactions.filter(account__member_id=filters['member_id'])
        if filters.get('product_id'):
            transactions = transactions.filter(account__savings_product_id=filters['product_id'])
    
    total_transactions = transactions.count()
    
    stats = {
        'total_transactions': total_transactions,
        'reversed_transactions': SavingsTransaction.objects.filter(is_reversed=True).count(),
    }
    
    # Transaction type breakdown
    type_breakdown = transactions.values('transaction_type').annotate(
        count=Count('id'),
        total_amount=Sum('amount'),
        avg_amount=Avg('amount'),
    ).order_by('-count')
    
    stats['by_type'] = [
        {
            'type': item['transaction_type'],
            'count': item['count'],
            'total_amount': float(item['total_amount'] or 0),
            'average_amount': float(item['avg_amount'] or 0),
            'percentage': round((item['count'] / total_transactions * 100) if total_transactions > 0 else 0, 2),
        }
        for item in type_breakdown
    ]
    
    # Amount statistics
    amount_stats = transactions.aggregate(
        total_amount=Sum('amount'),
        avg_amount=Avg('amount'),
        max_amount=Max('amount'),
        min_amount=Min('amount'),
        total_fees=Sum('fees'),
        total_taxes=Sum('tax_amount'),
    )
    
    stats['amounts'] = {
        'total_transacted': float(amount_stats['total_amount'] or 0),
        'average_transaction': float(amount_stats['avg_amount'] or 0),
        'largest_transaction': float(amount_stats['max_amount'] or 0),
        'smallest_transaction': float(amount_stats['min_amount'] or 0),
        'total_fees_collected': float(amount_stats['total_fees'] or 0),
        'total_taxes_collected': float(amount_stats['total_taxes'] or 0),
    }
    
    # Deposits vs Withdrawals
    deposits = transactions.filter(transaction_type='DEPOSIT')
    withdrawals = transactions.filter(transaction_type='WITHDRAWAL')
    
    deposit_stats = deposits.aggregate(
        count=Count('id'),
        total_amount=Sum('amount'),
        avg_amount=Avg('amount'),
    )
    
    withdrawal_stats = withdrawals.aggregate(
        count=Count('id'),
        total_amount=Sum('amount'),
        avg_amount=Avg('amount'),
    )
    
    stats['deposits'] = {
        'count': deposit_stats['count'] or 0,
        'total_amount': float(deposit_stats['total_amount'] or 0),
        'average_amount': float(deposit_stats['avg_amount'] or 0),
    }
    
    stats['withdrawals'] = {
        'count': withdrawal_stats['count'] or 0,
        'total_amount': float(withdrawal_stats['total_amount'] or 0),
        'average_amount': float(withdrawal_stats['avg_amount'] or 0),
    }
    
    # Net flow (deposits - withdrawals)
    net_flow = (deposit_stats['total_amount'] or 0) - (withdrawal_stats['total_amount'] or 0)
    stats['net_flow'] = float(net_flow)
    
    # Payment method breakdown
    payment_method_breakdown = transactions.filter(
        payment_method__isnull=False
    ).values('payment_method__name').annotate(
        count=Count('id'),
        total_amount=Sum('amount'),
    ).order_by('-count')
    
    stats['by_payment_method'] = [
        {
            'payment_method': item['payment_method__name'],
            'count': item['count'],
            'total_amount': float(item['total_amount'] or 0),
        }
        for item in payment_method_breakdown[:10]
    ]
    
    # Transfers
    transfers_in = transactions.filter(transaction_type='TRANSFER_IN')
    transfers_out = transactions.filter(transaction_type='TRANSFER_OUT')
    
    stats['transfers'] = {
        'transfers_in': transfers_in.count(),
        'transfers_out': transfers_out.count(),
        'total_transferred_in': float(transfers_in.aggregate(total=Sum('amount'))['total'] or 0),
        'total_transferred_out': float(transfers_out.aggregate(total=Sum('amount'))['total'] or 0),
    }
    
    # Interest transactions
    interest_txns = transactions.filter(transaction_type='INTEREST')
    stats['interest_transactions'] = {
        'count': interest_txns.count(),
        'total_posted': float(interest_txns.aggregate(total=Sum('amount'))['total'] or 0),
        'average_posting': float(interest_txns.aggregate(avg=Avg('amount'))['avg'] or 0),
    }
    
    # Fee and tax transactions
    fee_txns = transactions.filter(transaction_type='FEE')
    tax_txns = transactions.filter(transaction_type='TAX')
    
    stats['fees_and_taxes'] = {
        'fee_transactions': fee_txns.count(),
        'tax_transactions': tax_txns.count(),
        'total_fees': float(fee_txns.aggregate(total=Sum('amount'))['total'] or 0),
        'total_taxes': float(tax_txns.aggregate(total=Sum('amount'))['total'] or 0),
    }
    
    # Daily transaction trends (last 30 days)
    today = timezone.now().date()
    thirty_days_ago = today - timedelta(days=30)
    
    daily_trends = transactions.filter(
        transaction_date__gte=thirty_days_ago
    ).annotate(
        date=TruncDate('transaction_date')
    ).values('date').annotate(
        count=Count('id'),
        total_amount=Sum('amount'),
    ).order_by('date')
    
    stats['daily_trends_30_days'] = [
        {
            'date': item['date'].isoformat(),
            'count': item['count'],
            'total_amount': float(item['total_amount'] or 0),
        }
        for item in daily_trends
    ]
    
    # Peak transaction times
    if total_transactions > 0:
        hourly_distribution = transactions.annotate(
            hour=F('transaction_date__hour')
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('-count')
        
        stats['peak_hours'] = [
            {
                'hour': item['hour'],
                'count': item['count'],
                'percentage': round((item['count'] / total_transactions * 100), 2),
            }
            for item in hourly_distribution[:5]
        ]
    
    # Recent activity
    stats['recent_activity'] = {
        'last_24_hours': transactions.filter(
            transaction_date__gte=timezone.now() - timedelta(hours=24)
        ).count(),
        'last_7_days': transactions.filter(
            transaction_date__gte=timezone.now() - timedelta(days=7)
        ).count(),
        'last_30_days': transactions.filter(
            transaction_date__gte=timezone.now() - timedelta(days=30)
        ).count(),
    }
    
    return stats


def get_transaction_trends(period='monthly', months=12):
    """
    Get transaction trends over time
    
    Args:
        period: 'daily', 'weekly', 'monthly', 'quarterly', 'yearly'
        months: Number of months to analyze (for monthly period)
    
    Returns:
        dict: Transaction trends data
    """
    from .models import SavingsTransaction
    
    end_date = timezone.now()
    
    if period == 'monthly':
        start_date = end_date - timedelta(days=30 * months)
        trunc_func = TruncMonth
    elif period == 'weekly':
        start_date = end_date - timedelta(weeks=months * 4)
        trunc_func = TruncWeek
    elif period == 'quarterly':
        start_date = end_date - timedelta(days=90 * months)
        trunc_func = TruncQuarter
    elif period == 'yearly':
        start_date = end_date - timedelta(days=365 * months)
        trunc_func = TruncYear
    else:  # daily
        start_date = end_date - timedelta(days=months * 30)
        trunc_func = TruncDate
    
    transactions = SavingsTransaction.objects.filter(
        transaction_date__gte=start_date,
        is_reversed=False
    )
    
    # Overall trends
    trends = transactions.annotate(
        period=trunc_func('transaction_date')
    ).values('period').annotate(
        count=Count('id'),
        total_amount=Sum('amount'),
        deposits=Count('id', filter=Q(transaction_type='DEPOSIT')),
        withdrawals=Count('id', filter=Q(transaction_type='WITHDRAWAL')),
        deposit_amount=Sum('amount', filter=Q(transaction_type='DEPOSIT')),
        withdrawal_amount=Sum('amount', filter=Q(transaction_type='WITHDRAWAL')),
    ).order_by('period')
    
    trend_data = [
        {
            'period': item['period'].isoformat() if hasattr(item['period'], 'isoformat') else str(item['period']),
            'transactions': item['count'],
            'total_amount': float(item['total_amount'] or 0),
            'deposits': item['deposits'],
            'withdrawals': item['withdrawals'],
            'deposit_amount': float(item['deposit_amount'] or 0),
            'withdrawal_amount': float(item['withdrawal_amount'] or 0),
            'net_flow': float((item['deposit_amount'] or 0) - (item['withdrawal_amount'] or 0)),
        }
        for item in trends
    ]
    
    return {
        'period': period,
        'start_date': start_date.date().isoformat(),
        'end_date': end_date.date().isoformat(),
        'data': trend_data,
    }


# =============================================================================
# INTEREST CALCULATION STATISTICS
# =============================================================================

def get_interest_statistics(filters=None):
    """
    Get interest calculation statistics
    
    Args:
        filters (dict): Optional filters
            - is_posted: Filter by posting status
            - date_from: Filter from calculation date
            - date_to: Filter to calculation date
            - product_id: Filter by product
    
    Returns:
        dict: Interest statistics
    """
    from .models import InterestCalculation
    
    calculations = InterestCalculation.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('is_posted') is not None:
            calculations = calculations.filter(is_posted=filters['is_posted'])
        if filters.get('date_from'):
            calculations = calculations.filter(calculation_date__gte=filters['date_from'])
        if filters.get('date_to'):
            calculations = calculations.filter(calculation_date__lte=filters['date_to'])
        if filters.get('product_id'):
            calculations = calculations.filter(account__savings_product_id=filters['product_id'])
    
    total_calculations = calculations.count()
    
    stats = {
        'total_calculations': total_calculations,
        'posted_calculations': calculations.filter(is_posted=True).count(),
        'pending_calculations': calculations.filter(is_posted=False).count(),
    }
    
    # Amount statistics
    amount_stats = calculations.aggregate(
        total_gross=Sum('gross_interest'),
        total_tax=Sum('withholding_tax'),
        total_net=Sum('net_interest'),
        avg_gross=Avg('gross_interest'),
        avg_net=Avg('net_interest'),
        max_interest=Max('gross_interest'),
    )
    
    stats['amounts'] = {
        'total_gross_interest': float(amount_stats['total_gross'] or 0),
        'total_withholding_tax': float(amount_stats['total_tax'] or 0),
        'total_net_interest': float(amount_stats['total_net'] or 0),
        'average_gross_interest': float(amount_stats['avg_gross'] or 0),
        'average_net_interest': float(amount_stats['avg_net'] or 0),
        'highest_interest_payment': float(amount_stats['max_interest'] or 0),
    }
    
    # Posted vs pending amounts
    posted = calculations.filter(is_posted=True)
    pending = calculations.filter(is_posted=False)
    
    stats['posted_amounts'] = {
        'gross_interest': float(posted.aggregate(total=Sum('gross_interest'))['total'] or 0),
        'net_interest': float(posted.aggregate(total=Sum('net_interest'))['total'] or 0),
    }
    
    stats['pending_amounts'] = {
        'gross_interest': float(pending.aggregate(total=Sum('gross_interest'))['total'] or 0),
        'net_interest': float(pending.aggregate(total=Sum('net_interest'))['total'] or 0),
    }
    
    # Calculation method breakdown
    method_breakdown = calculations.values('calculation_method').annotate(
        count=Count('id'),
        total_interest=Sum('gross_interest'),
    ).order_by('-count')
    
    stats['by_method'] = [
        {
            'method': item['calculation_method'],
            'count': item['count'],
            'total_interest': float(item['total_interest'] or 0),
        }
        for item in method_breakdown
    ]
    
    # Tax statistics
    tax_stats = calculations.aggregate(
        avg_tax_rate=Avg('tax_rate'),
        total_tax=Sum('withholding_tax'),
        calculations_with_tax=Count('id', filter=Q(withholding_tax__gt=0)),
    )
    
    stats['tax'] = {
        'average_tax_rate': float(tax_stats['avg_tax_rate'] or 0),
        'total_tax_withheld': float(tax_stats['total_tax'] or 0),
        'calculations_with_tax': tax_stats['calculations_with_tax'] or 0,
    }
    
    # Recent calculations
    now = timezone.now()
    today = now.date()
    
    stats['recent_activity'] = {
        'calculated_today': calculations.filter(calculation_date=today).count(),
        'posted_today': calculations.filter(posted_date=today).count(),
        'calculated_last_7_days': calculations.filter(
            calculation_date__gte=today - timedelta(days=7)
        ).count(),
        'posted_last_7_days': calculations.filter(
            posted_date__gte=today - timedelta(days=7)
        ).count(),
    }
    
    # Monthly interest trends
    monthly_trends = calculations.filter(
        calculation_date__gte=today - timedelta(days=365)
    ).annotate(
        month=TruncMonth('calculation_date')
    ).values('month').annotate(
        count=Count('id'),
        gross_interest=Sum('gross_interest'),
        net_interest=Sum('net_interest'),
    ).order_by('month')
    
    stats['monthly_trends'] = [
        {
            'month': item['month'].isoformat(),
            'calculations': item['count'],
            'gross_interest': float(item['gross_interest'] or 0),
            'net_interest': float(item['net_interest'] or 0),
        }
        for item in monthly_trends
    ]
    
    return stats


# =============================================================================
# STANDING ORDER STATISTICS
# =============================================================================

def get_standing_order_statistics(filters=None):
    """
    Get standing order statistics
    
    Args:
        filters (dict): Optional filters
            - status: Filter by status
            - frequency: Filter by frequency
            - member_id: Filter by member
    
    Returns:
        dict: Standing order statistics
    """
    from .models import StandingOrder
    
    orders = StandingOrder.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('status'):
            orders = orders.filter(status=filters['status'])
        if filters.get('frequency'):
            orders = orders.filter(frequency=filters['frequency'])
        if filters.get('member_id'):
            orders = orders.filter(source_account__member_id=filters['member_id'])
    
    total_orders = orders.count()
    
    stats = {
        'total_orders': total_orders,
    }
    
    # Status breakdown
    status_breakdown = orders.values('status').annotate(
        count=Count('id'),
        total_amount=Sum('amount'),
    ).order_by('-count')
    
    stats['by_status'] = [
        {
            'status': item['status'],
            'count': item['count'],
            'total_amount': float(item['total_amount'] or 0),
            'percentage': round((item['count'] / total_orders * 100) if total_orders > 0 else 0, 2),
        }
        for item in status_breakdown
    ]
    
    # Frequency breakdown
    frequency_breakdown = orders.values('frequency').annotate(
        count=Count('id'),
        total_amount=Sum('amount'),
    ).order_by('-count')
    
    stats['by_frequency'] = [
        {
            'frequency': item['frequency'],
            'count': item['count'],
            'total_amount': float(item['total_amount'] or 0),
        }
        for item in frequency_breakdown
    ]
    
    # Amount statistics
    amount_stats = orders.aggregate(
        total_amount=Sum('amount'),
        avg_amount=Avg('amount'),
        max_amount=Max('amount'),
        min_amount=Min('amount'),
    )
    
    stats['amounts'] = {
        'total_transfer_amount': float(amount_stats['total_amount'] or 0),
        'average_amount': float(amount_stats['avg_amount'] or 0),
        'largest_amount': float(amount_stats['max_amount'] or 0),
        'smallest_amount': float(amount_stats['min_amount'] or 0),
    }
    
    # Execution statistics
    execution_stats = orders.aggregate(
        total_executions=Sum('execution_count'),
        avg_executions=Avg('execution_count'),
        orders_with_executions=Count('id', filter=Q(execution_count__gt=0)),
    )
    
    stats['executions'] = {
        'total_executions': execution_stats['total_executions'] or 0,
        'average_per_order': float(execution_stats['avg_executions'] or 0),
        'orders_executed': execution_stats['orders_with_executions'] or 0,
        'orders_never_executed': total_orders - (execution_stats['orders_with_executions'] or 0),
    }
    
    # Due orders
    today = timezone.now().date()
    stats['due_orders'] = {
        'due_today': orders.filter(status='ACTIVE', next_run_date=today).count(),
        'due_this_week': orders.filter(
            status='ACTIVE',
            next_run_date__gte=today,
            next_run_date__lte=today + timedelta(days=7)
        ).count(),
        'due_this_month': orders.filter(
            status='ACTIVE',
            next_run_date__gte=today,
            next_run_date__lte=today + timedelta(days=30)
        ).count(),
    }
    
    # Failed orders
    failed_orders = orders.filter(last_execution_status='FAILED')
    stats['failures'] = {
        'orders_with_failures': failed_orders.count(),
        'total_amount_failed': float(failed_orders.aggregate(
            total=Sum('amount')
        )['total'] or 0),
    }
    
    return stats


# =============================================================================
# SAVINGS GOAL STATISTICS
# =============================================================================

def get_savings_goal_statistics(filters=None):
    """
    Get savings goal statistics
    
    Args:
        filters (dict): Optional filters
            - is_achieved: Filter by achievement status
            - goal_type: Filter by goal type
            - member_id: Filter by member
    
    Returns:
        dict: Savings goal statistics
    """
    from .models import SavingsGoal
    
    goals = SavingsGoal.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('is_achieved') is not None:
            goals = goals.filter(is_achieved=filters['is_achieved'])
        if filters.get('goal_type'):
            goals = goals.filter(goal_type=filters['goal_type'])
        if filters.get('member_id'):
            goals = goals.filter(account__member_id=filters['member_id'])
    
    total_goals = goals.count()
    
    stats = {
        'total_goals': total_goals,
        'achieved_goals': goals.filter(is_achieved=True).count(),
        'active_goals': goals.filter(is_achieved=False).count(),
    }
    
    # Goal type breakdown
    type_breakdown = goals.values('goal_type').annotate(
        count=Count('id'),
        achieved_count=Count('id', filter=Q(is_achieved=True)),
        total_target=Sum('target_amount'),
        total_current=Sum('current_amount'),
    ).order_by('-count')
    
    stats['by_type'] = [
        {
            'type': item['goal_type'],
            'count': item['count'],
            'achieved': item['achieved_count'],
            'total_target': float(item['total_target'] or 0),
            'total_saved': float(item['total_current'] or 0),
            'achievement_rate': round(
                (item['achieved_count'] / item['count'] * 100) if item['count'] > 0 else 0,
                2
            ),
        }
        for item in type_breakdown
    ]
    
    # Amount statistics
    amount_stats = goals.aggregate(
        total_target=Sum('target_amount'),
        total_current=Sum('current_amount'),
        avg_target=Avg('target_amount'),
        avg_current=Avg('current_amount'),
        avg_progress=Avg('progress_percentage'),
    )
    
    total_target = float(amount_stats['total_target'] or 0)
    total_current = float(amount_stats['total_current'] or 0)
    total_remaining = total_target - total_current
    
    stats['amounts'] = {
        'total_target_amount': total_target,
        'total_saved': total_current,
        'total_remaining': total_remaining,
        'average_target': float(amount_stats['avg_target'] or 0),
        'average_saved': float(amount_stats['avg_current'] or 0),
        'overall_progress': round(
            (total_current / total_target * 100) if total_target > 0 else 0,
            2
        ),
    }
    
    # Progress distribution
    active_goals = goals.filter(is_achieved=False)
    progress_ranges = {
        '0_25': active_goals.filter(progress_percentage__lt=25).count(),
        '25_50': active_goals.filter(progress_percentage__gte=25, progress_percentage__lt=50).count(),
        '50_75': active_goals.filter(progress_percentage__gte=50, progress_percentage__lt=75).count(),
        '75_100': active_goals.filter(progress_percentage__gte=75, progress_percentage__lt=100).count(),
    }
    
    stats['progress_distribution'] = progress_ranges
    
    # Timeline analysis
    today = timezone.now().date()
    
    timeline_stats = {
        'overdue': active_goals.filter(target_date__lt=today).count(),
        'due_this_month': active_goals.filter(
            target_date__gte=today,
            target_date__lte=today + timedelta(days=30)
        ).count(),
        'due_this_quarter': active_goals.filter(
            target_date__gte=today,
            target_date__lte=today + timedelta(days=90)
        ).count(),
        'due_this_year': active_goals.filter(
            target_date__gte=today,
            target_date__lte=today + timedelta(days=365)
        ).count(),
    }
    
    stats['timeline'] = timeline_stats
    
    # Achievement statistics
    achieved_goals = goals.filter(is_achieved=True)
    if achieved_goals.exists():
        achievement_stats = achieved_goals.aggregate(
            avg_days_to_achieve=Avg(
                F('achievement_date') - F('start_date'),
                output_field=IntegerField()
            ),
        )
        
        stats['achievement'] = {
            'total_achieved': achieved_goals.count(),
            'achievement_rate': round(
                (achieved_goals.count() / total_goals * 100) if total_goals > 0 else 0,
                2
            ),
            'total_achieved_amount': float(achieved_goals.aggregate(
                total=Sum('target_amount')
            )['total'] or 0),
        }
        
        # Recent achievements
        stats['recent_achievements'] = {
            'last_7_days': achieved_goals.filter(
                achievement_date__gte=today - timedelta(days=7)
            ).count(),
            'last_30_days': achieved_goals.filter(
                achievement_date__gte=today - timedelta(days=30)
            ).count(),
            'last_90_days': achieved_goals.filter(
                achievement_date__gte=today - timedelta(days=90)
            ).count(),
        }
    
    # Top goals by amount
    top_goals = goals.order_by('-target_amount')[:10]
    
    stats['top_goals_by_target'] = [
        {
            'goal_name': goal.name,
            'goal_type': goal.goal_type,
            'target_amount': float(goal.target_amount),
            'current_amount': float(goal.current_amount),
            'progress': float(goal.progress_percentage),
            'is_achieved': goal.is_achieved,
        }
        for goal in top_goals
    ]
    
    return stats


# =============================================================================
# COMPREHENSIVE SAVINGS OVERVIEW
# =============================================================================

def get_savings_overview(date_from=None, date_to=None):
    """
    Get comprehensive savings overview with all key metrics
    
    Args:
        date_from: Optional start date for filtering
        date_to: Optional end date for filtering
    
    Returns:
        dict: Comprehensive savings overview
    """
    from .models import SavingsProduct, SavingsAccount, SavingsTransaction
    
    # Set default date range if not provided
    if not date_to:
        date_to = timezone.now().date()
    if not date_from:
        date_from = date_to - timedelta(days=30)
    
    overview = {
        'report_period': {
            'from': date_from.isoformat(),
            'to': date_to.isoformat(),
        },
        'currency': get_base_currency(),
    }
    
    # Products summary
    products = SavingsProduct.objects.all()
    overview['products'] = {
        'total': products.count(),
        'active': products.filter(is_active=True).count(),
        'fixed_deposit': products.filter(is_fixed_deposit=True, is_active=True).count(),
        'regular_savings': products.filter(is_fixed_deposit=False, is_active=True).count(),
    }
    
    # Accounts summary
    accounts = SavingsAccount.objects.all()
    active_accounts = accounts.filter(status__in=['ACTIVE', 'DORMANT'])
    
    account_balances = active_accounts.aggregate(
        total_balance=Sum('current_balance'),
        total_available=Sum('available_balance'),
        total_accrued_interest=Sum('accrued_interest'),
    )
    
    overview['accounts'] = {
        'total': accounts.count(),
        'active': accounts.filter(status='ACTIVE').count(),
        'dormant': accounts.filter(status='DORMANT').count(),
        'pending_approval': accounts.filter(status='PENDING_APPROVAL').count(),
        'total_balance': float(account_balances['total_balance'] or 0),
        'total_available': float(account_balances['total_available'] or 0),
        'total_accrued_interest': float(account_balances['total_accrued_interest'] or 0),
    }
    
    # Transactions summary for period
    transactions = SavingsTransaction.objects.filter(
        transaction_date__date__gte=date_from,
        transaction_date__date__lte=date_to,
        is_reversed=False
    )
    
    transaction_summary = transactions.aggregate(
        total_count=Count('id'),
        deposits=Count('id', filter=Q(transaction_type='DEPOSIT')),
        withdrawals=Count('id', filter=Q(transaction_type='WITHDRAWAL')),
        deposit_amount=Sum('amount', filter=Q(transaction_type='DEPOSIT')),
        withdrawal_amount=Sum('amount', filter=Q(transaction_type='WITHDRAWAL')),
        total_fees=Sum('fees'),
        total_taxes=Sum('tax_amount'),
    )
    
    overview['transactions'] = {
        'total': transaction_summary['total_count'] or 0,
        'deposits': transaction_summary['deposits'] or 0,
        'withdrawals': transaction_summary['withdrawals'] or 0,
        'deposit_amount': float(transaction_summary['deposit_amount'] or 0),
        'withdrawal_amount': float(transaction_summary['withdrawal_amount'] or 0),
        'net_flow': float((transaction_summary['deposit_amount'] or 0) - (transaction_summary['withdrawal_amount'] or 0)),
        'fees_collected': float(transaction_summary['total_fees'] or 0),
        'taxes_collected': float(transaction_summary['total_taxes'] or 0),
    }
    
    # Interest summary
    from .models import InterestCalculation
    interest_calcs = InterestCalculation.objects.filter(
        calculation_date__gte=date_from,
        calculation_date__lte=date_to
    )
    
    interest_summary = interest_calcs.aggregate(
        total_calculations=Count('id'),
        posted=Count('id', filter=Q(is_posted=True)),
        gross_interest=Sum('gross_interest'),
        withholding_tax=Sum('withholding_tax'),
        net_interest=Sum('net_interest'),
    )
    
    overview['interest'] = {
        'calculations': interest_summary['total_calculations'] or 0,
        'posted': interest_summary['posted'] or 0,
        'gross_interest': float(interest_summary['gross_interest'] or 0),
        'withholding_tax': float(interest_summary['withholding_tax'] or 0),
        'net_interest': float(interest_summary['net_interest'] or 0),
    }
    
    # Standing orders
    from .models import StandingOrder
    standing_orders = StandingOrder.objects.all()
    
    overview['standing_orders'] = {
        'total': standing_orders.count(),
        'active': standing_orders.filter(status='ACTIVE').count(),
        'due_this_month': standing_orders.filter(
            status='ACTIVE',
            next_run_date__gte=date_to,
            next_run_date__lte=date_to + timedelta(days=30)
        ).count(),
    }
    
    # Savings goals
    from .models import SavingsGoal
    goals = SavingsGoal.objects.all()
    
    goal_summary = goals.aggregate(
        total_goals=Count('id'),
        achieved=Count('id', filter=Q(is_achieved=True)),
        total_target=Sum('target_amount'),
        total_saved=Sum('current_amount'),
    )
    
    overview['savings_goals'] = {
        'total': goal_summary['total_goals'] or 0,
        'achieved': goal_summary['achieved'] or 0,
        'active': (goal_summary['total_goals'] or 0) - (goal_summary['achieved'] or 0),
        'total_target': float(goal_summary['total_target'] or 0),
        'total_saved': float(goal_summary['total_saved'] or 0),
    }
    
    # Growth metrics (compare with previous period)
    previous_date_from = date_from - (date_to - date_from)
    previous_date_to = date_from - timedelta(days=1)
    
    previous_transactions = SavingsTransaction.objects.filter(
        transaction_date__date__gte=previous_date_from,
        transaction_date__date__lte=previous_date_to,
        is_reversed=False
    )
    
    previous_summary = previous_transactions.aggregate(
        deposit_amount=Sum('amount', filter=Q(transaction_type='DEPOSIT')),
        withdrawal_amount=Sum('amount', filter=Q(transaction_type='WITHDRAWAL')),
    )
    
    current_deposits = float(transaction_summary['deposit_amount'] or 0)
    previous_deposits = float(previous_summary['deposit_amount'] or 0)
    
    deposit_growth = (
        ((current_deposits - previous_deposits) / previous_deposits * 100)
        if previous_deposits > 0 else 0
    )
    
    overview['growth'] = {
        'deposit_growth_percentage': round(deposit_growth, 2),
        'new_accounts_in_period': accounts.filter(
            opening_date__gte=date_from,
            opening_date__lte=date_to
        ).count(),
    }
    
    return overview