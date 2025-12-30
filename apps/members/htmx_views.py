# members/htmx_views.py

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Count, Sum, Avg, F, DecimalField, Case, When, Max, Min, IntegerField
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from datetime import timedelta
from decimal import Decimal
import logging

from .models import (
    Member,
    MemberPaymentMethod,
    NextOfKin,
    MemberAdditionalContact,
    MemberGroup,
    GroupMembership
)
from core.utils import parse_filters, paginate_queryset, format_money

logger = logging.getLogger(__name__)


# =============================================================================
# MEMBER SEARCH
# =============================================================================

def member_search(request):
    """HTMX-compatible member search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'status', 'member_category', 'membership_plan', 'gender',
        'marital_status', 'employment_status', 'kyc_status', 'risk_rating',
        'membership_date_from', 'membership_date_to', 'min_age', 'max_age',
        'min_income', 'max_income', 'min_credit_score', 'max_credit_score',
        'has_kyc_documents', 'tax_exemption', 'nationality'
    ])
    
    query = filters['q']
    status = filters['status']
    member_category = filters['member_category']
    membership_plan = filters['membership_plan']
    gender = filters['gender']
    marital_status = filters['marital_status']
    employment_status = filters['employment_status']
    kyc_status = filters['kyc_status']
    risk_rating = filters['risk_rating']
    membership_date_from = filters['membership_date_from']
    membership_date_to = filters['membership_date_to']
    min_age = filters['min_age']
    max_age = filters['max_age']
    min_income = filters['min_income']
    max_income = filters['max_income']
    min_credit_score = filters['min_credit_score']
    max_credit_score = filters['max_credit_score']
    has_kyc_documents = filters['has_kyc_documents']
    tax_exemption = filters['tax_exemption']
    nationality = filters['nationality']
    
    # Build queryset
    members = Member.objects.annotate(
        savings_account_count=Count('savings_accounts', distinct=True),
        active_loan_count=Count(
            'loans',
            filter=Q(loans__status='ACTIVE'),
            distinct=True
        ),
        group_membership_count=Count(
            'groupmembership',  
            filter=Q(groupmembership__is_active=True),
            distinct=True
        ),
        payment_method_count=Count('payment_methods', distinct=True),
        next_of_kin_count=Count('next_of_kin', distinct=True)
    ).order_by('-membership_date', 'member_number')
    
    # Apply text search with multi-word support
    if query:
        # Split query into words and search for each word across fields
        words = query.strip().split()
        
        if words:
            # Build combined query: each word must match at least one field
            combined_q = Q()
            
            for word in words:
                word_q = (
                    Q(member_number__icontains=word) |
                    Q(first_name__icontains=word) |
                    Q(last_name__icontains=word) |
                    Q(middle_name__icontains=word) |
                    Q(id_number__icontains=word) |
                    Q(phone_primary__icontains=word) |
                    Q(personal_email__icontains=word) |
                    Q(tax_id__icontains=word)
                )
                combined_q &= word_q
            
            members = members.filter(combined_q)
    
    # Apply filters
    if status:
        members = members.filter(status=status)
    
    if member_category:
        members = members.filter(member_category=member_category)
    
    if membership_plan:
        members = members.filter(membership_plan=membership_plan)
    
    if gender:
        members = members.filter(gender=gender)
    
    if marital_status:
        members = members.filter(marital_status=marital_status)
    
    if employment_status:
        members = members.filter(employment_status=employment_status)
    
    if kyc_status:
        members = members.filter(kyc_status=kyc_status)
    
    if risk_rating:
        members = members.filter(risk_rating=risk_rating)
    
    if nationality:
        members = members.filter(nationality=nationality)
    
    # Date filters
    if membership_date_from:
        members = members.filter(membership_date__gte=membership_date_from)
    
    if membership_date_to:
        members = members.filter(membership_date__lte=membership_date_to)
    
    # Age filters
    if min_age or max_age:
        from datetime import date
        today = date.today()
        
        if max_age:
            try:
                min_birth_date = date(today.year - int(max_age), today.month, today.day)
                members = members.filter(date_of_birth__gte=min_birth_date)
            except (ValueError, TypeError):
                pass
        
        if min_age:
            try:
                max_birth_date = date(today.year - int(min_age), today.month, today.day)
                members = members.filter(date_of_birth__lte=max_birth_date)
            except (ValueError, TypeError):
                pass
    
    # Income filters
    if min_income:
        try:
            members = members.filter(monthly_income__gte=Decimal(min_income))
        except (ValueError, TypeError):
            pass
    
    if max_income:
        try:
            members = members.filter(monthly_income__lte=Decimal(max_income))
        except (ValueError, TypeError):
            pass
    
    # Credit score filters
    if min_credit_score:
        try:
            members = members.filter(credit_score__gte=int(min_credit_score))
        except (ValueError, TypeError):
            pass
    
    if max_credit_score:
        try:
            members = members.filter(credit_score__lte=int(max_credit_score))
        except (ValueError, TypeError):
            pass
    
    # Boolean filters
    if has_kyc_documents is not None:
        members = members.filter(kyc_documents_uploaded=(has_kyc_documents.lower() == 'true'))
    
    if tax_exemption is not None:
        members = members.filter(tax_exemption_status=(tax_exemption.lower() == 'true'))
    
    # Paginate
    members_page, paginator = paginate_queryset(request, members, per_page=20)
    
    # Calculate stats
    total = members.count()
    
    aggregates = members.aggregate(
        avg_age=Avg(
            Case(
                When(
                    date_of_birth__isnull=False,
                    then=timezone.now().year - F('date_of_birth__year')
                ),
                output_field=DecimalField()
            )
        ),
        avg_credit_score=Avg('credit_score'),
        avg_income=Avg('monthly_income'),
        total_income=Sum('monthly_income')
    )
    
    stats = {
        'total': total,
        'active': members.filter(status='ACTIVE').count(),
        'pending_approval': members.filter(status='PENDING_APPROVAL').count(),
        'dormant': members.filter(status='DORMANT').count(),
        'suspended': members.filter(status='SUSPENDED').count(),
        'blacklisted': members.filter(status='BLACKLISTED').count(),
        'male': members.filter(gender='MALE').count(),
        'female': members.filter(gender='FEMALE').count(),
        'kyc_verified': members.filter(kyc_status='VERIFIED').count(),
        'kyc_pending': members.filter(kyc_status='PENDING').count(),
        'high_risk': members.filter(risk_rating__in=['HIGH', 'VERY_HIGH']).count(),
        'low_risk': members.filter(risk_rating__in=['LOW', 'VERY_LOW']).count(),
        'avg_age': round(aggregates['avg_age'] or 0, 1),
        'avg_credit_score': round(aggregates['avg_credit_score'] or 0),
        'avg_income': aggregates['avg_income'] or Decimal('0.00'),
        'total_income': aggregates['total_income'] or Decimal('0.00'),
    }
    
    # Format money in stats
    stats['avg_income_formatted'] = format_money(stats['avg_income'])
    stats['total_income_formatted'] = format_money(stats['total_income'])
    
    return render(request, 'members/_member_results.html', {
        'members_page': members_page,
        'stats': stats,
    })


# =============================================================================
# MEMBER PAYMENT METHOD SEARCH
# =============================================================================

def payment_method_search(request):
    """HTMX-compatible payment method search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'member', 'method_type', 'is_primary', 'is_verified',
        'is_active', 'provider', 'account_type'
    ])
    
    query = filters['q']
    member = filters['member']
    method_type = filters['method_type']
    is_primary = filters['is_primary']
    is_verified = filters['is_verified']
    is_active = filters['is_active']
    provider = filters['provider']
    account_type = filters['account_type']
    
    # Build queryset
    payment_methods = MemberPaymentMethod.objects.select_related(
        'member'
    ).order_by('-is_primary', '-is_verified', 'member__last_name')
    
    # Apply text search with multi-word support
    if query:
        # Split query into words and search for each word across fields
        words = query.strip().split()
        
        if words:
            # Build combined query: each word must match at least one field
            combined_q = Q()
            
            for word in words:
                word_q = (
                    Q(member__first_name__icontains=word) |
                    Q(member__last_name__icontains=word) |
                    Q(member__member_number__icontains=word) |
                    Q(provider__icontains=word) |
                    Q(account_number__icontains=word) |
                    Q(account_name__icontains=word)
                )
                combined_q &= word_q
            
            payment_methods = payment_methods.filter(combined_q)
    
    # Apply filters
    if member:
        payment_methods = payment_methods.filter(member_id=member)
    
    if method_type:
        payment_methods = payment_methods.filter(method_type=method_type)
    
    if provider:
        payment_methods = payment_methods.filter(provider__icontains=provider)
    
    if account_type:
        payment_methods = payment_methods.filter(account_type=account_type)
    
    if is_primary is not None:
        payment_methods = payment_methods.filter(is_primary=(is_primary.lower() == 'true'))
    
    if is_verified is not None:
        payment_methods = payment_methods.filter(is_verified=(is_verified.lower() == 'true'))
    
    if is_active is not None:
        payment_methods = payment_methods.filter(is_active=(is_active.lower() == 'true'))
    
    # Paginate
    payment_methods_page, paginator = paginate_queryset(request, payment_methods, per_page=20)
    
    # Calculate stats
    total = payment_methods.count()
    
    stats = {
        'total': total,
        'primary': payment_methods.filter(is_primary=True).count(),
        'verified': payment_methods.filter(is_verified=True).count(),
        'active': payment_methods.filter(is_active=True).count(),
        'bank_accounts': payment_methods.filter(method_type='BANK_ACCOUNT').count(),
        'mobile_money': payment_methods.filter(method_type='MOBILE_MONEY').count(),
        'cash': payment_methods.filter(method_type='CASH').count(),
        'unique_members': payment_methods.values('member').distinct().count(),
    }
    
    return render(request, 'members/payment_methods/_payment_method_results.html', {
        'payment_methods_page': payment_methods_page,
        'stats': stats,
    })


