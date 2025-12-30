# loans/signals.py

"""
Loans Signals

Handles automatic operations on model save/delete:
- Application number generation
- Loan number generation
- Payment number generation
- Balance updates after payments
- Status changes
- Schedule generation
- Automatic field population
- Payment allocation

All number generation is delegated to utils.py for clean separation.
"""

from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction as db_transaction
from decimal import Decimal
import logging

from .models import (
    LoanApplication,
    Loan,
    LoanPayment,
    LoanSchedule,
    LoanGuarantor,
    LoanCollateral,
    LoanDocument,
)

logger = logging.getLogger(__name__)


# =============================================================================
# LOAN APPLICATION SIGNALS
# =============================================================================

@receiver(pre_save, sender=LoanApplication)
def generate_application_number(sender, instance, **kwargs):
    """
    Generate application number if not set.
    Delegates to utils.generate_loan_application_number() for generation logic.
    """
    if not instance.application_number:
        from .utils import generate_loan_application_number
        
        # Get product code if available
        product_code = None
        if instance.loan_product:
            product_code = instance.loan_product.code
        
        instance.application_number = generate_loan_application_number(product_code)
        
        logger.info(f"Generated application number: {instance.application_number}")


@receiver(pre_save, sender=LoanApplication)
def calculate_application_fees(sender, instance, **kwargs):
    """
    Calculate processing and insurance fees if not already set.
    """
    if instance.loan_product and not instance.processing_fee_amount:
        instance.processing_fee_amount = instance.loan_product.calculate_processing_fee(
            instance.amount_requested
        )
        instance.insurance_fee_amount = instance.loan_product.calculate_insurance_fee(
            instance.amount_requested
        )
        
        logger.debug(
            f"Calculated fees for application {instance.application_number}: "
            f"Processing={instance.processing_fee_amount}, Insurance={instance.insurance_fee_amount}"
        )


@receiver(pre_save, sender=LoanApplication)
def set_application_financial_period(sender, instance, **kwargs):
    """
    Set financial period if not set.
    """
    if not instance.financial_period:
        from core.utils import get_active_fiscal_period
        
        try:
            instance.financial_period = get_active_fiscal_period()
            logger.debug(f"Set financial period for application {instance.application_number}")
        except Exception as e:
            logger.warning(f"Could not set financial period for application: {e}")


@receiver(pre_save, sender=LoanApplication)
def set_submission_date(sender, instance, **kwargs):
    """
    Set submission date when status changes to SUBMITTED.
    """
    if instance.pk:  # Only for existing applications
        try:
            old_instance = LoanApplication.objects.get(pk=instance.pk)
            
            # Check if status changed to SUBMITTED
            if old_instance.status != 'SUBMITTED' and instance.status == 'SUBMITTED':
                if not instance.submission_date:
                    instance.submission_date = timezone.now().date()
                    logger.info(f"Application {instance.application_number} submitted")
            
            # Check if status changed to APPROVED
            if old_instance.status != 'APPROVED' and instance.status == 'APPROVED':
                if not instance.approval_date:
                    instance.approval_date = timezone.now()
                    logger.info(f"Application {instance.application_number} approved")
            
        except LoanApplication.DoesNotExist:
            pass


@receiver(post_save, sender=LoanApplication)
def log_application_creation(sender, instance, created, **kwargs):
    """
    Log when a new application is created.
    """
    if created:
        logger.info(
            f"New loan application created: {instance.application_number} | "
            f"Member: {instance.member.get_full_name()} | "
            f"Product: {instance.loan_product.name} | "
            f"Amount: {instance.amount_requested}"
        )


# =============================================================================
# LOAN SIGNALS
# =============================================================================

@receiver(pre_save, sender=Loan)
def generate_loan_number(sender, instance, **kwargs):
    """
    Generate loan number if not set.
    Delegates to utils.generate_loan_number() for generation logic.
    """
    if not instance.loan_number:
        from .utils import generate_loan_number
        
        # Get product code
        product_code = None
        if instance.loan_product:
            product_code = instance.loan_product.code
        
        # Get member ID
        member_id = None
        if instance.member:
            member_id = instance.member.id
        
        instance.loan_number = generate_loan_number(product_code, member_id)
        
        logger.info(f"Generated loan number: {instance.loan_number}")


