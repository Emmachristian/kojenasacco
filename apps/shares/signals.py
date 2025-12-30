# shares/signals.py

"""
Shares Signals

Handles automatic operations on model save/delete:
- Transaction number generation
- Certificate number generation
- Transfer request number generation
- Total amount calculation
- Status updates
- Balance tracking
- Certificate issuance
- Validation

All number generation is delegated to utils.py for clean separation.
"""

from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction as db_transaction
from decimal import Decimal
import logging

from .models import (
    ShareCapital,
    ShareTransaction,
    ShareCertificate,
    ShareTransferRequest,
)

logger = logging.getLogger(__name__)


# =============================================================================
# SHARE CAPITAL SIGNALS
# =============================================================================

@receiver(post_save, sender=ShareCapital)
def log_share_capital_creation(sender, instance, created, **kwargs):
    """
    Log when a new share capital configuration is created.
    """
    if created:
        logger.info(
            f"New share capital created: {instance.name} | "
            f"Share Price: {instance.share_price} | "
            f"Min Shares: {instance.minimum_shares} | "
            f"Max Shares: {instance.maximum_shares or 'Unlimited'}"
        )


@receiver(pre_save, sender=ShareCapital)
def deactivate_previous_share_capital(sender, instance, **kwargs):
    """
    Deactivate previous share capital when new one is activated.
    """
    if instance.is_active and instance.pk is None:  # New active share capital
        # Deactivate all other active share capitals
        ShareCapital.objects.filter(is_active=True).update(is_active=False)
        
        logger.info(f"Deactivated previous share capital configurations")


# =============================================================================
# SHARE TRANSACTION SIGNALS
# =============================================================================

@receiver(pre_save, sender=ShareTransaction)
def generate_transaction_number(sender, instance, **kwargs):
    """
    Generate transaction number if not set.
    Delegates to utils.generate_transaction_number() for generation logic.
    """
    if not instance.transaction_number:
        from .utils import generate_transaction_number
        
        instance.transaction_number = generate_transaction_number(instance.transaction_type)
        
        logger.info(f"Generated transaction number: {instance.transaction_number}")


@receiver(pre_save, sender=ShareTransaction)
def calculate_transaction_total(sender, instance, **kwargs):
    """
    Calculate total amount from shares and price.
    """
    if instance.shares_count and instance.price_per_share:
        instance.total_amount = instance.shares_count * instance.price_per_share
        
        logger.debug(
            f"Calculated total for {instance.transaction_number}: {instance.total_amount}"
        )


@receiver(pre_save, sender=ShareTransaction)
def set_financial_period(sender, instance, **kwargs):
    """
    Set financial period if not set.
    """
    if not instance.financial_period:
        from core.utils import get_active_fiscal_period
        
        try:
            instance.financial_period = get_active_fiscal_period()
            logger.debug(f"Set financial period for transaction {instance.transaction_number}")
        except Exception as e:
            logger.warning(f"Could not set financial period: {e}")


@receiver(pre_save, sender=ShareTransaction)
def set_share_price_if_not_set(sender, instance, **kwargs):
    """
    Set price per share from active share capital if not set.
    """
    if not instance.price_per_share and instance.share_capital:
        instance.price_per_share = instance.share_capital.share_price
        
        logger.debug(
            f"Set price per share for {instance.transaction_number}: {instance.price_per_share}"
        )


@receiver(pre_save, sender=ShareTransaction)
def validate_transaction_before_save(sender, instance, **kwargs):
    """
    Perform validation before saving transaction.
    """
    # Only validate on creation or when status changes to COMPLETED
    if instance.pk:
        try:
            old_instance = ShareTransaction.objects.get(pk=instance.pk)
            
            # Skip validation if already validated
            if old_instance.status == instance.status:
                return
        except ShareTransaction.DoesNotExist:
            pass
    
    # Validate based on transaction type
    if instance.transaction_type == 'BUY' and instance.status == 'COMPLETED':
        from .utils import validate_share_purchase
        
        is_valid, message = validate_share_purchase(
            instance.member,
            instance.shares_count,
            instance.share_capital
        )
        
        if not is_valid:
            logger.warning(
                f"Share purchase validation failed for {instance.member.get_full_name()}: {message}"
            )
            # Don't prevent save, but log the issue
    
    elif instance.transaction_type == 'SELL' and instance.status == 'COMPLETED':
        from .utils import validate_share_sale
        
        is_valid, message = validate_share_sale(
            instance.member,
            instance.shares_count,
            instance.share_capital
        )
        
        if not is_valid:
            logger.warning(
                f"Share sale validation failed for {instance.member.get_full_name()}: {message}"
            )