# =============================================================================
# NEXT OF KIN SEARCH
# =============================================================================

def next_of_kin_search(request):
    """HTMX-compatible next of kin search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'member', 'relation', 'is_primary', 'is_emergency_contact',
        'is_beneficiary', 'min_percentage', 'max_percentage'
    ])
    
    query = filters['q']
    member = filters['member']
    relation = filters['relation']
    is_primary = filters['is_primary']
    is_emergency_contact = filters['is_emergency_contact']
    is_beneficiary = filters['is_beneficiary']
    min_percentage = filters['min_percentage']
    max_percentage = filters['max_percentage']
    
    # Build queryset
    next_of_kin = NextOfKin.objects.select_related(
        'member'
    ).order_by('-is_primary', 'member__last_name', 'name')
    
    # Apply text search with multi-word support
    if query:
        # Split query into words and search for each word across fields
        words = query.strip().split()
        
        if words:
            # Build combined query: each word must match at least one field
            combined_q = Q()
            
            for word in words:
                word_q = (
                    Q(name__icontains=word) |
                    Q(member__first_name__icontains=word) |
                    Q(member__last_name__icontains=word) |
                    Q(member__member_number__icontains=word) |
                    Q(contact__icontains=word) |
                    Q(email__icontains=word) |
                    Q(id_number__icontains=word)
                )
                combined_q &= word_q
            
            next_of_kin = next_of_kin.filter(combined_q)
    
    # Apply filters
    if member:
        next_of_kin = next_of_kin.filter(member_id=member)
    
    if relation:
        next_of_kin = next_of_kin.filter(relation=relation)
    
    if is_primary is not None:
        next_of_kin = next_of_kin.filter(is_primary=(is_primary.lower() == 'true'))
    
    if is_emergency_contact is not None:
        next_of_kin = next_of_kin.filter(is_emergency_contact=(is_emergency_contact.lower() == 'true'))
    
    if is_beneficiary is not None:
        next_of_kin = next_of_kin.filter(is_beneficiary=(is_beneficiary.lower() == 'true'))
    
    # Percentage filters
    if min_percentage:
        try:
            next_of_kin = next_of_kin.filter(beneficiary_percentage__gte=Decimal(min_percentage))
        except (ValueError, TypeError):
            pass
    
    if max_percentage:
        try:
            next_of_kin = next_of_kin.filter(beneficiary_percentage__lte=Decimal(max_percentage))
        except (ValueError, TypeError):
            pass
    
    # Paginate
    next_of_kin_page, paginator = paginate_queryset(request, next_of_kin, per_page=20)
    
    # Calculate stats
    total = next_of_kin.count()
    
    aggregates = next_of_kin.filter(is_beneficiary=True).aggregate(
        total_percentage=Sum('beneficiary_percentage'),
        avg_percentage=Avg('beneficiary_percentage')
    )
    
    # Relation breakdown
    relation_counts = {}
    for rel in NextOfKin.RELATION_CHOICES:
        count = next_of_kin.filter(relation=rel[0]).count()
        if count > 0:
            relation_counts[rel[1]] = count
    
    stats = {
        'total': total,
        'primary': next_of_kin.filter(is_primary=True).count(),
        'emergency_contacts': next_of_kin.filter(is_emergency_contact=True).count(),
        'beneficiaries': next_of_kin.filter(is_beneficiary=True).count(),
        'unique_members': next_of_kin.values('member').distinct().count(),
        'avg_beneficiary_percentage': aggregates['avg_percentage'] or Decimal('0.00'),
        'relation_counts': relation_counts,
    }
    
    return render(request, 'members/next_of_kin/_next_of_kin_results.html', {
        'next_of_kin_page': next_of_kin_page,
        'stats': stats,
    })


# =============================================================================
# MEMBER ADDITIONAL CONTACT SEARCH
# =============================================================================

def additional_contact_search(request):
    """HTMX-compatible additional contact search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'member', 'contact_type', 'is_verified', 'is_active'
    ])
    
    query = filters['q']
    member = filters['member']
    contact_type = filters['contact_type']
    is_verified = filters['is_verified']
    is_active = filters['is_active']
    
    # Build queryset
    contacts = MemberAdditionalContact.objects.select_related(
        'member'
    ).order_by('member__last_name', 'contact_type')
    
    # Apply text search with multi-word support
    if query:
        # Split query into words and search for each word across fields
        words = query.strip().split()
        
        if words:
            # Build combined query: each word must match at least one field
            combined_q = Q()
            
            for word in words:
                word_q = (
                    Q(member__first_name__icontains=word) |
                    Q(member__last_name__icontains=word) |
                    Q(member__member_number__icontains=word) |
                    Q(contact_value__icontains=word)
                )
                combined_q &= word_q
            
            contacts = contacts.filter(combined_q)
    
    # Apply filters
    if member:
        contacts = contacts.filter(member_id=member)
    
    if contact_type:
        contacts = contacts.filter(contact_type=contact_type)
    
    if is_verified is not None:
        contacts = contacts.filter(is_verified=(is_verified.lower() == 'true'))
    
    if is_active is not None:
        contacts = contacts.filter(is_active=(is_active.lower() == 'true'))
    
    # Paginate
    contacts_page, paginator = paginate_queryset(request, contacts, per_page=20)
    
    # Calculate stats
    total = contacts.count()
    
    # Type breakdown
    type_counts = {}
    for ctype in MemberAdditionalContact.CONTACT_TYPE_CHOICES:
        count = contacts.filter(contact_type=ctype[0]).count()
        if count > 0:
            type_counts[ctype[1]] = count
    
    stats = {
        'total': total,
        'verified': contacts.filter(is_verified=True).count(),
        'active': contacts.filter(is_active=True).count(),
        'unique_members': contacts.values('member').distinct().count(),
        'type_counts': type_counts,
    }
    
    return render(request, 'members/additional_contacts/_contact_results.html', {
        'contacts_page': contacts_page,
        'stats': stats,
    })


