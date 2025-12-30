# core/stats.py
"""
Comprehensive statistics utility functions for Core models
Provides detailed analytics for fiscal years, periods, payment methods, tax rates, 
units of measure, and SACCO configurations
"""

from django.utils import timezone
from django.db.models import (
    Count, Q, Avg, Sum, Max, Min, F, Case, When,
    IntegerField, FloatField, DecimalField, Value
)
from django.db.models.functions import TruncMonth, TruncYear, TruncWeek, TruncDate, TruncQuarter
from datetime import timedelta, date
from decimal import Decimal
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# FISCAL YEAR STATISTICS
# =============================================================================

def get_fiscal_year_statistics(filters=None):
    """
    Get comprehensive statistics for fiscal years
    
    Args:
        filters (dict): Optional filters
            - status: Filter by status (DRAFT, ACTIVE, CLOSED, LOCKED)
            - is_active: Filter by active status
            - year_range: Tuple of (start_year, end_year)
            - is_closed: Filter by closure status
            - is_locked: Filter by lock status
    
    Returns:
        dict: Fiscal year statistics
    """
    from .models import FiscalYear
    
    fiscal_years = FiscalYear.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('status'):
            fiscal_years = fiscal_years.filter(status=filters['status'])
        if filters.get('is_active') is not None:
            fiscal_years = fiscal_years.filter(is_active=filters['is_active'])
        if filters.get('is_closed') is not None:
            fiscal_years = fiscal_years.filter(is_closed=filters['is_closed'])
        if filters.get('is_locked') is not None:
            fiscal_years = fiscal_years.filter(is_locked=filters['is_locked'])
        if filters.get('year_range'):
            start_year, end_year = filters['year_range']
            fiscal_years = fiscal_years.filter(
                start_date__year__gte=start_year,
                start_date__year__lte=end_year
            )
    
    total_fiscal_years = fiscal_years.count()
    
    stats = {
        'total_fiscal_years': total_fiscal_years,
        
        # Status breakdown
        'by_status': {
            'draft': fiscal_years.filter(status='DRAFT').count(),
            'active': fiscal_years.filter(status='ACTIVE').count(),
            'closed': fiscal_years.filter(status='CLOSED').count(),
            'locked': fiscal_years.filter(status='LOCKED').count(),
        },
        
        # Active status
        'active_fiscal_years': fiscal_years.filter(is_active=True).count(),
        'inactive_fiscal_years': fiscal_years.filter(is_active=False).count(),
        
        # Closure status
        'closed_fiscal_years': fiscal_years.filter(is_closed=True).count(),
        'open_fiscal_years': fiscal_years.filter(is_closed=False).count(),
        
        # Lock status
        'locked_fiscal_years': fiscal_years.filter(is_locked=True).count(),
        'unlocked_fiscal_years': fiscal_years.filter(is_locked=False).count(),
        
        # Current fiscal year
        'current_fiscal_year': None,
        
        # Time-based categorization
        'time_categories': {
            'current': 0,
            'upcoming': 0,
            'past': 0,
        },
        
        # Duration analysis
        'duration_analysis': {},
        
        # Period statistics
        'period_statistics': {},
    }
    
    # Get current fiscal year
    current_fy = FiscalYear.get_active_fiscal_year()
    if current_fy:
        stats['current_fiscal_year'] = {
            'id': str(current_fy.id),
            'name': current_fy.name,
            'code': current_fy.code,
            'start_date': current_fy.start_date.strftime('%Y-%m-%d'),
            'end_date': current_fy.end_date.strftime('%Y-%m-%d'),
            'status': current_fy.status,
            'duration_days': current_fy.get_duration_days(),
            'duration_weeks': current_fy.get_duration_weeks(),
            'elapsed_days': current_fy.get_elapsed_days(),
            'remaining_days': current_fy.get_remaining_days(),
            'progress_percentage': current_fy.get_progress_percentage(),
            'period_count': current_fy.get_period_count(),
        }
    
    # Time-based categorization
    for fy in fiscal_years:
        if fy.is_current():
            stats['time_categories']['current'] += 1
        elif fy.is_upcoming():
            stats['time_categories']['upcoming'] += 1
        elif fy.is_past():
            stats['time_categories']['past'] += 1
    
    # Duration analysis
    if total_fiscal_years > 0:
        durations = [fy.get_duration_days() for fy in fiscal_years]
        stats['duration_analysis'] = {
            'average_duration_days': sum(durations) / len(durations),
            'min_duration_days': min(durations),
            'max_duration_days': max(durations),
            'total_days': sum(durations),
        }
    
    # Period statistics across all fiscal years
    total_periods = sum(fy.get_period_count() for fy in fiscal_years)
    active_periods = sum(fy.periods.filter(is_active=True).count() for fy in fiscal_years)
    closed_periods = sum(fy.periods.filter(is_closed=True).count() for fy in fiscal_years)
    
    stats['period_statistics'] = {
        'total_periods': total_periods,
        'active_periods': active_periods,
        'closed_periods': closed_periods,
        'average_periods_per_year': total_periods / total_fiscal_years if total_fiscal_years > 0 else 0,
    }
    
    # Recent activity
    current_date = timezone.now()
    stats['recent_activity'] = {
        'created_last_7_days': fiscal_years.filter(
            created_at__gte=current_date - timedelta(days=7)
        ).count(),
        'created_last_30_days': fiscal_years.filter(
            created_at__gte=current_date - timedelta(days=30)
        ).count(),
        'created_last_90_days': fiscal_years.filter(
            created_at__gte=current_date - timedelta(days=90)
        ).count(),
        'closed_last_30_days': fiscal_years.filter(
            closed_at__gte=current_date - timedelta(days=30)
        ).count() if fiscal_years.filter(closed_at__isnull=False).exists() else 0,
    }
    
    # Yearly trend (if we have fiscal years)
    if total_fiscal_years > 0:
        yearly_data = fiscal_years.extra(
            select={'year': "EXTRACT(year FROM start_date)"}
        ).values('year').annotate(
            count=Count('id')
        ).order_by('year')
        
        stats['yearly_trend'] = {
            int(item['year']): item['count'] 
            for item in yearly_data
        }
    
    return stats


