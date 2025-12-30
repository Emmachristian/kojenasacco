# loans/stats.py

"""
Comprehensive statistics utility functions for Loans models.
Provides detailed analytics for loan products, applications, active loans,
payments, guarantors, collateral, schedules, and documents.
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
# LOAN PRODUCT STATISTICS
# =============================================================================

def get_product_statistics(filters=None):
    """
    Get comprehensive loan product statistics
    
    Args:
        filters (dict): Optional filters
            - is_active: Filter by active status
            - interest_type: Filter by interest type
            - requires_guarantor: Filter by guarantor requirement
            - requires_collateral: Filter by collateral requirement
    
    Returns:
        dict: Product statistics
    """
    from .models import LoanProduct, LoanApplication, Loan
    
    products = LoanProduct.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('is_active') is not None:
            products = products.filter(is_active=filters['is_active'])
        if filters.get('interest_type'):
            products = products.filter(interest_type=filters['interest_type'])
        if filters.get('requires_guarantor') is not None:
            products = products.filter(guarantor_required=filters['requires_guarantor'])
        if filters.get('requires_collateral') is not None:
            products = products.filter(collateral_required=filters['requires_collateral'])
    
    total_products = products.count()
    
    stats = {
        'total_products': total_products,
        'active_products': products.filter(is_active=True).count(),
        'inactive_products': products.filter(is_active=False).count(),
    }
    
    # Product requirements
    stats['requirements'] = {
        'requires_guarantor': products.filter(guarantor_required=True).count(),
        'requires_collateral': products.filter(collateral_required=True).count(),
        'requires_approval': products.filter(requires_approval=True).count(),
        'allows_top_up': products.filter(allow_top_up=True).count(),
        'allows_early_repayment': products.filter(allow_early_repayment=True).count(),
    }
    
    # Interest type distribution
    interest_types = products.values('interest_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    stats['interest_types'] = [
        {
            'type': item['interest_type'],
            'count': item['count'],
            'percentage': round((item['count'] / total_products * 100) if total_products > 0 else 0, 2)
        }
        for item in interest_types
    ]
    
    # Interest rates analysis
    interest_stats = products.aggregate(
        avg_rate=Avg('interest_rate'),
        max_rate=Max('interest_rate'),
        min_rate=Min('interest_rate'),
        avg_penalty=Avg('penalty_rate'),
    )
    
    stats['interest_rates'] = {
        'average': float(interest_stats['avg_rate'] or 0),
        'maximum': float(interest_stats['max_rate'] or 0),
        'minimum': float(interest_stats['min_rate'] or 0),
        'avg_penalty_rate': float(interest_stats['avg_penalty'] or 0),
    }
    
    # Loan amount ranges
    amount_stats = products.aggregate(
        avg_min_amount=Avg('min_amount'),
        avg_max_amount=Avg('max_amount'),
        highest_max_amount=Max('max_amount'),
        lowest_min_amount=Min('min_amount'),
    )
    
    stats['loan_amounts'] = {
        'avg_minimum': float(amount_stats['avg_min_amount'] or 0),
        'avg_maximum': float(amount_stats['avg_max_amount'] or 0),
        'highest_maximum': float(amount_stats['highest_max_amount'] or 0),
        'lowest_minimum': float(amount_stats['lowest_min_amount'] or 0),
    }
    
    # Term ranges
    term_stats = products.aggregate(
        avg_min_term=Avg('min_term'),
        avg_max_term=Avg('max_term'),
        longest_max_term=Max('max_term'),
        shortest_min_term=Min('min_term'),
    )
    
    stats['loan_terms'] = {
        'avg_minimum_months': round(float(term_stats['avg_min_term'] or 0), 0),
        'avg_maximum_months': round(float(term_stats['avg_max_term'] or 0), 0),
        'longest_term_months': term_stats['longest_max_term'] or 0,
        'shortest_term_months': term_stats['shortest_min_term'] or 0,
    }
    
    # Fee structure analysis
    fee_stats = products.aggregate(
        avg_processing_fee=Avg('loan_processing_fee'),
        avg_insurance_fee=Avg('insurance_fee'),
        avg_early_repayment_fee=Avg('early_repayment_fee'),
    )
    
    stats['fees'] = {
        'avg_processing_fee_pct': float(fee_stats['avg_processing_fee'] or 0),
        'avg_insurance_fee_pct': float(fee_stats['avg_insurance_fee'] or 0),
        'avg_early_repayment_fee_pct': float(fee_stats['avg_early_repayment_fee'] or 0),
    }
    
    # Products with fees
    stats['products_with_fees'] = {
        'processing_fees': products.filter(loan_processing_fee__gt=0).count(),
        'insurance_fees': products.filter(insurance_fee__gt=0).count(),
        'early_repayment_penalties': products.filter(early_repayment_fee__gt=0).count(),
    }
    
    # Repayment cycle distribution
    repayment_cycles = products.values('repayment_cycle').annotate(
        count=Count('id')
    ).order_by('-count')
    
    stats['repayment_cycles'] = [
        {
            'cycle': item['repayment_cycle'],
            'count': item['count'],
        }
        for item in repayment_cycles
    ]
    
    # Product usage - applications and loans per product
    product_usage = products.annotate(
        application_count=Count('loanapplication'),
        approved_applications=Count('loanapplication', filter=Q(loanapplication__status='APPROVED')),
        active_loans=Count('loan', filter=Q(loan__status='ACTIVE')),
        total_disbursed=Sum('loan__principal_amount', filter=Q(loan__status__in=['ACTIVE', 'PAID'])),
        total_outstanding=Sum('loan__outstanding_total', filter=Q(loan__status='ACTIVE')),
    ).order_by('-active_loans')
    
    stats['top_products_by_usage'] = [
        {
            'product_id': str(prod.id),
            'name': prod.name,
            'code': prod.code,
            'applications': prod.application_count or 0,
            'approved_applications': prod.approved_applications or 0,
            'active_loans': prod.active_loans or 0,
            'total_disbursed': float(prod.total_disbursed or 0),
            'total_outstanding': float(prod.total_outstanding or 0),
            'interest_rate': float(prod.interest_rate),
        }
        for prod in product_usage[:10]
    ]
    
    # Minimum savings requirements
    savings_requirements = products.values('minimum_savings_percentage').annotate(
        count=Count('id')
    ).order_by('minimum_savings_percentage')
    
    stats['savings_requirements'] = [
        {
            'percentage': float(item['minimum_savings_percentage']),
            'product_count': item['count'],
        }
        for item in savings_requirements
    ]
    
    # Guarantor requirements
    guarantor_distribution = products.filter(
        guarantor_required=True
    ).values('number_of_guarantors').annotate(
        count=Count('id')
    ).order_by('number_of_guarantors')
    
    stats['guarantor_requirements'] = [
        {
            'number_of_guarantors': item['number_of_guarantors'],
            'product_count': item['count'],
        }
        for item in guarantor_distribution
    ]
    
    # Product health score
    # Healthy products are active, have loans, and have GL integration
    healthy_products = products.filter(
        is_active=True,
        gl_account_code__isnull=False
    ).exclude(gl_account_code='').annotate(
        loan_count=Count('loan')
    ).filter(loan_count__gt=0)
    
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
    Get detailed performance breakdown for loan products
    
    Args:
        product_id: Optional specific product ID
    
    Returns:
        dict: Product performance breakdown
    """
    from .models import LoanProduct, LoanApplication, Loan, LoanPayment
    
    if product_id:
        products = LoanProduct.objects.filter(id=product_id)
    else:
        products = LoanProduct.objects.filter(is_active=True)
    
    breakdown = []
    
    for product in products:
        # Application statistics
        applications = LoanApplication.objects.filter(loan_product=product)
        
        app_stats = applications.aggregate(
            total_count=Count('id'),
            draft=Count('id', filter=Q(status='DRAFT')),
            submitted=Count('id', filter=Q(status='SUBMITTED')),
            under_review=Count('id', filter=Q(status='UNDER_REVIEW')),
            approved=Count('id', filter=Q(status='APPROVED')),
            rejected=Count('id', filter=Q(status='REJECTED')),
            cancelled=Count('id', filter=Q(status='CANCELLED')),
            disbursed=Count('id', filter=Q(status='DISBURSED')),
            total_requested=Sum('amount_requested'),
            total_approved_amount=Sum('approved_amount', filter=Q(status='APPROVED')),
        )
        
        # Loan statistics
        loans = Loan.objects.filter(loan_product=product)
        
        loan_stats = loans.aggregate(
            total_loans=Count('id'),
            active_loans=Count('id', filter=Q(status='ACTIVE')),
            paid_loans=Count('id', filter=Q(status='PAID')),
            defaulted_loans=Count('id', filter=Q(status='DEFAULTED')),
            total_principal_disbursed=Sum('principal_amount'),
            total_outstanding=Sum('outstanding_total', filter=Q(status='ACTIVE')),
            total_collected=Sum('total_paid'),
            avg_loan_amount=Avg('principal_amount'),
            avg_term_months=Avg('term_months'),
        )
        
        # Payment statistics
        payments = LoanPayment.objects.filter(
            loan__loan_product=product,
            is_reversed=False
        )
        
        payment_stats = payments.aggregate(
            total_payments=Count('id'),
            total_amount_paid=Sum('amount'),
            principal_collected=Sum('principal_amount'),
            interest_collected=Sum('interest_amount'),
            penalties_collected=Sum('penalty_amount'),
            fees_collected=Sum('fee_amount'),
        )
        
        # Arrears analysis
        overdue_loans = loans.filter(status='ACTIVE', days_in_arrears__gt=0)
        arrears_stats = overdue_loans.aggregate(
            overdue_count=Count('id'),
            total_overdue_amount=Sum('outstanding_total'),
            avg_days_overdue=Avg('days_in_arrears'),
            max_days_overdue=Max('days_in_arrears'),
        )
        
        # Calculate ratios
        total_apps = app_stats['total_count'] or 0
        approval_rate = (app_stats['approved'] / total_apps * 100) if total_apps > 0 else 0
        rejection_rate = (app_stats['rejected'] / total_apps * 100) if total_apps > 0 else 0
        
        total_loans = loan_stats['total_loans'] or 0
        default_rate = (loan_stats['defaulted_loans'] / total_loans * 100) if total_loans > 0 else 0
        
        active_loans = loan_stats['active_loans'] or 0
        overdue_rate = (arrears_stats['overdue_count'] / active_loans * 100) if active_loans > 0 else 0
        
        # Portfolio quality
        par_30 = overdue_loans.filter(days_in_arrears__gte=30).count()
        par_90 = overdue_loans.filter(days_in_arrears__gte=90).count()
        
        par_30_rate = (par_30 / active_loans * 100) if active_loans > 0 else 0
        par_90_rate = (par_90 / active_loans * 100) if active_loans > 0 else 0
        
        breakdown.append({
            'product_id': str(product.id),
            'product_name': product.name,
            'product_code': product.code,
            'interest_rate': float(product.interest_rate),
            'interest_type': product.interest_type,
            'applications': {
                'total': total_apps,
                'draft': app_stats['draft'] or 0,
                'submitted': app_stats['submitted'] or 0,
                'under_review': app_stats['under_review'] or 0,
                'approved': app_stats['approved'] or 0,
                'rejected': app_stats['rejected'] or 0,
                'cancelled': app_stats['cancelled'] or 0,
                'disbursed': app_stats['disbursed'] or 0,
                'total_requested': float(app_stats['total_requested'] or 0),
                'total_approved': float(app_stats['total_approved_amount'] or 0),
                'approval_rate': round(approval_rate, 2),
                'rejection_rate': round(rejection_rate, 2),
            },
            'loans': {
                'total': total_loans,
                'active': active_loans,
                'paid': loan_stats['paid_loans'] or 0,
                'defaulted': loan_stats['defaulted_loans'] or 0,
                'total_principal_disbursed': float(loan_stats['total_principal_disbursed'] or 0),
                'total_outstanding': float(loan_stats['total_outstanding'] or 0),
                'total_collected': float(loan_stats['total_collected'] or 0),
                'avg_loan_amount': float(loan_stats['avg_loan_amount'] or 0),
                'avg_term_months': round(float(loan_stats['avg_term_months'] or 0), 1),
                'default_rate': round(default_rate, 2),
            },
            'payments': {
                'total_payments': payment_stats['total_payments'] or 0,
                'total_amount': float(payment_stats['total_amount_paid'] or 0),
                'principal_collected': float(payment_stats['principal_collected'] or 0),
                'interest_collected': float(payment_stats['interest_collected'] or 0),
                'penalties_collected': float(payment_stats['penalties_collected'] or 0),
                'fees_collected': float(payment_stats['fees_collected'] or 0),
            },
            'arrears': {
                'overdue_loans': arrears_stats['overdue_count'] or 0,
                'total_overdue_amount': float(arrears_stats['total_overdue_amount'] or 0),
                'avg_days_overdue': round(float(arrears_stats['avg_days_overdue'] or 0), 1),
                'max_days_overdue': arrears_stats['max_days_overdue'] or 0,
                'overdue_rate': round(overdue_rate, 2),
            },
            'portfolio_quality': {
                'par_30_count': par_30,
                'par_90_count': par_90,
                'par_30_rate': round(par_30_rate, 2),
                'par_90_rate': round(par_90_rate, 2),
            },
        })
    
    return {
        'products_analyzed': len(breakdown),
        'breakdown': breakdown,
    }


