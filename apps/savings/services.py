# savings/services.py

"""
Savings Business Logic Services

Contains complex business logic that shouldn't be in views or models:
- Transaction processing workflows
- Interest calculation and posting
- Standing order execution
- Account lifecycle management
- Bulk operations

WHY SERVICES.PY?
1. Separation of Concerns: Complex business logic separate from views
2. Reusability: Can be called from views, management commands, celery tasks
3. Testing: Easier to test business logic in isolation
4. Transaction Management: Handle complex multi-step operations
5. Clear API: Well-defined functions for each business operation
"""

from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from django.db.models import Q
import logging

from .models import (
    SavingsAccount,
    SavingsTransaction,
    SavingsProduct,
    InterestCalculation,
    StandingOrder,
    SavingsGoal,
)
from .utils import (
    validate_withdrawal,
    validate_deposit,
    validate_transfer,
    calculate_simple_interest,
    calculate_compound_interest,
    calculate_tiered_interest,
    calculate_withholding_tax,
    calculate_next_frequency_date,
    can_close_account,
)
from core.models import PaymentMethod

logger = logging.getLogger(__name__)


# =============================================================================
# TRANSACTION SERVICES
# =============================================================================

class TransactionService:
    """Handle all transaction-related operations"""
    
    @staticmethod
    @transaction.atomic
    def process_deposit(account, amount, payment_method, reference_number=None, 
                       description=None, processed_by=None):
        """
        Process a deposit transaction with full validation and updates.
        
        Args:
            account: SavingsAccount instance
            amount: Deposit amount
            payment_method: PaymentMethod instance
            reference_number: Optional reference
            description: Optional description
            processed_by: User who processed the transaction
        
        Returns:
            tuple: (success, transaction_or_error_message)
        """
        # Validate deposit
        is_valid, message = validate_deposit(account, amount)
        if not is_valid:
            return False, message
        
        try:
            # Calculate fees if applicable
            fees = account.savings_product.calculate_deposit_fee(amount)
            
            # Create transaction
            txn = SavingsTransaction.objects.create(
                account=account,
                transaction_type='DEPOSIT',
                amount=amount,
                fees=fees,
                payment_method=payment_method,
                reference_number=reference_number,
                description=description or 'Deposit',
            )
            
            # Update account - signals handle the balance update
            # but we can add additional logic here
            
            # Approve pending account if deposit meets minimum
            if account.status == 'PENDING_APPROVAL':
                if account.current_balance >= account.savings_product.minimum_opening_balance:
                    account.approve_account()
            
            logger.info(f"Processed deposit: {txn.transaction_id} - {amount}")
            return True, txn
            
        except Exception as e:
            logger.error(f"Error processing deposit: {e}")
            return False, str(e)
    
    @staticmethod
    @transaction.atomic
    def process_withdrawal(account, amount, payment_method, reference_number=None,
                          description=None, processed_by=None):
        """
        Process a withdrawal transaction with full validation.
        
        Returns:
            tuple: (success, transaction_or_error_message)
        """
        # Validate withdrawal
        is_valid, message = validate_withdrawal(account, amount)
        if not is_valid:
            return False, message
        
        try:
            # Calculate fees
            fees = account.savings_product.calculate_withdrawal_fee(amount)
            
            # Calculate early withdrawal penalty if applicable
            penalty = Decimal('0.00')
            if account.is_fixed_deposit and not account.is_matured:
                from .utils import calculate_early_withdrawal_penalty
                penalty = calculate_early_withdrawal_penalty(
                    amount,
                    account.savings_product.early_withdrawal_penalty_rate
                )
                fees += penalty
            
            # Create transaction
            txn = SavingsTransaction.objects.create(
                account=account,
                transaction_type='WITHDRAWAL',
                amount=amount,
                fees=fees,
                payment_method=payment_method,
                reference_number=reference_number,
                description=description or 'Withdrawal',
            )
            
            logger.info(f"Processed withdrawal: {txn.transaction_id} - {amount}")
            return True, txn
            
        except Exception as e:
            logger.error(f"Error processing withdrawal: {e}")
            return False, str(e)
    
    @staticmethod
    @transaction.atomic
    def process_transfer(source_account, destination_account, amount, 
                        description=None, processed_by=None):
        """
        Process transfer between accounts with full validation.
        
        Returns:
            tuple: (success, transaction_tuple_or_error_message)
        """
        # Validate transfer
        is_valid, message = validate_transfer(source_account, destination_account, amount)
        if not is_valid:
            return False, message
        
        try:
            # Create transfer out transaction
            txn_out = SavingsTransaction.objects.create(
                account=source_account,
                transaction_type='TRANSFER_OUT',
                amount=amount,
                linked_account=destination_account,
                description=description or f'Transfer to {destination_account.account_number}',
            )
            
            # Create transfer in transaction
            txn_in = SavingsTransaction.objects.create(
                account=destination_account,
                transaction_type='TRANSFER_IN',
                amount=amount,
                linked_account=source_account,
                linked_transaction=txn_out,
                description=description or f'Transfer from {source_account.account_number}',
            )
            
            # Link transactions
            txn_out.linked_transaction = txn_in
            txn_out.save(update_fields=['linked_transaction'])
            
            logger.info(f"Processed transfer: {amount} from {source_account.account_number} to {destination_account.account_number}")
            return True, (txn_out, txn_in)
            
        except Exception as e:
            logger.error(f"Error processing transfer: {e}")
            return False, str(e)
    
    @staticmethod
    @transaction.atomic
    def reverse_transaction(transaction, reason, reversed_by=None):
        """
        Reverse a transaction.
        
        Returns:
            tuple: (success, reversal_transaction_or_error_message)
        """
        if transaction.is_reversed:
            return False, "Transaction is already reversed"
        
        try:
            # Create reversal transaction
            reversal = SavingsTransaction.objects.create(
                account=transaction.account,
                transaction_type='REVERSAL',
                amount=transaction.amount,
                description=f"Reversal of {transaction.transaction_id}: {reason}",
                original_transaction=transaction,
            )
            
            # Mark original as reversed
            transaction.is_reversed = True
            transaction.reversal_reason = reason
            transaction.reversal_date = timezone.now()
            if reversed_by:
                transaction.reversed_by_id = str(reversed_by.id)
            transaction.save()
            
            # If it was a transfer, reverse the linked transaction too
            if transaction.linked_transaction:
                transaction.linked_transaction.is_reversed = True
                transaction.linked_transaction.reversal_reason = reason
                transaction.linked_transaction.reversal_date = timezone.now()
                if reversed_by:
                    transaction.linked_transaction.reversed_by_id = str(reversed_by.id)
                transaction.linked_transaction.save()
            
            logger.info(f"Reversed transaction: {transaction.transaction_id}")
            return True, reversal
            
        except Exception as e:
            logger.error(f"Error reversing transaction: {e}")
            return False, str(e)


