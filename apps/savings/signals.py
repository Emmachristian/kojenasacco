# savings/signals.py

"""
Savings Signals

Handles automatic operations on model save/delete:
- Account number generation
- Transaction ID generation
- Balance updates
- Status changes
- Interest posting automation
- Standing order date calculation
- Savings goal progress updates

All number generation is delegated to utils.py for clean separation.
"""

from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction as db_transaction
from decimal import Decimal
import logging

from .models import (
    SavingsAccount,
    SavingsTransaction,
    InterestCalculation,
    StandingOrder,
    SavingsGoal,
)

logger = logging.getLogger(__name__)


# =============================================================================
# SAVINGS ACCOUNT SIGNALS
# =============================================================================

@receiver(pre_save, sender=SavingsAccount)
def generate_savings_account_number(sender, instance, **kwargs):
    """
    Generate account number if not set.
    Delegates to utils.generate_account_number() for actual generation logic.
    """
    if not instance.account_number:
        from .utils import generate_account_number
        
        # Extract product code if available
        product_code = None
        if instance.savings_product:
            product_code = instance.savings_product.code
        
        # Extract member number if available
        member_number = None
        if instance.member:
            if hasattr(instance.member, 'membership_number'):
                member_number = instance.member.membership_number
            elif hasattr(instance.member, 'member_number'):
                member_number = instance.member.member_number
        
        # Generate account number
        instance.account_number = generate_account_number(
            product_code=product_code,
            member_number=member_number
        )
        
        logger.info(f"Generated account number: {instance.account_number} for member {instance.member.get_full_name() if instance.member else 'Unknown'}")


@receiver(pre_save, sender=SavingsAccount)
def set_fixed_deposit_dates(sender, instance, **kwargs):
    """
    Set maturity date for fixed deposits if not already set.
    """
    if instance.is_fixed_deposit and instance.term_length_days and not instance.maturity_date:
        from .utils import calculate_maturity_date
        
        instance.maturity_date = calculate_maturity_date(
            instance.opening_date,
            instance.term_length_days
        )
        
        logger.info(f"Set maturity date for FD account {instance.account_number}: {instance.maturity_date}")


@receiver(pre_save, sender=SavingsAccount)
def update_available_balance_on_save(sender, instance, **kwargs):
    """
    Automatically update available balance when hold amount or current balance changes.
    Only updates if the account already exists (not on creation).
    """
    # Only update for existing accounts (not during creation)
    if instance.pk:
        from .utils import calculate_available_balance
        
        # Calculate what available balance should be
        calculated_available = calculate_available_balance(
            instance.current_balance,
            instance.hold_amount
        )
        
        # Update if different (avoids unnecessary signal loops)
        if calculated_available != instance.available_balance:
            instance.available_balance = calculated_available
            logger.debug(f"Updated available balance for account {instance.account_number}: {calculated_available}")


@receiver(post_save, sender=SavingsAccount)
def set_activated_date(sender, instance, created, **kwargs):
    """
    Set activated date when account status changes to ACTIVE.
    """
    if not created and instance.status == 'ACTIVE' and not instance.activated_date:
        # Use update to avoid triggering signals again
        SavingsAccount.objects.filter(pk=instance.pk).update(
            activated_date=timezone.now().date()
        )
        logger.info(f"Set activated date for account {instance.account_number}")


@receiver(post_save, sender=SavingsAccount)
def log_account_creation(sender, instance, created, **kwargs):
    """
    Log when a new account is created.
    """
    if created:
        logger.info(
            f"New savings account created: {instance.account_number} | "
            f"Member: {instance.member.get_full_name() if instance.member else 'N/A'} | "
            f"Product: {instance.savings_product.name if instance.savings_product else 'N/A'} | "
            f"Opening Balance: {instance.current_balance}"
        )


# =============================================================================
# SAVINGS TRANSACTION SIGNALS
# =============================================================================

