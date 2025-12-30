# members/ajax_views.py

from django.http import JsonResponse
from django.db.models import Q
import logging

from .models import (
    Member, 
    MemberPaymentMethod, 
    NextOfKin, 
    MemberGroup,
    GroupMembership
)
from utils.utils import parse_filters, paginate_queryset
from .stats import (
    get_member_statistics,
    get_payment_method_statistics,
    get_next_of_kin_statistics,
    get_group_statistics,
)

logger = logging.getLogger(__name__)


# =============================================================================
# MEMBER SEARCH
# =============================================================================

def member_search(request):
    """
    AJAX view to return filtered members as JSON with statistics
    """
    # Extract filters using parse_filters
    filters = parse_filters(request, [
        'q', 'status', 'member_category', 'membership_plan', 
        'gender', 'employment_status', 'kyc_status', 'risk_rating',
        'min_age', 'max_age', 'page'
    ])
    
    query = filters['q']
    status = filters['status']
    member_category = filters['member_category']
    membership_plan = filters['membership_plan']
    gender = filters['gender']
    employment_status = filters['employment_status']
    kyc_status = filters['kyc_status']
    risk_rating = filters['risk_rating']
    min_age = filters['min_age']
    max_age = filters['max_age']
    page = filters['page'] or 1

    # Start with all members
    members = Member.objects.all().select_related().order_by('-created_at')

    # Apply text search
    if query:
        members = members.filter(
            Q(member_number__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(middle_name__icontains=query) |
            Q(id_number__icontains=query) |
            Q(phone_primary__icontains=query) |
            Q(personal_email__icontains=query)
        )

    # Apply filters
    if status:
        members = members.filter(status=status)
    if member_category:
        members = members.filter(member_category=member_category)
    if membership_plan:
        members = members.filter(membership_plan=membership_plan)
    if gender:
        members = members.filter(gender=gender)
    if employment_status:
        members = members.filter(employment_status=employment_status)
    if kyc_status:
        members = members.filter(kyc_status=kyc_status)
    if risk_rating:
        members = members.filter(risk_rating=risk_rating)
    
    # Age filters
    if min_age:
        try:
            from datetime import date
            min_age_int = int(min_age)
            max_birth_date = date.today().replace(year=date.today().year - min_age_int)
            members = members.filter(date_of_birth__lte=max_birth_date)
        except (ValueError, TypeError):
            pass
    
    if max_age:
        try:
            from datetime import date
            max_age_int = int(max_age)
            min_birth_date = date.today().replace(year=date.today().year - max_age_int - 1)
            members = members.filter(date_of_birth__gte=min_birth_date)
        except (ValueError, TypeError):
            pass

    # Get comprehensive statistics using statistics module
    stats_filters = {}
    if status:
        stats_filters['status'] = status
    if member_category:
        stats_filters['member_category'] = member_category
    if membership_plan:
        stats_filters['membership_plan'] = membership_plan
    if gender:
        stats_filters['gender'] = gender
    if employment_status:
        stats_filters['employment_status'] = employment_status
    if kyc_status:
        stats_filters['kyc_status'] = kyc_status
    if risk_rating:
        stats_filters['risk_rating'] = risk_rating
    if min_age:
        try:
            stats_filters['min_age'] = int(min_age)
        except (ValueError, TypeError):
            pass
    if max_age:
        try:
            stats_filters['max_age'] = int(max_age)
        except (ValueError, TypeError):
            pass
    
    try:
        stats = get_member_statistics(filters=stats_filters if stats_filters else None)
    except Exception as e:
        logger.error(f"Error getting member statistics: {e}")
        stats = {
            'total_members': members.count(),
            'active_members': 0,
            'pending_approval': 0,
        }

    # Handle pagination (or return all)
    if page == 'all':
        member_list = []
        for m in members:
            try:
                member_list.append(serialize_member_data(m))
            except Exception as e:
                logger.error(f"Error serializing member {m.id}: {e}")
                continue
        
        return JsonResponse({
            'members': member_list,
            'total_count': members.count(),
            'stats': stats,
        })

    # Paginated response
    members_page, paginator = paginate_queryset(request, members, per_page=10)

    member_list = []
    for m in members_page:
        try:
            member_list.append(serialize_member_data(m))
        except Exception as e:
            logger.error(f"Error serializing member {m.id}: {e}")
            continue

    return JsonResponse({
        'members': member_list,
        'current_page': members_page.number,
        'total_pages': paginator.num_pages,
        'total_count': paginator.count,
        'has_previous': members_page.has_previous(),
        'has_next': members_page.has_next(),
        'start_index': members_page.start_index(),
        'end_index': members_page.end_index(),
        'stats': stats,
    })


def serialize_member_data(m):
    """
    Helper function to serialize a Member object to match frontend expectations
    """
    # Get display values
    try:
        status_display = m.get_status_display()
    except Exception:
        status_display = m.status
    
    try:
        category_display = m.get_member_category_display()
    except Exception:
        category_display = m.member_category
    
    try:
        plan_display = m.get_membership_plan_display()
    except Exception:
        plan_display = m.membership_plan
    
    try:
        gender_display = m.get_gender_display()
    except Exception:
        gender_display = m.gender
    
    try:
        employment_display = m.get_employment_status_display()
    except Exception:
        employment_display = m.employment_status
    
    try:
        kyc_display = m.get_kyc_status_display()
    except Exception:
        kyc_display = m.kyc_status
    
    try:
        risk_display = m.get_risk_rating_display()
    except Exception:
        risk_display = m.risk_rating
    
    # Format dates
    membership_date_str = m.membership_date.strftime('%b %d, %Y') if m.membership_date else None
    dob_str = m.date_of_birth.strftime('%b %d, %Y') if m.date_of_birth else None
    
    # Get age and duration
    try:
        age = m.age
    except:
        age = None
    
    try:
        membership_duration = m.membership_duration_days
    except:
        membership_duration = None
    
    return {
        'id': str(m.id),
        'member_number': m.member_number,
        'full_name': m.get_full_name(),
        'display_name': m.display_name,
        'first_name': m.first_name,
        'last_name': m.last_name,
        'middle_name': m.middle_name,
        'id_number': m.id_number,
        'id_type': m.id_type,
        'date_of_birth': dob_str,
        'age': age,
        'gender': m.gender,
        'gender_display': gender_display,
        'status': m.status,
        'status_display': status_display,
        'member_category': m.member_category,
        'category_display': category_display,
        'membership_plan': m.membership_plan,
        'plan_display': plan_display,
        'membership_date': membership_date_str,
        'membership_duration_days': membership_duration,
        'employment_status': m.employment_status,
        'employment_display': employment_display,
        'occupation': m.occupation,
        'employer': m.employer,
        'monthly_income': float(m.monthly_income) if m.monthly_income else None,
        'phone_primary': m.phone_primary,
        'personal_email': m.personal_email,
        'city': m.city,
        'country': str(m.country.name) if m.country else None,
        'kyc_status': m.kyc_status,
        'kyc_display': kyc_display,
        'credit_score': m.credit_score,
        'risk_rating': m.risk_rating,
        'risk_display': risk_display,
        'is_active': m.is_active,
        'is_kyc_verified': m.is_kyc_verified,
        'member_photo': m.member_photo.url if m.member_photo else None,
    }


# =============================================================================
# PAYMENT METHOD SEARCH
# =============================================================================

def payment_method_search(request):
    """
    AJAX view to return filtered payment methods as JSON with statistics
    """
    # Extract filters using parse_filters
    filters = parse_filters(request, [
        'q', 'member', 'method_type', 'is_verified', 'is_primary', 'page'
    ])
    
    query = filters['q']
    member_id = filters['member']
    method_type = filters['method_type']
    is_verified = filters['is_verified']
    is_primary = filters['is_primary']
    page = filters['page'] or 1

    # Start with all payment methods
    payment_methods = MemberPaymentMethod.objects.all().select_related('member').order_by(
        '-is_primary', '-is_verified', 'provider'
    )

    # Apply text search
    if query:
        payment_methods = payment_methods.filter(
            Q(provider__icontains=query) |
            Q(account_number__icontains=query) |
            Q(account_name__icontains=query) |
            Q(member__member_number__icontains=query) |
            Q(member__first_name__icontains=query) |
            Q(member__last_name__icontains=query)
        )

    # Apply filters
    if member_id:
        payment_methods = payment_methods.filter(member_id=member_id)
    if method_type:
        payment_methods = payment_methods.filter(method_type=method_type)
    if is_verified is not None:
        payment_methods = payment_methods.filter(is_verified=(is_verified.lower() == 'true'))
    if is_primary is not None:
        payment_methods = payment_methods.filter(is_primary=(is_primary.lower() == 'true'))

    # Get comprehensive statistics using statistics module
    stats_filters = {}
    if member_id:
        stats_filters['member'] = member_id
    if method_type:
        stats_filters['method_type'] = method_type
    if is_verified is not None:
        stats_filters['is_verified'] = (is_verified.lower() == 'true')
    
    try:
        stats = get_payment_method_statistics(filters=stats_filters if stats_filters else None)
    except Exception as e:
        logger.error(f"Error getting payment method statistics: {e}")
        stats = {
            'total_payment_methods': payment_methods.count(),
            'verified_methods': 0,
        }

    # Handle pagination (or return all)
    if page == 'all':
        method_list = []
        for pm in payment_methods:
            try:
                method_list.append(serialize_payment_method_data(pm))
            except Exception as e:
                logger.error(f"Error serializing payment method {pm.id}: {e}")
                continue
        
        return JsonResponse({
            'payment_methods': method_list,
            'total_count': payment_methods.count(),
            'stats': stats,
        })

    # Paginated response
    methods_page, paginator = paginate_queryset(request, payment_methods, per_page=10)

    method_list = []
    for pm in methods_page:
        try:
            method_list.append(serialize_payment_method_data(pm))
        except Exception as e:
            logger.error(f"Error serializing payment method {pm.id}: {e}")
            continue

    return JsonResponse({
        'payment_methods': method_list,
        'current_page': methods_page.number,
        'total_pages': paginator.num_pages,
        'total_count': paginator.count,
        'has_previous': methods_page.has_previous(),
        'has_next': methods_page.has_next(),
        'start_index': methods_page.start_index(),
        'end_index': methods_page.end_index(),
        'stats': stats,
    })


def serialize_payment_method_data(pm):
    """
    Helper function to serialize a MemberPaymentMethod object
    """
    try:
        method_type_display = pm.get_method_type_display()
    except Exception:
        method_type_display = pm.method_type
    
    try:
        account_type_display = pm.get_account_type_display() if pm.account_type else None
    except Exception:
        account_type_display = pm.account_type
    
    return {
        'id': str(pm.id),
        'member_id': str(pm.member.id),
        'member_name': pm.member.get_full_name(),
        'member_number': pm.member.member_number,
        'method_type': pm.method_type,
        'method_type_display': method_type_display,
        'provider': pm.provider,
        'account_number': pm.account_number,
        'masked_account_number': pm.masked_account_number,
        'account_name': pm.account_name,
        'account_type': pm.account_type,
        'account_type_display': account_type_display,
        'branch': pm.branch,
        'is_primary': pm.is_primary,
        'is_verified': pm.is_verified,
        'verified_date': pm.verified_date.strftime('%b %d, %Y') if pm.verified_date else None,
        'is_active': pm.is_active,
        'notes': pm.notes[:100] if pm.notes else None,
    }


# =============================================================================
# NEXT OF KIN SEARCH
# =============================================================================

def next_of_kin_search(request):
    """
    AJAX view to return filtered next of kin as JSON with statistics
    """
    # Extract filters using parse_filters
    filters = parse_filters(request, [
        'q', 'member', 'relation', 'is_primary', 'is_emergency_contact', 
        'is_beneficiary', 'page'
    ])
    
    query = filters['q']
    member_id = filters['member']
    relation = filters['relation']
    is_primary = filters['is_primary']
    is_emergency = filters['is_emergency_contact']
    is_beneficiary = filters['is_beneficiary']
    page = filters['page'] or 1

    # Start with all next of kin
    next_of_kin = NextOfKin.objects.all().select_related('member').order_by(
        'member__member_number', '-is_primary', 'name'
    )

    # Apply text search
    if query:
        next_of_kin = next_of_kin.filter(
            Q(name__icontains=query) |
            Q(contact__icontains=query) |
            Q(email__icontains=query) |
            Q(id_number__icontains=query) |
            Q(member__member_number__icontains=query) |
            Q(member__first_name__icontains=query) |
            Q(member__last_name__icontains=query)
        )

    # Apply filters
    if member_id:
        next_of_kin = next_of_kin.filter(member_id=member_id)
    if relation:
        next_of_kin = next_of_kin.filter(relation=relation)
    if is_primary is not None:
        next_of_kin = next_of_kin.filter(is_primary=(is_primary.lower() == 'true'))
    if is_emergency is not None:
        next_of_kin = next_of_kin.filter(is_emergency_contact=(is_emergency.lower() == 'true'))
    if is_beneficiary is not None:
        next_of_kin = next_of_kin.filter(is_beneficiary=(is_beneficiary.lower() == 'true'))

    # Get comprehensive statistics using statistics module
    stats_filters = {}
    if member_id:
        stats_filters['member'] = member_id
    if relation:
        stats_filters['relation'] = relation
    if is_primary is not None:
        stats_filters['is_primary'] = (is_primary.lower() == 'true')
    
    try:
        stats = get_next_of_kin_statistics(filters=stats_filters if stats_filters else None)
    except Exception as e:
        logger.error(f"Error getting next of kin statistics: {e}")
        stats = {
            'total_next_of_kin': next_of_kin.count(),
            'primary_contacts': 0,
        }

    # Handle pagination (or return all)
    if page == 'all':
        nok_list = []
        for nok in next_of_kin:
            try:
                nok_list.append(serialize_next_of_kin_data(nok))
            except Exception as e:
                logger.error(f"Error serializing next of kin {nok.id}: {e}")
                continue
        
        return JsonResponse({
            'next_of_kin': nok_list,
            'total_count': next_of_kin.count(),
            'stats': stats,
        })

    # Paginated response
    nok_page, paginator = paginate_queryset(request, next_of_kin, per_page=10)

    nok_list = []
    for nok in nok_page:
        try:
            nok_list.append(serialize_next_of_kin_data(nok))
        except Exception as e:
            logger.error(f"Error serializing next of kin {nok.id}: {e}")
            continue

    return JsonResponse({
        'next_of_kin': nok_list,
        'current_page': nok_page.number,
        'total_pages': paginator.num_pages,
        'total_count': paginator.count,
        'has_previous': nok_page.has_previous(),
        'has_next': nok_page.has_next(),
        'start_index': nok_page.start_index(),
        'end_index': nok_page.end_index(),
        'stats': stats,
    })


def serialize_next_of_kin_data(nok):
    """
    Helper function to serialize a NextOfKin object
    """
    try:
        relation_display = nok.get_relation_display()
    except Exception:
        relation_display = nok.relation
    
    return {
        'id': str(nok.id),
        'member_id': str(nok.member.id),
        'member_name': nok.member.get_full_name(),
        'member_number': nok.member.member_number,
        'name': nok.name,
        'relation': nok.relation,
        'relation_display': relation_display,
        'contact': nok.contact,
        'email': nok.email,
        'address': nok.address[:100] if nok.address else None,
        'id_number': nok.id_number,
        'date_of_birth': nok.date_of_birth.strftime('%b %d, %Y') if nok.date_of_birth else None,
        'age': nok.age,
        'is_primary': nok.is_primary,
        'is_emergency_contact': nok.is_emergency_contact,
        'is_beneficiary': nok.is_beneficiary,
        'beneficiary_percentage': float(nok.beneficiary_percentage) if nok.is_beneficiary else 0,
        'notes': nok.notes[:100] if nok.notes else None,
    }


# =============================================================================
# GROUP SEARCH
# =============================================================================

def group_search(request):
    """
    AJAX view to return filtered groups as JSON with statistics
    """
    # Extract filters using parse_filters
    filters = parse_filters(request, [
        'q', 'group_type', 'is_active', 'is_full', 'page'
    ])
    
    query = filters['q']
    group_type = filters['group_type']
    is_active = filters['is_active']
    is_full = filters['is_full']
    page = filters['page'] or 1

    # Start with all groups
    groups = MemberGroup.objects.all().select_related(
        'group_leader', 'group_secretary', 'group_treasurer'
    ).order_by('-created_at')

    # Apply text search
    if query:
        groups = groups.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        )

    # Apply filters
    if group_type:
        groups = groups.filter(group_type=group_type)
    if is_active is not None:
        groups = groups.filter(is_active=(is_active.lower() == 'true'))
    if is_full is not None:
        groups = groups.filter(is_full=(is_full.lower() == 'true'))

    # Get comprehensive statistics using statistics module
    stats_filters = {}
    if group_type:
        stats_filters['group_type'] = group_type
    if is_active is not None:
        stats_filters['is_active'] = (is_active.lower() == 'true')
    if is_full is not None:
        stats_filters['is_full'] = (is_full.lower() == 'true')
    
    try:
        stats = get_group_statistics(filters=stats_filters if stats_filters else None)
    except Exception as e:
        logger.error(f"Error getting group statistics: {e}")
        stats = {
            'total_groups': groups.count(),
            'active_groups': 0,
        }

    # Handle pagination (or return all)
    if page == 'all':
        group_list = []
        for g in groups:
            try:
                group_list.append(serialize_group_data(g))
            except Exception as e:
                logger.error(f"Error serializing group {g.id}: {e}")
                continue
        
        return JsonResponse({
            'groups': group_list,
            'total_count': groups.count(),
            'stats': stats,
        })

    # Paginated response
    groups_page, paginator = paginate_queryset(request, groups, per_page=10)

    group_list = []
    for g in groups_page:
        try:
            group_list.append(serialize_group_data(g))
        except Exception as e:
            logger.error(f"Error serializing group {g.id}: {e}")
            continue

    return JsonResponse({
        'groups': group_list,
        'current_page': groups_page.number,
        'total_pages': paginator.num_pages,
        'total_count': paginator.count,
        'has_previous': groups_page.has_previous(),
        'has_next': groups_page.has_next(),
        'start_index': groups_page.start_index(),
        'end_index': groups_page.end_index(),
        'stats': stats,
    })


