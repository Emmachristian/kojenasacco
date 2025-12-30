# core/htmx_views.py

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Count, Sum, Avg, Min, Max, F, DecimalField, Case, When
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from datetime import timedelta
from decimal import Decimal
import logging

from .models import (
    SaccoConfiguration,
    FinancialSettings,
    FiscalYear,
    FiscalPeriod,
    PaymentMethod,
    TaxRate,
    UnitOfMeasure,
)
from core.utils import parse_filters, paginate_queryset, format_money

logger = logging.getLogger(__name__)


# =============================================================================
# FISCAL YEAR SEARCH
# =============================================================================

def fiscal_year_search(request):
    """HTMX-compatible fiscal year search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'status', 'is_active', 'is_closed', 'is_locked',
        'start_date_from', 'start_date_to', 'end_date_from', 'end_date_to',
        'year'
    ])
    
    query = filters['q']
    status = filters['status']
    is_active = filters['is_active']
    is_closed = filters['is_closed']
    is_locked = filters['is_locked']
    start_date_from = filters['start_date_from']
    start_date_to = filters['start_date_to']
    end_date_from = filters['end_date_from']
    end_date_to = filters['end_date_to']
    year = filters['year']
    
    # Build queryset
    fiscal_years = FiscalYear.objects.annotate(
        period_count=Count('periods', distinct=True),
        open_periods=Count(
            'periods',
            filter=Q(periods__is_closed=False),
            distinct=True
        ),
        duration_days=F('end_date') - F('start_date')
    ).order_by('-start_date')
    
    # Apply text search
    if query:
        fiscal_years = fiscal_years.filter(
            Q(name__icontains=query) |
            Q(code__icontains=query) |
            Q(description__icontains=query)
        )
    
    # Apply filters
    if status:
        fiscal_years = fiscal_years.filter(status=status)
    
    if is_active is not None:
        fiscal_years = fiscal_years.filter(is_active=(is_active.lower() == 'true'))
    
    if is_closed is not None:
        fiscal_years = fiscal_years.filter(is_closed=(is_closed.lower() == 'true'))
    
    if is_locked is not None:
        fiscal_years = fiscal_years.filter(is_locked=(is_locked.lower() == 'true'))
    
    # Date filters
    if start_date_from:
        fiscal_years = fiscal_years.filter(start_date__gte=start_date_from)
    
    if start_date_to:
        fiscal_years = fiscal_years.filter(start_date__lte=start_date_to)
    
    if end_date_from:
        fiscal_years = fiscal_years.filter(end_date__gte=end_date_from)
    
    if end_date_to:
        fiscal_years = fiscal_years.filter(end_date__lte=end_date_to)
    
    if year:
        try:
            fiscal_years = fiscal_years.filter(
                Q(start_date__year=int(year)) | Q(end_date__year=int(year))
            )
        except ValueError:
            pass
    
    # Paginate
    fiscal_years_page, paginator = paginate_queryset(request, fiscal_years, per_page=20)
    
    # Calculate stats
    total = fiscal_years.count()
    
    stats = {
        'total': total,
        'draft': fiscal_years.filter(status='DRAFT').count(),
        'active': fiscal_years.filter(status='ACTIVE').count(),
        'closed': fiscal_years.filter(status='CLOSED').count(),
        'locked': fiscal_years.filter(status='LOCKED').count(),
        'current': fiscal_years.filter(is_active=True).count(),
        'total_periods': fiscal_years.aggregate(Sum('period_count'))['period_count__sum'] or 0,
        'avg_duration': fiscal_years.aggregate(Avg('duration_days'))['duration_days__avg'],
    }
    
    # Format average duration
    if stats['avg_duration']:
        stats['avg_duration_days'] = stats['avg_duration'].days
    else:
        stats['avg_duration_days'] = 0
    
    return render(request, 'core/fiscal_years/_fiscal_year_results.html', {
        'fiscal_years_page': fiscal_years_page,
        'stats': stats,
    })


# =============================================================================
# FISCAL PERIOD SEARCH
# =============================================================================

def fiscal_period_search(request):
    """HTMX-compatible fiscal period search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'fiscal_year', 'status', 'is_active', 'is_closed', 'is_locked',
        'start_date_from', 'start_date_to', 'end_date_from', 'end_date_to',
        'min_period_number', 'max_period_number'
    ])
    
    query = filters['q']
    fiscal_year = filters['fiscal_year']
    status = filters['status']
    is_active = filters['is_active']
    is_closed = filters['is_closed']
    is_locked = filters['is_locked']
    start_date_from = filters['start_date_from']
    start_date_to = filters['start_date_to']
    end_date_from = filters['end_date_from']
    end_date_to = filters['end_date_to']
    min_period_number = filters['min_period_number']
    max_period_number = filters['max_period_number']
    
    # Build queryset
    periods = FiscalPeriod.objects.select_related(
        'fiscal_year'
    ).annotate(
        duration_days=F('end_date') - F('start_date')
    ).order_by('-fiscal_year__start_date', 'period_number')
    
    # Apply text search
    if query:
        periods = periods.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(fiscal_year__name__icontains=query) |
            Q(fiscal_year__code__icontains=query)
        )
    
    # Apply filters
    if fiscal_year:
        periods = periods.filter(fiscal_year_id=fiscal_year)
    
    if status:
        periods = periods.filter(status=status)
    
    if is_active is not None:
        periods = periods.filter(is_active=(is_active.lower() == 'true'))
    
    if is_closed is not None:
        periods = periods.filter(is_closed=(is_closed.lower() == 'true'))
    
    if is_locked is not None:
        periods = periods.filter(is_locked=(is_locked.lower() == 'true'))
    
    # Date filters
    if start_date_from:
        periods = periods.filter(start_date__gte=start_date_from)
    
    if start_date_to:
        periods = periods.filter(start_date__lte=start_date_to)
    
    if end_date_from:
        periods = periods.filter(end_date__gte=end_date_from)
    
    if end_date_to:
        periods = periods.filter(end_date__lte=end_date_to)
    
    # Period number filters
    if min_period_number:
        try:
            periods = periods.filter(period_number__gte=int(min_period_number))
        except (ValueError, TypeError):
            pass
    
    if max_period_number:
        try:
            periods = periods.filter(period_number__lte=int(max_period_number))
        except (ValueError, TypeError):
            pass
    
    # Paginate
    periods_page, paginator = paginate_queryset(request, periods, per_page=20)
    
    # Calculate stats
    total = periods.count()
    
    stats = {
        'total': total,
        'draft': periods.filter(status='DRAFT').count(),
        'active': periods.filter(status='ACTIVE').count(),
        'closed': periods.filter(status='CLOSED').count(),
        'locked': periods.filter(status='LOCKED').count(),
        'current': periods.filter(is_active=True).count(),
        'unique_fiscal_years': periods.values('fiscal_year').distinct().count(),
        'avg_duration': periods.aggregate(Avg('duration_days'))['duration_days__avg'],
        'min_period_number': periods.aggregate(Min('period_number'))['period_number__min'] or 0,
        'max_period_number': periods.aggregate(Max('period_number'))['period_number__max'] or 0,
    }
    
    # Format average duration
    if stats['avg_duration']:
        stats['avg_duration_days'] = stats['avg_duration'].days
    else:
        stats['avg_duration_days'] = 0
    
    return render(request, 'core/periods/_period_results.html', {
        'periods_page': periods_page,
        'stats': stats,
    })