def get_fiscal_year_timeline(fiscal_year_id=None):
    """
    Get timeline data for fiscal year(s)
    
    Args:
        fiscal_year_id: Specific fiscal year ID or None for all
    
    Returns:
        list: Timeline data for fiscal years
    """
    from .models import FiscalYear
    
    fiscal_years = FiscalYear.objects.all().order_by('start_date')
    
    if fiscal_year_id:
        fiscal_years = fiscal_years.filter(id=fiscal_year_id)
    
    timeline = []
    for fy in fiscal_years:
        timeline.append({
            'id': str(fy.id),
            'name': fy.name,
            'code': fy.code,
            'start_date': fy.start_date.strftime('%Y-%m-%d'),
            'end_date': fy.end_date.strftime('%Y-%m-%d'),
            'duration_days': fy.get_duration_days(),
            'duration_weeks': fy.get_duration_weeks(),
            'status': fy.status,
            'status_display': fy.get_status_display(),
            'is_active': fy.is_active,
            'is_closed': fy.is_closed,
            'is_locked': fy.is_locked,
            'is_current': fy.is_current(),
            'is_upcoming': fy.is_upcoming(),
            'is_past': fy.is_past(),
            'period_count': fy.get_period_count(),
            'progress_percentage': fy.get_progress_percentage(),
            'elapsed_days': fy.get_elapsed_days(),
            'remaining_days': fy.get_remaining_days(),
        })
    
    return timeline


def get_fiscal_year_detail_stats(fiscal_year_id):
    """
    Get detailed statistics for a specific fiscal year
    
    Args:
        fiscal_year_id: Fiscal year ID
    
    Returns:
        dict: Detailed fiscal year statistics
    """
    from .models import FiscalYear
    
    try:
        fiscal_year = FiscalYear.objects.get(id=fiscal_year_id)
    except FiscalYear.DoesNotExist:
        return None
    
    periods = fiscal_year.periods.all()
    
    stats = {
        'fiscal_year': {
            'id': str(fiscal_year.id),
            'name': fiscal_year.name,
            'code': fiscal_year.code,
            'start_date': fiscal_year.start_date.strftime('%Y-%m-%d'),
            'end_date': fiscal_year.end_date.strftime('%Y-%m-%d'),
            'status': fiscal_year.status,
            'is_active': fiscal_year.is_active,
            'is_closed': fiscal_year.is_closed,
            'is_locked': fiscal_year.is_locked,
        },
        
        # Time metrics
        'time_metrics': {
            'duration_days': fiscal_year.get_duration_days(),
            'duration_weeks': fiscal_year.get_duration_weeks(),
            'elapsed_days': fiscal_year.get_elapsed_days(),
            'remaining_days': fiscal_year.get_remaining_days(),
            'progress_percentage': fiscal_year.get_progress_percentage(),
            'is_current': fiscal_year.is_current(),
            'is_upcoming': fiscal_year.is_upcoming(),
            'is_past': fiscal_year.is_past(),
        },
        
        # Period statistics
        'periods': {
            'total': periods.count(),
            'active': periods.filter(is_active=True).count(),
            'closed': periods.filter(is_closed=True).count(),
            'locked': periods.filter(is_locked=True).count(),
            'by_status': {
                'draft': periods.filter(status='DRAFT').count(),
                'active': periods.filter(status='ACTIVE').count(),
                'closed': periods.filter(status='CLOSED').count(),
                'locked': periods.filter(status='LOCKED').count(),
            },
        },
        
        # Closure information
        'closure_info': {
            'is_closed': fiscal_year.is_closed,
            'closed_at': fiscal_year.closed_at.strftime('%Y-%m-%d %H:%M:%S') if fiscal_year.closed_at else None,
            'closed_by': fiscal_year.closed_by_name if fiscal_year.is_closed else None,
        },
    }
    
    return stats