def serialize_group_data(g):
    """
    Helper function to serialize a MemberGroup object
    """
    try:
        group_type_display = g.get_group_type_display()
    except Exception:
        group_type_display = g.group_type
    
    try:
        meeting_freq_display = g.get_meeting_frequency_display()
    except Exception:
        meeting_freq_display = g.meeting_frequency
    
    # Get leadership
    leader_name = g.group_leader.get_full_name() if g.group_leader else None
    secretary_name = g.group_secretary.get_full_name() if g.group_secretary else None
    treasurer_name = g.group_treasurer.get_full_name() if g.group_treasurer else None
    
    return {
        'id': str(g.id),
        'name': g.name,
        'description': g.description[:200] if g.description else None,
        'group_type': g.group_type,
        'group_type_display': group_type_display,
        'formation_date': g.formation_date.strftime('%b %d, %Y') if g.formation_date else None,
        'group_age_days': g.group_age_days,
        'meeting_frequency': g.meeting_frequency,
        'meeting_frequency_display': meeting_freq_display,
        'meeting_day': g.meeting_day,
        'meeting_time': g.meeting_time.strftime('%I:%M %p') if g.meeting_time else None,
        'meeting_location': g.meeting_location,
        'minimum_contribution': float(g.minimum_contribution),
        'maximum_loan_amount': float(g.maximum_loan_amount),
        'interest_rate': float(g.interest_rate),
        'maximum_members': g.maximum_members,
        'minimum_members': g.minimum_members,
        'member_count': g.member_count,
        'available_slots': g.available_slots,
        'is_active': g.is_active,
        'is_full': g.is_full,
        'can_add_member': g.can_add_member(),
        'leader_name': leader_name,
        'leader_id': str(g.group_leader.id) if g.group_leader else None,
        'secretary_name': secretary_name,
        'secretary_id': str(g.group_secretary.id) if g.group_secretary else None,
        'treasurer_name': treasurer_name,
        'treasurer_id': str(g.group_treasurer.id) if g.group_treasurer else None,
    }