# =============================================================================
# PAYMENT METHOD SEARCH
# =============================================================================

def payment_method_search(request):
    """HTMX-compatible payment method search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'method_type', 'mobile_money_provider', 'is_active',
        'is_default', 'requires_approval', 'has_transaction_fee'
    ])
    
    query = filters['q']
    method_type = filters['method_type']
    mobile_money_provider = filters['mobile_money_provider']
    is_active = filters['is_active']
    is_default = filters['is_default']
    requires_approval = filters['requires_approval']
    has_transaction_fee = filters['has_transaction_fee']
    
    # Build queryset
    payment_methods = PaymentMethod.objects.annotate(
        has_limits=Case(
            When(
                Q(minimum_amount__isnull=False) | Q(maximum_amount__isnull=False),
                then=True
            ),
            default=False
        )
    ).order_by('display_order', 'name')
    
    # Apply text search
    if query:
        payment_methods = payment_methods.filter(
            Q(name__icontains=query) |
            Q(code__icontains=query) |
            Q(bank_name__icontains=query) |
            Q(bank_account_number__icontains=query) |
            Q(instructions__icontains=query)
        )
    
    # Apply filters
    if method_type:
        payment_methods = payment_methods.filter(method_type=method_type)
    
    if mobile_money_provider:
        payment_methods = payment_methods.filter(mobile_money_provider=mobile_money_provider)
    
    if is_active is not None:
        payment_methods = payment_methods.filter(is_active=(is_active.lower() == 'true'))
    
    if is_default is not None:
        payment_methods = payment_methods.filter(is_default=(is_default.lower() == 'true'))
    
    if requires_approval is not None:
        payment_methods = payment_methods.filter(requires_approval=(requires_approval.lower() == 'true'))
    
    if has_transaction_fee is not None:
        payment_methods = payment_methods.filter(has_transaction_fee=(has_transaction_fee.lower() == 'true'))
    
    # Paginate
    payment_methods_page, paginator = paginate_queryset(request, payment_methods, per_page=20)
    
    # Calculate stats
    total = payment_methods.count()
    
    stats = {
        'total': total,
        'active': payment_methods.filter(is_active=True).count(),
        'inactive': payment_methods.filter(is_active=False).count(),
        'default': payment_methods.filter(is_default=True).count(),
        'requires_approval': payment_methods.filter(requires_approval=True).count(),
        'has_fees': payment_methods.filter(has_transaction_fee=True).count(),
        'cash': payment_methods.filter(method_type='CASH').count(),
        'mobile_money': payment_methods.filter(method_type='MOBILE_MONEY').count(),
        'bank_transfer': payment_methods.filter(method_type='BANK_TRANSFER').count(),
        'cheque': payment_methods.filter(method_type='CHEQUE').count(),
        'card': payment_methods.filter(method_type='CARD').count(),
        'other': payment_methods.filter(method_type='OTHER').count(),
    }
    
    # Mobile money breakdown
    stats['mtn'] = payment_methods.filter(mobile_money_provider='MTN').count()
    stats['airtel'] = payment_methods.filter(mobile_money_provider='AIRTEL').count()
    stats['africell'] = payment_methods.filter(mobile_money_provider='AFRICELL').count()
    
    return render(request, 'core/payment_methods/_payment_method_results.html', {
        'payment_methods_page': payment_methods_page,
        'stats': stats,
    })


# =============================================================================
# TAX RATE SEARCH
# =============================================================================

def tax_rate_search(request):
    """HTMX-compatible tax rate search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'tax_type', 'is_active', 'applies_to_members',
        'applies_to_sacco', 'effective_from', 'effective_to',
        'min_rate', 'max_rate', 'is_effective'
    ])
    
    query = filters['q']
    tax_type = filters['tax_type']
    is_active = filters['is_active']
    applies_to_members = filters['applies_to_members']
    applies_to_sacco = filters['applies_to_sacco']
    effective_from = filters['effective_from']
    effective_to = filters['effective_to']
    min_rate = filters['min_rate']
    max_rate = filters['max_rate']
    is_effective = filters['is_effective']
    
    # Build queryset
    tax_rates = TaxRate.objects.order_by('-effective_from', 'tax_type')
    
    # Apply text search
    if query:
        tax_rates = tax_rates.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(legal_reference__icontains=query)
        )
    
    # Apply filters
    if tax_type:
        tax_rates = tax_rates.filter(tax_type=tax_type)
    
    if is_active is not None:
        tax_rates = tax_rates.filter(is_active=(is_active.lower() == 'true'))
    
    if applies_to_members is not None:
        tax_rates = tax_rates.filter(applies_to_members=(applies_to_members.lower() == 'true'))
    
    if applies_to_sacco is not None:
        tax_rates = tax_rates.filter(applies_to_sacco=(applies_to_sacco.lower() == 'true'))
    
    # Date filters
    if effective_from:
        tax_rates = tax_rates.filter(effective_from__gte=effective_from)
    
    if effective_to:
        tax_rates = tax_rates.filter(
            Q(effective_to__lte=effective_to) | Q(effective_to__isnull=True)
        )
    
    # Rate filters
    if min_rate:
        try:
            tax_rates = tax_rates.filter(rate__gte=Decimal(min_rate))
        except (ValueError, TypeError):
            pass
    
    if max_rate:
        try:
            tax_rates = tax_rates.filter(rate__lte=Decimal(max_rate))
        except (ValueError, TypeError):
            pass
    
    # Effective filter (currently effective rates)
    if is_effective is not None and is_effective.lower() == 'true':
        today = timezone.now().date()
        tax_rates = tax_rates.filter(
            is_active=True,
            effective_from__lte=today
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=today)
        )
    
    # Paginate
    tax_rates_page, paginator = paginate_queryset(request, tax_rates, per_page=20)
    
    # Calculate stats
    total = tax_rates.count()
    
    # Get currently effective rates
    today = timezone.now().date()
    effective_rates = tax_rates.filter(
        is_active=True,
        effective_from__lte=today
    ).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gte=today)
    )
    
    aggregates = tax_rates.filter(is_active=True).aggregate(
        avg_rate=Avg('rate'),
        min_rate=Min('rate'),
        max_rate=Max('rate')
    )
    
    stats = {
        'total': total,
        'active': tax_rates.filter(is_active=True).count(),
        'inactive': tax_rates.filter(is_active=False).count(),
        'effective_now': effective_rates.count(),
        'applies_to_members': tax_rates.filter(applies_to_members=True).count(),
        'applies_to_sacco': tax_rates.filter(applies_to_sacco=True).count(),
        'avg_rate': aggregates['avg_rate'] or Decimal('0.00'),
        'min_rate': aggregates['min_rate'] or Decimal('0.00'),
        'max_rate': aggregates['max_rate'] or Decimal('0.00'),
        'wht_interest': tax_rates.filter(tax_type='WHT_INTEREST').count(),
        'wht_dividend': tax_rates.filter(tax_type='WHT_DIVIDEND').count(),
        'corporate': tax_rates.filter(tax_type='CORPORATE').count(),
        'vat': tax_rates.filter(tax_type='VAT').count(),
        'other': tax_rates.filter(tax_type='OTHER').count(),
    }
    
    return render(request, 'core/tax_rates/_tax_rate_results.html', {
        'tax_rates_page': tax_rates_page,
        'stats': stats,
    })


