# savings/utils.py

"""
Savings Utility Functions

Contains:
- Account number generation
- Transaction ID generation
- Balance calculations
- Interest calculations
- Fee calculations
- Validation utilities
- Helper functions for common operations
"""

from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta, date
from dateutil.relativedelta import relativedelta
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# ACCOUNT NUMBER GENERATION
# =============================================================================

def generate_account_number(product_code=None, member_number=None):
    """
    Generate unique savings account number.
    
    Format options based on parameters:
    1. With product_code and member_number: SAV-FD-M12345-0001
    2. With product_code only: SAV-FD-0001
    3. With member_number only: SAV-M12345-0001
    4. No parameters: SAV-0001
    
    Args:
        product_code (str, optional): Product code prefix (e.g., 'FD' for Fixed Deposit)
        member_number (str, optional): Member number to include in account number
    
    Returns:
        str: Unique account number
    
    Example:
        >>> generate_account_number('FD', 'M12345')
        'SAV-FD-M12345-0001'
        >>> generate_account_number('RG')
        'SAV-RG-0001'
        >>> generate_account_number()
        'SAV-0001'
    """
    from savings.models import SavingsAccount
    from core.models import SaccoConfiguration
    
    # Get configuration
    try:
        config = SaccoConfiguration.get_instance()
        prefix = config.savings_account_prefix or "SAV"
    except Exception as e:
        logger.warning(f"Could not get SaccoConfiguration: {e}. Using default prefix 'SAV'")
        prefix = "SAV"
    
    # Clean inputs
    prefix = prefix.strip().upper()
    if product_code:
        product_code = product_code.strip().upper()
    if member_number:
        member_number = member_number.strip().upper()
    
    # Build search pattern based on provided parameters
    if product_code and member_number:
        search_prefix = f"{prefix}-{product_code}-{member_number}-"
    elif product_code:
        search_prefix = f"{prefix}-{product_code}-"
    elif member_number:
        search_prefix = f"{prefix}-{member_number}-"
    else:
        search_prefix = f"{prefix}-"
    
    with transaction.atomic():
        # Query accounts with this prefix pattern
        if search_prefix:
            queryset = SavingsAccount.objects.filter(
                account_number__startswith=search_prefix
            ).select_for_update()
        else:
            queryset = SavingsAccount.objects.select_for_update()
        
        # Get the maximum account number
        result = queryset.aggregate(max_number=Max('account_number'))
        
        if result['max_number']:
            try:
                # Extract the numeric part (last segment after final dash)
                last_number = int(result['max_number'].split('-')[-1])
                new_number = last_number + 1
            except (ValueError, IndexError):
                # Fallback: iterate through all matching accounts to find max
                logger.warning(f"Could not parse max account number: {result['max_number']}. Using fallback method.")
                numbers = []
                for account_num in queryset.values_list('account_number', flat=True):
                    try:
                        # Extract last segment and convert to int
                        num = int(account_num.split('-')[-1])
                        numbers.append(num)
                    except (ValueError, IndexError):
                        continue
                
                new_number = max(numbers) + 1 if numbers else 1
        else:
            # No existing accounts with this pattern
            new_number = 1
        
        # Format the number with leading zeros (4 digits for numbers <= 9999)
        if new_number <= 9999:
            formatted_number = f"{new_number:04d}"
        elif new_number <= 99999:
            formatted_number = f"{new_number:05d}"
        else:
            # For very large numbers, just use the number as-is
            formatted_number = str(new_number)
        
        # Build final account number based on provided parameters
        if product_code and member_number:
            account_number = f"{prefix}-{product_code}-{member_number}-{formatted_number}"
        elif product_code:
            account_number = f"{prefix}-{product_code}-{formatted_number}"
        elif member_number:
            account_number = f"{prefix}-{member_number}-{formatted_number}"
        else:
            account_number = f"{prefix}-{formatted_number}"
        
        logger.info(f"Generated savings account number: {account_number}")
        return account_number