@receiver(pre_save, sender=Loan)
def initialize_loan_balances(sender, instance, **kwargs):
    """
    Initialize outstanding amounts for new loans.
    """
    if not instance.pk:  # New loan
        # Set outstanding principal to principal amount
        instance.outstanding_principal = instance.principal_amount
        
        # Set outstanding interest to total interest
        instance.outstanding_interest = instance.total_interest
        
        # Set outstanding fees to total fees
        instance.outstanding_fees = instance.total_fees
        
        # Initialize penalties to zero
        instance.outstanding_penalties = Decimal('0.00')
        
        logger.debug(f"Initialized balances for loan {instance.loan_number}")


@receiver(pre_save, sender=Loan)
def calculate_loan_outstanding_total(sender, instance, **kwargs):
    """
    Calculate total outstanding amount.
    """
    instance.outstanding_total = (
        instance.outstanding_principal +
        instance.outstanding_interest +
        instance.outstanding_penalties +
        instance.outstanding_fees
    )


@receiver(pre_save, sender=Loan)
def update_loan_status_based_on_balance(sender, instance, **kwargs):
    """
    Update loan status based on outstanding balance.
    """
    # Only update if loan was ACTIVE
    if instance.pk and instance.status == 'ACTIVE':
        if instance.outstanding_total <= Decimal('0.00'):
            instance.status = 'PAID'
            if not instance.actual_end_date:
                instance.actual_end_date = timezone.now().date()
            
            logger.info(f"Loan {instance.loan_number} marked as PAID")


@receiver(pre_save, sender=Loan)
def set_loan_financial_period(sender, instance, **kwargs):
    """
    Set financial period if not set.
    """
    if not instance.financial_period:
        from core.utils import get_active_fiscal_period
        
        try:
            instance.financial_period = get_active_fiscal_period()
            logger.debug(f"Set financial period for loan {instance.loan_number}")
        except Exception as e:
            logger.warning(f"Could not set financial period for loan: {e}")


@receiver(post_save, sender=Loan)
def generate_loan_schedule_on_creation(sender, instance, created, **kwargs):
    """
    Generate loan repayment schedule when loan is created.
    """
    if created:
        from .utils import generate_loan_schedule
        
        try:
            # Generate schedule
            schedule_items = generate_loan_schedule(
                principal=instance.principal_amount,
                rate=instance.interest_rate,
                term_months=instance.term_months,
                start_date=instance.disbursement_date,
                payment_frequency=instance.payment_frequency,
                interest_type=instance.loan_product.interest_type,
                grace_period_days=instance.loan_product.grace_period
            )
            
            # Create schedule records
            schedule_records = []
            for item in schedule_items:
                schedule_records.append(
                    LoanSchedule(
                        loan=instance,
                        installment_number=item['installment_number'],
                        due_date=item['due_date'],
                        principal_amount=item['principal'],
                        interest_amount=item['interest'],
                        total_amount=item['total'],
                        balance=item['balance']
                    )
                )
            
            # Bulk create
            LoanSchedule.objects.bulk_create(schedule_records)
            
            # Update loan's next payment date
            if schedule_records:
                instance.next_payment_date = schedule_records[0].due_date
                instance.next_payment_amount = schedule_records[0].total_amount
                instance.save(update_fields=['next_payment_date', 'next_payment_amount'])
            
            logger.info(
                f"Generated {len(schedule_records)} installments for loan {instance.loan_number}"
            )
            
        except Exception as e:
            logger.error(f"Error generating loan schedule: {e}", exc_info=True)


@receiver(post_save, sender=Loan)
def link_application_to_loan(sender, instance, created, **kwargs):
    """
    Mark application as disbursed when loan is created.
    """
    if created and instance.application:
        from loans.models import LoanApplication
        
        LoanApplication.objects.filter(pk=instance.application.pk).update(
            status='DISBURSED'
        )
        
        logger.info(
            f"Marked application {instance.application.application_number} as DISBURSED"
        )


@receiver(post_save, sender=Loan)
def log_loan_creation(sender, instance, created, **kwargs):
    """
    Log when a new loan is created.
    """
    if created:
        logger.info(
            f"New loan created: {instance.loan_number} | "
            f"Member: {instance.member.get_full_name()} | "
            f"Principal: {instance.principal_amount} | "
            f"Term: {instance.term_months} months | "
            f"Interest Rate: {instance.interest_rate}%"
        )


