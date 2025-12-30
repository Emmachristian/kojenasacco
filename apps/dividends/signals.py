# dividends/signals.py

"""
Dividends Signals

Handles automatic operations on model save/delete:
- Batch number generation
- Status updates
- Statistics calculations
- Automatic field population
- Net dividend calculation
- Validation

All batch number generation is delegated to utils.py for clean separation.
"""

from django.db.models.signals import pre_save, post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction as db_transaction
from decimal import Decimal
from django.db.models import Q
import logging

from .models import (
    DividendPeriod,
    MemberDividend,
    DividendRate,
    DividendDisbursement,
    DividendPayment,
    DividendPreference,
)

logger = logging.getLogger(__name__)


# =============================================================================
# DIVIDEND PERIOD SIGNALS
# =============================================================================

@receiver(pre_save, sender=DividendPeriod)
def set_declaration_date(sender, instance, **kwargs):
    """
    Set declaration date when period is approved.
    """
    if instance.pk:
        try:
            old_instance = DividendPeriod.objects.get(pk=instance.pk)
            
            # Check if status changed to APPROVED
            if old_instance.status != 'APPROVED' and instance.status == 'APPROVED':
                if not instance.declaration_date:
                    instance.declaration_date = timezone.now().date()
                if not instance.approval_date:
                    instance.approval_date = timezone.now()
                instance.is_approved = True
                
                logger.info(f"Dividend period {instance.name} approved")
        except DividendPeriod.DoesNotExist:
            pass


@receiver(post_save, sender=DividendPeriod)
def log_dividend_period_creation(sender, instance, created, **kwargs):
    """
    Log when a new dividend period is created.
    """
    if created:
        logger.info(
            f"New dividend period created: {instance.name} | "
            f"Period: {instance.start_date} to {instance.end_date} | "
            f"Total Amount: {instance.total_dividend_amount} | "
            f"Rate: {instance.dividend_rate}%"
        )


@receiver(post_save, sender=DividendPeriod)
def update_period_status_on_completion(sender, instance, **kwargs):
    """
    Update period status when all disbursements are completed.
    """
    if instance.status == 'DISBURSING':
        # Check if all disbursements are completed
        disbursements = instance.disbursements.all()
        
        if disbursements.exists():
            all_completed = all(
                d.status in ['COMPLETED', 'CANCELLED'] 
                for d in disbursements
            )
            
            if all_completed:
                has_successful = disbursements.filter(status='COMPLETED').exists()
                
                if has_successful:
                    DividendPeriod.objects.filter(pk=instance.pk).update(
                        status='COMPLETED'
                    )
                    logger.info(f"Dividend period {instance.name} completed")


# =============================================================================
# MEMBER DIVIDEND SIGNALS
# =============================================================================

@receiver(pre_save, sender=MemberDividend)
def calculate_net_dividend(sender, instance, **kwargs):
    """
    Automatically calculate net dividend from gross and tax.
    """
    if instance.gross_dividend is not None and instance.tax_amount is not None:
        instance.net_dividend = instance.gross_dividend - instance.tax_amount
        
        # Ensure not negative
        if instance.net_dividend < Decimal('0.00'):
            instance.net_dividend = Decimal('0.00')
            logger.warning(
                f"Net dividend for {instance.member.get_full_name()} was negative, set to zero"
            )


@receiver(pre_save, sender=MemberDividend)
def set_applied_rate(sender, instance, **kwargs):
    """
    Set applied rate from dividend period if not already set.
    """
    if not instance.applied_rate and instance.dividend_period:
        instance.applied_rate = instance.dividend_period.dividend_rate


@receiver(post_save, sender=MemberDividend)
def log_member_dividend_creation(sender, instance, created, **kwargs):
    """
    Log when a member dividend is created.
    """
    if created:
        logger.info(
            f"Member dividend created: {instance.member.get_full_name()} | "
            f"Period: {instance.dividend_period.name} | "
            f"Gross: {instance.gross_dividend} | "
            f"Net: {instance.net_dividend}"
        )