def generate_transaction_id(txn_type='SAV'):
    """
    Generate unique transaction ID.
    
    Format: TYPE-YYYYMMDDHHMMSS-XXXX
    Where:
    - TYPE: Transaction type prefix (DEP, WDL, SAV, etc.)
    - YYYYMMDDHHMMSS: Timestamp
    - XXXX: Counter (for multiple transactions in same second)
    
    Args:
        txn_type (str): Transaction type prefix (e.g., 'DEP', 'WDL', 'SAV')
    
    Returns:
        str: Unique transaction ID
    
    Example:
        >>> generate_transaction_id('DEP')
        'DEP-20250115143025-0001'
        >>> generate_transaction_id()
        'SAV-20250115143025-0001'
    """
    from savings.models import SavingsTransaction
    
    # Clean and validate transaction type
    txn_type = txn_type.strip().upper()
    if not txn_type:
        txn_type = 'SAV'
    
    # Generate timestamp
    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
    base_id = f"{txn_type}-{timestamp}"
    
    with transaction.atomic():
        # Check if any transactions exist with this base ID
        existing_txns = SavingsTransaction.objects.filter(
            transaction_id__startswith=base_id
        ).select_for_update()
        
        if existing_txns.exists():
            # Extract counter from existing transaction IDs
            max_counter = 0
            for txn in existing_txns.values_list('transaction_id', flat=True):
                try:
                    # Extract the counter (last part after final dash)
                    counter = int(txn.split('-')[-1])
                    max_counter = max(max_counter, counter)
                except (ValueError, IndexError):
                    continue
            
            # Increment counter
            new_counter = max_counter + 1
        else:
            # First transaction with this timestamp
            new_counter = 1
        
        # Format counter with leading zeros (4 digits)
        formatted_counter = f"{new_counter:04d}"
        
        # Build final transaction ID
        transaction_id = f"{base_id}-{formatted_counter}"
        
        # Double-check uniqueness (should never happen, but safety check)
        retry_count = 0
        max_retries = 10
        while SavingsTransaction.objects.filter(transaction_id=transaction_id).exists():
            retry_count += 1
            if retry_count > max_retries:
                # Very rare case - add random component
                import random
                random_suffix = random.randint(1000, 9999)
                transaction_id = f"{base_id}-{formatted_counter}-{random_suffix}"
                logger.warning(f"Had to add random suffix to transaction ID: {transaction_id}")
                break
            
            new_counter += 1
            formatted_counter = f"{new_counter:04d}"
            transaction_id = f"{base_id}-{formatted_counter}"
        
        logger.info(f"Generated transaction ID: {transaction_id}")
        return transaction_id


# =============================================================================
# BALANCE CALCULATIONS
# =============================================================================

def calculate_available_balance(current_balance, hold_amount):
    """
    Calculate available balance for withdrawals.
    
    Formula: Available = Current Balance - Holds
    Cannot be negative (minimum is 0)
    
    Args:
        current_balance (Decimal): Current account balance
        hold_amount (Decimal): Amount on hold
    
    Returns:
        Decimal: Available balance (never negative)
    
    Example:
        >>> calculate_available_balance(Decimal('1000.00'), Decimal('200.00'))
        Decimal('800.00')
        >>> calculate_available_balance(Decimal('100.00'), Decimal('200.00'))
        Decimal('0.00')
    """
    try:
        current = Decimal(str(current_balance))
        hold = Decimal(str(hold_amount))
        available = current - hold
        
        # Never return negative available balance
        return max(available, Decimal('0.00'))
    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating available balance: {e}")
        return Decimal('0.00')


def calculate_running_balance(account, transaction_amount, transaction_type):
    """
    Calculate running balance after a transaction.
    
    Args:
        account: SavingsAccount instance
        transaction_amount (Decimal): Transaction amount
        transaction_type (str): Type of transaction (DEPOSIT, WITHDRAWAL, etc.)
    
    Returns:
        Decimal: New running balance
    
    Example:
        >>> calculate_running_balance(account, Decimal('500.00'), 'DEPOSIT')
        Decimal('1500.00')  # If current balance was 1000.00
    """
    try:
        amount = Decimal(str(transaction_amount))
        current = Decimal(str(account.current_balance))
        
        # Credit transactions (increase balance)
        if transaction_type in ['DEPOSIT', 'TRANSFER_IN', 'INTEREST', 'DIVIDEND']:
            return current + amount
        
        # Debit transactions (decrease balance)
        elif transaction_type in ['WITHDRAWAL', 'TRANSFER_OUT', 'FEE', 'TAX', 'MAINTENANCE_FEE']:
            return current - amount
        
        # Adjustment can be either way (amount should have correct sign)
        elif transaction_type == 'ADJUSTMENT':
            return current + amount  # Assumes adjustment amount has correct sign
        
        # Reversal - opposite of original transaction
        elif transaction_type == 'REVERSAL':
            return current  # Reversal logic should be handled separately
        
        else:
            logger.warning(f"Unknown transaction type: {transaction_type}")
            return current
            
    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating running balance: {e}")
        return account.current_balance