# =============================================================================
# FISCAL PERIOD STATISTICS
# =============================================================================

def get_period_statistics(filters=None):
    """
    Get comprehensive statistics for fiscal periods
    
    Args:
        filters (dict): Optional filters
            - fiscal_year: Filter by fiscal year ID
            - status: Filter by status
            - is_active: Filter by active status
            - is_closed: Filter by closure status
            - is_locked: Filter by lock status
            - period_number: Filter by specific period number
    
    Returns:
        dict: Period statistics
    """
    from .models import FiscalPeriod
    
    periods = FiscalPeriod.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('fiscal_year'):
            periods = periods.filter(fiscal_year_id=filters['fiscal_year'])
        if filters.get('status'):
            periods = periods.filter(status=filters['status'])
        if filters.get('is_active') is not None:
            periods = periods.filter(is_active=filters['is_active'])
        if filters.get('is_closed') is not None:
            periods = periods.filter(is_closed=filters['is_closed'])
        if filters.get('is_locked') is not None:
            periods = periods.filter(is_locked=filters['is_locked'])
        if filters.get('period_number'):
            periods = periods.filter(period_number=filters['period_number'])
    
    total_periods = periods.count()
    
    stats = {
        'total_periods': total_periods,
        
        # Status breakdown
        'by_status': {
            'draft': periods.filter(status='DRAFT').count(),
            'active': periods.filter(status='ACTIVE').count(),
            'closed': periods.filter(status='CLOSED').count(),
            'locked': periods.filter(status='LOCKED').count(),
        },
        
        # Active status
        'active_periods': periods.filter(is_active=True).count(),
        'inactive_periods': periods.filter(is_active=False).count(),
        
        # Closure status
        'closed_periods': periods.filter(is_closed=True).count(),
        'open_periods': periods.filter(is_closed=False).count(),
        
        # Lock status
        'locked_periods': periods.filter(is_locked=True).count(),
        'unlocked_periods': periods.filter(is_locked=False).count(),
        
        # Current period
        'current_period': None,
        
        # Time-based categorization
        'time_categories': {
            'current': 0,
            'upcoming': 0,
            'past': 0,
        },
        
        # By fiscal year
        'by_fiscal_year': {},
        
        # Duration analysis
        'duration_analysis': {},
        
        # Period distribution
        'period_distribution': {},
    }
    
    # Get current period
    current_period = FiscalPeriod.get_active_period()
    if current_period:
        stats['current_period'] = {
            'id': str(current_period.id),
            'name': current_period.name,
            'period_number': current_period.period_number,
            'fiscal_year_id': str(current_period.fiscal_year.id),
            'fiscal_year_name': current_period.fiscal_year.name,
            'start_date': current_period.start_date.strftime('%Y-%m-%d'),
            'end_date': current_period.end_date.strftime('%Y-%m-%d'),
            'status': current_period.status,
            'duration_days': current_period.get_duration_days(),
            'elapsed_days': current_period.get_elapsed_days(),
            'remaining_days': current_period.get_remaining_days(),
            'progress_percentage': current_period.get_progress_percentage(),
        }
    
    # Time-based categorization
    for period in periods:
        if period.is_current():
            stats['time_categories']['current'] += 1
        elif period.is_upcoming():
            stats['time_categories']['upcoming'] += 1
        elif period.is_past():
            stats['time_categories']['past'] += 1
    
    # Breakdown by fiscal year
    fy_data = periods.values(
        'fiscal_year__name',
        'fiscal_year__id'
    ).annotate(
        count=Count('id'),
        active_count=Count(Case(When(is_active=True, then=1))),
        closed_count=Count(Case(When(is_closed=True, then=1))),
        locked_count=Count(Case(When(is_locked=True, then=1)))
    ).order_by('fiscal_year__start_date')
    
    for item in fy_data:
        fy_name = item['fiscal_year__name']
        stats['by_fiscal_year'][fy_name] = {
            'fiscal_year_id': str(item['fiscal_year__id']),
            'total_periods': item['count'],
            'active_periods': item['active_count'],
            'closed_periods': item['closed_count'],
            'locked_periods': item['locked_count'],
        }
    
    # Duration analysis
    if total_periods > 0:
        durations = [p.get_duration_days() for p in periods]
        stats['duration_analysis'] = {
            'average_duration_days': sum(durations) / len(durations),
            'min_duration_days': min(durations),
            'max_duration_days': max(durations),
            'total_days': sum(durations),
        }
    
    # Period numbering distribution
    period_numbers = periods.values('period_number').annotate(
        count=Count('id'),
        active_count=Count(Case(When(is_active=True, then=1))),
        closed_count=Count(Case(When(is_closed=True, then=1)))
    ).order_by('period_number')
    
    stats['period_distribution'] = {
        item['period_number']: {
            'total': item['count'],
            'active': item['active_count'],
            'closed': item['closed_count'],
        }
        for item in period_numbers
    }
    
    # Recent activity
    current_date = timezone.now()
    stats['recent_activity'] = {
        'created_last_7_days': periods.filter(
            created_at__gte=current_date - timedelta(days=7)
        ).count(),
        'created_last_30_days': periods.filter(
            created_at__gte=current_date - timedelta(days=30)
        ).count(),
        'closed_last_30_days': periods.filter(
            closed_at__gte=current_date - timedelta(days=30)
        ).count() if periods.filter(closed_at__isnull=False).exists() else 0,
    }
    
    return stats