# =============================================================================
# LOAN APPLICATION STATISTICS
# =============================================================================

def get_application_statistics(filters=None):
    """
    Get comprehensive loan application statistics
    
    Args:
        filters (dict): Optional filters
            - status: Filter by application status
            - product_id: Filter by specific product
            - member_id: Filter by specific member
            - date_from: Filter applications from date
            - date_to: Filter applications to date
    
    Returns:
        dict: Application statistics
    """
    from .models import LoanApplication
    
    applications = LoanApplication.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('status'):
            applications = applications.filter(status=filters['status'])
        if filters.get('product_id'):
            applications = applications.filter(loan_product_id=filters['product_id'])
        if filters.get('member_id'):
            applications = applications.filter(member_id=filters['member_id'])
        if filters.get('date_from'):
            applications = applications.filter(application_date__gte=filters['date_from'])
        if filters.get('date_to'):
            applications = applications.filter(application_date__lte=filters['date_to'])
    
    total_applications = applications.count()
    
    stats = {
        'total_applications': total_applications,
    }
    
    # Status breakdown
    status_breakdown = applications.values('status').annotate(
        count=Count('id'),
        total_amount=Sum('amount_requested'),
    ).order_by('-count')
    
    stats['by_status'] = [
        {
            'status': item['status'],
            'count': item['count'],
            'total_amount': float(item['total_amount'] or 0),
            'percentage': round((item['count'] / total_applications * 100) if total_applications > 0 else 0, 2),
        }
        for item in status_breakdown
    ]
    
    # Amount statistics
    amount_stats = applications.aggregate(
        total_requested=Sum('amount_requested'),
        avg_requested=Avg('amount_requested'),
        max_requested=Max('amount_requested'),
        min_requested=Min('amount_requested'),
        total_approved=Sum('approved_amount', filter=Q(status='APPROVED')),
        avg_approved=Avg('approved_amount', filter=Q(status='APPROVED')),
    )
    
    stats['amounts'] = {
        'total_requested': float(amount_stats['total_requested'] or 0),
        'average_requested': float(amount_stats['avg_requested'] or 0),
        'largest_request': float(amount_stats['max_requested'] or 0),
        'smallest_request': float(amount_stats['min_requested'] or 0),
        'total_approved': float(amount_stats['total_approved'] or 0),
        'average_approved': float(amount_stats['avg_approved'] or 0),
    }
    
    # Term statistics
    term_stats = applications.aggregate(
        avg_term=Avg('term_months'),
        max_term=Max('term_months'),
        min_term=Min('term_months'),
        avg_approved_term=Avg('approved_term', filter=Q(status='APPROVED')),
    )
    
    stats['terms'] = {
        'avg_requested_months': round(float(term_stats['avg_term'] or 0), 1),
        'longest_requested_months': term_stats['max_term'] or 0,
        'shortest_requested_months': term_stats['min_term'] or 0,
        'avg_approved_months': round(float(term_stats['avg_approved_term'] or 0), 1),
    }
    
    # Fee statistics
    fee_stats = applications.aggregate(
        total_processing_fees=Sum('processing_fee_amount'),
        total_insurance_fees=Sum('insurance_fee_amount'),
        fees_paid=Count('id', filter=Q(processing_fee_paid=True)),
    )
    
    stats['fees'] = {
        'total_processing_fees': float(fee_stats['total_processing_fees'] or 0),
        'total_insurance_fees': float(fee_stats['total_insurance_fees'] or 0),
        'applications_with_fees_paid': fee_stats['fees_paid'] or 0,
        'fees_paid_rate': round(
            (fee_stats['fees_paid'] / total_applications * 100) if total_applications > 0 else 0,
            2
        ),
    }
    
    # Approval metrics
    approved = applications.filter(status='APPROVED')
    rejected = applications.filter(status='REJECTED')
    pending = applications.filter(status__in=['DRAFT', 'SUBMITTED', 'UNDER_REVIEW'])
    
    stats['approval_metrics'] = {
        'approved_count': approved.count(),
        'rejected_count': rejected.count(),
        'pending_count': pending.count(),
        'approval_rate': round(
            (approved.count() / total_applications * 100) if total_applications > 0 else 0,
            2
        ),
        'rejection_rate': round(
            (rejected.count() / total_applications * 100) if total_applications > 0 else 0,
            2
        ),
    }
    
    # Disbursement method breakdown
    disbursement_methods = applications.filter(
        status='DISBURSED',
        disbursement_method__isnull=False
    ).values('disbursement_method').annotate(
        count=Count('id')
    ).order_by('-count')
    
    stats['disbursement_methods'] = [
        {
            'method': item['disbursement_method'],
            'count': item['count'],
        }
        for item in disbursement_methods
    ]
    
    # Processing time analysis (for approved applications)
    approved_apps = applications.filter(
        status='APPROVED',
        submission_date__isnull=False,
        approval_date__isnull=False
    )
    
    if approved_apps.exists():
        processing_times = []
        for app in approved_apps:
            days = (app.approval_date.date() - app.submission_date).days
            processing_times.append(days)
        
        if processing_times:
            stats['processing_time'] = {
                'avg_days': round(sum(processing_times) / len(processing_times), 1),
                'max_days': max(processing_times),
                'min_days': min(processing_times),
            }
    
    # Recent activity
    today = timezone.now().date()
    stats['recent_activity'] = {
        'submitted_last_7_days': applications.filter(
            application_date__gte=today - timedelta(days=7)
        ).count(),
        'submitted_last_30_days': applications.filter(
            application_date__gte=today - timedelta(days=30)
        ).count(),
        'approved_last_7_days': applications.filter(
            status='APPROVED',
            approval_date__gte=timezone.now() - timedelta(days=7)
        ).count(),
        'approved_last_30_days': applications.filter(
            status='APPROVED',
            approval_date__gte=timezone.now() - timedelta(days=30)
        ).count(),
    }
    
    # Top applicants by amount
    top_applications = applications.order_by('-amount_requested')[:10]
    
    stats['top_applications'] = [
        {
            'application_number': app.application_number,
            'member_name': app.member.get_full_name(),
            'product_name': app.loan_product.name,
            'amount_requested': float(app.amount_requested),
            'status': app.status,
        }
        for app in top_applications
    ]
    
    return stats