# =============================================================================
# INTEREST CALCULATIONS
# =============================================================================

def calculate_simple_interest(principal, rate, days):
    """
    Calculate simple interest.
    
    Formula: Interest = (Principal × Rate × Days) / (100 × 365)
    
    Args:
        principal (Decimal): Principal amount
        rate (Decimal): Annual interest rate (percentage)
        days (int): Number of days
    
    Returns:
        Decimal: Interest amount (rounded to 2 decimal places)
    
    Example:
        >>> calculate_simple_interest(Decimal('10000'), Decimal('10'), 365)
        Decimal('1000.00')
        >>> calculate_simple_interest(Decimal('10000'), Decimal('10'), 30)
        Decimal('82.19')
    """
    try:
        p = Decimal(str(principal))
        r = Decimal(str(rate))
        d = Decimal(str(days))
        
        # Validate inputs
        if p < 0 or r < 0 or d < 0:
            logger.warning(f"Negative values in interest calculation: p={p}, r={r}, d={d}")
            return Decimal('0.00')
        
        # Calculate interest
        interest = (p * r * d) / (Decimal('100') * Decimal('365'))
        
        # Round to 2 decimal places
        return interest.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.error(f"Error calculating simple interest: {e}")
        return Decimal('0.00')


def calculate_compound_interest(principal, rate, days, compounding_frequency='MONTHLY'):
    """
    Calculate compound interest.
    
    Formula: A = P(1 + r/n)^(nt)
    Where:
    - A = Final amount
    - P = Principal
    - r = Annual interest rate (as decimal)
    - n = Number of times interest compounds per year
    - t = Time in years
    
    Args:
        principal (Decimal): Principal amount
        rate (Decimal): Annual interest rate (percentage)
        days (int): Number of days
        compounding_frequency (str): How often interest compounds
            Options: DAILY, WEEKLY, MONTHLY, QUARTERLY, SEMI_ANNUALLY, ANNUALLY
    
    Returns:
        Decimal: Interest amount only (not including principal)
    
    Example:
        >>> calculate_compound_interest(Decimal('10000'), Decimal('10'), 365, 'MONTHLY')
        Decimal('1047.13')  # Slightly more than simple interest due to compounding
    """
    try:
        p = Decimal(str(principal))
        r = Decimal(str(rate)) / Decimal('100')  # Convert percentage to decimal
        t = Decimal(str(days)) / Decimal('365')  # Convert days to years
        
        # Validate inputs
        if p < 0 or r < 0 or t < 0:
            logger.warning(f"Negative values in compound interest calculation: p={p}, r={r}, t={t}")
            return Decimal('0.00')
        
        # Determine compounding periods per year
        frequency_map = {
            'DAILY': 365,
            'WEEKLY': 52,
            'MONTHLY': 12,
            'QUARTERLY': 4,
            'SEMI_ANNUALLY': 2,
            'ANNUALLY': 1,
        }
        n = Decimal(str(frequency_map.get(compounding_frequency, 12)))
        
        # Calculate compound interest
        # A = P(1 + r/n)^(nt)
        rate_per_period = r / n
        num_periods = n * t
        
        # Convert to float for power calculation, then back to Decimal
        multiplier = float(1 + rate_per_period) ** float(num_periods)
        final_amount = p * Decimal(str(multiplier))
        
        # Interest is final amount minus principal
        interest = final_amount - p
        
        # Round to 2 decimal places
        return interest.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError, ZeroDivisionError, OverflowError) as e:
        logger.error(f"Error calculating compound interest: {e}")
        return Decimal('0.00')