@receiver(pre_save, sender=SavingsTransaction)
def generate_savings_transaction_id(sender, instance, **kwargs):
    """
    Generate transaction ID if not set.
    Uses transaction type to determine prefix.
    """
    if not instance.transaction_id:
        from .utils import generate_transaction_id
        
        # Map transaction types to prefixes
        prefix_map = {
            'DEPOSIT': 'DEP',
            'WITHDRAWAL': 'WDL',
            'TRANSFER_IN': 'TFI',
            'TRANSFER_OUT': 'TFO',
            'INTEREST': 'INT',
            'FEE': 'FEE',
            'TAX': 'TAX',
            'ADJUSTMENT': 'ADJ',
            'REVERSAL': 'REV',
            'DIVIDEND': 'DIV',
            'MAINTENANCE_FEE': 'MNT',
        }
        
        prefix = prefix_map.get(instance.transaction_type, 'SAV')
        instance.transaction_id = generate_transaction_id(prefix)
        
        logger.info(f"Generated transaction ID: {instance.transaction_id} for {instance.transaction_type}")


@receiver(pre_save, sender=SavingsTransaction)
def calculate_transaction_running_balance(sender, instance, **kwargs):
    """
    Calculate running balance for transaction if not already set.
    """
    if not instance.running_balance or instance.running_balance == Decimal('0.00'):
        from .utils import calculate_running_balance
        
        instance.running_balance = calculate_running_balance(
            instance.account,
            instance.amount,
            instance.transaction_type
        )
        
        logger.debug(f"Calculated running balance for transaction {instance.transaction_id}: {instance.running_balance}")


@receiver(pre_save, sender=SavingsTransaction)
def set_financial_period(sender, instance, **kwargs):
    """
    Set financial period if not set.
    Uses current active fiscal period.
    """
    if not instance.financial_period:
        from core.utils import get_active_fiscal_period
        
        try:
            instance.financial_period = get_active_fiscal_period()
            logger.debug(f"Set financial period for transaction {instance.transaction_id}")
        except Exception as e:
            logger.warning(f"Could not set financial period: {e}")
            # Continue without setting - not critical for transaction


@receiver(pre_save, sender=SavingsTransaction)
def set_transaction_dates(sender, instance, **kwargs):
    """
    Set post_date and value_date if not already set.
    """
    today = timezone.now().date()
    
    # Set post_date if not set
    if not instance.post_date:
        instance.post_date = today
    
    # Set value_date if not set (same as post_date by default)
    if not instance.value_date:
        instance.value_date = instance.post_date or today


@receiver(post_save, sender=SavingsTransaction)
def update_account_balance_after_transaction(sender, instance, created, **kwargs):
    """
    Update account balance after transaction is created.
    Only processes new, non-reversed transactions.
    Uses atomic transaction to ensure consistency.
    """
    if created and not instance.is_reversed:
        account = instance.account
        
        with db_transaction.atomic():
            # Lock the account row for update
            account = SavingsAccount.objects.select_for_update().get(pk=account.pk)
            
            # Calculate new balance based on transaction type
            if instance.transaction_type in ['DEPOSIT', 'TRANSFER_IN', 'INTEREST', 'DIVIDEND']:
                # Credit transactions
                new_balance = account.current_balance + instance.amount
                logger.debug(f"Credit transaction: {account.current_balance} + {instance.amount} = {new_balance}")
                
            elif instance.transaction_type in ['WITHDRAWAL', 'TRANSFER_OUT', 'FEE', 'TAX', 'MAINTENANCE_FEE']:
                # Debit transactions
                total_debit = instance.amount + instance.fees + instance.tax_amount
                new_balance = account.current_balance - total_debit
                logger.debug(f"Debit transaction: {account.current_balance} - {total_debit} = {new_balance}")
                
            elif instance.transaction_type == 'ADJUSTMENT':
                # Adjustment (amount should have correct sign)
                new_balance = account.current_balance + instance.amount
                logger.debug(f"Adjustment transaction: {account.current_balance} + {instance.amount} = {new_balance}")
                
            else:
                # Unknown transaction type - don't change balance
                logger.warning(f"Unknown transaction type: {instance.transaction_type}")
                new_balance = account.current_balance
            
            # Update account balance
            from .utils import calculate_available_balance
            new_available = calculate_available_balance(new_balance, account.hold_amount)
            
            SavingsAccount.objects.filter(pk=account.pk).update(
                current_balance=new_balance,
                available_balance=new_available,
                updated_at=timezone.now()
            )
            
            logger.info(
                f"Updated account {account.account_number} balance: "
                f"{account.current_balance} → {new_balance} | "
                f"Transaction: {instance.transaction_id}"
            )


