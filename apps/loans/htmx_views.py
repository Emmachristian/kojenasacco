# loans/htmx_views.py

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Count, Sum, Avg, F, DecimalField, Case, When, Max, Min
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from datetime import timedelta
from decimal import Decimal
import logging

from .models import (
    LoanProduct,
    LoanApplication,
    Loan,
    LoanPayment,
    LoanGuarantor,
    LoanCollateral,
    LoanSchedule,
    LoanDocument
)
from core.utils import parse_filters, paginate_queryset, format_money

logger = logging.getLogger(__name__)


# =============================================================================
# LOAN PRODUCT SEARCH
# =============================================================================

def loan_product_search(request):
    """HTMX-compatible loan product search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'is_active', 'interest_type', 'repayment_cycle',
        'guarantor_required', 'collateral_required', 'allow_top_up',
        'allow_early_repayment', 'min_interest_rate', 'max_interest_rate',
        'min_amount', 'max_amount', 'min_term', 'max_term'
    ])
    
    query = filters['q']
    is_active = filters['is_active']
    interest_type = filters['interest_type']
    repayment_cycle = filters['repayment_cycle']
    guarantor_required = filters['guarantor_required']
    collateral_required = filters['collateral_required']
    allow_top_up = filters['allow_top_up']
    allow_early_repayment = filters['allow_early_repayment']
    min_interest_rate = filters['min_interest_rate']
    max_interest_rate = filters['max_interest_rate']
    min_amount = filters['min_amount']
    max_amount = filters['max_amount']
    min_term = filters['min_term']
    max_term = filters['max_term']
    
    # Build queryset
    products = LoanProduct.objects.annotate(
        application_count=Count('loanapplication', distinct=True),
        active_loan_count=Count(
            'loan',
            filter=Q(loan__status='ACTIVE'),
            distinct=True
        ),
        total_disbursed=Sum(
            'loan__principal_amount',
            filter=Q(loan__status__in=['ACTIVE', 'PAID'])
        ),
        total_outstanding=Sum(
            'loan__outstanding_total',
            filter=Q(loan__status='ACTIVE')
        )
    ).order_by('-is_active', 'name')
    
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
    
    if interest_type:
        products = products.filter(interest_type=interest_type)
    
    if repayment_cycle:
        products = products.filter(repayment_cycle=repayment_cycle)
    
    if guarantor_required is not None:
        products = products.filter(guarantor_required=(guarantor_required.lower() == 'true'))
    
    if collateral_required is not None:
        products = products.filter(collateral_required=(collateral_required.lower() == 'true'))
    
    if allow_top_up is not None:
        products = products.filter(allow_top_up=(allow_top_up.lower() == 'true'))
    
    if allow_early_repayment is not None:
        products = products.filter(allow_early_repayment=(allow_early_repayment.lower() == 'true'))
    
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
    
    # Amount filters
    if min_amount:
        try:
            products = products.filter(min_amount__gte=Decimal(min_amount))
        except (ValueError, TypeError):
            pass
    
    if max_amount:
        try:
            products = products.filter(max_amount__lte=Decimal(max_amount))
        except (ValueError, TypeError):
            pass
    
    # Term filters
    if min_term:
        try:
            products = products.filter(min_term__gte=int(min_term))
        except (ValueError, TypeError):
            pass
    
    if max_term:
        try:
            products = products.filter(max_term__lte=int(max_term))
        except (ValueError, TypeError):
            pass
    
    # Paginate
    products_page, paginator = paginate_queryset(request, products, per_page=20)
    
    # Calculate stats
    total = products.count()
    
    aggregates = products.aggregate(
        total_applications=Sum('application_count'),
        total_active_loans=Sum('active_loan_count'),
        total_disbursed_sum=Sum('total_disbursed'),
        total_outstanding_sum=Sum('total_outstanding'),
        avg_interest_rate=Avg('interest_rate'),
        min_interest_rate=Min('interest_rate'),
        max_interest_rate=Max('interest_rate')
    )
    
    stats = {
        'total': total,
        'active': products.filter(is_active=True).count(),
        'inactive': products.filter(is_active=False).count(),
        'with_guarantor': products.filter(guarantor_required=True).count(),
        'with_collateral': products.filter(collateral_required=True).count(),
        'allow_top_up': products.filter(allow_top_up=True).count(),
        'total_applications': aggregates['total_applications'] or 0,
        'total_active_loans': aggregates['total_active_loans'] or 0,
        'total_disbursed': aggregates['total_disbursed_sum'] or Decimal('0.00'),
        'total_outstanding': aggregates['total_outstanding_sum'] or Decimal('0.00'),
        'avg_interest_rate': aggregates['avg_interest_rate'] or Decimal('0.00'),
        'min_interest_rate': aggregates['min_interest_rate'] or Decimal('0.00'),
        'max_interest_rate': aggregates['max_interest_rate'] or Decimal('0.00'),
    }
    
    # Format money in stats
    stats['total_disbursed_formatted'] = format_money(stats['total_disbursed'])
    stats['total_outstanding_formatted'] = format_money(stats['total_outstanding'])
    
    return render(request, 'loans/products/_product_results.html', {
        'products_page': products_page,
        'stats': stats,
    })


# =============================================================================
# LOAN APPLICATION SEARCH
# =============================================================================

def loan_application_search(request):
    """HTMX-compatible loan application search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'status', 'loan_product', 'member', 'min_amount', 'max_amount',
        'min_term', 'max_term', 'application_date_from', 'application_date_to',
        'processing_fee_paid', 'has_guarantors', 'has_collateral',
        'disbursement_method', 'financial_period'
    ])
    
    query = filters['q']
    status = filters['status']
    loan_product = filters['loan_product']
    member = filters['member']
    min_amount = filters['min_amount']
    max_amount = filters['max_amount']
    min_term = filters['min_term']
    max_term = filters['max_term']
    application_date_from = filters['application_date_from']
    application_date_to = filters['application_date_to']
    processing_fee_paid = filters['processing_fee_paid']
    has_guarantors = filters['has_guarantors']
    has_collateral = filters['has_collateral']
    disbursement_method = filters['disbursement_method']
    financial_period = filters['financial_period']
    
    # Build queryset
    applications = LoanApplication.objects.select_related(
        'member',
        'loan_product',
        'financial_period'
    ).annotate(
        guarantor_count=Count('guarantors', distinct=True),
        approved_guarantor_count=Count(
            'guarantors',
            filter=Q(guarantors__status='APPROVED'),
            distinct=True
        ),
        collateral_count=Count('collaterals', distinct=True),
        document_count=Count('documents', distinct=True)
    ).order_by('-application_date', '-created_at')
    
    # Apply text search
    if query:
        applications = applications.filter(
            Q(application_number__icontains=query) |
            Q(member__first_name__icontains=query) |
            Q(member__last_name__icontains=query) |
            Q(member__member_number__icontains=query) |
            Q(loan_product__name__icontains=query) |
            Q(purpose__icontains=query)
        )
    
    # Apply filters
    if status:
        applications = applications.filter(status=status)
    
    if loan_product:
        applications = applications.filter(loan_product_id=loan_product)
    
    if member:
        applications = applications.filter(member_id=member)
    
    if disbursement_method:
        applications = applications.filter(disbursement_method=disbursement_method)
    
    if financial_period:
        applications = applications.filter(financial_period_id=financial_period)
    
    # Amount filters
    if min_amount:
        try:
            applications = applications.filter(amount_requested__gte=Decimal(min_amount))
        except (ValueError, TypeError):
            pass
    
    if max_amount:
        try:
            applications = applications.filter(amount_requested__lte=Decimal(max_amount))
        except (ValueError, TypeError):
            pass
    
    # Term filters
    if min_term:
        try:
            applications = applications.filter(term_months__gte=int(min_term))
        except (ValueError, TypeError):
            pass
    
    if max_term:
        try:
            applications = applications.filter(term_months__lte=int(max_term))
        except (ValueError, TypeError):
            pass
    
    # Date filters
    if application_date_from:
        applications = applications.filter(application_date__gte=application_date_from)
    
    if application_date_to:
        applications = applications.filter(application_date__lte=application_date_to)
    
    # Boolean filters
    if processing_fee_paid is not None:
        applications = applications.filter(processing_fee_paid=(processing_fee_paid.lower() == 'true'))
    
    if has_guarantors is not None:
        if has_guarantors.lower() == 'true':
            applications = applications.filter(guarantor_count__gt=0)
        else:
            applications = applications.filter(guarantor_count=0)
    
    if has_collateral is not None:
        if has_collateral.lower() == 'true':
            applications = applications.filter(collateral_count__gt=0)
        else:
            applications = applications.filter(collateral_count=0)
    
    # Paginate
    applications_page, paginator = paginate_queryset(request, applications, per_page=20)
    
    # Calculate stats
    total = applications.count()
    
    aggregates = applications.aggregate(
        total_requested=Sum('amount_requested'),
        total_approved=Sum('approved_amount'),
        avg_requested=Avg('amount_requested'),
        avg_approved=Avg('approved_amount'),
        total_fees=Sum('processing_fee_amount') + Sum('insurance_fee_amount')
    )
    
    stats = {
        'total': total,
        'draft': applications.filter(status='DRAFT').count(),
        'submitted': applications.filter(status='SUBMITTED').count(),
        'under_review': applications.filter(status='UNDER_REVIEW').count(),
        'approved': applications.filter(status='APPROVED').count(),
        'rejected': applications.filter(status='REJECTED').count(),
        'cancelled': applications.filter(status='CANCELLED').count(),
        'disbursed': applications.filter(status='DISBURSED').count(),
        'total_requested': aggregates['total_requested'] or Decimal('0.00'),
        'total_approved': aggregates['total_approved'] or Decimal('0.00'),
        'avg_requested': aggregates['avg_requested'] or Decimal('0.00'),
        'avg_approved': aggregates['avg_approved'] or Decimal('0.00'),
        'total_fees': aggregates['total_fees'] or Decimal('0.00'),
        'unique_members': applications.values('member').distinct().count(),
        'unique_products': applications.values('loan_product').distinct().count(),
    }
    
    # Format money in stats
    stats['total_requested_formatted'] = format_money(stats['total_requested'])
    stats['total_approved_formatted'] = format_money(stats['total_approved'])
    stats['avg_requested_formatted'] = format_money(stats['avg_requested'])
    stats['avg_approved_formatted'] = format_money(stats['avg_approved'])
    stats['total_fees_formatted'] = format_money(stats['total_fees'])
    
    return render(request, 'loans/applications/_application_results.html', {
        'applications_page': applications_page,
        'stats': stats,
    })