# =============================================================================
# LOAN PAYMENT SIGNALS
# =============================================================================

@receiver(pre_save, sender=LoanPayment)
def generate_payment_number(sender, instance, **kwargs):
    """
    Generate payment number if not set.
    Delegates to utils.generate_payment_number() for generation logic.
    """
    if not instance.payment_number:
        from .utils import generate_payment_number
        
        instance.payment_number = generate_payment_number()
        
        logger.info(f"Generated payment number: {instance.payment_number}")


@receiver(pre_save, sender=LoanPayment)
def allocate_payment_to_loan_components(sender, instance, **kwargs):
    """
    Automatically allocate payment to fees, penalties, interest, and principal.
    Only runs if component amounts are not already set.
    """
    # Only auto-allocate if amounts are not manually set
    total_allocated = (
        instance.fee_amount +
        instance.penalty_amount +
        instance.interest_amount +
        instance.principal_amount
    )
    
    # If already allocated, skip
    if total_allocated > Decimal('0.00'):
        return
    
    # Get loan outstanding amounts
    loan = instance.loan
    
    from .utils import allocate_payment
    
    allocation = allocate_payment(
        payment_amount=instance.amount,
        outstanding_fees=loan.outstanding_fees,
        outstanding_penalties=loan.outstanding_penalties,
        outstanding_interest=loan.outstanding_interest,
        outstanding_principal=loan.outstanding_principal
    )
    
    # Set allocated amounts
    instance.fee_amount = allocation['fee_amount']
    instance.penalty_amount = allocation['penalty_amount']
    instance.interest_amount = allocation['interest_amount']
    instance.principal_amount = allocation['principal_amount']
    
    logger.debug(
        f"Allocated payment {instance.payment_number}: "
        f"Fees={instance.fee_amount}, Penalties={instance.penalty_amount}, "
        f"Interest={instance.interest_amount}, Principal={instance.principal_amount}"
    )


@receiver(pre_save, sender=LoanPayment)
def set_payment_financial_period(sender, instance, **kwargs):
    """
    Set financial period if not set.
    """
    if not instance.financial_period:
        from core.utils import get_active_fiscal_period
        
        try:
            instance.financial_period = get_active_fiscal_period()
            logger.debug(f"Set financial period for payment {instance.payment_number}")
        except Exception as e:
            logger.warning(f"Could not set financial period for payment: {e}")


@receiver(post_save, sender=LoanPayment)
def update_loan_balances_after_payment(sender, instance, created, **kwargs):
    """
    Update loan balances after payment is saved.
    Only processes new, non-reversed payments.
    """
    if created and not instance.is_reversed:
        loan = instance.loan
        
        with db_transaction.atomic():
            # Lock the loan row for update
            loan = Loan.objects.select_for_update().get(pk=loan.pk)
            
            # Update paid amounts
            loan.total_paid += instance.amount
            loan.total_paid_principal += instance.principal_amount
            loan.total_paid_interest += instance.interest_amount
            loan.total_paid_penalties += instance.penalty_amount
            loan.total_paid_fees += instance.fee_amount
            
            # Update outstanding amounts
            loan.outstanding_principal -= instance.principal_amount
            loan.outstanding_interest -= instance.interest_amount
            loan.outstanding_penalties -= instance.penalty_amount
            loan.outstanding_fees -= instance.fee_amount
            
            # Ensure no negative balances
            loan.outstanding_principal = max(loan.outstanding_principal, Decimal('0.00'))
            loan.outstanding_interest = max(loan.outstanding_interest, Decimal('0.00'))
            loan.outstanding_penalties = max(loan.outstanding_penalties, Decimal('0.00'))
            loan.outstanding_fees = max(loan.outstanding_fees, Decimal('0.00'))
            
            # Update payment tracking
            loan.last_payment_date = instance.payment_date
            
            # Save loan (will trigger loan signals to update outstanding_total and status)
            loan.save()
            
            logger.info(
                f"Updated loan {loan.loan_number} after payment {instance.payment_number} | "
                f"Outstanding: {loan.outstanding_total}"
            )