@receiver(post_save, sender=SavingsTransaction)
def log_transaction_creation(sender, instance, created, **kwargs):
    """
    Log when a new transaction is created.
    """
    if created:
        logger.info(
            f"New transaction created: {instance.transaction_id} | "
            f"Type: {instance.get_transaction_type_display()} | "
            f"Amount: {instance.amount} | "
            f"Account: {instance.account.account_number} | "
            f"Member: {instance.account.member.get_full_name() if instance.account.member else 'N/A'}"
        )


@receiver(pre_save, sender=SavingsTransaction)
def validate_reversal_transaction(sender, instance, **kwargs):
    """
    Ensure reversal transactions have an original transaction reference.
    """
    if instance.transaction_type == 'REVERSAL':
        if not instance.original_transaction:
            logger.warning(f"Reversal transaction {instance.transaction_id} created without original transaction reference")


# =============================================================================
# INTEREST CALCULATION SIGNALS
# =============================================================================

@receiver(post_save, sender=InterestCalculation)
def post_interest_to_account(sender, instance, created, **kwargs):
    """
    Automatically create interest transaction when calculation is marked as posted.
    Only processes when:
    1. Calculation is marked as posted
    2. No transaction exists yet
    3. Not during initial creation
    """
    if not created and instance.is_posted and not instance.transaction:
        try:
            with db_transaction.atomic():
                # Create interest transaction
                txn = SavingsTransaction.objects.create(
                    account=instance.account,
                    transaction_type='INTEREST',
                    amount=instance.net_interest,
                    tax_amount=instance.withholding_tax,
                    description=f"Interest for period {instance.period_start_date} to {instance.period_end_date}",
                    transaction_date=timezone.now(),
                    post_date=instance.posted_date or timezone.now().date(),
                    value_date=instance.posted_date or timezone.now().date(),
                )
                
                # Link transaction to calculation
                InterestCalculation.objects.filter(pk=instance.pk).update(
                    transaction=txn
                )
                
                # Update account interest tracking
                account = instance.account
                SavingsAccount.objects.filter(pk=account.pk).update(
                    total_interest_earned=account.total_interest_earned + instance.net_interest,
                    accrued_interest=Decimal('0.00'),  # Clear accrued interest after posting
                    last_interest_posted_date=instance.posted_date or timezone.now().date(),
                )
                
                logger.info(
                    f"Posted interest of {instance.net_interest} to account {account.account_number} | "
                    f"Transaction: {txn.transaction_id}"
                )
                
        except Exception as e:
            logger.error(f"Error posting interest for calculation {instance.id}: {e}")


@receiver(pre_save, sender=InterestCalculation)
def calculate_net_interest(sender, instance, **kwargs):
    """
    Automatically calculate net interest from gross interest and tax.
    """
    if instance.gross_interest and instance.withholding_tax:
        instance.net_interest = instance.gross_interest - instance.withholding_tax
        logger.debug(f"Calculated net interest: {instance.net_interest}")


@receiver(pre_save, sender=InterestCalculation)
def set_calculation_financial_period(sender, instance, **kwargs):
    """
    Set financial period for interest calculation if not set.
    """
    if not instance.financial_period:
        from core.utils import get_active_fiscal_period
        
        try:
            instance.financial_period = get_active_fiscal_period()
        except Exception as e:
            logger.warning(f"Could not set financial period for interest calculation: {e}")


# =============================================================================
# STANDING ORDER SIGNALS
# =============================================================================