# =============================================================================
# UNIT OF MEASURE SEARCH
# =============================================================================

def unit_of_measure_search(request):
    """HTMX-compatible unit of measure search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'uom_type', 'base_unit', 'is_active', 'has_base_unit'
    ])
    
    query = filters['q']
    uom_type = filters['uom_type']
    base_unit = filters['base_unit']
    is_active = filters['is_active']
    has_base_unit = filters['has_base_unit']
    
    # Build queryset
    units = UnitOfMeasure.objects.select_related(
        'base_unit'
    ).annotate(
        derived_count=Count('derived_units', distinct=True)
    ).order_by('uom_type', 'name')
    
    # Apply text search
    if query:
        units = units.filter(
            Q(name__icontains=query) |
            Q(abbreviation__icontains=query) |
            Q(symbol__icontains=query) |
            Q(description__icontains=query)
        )
    
    # Apply filters
    if uom_type:
        units = units.filter(uom_type=uom_type)
    
    if base_unit:
        units = units.filter(base_unit_id=base_unit)
    
    if is_active is not None:
        units = units.filter(is_active=(is_active.lower() == 'true'))
    
    if has_base_unit is not None:
        if has_base_unit.lower() == 'true':
            units = units.exclude(base_unit__isnull=True)
        else:
            units = units.filter(base_unit__isnull=True)
    
    # Paginate
    units_page, paginator = paginate_queryset(request, units, per_page=20)
    
    # Calculate stats
    total = units.count()
    
    stats = {
        'total': total,
        'active': units.filter(is_active=True).count(),
        'inactive': units.filter(is_active=False).count(),
        'base_units': units.filter(base_unit__isnull=True).count(),
        'derived_units': units.exclude(base_unit__isnull=True).count(),
        'length': units.filter(uom_type='LENGTH').count(),
        'weight': units.filter(uom_type='WEIGHT').count(),
        'volume': units.filter(uom_type='VOLUME').count(),
        'area': units.filter(uom_type='AREA').count(),
        'quantity': units.filter(uom_type='QUANTITY').count(),
        'time': units.filter(uom_type='TIME').count(),
        'other': units.filter(uom_type='OTHER').count(),
        'with_derived': units.filter(derived_count__gt=0).count(),
    }
    
    return render(request, 'core/units/_unit_results.html', {
        'units_page': units_page,
        'stats': stats,
    })


# =============================================================================
# QUICK STATS ENDPOINTS
# =============================================================================

@require_http_methods(["GET"])
def fiscal_year_quick_stats(request):
    """Get quick statistics for fiscal years"""
    
    today = timezone.now().date()
    
    stats = {
        'total_fiscal_years': FiscalYear.objects.count(),
        'draft': FiscalYear.objects.filter(status='DRAFT').count(),
        'active': FiscalYear.objects.filter(status='ACTIVE').count(),
        'closed': FiscalYear.objects.filter(status='CLOSED').count(),
        'locked': FiscalYear.objects.filter(status='LOCKED').count(),
        'current_year': None,
        'total_periods': FiscalPeriod.objects.count(),
        'open_periods': FiscalPeriod.objects.filter(is_closed=False).count(),
    }
    
    # Get current fiscal year
    current_fy = FiscalYear.objects.filter(is_active=True).first()
    if current_fy:
        stats['current_year'] = current_fy.name
        stats['current_year_id'] = str(current_fy.id)
        stats['current_year_progress'] = current_fy.get_progress_percentage()
        stats['current_year_remaining_days'] = current_fy.get_remaining_days()
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def fiscal_period_quick_stats(request):
    """Get quick statistics for fiscal periods"""
    
    today = timezone.now().date()
    
    stats = {
        'total_periods': FiscalPeriod.objects.count(),
        'draft': FiscalPeriod.objects.filter(status='DRAFT').count(),
        'active': FiscalPeriod.objects.filter(status='ACTIVE').count(),
        'closed': FiscalPeriod.objects.filter(status='CLOSED').count(),
        'locked': FiscalPeriod.objects.filter(status='LOCKED').count(),
        'current_period': None,
        'unique_fiscal_years': FiscalPeriod.objects.values('fiscal_year').distinct().count(),
    }
    
    # Get current period
    current_period = FiscalPeriod.objects.filter(is_active=True).first()
    if current_period:
        stats['current_period'] = current_period.name
        stats['current_period_id'] = str(current_period.id)
        stats['current_period_number'] = current_period.period_number
        stats['current_period_progress'] = current_period.get_progress_percentage()
        stats['current_period_remaining_days'] = current_period.get_remaining_days()
        stats['current_fiscal_year'] = current_period.fiscal_year.name
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def payment_method_quick_stats(request):
    """Get quick statistics for payment methods"""
    
    stats = {
        'total_methods': PaymentMethod.objects.count(),
        'active': PaymentMethod.objects.filter(is_active=True).count(),
        'inactive': PaymentMethod.objects.filter(is_active=False).count(),
        'default': PaymentMethod.objects.filter(is_default=True).count(),
        'with_fees': PaymentMethod.objects.filter(has_transaction_fee=True).count(),
        'requires_approval': PaymentMethod.objects.filter(requires_approval=True).count(),
        'cash': PaymentMethod.objects.filter(method_type='CASH', is_active=True).count(),
        'mobile_money': PaymentMethod.objects.filter(method_type='MOBILE_MONEY', is_active=True).count(),
        'bank_transfer': PaymentMethod.objects.filter(method_type='BANK_TRANSFER', is_active=True).count(),
        'cheque': PaymentMethod.objects.filter(method_type='CHEQUE', is_active=True).count(),
        'card': PaymentMethod.objects.filter(method_type='CARD', is_active=True).count(),
    }
    
    # Get default payment method
    default_method = PaymentMethod.objects.filter(is_default=True, is_active=True).first()
    if default_method:
        stats['default_method'] = default_method.name
        stats['default_method_type'] = default_method.get_method_type_display()
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def tax_rate_quick_stats(request):
    """Get quick statistics for tax rates"""
    
    today = timezone.now().date()
    
    # Get currently effective rates
    effective_rates = TaxRate.objects.filter(
        is_active=True,
        effective_from__lte=today
    ).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gte=today)
    )
    
    aggregates = TaxRate.objects.filter(is_active=True).aggregate(
        avg_rate=Avg('rate'),
        min_rate=Min('rate'),
        max_rate=Max('rate')
    )
    
    stats = {
        'total_rates': TaxRate.objects.count(),
        'active': TaxRate.objects.filter(is_active=True).count(),
        'inactive': TaxRate.objects.filter(is_active=False).count(),
        'effective_now': effective_rates.count(),
        'avg_rate': str(aggregates['avg_rate'] or Decimal('0.00')),
        'min_rate': str(aggregates['min_rate'] or Decimal('0.00')),
        'max_rate': str(aggregates['max_rate'] or Decimal('0.00')),
        'wht_interest': TaxRate.objects.filter(tax_type='WHT_INTEREST', is_active=True).count(),
        'wht_dividend': TaxRate.objects.filter(tax_type='WHT_DIVIDEND', is_active=True).count(),
        'corporate': TaxRate.objects.filter(tax_type='CORPORATE', is_active=True).count(),
        'vat': TaxRate.objects.filter(tax_type='VAT', is_active=True).count(),
    }
    
    # Get current WHT rates
    wht_interest = TaxRate.get_active_rate('WHT_INTEREST', today)
    if wht_interest:
        stats['current_wht_interest'] = str(wht_interest.rate)
    
    wht_dividend = TaxRate.get_active_rate('WHT_DIVIDEND', today)
    if wht_dividend:
        stats['current_wht_dividend'] = str(wht_dividend.rate)
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def unit_of_measure_quick_stats(request):
    """Get quick statistics for units of measure"""
    
    stats = {
        'total_units': UnitOfMeasure.objects.count(),
        'active': UnitOfMeasure.objects.filter(is_active=True).count(),
        'inactive': UnitOfMeasure.objects.filter(is_active=False).count(),
        'base_units': UnitOfMeasure.objects.filter(base_unit__isnull=True).count(),
        'derived_units': UnitOfMeasure.objects.exclude(base_unit__isnull=True).count(),
        'length': UnitOfMeasure.objects.filter(uom_type='LENGTH', is_active=True).count(),
        'weight': UnitOfMeasure.objects.filter(uom_type='WEIGHT', is_active=True).count(),
        'volume': UnitOfMeasure.objects.filter(uom_type='VOLUME', is_active=True).count(),
        'area': UnitOfMeasure.objects.filter(uom_type='AREA', is_active=True).count(),
        'quantity': UnitOfMeasure.objects.filter(uom_type='QUANTITY', is_active=True).count(),
        'time': UnitOfMeasure.objects.filter(uom_type='TIME', is_active=True).count(),
        'other': UnitOfMeasure.objects.filter(uom_type='OTHER', is_active=True).count(),
    }
    
    return JsonResponse(stats)


# =============================================================================
# DETAIL STATS ENDPOINTS
# =============================================================================

@require_http_methods(["GET"])
def fiscal_year_detail_stats(request, year_id):
    """Get detailed statistics for a specific fiscal year"""
    
    fiscal_year = get_object_or_404(FiscalYear, id=year_id)
    
    periods = fiscal_year.periods.all()
    
    stats = {
        'year_name': fiscal_year.name,
        'year_code': fiscal_year.code,
        'year_status': fiscal_year.get_status_display(),
        'start_date': fiscal_year.start_date.isoformat(),
        'end_date': fiscal_year.end_date.isoformat(),
        'duration_days': fiscal_year.get_duration_days(),
        'progress_percentage': fiscal_year.get_progress_percentage(),
        'elapsed_days': fiscal_year.get_elapsed_days(),
        'remaining_days': fiscal_year.get_remaining_days(),
        'is_current': fiscal_year.is_current(),
        'is_upcoming': fiscal_year.is_upcoming(),
        'is_past': fiscal_year.is_past(),
        'total_periods': periods.count(),
        'draft_periods': periods.filter(status='DRAFT').count(),
        'active_periods': periods.filter(status='ACTIVE').count(),
        'closed_periods': periods.filter(status='CLOSED').count(),
        'locked_periods': periods.filter(status='LOCKED').count(),
        'open_periods': periods.filter(is_closed=False).count(),
    }
    
    # Current period in this fiscal year
    current_period = periods.filter(is_active=True).first()
    if current_period:
        stats['current_period'] = current_period.name
        stats['current_period_number'] = current_period.period_number
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def fiscal_period_detail_stats(request, period_id):
    """Get detailed statistics for a specific fiscal period"""
    
    period = get_object_or_404(FiscalPeriod, id=period_id)
    
    stats = {
        'period_name': period.name,
        'period_number': period.period_number,
        'period_status': period.get_status_display(),
        'fiscal_year': period.fiscal_year.name,
        'start_date': period.start_date.isoformat(),
        'end_date': period.end_date.isoformat(),
        'duration_days': period.get_duration_days(),
        'progress_percentage': period.get_progress_percentage(),
        'elapsed_days': period.get_elapsed_days(),
        'remaining_days': period.get_remaining_days(),
        'is_current': period.is_current(),
        'is_upcoming': period.is_upcoming(),
        'is_past': period.is_past(),
        'is_last_period': period.is_last_period(),
    }
    
    # Next and previous periods
    next_period = period.get_next_period()
    if next_period:
        stats['next_period'] = next_period.name
        stats['next_period_id'] = str(next_period.id)
    
    previous_period = period.get_previous_period()
    if previous_period:
        stats['previous_period'] = previous_period.name
        stats['previous_period_id'] = str(previous_period.id)
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def payment_method_detail_stats(request, method_id):
    """Get detailed statistics for a specific payment method"""
    
    method = get_object_or_404(PaymentMethod, id=method_id)
    
    stats = {
        'name': method.name,
        'code': method.code,
        'method_type': method.get_method_type_display(),
        'is_active': method.is_active,
        'is_default': method.is_default,
        'requires_approval': method.requires_approval,
        'has_transaction_fee': method.has_transaction_fee,
        'requires_reference': method.requires_reference,
        'processing_time': method.processing_time or 'Not specified',
    }
    
    # Fee information
    if method.has_transaction_fee:
        stats['fee_type'] = method.get_transaction_fee_type_display() if method.transaction_fee_type else None
        stats['fee_amount'] = str(method.transaction_fee_amount) if method.transaction_fee_amount else None
        stats['fee_bearer'] = method.get_fee_bearer_display() if method.fee_bearer else None
        stats['fee_display'] = method.get_fee_display()
    
    # Limits
    stats['has_limits'] = bool(method.minimum_amount or method.maximum_amount or method.daily_limit)
    if method.minimum_amount:
        stats['minimum_amount'] = str(method.minimum_amount)
        stats['minimum_amount_formatted'] = format_money(method.minimum_amount)
    if method.maximum_amount:
        stats['maximum_amount'] = str(method.maximum_amount)
        stats['maximum_amount_formatted'] = format_money(method.maximum_amount)
    if method.daily_limit:
        stats['daily_limit'] = str(method.daily_limit)
        stats['daily_limit_formatted'] = format_money(method.daily_limit)
    
    # Mobile money specific
    if method.method_type == 'MOBILE_MONEY' and method.mobile_money_provider:
        stats['mobile_money_provider'] = method.get_mobile_money_provider_display()
    
    # Bank specific
    if method.method_type == 'BANK_TRANSFER':
        if method.bank_name:
            stats['bank_name'] = method.bank_name
        if method.bank_account_number:
            stats['bank_account_number'] = method.bank_account_number
        if method.bank_branch:
            stats['bank_branch'] = method.bank_branch
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def tax_rate_detail_stats(request, rate_id):
    """Get detailed statistics for a specific tax rate"""
    
    rate = get_object_or_404(TaxRate, id=rate_id)
    
    today = timezone.now().date()
    
    stats = {
        'name': rate.name,
        'tax_type': rate.get_tax_type_display(),
        'rate': str(rate.rate),
        'rate_decimal': str(rate.get_rate_decimal()),
        'effective_from': rate.effective_from.isoformat(),
        'effective_to': rate.effective_to.isoformat() if rate.effective_to else None,
        'is_active': rate.is_active,
        'is_effective': rate.is_effective(today),
        'applies_to_members': rate.applies_to_members,
        'applies_to_sacco': rate.applies_to_sacco,
    }
    
    # Calculate sample tax amounts
    sample_amounts = [Decimal('100000'), Decimal('500000'), Decimal('1000000')]
    stats['sample_calculations'] = []
    for amount in sample_amounts:
        tax_amount = rate.calculate_tax(amount)
        stats['sample_calculations'].append({
            'amount': str(amount),
            'amount_formatted': format_money(amount),
            'tax': str(tax_amount),
            'tax_formatted': format_money(tax_amount),
            'net': str(amount - tax_amount),
            'net_formatted': format_money(amount - tax_amount)
        })
    
    if rate.description:
        stats['description'] = rate.description
    
    if rate.legal_reference:
        stats['legal_reference'] = rate.legal_reference
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def unit_of_measure_detail_stats(request, unit_id):
    """Get detailed statistics for a specific unit of measure"""
    
    unit = get_object_or_404(UnitOfMeasure, id=unit_id)
    
    stats = {
        'name': unit.name,
        'abbreviation': unit.abbreviation,
        'symbol': unit.symbol,
        'uom_type': unit.get_uom_type_display(),
        'is_active': unit.is_active,
        'conversion_factor': str(unit.conversion_factor),
    }
    
    # Base unit information
    if unit.base_unit:
        stats['base_unit'] = unit.base_unit.name
        stats['base_unit_id'] = str(unit.base_unit.id)
        stats['is_derived'] = True
        
        # Sample conversions
        sample_values = [1, 10, 100, 1000]
        stats['sample_conversions'] = []
        for value in sample_values:
            base_value = unit.convert_to_base(value)
            stats['sample_conversions'].append({
                'value': value,
                'unit': unit.abbreviation,
                'base_value': base_value,
                'base_unit': unit.base_unit.abbreviation
            })
    else:
        stats['is_derived'] = False
        stats['is_base_unit'] = True
        
        # Count derived units
        derived_count = unit.derived_units.count()
        stats['derived_units_count'] = derived_count
        
        if derived_count > 0:
            stats['derived_units'] = [
                {
                    'name': du.name,
                    'abbreviation': du.abbreviation,
                    'conversion_factor': str(du.conversion_factor)
                }
                for du in unit.derived_units.filter(is_active=True)[:5]
            ]
    
    if unit.description:
        stats['description'] = unit.description
    
    return JsonResponse(stats)


# =============================================================================
# CONFIGURATION STATS
# =============================================================================

@require_http_methods(["GET"])
def sacco_configuration_stats(request):
    """Get SACCO configuration statistics"""
    
    config = SaccoConfiguration.get_instance()
    
    if not config:
        return JsonResponse({'error': 'SACCO configuration not found'}, status=404)
    
    stats = {
        'period_system': config.get_period_system_display(),
        'periods_per_year': config.periods_per_year,
        'period_type': config.get_period_type_name(),
        'period_type_plural': config.get_period_type_name_plural(),
        'period_naming_convention': config.get_period_naming_convention_display(),
        'fiscal_year_type': config.get_fiscal_year_type_display(),
        'fiscal_year_start_month': config.get_fiscal_year_start_month_display(),
        'fiscal_year_start_day': config.fiscal_year_start_day,
        'dividend_calculation_method': config.get_dividend_calculation_method_display(),
        'dividend_distribution_frequency': config.get_dividend_distribution_frequency_display(),
        'enable_automatic_reminders': config.enable_automatic_reminders,
        'enable_sms': config.enable_sms,
        'enable_email_notifications': config.enable_email_notifications,
    }
    
    # Get all period names
    stats['period_names'] = config.get_all_period_names()
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def financial_settings_stats(request):
    """Get financial settings statistics"""
    
    settings = FinancialSettings.get_instance()
    
    if not settings:
        return JsonResponse({'error': 'Financial settings not found'}, status=404)
    
    stats = {
        'currency': settings.sacco_currency.code,
        'currency_position': settings.get_currency_position_display(),
        'decimal_places': settings.decimal_places,
        'use_thousand_separator': settings.use_thousand_separator,
        'default_loan_term_days': settings.default_loan_term_days,
        'default_interest_rate': str(settings.default_interest_rate),
        'late_payment_penalty_rate': str(settings.late_payment_penalty_rate),
        'grace_period_days': settings.grace_period_days,
        'minimum_loan_amount': str(settings.minimum_loan_amount),
        'minimum_loan_amount_formatted': settings.format_currency(settings.minimum_loan_amount),
        'maximum_loan_amount': str(settings.maximum_loan_amount),
        'maximum_loan_amount_formatted': settings.format_currency(settings.maximum_loan_amount),
        'minimum_savings_balance': str(settings.minimum_savings_balance),
        'minimum_savings_balance_formatted': settings.format_currency(settings.minimum_savings_balance),
        'savings_interest_rate': str(settings.savings_interest_rate),
        'share_value': str(settings.share_value),
        'share_value_formatted': settings.format_currency(settings.share_value),
        'minimum_shares': settings.minimum_shares,
        'loan_approval_required': settings.loan_approval_required,
        'withdrawal_approval_required': settings.withdrawal_approval_required,
        'withdrawal_approval_limit': str(settings.withdrawal_approval_limit),
        'withdrawal_approval_limit_formatted': settings.format_currency(settings.withdrawal_approval_limit),
        'send_transaction_notifications': settings.send_transaction_notifications,
        'send_loan_reminders': settings.send_loan_reminders,
        'send_dividend_notifications': settings.send_dividend_notifications,
    }
    
    return JsonResponse(stats)