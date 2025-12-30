# dividends/htmx_views.py

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Count, Sum, Avg, F, DecimalField, Case, When, Min, Max
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from datetime import timedelta
from decimal import Decimal
import logging

from .models import (
    DividendPeriod,
    MemberDividend,
    DividendDisbursement,
    DividendPayment,
    DividendRate,
    DividendPreference
)
from core.utils import parse_filters, paginate_queryset, format_money

logger = logging.getLogger(__name__)


# =============================================================================
# DIVIDEND PERIOD SEARCH
# =============================================================================

def dividend_period_search(request):
    """HTMX-compatible dividend period search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'status', 'calculation_method', 'financial_period',
        'is_approved', 'start_date', 'end_date', 'year',
        'min_amount', 'max_amount', 'apply_tax'
    ])
    
    query = filters['q']
    status = filters['status']
    calculation_method = filters['calculation_method']
    financial_period = filters['financial_period']
    is_approved = filters['is_approved']
    start_date = filters['start_date']
    end_date = filters['end_date']
    year = filters['year']
    min_amount = filters['min_amount']
    max_amount = filters['max_amount']
    apply_tax = filters['apply_tax']
    
    # Build queryset
    periods = DividendPeriod.objects.select_related(
        'financial_period'
    ).annotate(
        calculated_members=Count(
            'member_dividends',
            filter=Q(member_dividends__status__in=['CALCULATED', 'APPROVED', 'PAID']),
            distinct=True
        ),
        paid_members=Count(
            'member_dividends',
            filter=Q(member_dividends__status='PAID'),
            distinct=True
        ),
        total_disbursed=Sum(
            'member_dividends__net_dividend',
            filter=Q(member_dividends__status='PAID')
        ),
        disbursement_count=Count('disbursements', distinct=True)
    ).order_by('-end_date', '-created_at')
    
    # Apply text search
    if query:
        periods = periods.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(financial_period__name__icontains=query)
        )
    
    # Apply filters
    if status:
        periods = periods.filter(status=status)
    
    if calculation_method:
        periods = periods.filter(calculation_method=calculation_method)
    
    if financial_period:
        periods = periods.filter(financial_period_id=financial_period)
    
    if is_approved is not None:
        periods = periods.filter(is_approved=(is_approved.lower() == 'true'))
    
    if apply_tax is not None:
        periods = periods.filter(apply_withholding_tax=(apply_tax.lower() == 'true'))
    
    # Date filters
    if start_date:
        periods = periods.filter(start_date__gte=start_date)
    
    if end_date:
        periods = periods.filter(end_date__lte=end_date)
    
    if year:
        try:
            periods = periods.filter(
                Q(start_date__year=int(year)) | Q(end_date__year=int(year))
            )
        except ValueError:
            pass
    
    # Amount filters
    if min_amount:
        try:
            periods = periods.filter(total_dividend_amount__gte=Decimal(min_amount))
        except (ValueError, TypeError):
            pass
    
    if max_amount:
        try:
            periods = periods.filter(total_dividend_amount__lte=Decimal(max_amount))
        except (ValueError, TypeError):
            pass
    
    # Paginate
    periods_page, paginator = paginate_queryset(request, periods, per_page=20)
    
    # Calculate stats
    total = periods.count()
    
    stats = {
        'total': total,
        'draft': periods.filter(status='DRAFT').count(),
        'calculating': periods.filter(status='CALCULATING').count(),
        'calculated': periods.filter(status='CALCULATED').count(),
        'approved': periods.filter(status='APPROVED').count(),
        'disbursing': periods.filter(status='DISBURSING').count(),
        'completed': periods.filter(status='COMPLETED').count(),
        'cancelled': periods.filter(status='CANCELLED').count(),
        'total_amount': periods.aggregate(Sum('total_dividend_amount'))['total_dividend_amount__sum'] or Decimal('0.00'),
        'total_disbursed': periods.aggregate(Sum('total_disbursed'))['total_disbursed__sum'] or Decimal('0.00'),
        'total_members': periods.aggregate(Sum('total_members'))['total_members__sum'] or 0,
        'avg_dividend_rate': periods.aggregate(Avg('dividend_rate'))['dividend_rate__avg'] or Decimal('0.00'),
    }
    
    # Format money in stats
    stats['total_amount_formatted'] = format_money(stats['total_amount'])
    stats['total_disbursed_formatted'] = format_money(stats['total_disbursed'])
    
    return render(request, 'dividends/periods/_period_results.html', {
        'periods_page': periods_page,
        'stats': stats,
    })


# =============================================================================
# MEMBER DIVIDEND SEARCH
# =============================================================================

def member_dividend_search(request):
    """HTMX-compatible member dividend search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'status', 'dividend_period', 'member', 'disbursement_method',
        'min_amount', 'max_amount', 'min_shares', 'max_shares',
        'payment_date_from', 'payment_date_to', 'has_payment_reference'
    ])
    
    query = filters['q']
    status = filters['status']
    dividend_period = filters['dividend_period']
    member = filters['member']
    disbursement_method = filters['disbursement_method']
    min_amount = filters['min_amount']
    max_amount = filters['max_amount']
    min_shares = filters['min_shares']
    max_shares = filters['max_shares']
    payment_date_from = filters['payment_date_from']
    payment_date_to = filters['payment_date_to']
    has_payment_reference = filters['has_payment_reference']
    
    # Build queryset
    dividends = MemberDividend.objects.select_related(
        'dividend_period',
        'member',
        'disbursement_account',
        'disbursement_account__savings_product'
    ).annotate(
        payment_count=Count('payments', distinct=True)
    ).order_by('-dividend_period__end_date', '-net_dividend')
    
    # Apply text search
    if query:
        dividends = dividends.filter(
            Q(member__first_name__icontains=query) |
            Q(member__last_name__icontains=query) |
            Q(member__member_number__icontains=query) |
            Q(payment_reference__icontains=query) |
            Q(disbursement_reference__icontains=query)
        )
    
    # Apply filters
    if status:
        dividends = dividends.filter(status=status)
    
    if dividend_period:
        dividends = dividends.filter(dividend_period_id=dividend_period)
    
    if member:
        dividends = dividends.filter(member_id=member)
    
    if disbursement_method:
        dividends = dividends.filter(disbursement_method=disbursement_method)
    
    # Amount filters
    if min_amount:
        try:
            dividends = dividends.filter(net_dividend__gte=Decimal(min_amount))
        except (ValueError, TypeError):
            pass
    
    if max_amount:
        try:
            dividends = dividends.filter(net_dividend__lte=Decimal(max_amount))
        except (ValueError, TypeError):
            pass
    
    # Shares filters
    if min_shares:
        try:
            dividends = dividends.filter(shares_count__gte=int(min_shares))
        except (ValueError, TypeError):
            pass
    
    if max_shares:
        try:
            dividends = dividends.filter(shares_count__lte=int(max_shares))
        except (ValueError, TypeError):
            pass
    
    # Payment date filters
    if payment_date_from:
        dividends = dividends.filter(payment_date__gte=payment_date_from)
    
    if payment_date_to:
        dividends = dividends.filter(payment_date__lte=payment_date_to)
    
    # Payment reference filter
    if has_payment_reference is not None:
        if has_payment_reference.lower() == 'true':
            dividends = dividends.exclude(Q(payment_reference__isnull=True) | Q(payment_reference=''))
        else:
            dividends = dividends.filter(Q(payment_reference__isnull=True) | Q(payment_reference=''))
    
    # Paginate
    dividends_page, paginator = paginate_queryset(request, dividends, per_page=20)
    
    # Calculate stats
    total = dividends.count()
    
    aggregates = dividends.aggregate(
        total_gross=Sum('gross_dividend'),
        total_tax=Sum('tax_amount'),
        total_net=Sum('net_dividend'),
        total_shares=Sum('shares_count'),
        total_shares_value=Sum('shares_value'),
        avg_dividend=Avg('net_dividend'),
        avg_rate=Avg('applied_rate')
    )
    
    stats = {
        'total': total,
        'calculated': dividends.filter(status='CALCULATED').count(),
        'approved': dividends.filter(status='APPROVED').count(),
        'processing': dividends.filter(status='PROCESSING').count(),
        'paid': dividends.filter(status='PAID').count(),
        'failed': dividends.filter(status='FAILED').count(),
        'cancelled': dividends.filter(status='CANCELLED').count(),
        'total_gross': aggregates['total_gross'] or Decimal('0.00'),
        'total_tax': aggregates['total_tax'] or Decimal('0.00'),
        'total_net': aggregates['total_net'] or Decimal('0.00'),
        'total_shares': aggregates['total_shares'] or 0,
        'total_shares_value': aggregates['total_shares_value'] or Decimal('0.00'),
        'avg_dividend': aggregates['avg_dividend'] or Decimal('0.00'),
        'avg_rate': aggregates['avg_rate'] or Decimal('0.00'),
        'unique_members': dividends.values('member').distinct().count(),
        'unique_periods': dividends.values('dividend_period').distinct().count(),
    }
    
    # Format money in stats
    stats['total_gross_formatted'] = format_money(stats['total_gross'])
    stats['total_tax_formatted'] = format_money(stats['total_tax'])
    stats['total_net_formatted'] = format_money(stats['total_net'])
    stats['total_shares_value_formatted'] = format_money(stats['total_shares_value'])
    stats['avg_dividend_formatted'] = format_money(stats['avg_dividend'])
    
    return render(request, 'dividends/members/_dividend_results.html', {
        'dividends_page': dividends_page,
        'stats': stats,
    })