@receiver(post_save, sender=StandingOrder)
def set_standing_order_next_run_date(sender, instance, created, **kwargs):
    """
    Set initial next_run_date for new standing orders.
    Sets to start_date if not already set.
    """
    if created and not instance.next_run_date:
        StandingOrder.objects.filter(pk=instance.pk).update(
            next_run_date=instance.start_date
        )
        logger.info(f"Set initial next_run_date for standing order {instance.id}: {instance.start_date}")


@receiver(post_save, sender=StandingOrder)
def log_standing_order_creation(sender, instance, created, **kwargs):
    """
    Log when a new standing order is created.
    """
    if created:
        logger.info(
            f"New standing order created: ID {instance.id} | "
            f"From: {instance.source_account.account_number} | "
            f"To: {instance.destination_account.account_number if instance.destination_account else 'N/A'} | "
            f"Amount: {instance.amount} | "
            f"Frequency: {instance.get_frequency_display()} | "
            f"Status: {instance.get_status_display()}"
        )


@receiver(pre_save, sender=StandingOrder)
def validate_standing_order_dates(sender, instance, **kwargs):
    """
    Validate standing order dates before saving.
    """
    # Ensure start_date is not in the past (for new orders)
    if not instance.pk:  # New order
        today = timezone.now().date()
        if instance.start_date < today:
            logger.warning(f"Standing order start_date {instance.start_date} is in the past")
    
    # Ensure end_date is after start_date
    if instance.end_date and instance.start_date:
        if instance.end_date <= instance.start_date:
            logger.warning(f"Standing order end_date {instance.end_date} is not after start_date {instance.start_date}")


# =============================================================================
# SAVINGS GOAL SIGNALS
# =============================================================================

@receiver(pre_save, sender=SavingsGoal)
def update_savings_goal_progress(sender, instance, **kwargs):
    """
    Automatically update progress percentage and achievement status.
    """
    if instance.target_amount > 0:
        # Calculate progress percentage
        progress = (instance.current_amount / instance.target_amount) * 100
        instance.progress_percentage = min(progress, Decimal('100.00'))
        
        # Check if goal is achieved
        if progress >= 100 and not instance.is_achieved:
            instance.is_achieved = True
            if not instance.achievement_date:
                instance.achievement_date = timezone.now().date()
            
            logger.info(f"Savings goal '{instance.name}' marked as achieved!")
        
        # If goal was achieved but amount dropped below target
        elif progress < 100 and instance.is_achieved:
            logger.warning(f"Savings goal '{instance.name}' dropped below target after being achieved")
    else:
        instance.progress_percentage = Decimal('0.00')


@receiver(post_save, sender=SavingsGoal)
def log_goal_creation(sender, instance, created, **kwargs):
    """
    Log when a new savings goal is created.
    """
    if created:
        logger.info(
            f"New savings goal created: '{instance.name}' | "
            f"Account: {instance.account.account_number} | "
            f"Member: {instance.account.member.get_full_name() if instance.account.member else 'N/A'} | "
            f"Target: {instance.target_amount} | "
            f"Type: {instance.get_goal_type_display()}"
        )


@receiver(post_save, sender=SavingsGoal)
def log_goal_achievement(sender, instance, created, **kwargs):
    """
    Log when a goal is achieved (not during creation).
    """
    if not created and instance.is_achieved:
        # Check if this is a new achievement (not previously achieved)
        if instance.achievement_date == timezone.now().date():
            logger.info(
                f"🎉 Savings goal achieved! '{instance.name}' | "
                f"Account: {instance.account.account_number} | "
                f"Target: {instance.target_amount} | "
                f"Final Amount: {instance.current_amount}"
            )


# =============================================================================
# CLEANUP SIGNALS
# =============================================================================

@receiver(post_delete, sender=SavingsAccount)
def log_account_deletion(sender, instance, **kwargs):
    """
    Log when an account is deleted (should be rare).
    """
    logger.warning(
        f"Savings account DELETED: {instance.account_number} | "
        f"Member: {instance.member.get_full_name() if instance.member else 'N/A'} | "
        f"Final Balance: {instance.current_balance}"
    )