# =============================================================================
# MEMBER GROUP SEARCH
# =============================================================================

def member_group_search(request):
    """HTMX-compatible member group search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'group_type', 'is_active', 'is_full', 'meeting_frequency',
        'formation_date_from', 'formation_date_to', 'min_members', 'max_members',
        'min_contribution', 'max_contribution'
    ])
    
    query = filters['q']
    group_type = filters['group_type']
    is_active = filters['is_active']
    is_full = filters['is_full']
    meeting_frequency = filters['meeting_frequency']
    formation_date_from = filters['formation_date_from']
    formation_date_to = filters['formation_date_to']
    min_members = filters['min_members']
    max_members = filters['max_members']
    min_contribution = filters['min_contribution']
    max_contribution = filters['max_contribution']
    
    # Build queryset
    groups = MemberGroup.objects.select_related(
        'group_leader',
        'group_secretary',
        'group_treasurer'
    ).annotate(
        active_member_count=Count(
            'groupmembership',
            filter=Q(groupmembership__is_active=True),
            distinct=True
        ),
        total_contributions=Sum('groupmembership__total_contributions')
    ).order_by('-is_active', 'name')
    
    # Apply text search with multi-word support
    if query:
        # Split query into words and search for each word across fields
        words = query.strip().split()
        
        if words:
            # Build combined query: each word must match at least one field
            combined_q = Q()
            
            for word in words:
                word_q = (
                    Q(name__icontains=word) |
                    Q(description__icontains=word) |
                    Q(group_leader__first_name__icontains=word) |
                    Q(group_leader__last_name__icontains=word)
                )
                combined_q &= word_q
            
            groups = groups.filter(combined_q)
    
    # Apply filters
    if group_type:
        groups = groups.filter(group_type=group_type)
    
    if meeting_frequency:
        groups = groups.filter(meeting_frequency=meeting_frequency)
    
    if is_active is not None:
        groups = groups.filter(is_active=(is_active.lower() == 'true'))
    
    if is_full is not None:
        groups = groups.filter(is_full=(is_full.lower() == 'true'))
    
    # Date filters
    if formation_date_from:
        groups = groups.filter(formation_date__gte=formation_date_from)
    
    if formation_date_to:
        groups = groups.filter(formation_date__lte=formation_date_to)
    
    # Member count filters
    if min_members:
        try:
            groups = groups.filter(active_member_count__gte=int(min_members))
        except (ValueError, TypeError):
            pass
    
    if max_members:
        try:
            groups = groups.filter(active_member_count__lte=int(max_members))
        except (ValueError, TypeError):
            pass
    
    # Contribution filters
    if min_contribution:
        try:
            groups = groups.filter(minimum_contribution__gte=Decimal(min_contribution))
        except (ValueError, TypeError):
            pass
    
    if max_contribution:
        try:
            groups = groups.filter(minimum_contribution__lte=Decimal(max_contribution))
        except (ValueError, TypeError):
            pass
    
    # Paginate
    groups_page, paginator = paginate_queryset(request, groups, per_page=20)
    
    # Calculate stats
    total = groups.count()
    
    aggregates = groups.aggregate(
        total_members=Sum('active_member_count'),
        avg_members=Avg('active_member_count'),
        total_contributions_sum=Sum('total_contributions'),
        avg_contribution=Avg('minimum_contribution')
    )
    
    # Type breakdown
    type_counts = {}
    for gtype in MemberGroup.GROUP_TYPE_CHOICES:
        count = groups.filter(group_type=gtype[0]).count()
        if count > 0:
            type_counts[gtype[1]] = count
    
    stats = {
        'total': total,
        'active': groups.filter(is_active=True).count(),
        'full': groups.filter(is_full=True).count(),
        'with_leader': groups.exclude(group_leader__isnull=True).count(),
        'total_members': aggregates['total_members'] or 0,
        'avg_members': round(aggregates['avg_members'] or 0, 1),
        'total_contributions': aggregates['total_contributions_sum'] or Decimal('0.00'),
        'avg_contribution': aggregates['avg_contribution'] or Decimal('0.00'),
        'type_counts': type_counts,
    }
    
    # Format money in stats
    stats['total_contributions_formatted'] = format_money(stats['total_contributions'])
    stats['avg_contribution_formatted'] = format_money(stats['avg_contribution'])
    
    return render(request, 'members/groups/_group_results.html', {
        'groups_page': groups_page,
        'stats': stats,
    })


# =============================================================================
# GROUP MEMBERSHIP SEARCH
# =============================================================================

def group_membership_search(request):
    """HTMX-compatible group membership search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'member', 'group', 'role', 'status', 'is_active',
        'join_date_from', 'join_date_to', 'min_contribution', 'max_contribution',
        'min_attendance', 'max_attendance'
    ])
    
    query = filters['q']
    member = filters['member']
    group = filters['group']
    role = filters['role']
    status = filters['status']
    is_active = filters['is_active']
    join_date_from = filters['join_date_from']
    join_date_to = filters['join_date_to']
    min_contribution = filters['min_contribution']
    max_contribution = filters['max_contribution']
    min_attendance = filters['min_attendance']
    max_attendance = filters['max_attendance']
    
    # Build queryset
    memberships = GroupMembership.objects.select_related(
        'member',
        'group'
    ).order_by('-is_active', 'group__name', 'member__last_name')
    
    # Apply text search with multi-word support
    if query:
        # Split query into words and search for each word across fields
        words = query.strip().split()
        
        if words:
            # Build combined query: each word must match at least one field
            combined_q = Q()
            
            for word in words:
                word_q = (
                    Q(member__first_name__icontains=word) |
                    Q(member__last_name__icontains=word) |
                    Q(member__member_number__icontains=word) |
                    Q(group__name__icontains=word)
                )
                combined_q &= word_q
            
            memberships = memberships.filter(combined_q)
    
    # Apply filters
    if member:
        memberships = memberships.filter(member_id=member)
    
    if group:
        memberships = memberships.filter(group_id=group)
    
    if role:
        memberships = memberships.filter(role=role)
    
    if status:
        memberships = memberships.filter(status=status)
    
    if is_active is not None:
        memberships = memberships.filter(is_active=(is_active.lower() == 'true'))
    
    # Date filters
    if join_date_from:
        memberships = memberships.filter(join_date__gte=join_date_from)
    
    if join_date_to:
        memberships = memberships.filter(join_date__lte=join_date_to)
    
    # Contribution filters
    if min_contribution:
        try:
            memberships = memberships.filter(total_contributions__gte=Decimal(min_contribution))
        except (ValueError, TypeError):
            pass
    
    if max_contribution:
        try:
            memberships = memberships.filter(total_contributions__lte=Decimal(max_contribution))
        except (ValueError, TypeError):
            pass
    
    # Attendance filters
    if min_attendance:
        try:
            memberships = memberships.filter(meeting_attendance_rate__gte=Decimal(min_attendance))
        except (ValueError, TypeError):
            pass
    
    if max_attendance:
        try:
            memberships = memberships.filter(meeting_attendance_rate__lte=Decimal(max_attendance))
        except (ValueError, TypeError):
            pass
    
    # Paginate
    memberships_page, paginator = paginate_queryset(request, memberships, per_page=20)
    
    # Calculate stats
    total = memberships.count()
    
    aggregates = memberships.aggregate(
        total_contributions_sum=Sum('total_contributions'),
        avg_contributions=Avg('total_contributions'),
        avg_attendance=Avg('meeting_attendance_rate')
    )
    
    # Role breakdown
    role_counts = {}
    for r in GroupMembership.ROLE_CHOICES:
        count = memberships.filter(role=r[0]).count()
        if count > 0:
            role_counts[r[1]] = count
    
    stats = {
        'total': total,
        'active': memberships.filter(is_active=True).count(),
        'suspended': memberships.filter(status='SUSPENDED').count(),
        'resigned': memberships.filter(status='RESIGNED').count(),
        'leaders': memberships.filter(role='LEADER').count(),
        'total_contributions': aggregates['total_contributions_sum'] or Decimal('0.00'),
        'avg_contributions': aggregates['avg_contributions'] or Decimal('0.00'),
        'avg_attendance': round(aggregates['avg_attendance'] or 0, 1),
        'unique_members': memberships.values('member').distinct().count(),
        'unique_groups': memberships.values('group').distinct().count(),
        'role_counts': role_counts,
    }
    
    # Format money in stats
    stats['total_contributions_formatted'] = format_money(stats['total_contributions'])
    stats['avg_contributions_formatted'] = format_money(stats['avg_contributions'])
    
    return render(request, 'members/memberships/_membership_results.html', {
        'memberships_page': memberships_page,
        'stats': stats,
    })