# =============================================================================
# LOAN SEARCH
# =============================================================================

def loan_search(request):
    """HTMX-compatible loan search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'status', 'loan_product', 'member', 'min_principal', 'max_principal',
        'min_outstanding', 'max_outstanding', 'disbursement_date_from',
        'disbursement_date_to', 'overdue', 'fully_paid', 'days_in_arrears',
        'financial_period'
    ])
    
    query = filters['q']
    status = filters['status']
    loan_product = filters['loan_product']
    member = filters['member']
    min_principal = filters['min_principal']
    max_principal = filters['max_principal']
    min_outstanding = filters['min_outstanding']
    max_outstanding = filters['max_outstanding']
    disbursement_date_from = filters['disbursement_date_from']
    disbursement_date_to = filters['disbursement_date_to']
    overdue = filters['overdue']
    fully_paid = filters['fully_paid']
    days_in_arrears = filters['days_in_arrears']
    financial_period = filters['financial_period']
    
    # Build queryset
    loans = Loan.objects.select_related(
        'member',
        'loan_product',
        'application',
        'financial_period',
        'disbursement_method'
    ).annotate(
        payment_count=Count('payments', distinct=True),
        schedule_count=Count('schedule', distinct=True),
        overdue_installments=Count(
            'schedule',
            filter=Q(schedule__status='OVERDUE'),
            distinct=True
        )
    ).order_by('-disbursement_date', '-created_at')
    
    # Apply text search
    if query:
        loans = loans.filter(
            Q(loan_number__icontains=query) |
            Q(member__first_name__icontains=query) |
            Q(member__last_name__icontains=query) |
            Q(member__member_number__icontains=query) |
            Q(loan_product__name__icontains=query)
        )
    
    # Apply filters
    if status:
        loans = loans.filter(status=status)
    
    if loan_product:
        loans = loans.filter(loan_product_id=loan_product)
    
    if member:
        loans = loans.filter(member_id=member)
    
    if financial_period:
        loans = loans.filter(financial_period_id=financial_period)
    
    # Amount filters
    if min_principal:
        try:
            loans = loans.filter(principal_amount__gte=Decimal(min_principal))
        except (ValueError, TypeError):
            pass
    
    if max_principal:
        try:
            loans = loans.filter(principal_amount__lte=Decimal(max_principal))
        except (ValueError, TypeError):
            pass
    
    if min_outstanding:
        try:
            loans = loans.filter(outstanding_total__gte=Decimal(min_outstanding))
        except (ValueError, TypeError):
            pass
    
    if max_outstanding:
        try:
            loans = loans.filter(outstanding_total__lte=Decimal(max_outstanding))
        except (ValueError, TypeError):
            pass
    
    # Date filters
    if disbursement_date_from:
        loans = loans.filter(disbursement_date__gte=disbursement_date_from)
    
    if disbursement_date_to:
        loans = loans.filter(disbursement_date__lte=disbursement_date_to)
    
    # Special filters
    if overdue and overdue.lower() == 'true':
        loans = loans.filter(days_in_arrears__gt=0)
    
    if fully_paid and fully_paid.lower() == 'true':
        loans = loans.filter(outstanding_total=0)
    
    if days_in_arrears:
        try:
            loans = loans.filter(days_in_arrears__gte=int(days_in_arrears))
        except (ValueError, TypeError):
            pass
    
    # Paginate
    loans_page, paginator = paginate_queryset(request, loans, per_page=20)
    
    # Calculate stats
    total = loans.count()
    
    aggregates = loans.aggregate(
        total_principal=Sum('principal_amount'),
        total_disbursed=Sum('principal_amount'),
        total_payable=Sum('total_payable'),
        total_paid=Sum('total_paid'),
        total_outstanding=Sum('outstanding_total'),
        avg_principal=Avg('principal_amount'),
        avg_outstanding=Avg('outstanding_total')
    )
    
    stats = {
        'total': total,
        'active': loans.filter(status='ACTIVE').count(),
        'paid': loans.filter(status='PAID').count(),
        'defaulted': loans.filter(status='DEFAULTED').count(),
        'written_off': loans.filter(status='WRITTEN_OFF').count(),
        'restructured': loans.filter(status='RESTRUCTURED').count(),
        'overdue': loans.filter(days_in_arrears__gt=0).count(),
        'severely_overdue': loans.filter(days_in_arrears__gte=90).count(),
        'total_principal': aggregates['total_principal'] or Decimal('0.00'),
        'total_payable': aggregates['total_payable'] or Decimal('0.00'),
        'total_paid': aggregates['total_paid'] or Decimal('0.00'),
        'total_outstanding': aggregates['total_outstanding'] or Decimal('0.00'),
        'avg_principal': aggregates['avg_principal'] or Decimal('0.00'),
        'avg_outstanding': aggregates['avg_outstanding'] or Decimal('0.00'),
        'unique_members': loans.values('member').distinct().count(),
        'unique_products': loans.values('loan_product').distinct().count(),
    }
    
    # Format money in stats
    stats['total_principal_formatted'] = format_money(stats['total_principal'])
    stats['total_payable_formatted'] = format_money(stats['total_payable'])
    stats['total_paid_formatted'] = format_money(stats['total_paid'])
    stats['total_outstanding_formatted'] = format_money(stats['total_outstanding'])
    stats['avg_principal_formatted'] = format_money(stats['avg_principal'])
    stats['avg_outstanding_formatted'] = format_money(stats['avg_outstanding'])
    
    return render(request, 'loans/loans/_loan_results.html', {
        'loans_page': loans_page,
        'stats': stats,
    })


# =============================================================================
# LOAN PAYMENT SEARCH
# =============================================================================

def loan_payment_search(request):
    """HTMX-compatible loan payment search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'loan', 'member', 'payment_method', 'min_amount', 'max_amount',
        'payment_date_from', 'payment_date_to', 'is_reversed',
        'has_reference', 'financial_period'
    ])
    
    query = filters['q']
    loan = filters['loan']
    member = filters['member']
    payment_method = filters['payment_method']
    min_amount = filters['min_amount']
    max_amount = filters['max_amount']
    payment_date_from = filters['payment_date_from']
    payment_date_to = filters['payment_date_to']
    is_reversed = filters['is_reversed']
    has_reference = filters['has_reference']
    financial_period = filters['financial_period']
    
    # Build queryset
    payments = LoanPayment.objects.select_related(
        'loan',
        'loan__member',
        'loan__loan_product',
        'payment_method_ref',
        'financial_period'
    ).order_by('-payment_date', '-created_at')
    
    # Apply text search
    if query:
        payments = payments.filter(
            Q(payment_number__icontains=query) |
            Q(loan__loan_number__icontains=query) |
            Q(loan__member__first_name__icontains=query) |
            Q(loan__member__last_name__icontains=query) |
            Q(reference_number__icontains=query) |
            Q(receipt_number__icontains=query)
        )
    
    # Apply filters
    if loan:
        payments = payments.filter(loan_id=loan)
    
    if member:
        payments = payments.filter(loan__member_id=member)
    
    if payment_method:
        payments = payments.filter(payment_method=payment_method)
    
    if financial_period:
        payments = payments.filter(financial_period_id=financial_period)
    
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
    
    # Date filters
    if payment_date_from:
        payments = payments.filter(payment_date__gte=payment_date_from)
    
    if payment_date_to:
        payments = payments.filter(payment_date__lte=payment_date_to)
    
    # Boolean filters
    if is_reversed is not None:
        payments = payments.filter(is_reversed=(is_reversed.lower() == 'true'))
    
    if has_reference is not None:
        if has_reference.lower() == 'true':
            payments = payments.exclude(Q(reference_number__isnull=True) | Q(reference_number=''))
        else:
            payments = payments.filter(Q(reference_number__isnull=True) | Q(reference_number=''))
    
    # Paginate
    payments_page, paginator = paginate_queryset(request, payments, per_page=20)
    
    # Calculate stats
    total = payments.count()
    
    aggregates = payments.aggregate(
        total_amount=Sum('amount'),
        total_principal=Sum('principal_amount'),
        total_interest=Sum('interest_amount'),
        total_penalty=Sum('penalty_amount'),
        total_fees=Sum('fee_amount'),
        avg_amount=Avg('amount')
    )
    
    # Payment method breakdown
    method_counts = {}
    for method in LoanPayment.PAYMENT_METHODS:
        count = payments.filter(payment_method=method[0]).count()
        if count > 0:
            method_counts[method[1]] = count
    
    stats = {
        'total': total,
        'reversed': payments.filter(is_reversed=True).count(),
        'total_amount': aggregates['total_amount'] or Decimal('0.00'),
        'total_principal': aggregates['total_principal'] or Decimal('0.00'),
        'total_interest': aggregates['total_interest'] or Decimal('0.00'),
        'total_penalty': aggregates['total_penalty'] or Decimal('0.00'),
        'total_fees': aggregates['total_fees'] or Decimal('0.00'),
        'avg_amount': aggregates['avg_amount'] or Decimal('0.00'),
        'unique_loans': payments.values('loan').distinct().count(),
        'unique_members': payments.values('loan__member').distinct().count(),
        'method_counts': method_counts,
    }
    
    # Format money in stats
    stats['total_amount_formatted'] = format_money(stats['total_amount'])
    stats['total_principal_formatted'] = format_money(stats['total_principal'])
    stats['total_interest_formatted'] = format_money(stats['total_interest'])
    stats['total_penalty_formatted'] = format_money(stats['total_penalty'])
    stats['total_fees_formatted'] = format_money(stats['total_fees'])
    stats['avg_amount_formatted'] = format_money(stats['avg_amount'])
    
    return render(request, 'loans/payments/_payment_results.html', {
        'payments_page': payments_page,
        'stats': stats,
    })