# =============================================================================
# INTEREST SERVICES
# =============================================================================

class InterestService:
    """Handle interest calculations and posting"""
    
    @staticmethod
    def calculate_account_interest(account, calculation_date=None, period_start=None, period_end=None):
        """
        Calculate interest for a single account.
        
        Returns:
            tuple: (success, interest_calculation_or_error_message)
        """
        if calculation_date is None:
            calculation_date = timezone.now().date()
        
        # Determine period
        if not period_start:
            # Use last calculation date or account opening
            last_calc = InterestCalculation.objects.filter(
                account=account
            ).order_by('-period_end_date').first()
            
            period_start = last_calc.period_end_date + timedelta(days=1) if last_calc else account.opening_date
        
        if not period_end:
            period_end = calculation_date
        
        # Ensure period is valid
        if period_start >= period_end:
            return False, "Invalid period: start date must be before end date"
        
        try:
            product = account.savings_product
            method = product.interest_calculation_method
            rate = product.interest_rate
            
            # Get applicable rate for tiered products
            if method == 'TIERED':
                tiers = product.interest_tiers.filter(is_active=True).order_by('min_balance')
                rate, tier = calculate_tiered_interest(account.current_balance, tiers)
            
            # Calculate based on method
            days = (period_end - period_start).days
            
            if method == 'SIMPLE':
                gross_interest = calculate_simple_interest(
                    account.current_balance,
                    rate,
                    days
                )
            elif method == 'COMPOUND':
                gross_interest = calculate_compound_interest(
                    account.current_balance,
                    rate,
                    days,
                    product.interest_calculation_frequency
                )
            elif method in ['AVERAGE_BALANCE', 'MINIMUM_BALANCE', 'DAILY_BALANCE']:
                # More complex - would need transaction history
                # Simplified here
                gross_interest = calculate_simple_interest(
                    account.current_balance,
                    rate,
                    days
                )
            else:
                gross_interest = calculate_simple_interest(
                    account.current_balance,
                    rate,
                    days
                )
            
            # Calculate tax
            from core.models import SaccoConfiguration
            config = SaccoConfiguration.get_instance()
            tax_rate = config.withholding_tax_rate if hasattr(config, 'withholding_tax_rate') else Decimal('15.00')
            
            withholding_tax = calculate_withholding_tax(gross_interest, tax_rate)
            net_interest = gross_interest - withholding_tax
            
            # Create calculation record
            calc = InterestCalculation.objects.create(
                account=account,
                calculation_date=calculation_date,
                period_start_date=period_start,
                period_end_date=period_end,
                calculation_method=method,
                opening_balance=account.current_balance,  # Simplified
                closing_balance=account.current_balance,
                interest_rate=rate,
                days_calculated=days,
                gross_interest=gross_interest,
                tax_rate=tax_rate,
                withholding_tax=withholding_tax,
                net_interest=net_interest,
            )
            
            # Update account accrued interest
            account.accrued_interest += net_interest
            account.last_interest_calculated_date = calculation_date
            account.save(update_fields=['accrued_interest', 'last_interest_calculated_date'])
            
            logger.info(f"Calculated interest for account {account.account_number}: {net_interest}")
            return True, calc
            
        except Exception as e:
            logger.error(f"Error calculating interest for account {account.account_number}: {e}")
            return False, str(e)
    
    @staticmethod
    @transaction.atomic
    def post_interest_calculation(calculation, posting_date=None):
        """
        Post a calculated interest to account.
        
        Returns:
            tuple: (success, transaction_or_error_message)
        """
        if calculation.is_posted:
            return False, "Interest already posted"
        
        if posting_date is None:
            posting_date = timezone.now().date()
        
        try:
            # The signal will handle creating the transaction
            calculation.is_posted = True
            calculation.posted_date = posting_date
            calculation.save()
            
            # Get the created transaction
            if calculation.transaction:
                logger.info(f"Posted interest calculation {calculation.id}")
                return True, calculation.transaction
            else:
                return False, "Transaction creation failed"
                
        except Exception as e:
            logger.error(f"Error posting interest calculation {calculation.id}: {e}")
            return False, str(e)
    
    @staticmethod
    def bulk_calculate_interest(product=None, calculation_date=None):
        """
        Calculate interest for multiple accounts.
        
        Returns:
            dict: Results summary
        """
        from .utils import get_accounts_for_interest_calculation
        
        accounts = get_accounts_for_interest_calculation(product=product)
        
        results = {
            'total': accounts.count(),
            'successful': 0,
            'failed': 0,
            'calculations': [],
            'errors': [],
        }
        
        for account in accounts:
            success, result = InterestService.calculate_account_interest(
                account,
                calculation_date=calculation_date
            )
            
            if success:
                results['successful'] += 1
                results['calculations'].append(result)
            else:
                results['failed'] += 1
                results['errors'].append({
                    'account': account.account_number,
                    'error': result
                })
        
        return results