# =============================================================================
# GROUP MEMBERSHIP SEARCH
# =============================================================================

def group_membership_search(request):
    """
    AJAX view to return filtered group memberships as JSON
    """
    # Extract filters using parse_filters
    filters = parse_filters(request, [
        'q', 'member', 'group', 'role', 'status', 'is_active', 'page'
    ])
    
    query = filters['q']
    member_id = filters['member']
    group_id = filters['group']
    role = filters['role']
    status = filters['status']
    is_active = filters['is_active']
    page = filters['page'] or 1

    # Start with all memberships
    memberships = GroupMembership.objects.all().select_related(
        'member', 'group'
    ).order_by('-join_date')

    # Apply text search
    if query:
        memberships = memberships.filter(
            Q(member__member_number__icontains=query) |
            Q(member__first_name__icontains=query) |
            Q(member__last_name__icontains=query) |
            Q(group__name__icontains=query)
        )

    # Apply filters
    if member_id:
        memberships = memberships.filter(member_id=member_id)
    if group_id:
        memberships = memberships.filter(group_id=group_id)
    if role:
        memberships = memberships.filter(role=role)
    if status:
        memberships = memberships.filter(status=status)
    if is_active is not None:
        memberships = memberships.filter(is_active=(is_active.lower() == 'true'))

    # Basic stats
    stats = {
        'total_memberships': memberships.count(),
        'active_memberships': memberships.filter(is_active=True).count(),
        'unique_members': memberships.values('member').distinct().count(),
        'unique_groups': memberships.values('group').distinct().count(),
    }

    # Handle pagination (or return all)
    if page == 'all':
        membership_list = []
        for gm in memberships:
            try:
                membership_list.append(serialize_group_membership_data(gm))
            except Exception as e:
                logger.error(f"Error serializing membership {gm.id}: {e}")
                continue
        
        return JsonResponse({
            'memberships': membership_list,
            'total_count': memberships.count(),
            'stats': stats,
        })

    # Paginated response
    memberships_page, paginator = paginate_queryset(request, memberships, per_page=10)

    membership_list = []
    for gm in memberships_page:
        try:
            membership_list.append(serialize_group_membership_data(gm))
        except Exception as e:
            logger.error(f"Error serializing membership {gm.id}: {e}")
            continue

    return JsonResponse({
        'memberships': membership_list,
        'current_page': memberships_page.number,
        'total_pages': paginator.num_pages,
        'total_count': paginator.count,
        'has_previous': memberships_page.has_previous(),
        'has_next': memberships_page.has_next(),
        'start_index': memberships_page.start_index(),
        'end_index': memberships_page.end_index(),
        'stats': stats,
    })