# =============================================================================
# QUICK STATS ENDPOINTS
# =============================================================================

@require_http_methods(["GET"])
def member_quick_stats(request):
    """Get quick statistics for members"""
    
    today = timezone.now().date()
    
    aggregates = Member.objects.aggregate(
        avg_credit_score=Avg('credit_score'),
        avg_income=Avg('monthly_income')
    )
    
    # This month's new members
    first_day_of_month = today.replace(day=1)
    new_this_month = Member.objects.filter(
        membership_date__gte=first_day_of_month
    ).count()
    
    stats = {
        'total_members': Member.objects.count(),
        'active': Member.objects.filter(status='ACTIVE').count(),
        'pending_approval': Member.objects.filter(status='PENDING_APPROVAL').count(),
        'dormant': Member.objects.filter(status='DORMANT').count(),
        'suspended': Member.objects.filter(status='SUSPENDED').count(),
        'kyc_verified': Member.objects.filter(kyc_status='VERIFIED').count(),
        'kyc_pending': Member.objects.filter(kyc_status='PENDING').count(),
        'high_risk': Member.objects.filter(risk_rating__in=['HIGH', 'VERY_HIGH']).count(),
        'new_this_month': new_this_month,
        'avg_credit_score': round(aggregates['avg_credit_score'] or 0),
        'avg_income': str(aggregates['avg_income'] or Decimal('0.00')),
        'avg_income_formatted': format_money(aggregates['avg_income'] or Decimal('0.00')),
    }
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def payment_method_quick_stats(request):
    """Get quick statistics for payment methods"""
    
    stats = {
        'total': MemberPaymentMethod.objects.count(),
        'verified': MemberPaymentMethod.objects.filter(is_verified=True).count(),
        'active': MemberPaymentMethod.objects.filter(is_active=True).count(),
        'bank_accounts': MemberPaymentMethod.objects.filter(method_type='BANK_ACCOUNT').count(),
        'mobile_money': MemberPaymentMethod.objects.filter(method_type='MOBILE_MONEY').count(),
        'unique_members': MemberPaymentMethod.objects.values('member').distinct().count(),
    }
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def member_group_quick_stats(request):
    """Get quick statistics for member groups"""
    
    aggregates = MemberGroup.objects.aggregate(
        total_members=Sum(
            Case(
                When(is_active=True, then=Count('groupmembership', filter=Q(groupmembership__is_active=True))),
                default=0,
                output_field=IntegerField()
            )
        ),
        avg_members=Avg(
            Count('groupmembership', filter=Q(groupmembership__is_active=True))
        )
    )
    
    stats = {
        'total_groups': MemberGroup.objects.count(),
        'active': MemberGroup.objects.filter(is_active=True).count(),
        'full': MemberGroup.objects.filter(is_full=True).count(),
        'lending_circles': MemberGroup.objects.filter(group_type='LENDING_CIRCLE').count(),
        'savings_groups': MemberGroup.objects.filter(group_type='SAVINGS_GROUP').count(),
        'total_members': GroupMembership.objects.filter(is_active=True).count(),
        'unique_members': GroupMembership.objects.filter(is_active=True).values('member').distinct().count(),
    }
    
    return JsonResponse(stats)