def get_period_detail_stats(period_id):
    """
    Get detailed statistics for a specific period
    
    Args:
        period_id: Period ID
    
    Returns:
        dict: Detailed period statistics
    """
    from .models import FiscalPeriod
    
    try:
        period = FiscalPeriod.objects.select_related('fiscal_year').get(id=period_id)
    except FiscalPeriod.DoesNotExist:
        return None
    
    stats = {
        'period': {
            'id': str(period.id),
            'name': period.name,
            'period_number': period.period_number,
            'start_date': period.start_date.strftime('%Y-%m-%d'),
            'end_date': period.end_date.strftime('%Y-%m-%d'),
            'status': period.status,
            'is_active': period.is_active,
            'is_closed': period.is_closed,
            'is_locked': period.is_locked,
        },
        
        'fiscal_year': {
            'id': str(period.fiscal_year.id),
            'name': period.fiscal_year.name,
            'code': period.fiscal_year.code,
        },
        
        # Time metrics
        'time_metrics': {
            'duration_days': period.get_duration_days(),
            'duration_weeks': period.get_duration_weeks(),
            'elapsed_days': period.get_elapsed_days(),
            'remaining_days': period.get_remaining_days(),
            'progress_percentage': period.get_progress_percentage(),
            'is_current': period.is_current(),
            'is_upcoming': period.is_upcoming(),
            'is_past': period.is_past(),
            'is_last_period': period.is_last_period(),
        },
        
        # Navigation
        'navigation': {
            'has_next': period.get_next_period() is not None,
            'has_previous': period.get_previous_period() is not None,
            'next_period_id': str(period.get_next_period().id) if period.get_next_period() else None,
            'previous_period_id': str(period.get_previous_period().id) if period.get_previous_period() else None,
        },
        
        # Closure information
        'closure_info': {
            'is_closed': period.is_closed,
            'closed_at': period.closed_at.strftime('%Y-%m-%d %H:%M:%S') if period.closed_at else None,
            'closed_by': period.closed_by_name if period.is_closed else None,
            'can_be_deleted': period.can_be_deleted(),
        },
    }
    
    return stats


# =============================================================================
# PAYMENT METHOD STATISTICS
# =============================================================================