# =============================================================================
# LOAN GUARANTOR SEARCH
# =============================================================================

def loan_guarantor_search(request):
    """HTMX-compatible loan guarantor search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'status', 'loan_application', 'guarantor', 'member',
        'min_amount', 'max_amount', 'request_date_from', 'request_date_to'
    ])
    
    query = filters['q']
    status = filters['status']
    loan_application = filters['loan_application']
    guarantor = filters['guarantor']
    member = filters['member']
    min_amount = filters['min_amount']
    max_amount = filters['max_amount']
    request_date_from = filters['request_date_from']
    request_date_to = filters['request_date_to']
    
    # Build queryset
    guarantors = LoanGuarantor.objects.select_related(
        'loan_application',
        'loan_application__member',
        'loan_application__loan_product',
        'guarantor'
    ).order_by('-request_date', '-created_at')
    
    # Apply text search
    if query:
        guarantors = guarantors.filter(
            Q(guarantor__first_name__icontains=query) |
            Q(guarantor__last_name__icontains=query) |
            Q(guarantor__member_number__icontains=query) |
            Q(loan_application__application_number__icontains=query) |
            Q(loan_application__member__first_name__icontains=query) |
            Q(loan_application__member__last_name__icontains=query) |
            Q(relationship__icontains=query)
        )
    
    # Apply filters
    if status:
        guarantors = guarantors.filter(status=status)
    
    if loan_application:
        guarantors = guarantors.filter(loan_application_id=loan_application)
    
    if guarantor:
        guarantors = guarantors.filter(guarantor_id=guarantor)
    
    if member:
        guarantors = guarantors.filter(loan_application__member_id=member)
    
    # Amount filters
    if min_amount:
        try:
            guarantors = guarantors.filter(guarantee_amount__gte=Decimal(min_amount))
        except (ValueError, TypeError):
            pass
    
    if max_amount:
        try:
            guarantors = guarantors.filter(guarantee_amount__lte=Decimal(max_amount))
        except (ValueError, TypeError):
            pass
    
    # Date filters
    if request_date_from:
        guarantors = guarantors.filter(request_date__gte=request_date_from)
    
    if request_date_to:
        guarantors = guarantors.filter(request_date__lte=request_date_to)
    
    # Paginate
    guarantors_page, paginator = paginate_queryset(request, guarantors, per_page=20)
    
    # Calculate stats
    total = guarantors.count()
    
    aggregates = guarantors.aggregate(
        total_guarantee=Sum('guarantee_amount'),
        avg_guarantee=Avg('guarantee_amount')
    )
    
    stats = {
        'total': total,
        'pending': guarantors.filter(status='PENDING').count(),
        'approved': guarantors.filter(status='APPROVED').count(),
        'rejected': guarantors.filter(status='REJECTED').count(),
        'cancelled': guarantors.filter(status='CANCELLED').count(),
        'expired': guarantors.filter(status='EXPIRED').count(),
        'total_guarantee': aggregates['total_guarantee'] or Decimal('0.00'),
        'avg_guarantee': aggregates['avg_guarantee'] or Decimal('0.00'),
        'unique_guarantors': guarantors.values('guarantor').distinct().count(),
        'unique_applicants': guarantors.values('loan_application__member').distinct().count(),
        'unique_applications': guarantors.values('loan_application').distinct().count(),
    }
    
    # Format money in stats
    stats['total_guarantee_formatted'] = format_money(stats['total_guarantee'])
    stats['avg_guarantee_formatted'] = format_money(stats['avg_guarantee'])
    
    return render(request, 'loans/guarantors/_guarantor_results.html', {
        'guarantors_page': guarantors_page,
        'stats': stats,
    })


# =============================================================================
# LOAN COLLATERAL SEARCH
# =============================================================================

def loan_collateral_search(request):
    """HTMX-compatible loan collateral search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'collateral_type', 'loan_application', 'member', 'is_verified',
        'is_insured', 'min_value', 'max_value', 'valuation_date_from',
        'valuation_date_to'
    ])
    
    query = filters['q']
    collateral_type = filters['collateral_type']
    loan_application = filters['loan_application']
    member = filters['member']
    is_verified = filters['is_verified']
    is_insured = filters['is_insured']
    min_value = filters['min_value']
    max_value = filters['max_value']
    valuation_date_from = filters['valuation_date_from']
    valuation_date_to = filters['valuation_date_to']
    
    # Build queryset
    collaterals = LoanCollateral.objects.select_related(
        'loan_application',
        'loan_application__member',
        'loan_application__loan_product'
    ).order_by('-valuation_date', '-created_at')
    
    # Apply text search
    if query:
        collaterals = collaterals.filter(
            Q(description__icontains=query) |
            Q(location__icontains=query) |
            Q(owner_name__icontains=query) |
            Q(ownership_document_number__icontains=query) |
            Q(loan_application__application_number__icontains=query) |
            Q(loan_application__member__first_name__icontains=query) |
            Q(loan_application__member__last_name__icontains=query)
        )
    
    # Apply filters
    if collateral_type:
        collaterals = collaterals.filter(collateral_type=collateral_type)
    
    if loan_application:
        collaterals = collaterals.filter(loan_application_id=loan_application)
    
    if member:
        collaterals = collaterals.filter(loan_application__member_id=member)
    
    if is_verified is not None:
        collaterals = collaterals.filter(is_verified=(is_verified.lower() == 'true'))
    
    if is_insured is not None:
        collaterals = collaterals.filter(is_insured=(is_insured.lower() == 'true'))
    
    # Value filters
    if min_value:
        try:
            collaterals = collaterals.filter(estimated_value__gte=Decimal(min_value))
        except (ValueError, TypeError):
            pass
    
    if max_value:
        try:
            collaterals = collaterals.filter(estimated_value__lte=Decimal(max_value))
        except (ValueError, TypeError):
            pass
    
    # Date filters
    if valuation_date_from:
        collaterals = collaterals.filter(valuation_date__gte=valuation_date_from)
    
    if valuation_date_to:
        collaterals = collaterals.filter(valuation_date__lte=valuation_date_to)
    
    # Paginate
    collaterals_page, paginator = paginate_queryset(request, collaterals, per_page=20)
    
    # Calculate stats
    total = collaterals.count()
    
    aggregates = collaterals.aggregate(
        total_estimated=Sum('estimated_value'),
        total_appraised=Sum('appraised_value'),
        avg_estimated=Avg('estimated_value'),
        avg_appraised=Avg('appraised_value')
    )
    
    # Type breakdown
    type_counts = {}
    for ctype in LoanCollateral.COLLATERAL_TYPES:
        count = collaterals.filter(collateral_type=ctype[0]).count()
        if count > 0:
            type_counts[ctype[1]] = count
    
    stats = {
        'total': total,
        'verified': collaterals.filter(is_verified=True).count(),
        'pending_verification': collaterals.filter(is_verified=False).count(),
        'insured': collaterals.filter(is_insured=True).count(),
        'not_insured': collaterals.filter(is_insured=False).count(),
        'total_estimated': aggregates['total_estimated'] or Decimal('0.00'),
        'total_appraised': aggregates['total_appraised'] or Decimal('0.00'),
        'avg_estimated': aggregates['avg_estimated'] or Decimal('0.00'),
        'avg_appraised': aggregates['avg_appraised'] or Decimal('0.00'),
        'unique_applications': collaterals.values('loan_application').distinct().count(),
        'type_counts': type_counts,
    }
    
    # Format money in stats
    stats['total_estimated_formatted'] = format_money(stats['total_estimated'])
    stats['total_appraised_formatted'] = format_money(stats['total_appraised'])
    stats['avg_estimated_formatted'] = format_money(stats['avg_estimated'])
    stats['avg_appraised_formatted'] = format_money(stats['avg_appraised'])
    
    return render(request, 'loans/collaterals/_collateral_results.html', {
        'collaterals_page': collaterals_page,
        'stats': stats,
    })