# =============================================================================
# DIVIDEND DISBURSEMENT SEARCH
# =============================================================================

def dividend_disbursement_search(request):
    """HTMX-compatible dividend disbursement search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'status', 'dividend_period', 'disbursement_method',
        'disbursement_date_from', 'disbursement_date_to',
        'min_amount', 'max_amount', 'min_members', 'max_members'
    ])
    
    query = filters['q']
    status = filters['status']
    dividend_period = filters['dividend_period']
    disbursement_method = filters['disbursement_method']
    disbursement_date_from = filters['disbursement_date_from']
    disbursement_date_to = filters['disbursement_date_to']
    min_amount = filters['min_amount']
    max_amount = filters['max_amount']
    min_members = filters['min_members']
    max_members = filters['max_members']
    
    # Build queryset
    disbursements = DividendDisbursement.objects.select_related(
        'dividend_period'
    ).annotate(
        payment_count=Count('payments', distinct=True),
        completion_rate=Case(
            When(total_members=0, then=0),
            default=F('processed_members') * 100.0 / F('total_members'),
            output_field=DecimalField(max_digits=5, decimal_places=2)
        ),
        success_rate=Case(
            When(processed_members=0, then=0),
            default=F('successful_members') * 100.0 / F('processed_members'),
            output_field=DecimalField(max_digits=5, decimal_places=2)
        )
    ).order_by('-disbursement_date', '-created_at')
    
    # Apply text search
    if query:
        disbursements = disbursements.filter(
            Q(batch_number__icontains=query) |
            Q(description__icontains=query) |
            Q(dividend_period__name__icontains=query)
        )
    
    # Apply filters
    if status:
        disbursements = disbursements.filter(status=status)
    
    if dividend_period:
        disbursements = disbursements.filter(dividend_period_id=dividend_period)
    
    if disbursement_method:
        disbursements = disbursements.filter(disbursement_method=disbursement_method)
    
    # Date filters
    if disbursement_date_from:
        disbursements = disbursements.filter(disbursement_date__gte=disbursement_date_from)
    
    if disbursement_date_to:
        disbursements = disbursements.filter(disbursement_date__lte=disbursement_date_to)
    
    # Amount filters
    if min_amount:
        try:
            disbursements = disbursements.filter(total_amount__gte=Decimal(min_amount))
        except (ValueError, TypeError):
            pass
    
    if max_amount:
        try:
            disbursements = disbursements.filter(total_amount__lte=Decimal(max_amount))
        except (ValueError, TypeError):
            pass
    
    # Member count filters
    if min_members:
        try:
            disbursements = disbursements.filter(total_members__gte=int(min_members))
        except (ValueError, TypeError):
            pass
    
    if max_members:
        try:
            disbursements = disbursements.filter(total_members__lte=int(max_members))
        except (ValueError, TypeError):
            pass
    
    # Paginate
    disbursements_page, paginator = paginate_queryset(request, disbursements, per_page=20)
    
    # Calculate stats
    total = disbursements.count()
    
    aggregates = disbursements.aggregate(
        total_amount_sum=Sum('total_amount'),
        total_processed=Sum('processed_amount'),
        total_members_sum=Sum('total_members'),
        total_successful=Sum('successful_members'),
        total_failed=Sum('failed_members'),
        avg_completion=Avg('completion_rate'),
        avg_success=Avg('success_rate')
    )
    
    stats = {
        'total': total,
        'pending': disbursements.filter(status='PENDING').count(),
        'processing': disbursements.filter(status='PROCESSING').count(),
        'completed': disbursements.filter(status='COMPLETED').count(),
        'failed': disbursements.filter(status='FAILED').count(),
        'cancelled': disbursements.filter(status='CANCELLED').count(),
        'total_amount': aggregates['total_amount_sum'] or Decimal('0.00'),
        'total_processed': aggregates['total_processed'] or Decimal('0.00'),
        'total_members': aggregates['total_members_sum'] or 0,
        'total_successful': aggregates['total_successful'] or 0,
        'total_failed': aggregates['total_failed'] or 0,
        'avg_completion': aggregates['avg_completion'] or Decimal('0.00'),
        'avg_success': aggregates['avg_success'] or Decimal('0.00'),
        'by_method': {},
    }
    
    # Group by disbursement method
    for method_choice in DividendDisbursement.DISBURSEMENT_METHOD_CHOICES:
        method_code = method_choice[0]
        method_label = method_choice[1]
        count = disbursements.filter(disbursement_method=method_code).count()
        if count > 0:
            stats['by_method'][method_label] = count
    
    # Format money in stats
    stats['total_amount_formatted'] = format_money(stats['total_amount'])
    stats['total_processed_formatted'] = format_money(stats['total_processed'])
    
    return render(request, 'dividends/disbursements/_disbursement_results.html', {
        'disbursements_page': disbursements_page,
        'stats': stats,
    })


# =============================================================================
# DIVIDEND PAYMENT SEARCH
# =============================================================================

def dividend_payment_search(request):
    """HTMX-compatible dividend payment search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'status', 'disbursement', 'member_dividend',
        'payment_date_from', 'payment_date_to',
        'min_amount', 'max_amount', 'retry_count',
        'has_transaction_id', 'has_failure_reason'
    ])
    
    query = filters['q']
    status = filters['status']
    disbursement = filters['disbursement']
    member_dividend = filters['member_dividend']
    payment_date_from = filters['payment_date_from']
    payment_date_to = filters['payment_date_to']
    min_amount = filters['min_amount']
    max_amount = filters['max_amount']
    retry_count = filters['retry_count']
    has_transaction_id = filters['has_transaction_id']
    has_failure_reason = filters['has_failure_reason']
    
    # Build queryset
    payments = DividendPayment.objects.select_related(
        'member_dividend',
        'member_dividend__member',
        'disbursement',
        'savings_account'
    ).order_by('-payment_date')
    
    # Apply text search
    if query:
        payments = payments.filter(
            Q(member_dividend__member__first_name__icontains=query) |
            Q(member_dividend__member__last_name__icontains=query) |
            Q(member_dividend__member__member_number__icontains=query) |
            Q(payment_reference__icontains=query) |
            Q(transaction_id__icontains=query) |
            Q(receipt_number__icontains=query)
        )
    
    # Apply filters
    if status:
        payments = payments.filter(status=status)
    
    if disbursement:
        payments = payments.filter(disbursement_id=disbursement)
    
    if member_dividend:
        payments = payments.filter(member_dividend_id=member_dividend)
    
    # Date filters
    if payment_date_from:
        payments = payments.filter(payment_date__gte=payment_date_from)
    
    if payment_date_to:
        payments = payments.filter(payment_date__lte=payment_date_to)
    
    # Amount filters
    if min_amount:
        try:
            payments = payments.filter(amount__gte=Decimal(min_amount))
        except (ValueError, TypeError):
            pass
    
    if max_amount:
        try:
            payments = payments.filter(amount__lte=Decimal(max_amount))
        except (ValueError, TypeError):
            pass
    
    # Retry count filter
    if retry_count:
        try:
            payments = payments.filter(retry_count__gte=int(retry_count))
        except (ValueError, TypeError):
            pass
    
    # Transaction ID filter
    if has_transaction_id is not None:
        if has_transaction_id.lower() == 'true':
            payments = payments.exclude(Q(transaction_id__isnull=True) | Q(transaction_id=''))
        else:
            payments = payments.filter(Q(transaction_id__isnull=True) | Q(transaction_id=''))
    
    # Failure reason filter
    if has_failure_reason is not None:
        if has_failure_reason.lower() == 'true':
            payments = payments.exclude(Q(failure_reason__isnull=True) | Q(failure_reason=''))
        else:
            payments = payments.filter(Q(failure_reason__isnull=True) | Q(failure_reason=''))
    
    # Paginate
    payments_page, paginator = paginate_queryset(request, payments, per_page=20)
    
    # Calculate stats
    total = payments.count()
    
    aggregates = payments.aggregate(
        total_amount=Sum('amount'),
        avg_amount=Avg('amount'),
        avg_retry=Avg('retry_count')
    )
    
    stats = {
        'total': total,
        'pending': payments.filter(status='PENDING').count(),
        'processing': payments.filter(status='PROCESSING').count(),
        'completed': payments.filter(status='COMPLETED').count(),
        'failed': payments.filter(status='FAILED').count(),
        'cancelled': payments.filter(status='CANCELLED').count(),
        'total_amount': aggregates['total_amount'] or Decimal('0.00'),
        'avg_amount': aggregates['avg_amount'] or Decimal('0.00'),
        'avg_retry': aggregates['avg_retry'] or Decimal('0.00'),
        'with_transaction_id': payments.exclude(Q(transaction_id__isnull=True) | Q(transaction_id='')).count(),
        'needs_retry': payments.filter(status='FAILED', retry_count__lt=3).count(),
        'max_retries_reached': payments.filter(status='FAILED', retry_count__gte=3).count(),
    }
    
    # Format money in stats
    stats['total_amount_formatted'] = format_money(stats['total_amount'])
    stats['avg_amount_formatted'] = format_money(stats['avg_amount'])
    
    return render(request, 'dividends/payments/_payment_results.html', {
        'payments_page': payments_page,
        'stats': stats,
    })


