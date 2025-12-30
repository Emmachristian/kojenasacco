# members/signals.py

"""
Members Signals

Handles automatic operations on model save/delete:
- Member number generation
- Credit score calculation
- Risk rating updates
- Status change tracking
- KYC expiry monitoring
- Group membership updates
- Automatic field population
- Validation

All number generation is delegated to utils.py for clean separation.
"""

from django.db.models.signals import pre_save, post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction as db_transaction
from decimal import Decimal
from django.db.models import Sum
import logging

from .models import (
    Member,
    MemberPaymentMethod,
    NextOfKin,
    MemberAdditionalContact,
    MemberGroup,
    GroupMembership,
)

logger = logging.getLogger(__name__)


# =============================================================================
# MEMBER SIGNALS
# =============================================================================

@receiver(pre_save, sender=Member)
def generate_member_number(sender, instance, **kwargs):
    """
    Generate member number if not set.
    Delegates to utils.generate_member_number() for generation logic.
    """
    if not instance.member_number:
        from .utils import generate_member_number as gen_number
        
        instance.member_number = gen_number('MEM')
        
        logger.info(f"Generated member number: {instance.member_number}")


@receiver(pre_save, sender=Member)
def calculate_initial_credit_score(sender, instance, **kwargs):
    """
    Calculate initial credit score for new members.
    """
    # Only for new members with default credit score
    if not instance.pk and instance.credit_score == 500:
        from .utils import calculate_simple_credit_score, calculate_age
        
        age = calculate_age(instance.date_of_birth)
        
        instance.credit_score = calculate_simple_credit_score(
            age=age,
            employment_status=instance.employment_status,
            monthly_income=instance.monthly_income or Decimal('0')
        )
        
        logger.debug(f"Calculated initial credit score for {instance.first_name}: {instance.credit_score}")


@receiver(pre_save, sender=Member)
def update_risk_rating_on_credit_score_change(sender, instance, **kwargs):
    """
    Update risk rating when credit score changes.
    """
    if instance.pk:
        try:
            old_instance = Member.objects.get(pk=instance.pk)
            
            # Check if credit score changed
            if old_instance.credit_score != instance.credit_score:
                from .utils import calculate_risk_rating
                
                instance.risk_rating = calculate_risk_rating(instance.credit_score)
                instance.risk_assessment_date = timezone.now()
                
                logger.debug(
                    f"Updated risk rating for {instance.member_number}: "
                    f"{old_instance.risk_rating} → {instance.risk_rating}"
                )
        except Member.DoesNotExist:
            pass


@receiver(pre_save, sender=Member)
def track_status_changes(sender, instance, **kwargs):
    """
    Track status changes with date and reason.
    """
    if instance.pk:
        try:
            old_instance = Member.objects.get(pk=instance.pk)
            
            # Check if status changed
            if old_instance.status != instance.status:
                instance.status_changed_date = timezone.now()
                
                # Auto-set reason if not provided
                if not instance.status_changed_reason:
                    instance.status_changed_reason = f"Status changed from {old_instance.get_status_display()} to {instance.get_status_display()}"
                
                logger.info(
                    f"Status changed for {instance.member_number}: "
                    f"{old_instance.status} → {instance.status}"
                )
        except Member.DoesNotExist:
            pass


@receiver(pre_save, sender=Member)
def set_membership_dates(sender, instance, **kwargs):
    """
    Set membership dates automatically based on status changes.
    """
    if instance.pk:
        try:
            old_instance = Member.objects.get(pk=instance.pk)
            
            # Set approved date when status changes to ACTIVE
            if old_instance.status == 'PENDING_APPROVAL' and instance.status == 'ACTIVE':
                if not instance.membership_approved_date:
                    instance.membership_approved_date = timezone.now().date()
                
                logger.info(f"Member {instance.member_number} approved and activated")
                
        except Member.DoesNotExist:
            pass