@receiver(post_save, sender=ShareTransaction)
def log_transaction_creation(sender, instance, created, **kwargs):
    """
    Log when a share transaction is created.
    """
    if created:
        logger.info(
            f"Share transaction created: {instance.transaction_number} | "
            f"Type: {instance.get_transaction_type_display()} | "
            f"Member: {instance.member.get_full_name()} | "
            f"Shares: {instance.shares_count} | "
            f"Amount: {instance.total_amount}"
        )


@receiver(post_save, sender=ShareTransaction)
def update_member_share_balance_on_transaction(sender, instance, **kwargs):
    """
    Update member's share balance summary when transaction is completed.
    
    Note: This assumes you have a shares_balance field on Member model.
    If not, this can be removed or adjusted.
    """
    # Only update when transaction is completed and not reversed
    if instance.status == 'COMPLETED' and not instance.is_reversed:
        try:
            from .utils import calculate_member_share_balance
            
            # Recalculate balance
            balance_info = calculate_member_share_balance(instance.member)
            
            # Update member's share balance (if field exists)
            if hasattr(instance.member, 'shares_balance'):
                instance.member.shares_balance = balance_info['net_shares']
                instance.member.shares_value = balance_info['total_value']
                instance.member.save(update_fields=['shares_balance', 'shares_value', 'updated_at'])
                
                logger.debug(
                    f"Updated share balance for {instance.member.get_full_name()}: "
                    f"{balance_info['net_shares']} shares"
                )
        except Exception as e:
            logger.error(f"Error updating member share balance: {e}")


@receiver(post_save, sender=ShareTransaction)
def auto_issue_certificate_on_purchase(sender, instance, created, **kwargs):
    """
    Automatically issue certificate when share purchase is completed.
    """
    # Only for completed purchases
    if instance.transaction_type == 'BUY' and instance.status == 'COMPLETED':
        # Check if certificates should be issued
        if instance.share_capital.issue_certificates:
            try:
                # Check if certificate already exists for this transaction
                existing_cert = ShareCertificate.objects.filter(
                    member=instance.member,
                    shares_count=instance.shares_count,
                    share_price=instance.price_per_share,
                    issue_date=instance.transaction_date.date(),
                    status='ACTIVE'
                ).exists()
                
                if not existing_cert:
                    # Create certificate (number will be auto-generated by signal)
                    certificate = ShareCertificate.objects.create(
                        member=instance.member,
                        share_capital=instance.share_capital,
                        shares_count=instance.shares_count,
                        share_price=instance.price_per_share,
                        issue_date=instance.transaction_date.date(),
                        status='ACTIVE'
                    )
                    
                    logger.info(
                        f"Auto-issued certificate {certificate.certificate_number} for "
                        f"transaction {instance.transaction_number}"
                    )
            except Exception as e:
                logger.error(f"Error auto-issuing certificate: {e}")


@receiver(post_save, sender=ShareTransaction)
def create_linked_transfer_transaction(sender, instance, created, **kwargs):
    """
    Create linked transaction for transfers.
    
    When TRANSFER_OUT is completed, create corresponding TRANSFER_IN.
    """
    if created and instance.transaction_type == 'TRANSFER_OUT' and instance.status == 'COMPLETED':
        # Check if linked transaction already exists
        if not instance.linked_transaction:
            try:
                # Create TRANSFER_IN transaction
                transfer_in = ShareTransaction.objects.create(
                    member=instance.transfer_to,
                    share_capital=instance.share_capital,
                    transaction_type='TRANSFER_IN',
                    transaction_date=instance.transaction_date,
                    shares_count=instance.shares_count,
                    price_per_share=instance.price_per_share,
                    total_amount=instance.total_amount,
                    transfer_from=instance.transfer_from,
                    transfer_to=instance.transfer_to,
                    linked_transaction=instance,
                    status='COMPLETED'
                )
                
                # Link back
                instance.linked_transaction = transfer_in
                instance.save(update_fields=['linked_transaction'])
                
                logger.info(
                    f"Created linked TRANSFER_IN transaction {transfer_in.transaction_number} "
                    f"for TRANSFER_OUT {instance.transaction_number}"
                )
            except Exception as e:
                logger.error(f"Error creating linked transfer transaction: {e}")