def calculate_daily_balance_interest(transactions, rate, start_date, end_date):
    """
    Calculate interest based on daily balance.
    
    Calculates interest by determining the balance for each day in the period
    and applying the daily interest rate to each day's balance.
    
    Args:
        transactions: QuerySet of transactions in period
        rate (Decimal): Annual interest rate (percentage)
        start_date (date): Period start date
        end_date (date): Period end date
    
    Returns:
        Decimal: Total interest amount for period
    
    Example:
        >>> txns = account.transactions.filter(date__gte=start, date__lte=end)
        >>> calculate_daily_balance_interest(txns, Decimal('10'), start, end)
        Decimal('82.47')
    """
    try:
        r = Decimal(str(rate)) / Decimal('100')  # Convert to decimal
        total_interest = Decimal('0.00')
        
        # Build daily balances
        current_date = start_date
        current_balance = Decimal('0.00')
        
        # Get all transactions ordered by date
        txn_list = list(transactions.order_by('transaction_date'))
        txn_index = 0
        
        # Iterate through each day in the period
        while current_date <= end_date:
            # Update balance for all transactions on this date
            while txn_index < len(txn_list):
                txn = txn_list[txn_index]
                txn_date = txn.transaction_date.date() if hasattr(txn.transaction_date, 'date') else txn.transaction_date
                
                if txn_date > current_date:
                    break  # This transaction is in the future
                
                # Apply transaction to balance
                if txn.transaction_type in ['DEPOSIT', 'TRANSFER_IN', 'INTEREST', 'DIVIDEND']:
                    current_balance += txn.amount
                elif txn.transaction_type in ['WITHDRAWAL', 'TRANSFER_OUT', 'FEE', 'TAX']:
                    current_balance -= (txn.amount + txn.fees + txn.tax_amount)
                
                txn_index += 1
            
            # Calculate interest for this day
            daily_interest = (current_balance * r) / Decimal('365')
            total_interest += daily_interest
            
            # Move to next day
            current_date += timedelta(days=1)
        
        # Round to 2 decimal places
        return total_interest.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.error(f"Error calculating daily balance interest: {e}")
        return Decimal('0.00')


def calculate_average_balance_interest(opening_balance, closing_balance, rate, days):
    """
    Calculate interest based on average balance.
    
    Formula: Interest = ((Opening + Closing) / 2) × Rate × Days / (100 × 365)
    
    Args:
        opening_balance (Decimal): Balance at start of period
        closing_balance (Decimal): Balance at end of period
        rate (Decimal): Annual interest rate (percentage)
        days (int): Number of days in period
    
    Returns:
        Decimal: Interest amount
    
    Example:
        >>> calculate_average_balance_interest(
        ...     Decimal('10000'), Decimal('12000'), Decimal('10'), 30
        ... )
        Decimal('90.41')
    """
    try:
        opening = Decimal(str(opening_balance))
        closing = Decimal(str(closing_balance))
        r = Decimal(str(rate)) / Decimal('100')
        d = Decimal(str(days))
        
        # Validate inputs
        if opening < 0 or closing < 0 or r < 0 or d < 0:
            logger.warning(f"Negative values in average balance interest calculation")
            return Decimal('0.00')
        
        # Calculate average balance
        avg_balance = (opening + closing) / Decimal('2')
        
        # Calculate interest
        interest = (avg_balance * r * d) / Decimal('365')
        
        # Round to 2 decimal places
        return interest.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.error(f"Error calculating average balance interest: {e}")
        return Decimal('0.00')


def calculate_minimum_balance_interest(minimum_balance, rate, days):
    """
    Calculate interest based on minimum balance in period.
    Uses simple interest formula with minimum balance.
    
    Args:
        minimum_balance (Decimal): Lowest balance in period
        rate (Decimal): Annual interest rate (percentage)
        days (int): Number of days in period
    
    Returns:
        Decimal: Interest amount
    
    Example:
        >>> calculate_minimum_balance_interest(Decimal('5000'), Decimal('10'), 30)
        Decimal('41.10')
    """
    return calculate_simple_interest(minimum_balance, rate, days)