# =============================================================================
# ACTIVE LOAN STATISTICS
# =============================================================================

def get_loan_statistics(filters=None):
    """
    Get comprehensive active loan statistics
    
    Args:
        filters (dict): Optional filters
            - status: Filter by loan status
            - product_id: Filter by specific product
            - member_id: Filter by specific member
            - date_from: Filter loans disbursed from date
            - date_to: Filter loans disbursed to date
            - is_overdue: Filter overdue loans
    
    Returns:
        dict: Loan statistics
    """
    from .models import Loan
    
    loans = Loan.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('status'):
            loans = loans.filter(status=filters['status'])
        if filters.get('product_id'):
            loans = loans.filter(loan_product_id=filters['product_id'])
        if filters.get('member_id'):
            loans = loans.filter(member_id=filters['member_id'])
        if filters.get('date_from'):
            loans = loans.filter(disbursement_date__gte=filters['date_from'])
        if filters.get('date_to'):
            loans = loans.filter(disbursement_date__lte=filters['date_to'])
        if filters.get('is_overdue') is not None:
            if filters['is_overdue']:
                loans = loans.filter(days_in_arrears__gt=0)
            else:
                loans = loans.filter(days_in_arrears=0)
    
    total_loans = loans.count()
    
    stats = {
        'total_loans': total_loans,
    }
    
    # Status breakdown
    status_breakdown = loans.values('status').annotate(
        count=Count('id'),
        total_principal=Sum('principal_amount'),
        total_outstanding=Sum('outstanding_total'),
    ).order_by('-count')
    
    stats['by_status'] = [
        {
            'status': item['status'],
            'count': item['count'],
            'total_principal': float(item['total_principal'] or 0),
            'total_outstanding': float(item['total_outstanding'] or 0),
            'percentage': round((item['count'] / total_loans * 100) if total_loans > 0 else 0, 2),
        }
        for item in status_breakdown
    ]
    
    # Principal statistics
    principal_stats = loans.aggregate(
        total_principal=Sum('principal_amount'),
        avg_principal=Avg('principal_amount'),
        max_principal=Max('principal_amount'),
        min_principal=Min('principal_amount'),
    )
    
    stats['principal'] = {
        'total_disbursed': float(principal_stats['total_principal'] or 0),
        'average_loan': float(principal_stats['avg_principal'] or 0),
        'largest_loan': float(principal_stats['max_principal'] or 0),
        'smallest_loan': float(principal_stats['min_principal'] or 0),
    }
    
    # Outstanding balances
    outstanding_stats = loans.filter(status='ACTIVE').aggregate(
        total_outstanding=Sum('outstanding_total'),
        outstanding_principal=Sum('outstanding_principal'),
        outstanding_interest=Sum('outstanding_interest'),
        outstanding_penalties=Sum('outstanding_penalties'),
        outstanding_fees=Sum('outstanding_fees'),
    )
    
    stats['outstanding'] = {
        'total': float(outstanding_stats['total_outstanding'] or 0),
        'principal': float(outstanding_stats['outstanding_principal'] or 0),
        'interest': float(outstanding_stats['outstanding_interest'] or 0),
        'penalties': float(outstanding_stats['outstanding_penalties'] or 0),
        'fees': float(outstanding_stats['outstanding_fees'] or 0),
    }
    
    # Payment statistics
    payment_stats = loans.aggregate(
        total_paid=Sum('total_paid'),
        total_paid_principal=Sum('total_paid_principal'),
        total_paid_interest=Sum('total_paid_interest'),
        total_paid_penalties=Sum('total_paid_penalties'),
        total_paid_fees=Sum('total_paid_fees'),
    )
    
    stats['payments'] = {
        'total_collected': float(payment_stats['total_paid'] or 0),
        'principal_collected': float(payment_stats['total_paid_principal'] or 0),
        'interest_collected': float(payment_stats['total_paid_interest'] or 0),
        'penalties_collected': float(payment_stats['total_paid_penalties'] or 0),
        'fees_collected': float(payment_stats['total_paid_fees'] or 0),
    }
    
    # Interest statistics
    interest_stats = loans.aggregate(
        total_interest_charged=Sum('total_interest'),
        avg_interest_rate=Avg('interest_rate'),
        max_interest_rate=Max('interest_rate'),
        min_interest_rate=Min('interest_rate'),
    )
    
    stats['interest'] = {
        'total_interest_charged': float(interest_stats['total_interest_charged'] or 0),
        'average_rate': float(interest_stats['avg_interest_rate'] or 0),
        'highest_rate': float(interest_stats['max_interest_rate'] or 0),
        'lowest_rate': float(interest_stats['min_interest_rate'] or 0),
    }
    
    # Arrears analysis
    active_loans = loans.filter(status='ACTIVE')
    overdue_loans = active_loans.filter(days_in_arrears__gt=0)
    
    arrears_stats = overdue_loans.aggregate(
        total_overdue_amount=Sum('outstanding_total'),
        avg_days_overdue=Avg('days_in_arrears'),
        max_days_overdue=Max('days_in_arrears'),
    )
    
    # Portfolio at Risk (PAR) calculations
    par_30 = overdue_loans.filter(days_in_arrears__gte=30)
    par_60 = overdue_loans.filter(days_in_arrears__gte=60)
    par_90 = overdue_loans.filter(days_in_arrears__gte=90)
    
    par_30_amount = par_30.aggregate(total=Sum('outstanding_total'))['total'] or 0
    par_60_amount = par_60.aggregate(total=Sum('outstanding_total'))['total'] or 0
    par_90_amount = par_90.aggregate(total=Sum('outstanding_total'))['total'] or 0
    
    total_portfolio = float(outstanding_stats['total_outstanding'] or 0)
    
    stats['arrears'] = {
        'overdue_loans': overdue_loans.count(),
        'total_overdue_amount': float(arrears_stats['total_overdue_amount'] or 0),
        'avg_days_overdue': round(float(arrears_stats['avg_days_overdue'] or 0), 1),
        'max_days_overdue': arrears_stats['max_days_overdue'] or 0,
        'overdue_rate': round(
            (overdue_loans.count() / active_loans.count() * 100) if active_loans.count() > 0 else 0,
            2
        ),
    }
    
    stats['portfolio_at_risk'] = {
        'par_30_count': par_30.count(),
        'par_60_count': par_60.count(),
        'par_90_count': par_90.count(),
        'par_30_amount': float(par_30_amount),
        'par_60_amount': float(par_60_amount),
        'par_90_amount': float(par_90_amount),
        'par_30_rate': round((float(par_30_amount) / total_portfolio * 100) if total_portfolio > 0 else 0, 2),
        'par_60_rate': round((float(par_60_amount) / total_portfolio * 100) if total_portfolio > 0 else 0, 2),
        'par_90_rate': round((float(par_90_amount) / total_portfolio * 100) if total_portfolio > 0 else 0, 2),
    }
    
    # Term analysis
    term_stats = loans.aggregate(
        avg_term=Avg('term_months'),
        max_term=Max('term_months'),
        min_term=Min('term_months'),
    )
    
    stats['terms'] = {
        'average_months': round(float(term_stats['avg_term'] or 0), 1),
        'longest_term_months': term_stats['max_term'] or 0,
        'shortest_term_months': term_stats['min_term'] or 0,
    }
    
    # Loan age distribution
    today = timezone.now().date()
    age_ranges = {
        'under_3_months': loans.filter(
            disbursement_date__gte=today - timedelta(days=90)
        ).count(),
        '3_6_months': loans.filter(
            disbursement_date__gte=today - timedelta(days=180),
            disbursement_date__lt=today - timedelta(days=90)
        ).count(),
        '6_12_months': loans.filter(
            disbursement_date__gte=today - timedelta(days=365),
            disbursement_date__lt=today - timedelta(days=180)
        ).count(),
        'over_12_months': loans.filter(
            disbursement_date__lt=today - timedelta(days=365)
        ).count(),
    }
    
    stats['loan_age_distribution'] = age_ranges
    
    # Repayment performance
    paid_loans = loans.filter(status='PAID')
    if paid_loans.exists():
        early_repayments = 0
        on_time = 0
        late = 0
        
        for loan in paid_loans:
            if loan.actual_end_date:
                if loan.actual_end_date < loan.expected_end_date:
                    early_repayments += 1
                elif loan.actual_end_date == loan.expected_end_date:
                    on_time += 1
                else:
                    late += 1
        
        stats['repayment_performance'] = {
            'early_repayments': early_repayments,
            'on_time_repayments': on_time,
            'late_repayments': late,
            'early_repayment_rate': round(
                (early_repayments / paid_loans.count() * 100) if paid_loans.count() > 0 else 0,
                2
            ),
        }
    
    # Recent activity
    stats['recent_activity'] = {
        'disbursed_last_7_days': loans.filter(
            disbursement_date__gte=today - timedelta(days=7)
        ).count(),
        'disbursed_last_30_days': loans.filter(
            disbursement_date__gte=today - timedelta(days=30)
        ).count(),
        'paid_off_last_30_days': loans.filter(
            status='PAID',
            actual_end_date__gte=today - timedelta(days=30)
        ).count(),
    }
    
    # Top loans by outstanding amount
    top_loans = active_loans.order_by('-outstanding_total')[:10]
    
    stats['top_loans_by_outstanding'] = [
        {
            'loan_number': loan.loan_number,
            'member_name': loan.member.get_full_name(),
            'product_name': loan.loan_product.name,
            'principal': float(loan.principal_amount),
            'outstanding': float(loan.outstanding_total),
            'days_in_arrears': loan.days_in_arrears,
        }
        for loan in top_loans
    ]
    
    return stats