def get_payment_method_statistics(filters=None):
    """
    Get comprehensive statistics for payment methods
    
    Args:
        filters (dict): Optional filters
            - method_type: Filter by payment method type
            - is_active: Filter by active status
            - has_transaction_fee: Filter by fee status
            - mobile_money_provider: Filter by mobile money provider
    
    Returns:
        dict: Payment method statistics
    """
    from .models import PaymentMethod
    
    payment_methods = PaymentMethod.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('method_type'):
            payment_methods = payment_methods.filter(method_type=filters['method_type'])
        if filters.get('is_active') is not None:
            payment_methods = payment_methods.filter(is_active=filters['is_active'])
        if filters.get('has_transaction_fee') is not None:
            payment_methods = payment_methods.filter(has_transaction_fee=filters['has_transaction_fee'])
        if filters.get('mobile_money_provider'):
            payment_methods = payment_methods.filter(mobile_money_provider=filters['mobile_money_provider'])
    
    total_payment_methods = payment_methods.count()
    
    stats = {
        'total_payment_methods': total_payment_methods,
        
        # Status
        'active_payment_methods': payment_methods.filter(is_active=True).count(),
        'inactive_payment_methods': payment_methods.filter(is_active=False).count(),
        
        # Default method
        'has_default_method': payment_methods.filter(is_default=True).exists(),
        'default_method': None,
        
        # By method type
        'by_method_type': {},
        
        # Fee configuration
        'fee_statistics': {
            'with_fees': payment_methods.filter(has_transaction_fee=True).count(),
            'without_fees': payment_methods.filter(has_transaction_fee=False).count(),
            'by_fee_type': {},
        },
        
        # Mobile money statistics
        'mobile_money': {
            'total': payment_methods.filter(method_type='MOBILE_MONEY').count(),
            'active': payment_methods.filter(method_type='MOBILE_MONEY', is_active=True).count(),
            'by_provider': {},
        },
        
        # API integration
        'api_integration': {
            'api_enabled': payment_methods.filter(api_enabled=True).count(),
            'api_disabled': payment_methods.filter(api_enabled=False).count(),
        },
        
        # Approval requirements
        'approval_requirements': {
            'requires_approval': payment_methods.filter(requires_approval=True).count(),
            'no_approval_required': payment_methods.filter(requires_approval=False).count(),
        },
    }
    
    # Get default payment method
    default_method = PaymentMethod.get_default_method()
    if default_method:
        stats['default_method'] = {
            'id': str(default_method.id),
            'name': default_method.name,
            'code': default_method.code,
            'method_type': default_method.method_type,
        }
    
    # Breakdown by method type
    method_type_data = payment_methods.values('method_type').annotate(
        count=Count('id'),
        active_count=Count(Case(When(is_active=True, then=1)))
    ).order_by('method_type')
    
    for item in method_type_data:
        method_type = item['method_type']
        stats['by_method_type'][method_type] = {
            'total': item['count'],
            'active': item['active_count'],
        }
    
    # Fee type breakdown
    fee_type_data = payment_methods.filter(
        has_transaction_fee=True
    ).values('transaction_fee_type').annotate(
        count=Count('id')
    )
    
    for item in fee_type_data:
        if item['transaction_fee_type']:
            stats['fee_statistics']['by_fee_type'][item['transaction_fee_type']] = item['count']
    
    # Mobile money provider breakdown
    mm_provider_data = payment_methods.filter(
        method_type='MOBILE_MONEY'
    ).values('mobile_money_provider').annotate(
        count=Count('id'),
        active_count=Count(Case(When(is_active=True, then=1)))
    )
    
    for item in mm_provider_data:
        if item['mobile_money_provider']:
            provider = item['mobile_money_provider']
            stats['mobile_money']['by_provider'][provider] = {
                'total': item['count'],
                'active': item['active_count'],
            }
    
    # Recent activity
    current_date = timezone.now()
    stats['recent_activity'] = {
        'created_last_30_days': payment_methods.filter(
            created_at__gte=current_date - timedelta(days=30)
        ).count(),
        'updated_last_30_days': payment_methods.filter(
            updated_at__gte=current_date - timedelta(days=30)
        ).count(),
    }
    
    return stats


def get_payment_method_detail_stats(payment_method_id):
    """
    Get detailed statistics for a specific payment method
    
    Args:
        payment_method_id: Payment method ID
    
    Returns:
        dict: Detailed payment method statistics
    """
    from .models import PaymentMethod
    
    try:
        pm = PaymentMethod.objects.get(id=payment_method_id)
    except PaymentMethod.DoesNotExist:
        return None
    
    stats = {
        'payment_method': {
            'id': str(pm.id),
            'name': pm.name,
            'code': pm.code,
            'method_type': pm.method_type,
            'is_active': pm.is_active,
            'is_default': pm.is_default,
        },
        
        # Configuration
        'configuration': {
            'requires_approval': pm.requires_approval,
            'requires_reference': pm.requires_reference,
            'processing_time': pm.processing_time,
        },
        
        # Limits
        'transaction_limits': {
            'minimum_amount': float(pm.minimum_amount) if pm.minimum_amount else None,
            'maximum_amount': float(pm.maximum_amount) if pm.maximum_amount else None,
            'daily_limit': float(pm.daily_limit) if pm.daily_limit else None,
        },
        
        # Fee information
        'fee_info': {
            'has_transaction_fee': pm.has_transaction_fee,
            'transaction_fee_type': pm.transaction_fee_type,
            'transaction_fee_amount': float(pm.transaction_fee_amount) if pm.transaction_fee_amount else None,
            'fee_bearer': pm.fee_bearer,
            'fee_display': pm.get_fee_display(),
        },
        
        # API integration
        'api_integration': {
            'api_enabled': pm.api_enabled,
            'api_endpoint': pm.api_endpoint,
        },
        
        # Availability
        'availability': {
            'can_process_transaction': pm.can_process_transaction(),
        },
    }
    
    # Method-specific information
    if pm.method_type == 'MOBILE_MONEY':
        stats['mobile_money_info'] = {
            'provider': pm.mobile_money_provider,
            'provider_display': pm.get_mobile_money_provider_display() if pm.mobile_money_provider else None,
        }
    elif pm.method_type == 'BANK_TRANSFER':
        stats['bank_info'] = {
            'bank_name': pm.bank_name,
            'account_number': pm.bank_account_number,
            'branch': pm.bank_branch,
            'swift_code': pm.swift_code,
        }
    
    return stats