# =============================================================================
# DIVIDEND RATE SEARCH
# =============================================================================

def dividend_rate_search(request):
    """HTMX-compatible dividend rate search with pagination"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'dividend_period', 'is_active',
        'min_rate', 'max_rate', 'min_shares', 'max_shares'
    ])
    
    query = filters['q']
    dividend_period = filters['dividend_period']
    is_active = filters['is_active']
    min_rate = filters['min_rate']
    max_rate = filters['max_rate']
    min_shares = filters['min_shares']
    max_shares = filters['max_shares']
    
    # Build queryset
    rates = DividendRate.objects.select_related(
        'dividend_period'
    ).order_by('dividend_period', 'min_shares', 'min_value')
    
    # Apply text search
    if query:
        rates = rates.filter(
            Q(tier_name__icontains=query) |
            Q(description__icontains=query) |
            Q(dividend_period__name__icontains=query)
        )
    
    # Apply filters
    if dividend_period:
        rates = rates.filter(dividend_period_id=dividend_period)
    
    if is_active is not None:
        rates = rates.filter(is_active=(is_active.lower() == 'true'))
    
    # Rate filters
    if min_rate:
        try:
            rates = rates.filter(rate__gte=Decimal(min_rate))
        except (ValueError, TypeError):
            pass
    
    if max_rate:
        try:
            rates = rates.filter(rate__lte=Decimal(max_rate))
        except (ValueError, TypeError):
            pass
    
    # Shares filters
    if min_shares:
        try:
            rates = rates.filter(min_shares__gte=int(min_shares))
        except (ValueError, TypeError):
            pass
    
    if max_shares:
        try:
            rates = rates.filter(
                Q(max_shares__lte=int(max_shares)) | Q(max_shares__isnull=True)
            )
        except (ValueError, TypeError):
            pass
    
    # Paginate
    rates_page, paginator = paginate_queryset(request, rates, per_page=20)
    
    # Calculate stats
    stats = {
        'total': rates.count(),
        'active': rates.filter(is_active=True).count(),
        'inactive': rates.filter(is_active=False).count(),
        'avg_rate': rates.filter(is_active=True).aggregate(Avg('rate'))['rate__avg'] or Decimal('0.00'),
        'min_rate': rates.filter(is_active=True).aggregate(Min('rate'))['rate__min'] or Decimal('0.00'),
        'max_rate': rates.filter(is_active=True).aggregate(Max('rate'))['rate__max'] or Decimal('0.00'),
        'unique_periods': rates.values('dividend_period').distinct().count(),
    }
    
    return render(request, 'dividends/rates/_rate_results.html', {
        'rates_page': rates_page,
        'stats': stats,
    })


# =============================================================================
# DIVIDEND PREFERENCE SEARCH
# =============================================================================

def dividend_preference_search(request):
    """HTMX-compatible dividend preference search with pagination"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'member', 'dividend_period', 'preference_method',
        'is_default', 'has_savings_account', 'has_bank_account',
        'has_mobile_number'
    ])
    
    query = filters['q']
    member = filters['member']
    dividend_period = filters['dividend_period']
    preference_method = filters['preference_method']
    is_default = filters['is_default']
    has_savings_account = filters['has_savings_account']
    has_bank_account = filters['has_bank_account']
    has_mobile_number = filters['has_mobile_number']
    
    # Build queryset
    preferences = DividendPreference.objects.select_related(
        'member',
        'dividend_period',
        'savings_account',
        'savings_account__savings_product'
    ).order_by('-is_default', 'member__last_name', 'member__first_name')
    
    # Apply text search
    if query:
        preferences = preferences.filter(
            Q(member__first_name__icontains=query) |
            Q(member__last_name__icontains=query) |
            Q(member__member_number__icontains=query) |
            Q(bank_name__icontains=query) |
            Q(bank_account__icontains=query) |
            Q(mobile_number__icontains=query)
        )
    
    # Apply filters
    if member:
        preferences = preferences.filter(member_id=member)
    
    if dividend_period:
        preferences = preferences.filter(dividend_period_id=dividend_period)
    
    if preference_method:
        preferences = preferences.filter(preference_method=preference_method)
    
    if is_default is not None:
        preferences = preferences.filter(is_default=(is_default.lower() == 'true'))
    
    # Account filters
    if has_savings_account is not None:
        if has_savings_account.lower() == 'true':
            preferences = preferences.exclude(savings_account__isnull=True)
        else:
            preferences = preferences.filter(savings_account__isnull=True)
    
    if has_bank_account is not None:
        if has_bank_account.lower() == 'true':
            preferences = preferences.exclude(Q(bank_account__isnull=True) | Q(bank_account=''))
        else:
            preferences = preferences.filter(Q(bank_account__isnull=True) | Q(bank_account=''))
    
    if has_mobile_number is not None:
        if has_mobile_number.lower() == 'true':
            preferences = preferences.exclude(Q(mobile_number__isnull=True) | Q(mobile_number=''))
        else:
            preferences = preferences.filter(Q(mobile_number__isnull=True) | Q(mobile_number=''))
    
    # Paginate
    preferences_page, paginator = paginate_queryset(request, preferences, per_page=20)
    
    # Calculate stats
    stats = {
        'total': preferences.count(),
        'default_preferences': preferences.filter(is_default=True).count(),
        'period_specific': preferences.exclude(dividend_period__isnull=True).count(),
        'savings_account': preferences.filter(preference_method='SAVINGS_ACCOUNT').count(),
        'bank_transfer': preferences.filter(preference_method='BANK_TRANSFER').count(),
        'mobile_money': preferences.filter(preference_method='MOBILE_MONEY').count(),
        'cash': preferences.filter(preference_method='CASH').count(),
        'unique_members': preferences.values('member').distinct().count(),
    }
    
    return render(request, 'dividends/preferences/_preference_results.html', {
        'preferences_page': preferences_page,
        'stats': stats,
    })