def calculate_tiered_interest(balance, interest_tiers):
    """
    Calculate interest using tiered rates.
    Finds the applicable tier based on balance.
    
    Args:
        balance (Decimal): Current balance
        interest_tiers: QuerySet of InterestTier objects (ordered by min_balance)
    
    Returns:
        tuple: (applicable_rate: Decimal, tier: InterestTier or None)
    
    Example:
        >>> tiers = product.interest_tiers.filter(is_active=True).order_by('min_balance')
        >>> rate, tier = calculate_tiered_interest(Decimal('50000'), tiers)
        >>> rate
        Decimal('12.50')
    """
    try:
        bal = Decimal(str(balance))
        
        # Find applicable tier
        applicable_tier = None
        for tier in interest_tiers:
            # Check if balance is within this tier's range
            if bal >= tier.min_balance:
                if tier.max_balance is None or bal <= tier.max_balance:
                    applicable_tier = tier
                    break  # Found the tier
        
        if applicable_tier:
            return applicable_tier.interest_rate, applicable_tier
        
        # No tier found - return zero rate
        return Decimal('0.00'), None
        
    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating tiered interest: {e}")
        return Decimal('0.00'), None


def calculate_withholding_tax(gross_interest, tax_rate):
    """
    Calculate withholding tax on interest.
    
    Formula: Tax = Gross Interest × (Tax Rate / 100)
    
    Args:
        gross_interest (Decimal): Gross interest amount
        tax_rate (Decimal): Tax rate (percentage)
    
    Returns:
        Decimal: Tax amount
    
    Example:
        >>> calculate_withholding_tax(Decimal('1000.00'), Decimal('15'))
        Decimal('150.00')
    """
    try:
        interest = Decimal(str(gross_interest))
        rate = Decimal(str(tax_rate)) / Decimal('100')
        
        # Validate inputs
        if interest < 0 or rate < 0:
            logger.warning(f"Negative values in tax calculation: interest={interest}, rate={rate}")
            return Decimal('0.00')
        
        tax = interest * rate
        
        # Round to 2 decimal places
        return tax.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating withholding tax: {e}")
        return Decimal('0.00')


# =============================================================================
# FEE CALCULATIONS
# =============================================================================

def calculate_transaction_fee(amount, flat_fee, percentage_fee):
    """
    Calculate transaction fee (flat + percentage).
    
    Formula: Total Fee = Flat Fee + (Amount × Percentage / 100)
    
    Args:
        amount (Decimal): Transaction amount
        flat_fee (Decimal): Flat fee amount
        percentage_fee (Decimal): Percentage fee
    
    Returns:
        Decimal: Total fee
    
    Example:
        >>> calculate_transaction_fee(Decimal('10000'), Decimal('50'), Decimal('2'))
        Decimal('250.00')  # 50 + (10000 * 0.02)
    """
    try:
        amt = Decimal(str(amount))
        flat = Decimal(str(flat_fee))
        pct = Decimal(str(percentage_fee)) / Decimal('100')
        
        # Validate inputs
        if amt < 0 or flat < 0 or pct < 0:
            logger.warning(f"Negative values in fee calculation")
            return Decimal('0.00')
        
        percentage_amount = amt * pct
        total_fee = flat + percentage_amount
        
        # Round to 2 decimal places
        return total_fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating transaction fee: {e}")
        return Decimal('0.00')


def calculate_early_withdrawal_penalty(amount, penalty_rate):
    """
    Calculate penalty for early withdrawal from fixed deposit.
    
    Formula: Penalty = Amount × (Penalty Rate / 100)
    
    Args:
        amount (Decimal): Withdrawal amount
        penalty_rate (Decimal): Penalty rate (percentage)
    
    Returns:
        Decimal: Penalty amount
    
    Example:
        >>> calculate_early_withdrawal_penalty(Decimal('50000'), Decimal('5'))
        Decimal('2500.00')
    """
    try:
        amt = Decimal(str(amount))
        rate = Decimal(str(penalty_rate)) / Decimal('100')
        
        # Validate inputs
        if amt < 0 or rate < 0:
            logger.warning(f"Negative values in penalty calculation")
            return Decimal('0.00')
        
        penalty = amt * rate
        
        # Round to 2 decimal places
        return penalty.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating early withdrawal penalty: {e}")
        return Decimal('0.00')

# =============================================================================
# VALIDATION UTILITIES
# =============================================================================