@receiver(post_save, sender=MemberDividend)
def update_period_statistics_on_dividend_change(sender, instance, **kwargs):
    """
    Update dividend period statistics when member dividends change.
    """
    try:
        period = instance.dividend_period
        
        # Calculate totals from all member dividends
        from django.db.models import Sum, Count
        
        stats = period.member_dividends.aggregate(
            total_members=Count('id'),
            total_shares=Sum('shares_count'),
            total_value=Sum('shares_value')
        )
        
        # Update period
        DividendPeriod.objects.filter(pk=period.pk).update(
            total_members=stats['total_members'] or 0,
            total_shares=stats['total_shares'] or 0,
            total_shares_value=stats['total_value'] or Decimal('0.00')
        )
        
    except Exception as e:
        logger.error(f"Error updating period statistics: {e}")


@receiver(post_delete, sender=MemberDividend)
def update_period_statistics_on_dividend_delete(sender, instance, **kwargs):
    """
    Update dividend period statistics when member dividend is deleted.
    """
    try:
        period = instance.dividend_period
        
        # Recalculate statistics
        from django.db.models import Sum, Count
        
        stats = period.member_dividends.aggregate(
            total_members=Count('id'),
            total_shares=Sum('shares_count'),
            total_value=Sum('shares_value')
        )
        
        DividendPeriod.objects.filter(pk=period.pk).update(
            total_members=stats['total_members'] or 0,
            total_shares=stats['total_shares'] or 0,
            total_shares_value=stats['total_value'] or Decimal('0.00')
        )
        
    except Exception as e:
        logger.error(f"Error updating period statistics after delete: {e}")


# =============================================================================
# DIVIDEND RATE SIGNALS
# =============================================================================

@receiver(post_save, sender=DividendRate)
def log_dividend_rate_creation(sender, instance, created, **kwargs):
    """
    Log when a dividend rate tier is created.
    """
    if created:
        logger.info(
            f"Dividend rate tier created: {instance.tier_name} | "
            f"Period: {instance.dividend_period.name} | "
            f"Rate: {instance.rate}% | "
            f"Shares: {instance.min_shares}-{instance.max_shares or 'unlimited'}"
        )


# =============================================================================
# DIVIDEND DISBURSEMENT SIGNALS
# =============================================================================

@receiver(pre_save, sender=DividendDisbursement)
def generate_batch_number(sender, instance, **kwargs):
    """
    Generate batch number if not set.
    Delegates to utils.generate_disbursement_batch_number() for generation logic.
    """
    if not instance.batch_number:
        from .utils import generate_disbursement_batch_number
        
        instance.batch_number = generate_disbursement_batch_number()
        
        logger.info(f"Generated disbursement batch number: {instance.batch_number}")


@receiver(pre_save, sender=DividendDisbursement)
def calculate_disbursement_statistics(sender, instance, **kwargs):
    """
    Calculate completion percentage and success rate.
    """
    # Calculate completion percentage
    if instance.total_members > 0:
        completion = (instance.processed_members / instance.total_members) * 100
        logger.debug(f"Disbursement {instance.batch_number} completion: {completion:.2f}%")
    
    # Calculate success rate
    if instance.processed_members > 0:
        success_rate = (instance.successful_members / instance.processed_members) * 100
        logger.debug(f"Disbursement {instance.batch_number} success rate: {success_rate:.2f}%")


@receiver(post_save, sender=DividendDisbursement)
def log_disbursement_creation(sender, instance, created, **kwargs):
    """
    Log when a disbursement batch is created.
    """
    if created:
        logger.info(
            f"Disbursement batch created: {instance.batch_number} | "
            f"Period: {instance.dividend_period.name} | "
            f"Method: {instance.get_disbursement_method_display()} | "
            f"Total Members: {instance.total_members} | "
            f"Total Amount: {instance.total_amount}"
        )


@receiver(post_save, sender=DividendDisbursement)
def update_period_status_on_disbursement_start(sender, instance, created, **kwargs):
    """
    Update period status when disbursement starts.
    """
    if instance.status == 'PROCESSING':
        period = instance.dividend_period
        
        if period.status != 'DISBURSING':
            DividendPeriod.objects.filter(pk=period.pk).update(
                status='DISBURSING'
            )
            logger.info(f"Period {period.name} status changed to DISBURSING")