@receiver(post_save, sender=LoanPayment)
def update_loan_schedule_after_payment(sender, instance, created, **kwargs):
    """
    Update loan schedule installments after payment.
    """
    if created and not instance.is_reversed:
        loan = instance.loan
        
        # Get pending and partially paid installments
        pending_installments = loan.schedule.filter(
            status__in=['PENDING', 'PARTIALLY_PAID', 'OVERDUE']
        ).order_by('installment_number')
        
        # Allocate payment to installments
        remaining_payment = instance.amount
        
        for installment in pending_installments:
            if remaining_payment <= Decimal('0.00'):
                break
            
            # Calculate how much to pay on this installment
            installment_balance = installment.balance
            payment_for_installment = min(remaining_payment, installment_balance)
            
            # Update installment
            installment.paid_amount += payment_for_installment
            
            # Allocate between principal and interest proportionally
            if installment.total_amount > 0:
                principal_ratio = installment.principal_amount / installment.total_amount
                interest_ratio = installment.interest_amount / installment.total_amount
                
                installment.paid_principal += payment_for_installment * principal_ratio
                installment.paid_interest += payment_for_installment * interest_ratio
            
            installment.save()  # Will trigger schedule signals to update balance and status
            
            remaining_payment -= payment_for_installment
        
        # Update loan's next payment date
        next_unpaid = loan.schedule.filter(
            status__in=['PENDING', 'PARTIALLY_PAID', 'OVERDUE']
        ).order_by('installment_number').first()
        
        if next_unpaid:
            Loan.objects.filter(pk=loan.pk).update(
                next_payment_date=next_unpaid.due_date,
                next_payment_amount=next_unpaid.balance
            )
        else:
            # All installments paid
            Loan.objects.filter(pk=loan.pk).update(
                next_payment_date=None,
                next_payment_amount=None
            )
        
        logger.debug(f"Updated loan schedule after payment {instance.payment_number}")


@receiver(post_save, sender=LoanPayment)
def log_payment_creation(sender, instance, created, **kwargs):
    """
    Log when a new payment is created.
    """
    if created:
        logger.info(
            f"New loan payment: {instance.payment_number} | "
            f"Loan: {instance.loan.loan_number} | "
            f"Amount: {instance.amount} | "
            f"Principal: {instance.principal_amount} | "
            f"Interest: {instance.interest_amount}"
        )


# =============================================================================
# LOAN SCHEDULE SIGNALS
# =============================================================================

@receiver(pre_save, sender=LoanSchedule)
def calculate_schedule_balance(sender, instance, **kwargs):
    """
    Calculate installment balance and update status.
    """
    # Calculate total
    instance.total_amount = instance.principal_amount + instance.interest_amount
    
    # Calculate balance
    instance.balance = instance.total_amount - instance.paid_amount
    
    # Ensure no negative balance
    instance.balance = max(instance.balance, Decimal('0.00'))
    
    # Update status based on balance
    if instance.balance <= Decimal('0.00'):
        instance.status = 'PAID'
        if not instance.paid_date:
            instance.paid_date = timezone.now().date()
    elif instance.paid_amount > Decimal('0.00'):
        instance.status = 'PARTIALLY_PAID'
    elif instance.due_date < timezone.now().date():
        instance.status = 'OVERDUE'
        instance.days_late = (timezone.now().date() - instance.due_date).days
    else:
        instance.status = 'PENDING'


@receiver(pre_save, sender=LoanSchedule)
def set_schedule_financial_period(sender, instance, **kwargs):
    """
    Set financial period based on due date.
    """
    if not instance.financial_period and instance.due_date:
        from core.models import FiscalPeriod
        
        try:
            # Find fiscal period that contains the due date
            period = FiscalPeriod.objects.filter(
                start_date__lte=instance.due_date,
                end_date__gte=instance.due_date
            ).first()
            
            if period:
                instance.financial_period = period
        except Exception as e:
            logger.warning(f"Could not set financial period for schedule: {e}")


# =============================================================================
# LOAN GUARANTOR SIGNALS
# =============================================================================

@receiver(post_save, sender=LoanGuarantor)
def log_guarantor_creation(sender, instance, created, **kwargs):
    """
    Log when a guarantor is added.
    """
    if created:
        logger.info(
            f"Guarantor added: {instance.guarantor.get_full_name()} | "
            f"Application: {instance.loan_application.application_number} | "
            f"Amount: {instance.guarantee_amount}"
        )