@receiver(post_delete, sender=SavingsTransaction)
def log_transaction_deletion(sender, instance, **kwargs):
    """
    Log when a transaction is deleted (should be very rare).
    """
    logger.warning(
        f"Transaction DELETED: {instance.transaction_id} | "
        f"Type: {instance.get_transaction_type_display()} | "
        f"Amount: {instance.amount} | "
        f"Account: {instance.account.account_number if instance.account else 'N/A'}"
    )


# =============================================================================
# SIGNAL DEBUGGING HELPERS
# =============================================================================

def disable_savings_signals():
    """
    Temporarily disable savings signals (useful for bulk operations).
    
    Usage:
        from savings.signals import disable_savings_signals, enable_savings_signals
        
        disable_savings_signals()
        # ... perform bulk operations ...
        enable_savings_signals()
    """
    from django.db.models.signals import pre_save, post_save, post_delete
    
    signals_to_disconnect = [
        (pre_save, generate_savings_account_number, SavingsAccount),
        (pre_save, set_fixed_deposit_dates, SavingsAccount),
        (pre_save, update_available_balance_on_save, SavingsAccount),
        (post_save, set_activated_date, SavingsAccount),
        (post_save, log_account_creation, SavingsAccount),
        (pre_save, generate_savings_transaction_id, SavingsTransaction),
        (pre_save, calculate_transaction_running_balance, SavingsTransaction),
        (pre_save, set_financial_period, SavingsTransaction),
        (pre_save, set_transaction_dates, SavingsTransaction),
        (post_save, update_account_balance_after_transaction, SavingsTransaction),
        (post_save, log_transaction_creation, SavingsTransaction),
        (post_save, post_interest_to_account, InterestCalculation),
        (pre_save, calculate_net_interest, InterestCalculation),
        (post_save, set_standing_order_next_run_date, StandingOrder),
        (post_save, log_standing_order_creation, StandingOrder),
        (pre_save, update_savings_goal_progress, SavingsGoal),
        (post_save, log_goal_creation, SavingsGoal),
        (post_save, log_goal_achievement, SavingsGoal),
    ]
    
    for signal, handler, model in signals_to_disconnect:
        signal.disconnect(handler, sender=model)
    
    logger.warning("Savings signals DISABLED")


def enable_savings_signals():
    """
    Re-enable savings signals after being disabled.
    """
    from django.db.models.signals import pre_save, post_save, post_delete
    
    signals_to_reconnect = [
        (pre_save, generate_savings_account_number, SavingsAccount),
        (pre_save, set_fixed_deposit_dates, SavingsAccount),
        (pre_save, update_available_balance_on_save, SavingsAccount),
        (post_save, set_activated_date, SavingsAccount),
        (post_save, log_account_creation, SavingsAccount),
        (pre_save, generate_savings_transaction_id, SavingsTransaction),
        (pre_save, calculate_transaction_running_balance, SavingsTransaction),
        (pre_save, set_financial_period, SavingsTransaction),
        (pre_save, set_transaction_dates, SavingsTransaction),
        (post_save, update_account_balance_after_transaction, SavingsTransaction),
        (post_save, log_transaction_creation, SavingsTransaction),
        (post_save, post_interest_to_account, InterestCalculation),
        (pre_save, calculate_net_interest, InterestCalculation),
        (post_save, set_standing_order_next_run_date, StandingOrder),
        (post_save, log_standing_order_creation, StandingOrder),
        (pre_save, update_savings_goal_progress, SavingsGoal),
        (post_save, log_goal_creation, SavingsGoal),
        (post_save, log_goal_achievement, SavingsGoal),
    ]
    
    for signal, handler, model in signals_to_reconnect:
        signal.connect(handler, sender=model)
    
    logger.warning("Savings signals ENABLED")


# =============================================================================
# APP READY - ENSURE SIGNALS ARE LOADED
# =============================================================================

def ready():
    """
    Called when the app is ready. Ensures signals are registered.
    This should be called from apps.py SavingsConfig.ready()
    """
    logger.info("Savings signals registered successfully")