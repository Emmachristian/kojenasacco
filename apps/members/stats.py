# members/stats.py
"""
Comprehensive statistics utility functions for Member models
Provides detailed analytics for members, payments, next of kin, and groups
"""

from django.utils import timezone
from django.db.models import (
    Count, Q, Avg, Sum, Max, Min
)
from django.db.models.functions import TruncMonth, TruncYear, TruncWeek, TruncDate
from datetime import timedelta, date
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# MEMBER STATISTICS
# =============================================================================

def get_member_statistics(filters=None):
    """
    Get comprehensive statistics for members
    
    Args:
        filters (dict): Optional filters to apply
            - status: Filter by member status
            - member_category: Filter by category
            - membership_plan: Filter by plan
            - gender: Filter by gender
            - employment_status: Filter by employment status
            - kyc_status: Filter by KYC status
            - risk_rating: Filter by risk rating
            - date_range: Tuple of (start_date, end_date) for membership
            - min_age: Minimum age filter
            - max_age: Maximum age filter
    
    Returns:
        dict: Comprehensive member statistics
    """
    from .models import Member
    
    members = Member.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('status'):
            members = members.filter(status=filters['status'])
        if filters.get('member_category'):
            members = members.filter(member_category=filters['member_category'])
        if filters.get('membership_plan'):
            members = members.filter(membership_plan=filters['membership_plan'])
        if filters.get('gender'):
            members = members.filter(gender=filters['gender'])
        if filters.get('employment_status'):
            members = members.filter(employment_status=filters['employment_status'])
        if filters.get('kyc_status'):
            members = members.filter(kyc_status=filters['kyc_status'])
        if filters.get('risk_rating'):
            members = members.filter(risk_rating=filters['risk_rating'])
        if filters.get('date_range'):
            start_date, end_date = filters['date_range']
            members = members.filter(
                membership_date__gte=start_date,
                membership_date__lte=end_date
            )
        if filters.get('min_age'):
            # Calculate date of birth threshold
            today = date.today()
            max_birth_date = date(today.year - filters['min_age'], today.month, today.day)
            members = members.filter(date_of_birth__lte=max_birth_date)
        if filters.get('max_age'):
            # Calculate date of birth threshold
            today = date.today()
            min_birth_date = date(today.year - filters['max_age'] - 1, today.month, today.day)
            members = members.filter(date_of_birth__gte=min_birth_date)
    
    # Basic counts
    total_members = members.count()
    current_date = timezone.now().date()
    
    stats = {
        'total_members': total_members,
        
        # Status breakdown
        'status_breakdown': dict(
            members.values('status')
            .annotate(count=Count('id'))
            .values_list('status', 'count')
        ),
        
        # Quick status counts
        'active_members': members.filter(status='ACTIVE').count(),
        'pending_approval': members.filter(status='PENDING_APPROVAL').count(),
        'suspended_members': members.filter(status='SUSPENDED').count(),
        'dormant_members': members.filter(status='DORMANT').count(),
        'deceased_members': members.filter(status='DECEASED').count(),
        'withdrawn_members': members.filter(status='WITHDRAWN').count(),
        
        # Gender distribution
        'by_gender': dict(
            members.values('gender')
            .annotate(count=Count('id'))
            .values_list('gender', 'count')
        ),
        
        # Category distribution
        'by_category': dict(
            members.values('member_category')
            .annotate(count=Count('id'))
            .values_list('member_category', 'count')
        ),
        
        # Membership plan distribution
        'by_plan': dict(
            members.values('membership_plan')
            .annotate(count=Count('id'))
            .values_list('membership_plan', 'count')
        ),
        
        # Employment status distribution
        'by_employment': dict(
            members.values('employment_status')
            .annotate(count=Count('id'))
            .values_list('employment_status', 'count')
        ),
        
        # KYC status distribution
        'by_kyc_status': dict(
            members.values('kyc_status')
            .annotate(count=Count('id'))
            .values_list('kyc_status', 'count')
        ),
        
        # Risk rating distribution
        'by_risk_rating': dict(
            members.values('risk_rating')
            .annotate(count=Count('id'))
            .values_list('risk_rating', 'count')
        ),
        
        # Marital status distribution
        'by_marital_status': dict(
            members.values('marital_status')
            .annotate(count=Count('id'))
            .values_list('marital_status', 'count')
        ),
    }
    
    # Age statistics
    if total_members > 0:
        members_with_dob = members.exclude(date_of_birth__isnull=True)
        
        if members_with_dob.exists():
            ages = []
            for member in members_with_dob:
                try:
                    age = member.age
                    ages.append(age)
                except:
                    continue
            
            if ages:
                stats['age_statistics'] = {
                    'average_age': sum(ages) / len(ages),
                    'youngest_age': min(ages),
                    'oldest_age': max(ages),
                    'median_age': sorted(ages)[len(ages) // 2] if ages else 0,
                }
                
                # Age distribution
                stats['age_distribution'] = {
                    'under_25': sum(1 for age in ages if age < 25),
                    '25_to_35': sum(1 for age in ages if 25 <= age < 35),
                    '35_to_45': sum(1 for age in ages if 35 <= age < 45),
                    '45_to_55': sum(1 for age in ages if 45 <= age < 55),
                    '55_to_65': sum(1 for age in ages if 55 <= age < 65),
                    'over_65': sum(1 for age in ages if age >= 65),
                }
    
    # Income statistics
    members_with_income = members.filter(monthly_income__isnull=False)
    if members_with_income.exists():
        income_data = members_with_income.aggregate(
            total_income=Sum('monthly_income'),
            average_income=Avg('monthly_income'),
            max_income=Max('monthly_income'),
            min_income=Min('monthly_income')
        )
        
        stats['income_statistics'] = {
            'total_monthly_income': float(income_data['total_income'] or 0),
            'average_monthly_income': float(income_data['average_income'] or 0),
            'highest_monthly_income': float(income_data['max_income'] or 0),
            'lowest_monthly_income': float(income_data['min_income'] or 0),
        }
        
        # Income distribution
        stats['income_distribution'] = {
            'under_200k': members.filter(monthly_income__lt=200000).count(),
            '200k_to_500k': members.filter(monthly_income__gte=200000, monthly_income__lt=500000).count(),
            '500k_to_1m': members.filter(monthly_income__gte=500000, monthly_income__lt=1000000).count(),
            '1m_to_2m': members.filter(monthly_income__gte=1000000, monthly_income__lt=2000000).count(),
            'over_2m': members.filter(monthly_income__gte=2000000).count(),
        }
    
    # Credit score statistics
    credit_data = members.aggregate(
        average_credit_score=Avg('credit_score'),
        max_credit_score=Max('credit_score'),
        min_credit_score=Min('credit_score')
    )
    
    stats['credit_statistics'] = {
        'average_credit_score': float(credit_data['average_credit_score'] or 0),
        'highest_credit_score': float(credit_data['max_credit_score'] or 0),
        'lowest_credit_score': float(credit_data['min_credit_score'] or 0),
    }
    
    # Credit score distribution
    stats['credit_score_distribution'] = {
        'poor_0_350': members.filter(credit_score__lt=350).count(),
        'fair_350_500': members.filter(credit_score__gte=350, credit_score__lt=500).count(),
        'good_500_650': members.filter(credit_score__gte=500, credit_score__lt=650).count(),
        'very_good_650_800': members.filter(credit_score__gte=650, credit_score__lt=800).count(),
        'excellent_800_plus': members.filter(credit_score__gte=800).count(),
    }
    
    # Membership duration analysis
    if total_members > 0:
        durations = []
        for member in members:
            try:
                duration = member.membership_duration_days
                durations.append(duration)
            except:
                continue
        
        if durations:
            stats['membership_duration'] = {
                'average_days': sum(durations) / len(durations),
                'shortest_days': min(durations),
                'longest_days': max(durations),
            }
            
            # Duration distribution
            stats['membership_duration_distribution'] = {
                'under_6_months': sum(1 for d in durations if d < 180),
                '6_to_12_months': sum(1 for d in durations if 180 <= d < 365),
                '1_to_2_years': sum(1 for d in durations if 365 <= d < 730),
                '2_to_5_years': sum(1 for d in durations if 730 <= d < 1825),
                'over_5_years': sum(1 for d in durations if d >= 1825),
            }
    
    # Membership trends - convert dates to strings
    stats['membership_trends'] = {
        'by_year': {},
        'by_month': {},
    }
    
    # Year trends
    year_data = members.filter(membership_date__isnull=False).annotate(
        year=TruncYear('membership_date')
    ).values('year').annotate(count=Count('id')).order_by('-year')
    
    for item in year_data:
        if item['year']:
            year_str = item['year'].strftime('%Y')
            stats['membership_trends']['by_year'][year_str] = item['count']
    
    # Month trends (last 12 months)
    month_data = members.filter(membership_date__isnull=False).annotate(
        month=TruncMonth('membership_date')
    ).values('month').annotate(count=Count('id')).order_by('-month')[:12]
    
    for item in month_data:
        if item['month']:
            month_str = item['month'].strftime('%Y-%m')
            stats['membership_trends']['by_month'][month_str] = item['count']
    
    # Recent activity
    stats['recent_activity'] = {
        'joined_last_7_days': members.filter(
            membership_date__gte=current_date - timedelta(days=7)
        ).count(),
        'joined_last_30_days': members.filter(
            membership_date__gte=current_date - timedelta(days=30)
        ).count(),
        'joined_last_90_days': members.filter(
            membership_date__gte=current_date - timedelta(days=90)
        ).count(),
        'created_last_7_days': members.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count(),
        'modified_last_7_days': members.filter(
            updated_at__gte=timezone.now() - timedelta(days=7)
        ).count(),
    }
    
    # KYC compliance metrics
    stats['kyc_compliance'] = {
        'verified': members.filter(kyc_status='VERIFIED').count(),
        'pending': members.filter(kyc_status='PENDING').count(),
        'in_progress': members.filter(kyc_status='IN_PROGRESS').count(),
        'rejected': members.filter(kyc_status='REJECTED').count(),
        'expired': members.filter(kyc_status='EXPIRED').count(),
        'requires_update': members.filter(kyc_status='REQUIRES_UPDATE').count(),
        'compliance_rate': 0,
    }
    
    if total_members > 0:
        stats['kyc_compliance']['compliance_rate'] = (
            stats['kyc_compliance']['verified'] / total_members * 100
        )
    
    # Risk assessment
    stats['risk_assessment'] = {
        'very_low': members.filter(risk_rating='VERY_LOW').count(),
        'low': members.filter(risk_rating='LOW').count(),
        'medium': members.filter(risk_rating='MEDIUM').count(),
        'high': members.filter(risk_rating='HIGH').count(),
        'very_high': members.filter(risk_rating='VERY_HIGH').count(),
        'unknown': members.filter(risk_rating='UNKNOWN').count(),
    }
    
    return stats


def get_member_growth_trends(period='month', limit=12):
    """
    Get member growth trends over time
    
    Args:
        period (str): 'day', 'week', 'month', or 'year'
        limit (int): Number of periods to return
    
    Returns:
        dict: Growth trend data
    """
    from .models import Member
    
    members = Member.objects.filter(membership_date__isnull=False)
    
    # Select appropriate truncation function
    trunc_functions = {
        'day': TruncDate,
        'week': TruncWeek,
        'month': TruncMonth,
        'year': TruncYear,
    }
    
    trunc_func = trunc_functions.get(period, TruncMonth)
    
    # Get new members by period
    growth_data = members.annotate(
        period_date=trunc_func('membership_date')
    ).values('period_date').annotate(
        new_members=Count('id')
    ).order_by('-period_date')[:limit]
    
    # Format dates as strings
    formatted_data = []
    for item in growth_data:
        if item['period_date']:
            date_str = item['period_date'].strftime('%Y-%m-%d')
            formatted_data.append({
                'period': date_str,
                'new_members': item['new_members']
            })
    
    # Calculate cumulative totals
    cumulative = 0
    for item in reversed(formatted_data):
        cumulative += item['new_members']
        item['cumulative_members'] = cumulative
    
    return {
        'period': period,
        'data': list(reversed(formatted_data)),
        'total_periods': len(formatted_data),
    }


# =============================================================================
# PAYMENT METHOD STATISTICS
# =============================================================================

def get_payment_method_statistics(filters=None):
    """
    Get statistics for member payment methods
    
    Args:
        filters (dict): Optional filters
            - member: Filter by member ID
            - method_type: Filter by method type
            - is_verified: Filter by verification status
    
    Returns:
        dict: Payment method statistics
    """
    from .models import MemberPaymentMethod
    
    payment_methods = MemberPaymentMethod.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('member'):
            payment_methods = payment_methods.filter(member_id=filters['member'])
        if filters.get('method_type'):
            payment_methods = payment_methods.filter(method_type=filters['method_type'])
        if filters.get('is_verified') is not None:
            payment_methods = payment_methods.filter(is_verified=filters['is_verified'])
    
    total_methods = payment_methods.count()
    
    stats = {
        'total_payment_methods': total_methods,
        'primary_methods': payment_methods.filter(is_primary=True).count(),
        'verified_methods': payment_methods.filter(is_verified=True).count(),
        'active_methods': payment_methods.filter(is_active=True).count(),
        
        # Type distribution
        'by_type': dict(
            payment_methods.values('method_type')
            .annotate(count=Count('id'))
            .values_list('method_type', 'count')
        ),
        
        # Provider distribution (top 10)
        'top_providers': dict(
            payment_methods.values('provider')
            .annotate(count=Count('id'))
            .order_by('-count')
            .values_list('provider', 'count')[:10]
        ),
        
        # Verification rate
        'verification_rate': 0,
    }
    
    if total_methods > 0:
        stats['verification_rate'] = (
            stats['verified_methods'] / total_methods * 100
        )
    
    # Members with payment methods
    from .models import Member
    total_members = Member.objects.filter(status='ACTIVE').count()
    members_with_payment = Member.objects.filter(
        payment_methods__isnull=False
    ).distinct().count()
    
    stats['member_coverage'] = {
        'total_active_members': total_members,
        'members_with_payment_methods': members_with_payment,
        'coverage_rate': (members_with_payment / total_members * 100) if total_members > 0 else 0,
    }
    
    return stats


# =============================================================================
# NEXT OF KIN STATISTICS
# =============================================================================

def get_next_of_kin_statistics(filters=None):
    """
    Get statistics for next of kin
    
    Args:
        filters (dict): Optional filters
            - member: Filter by member ID
            - relation: Filter by relationship
            - is_primary: Filter by primary status
    
    Returns:
        dict: Next of kin statistics
    """
    from .models import NextOfKin
    
    next_of_kin = NextOfKin.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('member'):
            next_of_kin = next_of_kin.filter(member_id=filters['member'])
        if filters.get('relation'):
            next_of_kin = next_of_kin.filter(relation=filters['relation'])
        if filters.get('is_primary') is not None:
            next_of_kin = next_of_kin.filter(is_primary=filters['is_primary'])
    
    total_nok = next_of_kin.count()
    
    stats = {
        'total_next_of_kin': total_nok,
        'primary_contacts': next_of_kin.filter(is_primary=True).count(),
        'emergency_contacts': next_of_kin.filter(is_emergency_contact=True).count(),
        'beneficiaries': next_of_kin.filter(is_beneficiary=True).count(),
        
        # Relationship distribution
        'by_relationship': dict(
            next_of_kin.values('relation')
            .annotate(count=Count('id'))
            .values_list('relation', 'count')
        ),
    }
    
    # Members coverage
    from .models import Member
    total_members = Member.objects.filter(status='ACTIVE').count()
    members_with_nok = Member.objects.filter(
        next_of_kin__isnull=False
    ).distinct().count()
    
    stats['member_coverage'] = {
        'total_active_members': total_members,
        'members_with_next_of_kin': members_with_nok,
        'coverage_rate': (members_with_nok / total_members * 100) if total_members > 0 else 0,
    }
    
    # Beneficiary statistics
    beneficiaries = next_of_kin.filter(is_beneficiary=True)
    if beneficiaries.exists():
        stats['beneficiary_stats'] = {
            'total_beneficiaries': beneficiaries.count(),
            'average_percentage': float(
                beneficiaries.aggregate(avg=Avg('beneficiary_percentage'))['avg'] or 0
            ),
            'total_allocated_percentage': float(
                beneficiaries.aggregate(total=Sum('beneficiary_percentage'))['total'] or 0
            ),
        }
    
    return stats


# =============================================================================
# GROUP STATISTICS
# =============================================================================

def get_group_statistics(filters=None):
    """
    Get comprehensive statistics for member groups
    
    Args:
        filters (dict): Optional filters
            - group_type: Filter by group type
            - is_active: Filter by active status
            - is_full: Filter by full status
    
    Returns:
        dict: Group statistics
    """
    from .models import MemberGroup, GroupMembership
    
    groups = MemberGroup.objects.all()
    
    # Apply filters
    if filters:
        if filters.get('group_type'):
            groups = groups.filter(group_type=filters['group_type'])
        if filters.get('is_active') is not None:
            groups = groups.filter(is_active=filters['is_active'])
        if filters.get('is_full') is not None:
            groups = groups.filter(is_full=filters['is_full'])
    
    total_groups = groups.count()
    
    stats = {
        'total_groups': total_groups,
        'active_groups': groups.filter(is_active=True).count(),
        'inactive_groups': groups.filter(is_active=False).count(),
        'full_groups': groups.filter(is_full=True).count(),
        'available_groups': groups.filter(is_full=False, is_active=True).count(),
        
        # Type distribution
        'by_type': dict(
            groups.values('group_type')
            .annotate(count=Count('id'))
            .values_list('group_type', 'count')
        ),
        
        # Meeting frequency distribution
        'by_meeting_frequency': dict(
            groups.values('meeting_frequency')
            .annotate(count=Count('id'))
            .values_list('meeting_frequency', 'count')
        ),
    }
    
    # Group size statistics
    if total_groups > 0:
        group_sizes = []
        for group in groups:
            try:
                size = group.member_count
                group_sizes.append(size)
            except:
                continue
        
        if group_sizes:
            stats['size_statistics'] = {
                'average_size': sum(group_sizes) / len(group_sizes),
                'smallest_group': min(group_sizes),
                'largest_group': max(group_sizes),
                'total_memberships': sum(group_sizes),
            }
    
    # Financial statistics
    financial_data = groups.aggregate(
        total_min_contribution=Sum('minimum_contribution'),
        average_min_contribution=Avg('minimum_contribution'),
        total_max_loan=Sum('maximum_loan_amount'),
        average_max_loan=Avg('maximum_loan_amount'),
        average_interest_rate=Avg('interest_rate')
    )
    
    stats['financial_statistics'] = {
        'total_minimum_contributions': float(financial_data['total_min_contribution'] or 0),
        'average_minimum_contribution': float(financial_data['average_min_contribution'] or 0),
        'total_maximum_loans': float(financial_data['total_max_loan'] or 0),
        'average_maximum_loan': float(financial_data['average_max_loan'] or 0),
        'average_interest_rate': float(financial_data['average_interest_rate'] or 0),
    }
    
    # Membership statistics
    memberships = GroupMembership.objects.filter(is_active=True)
    
    stats['membership_statistics'] = {
        'total_active_memberships': memberships.count(),
        'unique_members_in_groups': memberships.values('member').distinct().count(),
        
        # Role distribution
        'by_role': dict(
            memberships.values('role')
            .annotate(count=Count('id'))
            .values_list('role', 'count')
        ),
        
        # Status distribution
        'by_status': dict(
            GroupMembership.objects.values('status')
            .annotate(count=Count('id'))
            .values_list('status', 'count')
        ),
    }
    
    # Recent activity
    current_date = timezone.now().date()
    stats['recent_activity'] = {
        'groups_formed_last_30_days': groups.filter(
            formation_date__gte=current_date - timedelta(days=30)
        ).count(),
        'groups_formed_last_90_days': groups.filter(
            formation_date__gte=current_date - timedelta(days=90)
        ).count(),
        'new_memberships_last_30_days': memberships.filter(
            join_date__gte=current_date - timedelta(days=30)
        ).count(),
    }
    
    return stats


def get_group_membership_trends(period='month', limit=12):
    """
    Get group membership trends over time
    
    Args:
        period (str): 'day', 'week', 'month', or 'year'
        limit (int): Number of periods to return
    
    Returns:
        dict: Membership trend data
    """
    from .models import GroupMembership
    
    # Select appropriate truncation function
    trunc_functions = {
        'day': TruncDate,
        'week': TruncWeek,
        'month': TruncMonth,
        'year': TruncYear,
    }
    
    trunc_func = trunc_functions.get(period, TruncMonth)
    
    # Get new memberships by period
    trend_data = GroupMembership.objects.annotate(
        period_date=trunc_func('join_date')
    ).values('period_date').annotate(
        new_memberships=Count('id'),
        active_memberships=Count('id', filter=Q(is_active=True))
    ).order_by('-period_date')[:limit]
    
    # Format dates as strings
    formatted_data = []
    for item in trend_data:
        if item['period_date']:
            date_str = item['period_date'].strftime('%Y-%m-%d')
            formatted_data.append({
                'period': date_str,
                'new_memberships': item['new_memberships'],
                'active_memberships': item['active_memberships'],
            })
    
    return {
        'period': period,
        'data': list(reversed(formatted_data)),
        'total_periods': len(formatted_data),
    }


# =============================================================================
# COMBINED ANALYTICS
# =============================================================================

def get_dashboard_summary():
    """
    Get a comprehensive dashboard summary combining all metrics
    
    Returns:
        dict: Dashboard summary with key metrics
    """
    current_date = timezone.now().date()
    
    # Get basic stats
    member_stats = get_member_statistics()
    payment_stats = get_payment_method_statistics()
    nok_stats = get_next_of_kin_statistics()
    group_stats = get_group_statistics()
    
    # Calculate key metrics
    summary = {
        'members': {
            'total': member_stats['total_members'],
            'active': member_stats['active_members'],
            'pending_approval': member_stats['pending_approval'],
            'suspended': member_stats['suspended_members'],
            'new_this_month': member_stats['recent_activity']['joined_last_30_days'],
        },
        'kyc_compliance': {
            'verified': member_stats['kyc_compliance']['verified'],
            'pending': member_stats['kyc_compliance']['pending'],
            'compliance_rate': member_stats['kyc_compliance']['compliance_rate'],
        },
        'risk_profile': {
            'high_risk': member_stats['risk_assessment']['high'] + member_stats['risk_assessment']['very_high'],
            'medium_risk': member_stats['risk_assessment']['medium'],
            'low_risk': member_stats['risk_assessment']['low'] + member_stats['risk_assessment']['very_low'],
        },
        'payment_methods': {
            'total': payment_stats['total_payment_methods'],
            'verified': payment_stats['verified_methods'],
            'coverage_rate': payment_stats['member_coverage']['coverage_rate'],
        },
        'next_of_kin': {
            'total': nok_stats['total_next_of_kin'],
            'coverage_rate': nok_stats['member_coverage']['coverage_rate'],
        },
        'groups': {
            'total': group_stats['total_groups'],
            'active': group_stats['active_groups'],
            'total_memberships': group_stats['membership_statistics']['total_active_memberships'],
        },
        'financial_overview': {
            'average_monthly_income': member_stats.get('income_statistics', {}).get('average_monthly_income', 0),
            'average_credit_score': member_stats['credit_statistics']['average_credit_score'],
        },
    }
    
    return summary


def get_member_retention_analysis(months=12):
    """
    Analyze member retention over time
    
    Args:
        months (int): Number of months to analyze
    
    Returns:
        dict: Retention analysis data
    """
    from .models import Member
    
    current_date = timezone.now().date()
    start_date = current_date - timedelta(days=months * 30)
    
    members = Member.objects.filter(membership_date__gte=start_date)
    
    retention_data = []
    
    for i in range(months):
        period_start = start_date + timedelta(days=i * 30)
        period_end = period_start + timedelta(days=30)
        
        joined_in_period = members.filter(
            membership_date__gte=period_start,
            membership_date__lt=period_end
        )
        
        still_active = joined_in_period.filter(status='ACTIVE')
        
        total = joined_in_period.count()
        retained = still_active.count()
        
        retention_data.append({
            'period': period_start.strftime('%Y-%m'),
            'joined': total,
            'retained': retained,
            'retention_rate': (retained / total * 100) if total > 0 else 0,
        })
    
    return {
        'months_analyzed': months,
        'data': retention_data,
        'average_retention_rate': sum(d['retention_rate'] for d in retention_data) / len(retention_data) if retention_data else 0,
    }