# =============================================================================
# MEMBER-SPECIFIC STATS
# =============================================================================

@require_http_methods(["GET"])
def member_detail_stats(request, member_id):
    """Get detailed statistics for a specific member"""
    
    member = get_object_or_404(Member, id=member_id)
    
    stats = {
        'member_number': member.member_number,
        'full_name': member.get_full_name(),
        'status': member.get_status_display(),
        'age': member.age,
        'membership_duration_years': round(member.membership_duration_years, 1),
        'credit_score': member.credit_score,
        'risk_rating': member.get_risk_rating_display(),
        'monthly_income': str(member.monthly_income) if member.monthly_income else None,
        'monthly_income_formatted': format_money(member.monthly_income) if member.monthly_income else None,
        'kyc_status': member.get_kyc_status_display(),
        'kyc_verified': member.is_kyc_verified,
        
        # Related counts
        'savings_accounts': member.savings_accounts.count(),
        'active_loans': member.get_active_loans_count(),
        'payment_methods': member.payment_methods.filter(is_active=True).count(),
        'next_of_kin': member.next_of_kin.count(),
        'group_memberships': member.group_memberships.filter(is_active=True).count(),
        
        # Financial aggregates
        'total_savings': str(member.get_total_savings()),
        'total_savings_formatted': member.formatted_total_savings,
        'total_loans': str(member.get_total_loans()),
        'total_loans_formatted': member.formatted_total_loans,
        'total_dividends': str(member.get_total_dividends()),
        'total_dividends_formatted': member.formatted_total_dividends,
    }
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def member_group_detail_stats(request, group_id):
    """Get detailed statistics for a specific member group"""
    
    group = get_object_or_404(MemberGroup, id=group_id)
    
    aggregates = group.groupmembership_set.filter(is_active=True).aggregate(
        total_contributions=Sum('total_contributions'),
        avg_contributions=Avg('total_contributions'),
        avg_attendance=Avg('meeting_attendance_rate')
    )
    
    stats = {
        'name': group.name,
        'group_type': group.get_group_type_display(),
        'is_active': group.is_active,
        'is_full': group.is_full,
        'formation_date': str(group.formation_date),
        'group_age_days': group.group_age_days,
        'member_count': group.member_count,
        'available_slots': group.available_slots,
        'minimum_contribution': str(group.minimum_contribution),
        'minimum_contribution_formatted': group.formatted_minimum_contribution,
        'maximum_loan_amount': str(group.maximum_loan_amount),
        'maximum_loan_amount_formatted': group.formatted_maximum_loan_amount,
        'total_contributions': str(aggregates['total_contributions'] or Decimal('0.00')),
        'total_contributions_formatted': format_money(aggregates['total_contributions'] or Decimal('0.00')),
        'avg_contributions': str(aggregates['avg_contributions'] or Decimal('0.00')),
        'avg_contributions_formatted': format_money(aggregates['avg_contributions'] or Decimal('0.00')),
        'avg_attendance': round(aggregates['avg_attendance'] or 0, 1),
        'leader': group.group_leader.get_full_name() if group.group_leader else None,
        'secretary': group.group_secretary.get_full_name() if group.group_secretary else None,
        'treasurer': group.group_treasurer.get_full_name() if group.group_treasurer else None,
    }
    
    return JsonResponse(stats)