# =============================================================================
# QUICK STATS ENDPOINTS
# =============================================================================

@require_http_methods(["GET"])
def dividend_period_quick_stats(request):
    """Get quick statistics for dividend periods"""
    
    today = timezone.now().date()
    
    aggregates = DividendPeriod.objects.aggregate(
        total_amount=Sum('total_dividend_amount'),
        total_members=Sum('total_members'),
        total_shares=Sum('total_shares'),
        avg_rate=Avg('dividend_rate')
    )
    
    stats = {
        'total_periods': DividendPeriod.objects.count(),
        'draft': DividendPeriod.objects.filter(status='DRAFT').count(),
        'active': DividendPeriod.objects.filter(status__in=['OPEN', 'CALCULATING', 'CALCULATED', 'APPROVED', 'DISBURSING']).count(),
        'completed': DividendPeriod.objects.filter(status='COMPLETED').count(),
        'total_amount': str(aggregates['total_amount'] or Decimal('0.00')),
        'total_amount_formatted': format_money(aggregates['total_amount'] or Decimal('0.00')),
        'total_members': aggregates['total_members'] or 0,
        'total_shares': aggregates['total_shares'] or 0,
        'avg_rate': str(aggregates['avg_rate'] or Decimal('0.00')),
        'awaiting_approval': DividendPeriod.objects.filter(status='CALCULATED', is_approved=False).count(),
        'pending_disbursement': DividendPeriod.objects.filter(status='APPROVED').count(),
    }
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def member_dividend_quick_stats(request):
    """Get quick statistics for member dividends"""
    
    aggregates = MemberDividend.objects.aggregate(
        total_gross=Sum('gross_dividend'),
        total_tax=Sum('tax_amount'),
        total_net=Sum('net_dividend'),
        avg_dividend=Avg('net_dividend')
    )
    
    stats = {
        'total_dividends': MemberDividend.objects.count(),
        'calculated': MemberDividend.objects.filter(status='CALCULATED').count(),
        'approved': MemberDividend.objects.filter(status='APPROVED').count(),
        'paid': MemberDividend.objects.filter(status='PAID').count(),
        'failed': MemberDividend.objects.filter(status='FAILED').count(),
        'processing': MemberDividend.objects.filter(status='PROCESSING').count(),
        'total_gross': str(aggregates['total_gross'] or Decimal('0.00')),
        'total_gross_formatted': format_money(aggregates['total_gross'] or Decimal('0.00')),
        'total_tax': str(aggregates['total_tax'] or Decimal('0.00')),
        'total_tax_formatted': format_money(aggregates['total_tax'] or Decimal('0.00')),
        'total_net': str(aggregates['total_net'] or Decimal('0.00')),
        'total_net_formatted': format_money(aggregates['total_net'] or Decimal('0.00')),
        'avg_dividend': str(aggregates['avg_dividend'] or Decimal('0.00')),
        'avg_dividend_formatted': format_money(aggregates['avg_dividend'] or Decimal('0.00')),
        'unique_members': MemberDividend.objects.values('member').distinct().count(),
    }
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def dividend_disbursement_quick_stats(request):
    """Get quick statistics for dividend disbursements"""
    
    aggregates = DividendDisbursement.objects.aggregate(
        total_amount=Sum('total_amount'),
        total_processed=Sum('processed_amount'),
        total_members=Sum('total_members'),
        total_successful=Sum('successful_members'),
        total_failed=Sum('failed_members')
    )
    
    stats = {
        'total_disbursements': DividendDisbursement.objects.count(),
        'pending': DividendDisbursement.objects.filter(status='PENDING').count(),
        'processing': DividendDisbursement.objects.filter(status='PROCESSING').count(),
        'completed': DividendDisbursement.objects.filter(status='COMPLETED').count(),
        'failed': DividendDisbursement.objects.filter(status='FAILED').count(),
        'total_amount': str(aggregates['total_amount'] or Decimal('0.00')),
        'total_amount_formatted': format_money(aggregates['total_amount'] or Decimal('0.00')),
        'total_processed': str(aggregates['total_processed'] or Decimal('0.00')),
        'total_processed_formatted': format_money(aggregates['total_processed'] or Decimal('0.00')),
        'total_members': aggregates['total_members'] or 0,
        'total_successful': aggregates['total_successful'] or 0,
        'total_failed': aggregates['total_failed'] or 0,
        'success_rate': round((aggregates['total_successful'] / aggregates['total_members'] * 100) if aggregates['total_members'] else 0, 2),
    }
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def dividend_payment_quick_stats(request):
    """Get quick statistics for dividend payments"""
    
    aggregates = DividendPayment.objects.aggregate(
        total_amount=Sum('amount'),
        avg_amount=Avg('amount'),
        avg_retry=Avg('retry_count')
    )
    
    stats = {
        'total_payments': DividendPayment.objects.count(),
        'pending': DividendPayment.objects.filter(status='PENDING').count(),
        'processing': DividendPayment.objects.filter(status='PROCESSING').count(),
        'completed': DividendPayment.objects.filter(status='COMPLETED').count(),
        'failed': DividendPayment.objects.filter(status='FAILED').count(),
        'total_amount': str(aggregates['total_amount'] or Decimal('0.00')),
        'total_amount_formatted': format_money(aggregates['total_amount'] or Decimal('0.00')),
        'avg_amount': str(aggregates['avg_amount'] or Decimal('0.00')),
        'avg_amount_formatted': format_money(aggregates['avg_amount'] or Decimal('0.00')),
        'avg_retry': round(aggregates['avg_retry'] or 0, 2),
        'needs_retry': DividendPayment.objects.filter(status='FAILED', retry_count__lt=3).count(),
        'max_retries_reached': DividendPayment.objects.filter(status='FAILED', retry_count__gte=3).count(),
    }
    
    return JsonResponse(stats)