def validate_withdrawal(account, amount):
    """
    Comprehensive withdrawal validation.
    
    Args:
        account: SavingsAccount instance
        amount: Withdrawal amount
    
    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        amt = Decimal(str(amount))
    except (ValueError, TypeError):
        return False, "Invalid amount"
    
    # Check account status
    if account.effective_status not in ['ACTIVE', 'DORMANT']:
        return False, f"Account is {account.get_status_display()}"
    
    # Check available balance
    if amt > account.available_balance:
        return False, "Insufficient available balance"
    
    # Check minimum withdrawal
    if amt < account.savings_product.minimum_withdrawal_amount:
        from core.utils import format_money
        min_formatted = format_money(account.savings_product.minimum_withdrawal_amount)
        return False, f"Amount below minimum withdrawal of {min_formatted}"
    
    # Check maximum withdrawal
    if account.savings_product.maximum_withdrawal_amount:
        if amt > account.savings_product.maximum_withdrawal_amount:
            from core.utils import format_money
            max_formatted = format_money(account.savings_product.maximum_withdrawal_amount)
            return False, f"Amount exceeds maximum withdrawal of {max_formatted}"
    
    # Check minimum balance maintenance
    balance_after = account.current_balance - amt
    if balance_after < account.savings_product.minimum_balance:
        from core.utils import format_money
        min_bal = format_money(account.savings_product.minimum_balance)
        return False, f"Withdrawal would bring balance below minimum of {min_bal}"
    
    # Check fixed deposit maturity
    if account.is_fixed_deposit and not account.is_matured:
        # Could allow with penalty
        if account.savings_product.early_withdrawal_penalty_rate > 0:
            penalty = calculate_early_withdrawal_penalty(
                amt,
                account.savings_product.early_withdrawal_penalty_rate
            )
            from core.utils import format_money
            return True, f"Early withdrawal penalty of {format_money(penalty)} will apply"
        else:
            return False, "Fixed deposit has not matured"
    
    return True, "Withdrawal allowed"


def validate_deposit(account, amount):
    """
    Comprehensive deposit validation.
    
    Args:
        account: SavingsAccount instance
        amount: Deposit amount
    
    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        amt = Decimal(str(amount))
    except (ValueError, TypeError):
        return False, "Invalid amount"
    
    # Check account status
    if account.effective_status not in ['ACTIVE', 'DORMANT', 'PENDING_APPROVAL']:
        return False, f"Account is {account.get_status_display()}"
    
    # Check minimum deposit
    if amt < account.savings_product.minimum_deposit_amount:
        from core.utils import format_money
        min_formatted = format_money(account.savings_product.minimum_deposit_amount)
        return False, f"Amount below minimum deposit of {min_formatted}"
    
    # Check maximum balance
    if account.savings_product.maximum_balance:
        balance_after = account.current_balance + amt
        if balance_after > account.savings_product.maximum_balance:
            from core.utils import format_money
            max_formatted = format_money(account.savings_product.maximum_balance)
            return False, f"Deposit would exceed maximum balance of {max_formatted}"
    
    # Check fixed deposit restrictions
    if account.is_fixed_deposit and account.status == 'ACTIVE':
        return False, "Cannot make additional deposits to active fixed deposit"
    
    return True, "Deposit allowed"


def validate_transfer(source_account, destination_account, amount):
    """
    Validate account transfer.
    
    Args:
        source_account: Source SavingsAccount
        destination_account: Destination SavingsAccount
        amount: Transfer amount
    
    Returns:
        tuple: (is_valid, error_message)
    """
    # Validate withdrawal from source
    withdrawal_valid, withdrawal_msg = validate_withdrawal(source_account, amount)
    if not withdrawal_valid:
        return False, f"Source account: {withdrawal_msg}"
    
    # Validate deposit to destination
    deposit_valid, deposit_msg = validate_deposit(destination_account, amount)
    if not deposit_valid:
        return False, f"Destination account: {deposit_msg}"
    
    # Check if accounts are different
    if source_account.id == destination_account.id:
        return False, "Cannot transfer to same account"
    
    return True, "Transfer allowed"


# =============================================================================
# DATE/TIME UTILITIES
# =============================================================================