# =============================================================================
# SHARE CERTIFICATE SIGNALS
# =============================================================================

@receiver(pre_save, sender=ShareCertificate)
def generate_certificate_number_signal(sender, instance, **kwargs):
    """
    Generate certificate number if not set.
    Delegates to utils.generate_certificate_number() for generation logic.
    """
    if not instance.certificate_number:
        from .utils import generate_certificate_number
        
        prefix = instance.share_capital.certificate_prefix if instance.share_capital else 'SC'
        instance.certificate_number = generate_certificate_number(prefix)
        
        logger.info(f"Generated certificate number: {instance.certificate_number}")


@receiver(pre_save, sender=ShareCertificate)
def calculate_certificate_total_value(sender, instance, **kwargs):
    """
    Calculate total value of shares on certificate.
    """
    if instance.shares_count and instance.share_price:
        instance.total_value = instance.shares_count * instance.share_price
        
        logger.debug(
            f"Calculated certificate value: {instance.total_value} "
            f"({instance.shares_count} × {instance.share_price})"
        )


@receiver(pre_save, sender=ShareCertificate)
def update_validity_based_on_status(sender, instance, **kwargs):
    """
    Update is_valid flag based on status.
    """
    if instance.status in ['CANCELLED', 'TRANSFERRED', 'REISSUED']:
        instance.is_valid = False
    elif instance.status == 'ACTIVE':
        instance.is_valid = True


@receiver(post_save, sender=ShareCertificate)
def log_certificate_creation(sender, instance, created, **kwargs):
    """
    Log when a certificate is created.
    """
    if created:
        logger.info(
            f"Share certificate issued: {instance.certificate_number} | "
            f"Member: {instance.member.get_full_name()} | "
            f"Shares: {instance.shares_count} | "
            f"Value: {instance.total_value}"
        )


@receiver(post_save, sender=ShareCertificate)
def cancel_previous_certificates_on_reissue(sender, instance, **kwargs):
    """
    When a certificate is reissued, mark the old one as reissued.
    """
    if instance.replaced_by:
        # This is an old certificate being replaced
        if instance.status != 'REISSUED':
            instance.status = 'REISSUED'
            instance.is_valid = False
            instance.save(update_fields=['status', 'is_valid'])
            
            logger.info(
                f"Marked certificate {instance.certificate_number} as reissued, "
                f"replaced by {instance.replaced_by.certificate_number}"
            )


# =============================================================================
# SHARE TRANSFER REQUEST SIGNALS
# =============================================================================

@receiver(pre_save, sender=ShareTransferRequest)
def generate_transfer_request_number_signal(sender, instance, **kwargs):
    """
    Generate request number if not set.
    Delegates to utils.generate_transfer_request_number() for generation logic.
    """
    if not instance.request_number:
        from .utils import generate_transfer_request_number
        
        instance.request_number = generate_transfer_request_number()
        
        logger.info(f"Generated transfer request number: {instance.request_number}")


@receiver(pre_save, sender=ShareTransferRequest)
def calculate_transfer_request_total(sender, instance, **kwargs):
    """
    Calculate total amount and transfer fee.
    """
    if instance.shares_count and instance.share_price:
        instance.total_amount = instance.shares_count * instance.share_price
        
        # Calculate transfer fee if not set
        if not instance.transfer_fee:
            from shares.models import ShareCapital
            
            share_capital = ShareCapital.get_active_share_capital()
            if share_capital:
                instance.transfer_fee = share_capital.calculate_transfer_fee(instance.shares_count)
        
        logger.debug(
            f"Calculated transfer request total: {instance.total_amount}, "
            f"Fee: {instance.transfer_fee}"
        )