@receiver(pre_save, sender=LoanGuarantor)
def set_guarantor_response_date(sender, instance, **kwargs):
    """
    Set response date when status changes from PENDING.
    """
    if instance.pk:
        try:
            old_instance = LoanGuarantor.objects.get(pk=instance.pk)
            
            # Check if status changed from PENDING
            if old_instance.status == 'PENDING' and instance.status != 'PENDING':
                if not instance.response_date:
                    instance.response_date = timezone.now()
                    logger.info(
                        f"Guarantor {instance.guarantor.get_full_name()} "
                        f"{instance.get_status_display().lower()} for "
                        f"application {instance.loan_application.application_number}"
                    )
        except LoanGuarantor.DoesNotExist:
            pass


# =============================================================================
# LOAN COLLATERAL SIGNALS
# =============================================================================

@receiver(post_save, sender=LoanCollateral)
def log_collateral_creation(sender, instance, created, **kwargs):
    """
    Log when collateral is added.
    """
    if created:
        logger.info(
            f"Collateral added: {instance.get_collateral_type_display()} | "
            f"Application: {instance.loan_application.application_number} | "
            f"Value: {instance.estimated_value}"
        )


@receiver(pre_save, sender=LoanCollateral)
def set_collateral_verification_date(sender, instance, **kwargs):
    """
    Set verification date when collateral is verified.
    """
    if instance.pk:
        try:
            old_instance = LoanCollateral.objects.get(pk=instance.pk)
            
            # Check if verification status changed
            if not old_instance.is_verified and instance.is_verified:
                if not instance.verification_date:
                    instance.verification_date = timezone.now()
                    logger.info(
                        f"Collateral verified for application "
                        f"{instance.loan_application.application_number}"
                    )
        except LoanCollateral.DoesNotExist:
            pass


# =============================================================================
# LOAN DOCUMENT SIGNALS
# =============================================================================

@receiver(post_save, sender=LoanDocument)
def log_document_upload(sender, instance, created, **kwargs):
    """
    Log when a document is uploaded.
    """
    if created:
        entity = instance.loan or instance.application
        logger.info(
            f"Document uploaded: {instance.get_document_type_display()} | "
            f"Entity: {entity} | "
            f"Title: {instance.title}"
        )


@receiver(pre_save, sender=LoanDocument)
def set_document_verification_date(sender, instance, **kwargs):
    """
    Set verification date when document is verified.
    """
    if instance.pk:
        try:
            old_instance = LoanDocument.objects.get(pk=instance.pk)
            
            # Check if verification status changed
            if not old_instance.is_verified and instance.is_verified:
                if not instance.verification_date:
                    instance.verification_date = timezone.now()
                    logger.info(f"Document '{instance.title}' verified")
        except LoanDocument.DoesNotExist:
            pass


# =============================================================================
# CLEANUP SIGNALS
# =============================================================================

@receiver(post_delete, sender=Loan)
def log_loan_deletion(sender, instance, **kwargs):
    """
    Log when a loan is deleted (should be rare).
    """
    logger.warning(
        f"Loan DELETED: {instance.loan_number} | "
        f"Member: {instance.member.get_full_name()} | "
        f"Outstanding: {instance.outstanding_total}"
    )


@receiver(post_delete, sender=LoanPayment)
def log_payment_deletion(sender, instance, **kwargs):
    """
    Log when a payment is deleted (should be rare).
    """
    logger.warning(
        f"Payment DELETED: {instance.payment_number} | "
        f"Loan: {instance.loan.loan_number} | "
        f"Amount: {instance.amount}"
    )


# =============================================================================
# SIGNAL DEBUGGING HELPERS
# =============================================================================