def calculate_maturity_date(opening_date, term_days):
    """
    Calculate maturity date for fixed deposit.
    
    Args:
        opening_date: Opening date
        term_days: Term length in days
    
    Returns:
        date: Maturity date
    """
    try:
        if isinstance(opening_date, date):
            start = opening_date
        else:
            start = opening_date.date()
        
        return start + timedelta(days=term_days)
    except (ValueError, TypeError, AttributeError):
        return None


def get_days_between(start_date, end_date):
    """
    Calculate days between two dates.
    
    Args:
        start_date: Start date
        end_date: End date
    
    Returns:
        int: Number of days
    """
    try:
        if isinstance(start_date, date):
            start = start_date
        else:
            start = start_date.date()
        
        if isinstance(end_date, date):
            end = end_date
        else:
            end = end_date.date()
        
        return (end - start).days
    except (ValueError, TypeError, AttributeError):
        return 0


def calculate_next_frequency_date(current_date, frequency):
    """
    Calculate next date based on frequency.
    
    Args:
        current_date: Current date
        frequency: DAILY, WEEKLY, BIWEEKLY, MONTHLY, QUARTERLY, ANNUALLY
    
    Returns:
        date: Next date
    """
    try:
        if isinstance(current_date, date):
            base_date = current_date
        else:
            base_date = current_date.date()
        
        if frequency == 'DAILY':
            return base_date + timedelta(days=1)
        elif frequency == 'WEEKLY':
            return base_date + timedelta(days=7)
        elif frequency == 'BIWEEKLY':
            return base_date + timedelta(days=14)
        elif frequency == 'MONTHLY':
            return base_date + relativedelta(months=1)
        elif frequency == 'QUARTERLY':
            return base_date + relativedelta(months=3)
        elif frequency == 'ANNUALLY':
            return base_date + relativedelta(years=1)
        else:
            return base_date
            
    except (ValueError, TypeError, AttributeError):
        return current_date


# =============================================================================
# REPORTING UTILITIES
# =============================================================================

def get_transaction_summary(transactions):
    """
    Get summary of transactions.
    
    Args:
        transactions: QuerySet of SavingsTransaction
    
    Returns:
        dict: Summary data
    """
    from django.db.models import Sum, Count, Avg
    
    summary = transactions.aggregate(
        total_count=Count('id'),
        total_amount=Sum('amount'),
        total_fees=Sum('fees'),
        total_taxes=Sum('tax_amount'),
        avg_amount=Avg('amount'),
        deposits=Count('id', filter=Q(transaction_type='DEPOSIT')),
        withdrawals=Count('id', filter=Q(transaction_type='WITHDRAWAL')),
        deposit_amount=Sum('amount', filter=Q(transaction_type='DEPOSIT')),
        withdrawal_amount=Sum('amount', filter=Q(transaction_type='WITHDRAWAL')),
    )
    
    return {
        'total_transactions': summary['total_count'] or 0,
        'total_amount': float(summary['total_amount'] or 0),
        'total_fees': float(summary['total_fees'] or 0),
        'total_taxes': float(summary['total_taxes'] or 0),
        'average_amount': float(summary['avg_amount'] or 0),
        'deposits': summary['deposits'] or 0,
        'withdrawals': summary['withdrawals'] or 0,
        'deposit_amount': float(summary['deposit_amount'] or 0),
        'withdrawal_amount': float(summary['withdrawal_amount'] or 0),
        'net_flow': float((summary['deposit_amount'] or 0) - (summary['withdrawal_amount'] or 0)),
    }


def format_account_statement(account, transactions, start_date, end_date):
    """
    Format account statement data.
    
    Args:
        account: SavingsAccount instance
        transactions: QuerySet of transactions
        start_date: Statement start date
        end_date: Statement end date
    
    Returns:
        dict: Formatted statement data
    """
    from core.utils import format_money
    
    # Get opening balance (balance before start_date)
    opening_transactions = account.transactions.filter(
        transaction_date__lt=start_date,
        is_reversed=False
    ).order_by('-transaction_date').first()
    
    opening_balance = opening_transactions.running_balance if opening_transactions else Decimal('0.00')
    
    # Get closing balance
    closing_transactions = transactions.filter(
        transaction_date__lte=end_date
    ).order_by('-transaction_date').first()
    
    closing_balance = closing_transactions.running_balance if closing_transactions else opening_balance
    
    # Get transaction summary
    summary = get_transaction_summary(transactions)
    
    return {
        'account': account,
        'period': {
            'start': start_date,
            'end': end_date,
        },
        'balances': {
            'opening': float(opening_balance),
            'closing': float(closing_balance),
            'opening_formatted': format_money(opening_balance),
            'closing_formatted': format_money(closing_balance),
        },
        'transactions': transactions,
        'summary': summary,
    }