@receiver(pre_save, sender=Member)
def update_kyc_status(sender, instance, **kwargs):
    """
    Update KYC status based on expiry date.
    """
    if instance.kyc_expiry_date:
        from .utils import is_kyc_expired
        
        is_expired, days = is_kyc_expired(instance.kyc_expiry_date)
        
        if is_expired and instance.kyc_status == 'VERIFIED':
            instance.kyc_status = 'EXPIRED'
            
            logger.warning(
                f"KYC expired for member {instance.member_number} "
                f"({abs(days)} days ago)"
            )


@receiver(post_save, sender=Member)
def log_member_creation(sender, instance, created, **kwargs):
    """
    Log when a new member is created.
    """
    if created:
        logger.info(
            f"New member created: {instance.member_number} | "
            f"Name: {instance.get_full_name()} | "
            f"Status: {instance.get_status_display()} | "
            f"Category: {instance.get_member_category_display()}"
        )


@receiver(post_save, sender=Member)
def create_default_payment_method(sender, instance, created, **kwargs):
    """
    Create default cash payment method for new members.
    """
    if created:
        try:
            # Check if member has any payment methods
            if not instance.payment_methods.exists():
                MemberPaymentMethod.objects.create(
                    member=instance,
                    method_type='CASH',
                    provider='Cash',
                    account_number='N/A',
                    account_name=instance.get_full_name(),
                    is_primary=True,
                    is_verified=True,
                    notes='Default cash payment method'
                )
                
                logger.info(f"Created default payment method for {instance.member_number}")
        except Exception as e:
            logger.error(f"Error creating default payment method: {e}")


@receiver(post_save, sender=Member)
def update_shares_balance_reference(sender, instance, **kwargs):
    """
    Update member's share balance if shares app integration exists.
    
    Note: This is a placeholder for shares integration.
    """
    try:
        # Check if shares app is installed
        from django.apps import apps
        if apps.is_installed('shares'):
            from shares.utils import calculate_member_share_balance
            
            balance_info = calculate_member_share_balance(instance)
            
            # Update if member has shares_balance field
            if hasattr(instance, 'shares_balance'):
                Member.objects.filter(pk=instance.pk).update(
                    shares_balance=balance_info['net_shares'],
                    shares_value=balance_info['total_value']
                )
    except Exception as e:
        # Silently pass if shares app not installed
        pass


# =============================================================================
# PAYMENT METHOD SIGNALS
# =============================================================================

@receiver(pre_save, sender=MemberPaymentMethod)
def ensure_single_primary_payment_method(sender, instance, **kwargs):
    """
    Ensure only one payment method is marked as primary.
    """
    if instance.is_primary:
        # Clear primary flag from other payment methods
        MemberPaymentMethod.objects.filter(
            member=instance.member,
            is_primary=True
        ).exclude(pk=instance.pk).update(is_primary=False)


@receiver(post_save, sender=MemberPaymentMethod)
def log_payment_method_creation(sender, instance, created, **kwargs):
    """
    Log when a payment method is created.
    """
    if created:
        logger.info(
            f"Payment method added: {instance.member.member_number} | "
            f"Type: {instance.get_method_type_display()} | "
            f"Provider: {instance.provider} | "
            f"Primary: {instance.is_primary}"
        )


@receiver(post_save, sender=MemberPaymentMethod)
def ensure_member_has_primary_payment_method(sender, instance, **kwargs):
    """
    Ensure member always has at least one primary payment method.
    """
    # Check if member has any primary payment method
    has_primary = instance.member.payment_methods.filter(is_primary=True).exists()
    
    if not has_primary:
        # Make the first active payment method primary
        first_active = instance.member.payment_methods.filter(is_active=True).first()
        if first_active:
            first_active.is_primary = True
            first_active.save(update_fields=['is_primary'])
            
            logger.info(f"Auto-set primary payment method for {instance.member.member_number}")


@receiver(post_delete, sender=MemberPaymentMethod)
def reassign_primary_on_delete(sender, instance, **kwargs):
    """
    Reassign primary status when primary payment method is deleted.
    """
    if instance.is_primary:
        # Find another payment method to make primary
        new_primary = instance.member.payment_methods.filter(
            is_active=True
        ).exclude(pk=instance.pk).first()
        
        if new_primary:
            new_primary.is_primary = True
            new_primary.save(update_fields=['is_primary'])
            
            logger.info(
                f"Reassigned primary payment method for {instance.member.member_number} "
                f"after deletion"
            )