# =============================================================================
# DIVIDEND PAYMENT SIGNALS
# =============================================================================

@receiver(post_save, sender=DividendPayment)
def log_payment_creation(sender, instance, created, **kwargs):
    """
    Log when a dividend payment is created.
    """
    if created:
        logger.info(
            f"Dividend payment created: {instance.member_dividend.member.get_full_name()} | "
            f"Amount: {instance.amount} | "
            f"Batch: {instance.disbursement.batch_number} | "
            f"Status: {instance.get_status_display()}"
        )


@receiver(post_save, sender=DividendPayment)
def update_disbursement_statistics_on_payment(sender, instance, **kwargs):
    """
    Update disbursement statistics when payment status changes.
    """
    try:
        disbursement = instance.disbursement
        
        # Count payments by status
        from django.db.models import Count, Sum
        
        stats = disbursement.payments.aggregate(
            total=Count('id'),
            completed=Count('id', filter=Q(status='COMPLETED')),
            failed=Count('id', filter=Q(status='FAILED')),
            processed_amount=Sum('amount', filter=Q(status='COMPLETED'))
        )
        
        # Update disbursement
        DividendDisbursement.objects.filter(pk=disbursement.pk).update(
            processed_members=stats['total'] or 0,
            successful_members=stats['completed'] or 0,
            failed_members=stats['failed'] or 0,
            processed_amount=stats['processed_amount'] or Decimal('0.00')
        )
        
    except Exception as e:
        logger.error(f"Error updating disbursement statistics: {e}")


@receiver(pre_save, sender=DividendPayment)
def update_last_retry_date(sender, instance, **kwargs):
    """
    Update last retry date when payment is retried.
    """
    if instance.pk:
        try:
            old_instance = DividendPayment.objects.get(pk=instance.pk)
            
            # Check if retry count increased
            if instance.retry_count > old_instance.retry_count:
                instance.last_retry_date = timezone.now()
                
        except DividendPayment.DoesNotExist:
            pass


# =============================================================================
# DIVIDEND PREFERENCE SIGNALS
# =============================================================================

@receiver(pre_save, sender=DividendPreference)
def ensure_single_default_preference(sender, instance, **kwargs):
    """
    Ensure only one default preference per member.
    """
    if instance.is_default and not instance.dividend_period:
        # Clear other defaults for this member
        DividendPreference.objects.filter(
            member=instance.member,
            is_default=True,
            dividend_period__isnull=True
        ).exclude(pk=instance.pk).update(is_default=False)


@receiver(post_save, sender=DividendPreference)
def log_preference_creation(sender, instance, created, **kwargs):
    """
    Log when a dividend preference is created.
    """
    if created:
        period_str = f" for {instance.dividend_period.name}" if instance.dividend_period else " (Default)"
        logger.info(
            f"Dividend preference created: {instance.member.get_full_name()} | "
            f"Method: {instance.get_preference_method_display()}{period_str}"
        )


# =============================================================================
# CLEANUP SIGNALS
# =============================================================================

@receiver(post_delete, sender=DividendPeriod)
def log_period_deletion(sender, instance, **kwargs):
    """
    Log when a dividend period is deleted (should be rare).
    """
    logger.warning(
        f"Dividend period DELETED: {instance.name} | "
        f"Total Amount: {instance.total_dividend_amount} | "
        f"Status: {instance.get_status_display()}"
    )


@receiver(post_delete, sender=MemberDividend)
def log_member_dividend_deletion(sender, instance, **kwargs):
    """
    Log when a member dividend is deleted.
    """
    logger.warning(
        f"Member dividend DELETED: {instance.member.get_full_name()} | "
        f"Period: {instance.dividend_period.name} | "
        f"Amount: {instance.net_dividend}"
    )


@receiver(post_delete, sender=DividendPayment)
def log_payment_deletion(sender, instance, **kwargs):
    """
    Log when a dividend payment is deleted (should be rare).
    """
    logger.warning(
        f"Dividend payment DELETED: {instance.member_dividend.member.get_full_name()} | "
        f"Amount: {instance.amount} | "
        f"Batch: {instance.disbursement.batch_number}"
    )