# =============================================================================
# STANDING ORDER SERVICES
# =============================================================================

class StandingOrderService:
    """Handle standing order execution"""
    
    @staticmethod
    @transaction.atomic
    def execute_standing_order(order):
        """
        Execute a single standing order.
        
        Returns:
            tuple: (success, transaction_or_error_message)
        """
        # Validate order is active and due
        if order.status != 'ACTIVE':
            return False, f"Standing order is {order.get_status_display()}"
        
        today = timezone.now().date()
        if order.next_run_date > today:
            return False, "Standing order is not due yet"
        
        # Check end date
        if order.end_date and today > order.end_date:
            order.status = 'COMPLETED'
            order.save()
            return False, "Standing order has ended"
        
        try:
            # Execute transfer
            success, result = TransactionService.process_transfer(
                source_account=order.source_account,
                destination_account=order.destination_account,
                amount=order.amount,
                description=f"Standing order: {order.description or 'Automated transfer'}"
            )
            
            if success:
                # Update order
                order.execution_count += 1
                order.last_execution_date = today
                order.last_execution_status = 'SUCCESS'
                order.next_run_date = calculate_next_frequency_date(today, order.frequency)
                order.save()
                
                logger.info(f"Executed standing order {order.id}")
                return True, result
            else:
                # Record failure
                order.last_execution_status = 'FAILED'
                order.last_failure_reason = result
                order.save()
                
                return False, result
                
        except Exception as e:
            logger.error(f"Error executing standing order {order.id}: {e}")
            order.last_execution_status = 'FAILED'
            order.last_failure_reason = str(e)
            order.save()
            return False, str(e)
    
    @staticmethod
    def execute_due_standing_orders(execution_date=None):
        """
        Execute all due standing orders.
        
        Returns:
            dict: Execution summary
        """
        if execution_date is None:
            execution_date = timezone.now().date()
        
        due_orders = StandingOrder.get_due_standing_orders(execution_date)
        
        results = {
            'total': due_orders.count(),
            'successful': 0,
            'failed': 0,
            'transactions': [],
            'errors': [],
        }
        
        for order in due_orders:
            success, result = StandingOrderService.execute_standing_order(order)
            
            if success:
                results['successful'] += 1
                results['transactions'].append(result)
            else:
                results['failed'] += 1
                results['errors'].append({
                    'order_id': order.id,
                    'error': result
                })
        
        return results