# =============================================================================
# NEXT OF KIN SIGNALS
# =============================================================================

@receiver(pre_save, sender=NextOfKin)
def ensure_single_primary_next_of_kin(sender, instance, **kwargs):
    """
    Ensure only one next of kin is marked as primary.
    """
    if instance.is_primary:
        # Clear primary flag from other next of kin
        NextOfKin.objects.filter(
            member=instance.member,
            is_primary=True
        ).exclude(pk=instance.pk).update(is_primary=False)


@receiver(pre_save, sender=NextOfKin)
def validate_total_beneficiary_allocation(sender, instance, **kwargs):
    """
    Validate total beneficiary percentage doesn't exceed 100%.
    """
    if instance.is_beneficiary and instance.beneficiary_percentage > 0:
        # Calculate total from other beneficiaries
        total = NextOfKin.objects.filter(
            member=instance.member,
            is_beneficiary=True
        ).exclude(pk=instance.pk).aggregate(
            total=Sum('beneficiary_percentage')
        )['total'] or Decimal('0.00')
        
        if total + instance.beneficiary_percentage > 100:
            logger.warning(
                f"Total beneficiary allocation would exceed 100% for "
                f"member {instance.member.member_number}"
            )


@receiver(post_save, sender=NextOfKin)
def log_next_of_kin_creation(sender, instance, created, **kwargs):
    """
    Log when next of kin is created.
    """
    if created:
        logger.info(
            f"Next of kin added: {instance.member.member_number} | "
            f"Name: {instance.name} | "
            f"Relation: {instance.get_relation_display()} | "
            f"Primary: {instance.is_primary} | "
            f"Beneficiary: {instance.is_beneficiary}"
        )


@receiver(post_save, sender=NextOfKin)
def ensure_member_has_primary_next_of_kin(sender, instance, **kwargs):
    """
    Ensure member always has at least one primary next of kin.
    """
    # Check if member has any primary next of kin
    has_primary = instance.member.next_of_kin.filter(is_primary=True).exists()
    
    if not has_primary:
        # Make the first next of kin primary
        first_nok = instance.member.next_of_kin.first()
        if first_nok:
            first_nok.is_primary = True
            first_nok.save(update_fields=['is_primary'])
            
            logger.info(f"Auto-set primary next of kin for {instance.member.member_number}")


# =============================================================================
# ADDITIONAL CONTACT SIGNALS
# =============================================================================

@receiver(post_save, sender=MemberAdditionalContact)
def log_additional_contact_creation(sender, instance, created, **kwargs):
    """
    Log when additional contact is created.
    """
    if created:
        logger.info(
            f"Additional contact added: {instance.member.member_number} | "
            f"Type: {instance.get_contact_type_display()} | "
            f"Value: {instance.contact_value}"
        )


# =============================================================================
# MEMBER GROUP SIGNALS
# =============================================================================

@receiver(post_save, sender=MemberGroup)
def log_group_creation(sender, instance, created, **kwargs):
    """
    Log when a member group is created.
    """
    if created:
        logger.info(
            f"Member group created: {instance.name} | "
            f"Type: {instance.get_group_type_display()} | "
            f"Max Members: {instance.maximum_members} | "
            f"Min Members: {instance.minimum_members}"
        )


@receiver(pre_save, sender=MemberGroup)
def update_group_full_status(sender, instance, **kwargs):
    """
    Update is_full status based on member count.
    """
    if instance.pk:
        current_members = instance.groupmembership_set.filter(is_active=True).count()
        instance.is_full = current_members >= instance.maximum_members


# =============================================================================
# GROUP MEMBERSHIP SIGNALS
# =============================================================================

@receiver(pre_save, sender=GroupMembership)
def set_join_date_for_new_membership(sender, instance, **kwargs):
    """
    Set join date when membership is created.
    """
    if not instance.pk and not instance.join_date:
        instance.join_date = timezone.now().date()