# =============================================================================
# TAX RATE STATISTICS
# =============================================================================

def get_tax_rate_statistics(filters=None):
    """
    Get comprehensive statistics for tax rates
    
    Args:
        filters (dict): Optional filters
            - tax_type: Filter by tax type
            - is_active: Filter by active status
            - is_effective: Filter by effectiveness on current date
    
    Returns:
        dict: Tax rate statistics
    """
    from .models import TaxRate
    
    tax_rates = TaxRate.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('tax_type'):
            tax_rates = tax_rates.filter(tax_type=filters['tax_type'])
        if filters.get('is_active') is not None:
            tax_rates = tax_rates.filter(is_active=filters['is_active'])
        if filters.get('is_effective'):
            current_date = timezone.now().date()
            tax_rates = tax_rates.filter(
                is_active=True,
                effective_from__lte=current_date
            ).filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=current_date)
            )
    
    total_tax_rates = tax_rates.count()
    current_date = timezone.now().date()
    
    stats = {
        'total_tax_rates': total_tax_rates,
        
        # Status
        'active_tax_rates': tax_rates.filter(is_active=True).count(),
        'inactive_tax_rates': tax_rates.filter(is_active=False).count(),
        
        # Effectiveness
        'effective_tax_rates': 0,
        'scheduled_tax_rates': 0,
        'expired_tax_rates': 0,
        
        # By tax type
        'by_tax_type': {},
        
        # Application scope
        'application_scope': {
            'applies_to_members': tax_rates.filter(applies_to_members=True).count(),
            'applies_to_sacco': tax_rates.filter(applies_to_sacco=True).count(),
            'applies_to_both': tax_rates.filter(
                applies_to_members=True, 
                applies_to_sacco=True
            ).count(),
        },
        
        # Current effective rates
        'current_effective_rates': {},
    }
    
    # Count effective, scheduled, and expired rates
    for rate in tax_rates.filter(is_active=True):
        if rate.is_effective(current_date):
            stats['effective_tax_rates'] += 1
        elif current_date < rate.effective_from:
            stats['scheduled_tax_rates'] += 1
        elif rate.effective_to and current_date > rate.effective_to:
            stats['expired_tax_rates'] += 1
    
    # Breakdown by tax type
    tax_type_data = tax_rates.values('tax_type').annotate(
        count=Count('id'),
        active_count=Count(Case(When(is_active=True, then=1)))
    ).order_by('tax_type')
    
    for item in tax_type_data:
        tax_type = item['tax_type']
        stats['by_tax_type'][tax_type] = {
            'total': item['count'],
            'active': item['active_count'],
        }
    
    # Current effective rates by type
    tax_types = ['WHT_INTEREST', 'WHT_DIVIDEND', 'CORPORATE', 'VAT', 'LOCAL_SERVICE', 'STAMP_DUTY', 'OTHER']
    for tax_type in tax_types:
        rate_obj = TaxRate.get_active_rate(tax_type)
        if rate_obj:
            stats['current_effective_rates'][tax_type] = {
                'id': str(rate_obj.id),
                'name': rate_obj.name,
                'rate': float(rate_obj.rate),
                'effective_from': rate_obj.effective_from.strftime('%Y-%m-%d'),
                'effective_to': rate_obj.effective_to.strftime('%Y-%m-%d') if rate_obj.effective_to else None,
            }
    
    # Recent activity
    current_datetime = timezone.now()
    stats['recent_activity'] = {
        'created_last_30_days': tax_rates.filter(
            created_at__gte=current_datetime - timedelta(days=30)
        ).count(),
        'becoming_effective_next_30_days': tax_rates.filter(
            is_active=True,
            effective_from__lte=current_date + timedelta(days=30),
            effective_from__gte=current_date
        ).count(),
    }
    
    return stats