# =============================================================================
# PERIOD-SPECIFIC STATS
# =============================================================================

@require_http_methods(["GET"])
def dividend_period_detail_stats(request, period_id):
    """Get detailed statistics for a specific dividend period"""
    
    period = get_object_or_404(DividendPeriod, id=period_id)
    
    member_dividends = period.member_dividends.all()
    
    aggregates = member_dividends.aggregate(
        total_gross=Sum('gross_dividend'),
        total_tax=Sum('tax_amount'),
        total_net=Sum('net_dividend'),
        total_shares=Sum('shares_count'),
        total_shares_value=Sum('shares_value'),
        avg_dividend=Avg('net_dividend'),
        min_dividend=Min('net_dividend'),
        max_dividend=Max('net_dividend')
    )
    
    stats = {
        'period_name': period.name,
        'period_status': period.get_status_display(),
        'total_members': member_dividends.count(),
        'calculated': member_dividends.filter(status='CALCULATED').count(),
        'approved': member_dividends.filter(status='APPROVED').count(),
        'paid': member_dividends.filter(status='PAID').count(),
        'failed': member_dividends.filter(status='FAILED').count(),
        'total_gross': str(aggregates['total_gross'] or Decimal('0.00')),
        'total_gross_formatted': format_money(aggregates['total_gross'] or Decimal('0.00')),
        'total_tax': str(aggregates['total_tax'] or Decimal('0.00')),
        'total_tax_formatted': format_money(aggregates['total_tax'] or Decimal('0.00')),
        'total_net': str(aggregates['total_net'] or Decimal('0.00')),
        'total_net_formatted': format_money(aggregates['total_net'] or Decimal('0.00')),
        'total_shares': aggregates['total_shares'] or 0,
        'total_shares_value': str(aggregates['total_shares_value'] or Decimal('0.00')),
        'total_shares_value_formatted': format_money(aggregates['total_shares_value'] or Decimal('0.00')),
        'avg_dividend': str(aggregates['avg_dividend'] or Decimal('0.00')),
        'avg_dividend_formatted': format_money(aggregates['avg_dividend'] or Decimal('0.00')),
        'min_dividend': str(aggregates['min_dividend'] or Decimal('0.00')),
        'min_dividend_formatted': format_money(aggregates['min_dividend'] or Decimal('0.00')),
        'max_dividend': str(aggregates['max_dividend'] or Decimal('0.00')),
        'max_dividend_formatted': format_money(aggregates['max_dividend'] or Decimal('0.00')),
        'disbursement_count': period.disbursements.count(),
        'payment_count': DividendPayment.objects.filter(disbursement__dividend_period=period).count(),
    }
    
    return JsonResponse(stats)