@receiver(pre_save, sender=GroupMembership)
def update_exit_date_on_status_change(sender, instance, **kwargs):
    """
    Set exit date when membership becomes inactive.
    """
    if instance.pk:
        try:
            old_instance = GroupMembership.objects.get(pk=instance.pk)
            
            # Set exit date when changing to inactive
            if old_instance.is_active and not instance.is_active:
                if not instance.exit_date:
                    instance.exit_date = timezone.now().date()
            
            # Clear exit date when reactivating
            if not old_instance.is_active and instance.is_active:
                instance.exit_date = None
                
        except GroupMembership.DoesNotExist:
            pass


@receiver(post_save, sender=GroupMembership)
def log_group_membership_creation(sender, instance, created, **kwargs):
    """
    Log when group membership is created.
    """
    if created:
        logger.info(
            f"Member joined group: {instance.member.member_number} | "
            f"Group: {instance.group.name} | "
            f"Role: {instance.get_role_display()}"
        )


@receiver(post_save, sender=GroupMembership)
def update_group_full_status_after_membership_change(sender, instance, **kwargs):
    """
    Update group's full status after membership changes.
    """
    try:
        instance.group.update_full_status()
    except Exception as e:
        logger.error(f"Error updating group full status: {e}")


@receiver(post_save, sender=GroupMembership)
def update_leadership_roles(sender, instance, **kwargs):
    """
    Update group leadership positions based on membership roles.
    """
    if instance.is_active:
        try:
            if instance.role == 'LEADER' and instance.group.group_leader != instance.member:
                instance.group.group_leader = instance.member
                instance.group.save(update_fields=['group_leader'])
                
            elif instance.role == 'SECRETARY' and instance.group.group_secretary != instance.member:
                instance.group.group_secretary = instance.member
                instance.group.save(update_fields=['group_secretary'])
                
            elif instance.role == 'TREASURER' and instance.group.group_treasurer != instance.member:
                instance.group.group_treasurer = instance.member
                instance.group.save(update_fields=['group_treasurer'])
                
        except Exception as e:
            logger.error(f"Error updating group leadership: {e}")


@receiver(post_delete, sender=GroupMembership)
def update_group_after_membership_deletion(sender, instance, **kwargs):
    """
    Update group status after membership is deleted.
    """
    try:
        instance.group.update_full_status()
        
        # Clear leadership positions if this member was a leader
        if instance.group.group_leader == instance.member:
            instance.group.group_leader = None
        if instance.group.group_secretary == instance.member:
            instance.group.group_secretary = None
        if instance.group.group_treasurer == instance.member:
            instance.group.group_treasurer = None
        
        instance.group.save(update_fields=['group_leader', 'group_secretary', 'group_treasurer'])
        
        logger.info(
            f"Member left group: {instance.member.member_number} | "
            f"Group: {instance.group.name}"
        )
    except Exception as e:
        logger.error(f"Error updating group after membership deletion: {e}")


# =============================================================================
# CLEANUP SIGNALS
# =============================================================================

@receiver(post_delete, sender=Member)
def log_member_deletion(sender, instance, **kwargs):
    """
    Log when a member is deleted (should be rare).
    """
    logger.warning(
        f"Member DELETED: {instance.member_number} | "
        f"Name: {instance.get_full_name()} | "
        f"Status: {instance.get_status_display()}"
    )


@receiver(post_delete, sender=NextOfKin)
def log_next_of_kin_deletion(sender, instance, **kwargs):
    """
    Log when next of kin is deleted.
    """
    logger.warning(
        f"Next of kin DELETED: {instance.name} | "
        f"Member: {instance.member.member_number}"
    )


# =============================================================================
# SIGNAL DEBUGGING HELPERS
# =============================================================================