# =============================================================================
# SIGNAL DEBUGGING HELPERS
# =============================================================================

def disable_dividend_signals():
    """
    Temporarily disable dividend signals (useful for bulk operations).
    
    Usage:
        from dividends.signals import disable_dividend_signals, enable_dividend_signals
        
        disable_dividend_signals()
        # ... perform bulk operations ...
        enable_dividend_signals()
    """
    from django.db.models.signals import pre_save, post_save, post_delete
    
    signals_to_disconnect = [
        # Period signals
        (pre_save, set_declaration_date, DividendPeriod),
        (post_save, log_dividend_period_creation, DividendPeriod),
        (post_save, update_period_status_on_completion, DividendPeriod),
        
        # Member dividend signals
        (pre_save, calculate_net_dividend, MemberDividend),
        (pre_save, set_applied_rate, MemberDividend),
        (post_save, log_member_dividend_creation, MemberDividend),
        (post_save, update_period_statistics_on_dividend_change, MemberDividend),
        (post_delete, update_period_statistics_on_dividend_delete, MemberDividend),
        
        # Rate signals
        (post_save, log_dividend_rate_creation, DividendRate),
        
        # Disbursement signals
        (pre_save, generate_batch_number, DividendDisbursement),
        (pre_save, calculate_disbursement_statistics, DividendDisbursement),
        (post_save, log_disbursement_creation, DividendDisbursement),
        (post_save, update_period_status_on_disbursement_start, DividendDisbursement),
        
        # Payment signals
        (post_save, log_payment_creation, DividendPayment),
        (post_save, update_disbursement_statistics_on_payment, DividendPayment),
        (pre_save, update_last_retry_date, DividendPayment),
        
        # Preference signals
        (pre_save, ensure_single_default_preference, DividendPreference),
        (post_save, log_preference_creation, DividendPreference),
    ]
    
    for signal, handler, model in signals_to_disconnect:
        signal.disconnect(handler, sender=model)
    
    logger.warning("Dividend signals DISABLED")


def enable_dividend_signals():
    """
    Re-enable dividend signals after being disabled.
    """
    from django.db.models.signals import pre_save, post_save, post_delete
    
    signals_to_reconnect = [
        # Period signals
        (pre_save, set_declaration_date, DividendPeriod),
        (post_save, log_dividend_period_creation, DividendPeriod),
        (post_save, update_period_status_on_completion, DividendPeriod),
        
        # Member dividend signals
        (pre_save, calculate_net_dividend, MemberDividend),
        (pre_save, set_applied_rate, MemberDividend),
        (post_save, log_member_dividend_creation, MemberDividend),
        (post_save, update_period_statistics_on_dividend_change, MemberDividend),
        (post_delete, update_period_statistics_on_dividend_delete, MemberDividend),
        
        # Rate signals
        (post_save, log_dividend_rate_creation, DividendRate),
        
        # Disbursement signals
        (pre_save, generate_batch_number, DividendDisbursement),
        (pre_save, calculate_disbursement_statistics, DividendDisbursement),
        (post_save, log_disbursement_creation, DividendDisbursement),
        (post_save, update_period_status_on_disbursement_start, DividendDisbursement),
        
        # Payment signals
        (post_save, log_payment_creation, DividendPayment),
        (post_save, update_disbursement_statistics_on_payment, DividendPayment),
        (pre_save, update_last_retry_date, DividendPayment),
        
        # Preference signals
        (pre_save, ensure_single_default_preference, DividendPreference),
        (post_save, log_preference_creation, DividendPreference),
    ]
    
    for signal, handler, model in signals_to_reconnect:
        signal.connect(handler, sender=model)
    
    logger.warning("Dividend signals ENABLED")


# =============================================================================
# APP READY - ENSURE SIGNALS ARE LOADED
# =============================================================================

def ready():
    """
    Called when the app is ready. Ensures signals are registered.
    This should be called from apps.py DividendsConfig.ready()
    """
    logger.info("Dividend signals registered successfully")