# =============================================================================
# ACCOUNT SERVICES
# =============================================================================

# =============================================================================
# ACCOUNT SERVICES
# =============================================================================

class AccountService:
    """Handle account lifecycle and management"""
    
    @staticmethod
    @transaction.atomic
    def open_account(member, savings_product, opening_balance, payment_method,
                    reference_number=None, description=None, is_fixed_deposit=False, 
                    term_days=None, auto_renew=False, processed_by=None):
        """
        Open a new savings account with initial deposit.
        
        Args:
            member: Member instance
            savings_product: SavingsProduct instance
            opening_balance (Decimal): Initial deposit amount
            payment_method: PaymentMethod instance
            reference_number (str, optional): Payment reference
            description (str, optional): Additional description
            is_fixed_deposit (bool): Whether this is a fixed deposit
            term_days (int, optional): Term length for fixed deposits
            auto_renew (bool): Auto-renew fixed deposit on maturity
            processed_by: User who processed this account opening
        
        Returns:
            tuple: (success: bool, account_or_error_message)
        
        Example:
            >>> success, account = AccountService.open_account(
            ...     member=member,
            ...     savings_product=product,
            ...     opening_balance=Decimal('50000.00'),
            ...     payment_method=cash_method
            ... )
        """
        # Import here to avoid circular imports
        from core.utils import format_money
        
        # Validate opening balance
        try:
            opening_balance = Decimal(str(opening_balance))
        except (ValueError, TypeError):
            return False, "Invalid opening balance amount"
        
        if opening_balance < savings_product.minimum_opening_balance:
            min_formatted = format_money(savings_product.minimum_opening_balance)
            return False, f"Opening balance must be at least {min_formatted}"
        
        # Check maximum balance limit
        if savings_product.maximum_balance:
            if opening_balance > savings_product.maximum_balance:
                max_formatted = format_money(savings_product.maximum_balance)
                return False, f"Opening balance exceeds maximum balance of {max_formatted}"
        
        # Validate member status
        if hasattr(member, 'status'):
            if member.status not in ['ACTIVE', 'PENDING']:
                return False, f"Cannot open account for member with status: {member.get_status_display()}"
        
        # Check product availability
        if not savings_product.is_active:
            return False, f"Product '{savings_product.name}' is not currently available"
        
        # Check product limits per member
        existing_count = SavingsAccount.objects.filter(
            member=member,
            savings_product=savings_product,
            status__in=['ACTIVE', 'DORMANT', 'PENDING_APPROVAL']
        ).count()
        
        if existing_count >= savings_product.maximum_accounts_per_member:
            return False, f"Member already has maximum allowed accounts ({savings_product.maximum_accounts_per_member}) for this product"
        
        # Validate fixed deposit requirements
        if is_fixed_deposit:
            if not savings_product.is_fixed_deposit:
                return False, "This product does not support fixed deposits"
            
            if not term_days:
                return False, "Term length is required for fixed deposits"
            
            if term_days < savings_product.minimum_term_days:
                return False, f"Minimum term is {savings_product.minimum_term_days} days"
            
            if savings_product.maximum_term_days and term_days > savings_product.maximum_term_days:
                return False, f"Maximum term is {savings_product.maximum_term_days} days"
        
        try:
            # Determine initial status
            initial_status = 'ACTIVE' if not savings_product.requires_approval else 'PENDING_APPROVAL'
            
            # Create account (account_number will be auto-generated by signal)
            account = SavingsAccount.objects.create(
                member=member,
                savings_product=savings_product,
                current_balance=Decimal('0.00'),  # Will be updated by transaction
                available_balance=Decimal('0.00'),
                opening_date=timezone.now().date(),
                status=initial_status,
                is_fixed_deposit=is_fixed_deposit,
                term_length_days=term_days,
                fixed_deposit_amount=opening_balance if is_fixed_deposit else None,
                auto_renew=auto_renew if is_fixed_deposit else False,
            )
            
            # Create opening deposit transaction
            # (transaction_id auto-generated, balance auto-updated by signals)
            deposit_description = description or f"Opening deposit for account {account.account_number}"
            
            txn = SavingsTransaction.objects.create(
                account=account,
                transaction_type='DEPOSIT',
                amount=opening_balance,
                payment_method=payment_method,
                reference_number=reference_number,
                description=deposit_description,
            )
            
            logger.info(
                f"Opened new account {account.account_number} | "
                f"Member: {member.get_full_name()} | "
                f"Product: {savings_product.name} | "
                f"Opening Balance: {format_money(opening_balance)} | "
                f"Status: {initial_status} | "
                f"FD: {is_fixed_deposit}"
            )
            
            return True, account
            
        except Exception as e:
            logger.error(f"Error opening account: {e}", exc_info=True)
            return False, f"Error opening account: {str(e)}"
    
    @staticmethod
    @transaction.atomic
    def close_account(account, reason, closed_by=None):
        """
        Close a savings account.
        
        Args:
            account: SavingsAccount instance
            reason (str): Reason for closure
            closed_by: User who closed the account
        
        Returns:
            tuple: (success: bool, message: str)
        
        Example:
            >>> success, msg = AccountService.close_account(
            ...     account=account,
            ...     reason="Member request",
            ...     closed_by=request.user
            ... )
        """
        # Validate closure
        can_close, message = can_close_account(account)
        if not can_close:
            return False, message
        
        # Additional validation
        if account.status == 'CLOSED':
            return False, "Account is already closed"
        
        try:
            # Update account status
            account.status = 'CLOSED'
            account.closure_date = timezone.now().date()
            account.save(update_fields=['status', 'closure_date', 'updated_at'])
            
            # Cancel any active standing orders
            active_orders = StandingOrder.objects.filter(
                source_account=account,
                status='ACTIVE'
            )
            
            if active_orders.exists():
                active_orders.update(
                    status='CANCELLED',
                    last_failure_reason=f"Source account {account.account_number} closed"
                )
                logger.info(f"Cancelled {active_orders.count()} standing orders for closed account {account.account_number}")
            
            # Log closure
            logger.info(
                f"Closed account {account.account_number} | "
                f"Member: {account.member.get_full_name()} | "
                f"Reason: {reason} | "
                f"Final Balance: {account.current_balance} | "
                f"Closed By: {closed_by if closed_by else 'System'}"
            )
            
            return True, f"Account {account.account_number} closed successfully"
            
        except Exception as e:
            logger.error(f"Error closing account {account.account_number}: {e}", exc_info=True)
            return False, f"Error closing account: {str(e)}"
    
    @staticmethod
    @transaction.atomic
    def freeze_account(account, reason, frozen_by=None):
        """
        Freeze a savings account (prevent transactions).
        
        Args:
            account: SavingsAccount instance
            reason (str): Reason for freezing
            frozen_by: User who froze the account
        
        Returns:
            tuple: (success: bool, message: str)
        """
        if account.status == 'FROZEN':
            return False, "Account is already frozen"
        
        if account.status == 'CLOSED':
            return False, "Cannot freeze a closed account"
        
        try:
            # Store previous status for potential unfreezing
            previous_status = account.status
            
            account.status = 'FROZEN'
            account.save(update_fields=['status', 'updated_at'])
            
            logger.info(
                f"Froze account {account.account_number} | "
                f"Previous Status: {previous_status} | "
                f"Reason: {reason} | "
                f"Frozen By: {frozen_by if frozen_by else 'System'}"
            )
            
            return True, f"Account {account.account_number} frozen successfully"
            
        except Exception as e:
            logger.error(f"Error freezing account {account.account_number}: {e}", exc_info=True)
            return False, f"Error freezing account: {str(e)}"
    
    @staticmethod
    @transaction.atomic
    def unfreeze_account(account, unfrozen_by=None):
        """
        Unfreeze a savings account.
        
        Args:
            account: SavingsAccount instance
            unfrozen_by: User who unfroze the account
        
        Returns:
            tuple: (success: bool, message: str)
        """
        if account.status != 'FROZEN':
            return False, "Account is not frozen"
        
        try:
            # Set to ACTIVE (default unfrozen state)
            account.status = 'ACTIVE'
            account.save(update_fields=['status', 'updated_at'])
            
            logger.info(
                f"Unfroze account {account.account_number} | "
                f"Unfrozen By: {unfrozen_by if unfrozen_by else 'System'}"
            )
            
            return True, f"Account {account.account_number} unfrozen successfully"
            
        except Exception as e:
            logger.error(f"Error unfreezing account {account.account_number}: {e}", exc_info=True)
            return False, f"Error unfreezing account: {str(e)}"
    
    @staticmethod
    @transaction.atomic
    def suspend_account(account, reason, suspended_by=None):
        """
        Suspend a savings account (more severe than freeze).
        
        Args:
            account: SavingsAccount instance
            reason (str): Reason for suspension
            suspended_by: User who suspended the account
        
        Returns:
            tuple: (success: bool, message: str)
        """
        if account.status == 'SUSPENDED':
            return False, "Account is already suspended"
        
        if account.status == 'CLOSED':
            return False, "Cannot suspend a closed account"
        
        try:
            account.status = 'SUSPENDED'
            account.save(update_fields=['status', 'updated_at'])
            
            # Cancel any active standing orders
            StandingOrder.objects.filter(
                source_account=account,
                status='ACTIVE'
            ).update(
                status='PAUSED',
                last_failure_reason=f"Account suspended: {reason}"
            )
            
            logger.warning(
                f"Suspended account {account.account_number} | "
                f"Reason: {reason} | "
                f"Suspended By: {suspended_by if suspended_by else 'System'}"
            )
            
            return True, f"Account {account.account_number} suspended successfully"
            
        except Exception as e:
            logger.error(f"Error suspending account {account.account_number}: {e}", exc_info=True)
            return False, f"Error suspending account: {str(e)}"
    
    @staticmethod
    @transaction.atomic
    def reactivate_account(account, reactivated_by=None):
        """
        Reactivate a suspended or dormant account.
        
        Args:
            account: SavingsAccount instance
            reactivated_by: User who reactivated the account
        
        Returns:
            tuple: (success: bool, message: str)
        """
        if account.status not in ['SUSPENDED', 'DORMANT', 'FROZEN']:
            return False, f"Cannot reactivate account with status: {account.get_status_display()}"
        
        if account.status == 'CLOSED':
            return False, "Cannot reactivate a closed account"
        
        try:
            previous_status = account.status
            
            account.status = 'ACTIVE'
            account.save(update_fields=['status', 'updated_at'])
            
            # Resume paused standing orders
            StandingOrder.objects.filter(
                source_account=account,
                status='PAUSED'
            ).update(status='ACTIVE')
            
            logger.info(
                f"Reactivated account {account.account_number} | "
                f"Previous Status: {previous_status} | "
                f"Reactivated By: {reactivated_by if reactivated_by else 'System'}"
            )
            
            return True, f"Account {account.account_number} reactivated successfully"
            
        except Exception as e:
            logger.error(f"Error reactivating account {account.account_number}: {e}", exc_info=True)
            return False, f"Error reactivating account: {str(e)}"
    
    @staticmethod
    @transaction.atomic
    def place_hold(account, amount, reason, hold_reference=None, placed_by=None):
        """
        Place a hold on account funds (reduce available balance).
        
        Args:
            account: SavingsAccount instance
            amount (Decimal): Amount to hold
            reason (str): Reason for hold
            hold_reference (str, optional): Reference for this hold
            placed_by: User who placed the hold
        
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            amount = Decimal(str(amount))
        except (ValueError, TypeError):
            return False, "Invalid hold amount"
        
        if amount <= 0:
            return False, "Hold amount must be greater than zero"
        
        if amount > account.available_balance:
            from core.utils import format_money
            return False, f"Insufficient available balance. Available: {format_money(account.available_balance)}"
        
        try:
            # Increase hold amount
            account.hold_amount += amount
            account.save(update_fields=['hold_amount', 'updated_at'])
            
            # Available balance will be auto-updated by signal
            
            logger.info(
                f"Placed hold on account {account.account_number} | "
                f"Amount: {amount} | "
                f"Reason: {reason} | "
                f"Reference: {hold_reference or 'N/A'} | "
                f"Total Holds: {account.hold_amount} | "
                f"Placed By: {placed_by if placed_by else 'System'}"
            )
            
            return True, f"Hold of {amount} placed successfully"
            
        except Exception as e:
            logger.error(f"Error placing hold on account {account.account_number}: {e}", exc_info=True)
            return False, f"Error placing hold: {str(e)}"
    
    @staticmethod
    @transaction.atomic
    def release_hold(account, amount, reason, released_by=None):
        """
        Release a hold on account funds (increase available balance).
        
        Args:
            account: SavingsAccount instance
            amount (Decimal): Amount to release
            reason (str): Reason for release
            released_by: User who released the hold
        
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            amount = Decimal(str(amount))
        except (ValueError, TypeError):
            return False, "Invalid release amount"
        
        if amount <= 0:
            return False, "Release amount must be greater than zero"
        
        if amount > account.hold_amount:
            from core.utils import format_money
            return False, f"Release amount exceeds total holds. Current holds: {format_money(account.hold_amount)}"
        
        try:
            # Decrease hold amount
            account.hold_amount -= amount
            account.save(update_fields=['hold_amount', 'updated_at'])
            
            # Available balance will be auto-updated by signal
            
            logger.info(
                f"Released hold on account {account.account_number} | "
                f"Amount: {amount} | "
                f"Reason: {reason} | "
                f"Remaining Holds: {account.hold_amount} | "
                f"Released By: {released_by if released_by else 'System'}"
            )
            
            return True, f"Hold of {amount} released successfully"
            
        except Exception as e:
            logger.error(f"Error releasing hold on account {account.account_number}: {e}", exc_info=True)
            return False, f"Error releasing hold: {str(e)}"
    
    @staticmethod
    def check_dormancy_eligibility(account):
        """
        Check if account should be marked as dormant.
        
        Args:
            account: SavingsAccount instance
        
        Returns:
            tuple: (is_eligible: bool, days_inactive: int, message: str)
        """
        from .utils import is_account_dormant
        
        if account.status != 'ACTIVE':
            return False, 0, f"Account status is {account.get_status_display()}"
        
        is_dormant, days_inactive = is_account_dormant(account)
        
        if is_dormant:
            message = f"Account has been inactive for {days_inactive} days (threshold: {account.savings_product.dormancy_period_days} days)"
            return True, days_inactive, message
        else:
            remaining_days = account.savings_product.dormancy_period_days - days_inactive
            message = f"Account is active. {remaining_days} days until dormancy eligibility"
            return False, days_inactive, message
    
    @staticmethod
    @transaction.atomic
    def mark_as_dormant(account, marked_by=None):
        """
        Mark account as dormant due to inactivity.
        
        Args:
            account: SavingsAccount instance
            marked_by: User who marked the account as dormant
        
        Returns:
            tuple: (success: bool, message: str)
        """
        if account.status == 'DORMANT':
            return False, "Account is already dormant"
        
        if account.status != 'ACTIVE':
            return False, f"Cannot mark account with status {account.get_status_display()} as dormant"
        
        # Check eligibility
        is_eligible, days_inactive, msg = AccountService.check_dormancy_eligibility(account)
        
        if not is_eligible:
            return False, msg
        
        try:
            account.status = 'DORMANT'
            account.save(update_fields=['status', 'updated_at'])
            
            logger.info(
                f"Marked account {account.account_number} as DORMANT | "
                f"Days Inactive: {days_inactive} | "
                f"Marked By: {marked_by if marked_by else 'System'}"
            )
            
            return True, f"Account {account.account_number} marked as dormant"
            
        except Exception as e:
            logger.error(f"Error marking account {account.account_number} as dormant: {e}", exc_info=True)
            return False, f"Error marking account as dormant: {str(e)}"
    
    @staticmethod
    def get_account_summary(account):
        """
        Get comprehensive summary of account status and metrics.
        
        Args:
            account: SavingsAccount instance
        
        Returns:
            dict: Account summary with all key metrics
        """
        from core.utils import format_money
        from .utils import get_account_age
        
        # Calculate age
        age_info = get_account_age(account)
        
        # Get transaction counts
        from django.db.models import Count, Sum
        
        txn_stats = account.transactions.filter(is_reversed=False).aggregate(
            total_count=Count('id'),
            total_deposits=Sum('amount', filter=Q(transaction_type='DEPOSIT')),
            total_withdrawals=Sum('amount', filter=Q(transaction_type='WITHDRAWAL')),
            deposit_count=Count('id', filter=Q(transaction_type='DEPOSIT')),
            withdrawal_count=Count('id', filter=Q(transaction_type='WITHDRAWAL')),
        )
        
        # Check dormancy eligibility
        is_dormant_eligible, days_inactive, dormancy_msg = AccountService.check_dormancy_eligibility(account)
        
        # Check if can close
        can_close, close_msg = can_close_account(account)
        
        summary = {
            'account_number': account.account_number,
            'status': account.get_status_display(),
            'effective_status': account.effective_status,
            'member': account.member.get_full_name() if account.member else 'N/A',
            'product': account.savings_product.name if account.savings_product else 'N/A',
            'balances': {
                'current': float(account.current_balance),
                'available': float(account.available_balance),
                'holds': float(account.hold_amount),
                'overdraft': float(account.overdraft_amount),
                'accrued_interest': float(account.accrued_interest),
                'total_interest_earned': float(account.total_interest_earned),
                'current_formatted': format_money(account.current_balance),
                'available_formatted': format_money(account.available_balance),
            },
            'dates': {
                'opening_date': account.opening_date.isoformat(),
                'activated_date': account.activated_date.isoformat() if account.activated_date else None,
                'closure_date': account.closure_date.isoformat() if account.closure_date else None,
                'maturity_date': account.maturity_date.isoformat() if account.maturity_date else None,
                'age_days': age_info['days'],
                'age_readable': age_info['readable'],
            },
            'transactions': {
                'total_count': txn_stats['total_count'] or 0,
                'deposit_count': txn_stats['deposit_count'] or 0,
                'withdrawal_count': txn_stats['withdrawal_count'] or 0,
                'total_deposits': float(txn_stats['total_deposits'] or 0),
                'total_withdrawals': float(txn_stats['total_withdrawals'] or 0),
                'last_transaction_date': account.last_transaction_date.isoformat() if account.last_transaction_date else None,
            },
            'fixed_deposit': {
                'is_fixed_deposit': account.is_fixed_deposit,
                'term_days': account.term_length_days,
                'maturity_date': account.maturity_date.isoformat() if account.maturity_date else None,
                'is_matured': account.is_matured if account.is_fixed_deposit else None,
                'days_to_maturity': account.days_to_maturity if account.is_fixed_deposit else None,
                'auto_renew': account.auto_renew if account.is_fixed_deposit else None,
            },
            'status_checks': {
                'is_dormant_eligible': is_dormant_eligible,
                'days_inactive': days_inactive,
                'can_close': can_close,
                'close_reason': close_msg if not can_close else None,
            },
            'limits': {
                'overdraft_limit': float(account.overdraft_limit),
                'overdraft_expiry': account.overdraft_expiry_date.isoformat() if account.overdraft_expiry_date else None,
            }
        }
        
        return summary