@receiver(pre_save, sender=ShareTransferRequest)
def set_approval_date_on_status_change(sender, instance, **kwargs):
    """
    Set approval/completion dates when status changes.
    """
    if instance.pk:
        try:
            old_instance = ShareTransferRequest.objects.get(pk=instance.pk)
            
            # Check if status changed to APPROVED
            if old_instance.status != 'APPROVED' and instance.status == 'APPROVED':
                if not instance.approval_date:
                    instance.approval_date = timezone.now()
            
            # Check if status changed to COMPLETED
            if old_instance.status != 'COMPLETED' and instance.status == 'COMPLETED':
                if not instance.completion_date:
                    instance.completion_date = timezone.now()
                    
        except ShareTransferRequest.DoesNotExist:
            pass


@receiver(post_save, sender=ShareTransferRequest)
def log_transfer_request_creation(sender, instance, created, **kwargs):
    """
    Log when a transfer request is created.
    """
    if created:
        logger.info(
            f"Share transfer request created: {instance.request_number} | "
            f"From: {instance.from_member.get_full_name()} | "
            f"To: {instance.to_member.get_full_name()} | "
            f"Shares: {instance.shares_count} | "
            f"Amount: {instance.total_amount}"
        )


@receiver(post_save, sender=ShareTransferRequest)
def create_transactions_on_transfer_completion(sender, instance, **kwargs):
    """
    Create share transactions when transfer request is completed.
    """
    if instance.status == 'COMPLETED':
        # Check if transactions already created
        if not instance.transfer_out_transaction or not instance.transfer_in_transaction:
            try:
                from shares.models import ShareCapital
                
                share_capital = ShareCapital.get_active_share_capital()
                
                # Create TRANSFER_OUT transaction
                if not instance.transfer_out_transaction:
                    transfer_out = ShareTransaction.objects.create(
                        member=instance.from_member,
                        share_capital=share_capital,
                        transaction_type='TRANSFER_OUT',
                        shares_count=instance.shares_count,
                        price_per_share=instance.share_price,
                        total_amount=instance.total_amount,
                        transfer_from=instance.from_member,
                        transfer_to=instance.to_member,
                        transfer_fee=instance.transfer_fee,
                        status='COMPLETED',
                        description=f"Transfer to {instance.to_member.get_full_name()} via {instance.request_number}"
                    )
                    
                    instance.transfer_out_transaction = transfer_out
                
                # Create TRANSFER_IN transaction
                if not instance.transfer_in_transaction:
                    transfer_in = ShareTransaction.objects.create(
                        member=instance.to_member,
                        share_capital=share_capital,
                        transaction_type='TRANSFER_IN',
                        shares_count=instance.shares_count,
                        price_per_share=instance.share_price,
                        total_amount=instance.total_amount,
                        transfer_from=instance.from_member,
                        transfer_to=instance.to_member,
                        linked_transaction=instance.transfer_out_transaction,
                        status='COMPLETED',
                        description=f"Transfer from {instance.from_member.get_full_name()} via {instance.request_number}"
                    )
                    
                    instance.transfer_in_transaction = transfer_in
                    
                    # Link transactions
                    if instance.transfer_out_transaction:
                        instance.transfer_out_transaction.linked_transaction = transfer_in
                        instance.transfer_out_transaction.save(update_fields=['linked_transaction'])
                
                # Save request with transaction references
                instance.save(update_fields=['transfer_out_transaction', 'transfer_in_transaction'])
                
                logger.info(
                    f"Created share transfer transactions for request {instance.request_number}"
                )
                
            except Exception as e:
                logger.error(f"Error creating transfer transactions: {e}")


# =============================================================================
# CLEANUP SIGNALS
# =============================================================================

@receiver(post_delete, sender=ShareTransaction)
def log_transaction_deletion(sender, instance, **kwargs):
    """
    Log when a share transaction is deleted (should be rare).
    """
    logger.warning(
        f"Share transaction DELETED: {instance.transaction_number} | "
        f"Type: {instance.get_transaction_type_display()} | "
        f"Member: {instance.member.get_full_name()} | "
        f"Shares: {instance.shares_count}"
    )


@receiver(post_delete, sender=ShareCertificate)
def log_certificate_deletion(sender, instance, **kwargs):
    """
    Log when a certificate is deleted (should be rare).
    """
    logger.warning(
        f"Share certificate DELETED: {instance.certificate_number} | "
        f"Member: {instance.member.get_full_name()} | "
        f"Shares: {instance.shares_count}"
    )


# =============================================================================
# SIGNAL DEBUGGING HELPERS
# =============================================================================