def serialize_group_membership_data(gm):
    """
    Helper function to serialize a GroupMembership object
    """
    try:
        role_display = gm.get_role_display()
    except Exception:
        role_display = gm.role
    
    try:
        status_display = gm.get_status_display()
    except Exception:
        status_display = gm.status
    
    return {
        'id': str(gm.id),
        'member_id': str(gm.member.id),
        'member_name': gm.member.get_full_name(),
        'member_number': gm.member.member_number,
        'group_id': str(gm.group.id),
        'group_name': gm.group.name,
        'group_type': gm.group.get_group_type_display(),
        'role': gm.role,
        'role_display': role_display,
        'join_date': gm.join_date.strftime('%b %d, %Y') if gm.join_date else None,
        'exit_date': gm.exit_date.strftime('%b %d, %Y') if gm.exit_date else None,
        'membership_duration_days': gm.membership_duration_days,
        'status': gm.status,
        'status_display': status_display,
        'is_active': gm.is_active,
        'monthly_contribution': float(gm.monthly_contribution),
        'total_contributions': float(gm.total_contributions),
        'meeting_attendance_rate': float(gm.meeting_attendance_rate),
        'last_meeting_attended': gm.last_meeting_attended.strftime('%b %d, %Y') if gm.last_meeting_attended else None,
    }