# =============================================================================
# BULK OPERATION HELPERS
# =============================================================================

def get_accounts_for_interest_calculation(product=None, status_list=None):
    """
    Get accounts eligible for interest calculation.
    
    Args:
        product: Optional SavingsProduct to filter
        status_list: Optional list of statuses
    
    Returns:
        QuerySet: Eligible accounts
    """
    from savings.models import SavingsAccount
    
    if status_list is None:
        status_list = ['ACTIVE', 'DORMANT']
    
    accounts = SavingsAccount.objects.filter(
        status__in=status_list
    ).select_related('savings_product', 'member')
    
    if product:
        accounts = accounts.filter(savings_product=product)
    
    # Exclude zero balance accounts
    accounts = accounts.filter(current_balance__gt=0)
    
    return accounts


def batch_update_available_balances(accounts):
    """
    Batch update available balances for multiple accounts.
    
    Args:
        accounts: QuerySet or list of SavingsAccount instances
    
    Returns:
        int: Number of accounts updated
    """
    updated_count = 0
    
    for account in accounts:
        try:
            account.available_balance = calculate_available_balance(
                account.current_balance,
                account.hold_amount
            )
            account.save(update_fields=['available_balance'])
            updated_count += 1
        except Exception as e:
            logger.error(f"Error updating available balance for account {account.account_number}: {e}")
            continue
    
    return updated_count


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_account_age(account):
    """
    Get account age in days and human-readable format.
    
    Args:
        account: SavingsAccount instance
    
    Returns:
        dict: Age information
    """
    today = timezone.now().date()
    age_days = (today - account.opening_date).days
    
    years = age_days // 365
    remaining_days = age_days % 365
    months = remaining_days // 30
    days = remaining_days % 30
    
    if years > 0:
        readable = f"{years} year{'s' if years > 1 else ''}"
        if months > 0:
            readable += f", {months} month{'s' if months > 1 else ''}"
    elif months > 0:
        readable = f"{months} month{'s' if months > 1 else ''}"
        if days > 0:
            readable += f", {days} day{'s' if days > 1 else ''}"
    else:
        readable = f"{days} day{'s' if days > 1 else ''}"
    
    return {
        'days': age_days,
        'years': years,
        'months': months,
        'readable': readable,
    }


def is_account_dormant(account):
    """
    Check if account should be marked as dormant.
    
    Args:
        account: SavingsAccount instance
    
    Returns:
        tuple: (is_dormant, days_inactive)
    """
    if not account.last_transaction_date:
        return False, 0
    
    today = timezone.now().date()
    days_inactive = (today - account.last_transaction_date).days
    dormancy_threshold = account.savings_product.dormancy_period_days
    
    return days_inactive >= dormancy_threshold, days_inactive


def can_close_account(account):
    """
    Check if account can be closed.
    
    Args:
        account: SavingsAccount instance
    
    Returns:
        tuple: (can_close, reason)
    """
    # Check if balance is zero or minimal
    if account.current_balance > Decimal('0.00'):
        from core.utils import format_money
        return False, f"Account has balance of {format_money(account.current_balance)}"
    
    # Check for pending transactions
    from savings.models import SavingsTransaction
    pending_txns = SavingsTransaction.objects.filter(
        account=account,
        is_reversed=False,
        post_date__gt=timezone.now().date()
    ).exists()
    
    if pending_txns:
        return False, "Account has pending transactions"
    
    # Check for active standing orders
    active_orders = account.standing_orders_out.filter(status='ACTIVE').exists()
    if active_orders:
        return False, "Account has active standing orders"
    
    # Check for holds
    if account.hold_amount > 0:
        from core.utils import format_money
        return False, f"Account has holds of {format_money(account.hold_amount)}"
    
    return True, "Account can be closed"