def disable_loan_signals():
    """
    Temporarily disable loan signals (useful for bulk operations).
    
    Usage:
        from loans.signals import disable_loan_signals, enable_loan_signals
        
        disable_loan_signals()
        # ... perform bulk operations ...
        enable_loan_signals()
    """
    from django.db.models.signals import pre_save, post_save, post_delete
    
    signals_to_disconnect = [
        # Application signals
        (pre_save, generate_application_number, LoanApplication),
        (pre_save, calculate_application_fees, LoanApplication),
        (pre_save, set_application_financial_period, LoanApplication),
        (pre_save, set_submission_date, LoanApplication),
        (post_save, log_application_creation, LoanApplication),
        
        # Loan signals
        (pre_save, generate_loan_number, Loan),
        (pre_save, initialize_loan_balances, Loan),
        (pre_save, calculate_loan_outstanding_total, Loan),
        (pre_save, update_loan_status_based_on_balance, Loan),
        (pre_save, set_loan_financial_period, Loan),
        (post_save, generate_loan_schedule_on_creation, Loan),
        (post_save, link_application_to_loan, Loan),
        (post_save, log_loan_creation, Loan),
        
        # Payment signals
        (pre_save, generate_payment_number, LoanPayment),
        (pre_save, allocate_payment_to_loan_components, LoanPayment),
        (pre_save, set_payment_financial_period, LoanPayment),
        (post_save, update_loan_balances_after_payment, LoanPayment),
        (post_save, update_loan_schedule_after_payment, LoanPayment),
        (post_save, log_payment_creation, LoanPayment),
        
        # Schedule signals
        (pre_save, calculate_schedule_balance, LoanSchedule),
        (pre_save, set_schedule_financial_period, LoanSchedule),
        
        # Guarantor signals
        (pre_save, set_guarantor_response_date, LoanGuarantor),
        (post_save, log_guarantor_creation, LoanGuarantor),
        
        # Collateral signals
        (pre_save, set_collateral_verification_date, LoanCollateral),
        (post_save, log_collateral_creation, LoanCollateral),
        
        # Document signals
        (pre_save, set_document_verification_date, LoanDocument),
        (post_save, log_document_upload, LoanDocument),
    ]
    
    for signal, handler, model in signals_to_disconnect:
        signal.disconnect(handler, sender=model)
    
    logger.warning("Loan signals DISABLED")


def enable_loan_signals():
    """
    Re-enable loan signals after being disabled.
    """
    from django.db.models.signals import pre_save, post_save, post_delete
    
    signals_to_reconnect = [
        # Application signals
        (pre_save, generate_application_number, LoanApplication),
        (pre_save, calculate_application_fees, LoanApplication),
        (pre_save, set_application_financial_period, LoanApplication),
        (pre_save, set_submission_date, LoanApplication),
        (post_save, log_application_creation, LoanApplication),
        
        # Loan signals
        (pre_save, generate_loan_number, Loan),
        (pre_save, initialize_loan_balances, Loan),
        (pre_save, calculate_loan_outstanding_total, Loan),
        (pre_save, update_loan_status_based_on_balance, Loan),
        (pre_save, set_loan_financial_period, Loan),
        (post_save, generate_loan_schedule_on_creation, Loan),
        (post_save, link_application_to_loan, Loan),
        (post_save, log_loan_creation, Loan),
        
        # Payment signals
        (pre_save, generate_payment_number, LoanPayment),
        (pre_save, allocate_payment_to_loan_components, LoanPayment),
        (pre_save, set_payment_financial_period, LoanPayment),
        (post_save, update_loan_balances_after_payment, LoanPayment),
        (post_save, update_loan_schedule_after_payment, LoanPayment),
        (post_save, log_payment_creation, LoanPayment),
        
        # Schedule signals
        (pre_save, calculate_schedule_balance, LoanSchedule),
        (pre_save, set_schedule_financial_period, LoanSchedule),
        
        # Guarantor signals
        (pre_save, set_guarantor_response_date, LoanGuarantor),
        (post_save, log_guarantor_creation, LoanGuarantor),
        
        # Collateral signals
        (pre_save, set_collateral_verification_date, LoanCollateral),
        (post_save, log_collateral_creation, LoanCollateral),
        
        # Document signals
        (pre_save, set_document_verification_date, LoanDocument),
        (post_save, log_document_upload, LoanDocument),
    ]
    
    for signal, handler, model in signals_to_reconnect:
        signal.connect(handler, sender=model)
    
    logger.warning("Loan signals ENABLED")


# =============================================================================
# APP READY - ENSURE SIGNALS ARE LOADED
# =============================================================================

def ready():
    """
    Called when the app is ready. Ensures signals are registered.
    This should be called from apps.py LoansConfig.ready()
    """
    logger.info("Loan signals registered successfully")