# =============================================================================
# LOAN PAYMENT STATISTICS
# =============================================================================

def get_payment_statistics(filters=None):
    """
    Get comprehensive loan payment statistics
    
    Args:
        filters (dict): Optional filters
            - payment_method: Filter by payment method
            - date_from: Filter payments from date
            - date_to: Filter payments to date
            - loan_id: Filter by specific loan
            - member_id: Filter by member's loans
    
    Returns:
        dict: Payment statistics
    """
    from .models import LoanPayment
    
    payments = LoanPayment.objects.filter(is_reversed=False)
    
    # Apply filters
    if filters:
        if filters.get('payment_method'):
            payments = payments.filter(payment_method=filters['payment_method'])
        if filters.get('date_from'):
            payments = payments.filter(payment_date__gte=filters['date_from'])
        if filters.get('date_to'):
            payments = payments.filter(payment_date__lte=filters['date_to'])
        if filters.get('loan_id'):
            payments = payments.filter(loan_id=filters['loan_id'])
        if filters.get('member_id'):
            payments = payments.filter(loan__member_id=filters['member_id'])
    
    total_payments = payments.count()
    
    stats = {
        'total_payments': total_payments,
        'reversed_payments': LoanPayment.objects.filter(is_reversed=True).count(),
    }
    
    # Amount statistics
    amount_stats = payments.aggregate(
        total_amount=Sum('amount'),
        avg_amount=Avg('amount'),
        max_amount=Max('amount'),
        min_amount=Min('amount'),
        total_principal=Sum('principal_amount'),
        total_interest=Sum('interest_amount'),
        total_penalties=Sum('penalty_amount'),
        total_fees=Sum('fee_amount'),
    )
    
    stats['amounts'] = {
        'total_paid': float(amount_stats['total_amount'] or 0),
        'average_payment': float(amount_stats['avg_amount'] or 0),
        'largest_payment': float(amount_stats['max_amount'] or 0),
        'smallest_payment': float(amount_stats['min_amount'] or 0),
        'principal_collected': float(amount_stats['total_principal'] or 0),
        'interest_collected': float(amount_stats['total_interest'] or 0),
        'penalties_collected': float(amount_stats['total_penalties'] or 0),
        'fees_collected': float(amount_stats['total_fees'] or 0),
    }
    
    # Payment allocation breakdown
    total_paid = float(amount_stats['total_amount'] or 0)
    if total_paid > 0:
        stats['payment_allocation'] = {
            'principal_percentage': round(
                (float(amount_stats['total_principal'] or 0) / total_paid * 100),
                2
            ),
            'interest_percentage': round(
                (float(amount_stats['total_interest'] or 0) / total_paid * 100),
                2
            ),
            'penalties_percentage': round(
                (float(amount_stats['total_penalties'] or 0) / total_paid * 100),
                2
            ),
            'fees_percentage': round(
                (float(amount_stats['total_fees'] or 0) / total_paid * 100),
                2
            ),
        }
    
    # Payment method breakdown
    method_breakdown = payments.values('payment_method').annotate(
        count=Count('id'),
        total_amount=Sum('amount'),
        avg_amount=Avg('amount'),
    ).order_by('-count')
    
    stats['by_payment_method'] = [
        {
            'method': item['payment_method'],
            'count': item['count'],
            'total_amount': float(item['total_amount'] or 0),
            'average_amount': float(item['avg_amount'] or 0),
            'percentage': round((item['count'] / total_payments * 100) if total_payments > 0 else 0, 2),
        }
        for item in method_breakdown
    ]
    
    # Daily payment trends (last 30 days)
    today = timezone.now().date()
    thirty_days_ago = today - timedelta(days=30)
    
    daily_trends = payments.filter(
        payment_date__gte=thirty_days_ago
    ).annotate(
        date=F('payment_date')
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
    
    # Recent activity
    stats['recent_activity'] = {
        'last_24_hours': payments.filter(
            payment_date__gte=today - timedelta(days=1)
        ).count(),
        'last_7_days': payments.filter(
            payment_date__gte=today - timedelta(days=7)
        ).count(),
        'last_30_days': payments.filter(
            payment_date__gte=today - timedelta(days=30)
        ).count(),
    }
    
    # Top payments
    top_payments = payments.order_by('-amount')[:10]
    
    stats['top_payments'] = [
        {
            'payment_number': pmt.payment_number,
            'loan_number': pmt.loan.loan_number,
            'member_name': pmt.loan.member.get_full_name(),
            'amount': float(pmt.amount),
            'payment_date': pmt.payment_date.isoformat(),
            'payment_method': pmt.payment_method,
        }
        for pmt in top_payments
    ]
    
    return stats


def get_payment_trends(period='monthly', months=12):
    """
    Get payment trends over time
    
    Args:
        period: 'daily', 'weekly', 'monthly', 'quarterly', 'yearly'
        months: Number of months to analyze
    
    Returns:
        dict: Payment trends data
    """
    from .models import LoanPayment
    
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
    
    payments = LoanPayment.objects.filter(
        payment_date__gte=start_date.date(),
        is_reversed=False
    )
    
    # Overall trends
    trends = payments.annotate(
        period=trunc_func('payment_date')
    ).values('period').annotate(
        count=Count('id'),
        total_amount=Sum('amount'),
        principal_amount=Sum('principal_amount'),
        interest_amount=Sum('interest_amount'),
        penalty_amount=Sum('penalty_amount'),
    ).order_by('period')
    
    trend_data = [
        {
            'period': item['period'].isoformat() if hasattr(item['period'], 'isoformat') else str(item['period']),
            'payments': item['count'],
            'total_amount': float(item['total_amount'] or 0),
            'principal': float(item['principal_amount'] or 0),
            'interest': float(item['interest_amount'] or 0),
            'penalties': float(item['penalty_amount'] or 0),
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
# GUARANTOR STATISTICS
# =============================================================================

def get_guarantor_statistics(filters=None):
    """
    Get guarantor statistics
    
    Args:
        filters (dict): Optional filters
            - status: Filter by guarantor status
            - guarantor_id: Filter by specific guarantor
    
    Returns:
        dict: Guarantor statistics
    """
    from .models import LoanGuarantor
    
    guarantors = LoanGuarantor.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('status'):
            guarantors = guarantors.filter(status=filters['status'])
        if filters.get('guarantor_id'):
            guarantors = guarantors.filter(guarantor_id=filters['guarantor_id'])
    
    total_guarantors = guarantors.count()
    
    stats = {
        'total_guarantor_requests': total_guarantors,
    }
    
    # Status breakdown
    status_breakdown = guarantors.values('status').annotate(
        count=Count('id'),
        total_amount=Sum('guarantee_amount'),
    ).order_by('-count')
    
    stats['by_status'] = [
        {
            'status': item['status'],
            'count': item['count'],
            'total_amount': float(item['total_amount'] or 0),
            'percentage': round((item['count'] / total_guarantors * 100) if total_guarantors > 0 else 0, 2),
        }
        for item in status_breakdown
    ]
    
    # Amount statistics
    amount_stats = guarantors.aggregate(
        total_guaranteed=Sum('guarantee_amount'),
        avg_guarantee=Avg('guarantee_amount'),
        max_guarantee=Max('guarantee_amount'),
        min_guarantee=Min('guarantee_amount'),
    )
    
    stats['amounts'] = {
        'total_guaranteed': float(amount_stats['total_guaranteed'] or 0),
        'average_guarantee': float(amount_stats['avg_guarantee'] or 0),
        'largest_guarantee': float(amount_stats['max_guarantee'] or 0),
        'smallest_guarantee': float(amount_stats['min_guarantee'] or 0),
    }
    
    # Approval metrics
    approved = guarantors.filter(status='APPROVED')
    rejected = guarantors.filter(status='REJECTED')
    pending = guarantors.filter(status='PENDING')
    
    stats['approval_metrics'] = {
        'approved': approved.count(),
        'rejected': rejected.count(),
        'pending': pending.count(),
        'approval_rate': round(
            (approved.count() / total_guarantors * 100) if total_guarantors > 0 else 0,
            2
        ),
        'rejection_rate': round(
            (rejected.count() / total_guarantors * 100) if total_guarantors > 0 else 0,
            2
        ),
    }
    
    # Top guarantors (by number of guarantees)
    from django.db.models import Count as CountFunc
    top_guarantors = guarantors.values(
        'guarantor__id',
        'guarantor__first_name',
        'guarantor__last_name'
    ).annotate(
        guarantee_count=CountFunc('id'),
        total_guaranteed=Sum('guarantee_amount', filter=Q(status='APPROVED')),
    ).order_by('-guarantee_count')[:10]
    
    stats['top_guarantors'] = [
        {
            'guarantor_id': str(item['guarantor__id']),
            'guarantor_name': f"{item['guarantor__first_name']} {item['guarantor__last_name']}",
            'guarantee_count': item['guarantee_count'],
            'total_guaranteed': float(item['total_guaranteed'] or 0),
        }
        for item in top_guarantors
    ]
    
    return stats


# =============================================================================
# COLLATERAL STATISTICS
# =============================================================================

def get_collateral_statistics(filters=None):
    """
    Get collateral statistics
    
    Args:
        filters (dict): Optional filters
            - collateral_type: Filter by collateral type
            - is_verified: Filter by verification status
    
    Returns:
        dict: Collateral statistics
    """
    from .models import LoanCollateral
    
    collaterals = LoanCollateral.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('collateral_type'):
            collaterals = collaterals.filter(collateral_type=filters['collateral_type'])
        if filters.get('is_verified') is not None:
            collaterals = collaterals.filter(is_verified=filters['is_verified'])
    
    total_collaterals = collaterals.count()
    
    stats = {
        'total_collaterals': total_collaterals,
        'verified_collaterals': collaterals.filter(is_verified=True).count(),
        'unverified_collaterals': collaterals.filter(is_verified=False).count(),
    }
    
    # Type breakdown
    type_breakdown = collaterals.values('collateral_type').annotate(
        count=Count('id'),
        total_estimated_value=Sum('estimated_value'),
        total_appraised_value=Sum('appraised_value'),
        avg_estimated_value=Avg('estimated_value'),
    ).order_by('-count')
    
    stats['by_type'] = [
        {
            'type': item['collateral_type'],
            'count': item['count'],
            'total_estimated_value': float(item['total_estimated_value'] or 0),
            'total_appraised_value': float(item['total_appraised_value'] or 0),
            'avg_estimated_value': float(item['avg_estimated_value'] or 0),
        }
        for item in type_breakdown
    ]
    
    # Valuation statistics
    valuation_stats = collaterals.aggregate(
        total_estimated=Sum('estimated_value'),
        total_appraised=Sum('appraised_value'),
        avg_estimated=Avg('estimated_value'),
        avg_appraised=Avg('appraised_value'),
    )
    
    stats['valuations'] = {
        'total_estimated_value': float(valuation_stats['total_estimated'] or 0),
        'total_appraised_value': float(valuation_stats['total_appraised'] or 0),
        'avg_estimated_value': float(valuation_stats['avg_estimated'] or 0),
        'avg_appraised_value': float(valuation_stats['avg_appraised'] or 0),
    }
    
    # Insurance statistics
    stats['insurance'] = {
        'insured_collaterals': collaterals.filter(is_insured=True).count(),
        'uninsured_collaterals': collaterals.filter(is_insured=False).count(),
        'insurance_rate': round(
            (collaterals.filter(is_insured=True).count() / total_collaterals * 100) if total_collaterals > 0 else 0,
            2
        ),
    }
    
    return stats


# =============================================================================
# LOAN SCHEDULE STATISTICS
# =============================================================================

def get_schedule_statistics(filters=None):
    """
    Get loan schedule statistics
    
    Args:
        filters (dict): Optional filters
            - status: Filter by schedule status
            - loan_id: Filter by specific loan
            - is_overdue: Filter overdue installments
    
    Returns:
        dict: Schedule statistics
    """
    from .models import LoanSchedule
    
    schedules = LoanSchedule.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('status'):
            schedules = schedules.filter(status=filters['status'])
        if filters.get('loan_id'):
            schedules = schedules.filter(loan_id=filters['loan_id'])
        if filters.get('is_overdue') is not None:
            if filters['is_overdue']:
                schedules = schedules.filter(status='OVERDUE')
            else:
                schedules = schedules.exclude(status='OVERDUE')
    
    total_schedules = schedules.count()
    
    stats = {
        'total_installments': total_schedules,
    }
    
    # Status breakdown
    status_breakdown = schedules.values('status').annotate(
        count=Count('id'),
        total_amount=Sum('total_amount'),
        total_balance=Sum('balance'),
    ).order_by('-count')
    
    stats['by_status'] = [
        {
            'status': item['status'],
            'count': item['count'],
            'total_amount': float(item['total_amount'] or 0),
            'total_balance': float(item['total_balance'] or 0),
            'percentage': round((item['count'] / total_schedules * 100) if total_schedules > 0 else 0, 2),
        }
        for item in status_breakdown
    ]
    
    # Amount statistics
    amount_stats = schedules.aggregate(
        total_scheduled=Sum('total_amount'),
        total_paid=Sum('paid_amount'),
        total_balance=Sum('balance'),
        avg_installment=Avg('total_amount'),
    )
    
    stats['amounts'] = {
        'total_scheduled': float(amount_stats['total_scheduled'] or 0),
        'total_paid': float(amount_stats['total_paid'] or 0),
        'total_balance': float(amount_stats['total_balance'] or 0),
        'avg_installment': float(amount_stats['avg_installment'] or 0),
    }
    
    # Overdue analysis
    overdue = schedules.filter(status='OVERDUE')
    overdue_stats = overdue.aggregate(
        count=Count('id'),
        total_overdue=Sum('balance'),
        avg_days_late=Avg('days_late'),
        max_days_late=Max('days_late'),
    )
    
    stats['overdue'] = {
        'overdue_installments': overdue_stats['count'] or 0,
        'total_overdue_amount': float(overdue_stats['total_overdue'] or 0),
        'avg_days_late': round(float(overdue_stats['avg_days_late'] or 0), 1),
        'max_days_late': overdue_stats['max_days_late'] or 0,
    }
    
    # Due installments
    today = timezone.now().date()
    stats['due_installments'] = {
        'due_today': schedules.filter(status='PENDING', due_date=today).count(),
        'due_this_week': schedules.filter(
            status='PENDING',
            due_date__gte=today,
            due_date__lte=today + timedelta(days=7)
        ).count(),
        'due_this_month': schedules.filter(
            status='PENDING',
            due_date__gte=today,
            due_date__lte=today + timedelta(days=30)
        ).count(),
    }
    
    return stats


# =============================================================================
# INDIVIDUAL LOAN/APPLICATION SUMMARIES
# =============================================================================

def get_loan_summary(loan):
    """
    Get comprehensive summary for a single loan
    
    Args:
        loan: Loan instance
        
    Returns:
        dict: Summary data for the loan
    """
    from django.db.models import Max
    
    # Payment summary
    payments = loan.payments.filter(is_reversed=False)
    
    payment_aggregates = payments.aggregate(
        total_payments=Sum('amount'),
        payment_count=Count('id'),
        last_payment_date=Max('payment_date')
    )
    
    # Schedule summary
    schedule = loan.schedule.all()
    
    schedule_aggregates = schedule.aggregate(
        total_installments=Count('id'),
        paid_installments=Count('id', filter=Q(status='PAID')),
        pending_installments=Count('id', filter=Q(status='PENDING')),
        overdue_installments=Count('id', filter=Q(status='OVERDUE')),
        partially_paid_installments=Count('id', filter=Q(status='PARTIALLY_PAID')),
        total_due=Sum('total_amount'),
        total_paid=Sum('paid_amount'),
        total_balance=Sum('balance')
    )
    
    # Calculate days to key dates
    today = timezone.now().date()
    days_to_first_payment = (loan.first_payment_date - today).days if loan.first_payment_date > today else 0
    days_to_maturity = (loan.expected_end_date - today).days if loan.expected_end_date > today else 0
    
    return {
        'payment_count': payment_aggregates['payment_count'] or 0,
        'total_payments': float(payment_aggregates['total_payments'] or 0),
        'last_payment_date': payment_aggregates['last_payment_date'],
        'total_installments': schedule_aggregates['total_installments'] or 0,
        'paid_installments': schedule_aggregates['paid_installments'] or 0,
        'pending_installments': schedule_aggregates['pending_installments'] or 0,
        'overdue_installments': schedule_aggregates['overdue_installments'] or 0,
        'partially_paid_installments': schedule_aggregates['partially_paid_installments'] or 0,
        'total_due': float(schedule_aggregates['total_due'] or 0),
        'total_paid_from_schedule': float(schedule_aggregates['total_paid'] or 0),
        'total_balance': float(schedule_aggregates['total_balance'] or 0),
        'payment_progress': float(loan.payment_progress_percentage),
        'days_to_first_payment': days_to_first_payment,
        'days_to_maturity': days_to_maturity,
        'is_overdue': loan.is_overdue,
        'days_in_arrears': loan.days_in_arrears,
        'loan_duration_days': loan.loan_duration_days,
        'remaining_term_months': float(loan.remaining_term_months),
    }


def get_application_summary(application):
    """
    Get comprehensive summary for a loan application
    
    Args:
        application: LoanApplication instance
        
    Returns:
        dict: Summary data for the application
    """
    
    guarantors = application.guarantors.all()
    collaterals = application.collaterals.all()
    documents = application.documents.all()
    
    guarantor_aggregates = guarantors.aggregate(
        total_count=Count('id'),
        approved_count=Count('id', filter=Q(status='APPROVED')),
        pending_count=Count('id', filter=Q(status='PENDING')),
        rejected_count=Count('id', filter=Q(status='REJECTED')),
        cancelled_count=Count('id', filter=Q(status='CANCELLED')),
        expired_count=Count('id', filter=Q(status='EXPIRED')),
        total_guarantee=Sum('guarantee_amount')
    )
    
    collateral_aggregates = collaterals.aggregate(
        total_count=Count('id'),
        verified_count=Count('id', filter=Q(is_verified=True)),
        insured_count=Count('id', filter=Q(is_insured=True)),
        total_estimated_value=Sum('estimated_value'),
        total_appraised_value=Sum('appraised_value')
    )
    
    document_aggregates = documents.aggregate(
        total_count=Count('id'),
        verified_count=Count('id', filter=Q(is_verified=True)),
        required_count=Count('id', filter=Q(is_required=True)),
        verified_required_count=Count('id', filter=Q(is_required=True, is_verified=True))
    )
    
    # Check if requirements are met
    meets_guarantor_requirement = True
    if application.loan_product.guarantor_required:
        meets_guarantor_requirement = (
            guarantor_aggregates['approved_count'] >= application.loan_product.number_of_guarantors
        )
    
    meets_collateral_requirement = True
    if application.loan_product.collateral_required:
        meets_collateral_requirement = collateral_aggregates['verified_count'] > 0
    
    # Document completeness
    all_required_docs_verified = False
    if document_aggregates['required_count'] > 0:
        all_required_docs_verified = (
            document_aggregates['verified_required_count'] == document_aggregates['required_count']
        )
    
    return {
        'guarantor_count': guarantor_aggregates['total_count'] or 0,
        'approved_guarantors': guarantor_aggregates['approved_count'] or 0,
        'pending_guarantors': guarantor_aggregates['pending_count'] or 0,
        'rejected_guarantors': guarantor_aggregates['rejected_count'] or 0,
        'cancelled_guarantors': guarantor_aggregates['cancelled_count'] or 0,
        'expired_guarantors': guarantor_aggregates['expired_count'] or 0,
        'total_guarantee': float(guarantor_aggregates['total_guarantee'] or 0),
        'collateral_count': collateral_aggregates['total_count'] or 0,
        'verified_collateral': collateral_aggregates['verified_count'] or 0,
        'insured_collateral': collateral_aggregates['insured_count'] or 0,
        'total_collateral_value': float(collateral_aggregates['total_estimated_value'] or 0),
        'total_appraised_value': float(collateral_aggregates['total_appraised_value'] or 0),
        'document_count': document_aggregates['total_count'] or 0,
        'verified_documents': document_aggregates['verified_count'] or 0,
        'required_documents': document_aggregates['required_count'] or 0,
        'verified_required_documents': document_aggregates['verified_required_count'] or 0,
        'meets_guarantor_requirement': meets_guarantor_requirement,
        'meets_collateral_requirement': meets_collateral_requirement,
        'all_required_docs_verified': all_required_docs_verified,
        'is_ready_for_approval': (
            meets_guarantor_requirement and 
            meets_collateral_requirement and 
            (all_required_docs_verified or document_aggregates['required_count'] == 0)
        ),
    }


# =============================================================================
# COMPREHENSIVE LOAN OVERVIEW
# =============================================================================

def get_loan_overview(date_from=None, date_to=None):
    """
    Get comprehensive loan overview with all key metrics
    
    Args:
        date_from: Optional start date for filtering
        date_to: Optional end date for filtering
    
    Returns:
        dict: Comprehensive loan overview
    """
    from .models import LoanProduct, LoanApplication, Loan, LoanPayment
    
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
    products = LoanProduct.objects.all()
    overview['products'] = {
        'total': products.count(),
        'active': products.filter(is_active=True).count(),
    }
    
    # Applications summary
    applications = LoanApplication.objects.filter(
        application_date__gte=date_from,
        application_date__lte=date_to
    )
    
    app_summary = applications.aggregate(
        total=Count('id'),
        approved=Count('id', filter=Q(status='APPROVED')),
        rejected=Count('id', filter=Q(status='REJECTED')),
        pending=Count('id', filter=Q(status__in=['DRAFT', 'SUBMITTED', 'UNDER_REVIEW'])),
        total_requested=Sum('amount_requested'),
        total_approved=Sum('approved_amount', filter=Q(status='APPROVED')),
    )
    
    overview['applications'] = {
        'total': app_summary['total'] or 0,
        'approved': app_summary['approved'] or 0,
        'rejected': app_summary['rejected'] or 0,
        'pending': app_summary['pending'] or 0,
        'total_requested': float(app_summary['total_requested'] or 0),
        'total_approved': float(app_summary['total_approved'] or 0),
        'approval_rate': round(
            (app_summary['approved'] / app_summary['total'] * 100) if app_summary['total'] > 0 else 0,
            2
        ),
    }
    
    # Loans summary
    loans = Loan.objects.all()
    active_loans = loans.filter(status='ACTIVE')
    
    loan_summary = loans.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(status='ACTIVE')),
        paid=Count('id', filter=Q(status='PAID')),
        defaulted=Count('id', filter=Q(status='DEFAULTED')),
        total_principal=Sum('principal_amount'),
        total_outstanding=Sum('outstanding_total', filter=Q(status='ACTIVE')),
        total_collected=Sum('total_paid'),
    )
    
    overview['loans'] = {
        'total': loan_summary['total'] or 0,
        'active': loan_summary['active'] or 0,
        'paid': loan_summary['paid'] or 0,
        'defaulted': loan_summary['defaulted'] or 0,
        'total_principal_disbursed': float(loan_summary['total_principal'] or 0),
        'total_outstanding': float(loan_summary['total_outstanding'] or 0),
        'total_collected': float(loan_summary['total_collected'] or 0),
    }
    
    # Portfolio quality
    overdue_loans = active_loans.filter(days_in_arrears__gt=0)
    par_30 = overdue_loans.filter(days_in_arrears__gte=30)
    par_90 = overdue_loans.filter(days_in_arrears__gte=90)
    
    overview['portfolio_quality'] = {
        'overdue_loans': overdue_loans.count(),
        'par_30_count': par_30.count(),
        'par_90_count': par_90.count(),
        'overdue_rate': round(
            (overdue_loans.count() / active_loans.count() * 100) if active_loans.count() > 0 else 0,
            2
        ),
    }
    
    # Payments summary for period
    payments = LoanPayment.objects.filter(
        payment_date__gte=date_from,
        payment_date__lte=date_to,
        is_reversed=False
    )
    
    payment_summary = payments.aggregate(
        total_payments=Count('id'),
        total_amount=Sum('amount'),
        principal_collected=Sum('principal_amount'),
        interest_collected=Sum('interest_amount'),
        penalties_collected=Sum('penalty_amount'),
    )
    
    overview['payments'] = {
        'total_payments': payment_summary['total_payments'] or 0,
        'total_amount': float(payment_summary['total_amount'] or 0),
        'principal_collected': float(payment_summary['principal_collected'] or 0),
        'interest_collected': float(payment_summary['interest_collected'] or 0),
        'penalties_collected': float(payment_summary['penalties_collected'] or 0),
    }
    
    # Growth metrics
    previous_date_from = date_from - (date_to - date_from)
    previous_date_to = date_from - timedelta(days=1)
    
    previous_applications = LoanApplication.objects.filter(
        application_date__gte=previous_date_from,
        application_date__lte=previous_date_to
    ).count()
    
    current_applications = app_summary['total'] or 0
    application_growth = (
        ((current_applications - previous_applications) / previous_applications * 100)
        if previous_applications > 0 else 0
    )
    
    overview['growth'] = {
        'application_growth_percentage': round(application_growth, 2),
        'new_loans_in_period': loans.filter(
            disbursement_date__gte=date_from,
            disbursement_date__lte=date_to
        ).count(),
    }
    
    return overview