def disable_share_signals():
    """
    Temporarily disable share signals (useful for bulk operations).
    
    Usage:
        from shares.signals import disable_share_signals, enable_share_signals
        
        disable_share_signals()
        # ... perform bulk operations ...
        enable_share_signals()
    """
    from django.db.models.signals import pre_save, post_save, post_delete
    
    signals_to_disconnect = [
        # Share capital signals
        (post_save, log_share_capital_creation, ShareCapital),
        (pre_save, deactivate_previous_share_capital, ShareCapital),
        
        # Transaction signals
        (pre_save, generate_transaction_number, ShareTransaction),
        (pre_save, calculate_transaction_total, ShareTransaction),
        (pre_save, set_financial_period, ShareTransaction),
        (pre_save, set_share_price_if_not_set, ShareTransaction),
        (pre_save, validate_transaction_before_save, ShareTransaction),
        (post_save, log_transaction_creation, ShareTransaction),
        (post_save, update_member_share_balance_on_transaction, ShareTransaction),
        (post_save, auto_issue_certificate_on_purchase, ShareTransaction),
        (post_save, create_linked_transfer_transaction, ShareTransaction),
        
        # Certificate signals
        (pre_save, generate_certificate_number_signal, ShareCertificate),
        (pre_save, calculate_certificate_total_value, ShareCertificate),
        (pre_save, update_validity_based_on_status, ShareCertificate),
        (post_save, log_certificate_creation, ShareCertificate),
        (post_save, cancel_previous_certificates_on_reissue, ShareCertificate),
        
        # Transfer request signals
        (pre_save, generate_transfer_request_number_signal, ShareTransferRequest),
        (pre_save, calculate_transfer_request_total, ShareTransferRequest),
        (pre_save, set_approval_date_on_status_change, ShareTransferRequest),
        (post_save, log_transfer_request_creation, ShareTransferRequest),
        (post_save, create_transactions_on_transfer_completion, ShareTransferRequest),
    ]
    
    for signal, handler, model in signals_to_disconnect:
        signal.disconnect(handler, sender=model)
    
    logger.warning("Share signals DISABLED")


def enable_share_signals():
    """
    Re-enable share signals after being disabled.
    """
    from django.db.models.signals import pre_save, post_save, post_delete
    
    signals_to_reconnect = [
        # Share capital signals
        (post_save, log_share_capital_creation, ShareCapital),
        (pre_save, deactivate_previous_share_capital, ShareCapital),
        
        # Transaction signals
        (pre_save, generate_transaction_number, ShareTransaction),
        (pre_save, calculate_transaction_total, ShareTransaction),
        (pre_save, set_financial_period, ShareTransaction),
        (pre_save, set_share_price_if_not_set, ShareTransaction),
        (pre_save, validate_transaction_before_save, ShareTransaction),
        (post_save, log_transaction_creation, ShareTransaction),
        (post_save, update_member_share_balance_on_transaction, ShareTransaction),
        (post_save, auto_issue_certificate_on_purchase, ShareTransaction),
        (post_save, create_linked_transfer_transaction, ShareTransaction),
        
        # Certificate signals
        (pre_save, generate_certificate_number_signal, ShareCertificate),
        (pre_save, calculate_certificate_total_value, ShareCertificate),
        (pre_save, update_validity_based_on_status, ShareCertificate),
        (post_save, log_certificate_creation, ShareCertificate),
        (post_save, cancel_previous_certificates_on_reissue, ShareCertificate),
        
        # Transfer request signals
        (pre_save, generate_transfer_request_number_signal, ShareTransferRequest),
        (pre_save, calculate_transfer_request_total, ShareTransferRequest),
        (pre_save, set_approval_date_on_status_change, ShareTransferRequest),
        (post_save, log_transfer_request_creation, ShareTransferRequest),
        (post_save, create_transactions_on_transfer_completion, ShareTransferRequest),
    ]
    
    for signal, handler, model in signals_to_reconnect:
        signal.connect(handler, sender=model)
    
    logger.warning("Share signals ENABLED")


# =============================================================================
# APP READY - ENSURE SIGNALS ARE LOADED
# =============================================================================

def ready():
    """
    Called when the app is ready. Ensures signals are registered.
    This should be called from apps.py SharesConfig.ready()
    """
    logger.info("Share signals registered successfully")