def get_tax_rate_detail_stats(tax_rate_id):
    """
    Get detailed statistics for a specific tax rate
    
    Args:
        tax_rate_id: Tax rate ID
    
    Returns:
        dict: Detailed tax rate statistics
    """
    from .models import TaxRate
    
    try:
        tax_rate = TaxRate.objects.get(id=tax_rate_id)
    except TaxRate.DoesNotExist:
        return None
    
    current_date = timezone.now().date()
    
    stats = {
        'tax_rate': {
            'id': str(tax_rate.id),
            'name': tax_rate.name,
            'tax_type': tax_rate.tax_type,
            'tax_type_display': tax_rate.get_tax_type_display(),
            'rate': float(tax_rate.rate),
            'rate_decimal': float(tax_rate.get_rate_decimal()),
            'is_active': tax_rate.is_active,
        },
        
        # Validity period
        'validity_period': {
            'effective_from': tax_rate.effective_from.strftime('%Y-%m-%d'),
            'effective_to': tax_rate.effective_to.strftime('%Y-%m-%d') if tax_rate.effective_to else None,
            'is_effective': tax_rate.is_effective(current_date),
            'is_valid_today': tax_rate.is_valid_on_date(current_date),
        },
        
        # Application
        'application': {
            'applies_to_members': tax_rate.applies_to_members,
            'applies_to_sacco': tax_rate.applies_to_sacco,
        },
        
        # Metadata
        'metadata': {
            'description': tax_rate.description,
            'legal_reference': tax_rate.legal_reference,
        },
    }
    
    # Calculate sample tax amounts
    sample_amounts = [10000, 50000, 100000, 500000, 1000000]
    stats['sample_calculations'] = {
        amount: float(tax_rate.calculate_tax(amount))
        for amount in sample_amounts
    }
    
    return stats


# =============================================================================
# UNIT OF MEASURE STATISTICS
# =============================================================================

def get_unit_of_measure_statistics(filters=None):
    """
    Get comprehensive statistics for units of measure
    
    Args:
        filters (dict): Optional filters
            - uom_type: Filter by UOM type
            - is_active: Filter by active status
            - has_base_unit: Filter by whether it has a base unit
    
    Returns:
        dict: Unit of measure statistics
    """
    from .models import UnitOfMeasure
    
    units = UnitOfMeasure.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('uom_type'):
            units = units.filter(uom_type=filters['uom_type'])
        if filters.get('is_active') is not None:
            units = units.filter(is_active=filters['is_active'])
        if filters.get('has_base_unit') is not None:
            if filters['has_base_unit']:
                units = units.filter(base_unit__isnull=False)
            else:
                units = units.filter(base_unit__isnull=True)
    
    total_units = units.count()
    
    stats = {
        'total_units': total_units,
        
        # Status
        'active_units': units.filter(is_active=True).count(),
        'inactive_units': units.filter(is_active=False).count(),
        
        # Unit hierarchy
        'base_units': units.filter(base_unit__isnull=True).count(),
        'derived_units': units.filter(base_unit__isnull=False).count(),
        
        # By UOM type
        'by_uom_type': {},
    }
    
    # Breakdown by UOM type
    uom_type_data = units.values('uom_type').annotate(
        count=Count('id'),
        active_count=Count(Case(When(is_active=True, then=1))),
        base_units=Count(Case(When(base_unit__isnull=True, then=1))),
        derived_units=Count(Case(When(base_unit__isnull=False, then=1)))
    ).order_by('uom_type')
    
    for item in uom_type_data:
        uom_type = item['uom_type']
        stats['by_uom_type'][uom_type] = {
            'total': item['count'],
            'active': item['active_count'],
            'base_units': item['base_units'],
            'derived_units': item['derived_units'],
        }
    
    # Recent activity
    current_date = timezone.now()
    stats['recent_activity'] = {
        'created_last_30_days': units.filter(
            created_at__gte=current_date - timedelta(days=30)
        ).count(),
        'updated_last_30_days': units.filter(
            updated_at__gte=current_date - timedelta(days=30)
        ).count(),
    }
    
    return stats


# =============================================================================
# SACCO CONFIGURATION STATISTICS
# =============================================================================