def disable_member_signals():
    """
    Temporarily disable member signals (useful for bulk operations).
    
    Usage:
        from members.signals import disable_member_signals, enable_member_signals
        
        disable_member_signals()
        # ... perform bulk operations ...
        enable_member_signals()
    """
    from django.db.models.signals import pre_save, post_save, post_delete
    
    signals_to_disconnect = [
        # Member signals
        (pre_save, generate_member_number, Member),
        (pre_save, calculate_initial_credit_score, Member),
        (pre_save, update_risk_rating_on_credit_score_change, Member),
        (pre_save, track_status_changes, Member),
        (pre_save, set_membership_dates, Member),
        (pre_save, update_kyc_status, Member),
        (post_save, log_member_creation, Member),
        (post_save, create_default_payment_method, Member),
        (post_save, update_shares_balance_reference, Member),
        
        # Payment method signals
        (pre_save, ensure_single_primary_payment_method, MemberPaymentMethod),
        (post_save, log_payment_method_creation, MemberPaymentMethod),
        (post_save, ensure_member_has_primary_payment_method, MemberPaymentMethod),
        (post_delete, reassign_primary_on_delete, MemberPaymentMethod),
        
        # Next of kin signals
        (pre_save, ensure_single_primary_next_of_kin, NextOfKin),
        (pre_save, validate_total_beneficiary_allocation, NextOfKin),
        (post_save, log_next_of_kin_creation, NextOfKin),
        (post_save, ensure_member_has_primary_next_of_kin, NextOfKin),
        
        # Additional contact signals
        (post_save, log_additional_contact_creation, MemberAdditionalContact),
        
        # Group signals
        (post_save, log_group_creation, MemberGroup),
        (pre_save, update_group_full_status, MemberGroup),
        
        # Group membership signals
        (pre_save, set_join_date_for_new_membership, GroupMembership),
        (pre_save, update_exit_date_on_status_change, GroupMembership),
        (post_save, log_group_membership_creation, GroupMembership),
        (post_save, update_group_full_status_after_membership_change, GroupMembership),
        (post_save, update_leadership_roles, GroupMembership),
        (post_delete, update_group_after_membership_deletion, GroupMembership),
    ]
    
    for signal, handler, model in signals_to_disconnect:
        signal.disconnect(handler, sender=model)
    
    logger.warning("Member signals DISABLED")


def enable_member_signals():
    """
    Re-enable member signals after being disabled.
    """
    from django.db.models.signals import pre_save, post_save, post_delete
    
    signals_to_reconnect = [
        # Member signals
        (pre_save, generate_member_number, Member),
        (pre_save, calculate_initial_credit_score, Member),
        (pre_save, update_risk_rating_on_credit_score_change, Member),
        (pre_save, track_status_changes, Member),
        (pre_save, set_membership_dates, Member),
        (pre_save, update_kyc_status, Member),
        (post_save, log_member_creation, Member),
        (post_save, create_default_payment_method, Member),
        (post_save, update_shares_balance_reference, Member),
        
        # Payment method signals
        (pre_save, ensure_single_primary_payment_method, MemberPaymentMethod),
        (post_save, log_payment_method_creation, MemberPaymentMethod),
        (post_save, ensure_member_has_primary_payment_method, MemberPaymentMethod),
        (post_delete, reassign_primary_on_delete, MemberPaymentMethod),
        
        # Next of kin signals
        (pre_save, ensure_single_primary_next_of_kin, NextOfKin),
        (pre_save, validate_total_beneficiary_allocation, NextOfKin),
        (post_save, log_next_of_kin_creation, NextOfKin),
        (post_save, ensure_member_has_primary_next_of_kin, NextOfKin),
        
        # Additional contact signals
        (post_save, log_additional_contact_creation, MemberAdditionalContact),
        
        # Group signals
        (post_save, log_group_creation, MemberGroup),
        (pre_save, update_group_full_status, MemberGroup),
        
        # Group membership signals
        (pre_save, set_join_date_for_new_membership, GroupMembership),
        (pre_save, update_exit_date_on_status_change, GroupMembership),
        (post_save, log_group_membership_creation, GroupMembership),
        (post_save, update_group_full_status_after_membership_change, GroupMembership),
        (post_save, update_leadership_roles, GroupMembership),
        (post_delete, update_group_after_membership_deletion, GroupMembership),
    ]
    
    for signal, handler, model in signals_to_reconnect:
        signal.connect(handler, sender=model)
    
    logger.warning("Member signals ENABLED")


# =============================================================================
# APP READY - ENSURE SIGNALS ARE LOADED
# =============================================================================

def ready():
    """
    Called when the app is ready. Ensures signals are registered.
    This should be called from apps.py MembersConfig.ready()
    """
    logger.info("Member signals registered successfully")