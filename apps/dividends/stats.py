# dividends/stats.py

"""
Comprehensive statistics utility functions for Dividends models.
Provides detailed analytics for dividend periods, member dividends,
disbursements, payments, and preferences.
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
# DIVIDEND PERIOD STATISTICS
# =============================================================================

def get_dividend_period_statistics(filters=None):
    """
    Get comprehensive dividend period statistics
    
    Args:
        filters (dict): Optional filters
            - status: Filter by period status
            - financial_period_id: Filter by financial period
            - date_from: Filter periods ending from date
            - date_to: Filter periods ending to date
            - is_approved: Filter by approval status
    
    Returns:
        dict: Dividend period statistics
    """
    from .models import DividendPeriod
    
    periods = DividendPeriod.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('status'):
            periods = periods.filter(status=filters['status'])
        if filters.get('financial_period_id'):
            periods = periods.filter(financial_period_id=filters['financial_period_id'])
        if filters.get('date_from'):
            periods = periods.filter(end_date__gte=filters['date_from'])
        if filters.get('date_to'):
            periods = periods.filter(end_date__lte=filters['date_to'])
        if filters.get('is_approved') is not None:
            periods = periods.filter(is_approved=filters['is_approved'])
    
    total_periods = periods.count()
    
    stats = {
        'total_periods': total_periods,
    }
    
    # Status breakdown
    status_breakdown = periods.values('status').annotate(
        count=Count('id'),
        total_amount=Sum('total_dividend_amount'),
        total_members=Sum('total_members'),
        total_shares=Sum('total_shares'),
    ).order_by('-count')
    
    stats['by_status'] = [
        {
            'status': item['status'],
            'count': item['count'],
            'total_amount': float(item['total_amount'] or 0),
            'total_members': item['total_members'] or 0,
            'total_shares': item['total_shares'] or 0,
            'percentage': round((item['count'] / total_periods * 100) if total_periods > 0 else 0, 2),
        }
        for item in status_breakdown
    ]
    
    # Amount statistics
    amount_stats = periods.aggregate(
        total_dividend_amount=Sum('total_dividend_amount'),
        avg_dividend_amount=Avg('total_dividend_amount'),
        max_dividend_amount=Max('total_dividend_amount'),
        min_dividend_amount=Min('total_dividend_amount'),
        total_shares_value=Sum('total_shares_value'),
        avg_dividend_rate=Avg('dividend_rate'),
        max_dividend_rate=Max('dividend_rate'),
        min_dividend_rate=Min('dividend_rate'),
    )
    
    stats['amounts'] = {
        'total_dividend_amount': float(amount_stats['total_dividend_amount'] or 0),
        'avg_dividend_amount': float(amount_stats['avg_dividend_amount'] or 0),
        'max_dividend_amount': float(amount_stats['max_dividend_amount'] or 0),
        'min_dividend_amount': float(amount_stats['min_dividend_amount'] or 0),
        'total_shares_value': float(amount_stats['total_shares_value'] or 0),
    }
    
    # Rate statistics
    stats['rates'] = {
        'avg_dividend_rate': float(amount_stats['avg_dividend_rate'] or 0),
        'max_dividend_rate': float(amount_stats['max_dividend_rate'] or 0),
        'min_dividend_rate': float(amount_stats['min_dividend_rate'] or 0),
    }
    
    # Member and share statistics
    member_stats = periods.aggregate(
        total_members_all=Sum('total_members'),
        avg_members_per_period=Avg('total_members'),
        total_shares_all=Sum('total_shares'),
        avg_shares_per_period=Avg('total_shares'),
    )
    
    stats['members_and_shares'] = {
        'total_members_all_periods': member_stats['total_members_all'] or 0,
        'avg_members_per_period': round(float(member_stats['avg_members_per_period'] or 0), 2),
        'total_shares_all_periods': member_stats['total_shares_all'] or 0,
        'avg_shares_per_period': round(float(member_stats['avg_shares_per_period'] or 0), 2),
    }
    
    # Calculation method breakdown
    method_breakdown = periods.values('calculation_method').annotate(
        count=Count('id'),
        total_amount=Sum('total_dividend_amount'),
    ).order_by('-count')
    
    stats['by_calculation_method'] = [
        {
            'method': item['calculation_method'],
            'count': item['count'],
            'total_amount': float(item['total_amount'] or 0),
            'percentage': round((item['count'] / total_periods * 100) if total_periods > 0 else 0, 2),
        }
        for item in method_breakdown
    ]
    
    # Tax configuration
    tax_stats = periods.aggregate(
        periods_with_tax=Count('id', filter=Q(apply_withholding_tax=True)),
        avg_tax_rate=Avg('withholding_tax_rate', filter=Q(apply_withholding_tax=True)),
        max_tax_rate=Max('withholding_tax_rate'),
    )
    
    stats['tax'] = {
        'periods_with_tax': tax_stats['periods_with_tax'] or 0,
        'periods_without_tax': total_periods - (tax_stats['periods_with_tax'] or 0),
        'avg_tax_rate': float(tax_stats['avg_tax_rate'] or 0),
        'max_tax_rate': float(tax_stats['max_tax_rate'] or 0),
    }
    
    # Disbursement method
    disbursement_breakdown = periods.values('default_disbursement_method').annotate(
        count=Count('id')
    ).order_by('-count')
    
    stats['by_disbursement_method'] = [
        {
            'method': item['default_disbursement_method'],
            'count': item['count'],
            'percentage': round((item['count'] / total_periods * 100) if total_periods > 0 else 0, 2),
        }
        for item in disbursement_breakdown
    ]
    
    # Approval statistics
    approved_periods = periods.filter(is_approved=True)
    pending_approval = periods.filter(status='CALCULATED', is_approved=False)
    
    stats['approval'] = {
        'approved_periods': approved_periods.count(),
        'pending_approval': pending_approval.count(),
        'approval_rate': round(
            (approved_periods.count() / total_periods * 100) if total_periods > 0 else 0,
            2
        ),
    }
    
    # Active periods
    today = timezone.now().date()
    active_periods = periods.filter(
        status__in=['OPEN', 'CALCULATING', 'CALCULATED', 'APPROVED', 'DISBURSING']
    )
    
    stats['active'] = {
        'active_periods': active_periods.count(),
        'open_periods': periods.filter(status='OPEN').count(),
        'calculating': periods.filter(status='CALCULATING').count(),
        'ready_to_approve': periods.filter(status='CALCULATED', is_approved=False).count(),
        'ready_to_disburse': periods.filter(status='APPROVED', is_approved=True).count(),
    }
    
    # Completed periods
    completed_periods = periods.filter(status='COMPLETED')
    
    stats['completed'] = {
        'completed_periods': completed_periods.count(),
        'total_completed_amount': float(
            completed_periods.aggregate(total=Sum('total_dividend_amount'))['total'] or 0
        ),
        'total_completed_members': completed_periods.aggregate(
            total=Sum('total_members')
        )['total'] or 0,
    }
    
    # Recent activity
    now = timezone.now()
    stats['recent_activity'] = {
        'created_last_30_days': periods.filter(created_at__gte=now - timedelta(days=30)).count(),
        'created_last_90_days': periods.filter(created_at__gte=now - timedelta(days=90)).count(),
        'approved_last_30_days': periods.filter(approval_date__gte=now - timedelta(days=30)).count(),
        'completed_last_30_days': periods.filter(
            status='COMPLETED',
            updated_at__gte=now - timedelta(days=30)
        ).count(),
    }
    
    # Top periods by amount
    top_periods = periods.order_by('-total_dividend_amount')[:10]
    
    stats['top_periods_by_amount'] = [
        {
            'period_id': str(period.id),
            'name': period.name,
            'total_amount': float(period.total_dividend_amount),
            'dividend_rate': float(period.dividend_rate),
            'total_members': period.total_members,
            'status': period.status,
            'is_approved': period.is_approved,
        }
        for period in top_periods
    ]
    
    return stats


def get_dividend_period_performance(period_id=None):
    """
    Get detailed performance breakdown for dividend periods
    
    Args:
        period_id: Optional specific period ID
    
    Returns:
        dict: Dividend period performance breakdown
    """
    from .models import DividendPeriod, MemberDividend, DividendDisbursement
    
    if period_id:
        periods = DividendPeriod.objects.filter(id=period_id)
    else:
        periods = DividendPeriod.objects.filter(status__in=['APPROVED', 'DISBURSING', 'COMPLETED'])
    
    breakdown = []
    
    for period in periods:
        # Member dividend statistics
        member_dividends = MemberDividend.objects.filter(dividend_period=period)
        
        dividend_stats = member_dividends.aggregate(
            total_members=Count('id'),
            total_gross=Sum('gross_dividend'),
            total_tax=Sum('tax_amount'),
            total_net=Sum('net_dividend'),
            avg_gross=Avg('gross_dividend'),
            avg_net=Avg('net_dividend'),
            max_dividend=Max('net_dividend'),
            min_dividend=Min('net_dividend'),
            paid_count=Count('id', filter=Q(status='PAID')),
            pending_count=Count('id', filter=Q(status__in=['CALCULATED', 'APPROVED', 'PROCESSING'])),
            failed_count=Count('id', filter=Q(status='FAILED')),
        )
        
        # Disbursement statistics
        disbursements = DividendDisbursement.objects.filter(dividend_period=period)
        
        disbursement_stats = disbursements.aggregate(
            total_disbursements=Count('id'),
            completed_disbursements=Count('id', filter=Q(status='COMPLETED')),
            total_disbursed=Sum('processed_amount'),
            total_members_paid=Sum('successful_members'),
            total_failures=Sum('failed_members'),
        )
        
        # Payment method breakdown
        from .models import DividendPayment
        payments = DividendPayment.objects.filter(disbursement__dividend_period=period)
        
        payment_stats = payments.aggregate(
            total_payments=Count('id'),
            successful_payments=Count('id', filter=Q(status='COMPLETED')),
            failed_payments=Count('id', filter=Q(status='FAILED')),
            total_paid_amount=Sum('amount', filter=Q(status='COMPLETED')),
        )
        
        # Calculate rates
        total_members = dividend_stats['total_members'] or 0
        paid_count = dividend_stats['paid_count'] or 0
        
        breakdown.append({
            'period_id': str(period.id),
            'period_name': period.name,
            'status': period.status,
            'is_approved': period.is_approved,
            'dates': {
                'start_date': period.start_date.isoformat(),
                'end_date': period.end_date.isoformat(),
                'record_date': period.record_date.isoformat(),
                'payment_date': period.payment_date.isoformat() if period.payment_date else None,
            },
            'configuration': {
                'total_dividend_amount': float(period.total_dividend_amount),
                'dividend_rate': float(period.dividend_rate),
                'calculation_method': period.calculation_method,
                'withholding_tax_rate': float(period.withholding_tax_rate),
            },
            'member_dividends': {
                'total_members': total_members,
                'members_paid': paid_count,
                'members_pending': dividend_stats['pending_count'] or 0,
                'members_failed': dividend_stats['failed_count'] or 0,
                'payment_rate': round((paid_count / total_members * 100) if total_members > 0 else 0, 2),
                'total_gross_dividend': float(dividend_stats['total_gross'] or 0),
                'total_tax': float(dividend_stats['total_tax'] or 0),
                'total_net_dividend': float(dividend_stats['total_net'] or 0),
                'avg_gross_dividend': float(dividend_stats['avg_gross'] or 0),
                'avg_net_dividend': float(dividend_stats['avg_net'] or 0),
                'max_dividend': float(dividend_stats['max_dividend'] or 0),
                'min_dividend': float(dividend_stats['min_dividend'] or 0),
            },
            'disbursements': {
                'total_disbursements': disbursement_stats['total_disbursements'] or 0,
                'completed_disbursements': disbursement_stats['completed_disbursements'] or 0,
                'total_disbursed': float(disbursement_stats['total_disbursed'] or 0),
                'total_members_paid': disbursement_stats['total_members_paid'] or 0,
                'total_failures': disbursement_stats['total_failures'] or 0,
            },
            'payments': {
                'total_payments': payment_stats['total_payments'] or 0,
                'successful_payments': payment_stats['successful_payments'] or 0,
                'failed_payments': payment_stats['failed_payments'] or 0,
                'total_paid_amount': float(payment_stats['total_paid_amount'] or 0),
                'success_rate': round(
                    (payment_stats['successful_payments'] / payment_stats['total_payments'] * 100)
                    if payment_stats['total_payments'] > 0 else 0,
                    2
                ),
            },
        })
    
    return {
        'periods_analyzed': len(breakdown),
        'breakdown': breakdown,
    }


# =============================================================================
# MEMBER DIVIDEND STATISTICS
# =============================================================================

def get_member_dividend_statistics(filters=None):
    """
    Get comprehensive member dividend statistics
    
    Args:
        filters (dict): Optional filters
            - status: Filter by dividend status
            - period_id: Filter by specific period
            - member_id: Filter by specific member
            - date_from: Filter from payment date
            - date_to: Filter to payment date
    
    Returns:
        dict: Member dividend statistics
    """
    from .models import MemberDividend
    
    dividends = MemberDividend.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('status'):
            dividends = dividends.filter(status=filters['status'])
        if filters.get('period_id'):
            dividends = dividends.filter(dividend_period_id=filters['period_id'])
        if filters.get('member_id'):
            dividends = dividends.filter(member_id=filters['member_id'])
        if filters.get('date_from'):
            dividends = dividends.filter(payment_date__gte=filters['date_from'])
        if filters.get('date_to'):
            dividends = dividends.filter(payment_date__lte=filters['date_to'])
    
    total_dividends = dividends.count()
    
    stats = {
        'total_dividends': total_dividends,
    }
    
    # Status breakdown
    status_breakdown = dividends.values('status').annotate(
        count=Count('id'),
        total_gross=Sum('gross_dividend'),
        total_net=Sum('net_dividend'),
        total_tax=Sum('tax_amount'),
    ).order_by('-count')
    
    stats['by_status'] = [
        {
            'status': item['status'],
            'count': item['count'],
            'total_gross': float(item['total_gross'] or 0),
            'total_net': float(item['total_net'] or 0),
            'total_tax': float(item['total_tax'] or 0),
            'percentage': round((item['count'] / total_dividends * 100) if total_dividends > 0 else 0, 2),
        }
        for item in status_breakdown
    ]
    
    # Amount statistics
    amount_stats = dividends.aggregate(
        total_gross=Sum('gross_dividend'),
        total_tax=Sum('tax_amount'),
        total_net=Sum('net_dividend'),
        avg_gross=Avg('gross_dividend'),
        avg_net=Avg('net_dividend'),
        max_dividend=Max('net_dividend'),
        min_dividend=Min('net_dividend'),
        total_shares_value=Sum('shares_value'),
    )
    
    stats['amounts'] = {
        'total_gross_dividend': float(amount_stats['total_gross'] or 0),
        'total_tax': float(amount_stats['total_tax'] or 0),
        'total_net_dividend': float(amount_stats['total_net'] or 0),
        'avg_gross_dividend': float(amount_stats['avg_gross'] or 0),
        'avg_net_dividend': float(amount_stats['avg_net'] or 0),
        'highest_dividend': float(amount_stats['max_dividend'] or 0),
        'lowest_dividend': float(amount_stats['min_dividend'] or 0),
        'total_shares_value': float(amount_stats['total_shares_value'] or 0),
    }
    
    # Share statistics
    share_stats = dividends.aggregate(
        total_shares=Sum('shares_count'),
        avg_shares=Avg('shares_count'),
        max_shares=Max('shares_count'),
        min_shares=Min('shares_count'),
    )
    
    stats['shares'] = {
        'total_shares': share_stats['total_shares'] or 0,
        'avg_shares_per_member': round(float(share_stats['avg_shares'] or 0), 2),
        'max_shares': share_stats['max_shares'] or 0,
        'min_shares': share_stats['min_shares'] or 0,
    }
    
    # Payment status
    paid_dividends = dividends.filter(status='PAID')
    pending_dividends = dividends.filter(status__in=['CALCULATED', 'APPROVED', 'PROCESSING'])
    failed_dividends = dividends.filter(status='FAILED')
    
    stats['payment_status'] = {
        'paid': paid_dividends.count(),
        'pending': pending_dividends.count(),
        'failed': failed_dividends.count(),
        'payment_rate': round(
            (paid_dividends.count() / total_dividends * 100) if total_dividends > 0 else 0,
            2
        ),
        'total_paid_amount': float(paid_dividends.aggregate(total=Sum('net_dividend'))['total'] or 0),
        'total_pending_amount': float(pending_dividends.aggregate(total=Sum('net_dividend'))['total'] or 0),
    }
    
    # Disbursement method breakdown
    method_breakdown = dividends.exclude(
        disbursement_method__isnull=True
    ).values('disbursement_method').annotate(
        count=Count('id'),
        total_amount=Sum('net_dividend'),
    ).order_by('-count')
    
    stats['by_disbursement_method'] = [
        {
            'method': item['disbursement_method'],
            'count': item['count'],
            'total_amount': float(item['total_amount'] or 0),
            'percentage': round((item['count'] / total_dividends * 100) if total_dividends > 0 else 0, 2),
        }
        for item in method_breakdown
    ]
    
    # Rate analysis
    rate_stats = dividends.aggregate(
        avg_rate=Avg('applied_rate'),
        max_rate=Max('applied_rate'),
        min_rate=Min('applied_rate'),
    )
    
    stats['rates'] = {
        'avg_applied_rate': float(rate_stats['avg_rate'] or 0),
        'max_applied_rate': float(rate_stats['max_rate'] or 0),
        'min_applied_rate': float(rate_stats['min_rate'] or 0),
    }
    
    # Dividend distribution ranges
    distribution_ranges = {
        'under_10k': dividends.filter(net_dividend__lt=10000).count(),
        '10k_50k': dividends.filter(net_dividend__gte=10000, net_dividend__lt=50000).count(),
        '50k_100k': dividends.filter(net_dividend__gte=50000, net_dividend__lt=100000).count(),
        '100k_500k': dividends.filter(net_dividend__gte=100000, net_dividend__lt=500000).count(),
        '500k_1m': dividends.filter(net_dividend__gte=500000, net_dividend__lt=1000000).count(),
        'above_1m': dividends.filter(net_dividend__gte=1000000).count(),
    }
    
    stats['distribution_ranges'] = distribution_ranges
    
    # Recent payments
    today = timezone.now().date()
    stats['recent_payments'] = {
        'paid_today': paid_dividends.filter(payment_date__date=today).count(),
        'paid_last_7_days': paid_dividends.filter(
            payment_date__gte=timezone.now() - timedelta(days=7)
        ).count(),
        'paid_last_30_days': paid_dividends.filter(
            payment_date__gte=timezone.now() - timedelta(days=30)
        ).count(),
    }
    
    # Failed payment analysis
    if failed_dividends.exists():
        retry_stats = failed_dividends.aggregate(
            avg_retries=Avg('retry_count'),
            max_retries=Max('retry_count'),
        )
        
        stats['failures'] = {
            'total_failed': failed_dividends.count(),
            'avg_retry_count': round(float(retry_stats['avg_retries'] or 0), 2),
            'max_retry_count': retry_stats['max_retries'] or 0,
            'failed_amount': float(failed_dividends.aggregate(total=Sum('net_dividend'))['total'] or 0),
        }
    
    # Top dividends by amount
    top_dividends = dividends.select_related('member', 'dividend_period').order_by('-net_dividend')[:10]
    
    stats['top_dividends_by_amount'] = [
        {
            'member_name': dividend.member.get_full_name(),
            'period_name': dividend.dividend_period.name,
            'shares_count': dividend.shares_count,
            'gross_dividend': float(dividend.gross_dividend),
            'net_dividend': float(dividend.net_dividend),
            'status': dividend.status,
        }
        for dividend in top_dividends
    ]
    
    # Unique members
    stats['unique_members'] = dividends.values('member').distinct().count()
    stats['unique_periods'] = dividends.values('dividend_period').distinct().count()
    
    return stats


# =============================================================================
# DISBURSEMENT STATISTICS
# =============================================================================

def get_disbursement_statistics(filters=None):
    """
    Get disbursement statistics
    
    Args:
        filters (dict): Optional filters
            - status: Filter by status
            - period_id: Filter by dividend period
            - date_from: Filter from disbursement date
            - date_to: Filter to disbursement date
            - disbursement_method: Filter by method
    
    Returns:
        dict: Disbursement statistics
    """
    from .models import DividendDisbursement
    
    disbursements = DividendDisbursement.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('status'):
            disbursements = disbursements.filter(status=filters['status'])
        if filters.get('period_id'):
            disbursements = disbursements.filter(dividend_period_id=filters['period_id'])
        if filters.get('date_from'):
            disbursements = disbursements.filter(disbursement_date__gte=filters['date_from'])
        if filters.get('date_to'):
            disbursements = disbursements.filter(disbursement_date__lte=filters['date_to'])
        if filters.get('disbursement_method'):
            disbursements = disbursements.filter(disbursement_method=filters['disbursement_method'])
    
    total_disbursements = disbursements.count()
    
    stats = {
        'total_disbursements': total_disbursements,
    }
    
    # Status breakdown
    status_breakdown = disbursements.values('status').annotate(
        count=Count('id'),
        total_amount=Sum('total_amount'),
        processed_amount=Sum('processed_amount'),
        total_members=Sum('total_members'),
    ).order_by('-count')
    
    stats['by_status'] = [
        {
            'status': item['status'],
            'count': item['count'],
            'total_amount': float(item['total_amount'] or 0),
            'processed_amount': float(item['processed_amount'] or 0),
            'total_members': item['total_members'] or 0,
            'percentage': round((item['count'] / total_disbursements * 100) if total_disbursements > 0 else 0, 2),
        }
        for item in status_breakdown
    ]
    
    # Amount statistics
    amount_stats = disbursements.aggregate(
        total_amount=Sum('total_amount'),
        total_processed=Sum('processed_amount'),
        avg_amount=Avg('total_amount'),
        max_amount=Max('total_amount'),
    )
    
    stats['amounts'] = {
        'total_amount': float(amount_stats['total_amount'] or 0),
        'total_processed': float(amount_stats['total_processed'] or 0),
        'avg_per_disbursement': float(amount_stats['avg_amount'] or 0),
        'max_disbursement': float(amount_stats['max_amount'] or 0),
    }
    
    # Member statistics
    member_stats = disbursements.aggregate(
        total_members=Sum('total_members'),
        total_processed=Sum('processed_members'),
        total_successful=Sum('successful_members'),
        total_failed=Sum('failed_members'),
    )
    
    stats['members'] = {
        'total_members': member_stats['total_members'] or 0,
        'processed_members': member_stats['total_processed'] or 0,
        'successful_members': member_stats['total_successful'] or 0,
        'failed_members': member_stats['total_failed'] or 0,
        'success_rate': round(
            (member_stats['total_successful'] / member_stats['total_processed'] * 100)
            if member_stats['total_processed'] > 0 else 0,
            2
        ),
    }
    
    # Method breakdown
    method_breakdown = disbursements.values('disbursement_method').annotate(
        count=Count('id'),
        total_amount=Sum('total_amount'),
        successful_members=Sum('successful_members'),
    ).order_by('-count')
    
    stats['by_method'] = [
        {
            'method': item['disbursement_method'],
            'count': item['count'],
            'total_amount': float(item['total_amount'] or 0),
            'successful_members': item['successful_members'] or 0,
        }
        for item in method_breakdown
    ]
    
    # Completion statistics
    completed = disbursements.filter(status='COMPLETED')
    
    if completed.exists():
        # Calculate average processing time
        completed_with_times = completed.exclude(
            Q(start_time__isnull=True) | Q(end_time__isnull=True)
        )
        
        if completed_with_times.exists():
            total_duration = sum(
                [(d.end_time - d.start_time).total_seconds() for d in completed_with_times],
                0
            )
            avg_duration_seconds = total_duration / completed_with_times.count()
            
            stats['completion'] = {
                'completed_count': completed.count(),
                'avg_processing_time_minutes': round(avg_duration_seconds / 60, 2),
                'total_completed_amount': float(completed.aggregate(total=Sum('processed_amount'))['total'] or 0),
            }
    
    # Recent activity
    today = timezone.now().date()
    stats['recent_activity'] = {
        'disbursed_today': disbursements.filter(disbursement_date=today).count(),
        'disbursed_last_7_days': disbursements.filter(
            disbursement_date__gte=today - timedelta(days=7)
        ).count(),
        'disbursed_last_30_days': disbursements.filter(
            disbursement_date__gte=today - timedelta(days=30)
        ).count(),
        'completed_last_7_days': completed.filter(
            end_time__gte=timezone.now() - timedelta(days=7)
        ).count(),
    }
    
    return stats


# =============================================================================
# PAYMENT STATISTICS
# =============================================================================

def get_payment_statistics(filters=None):
    """
    Get payment statistics
    
    Args:
        filters (dict): Optional filters
            - status: Filter by status
            - disbursement_id: Filter by disbursement
            - date_from: Filter from payment date
            - date_to: Filter to payment date
    
    Returns:
        dict: Payment statistics
    """
    from .models import DividendPayment
    
    payments = DividendPayment.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('status'):
            payments = payments.filter(status=filters['status'])
        if filters.get('disbursement_id'):
            payments = payments.filter(disbursement_id=filters['disbursement_id'])
        if filters.get('date_from'):
            payments = payments.filter(payment_date__gte=filters['date_from'])
        if filters.get('date_to'):
            payments = payments.filter(payment_date__lte=filters['date_to'])
    
    total_payments = payments.count()
    
    stats = {
        'total_payments': total_payments,
    }
    
    # Status breakdown
    status_breakdown = payments.values('status').annotate(
        count=Count('id'),
        total_amount=Sum('amount'),
    ).order_by('-count')
    
    stats['by_status'] = [
        {
            'status': item['status'],
            'count': item['count'],
            'total_amount': float(item['total_amount'] or 0),
            'percentage': round((item['count'] / total_payments * 100) if total_payments > 0 else 0, 2),
        }
        for item in status_breakdown
    ]
    
    # Amount statistics
    amount_stats = payments.aggregate(
        total_amount=Sum('amount'),
        avg_amount=Avg('amount'),
        max_amount=Max('amount'),
        min_amount=Min('amount'),
    )
    
    stats['amounts'] = {
        'total_amount': float(amount_stats['total_amount'] or 0),
        'avg_payment': float(amount_stats['avg_amount'] or 0),
        'max_payment': float(amount_stats['max_amount'] or 0),
        'min_payment': float(amount_stats['min_amount'] or 0),
    }
    
    # Success statistics
    successful = payments.filter(status='COMPLETED')
    failed = payments.filter(status='FAILED')
    
    stats['success'] = {
        'successful_payments': successful.count(),
        'failed_payments': failed.count(),
        'success_rate': round(
            (successful.count() / total_payments * 100) if total_payments > 0 else 0,
            2
        ),
        'total_successful_amount': float(successful.aggregate(total=Sum('amount'))['total'] or 0),
    }
    
    # Retry analysis
    if failed.exists():
        retry_stats = failed.aggregate(
            avg_retries=Avg('retry_count'),
            max_retries=Max('retry_count'),
        )
        
        stats['retries'] = {
            'avg_retry_count': round(float(retry_stats['avg_retries'] or 0), 2),
            'max_retry_count': retry_stats['max_retries'] or 0,
            'payments_with_retries': failed.filter(retry_count__gt=0).count(),
        }
    
    # Recent activity
    today = timezone.now()
    stats['recent_activity'] = {
        'paid_today': payments.filter(payment_date__date=today.date()).count(),
        'paid_last_24_hours': payments.filter(payment_date__gte=today - timedelta(hours=24)).count(),
        'paid_last_7_days': payments.filter(payment_date__gte=today - timedelta(days=7)).count(),
    }
    
    return stats


# =============================================================================
# DIVIDEND PREFERENCE STATISTICS
# =============================================================================

def get_preference_statistics(filters=None):
    """
    Get dividend preference statistics
    
    Args:
        filters (dict): Optional filters
            - member_id: Filter by member
            - period_id: Filter by period
            - preference_method: Filter by method
    
    Returns:
        dict: Preference statistics
    """
    from .models import DividendPreference
    
    preferences = DividendPreference.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('member_id'):
            preferences = preferences.filter(member_id=filters['member_id'])
        if filters.get('period_id'):
            preferences = preferences.filter(dividend_period_id=filters['period_id'])
        if filters.get('preference_method'):
            preferences = preferences.filter(preference_method=filters['preference_method'])
    
    total_preferences = preferences.count()
    
    stats = {
        'total_preferences': total_preferences,
        'default_preferences': preferences.filter(is_default=True, dividend_period__isnull=True).count(),
        'period_specific': preferences.filter(dividend_period__isnull=False).count(),
    }
    
    # Method breakdown
    method_breakdown = preferences.values('preference_method').annotate(
        count=Count('id')
    ).order_by('-count')
    
    stats['by_method'] = [
        {
            'method': item['preference_method'],
            'count': item['count'],
            'percentage': round((item['count'] / total_preferences * 100) if total_preferences > 0 else 0, 2),
        }
        for item in method_breakdown
    ]
    
    # Account usage
    stats['accounts'] = {
        'using_savings_account': preferences.filter(
            preference_method='SAVINGS_ACCOUNT',
            savings_account__isnull=False
        ).count(),
        'using_bank_transfer': preferences.filter(preference_method='BANK_TRANSFER').count(),
        'using_mobile_money': preferences.filter(preference_method='MOBILE_MONEY').count(),
        'using_cash': preferences.filter(preference_method='CASH').count(),
    }
    
    # Unique counts
    stats['unique_members'] = preferences.values('member').distinct().count()
    stats['unique_periods'] = preferences.filter(
        dividend_period__isnull=False
    ).values('dividend_period').distinct().count()
    
    return stats


# =============================================================================
# COMPREHENSIVE DIVIDEND OVERVIEW
# =============================================================================

def get_dividend_overview(date_from=None, date_to=None):
    """
    Get comprehensive dividend overview
    
    Args:
        date_from: Optional start date
        date_to: Optional end date
    
    Returns:
        dict: Comprehensive dividend overview
    """
    from .models import DividendPeriod, MemberDividend, DividendDisbursement, DividendPayment
    
    # Set default date range
    if not date_to:
        date_to = timezone.now().date()
    if not date_from:
        date_from = date_to - timedelta(days=365)
    
    overview = {
        'report_period': {
            'from': date_from.isoformat(),
            'to': date_to.isoformat(),
        },
        'currency': get_base_currency(),
    }
    
    # Period summary
    periods = DividendPeriod.objects.filter(
        end_date__gte=date_from,
        end_date__lte=date_to
    )
    
    period_summary = periods.aggregate(
        total_periods=Count('id'),
        active_periods=Count('id', filter=Q(status__in=['OPEN', 'CALCULATING', 'CALCULATED', 'APPROVED', 'DISBURSING'])),
        completed_periods=Count('id', filter=Q(status='COMPLETED')),
        total_dividend_amount=Sum('total_dividend_amount'),
        total_members=Sum('total_members'),
    )
    
    overview['periods'] = {
        'total': period_summary['total_periods'] or 0,
        'active': period_summary['active_periods'] or 0,
        'completed': period_summary['completed_periods'] or 0,
        'total_amount': float(period_summary['total_dividend_amount'] or 0),
        'total_members': period_summary['total_members'] or 0,
    }
    
    # Member dividend summary
    dividends = MemberDividend.objects.filter(
        dividend_period__in=periods
    )
    
    dividend_summary = dividends.aggregate(
        total_dividends=Count('id'),
        paid=Count('id', filter=Q(status='PAID')),
        pending=Count('id', filter=Q(status__in=['CALCULATED', 'APPROVED', 'PROCESSING'])),
        total_gross=Sum('gross_dividend'),
        total_tax=Sum('tax_amount'),
        total_net=Sum('net_dividend'),
    )
    
    overview['dividends'] = {
        'total': dividend_summary['total_dividends'] or 0,
        'paid': dividend_summary['paid'] or 0,
        'pending': dividend_summary['pending'] or 0,
        'total_gross': float(dividend_summary['total_gross'] or 0),
        'total_tax': float(dividend_summary['total_tax'] or 0),
        'total_net': float(dividend_summary['total_net'] or 0),
        'payment_rate': round(
            (dividend_summary['paid'] / dividend_summary['total_dividends'] * 100)
            if dividend_summary['total_dividends'] > 0 else 0,
            2
        ),
    }
    
    # Disbursement summary
    disbursements = DividendDisbursement.objects.filter(
        dividend_period__in=periods
    )
    
    disbursement_summary = disbursements.aggregate(
        total_disbursements=Count('id'),
        completed=Count('id', filter=Q(status='COMPLETED')),
        total_amount=Sum('total_amount'),
        processed_amount=Sum('processed_amount'),
        successful_members=Sum('successful_members'),
    )
    
    overview['disbursements'] = {
        'total': disbursement_summary['total_disbursements'] or 0,
        'completed': disbursement_summary['completed'] or 0,
        'total_amount': float(disbursement_summary['total_amount'] or 0),
        'processed_amount': float(disbursement_summary['processed_amount'] or 0),
        'successful_members': disbursement_summary['successful_members'] or 0,
    }
    
    # Payment summary
    payments = DividendPayment.objects.filter(
        disbursement__in=disbursements
    )
    
    payment_summary = payments.aggregate(
        total_payments=Count('id'),
        successful=Count('id', filter=Q(status='COMPLETED')),
        failed=Count('id', filter=Q(status='FAILED')),
        total_paid=Sum('amount', filter=Q(status='COMPLETED')),
    )
    
    overview['payments'] = {
        'total': payment_summary['total_payments'] or 0,
        'successful': payment_summary['successful'] or 0,
        'failed': payment_summary['failed'] or 0,
        'total_paid': float(payment_summary['total_paid'] or 0),
        'success_rate': round(
            (payment_summary['successful'] / payment_summary['total_payments'] * 100)
            if payment_summary['total_payments'] > 0 else 0,
            2
        ),
    }
    
    return overview