# =============================================================================
# QUICK STATS ENDPOINTS
# =============================================================================

def member_quick_stats(request):
    """
    Get quick statistics for dashboard widgets
    """
    try:
        from .stats import get_dashboard_summary
        summary = get_dashboard_summary()
        return JsonResponse(summary)
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {e}")
        return JsonResponse({
            'error': 'Failed to retrieve statistics',
            'message': str(e)
        }, status=500)


def member_growth_trends(request):
    """
    Get member growth trends for charts
    """
    try:
        from .stats import get_member_growth_trends
        period = request.GET.get('period', 'month')
        limit = int(request.GET.get('limit', 12))
        
        trends = get_member_growth_trends(period=period, limit=limit)
        return JsonResponse(trends)
    except Exception as e:
        logger.error(f"Error getting growth trends: {e}")
        return JsonResponse({
            'error': 'Failed to retrieve growth trends',
            'message': str(e)
        }, status=500)


def group_membership_trends(request):
    """
    Get group membership trends for charts
    """
    try:
        from .stats import get_group_membership_trends
        period = request.GET.get('period', 'month')
        limit = int(request.GET.get('limit', 12))
        
        trends = get_group_membership_trends(period=period, limit=limit)
        return JsonResponse(trends)
    except Exception as e:
        logger.error(f"Error getting membership trends: {e}")
        return JsonResponse({
            'error': 'Failed to retrieve membership trends',
            'message': str(e)
        }, status=500)


def member_retention_analysis(request):
    """
    Get member retention analysis
    """
    try:
        from .stats import get_member_retention_analysis
        months = int(request.GET.get('months', 12))
        
        analysis = get_member_retention_analysis(months=months)
        return JsonResponse(analysis)
    except Exception as e:
        logger.error(f"Error getting retention analysis: {e}")
        return JsonResponse({
            'error': 'Failed to retrieve retention analysis',
            'message': str(e)
        }, status=500)