# =============================================================================
# LOAN SCHEDULE SEARCH
# =============================================================================

def loan_schedule_search(request):
    """HTMX-compatible loan schedule search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'status', 'loan', 'member', 'due_date_from', 'due_date_to',
        'overdue', 'paid', 'min_amount', 'max_amount', 'financial_period'
    ])
    
    query = filters['q']
    status = filters['status']
    loan = filters['loan']
    member = filters['member']
    due_date_from = filters['due_date_from']
    due_date_to = filters['due_date_to']
    overdue = filters['overdue']
    paid = filters['paid']
    min_amount = filters['min_amount']
    max_amount = filters['max_amount']
    financial_period = filters['financial_period']
    
    # Build queryset
    schedules = LoanSchedule.objects.select_related(
        'loan',
        'loan__member',
        'loan__loan_product',
        'financial_period'
    ).order_by('loan', 'installment_number')
    
    # Apply text search
    if query:
        schedules = schedules.filter(
            Q(loan__loan_number__icontains=query) |
            Q(loan__member__first_name__icontains=query) |
            Q(loan__member__last_name__icontains=query) |
            Q(loan__member__member_number__icontains=query)
        )
    
    # Apply filters
    if status:
        schedules = schedules.filter(status=status)
    
    if loan:
        schedules = schedules.filter(loan_id=loan)
    
    if member:
        schedules = schedules.filter(loan__member_id=member)
    
    if financial_period:
        schedules = schedules.filter(financial_period_id=financial_period)
    
    # Date filters
    if due_date_from:
        schedules = schedules.filter(due_date__gte=due_date_from)
    
    if due_date_to:
        schedules = schedules.filter(due_date__lte=due_date_to)
    
    # Amount filters
    if min_amount:
        try:
            schedules = schedules.filter(total_amount__gte=Decimal(min_amount))
        except (ValueError, TypeError):
            pass
    
    if max_amount:
        try:
            schedules = schedules.filter(total_amount__lte=Decimal(max_amount))
        except (ValueError, TypeError):
            pass
    
    # Special filters
    if overdue and overdue.lower() == 'true':
        schedules = schedules.filter(status='OVERDUE')
    
    if paid and paid.lower() == 'true':
        schedules = schedules.filter(status='PAID')
    
    # Paginate
    schedules_page, paginator = paginate_queryset(request, schedules, per_page=20)
    
    # Calculate stats
    total = schedules.count()
    
    aggregates = schedules.aggregate(
        total_due=Sum('total_amount'),
        total_paid=Sum('paid_amount'),
        total_balance=Sum('balance'),
        avg_installment=Avg('total_amount')
    )
    
    today = timezone.now().date()
    
    stats = {
        'total': total,
        'pending': schedules.filter(status='PENDING').count(),
        'partially_paid': schedules.filter(status='PARTIALLY_PAID').count(),
        'paid': schedules.filter(status='PAID').count(),
        'overdue': schedules.filter(status='OVERDUE').count(),
        'waived': schedules.filter(status='WAIVED').count(),
        'due_today': schedules.filter(status='PENDING', due_date=today).count(),
        'total_due': aggregates['total_due'] or Decimal('0.00'),
        'total_paid': aggregates['total_paid'] or Decimal('0.00'),
        'total_balance': aggregates['total_balance'] or Decimal('0.00'),
        'avg_installment': aggregates['avg_installment'] or Decimal('0.00'),
        'unique_loans': schedules.values('loan').distinct().count(),
    }
    
    # Format money in stats
    stats['total_due_formatted'] = format_money(stats['total_due'])
    stats['total_paid_formatted'] = format_money(stats['total_paid'])
    stats['total_balance_formatted'] = format_money(stats['total_balance'])
    stats['avg_installment_formatted'] = format_money(stats['avg_installment'])
    
    return render(request, 'loans/schedules/_schedule_results.html', {
        'schedules_page': schedules_page,
        'stats': stats,
    })


# =============================================================================
# QUICK STATS ENDPOINTS
# =============================================================================

@require_http_methods(["GET"])
def loan_product_quick_stats(request):
    """Get quick statistics for loan products"""
    
    aggregates = LoanProduct.objects.aggregate(
        total_products=Count('id'),
        active_products=Count('id', filter=Q(is_active=True)),
        total_loans=Count('loan', distinct=True),
        active_loans=Count('loan', filter=Q(loan__status='ACTIVE'), distinct=True),
        total_disbursed=Sum('loan__principal_amount', filter=Q(loan__status__in=['ACTIVE', 'PAID']))
    )
    
    stats = {
        'total_products': aggregates['total_products'] or 0,
        'active_products': aggregates['active_products'] or 0,
        'total_loans': aggregates['total_loans'] or 0,
        'active_loans': aggregates['active_loans'] or 0,
        'total_disbursed': str(aggregates['total_disbursed'] or Decimal('0.00')),
        'total_disbursed_formatted': format_money(aggregates['total_disbursed'] or Decimal('0.00')),
    }
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def loan_application_quick_stats(request):
    """Get quick statistics for loan applications"""
    
    aggregates = LoanApplication.objects.aggregate(
        total_requested=Sum('amount_requested'),
        total_approved=Sum('approved_amount')
    )
    
    stats = {
        'total_applications': LoanApplication.objects.count(),
        'pending': LoanApplication.objects.filter(status__in=['DRAFT', 'SUBMITTED', 'UNDER_REVIEW']).count(),
        'approved': LoanApplication.objects.filter(status='APPROVED').count(),
        'rejected': LoanApplication.objects.filter(status='REJECTED').count(),
        'disbursed': LoanApplication.objects.filter(status='DISBURSED').count(),
        'total_requested': str(aggregates['total_requested'] or Decimal('0.00')),
        'total_requested_formatted': format_money(aggregates['total_requested'] or Decimal('0.00')),
        'total_approved': str(aggregates['total_approved'] or Decimal('0.00')),
        'total_approved_formatted': format_money(aggregates['total_approved'] or Decimal('0.00')),
    }
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def loan_quick_stats(request):
    """Get quick statistics for loans"""
    
    aggregates = Loan.objects.aggregate(
        total_principal=Sum('principal_amount'),
        total_outstanding=Sum('outstanding_total', filter=Q(status='ACTIVE')),
        total_paid=Sum('total_paid')
    )
    
    stats = {
        'total_loans': Loan.objects.count(),
        'active': Loan.objects.filter(status='ACTIVE').count(),
        'paid': Loan.objects.filter(status='PAID').count(),
        'defaulted': Loan.objects.filter(status='DEFAULTED').count(),
        'overdue': Loan.objects.filter(days_in_arrears__gt=0).count(),
        'severely_overdue': Loan.objects.filter(days_in_arrears__gte=90).count(),
        'total_principal': str(aggregates['total_principal'] or Decimal('0.00')),
        'total_principal_formatted': format_money(aggregates['total_principal'] or Decimal('0.00')),
        'total_outstanding': str(aggregates['total_outstanding'] or Decimal('0.00')),
        'total_outstanding_formatted': format_money(aggregates['total_outstanding'] or Decimal('0.00')),
        'total_paid': str(aggregates['total_paid'] or Decimal('0.00')),
        'total_paid_formatted': format_money(aggregates['total_paid'] or Decimal('0.00')),
    }
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def loan_payment_quick_stats(request):
    """Get quick statistics for loan payments"""
    
    today = timezone.now().date()
    
    today_payments = LoanPayment.objects.filter(
        payment_date__date=today,
        is_reversed=False
    )
    
    today_aggregates = today_payments.aggregate(
        total_amount=Sum('amount'),
        count=Count('id')
    )
    
    overall_aggregates = LoanPayment.objects.filter(is_reversed=False).aggregate(
        total_amount=Sum('amount')
    )
    
    stats = {
        'total_payments': LoanPayment.objects.count(),
        'today_count': today_aggregates['count'] or 0,
        'today_amount': str(today_aggregates['total_amount'] or Decimal('0.00')),
        'today_amount_formatted': format_money(today_aggregates['total_amount'] or Decimal('0.00')),
        'total_amount': str(overall_aggregates['total_amount'] or Decimal('0.00')),
        'total_amount_formatted': format_money(overall_aggregates['total_amount'] or Decimal('0.00')),
        'reversed': LoanPayment.objects.filter(is_reversed=True).count(),
    }
    
    return JsonResponse(stats)


# =============================================================================
# LOAN-SPECIFIC STATS
# =============================================================================

@require_http_methods(["GET"])
def loan_detail_stats(request, loan_id):
    """Get detailed statistics for a specific loan"""
    
    loan = get_object_or_404(Loan, id=loan_id)
    
    payments = loan.payments.filter(is_reversed=False)
    
    aggregates = payments.aggregate(
        total_payments=Sum('amount'),
        payment_count=Count('id')
    )
    
    schedule_stats = loan.schedule.aggregate(
        total_installments=Count('id'),
        paid_installments=Count('id', filter=Q(status='PAID')),
        overdue_installments=Count('id', filter=Q(status='OVERDUE'))
    )
    
    stats = {
        'loan_number': loan.loan_number,
        'loan_status': loan.get_status_display(),
        'principal_amount': str(loan.principal_amount),
        'principal_amount_formatted': format_money(loan.principal_amount),
        'outstanding_total': str(loan.outstanding_total),
        'outstanding_total_formatted': format_money(loan.outstanding_total),
        'total_paid': str(loan.total_paid),
        'total_paid_formatted': format_money(loan.total_paid),
        'payment_progress': float(loan.payment_progress_percentage),
        'days_in_arrears': loan.days_in_arrears,
        'payment_count': aggregates['payment_count'] or 0,
        'total_installments': schedule_stats['total_installments'] or 0,
        'paid_installments': schedule_stats['paid_installments'] or 0,
        'overdue_installments': schedule_stats['overdue_installments'] or 0,
        'guarantor_count': loan.application.guarantors.filter(status='APPROVED').count() if loan.application else 0,
        'collateral_count': loan.application.collaterals.count() if loan.application else 0,
    }
    
    return JsonResponse(stats)