def get_sacco_configuration_stats():
    """
    Get statistics for SACCO configuration
    
    Returns:
        dict: SACCO configuration statistics
    """
    from .models import SaccoConfiguration
    
    config = SaccoConfiguration.get_instance()
    
    if not config:
        return {
            'configuration_exists': False,
            'error': 'SACCO configuration not found'
        }
    
    stats = {
        'configuration_exists': True,
        
        # Period system
        'period_system': {
            'system': config.period_system,
            'system_display': config.get_period_system_display(),
            'periods_per_year': config.periods_per_year,
            'period_naming_convention': config.period_naming_convention,
            'period_type_name': config.get_period_type_name(),
            'period_type_name_plural': config.get_period_type_name_plural(),
        },
        
        # Fiscal year configuration
        'fiscal_year': {
            'fiscal_year_type': config.fiscal_year_type,
            'fiscal_year_type_display': config.get_fiscal_year_type_display(),
            'start_month': config.fiscal_year_start_month,
            'start_month_display': config.get_fiscal_year_start_month_display(),
            'start_day': config.fiscal_year_start_day,
        },
        
        # Dividend settings
        'dividend_settings': {
            'calculation_method': config.dividend_calculation_method,
            'calculation_method_display': config.get_dividend_calculation_method_display(),
            'distribution_frequency': config.dividend_distribution_frequency,
            'distribution_frequency_display': config.get_dividend_distribution_frequency_display(),
        },
        
        # Communication settings
        'communication': {
            'automatic_reminders': config.enable_automatic_reminders,
            'sms_enabled': config.enable_sms,
            'email_enabled': config.enable_email_notifications,
        },
        
        # Period names
        'all_period_names': config.get_all_period_names(),
    }
    
    # Add custom period names if using custom naming
    if config.period_naming_convention == 'custom':
        stats['custom_period_names'] = config.custom_period_names
    
    return stats


# =============================================================================
# FINANCIAL SETTINGS STATISTICS
# =============================================================================

def get_financial_settings_stats():
    """
    Get statistics for financial settings
    
    Returns:
        dict: Financial settings statistics
    """
    from .models import FinancialSettings
    
    settings = FinancialSettings.get_instance()
    
    if not settings:
        return {
            'settings_exist': False,
            'error': 'Financial settings not found'
        }
    
    stats = {
        'settings_exist': True,
        
        # Currency configuration
        'currency': {
            'sacco_currency': settings.sacco_currency.code,
            'currency_position': settings.currency_position,
            'currency_position_display': settings.get_currency_position_display(),
            'decimal_places': settings.decimal_places,
            'use_thousand_separator': settings.use_thousand_separator,
        },
        
        # Loan settings
        'loan_settings': {
            'default_loan_term_days': settings.default_loan_term_days,
            'default_interest_rate': float(settings.default_interest_rate),
            'late_payment_penalty_rate': float(settings.late_payment_penalty_rate),
            'grace_period_days': settings.grace_period_days,
            'minimum_loan_amount': float(settings.minimum_loan_amount),
            'maximum_loan_amount': float(settings.maximum_loan_amount),
        },
        
        # Savings settings
        'savings_settings': {
            'minimum_savings_balance': float(settings.minimum_savings_balance),
            'savings_interest_rate': float(settings.savings_interest_rate),
        },
        
        # Share capital settings
        'share_settings': {
            'share_value': float(settings.share_value),
            'minimum_shares': settings.minimum_shares,
        },
        
        # Workflow settings
        'workflow': {
            'loan_approval_required': settings.loan_approval_required,
            'withdrawal_approval_required': settings.withdrawal_approval_required,
            'withdrawal_approval_limit': float(settings.withdrawal_approval_limit),
        },
        
        # Communication settings
        'communication': {
            'send_transaction_notifications': settings.send_transaction_notifications,
            'send_loan_reminders': settings.send_loan_reminders,
            'send_dividend_notifications': settings.send_dividend_notifications,
        },
    }
    
    # Sample currency formatting
    sample_amounts = [1000, 10000, 100000, 1000000]
    stats['sample_formatting'] = {
        amount: settings.format_currency(amount)
        for amount in sample_amounts
    }
    
    return stats


# =============================================================================
# COMPREHENSIVE CORE STATISTICS
# =============================================================================

def get_comprehensive_core_statistics():
    """
    Get comprehensive statistics for all core models
    
    Returns:
        dict: Complete core statistics
    """
    return {
        'fiscal_years': get_fiscal_year_statistics(),
        'periods': get_period_statistics(),
        'payment_methods': get_payment_method_statistics(),
        'tax_rates': get_tax_rate_statistics(),
        'units_of_measure': get_unit_of_measure_statistics(),
        'sacco_configuration': get_sacco_configuration_stats(),
        'financial_settings': get_financial_settings_stats(),
        'generated_at': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }