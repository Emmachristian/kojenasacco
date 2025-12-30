# members/modal_views.py

"""
Modal views for member actions using centralized utilities from core.utils

All modal responses use the standardized create_sweetalert_response() helper
from core.utils, ensuring consistency across the entire application.

Includes modals for:
- Member status changes (activate, suspend, deactivate)
- Member deletion
- Payment method verification and deletion
- Next of kin approval and deletion
- Group membership management
- Additional contact verification
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
from django.db.models import Q

# Import the centralized response helpers
from core.utils import (
    create_sweetalert_response,
    create_success_response,
    create_error_response,
    create_warning_response,
    create_info_response
)

from .models import (
    Member,
    MemberPaymentMethod,
    NextOfKin,
    MemberAdditionalContact,
    MemberGroup,
    GroupMembership
)

import logging
logger = logging.getLogger(__name__)


# =============================================================================
# MEMBER STATUS CHANGE MODALS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def member_activate_modal(request, pk):
    """Load member activation confirmation modal"""
    member = get_object_or_404(Member, pk=pk)
    
    # Check if already active
    if member.status == 'ACTIVE':
        return render(request, 'members/modals/already_active.html', {
            'member': member,
        })
    
    return render(request, 'members/modals/activate_member.html', {
        'member': member,
    })


@login_required
@require_http_methods(["POST"])
def member_activate_submit(request, pk):
    """Process member activation"""
    member = get_object_or_404(Member, pk=pk)
    
    # Check if already active
    if member.status == 'ACTIVE':
        return create_warning_response(
            message=f"{member.get_full_name()} is already active",
            title='Already Active'
        )
    
    # Activate member
    member.activate()
    
    # Return updated member card
    member.refresh_from_db()
    
    updated_html = render_to_string(
        'members/_member_card.html',
        {'member': member},
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=f"{member.get_full_name()} has been activated successfully",
        title='Member Activated'
    )


@login_required
@require_http_methods(["GET"])
def member_suspend_modal(request, pk):
    """Load member suspension modal"""
    member = get_object_or_404(Member, pk=pk)
    
    # Check if already suspended
    if member.status == 'SUSPENDED':
        return render(request, 'members/modals/already_suspended.html', {
            'member': member,
        })
    
    return render(request, 'members/modals/suspend_member.html', {
        'member': member,
    })


@login_required
@require_http_methods(["POST"])
def member_suspend_submit(request, pk):
    """Process member suspension"""
    member = get_object_or_404(Member, pk=pk)
    reason = request.POST.get('reason', '').strip()
    
    if not reason:
        return render(request, 'members/modals/suspend_member.html', {
            'member': member,
            'error_message': 'Suspension reason is required',
        })
    
    # Suspend member
    member.suspend(reason)
    
    # Return updated member card
    member.refresh_from_db()
    
    updated_html = render_to_string(
        'members/_member_card.html',
        {'member': member},
        request=request
    )
    
    return create_warning_response(
        html_content=updated_html,
        message=f"{member.get_full_name()} has been suspended",
        title='Member Suspended'
    )


@login_required
@require_http_methods(["GET"])
def member_deactivate_modal(request, pk):
    """Load member deactivation confirmation modal"""
    member = get_object_or_404(Member, pk=pk)
    
    # Check if already inactive
    if member.status in ['DORMANT', 'WITHDRAWN', 'DECEASED']:
        return render(request, 'members/modals/already_inactive.html', {
            'member': member,
        })
    
    return render(request, 'members/modals/deactivate_member.html', {
        'member': member,
    })


@login_required
@require_http_methods(["POST"])
def member_deactivate_submit(request, pk):
    """Process member deactivation"""
    member = get_object_or_404(Member, pk=pk)
    
    # Deactivate member
    member.deactivate()
    
    # Return updated member card
    member.refresh_from_db()
    
    updated_html = render_to_string(
        'members/_member_card.html',
        {'member': member},
        request=request
    )
    
    return create_info_response(
        html_content=updated_html,
        message=f"{member.get_full_name()} has been deactivated",
        title='Member Deactivated'
    )


# =============================================================================
# MEMBER DELETION
# =============================================================================

@login_required
@require_http_methods(["GET"])
def member_delete_modal(request, pk):
    """Load member deletion confirmation modal"""
    member = get_object_or_404(Member, pk=pk)
    
    # Check if deletion is allowed
    has_loans = hasattr(member, 'loans') and member.loans.exists()
    has_savings = hasattr(member, 'savings_accounts') and member.savings_accounts.exists()
    has_shares = hasattr(member, 'share_accounts') and member.share_accounts.exists()
    has_transactions = hasattr(member, 'transactions') and member.transactions.exists()
    
    can_delete = not (has_loans or has_savings or has_shares or has_transactions)
    
    return render(request, 'members/modals/delete_member.html', {
        'member': member,
        'can_delete': can_delete,
        'has_loans': has_loans,
        'has_savings': has_savings,
        'has_shares': has_shares,
        'has_transactions': has_transactions,
    })


@login_required
@require_http_methods(["DELETE", "POST"])
def member_delete_submit(request, pk):
    """Process member deletion"""
    member = get_object_or_404(Member, pk=pk)
    
    # Verify can delete
    has_loans = hasattr(member, 'loans') and member.loans.exists()
    has_savings = hasattr(member, 'savings_accounts') and member.savings_accounts.exists()
    has_shares = hasattr(member, 'share_accounts') and member.share_accounts.exists()
    has_transactions = hasattr(member, 'transactions') and member.transactions.exists()
    
    if has_loans or has_savings or has_shares or has_transactions:
        return create_error_response(
            message=f"Cannot delete {member.get_full_name()} because they have associated records (loans, savings, shares, or transactions).",
            title='Cannot Delete'
        )
    
    member_name = member.get_full_name()
    member.delete()
    
    # Return success (row will be removed by HTMX)
    return create_success_response(
        html_content='',  # No content needed - HTMX removes the row
        message=f"Member '{member_name}' has been deleted successfully.",
        title='Member Deleted'
    )


# =============================================================================
# PAYMENT METHOD MODALS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def payment_method_verify_modal(request, pk):
    """Load payment method verification modal"""
    payment_method = get_object_or_404(MemberPaymentMethod, pk=pk)
    
    # Check if already verified
    if payment_method.is_verified:
        return render(request, 'members/modals/payment_already_verified.html', {
            'payment_method': payment_method,
        })
    
    return render(request, 'members/modals/verify_payment_method.html', {
        'payment_method': payment_method,
    })


@login_required
@require_http_methods(["POST"])
def payment_method_verify_submit(request, pk):
    """Process payment method verification"""
    payment_method = get_object_or_404(MemberPaymentMethod, pk=pk)
    
    # Verify payment method
    payment_method.verify()
    
    # Return updated payment method card
    payment_method.refresh_from_db()
    
    updated_html = render_to_string(
        'members/payment_methods/_payment_method_card.html',
        {'payment_method': payment_method},
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=f"Payment method for {payment_method.member.get_full_name()} has been verified",
        title='Payment Method Verified'
    )


@login_required
@require_http_methods(["GET"])
def payment_method_set_primary_modal(request, pk):
    """Load set as primary payment method modal"""
    payment_method = get_object_or_404(MemberPaymentMethod, pk=pk)
    
    # Check if already primary
    if payment_method.is_primary:
        return render(request, 'members/modals/payment_already_primary.html', {
            'payment_method': payment_method,
        })
    
    return render(request, 'members/modals/set_primary_payment.html', {
        'payment_method': payment_method,
    })


@login_required
@require_http_methods(["POST"])
def payment_method_set_primary_submit(request, pk):
    """Process setting payment method as primary"""
    payment_method = get_object_or_404(MemberPaymentMethod, pk=pk)
    
    # Set as primary
    payment_method.set_as_primary()
    
    # Return updated payment method list for this member
    payment_methods = payment_method.member.payment_methods.all()
    
    updated_html = render_to_string(
        'members/payment_methods/_payment_methods_list.html',
        {
            'payment_methods': payment_methods,
            'member': payment_method.member
        },
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=f"Payment method set as primary for {payment_method.member.get_full_name()}",
        title='Primary Payment Method Set'
    )


@login_required
@require_http_methods(["GET"])
def payment_method_delete_modal(request, pk):
    """Load payment method deletion confirmation modal"""
    payment_method = get_object_or_404(MemberPaymentMethod, pk=pk)
    
    # Check if it's the only payment method
    is_only_method = payment_method.member.payment_methods.count() == 1
    
    # Check if it's primary
    is_primary = payment_method.is_primary
    
    return render(request, 'members/modals/delete_payment_method.html', {
        'payment_method': payment_method,
        'is_only_method': is_only_method,
        'is_primary': is_primary,
    })


@login_required
@require_http_methods(["DELETE", "POST"])
def payment_method_delete_submit(request, pk):
    """Process payment method deletion"""
    payment_method = get_object_or_404(MemberPaymentMethod, pk=pk)
    member = payment_method.member
    
    payment_method.delete()
    
    # Return updated payment methods list
    payment_methods = member.payment_methods.all()
    
    updated_html = render_to_string(
        'members/payment_methods/_payment_methods_list.html',
        {
            'payment_methods': payment_methods,
            'member': member
        },
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message="Payment method removed successfully",
        title='Payment Method Deleted'
    )


# =============================================================================
# NEXT OF KIN MODALS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def next_of_kin_set_primary_modal(request, pk):
    """Load set as primary next of kin modal"""
    nok = get_object_or_404(NextOfKin, pk=pk)
    
    # Check if already primary
    if nok.is_primary:
        return render(request, 'members/modals/nok_already_primary.html', {
            'nok': nok,
        })
    
    return render(request, 'members/modals/set_primary_nok.html', {
        'nok': nok,
    })


@login_required
@require_http_methods(["POST"])
def next_of_kin_set_primary_submit(request, pk):
    """Process setting next of kin as primary"""
    nok = get_object_or_404(NextOfKin, pk=pk)
    
    # Set as primary
    nok.set_as_primary()
    
    # Return updated next of kin list for this member
    next_of_kin = nok.member.next_of_kin.all()
    
    updated_html = render_to_string(
        'members/next_of_kin/_next_of_kin_list.html',
        {
            'next_of_kin': next_of_kin,
            'member': nok.member
        },
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=f"{nok.name} set as primary next of kin for {nok.member.get_full_name()}",
        title='Primary Next of Kin Set'
    )


@login_required
@require_http_methods(["GET"])
def next_of_kin_set_emergency_modal(request, pk):
    """Load set as emergency contact modal"""
    nok = get_object_or_404(NextOfKin, pk=pk)
    
    # Check if already emergency contact
    if nok.is_emergency_contact:
        return render(request, 'members/modals/nok_already_emergency.html', {
            'nok': nok,
        })
    
    return render(request, 'members/modals/set_emergency_contact.html', {
        'nok': nok,
    })


@login_required
@require_http_methods(["POST"])
def next_of_kin_set_emergency_submit(request, pk):
    """Process setting next of kin as emergency contact"""
    nok = get_object_or_404(NextOfKin, pk=pk)
    
    # Set as emergency contact
    nok.is_emergency_contact = True
    nok.save()
    
    # Return updated next of kin card
    nok.refresh_from_db()
    
    updated_html = render_to_string(
        'members/next_of_kin/_nok_card.html',
        {'nok': nok},
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=f"{nok.name} set as emergency contact",
        title='Emergency Contact Set'
    )


@login_required
@require_http_methods(["GET"])
def next_of_kin_delete_modal(request, pk):
    """Load next of kin deletion confirmation modal"""
    nok = get_object_or_404(NextOfKin, pk=pk)
    
    # Check if it's the only next of kin
    is_only_nok = nok.member.next_of_kin.count() == 1
    
    # Check if it's primary
    is_primary = nok.is_primary
    
    return render(request, 'members/modals/delete_nok.html', {
        'nok': nok,
        'is_only_nok': is_only_nok,
        'is_primary': is_primary,
    })


@login_required
@require_http_methods(["DELETE", "POST"])
def next_of_kin_delete_submit(request, pk):
    """Process next of kin deletion"""
    nok = get_object_or_404(NextOfKin, pk=pk)
    member = nok.member
    nok_name = nok.name
    
    nok.delete()
    
    # Return updated next of kin list
    next_of_kin = member.next_of_kin.all()
    
    updated_html = render_to_string(
        'members/next_of_kin/_next_of_kin_list.html',
        {
            'next_of_kin': next_of_kin,
            'member': member
        },
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=f"Next of kin {nok_name} removed successfully",
        title='Next of Kin Deleted'
    )


# =============================================================================
# ADDITIONAL CONTACT MODALS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def additional_contact_verify_modal(request, pk):
    """Load additional contact verification modal"""
    contact = get_object_or_404(MemberAdditionalContact, pk=pk)
    
    # Check if already verified
    if contact.is_verified:
        return render(request, 'members/modals/contact_already_verified.html', {
            'contact': contact,
        })
    
    return render(request, 'members/modals/verify_contact.html', {
        'contact': contact,
    })


@login_required
@require_http_methods(["POST"])
def additional_contact_verify_submit(request, pk):
    """Process additional contact verification"""
    contact = get_object_or_404(MemberAdditionalContact, pk=pk)
    
    # Verify contact
    contact.is_verified = True
    contact.save()
    
    # Return updated contact card
    contact.refresh_from_db()
    
    updated_html = render_to_string(
        'members/additional_contacts/_contact_card.html',
        {'contact': contact},
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=f"Contact {contact.get_contact_type_display()} has been verified",
        title='Contact Verified'
    )


@login_required
@require_http_methods(["GET"])
def additional_contact_delete_modal(request, pk):
    """Load additional contact deletion confirmation modal"""
    contact = get_object_or_404(MemberAdditionalContact, pk=pk)
    
    return render(request, 'members/modals/delete_contact.html', {
        'contact': contact,
    })


@login_required
@require_http_methods(["DELETE", "POST"])
def additional_contact_delete_submit(request, pk):
    """Process additional contact deletion"""
    contact = get_object_or_404(MemberAdditionalContact, pk=pk)
    member = contact.member
    
    contact.delete()
    
    # Return updated contacts list
    contacts = member.additional_contacts.all()
    
    updated_html = render_to_string(
        'members/additional_contacts/_contacts_list.html',
        {
            'contacts': contacts,
            'member': member
        },
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message="Additional contact removed successfully",
        title='Contact Deleted'
    )


# =============================================================================
# MEMBER GROUP MODALS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def group_delete_modal(request, pk):
    """Load group deletion confirmation modal"""
    group = get_object_or_404(MemberGroup, pk=pk)
    
    # Check if group has members
    has_members = group.groupmembership_set.filter(is_active=True).exists()
    
    # Check if group has financial transactions
    has_transactions = False  # TODO: Check if group has any financial records
    
    can_delete = not (has_members or has_transactions)
    
    return render(request, 'members/modals/delete_group.html', {
        'group': group,
        'can_delete': can_delete,
        'has_members': has_members,
        'has_transactions': has_transactions,
        'member_count': group.groupmembership_set.filter(is_active=True).count(),
    })


@login_required
@require_http_methods(["DELETE", "POST"])
def group_delete_submit(request, pk):
    """Process group deletion"""
    group = get_object_or_404(MemberGroup, pk=pk)
    
    # Verify can delete
    has_members = group.groupmembership_set.filter(is_active=True).exists()
    
    if has_members:
        return create_error_response(
            message=f"Cannot delete '{group.name}' because it has active members. Please remove all members first.",
            title='Cannot Delete'
        )
    
    group_name = group.name
    group.delete()
    
    # Return success (row will be removed by HTMX)
    return create_success_response(
        html_content='',  # No content needed - HTMX removes the row
        message=f"Group '{group_name}' has been deleted successfully.",
        title='Group Deleted'
    )


@login_required
@require_http_methods(["GET"])
def group_activate_modal(request, pk):
    """Load group activation confirmation modal"""
    group = get_object_or_404(MemberGroup, pk=pk)
    
    # Check if already active
    if group.is_active:
        return render(request, 'members/modals/group_already_active.html', {
            'group': group,
        })
    
    return render(request, 'members/modals/activate_group.html', {
        'group': group,
    })


@login_required
@require_http_methods(["POST"])
def group_activate_submit(request, pk):
    """Process group activation"""
    group = get_object_or_404(MemberGroup, pk=pk)
    
    # Activate group
    group.is_active = True
    group.save()
    
    # Return updated group card
    group.refresh_from_db()
    
    updated_html = render_to_string(
        'members/groups/_group_card.html',
        {'group': group},
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=f"Group '{group.name}' has been activated",
        title='Group Activated'
    )


@login_required
@require_http_methods(["GET"])
def group_deactivate_modal(request, pk):
    """Load group deactivation confirmation modal"""
    group = get_object_or_404(MemberGroup, pk=pk)
    
    # Check if already inactive
    if not group.is_active:
        return render(request, 'members/modals/group_already_inactive.html', {
            'group': group,
        })
    
    return render(request, 'members/modals/deactivate_group.html', {
        'group': group,
    })


@login_required
@require_http_methods(["POST"])
def group_deactivate_submit(request, pk):
    """Process group deactivation"""
    group = get_object_or_404(MemberGroup, pk=pk)
    
    # Deactivate group
    group.is_active = False
    group.save()
    
    # Return updated group card
    group.refresh_from_db()
    
    updated_html = render_to_string(
        'members/groups/_group_card.html',
        {'group': group},
        request=request
    )
    
    return create_warning_response(
        html_content=updated_html,
        message=f"Group '{group.name}' has been deactivated",
        title='Group Deactivated'
    )


# =============================================================================
# GROUP MEMBERSHIP MODALS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def group_membership_remove_modal(request, pk):
    """Load group membership removal confirmation modal"""
    membership = get_object_or_404(GroupMembership, pk=pk)
    
    return render(request, 'members/modals/remove_membership.html', {
        'membership': membership,
    })


@login_required
@require_http_methods(["POST"])
def group_membership_remove_submit(request, pk):
    """Process group membership removal"""
    membership = get_object_or_404(GroupMembership, pk=pk)
    reason = request.POST.get('reason', 'Removed by administrator')
    
    group = membership.group
    member_name = membership.member.get_full_name()
    
    # Leave group
    membership.leave_group(reason)
    
    # Return updated memberships list
    memberships = group.groupmembership_set.filter(is_active=True)
    
    updated_html = render_to_string(
        'members/groups/_memberships_list.html',
        {
            'memberships': memberships,
            'group': group
        },
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=f"{member_name} removed from {group.name}",
        title='Member Removed'
    )


@login_required
@require_http_methods(["GET"])
def group_membership_suspend_modal(request, pk):
    """Load group membership suspension modal"""
    membership = get_object_or_404(GroupMembership, pk=pk)
    
    # Check if already suspended
    if membership.status == 'SUSPENDED':
        return render(request, 'members/modals/membership_already_suspended.html', {
            'membership': membership,
        })
    
    return render(request, 'members/modals/suspend_membership.html', {
        'membership': membership,
    })


@login_required
@require_http_methods(["POST"])
def group_membership_suspend_submit(request, pk):
    """Process group membership suspension"""
    membership = get_object_or_404(GroupMembership, pk=pk)
    reason = request.POST.get('reason', '').strip()
    
    if not reason:
        return render(request, 'members/modals/suspend_membership.html', {
            'membership': membership,
            'error_message': 'Suspension reason is required',
        })
    
    # Suspend membership
    membership.status = 'SUSPENDED'
    membership.notes = f"{membership.notes}\n\nSuspended: {reason}" if membership.notes else f"Suspended: {reason}"
    membership.save()
    
    # Return updated membership card
    membership.refresh_from_db()
    
    updated_html = render_to_string(
        'members/groups/_membership_card.html',
        {'membership': membership},
        request=request
    )
    
    return create_warning_response(
        html_content=updated_html,
        message=f"Membership suspended for {membership.member.get_full_name()}",
        title='Membership Suspended'
    )


@login_required
@require_http_methods(["GET"])
def group_membership_reactivate_modal(request, pk):
    """Load group membership reactivation modal"""
    membership = get_object_or_404(GroupMembership, pk=pk)
    
    # Check if active
    if membership.status == 'ACTIVE':
        return render(request, 'members/modals/membership_already_active.html', {
            'membership': membership,
        })
    
    return render(request, 'members/modals/reactivate_membership.html', {
        'membership': membership,
    })


@login_required
@require_http_methods(["POST"])
def group_membership_reactivate_submit(request, pk):
    """Process group membership reactivation"""
    membership = get_object_or_404(GroupMembership, pk=pk)
    
    # Reactivate membership
    membership.status = 'ACTIVE'
    membership.is_active = True
    membership.save()
    
    # Return updated membership card
    membership.refresh_from_db()
    
    updated_html = render_to_string(
        'members/groups/_membership_card.html',
        {'membership': membership},
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=f"Membership reactivated for {membership.member.get_full_name()}",
        title='Membership Reactivated'
    )