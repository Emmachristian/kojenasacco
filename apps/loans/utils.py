# loans/utils.py

"""
Loans Utility Functions

Pure utility functions with NO side effects (no database writes):
- Loan number generation logic
- Application number generation logic
- Payment number generation logic
- Interest calculations (flat, reducing balance, compound)
- EMI/installment calculations
- Loan schedule generation
- Fee calculations
- Validation functions
- Date utilities
- Payment allocation logic
- Amortization calculations
- Helper functions for common operations

All functions are pure - they calculate and return values without modifying the database.
Database writes are handled by signals.py and services.py.
"""

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from datetime import timedelta, date
from dateutil.relativedelta import relativedelta
import logging
import math

logger = logging.getLogger(__name__)


# =============================================================================
# NUMBER GENERATION
# =============================================================================

def generate_loan_application_number(product_code=None):
    """
    Generate unique loan application number.
    
    Format: LA-{PRODUCT_CODE}-YYYYMMDDHHMMSS-XXXX
    
    Args:
        product_code (str, optional): Loan product code prefix
    
    Returns:
        str: Unique application number
    
    Example:
        >>> generate_loan_application_number('PL')
        'LA-PL-20250129143025-0001'
        >>> generate_loan_application_number()
        'LA-20250129143025-0001'
    """
    from loans.models import LoanApplication
    
    # Clean product code
    if product_code:
        product_code = product_code.strip().upper()[:3]
    
    # Generate timestamp
    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
    
    # Build base ID
    if product_code:
        base_id = f"LA-{product_code}-{timestamp}"
    else:
        base_id = f"LA-{timestamp}"
    
    with transaction.atomic():
        # Check for existing applications with this base ID
        existing_apps = LoanApplication.objects.filter(
            application_number__startswith=base_id
        ).select_for_update()
        
        if existing_apps.exists():
            # Extract counters
            max_counter = 0
            for app_num in existing_apps.values_list('application_number', flat=True):
                try:
                    counter = int(app_num.split('-')[-1])
                    max_counter = max(max_counter, counter)
                except (ValueError, IndexError):
                    continue
            
            new_counter = max_counter + 1
        else:
            new_counter = 1
        
        # Format counter
        formatted_counter = f"{new_counter:04d}"
        application_number = f"{base_id}-{formatted_counter}"
        
        logger.info(f"Generated loan application number: {application_number}")
        return application_number


def generate_loan_number(product_code=None, member_id=None):
    """
    Generate unique loan number.
    
    Format options:
    1. With both: LN-{PRODUCT}-M{MEMBER_ID}-YYYYMMDD-XXXX
    2. Product only: LN-{PRODUCT}-YYYYMMDD-XXXX
    3. No parameters: LN-YYYYMMDD-XXXX
    
    Args:
        product_code (str, optional): Loan product code
        member_id (str/int, optional): Member ID
    
    Returns:
        str: Unique loan number
    
    Example:
        >>> generate_loan_number('PL', 12345)
        'LN-PL-M12345-20250129-0001'
    """
    from loans.models import Loan
    
    # Clean inputs
    if product_code:
        product_code = product_code.strip().upper()[:3]
    
    if member_id:
        member_id = str(member_id)[:8]
    
    # Generate timestamp
    timestamp = timezone.now().strftime('%Y%m%d')
    
    # Build search pattern
    if product_code and member_id:
        base_id = f"LN-{product_code}-M{member_id}-{timestamp}"
    elif product_code:
        base_id = f"LN-{product_code}-{timestamp}"
    else:
        base_id = f"LN-{timestamp}"
    
    with transaction.atomic():
        # Check for existing loans
        existing_loans = Loan.objects.filter(
            loan_number__startswith=base_id
        ).select_for_update()
        
        if existing_loans.exists():
            max_counter = 0
            for loan_num in existing_loans.values_list('loan_number', flat=True):
                try:
                    counter = int(loan_num.split('-')[-1])
                    max_counter = max(max_counter, counter)
                except (ValueError, IndexError):
                    continue
            
            new_counter = max_counter + 1
        else:
            new_counter = 1
        
        # Format counter
        formatted_counter = f"{new_counter:04d}"
        loan_number = f"{base_id}-{formatted_counter}"
        
        logger.info(f"Generated loan number: {loan_number}")
        return loan_number


def generate_payment_number():
    """
    Generate unique payment number.
    
    Format: PMT-YYYYMMDDHHMMSS-XXXX
    
    Returns:
        str: Unique payment number
    
    Example:
        >>> generate_payment_number()
        'PMT-20250129143025-0001'
    """
    from loans.models import LoanPayment
    
    # Generate timestamp
    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
    base_id = f"PMT-{timestamp}"
    
    with transaction.atomic():
        # Check for existing payments
        existing_payments = LoanPayment.objects.filter(
            payment_number__startswith=base_id
        ).select_for_update()
        
        if existing_payments.exists():
            max_counter = 0
            for pmt_num in existing_payments.values_list('payment_number', flat=True):
                try:
                    counter = int(pmt_num.split('-')[-1])
                    max_counter = max(max_counter, counter)
                except (ValueError, IndexError):
                    continue
            
            new_counter = max_counter + 1
        else:
            new_counter = 1
        
        # Format counter
        formatted_counter = f"{new_counter:04d}"
        payment_number = f"{base_id}-{formatted_counter}"
        
        logger.info(f"Generated payment number: {payment_number}")
        return payment_number


# =============================================================================
# INTEREST CALCULATIONS
# =============================================================================

def calculate_flat_interest(principal, rate, term_months):
    """
    Calculate total interest using flat rate method.
    
    Flat rate calculates interest on the full principal for entire term.
    Formula: Interest = (Principal × Rate × Term) / (100 × 12)
    
    Args:
        principal (Decimal): Loan principal amount
        rate (Decimal): Annual interest rate (percentage)
        term_months (int): Loan term in months
    
    Returns:
        Decimal: Total interest amount
    
    Example:
        >>> calculate_flat_interest(Decimal('100000'), Decimal('12'), 12)
        Decimal('12000.00')
    """
    try:
        p = Decimal(str(principal))
        r = Decimal(str(rate)) / Decimal('100')  # Convert to decimal
        t = Decimal(str(term_months)) / Decimal('12')  # Convert to years
        
        # Validate inputs
        if p < 0 or r < 0 or t < 0:
            logger.warning("Negative values in flat interest calculation")
            return Decimal('0.00')
        
        # Calculate interest
        interest = p * r * t
        
        return interest.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.error(f"Error calculating flat interest: {e}")
        return Decimal('0.00')


def calculate_reducing_balance_interest(principal, rate, term_months, payment_frequency='MONTHLY'):
    """
    Calculate total interest using reducing balance method.
    
    Interest is calculated on the outstanding balance, which reduces with each payment.
    Uses actual loan amortization schedule.
    
    Args:
        principal (Decimal): Loan principal amount
        rate (Decimal): Annual interest rate (percentage)
        term_months (int): Loan term in months
        payment_frequency (str): Payment frequency (MONTHLY, WEEKLY, etc.)
    
    Returns:
        Decimal: Total interest amount
    
    Example:
        >>> calculate_reducing_balance_interest(Decimal('100000'), Decimal('12'), 12)
        Decimal('6618.48')
    """
    try:
        # Generate amortization schedule
        schedule = generate_loan_schedule(
            principal=principal,
            rate=rate,
            term_months=term_months,
            start_date=timezone.now().date(),
            payment_frequency=payment_frequency,
            interest_type='REDUCING_BALANCE'
        )
        
        # Sum up all interest from schedule
        total_interest = sum(item['interest'] for item in schedule)
        
        return Decimal(str(total_interest)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception as e:
        logger.error(f"Error calculating reducing balance interest: {e}")
        return Decimal('0.00')


def calculate_monthly_emi(principal, rate, term_months):
    """
    Calculate Equal Monthly Installment (EMI) for reducing balance loan.
    
    Formula: EMI = P × r × (1 + r)^n / ((1 + r)^n - 1)
    Where:
        P = Principal
        r = Monthly interest rate (annual rate / 12 / 100)
        n = Number of months
    
    Args:
        principal (Decimal): Loan principal amount
        rate (Decimal): Annual interest rate (percentage)
        term_months (int): Loan term in months
    
    Returns:
        Decimal: Monthly EMI amount
    
    Example:
        >>> calculate_monthly_emi(Decimal('100000'), Decimal('12'), 12)
        Decimal('8884.88')
    """
    try:
        p = float(principal)
        r = float(rate) / 100 / 12  # Monthly interest rate
        n = int(term_months)
        
        # Validate inputs
        if p <= 0 or r < 0 or n <= 0:
            logger.warning("Invalid values in EMI calculation")
            return Decimal('0.00')
        
        # Handle zero interest rate
        if r == 0:
            emi = p / n
        else:
            # EMI formula
            emi = p * r * math.pow(1 + r, n) / (math.pow(1 + r, n) - 1)
        
        return Decimal(str(emi)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError, ZeroDivisionError, OverflowError) as e:
        logger.error(f"Error calculating EMI: {e}")
        return Decimal('0.00')


def calculate_interest_for_period(outstanding_balance, rate, days):
    """
    Calculate interest for a specific period based on outstanding balance.
    
    Used for calculating interest between irregular payments.
    Formula: Interest = (Balance × Rate × Days) / (365 × 100)
    
    Args:
        outstanding_balance (Decimal): Current outstanding balance
        rate (Decimal): Annual interest rate (percentage)
        days (int): Number of days
    
    Returns:
        Decimal: Interest for the period
    
    Example:
        >>> calculate_interest_for_period(Decimal('50000'), Decimal('12'), 30)
        Decimal('493.15')
    """
    try:
        balance = Decimal(str(outstanding_balance))
        r = Decimal(str(rate)) / Decimal('100')
        d = Decimal(str(days))
        
        # Validate inputs
        if balance < 0 or r < 0 or d < 0:
            logger.warning("Negative values in interest calculation")
            return Decimal('0.00')
        
        # Calculate interest
        interest = (balance * r * d) / Decimal('365')
        
        return interest.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.error(f"Error calculating interest for period: {e}")
        return Decimal('0.00')


# =============================================================================
# LOAN SCHEDULE GENERATION
# =============================================================================

def generate_loan_schedule(principal, rate, term_months, start_date, 
                           payment_frequency='MONTHLY', interest_type='REDUCING_BALANCE',
                           grace_period_days=0):
    """
    Generate complete loan repayment schedule.
    
    Args:
        principal (Decimal): Loan principal amount
        rate (Decimal): Annual interest rate (percentage)
        term_months (int): Loan term in months
        start_date (date): Loan start date
        payment_frequency (str): Payment frequency
        interest_type (str): Interest calculation method
        grace_period_days (int): Grace period before first payment
    
    Returns:
        list: List of dictionaries with schedule details
            [
                {
                    'installment_number': 1,
                    'due_date': date,
                    'principal': Decimal,
                    'interest': Decimal,
                    'total': Decimal,
                    'balance': Decimal
                },
                ...
            ]
    
    Example:
        >>> schedule = generate_loan_schedule(
        ...     Decimal('100000'), Decimal('12'), 12,
        ...     date(2025, 1, 1), 'MONTHLY', 'REDUCING_BALANCE'
        ... )
    """
    try:
        p = Decimal(str(principal))
        r = Decimal(str(rate))
        
        schedule = []
        
        if interest_type == 'FLAT':
            # Flat rate - equal principal, equal interest each period
            schedule = _generate_flat_schedule(p, r, term_months, start_date, 
                                              payment_frequency, grace_period_days)
        
        elif interest_type == 'REDUCING_BALANCE':
            # Reducing balance - EMI calculation
            schedule = _generate_reducing_balance_schedule(p, r, term_months, start_date,
                                                          payment_frequency, grace_period_days)
        
        elif interest_type == 'COMPOUND':
            # Compound interest
            schedule = _generate_compound_schedule(p, r, term_months, start_date,
                                                  payment_frequency, grace_period_days)
        
        return schedule
        
    except Exception as e:
        logger.error(f"Error generating loan schedule: {e}")
        return []


def _generate_flat_schedule(principal, rate, term_months, start_date, 
                            payment_frequency, grace_period_days):
    """Generate schedule for flat rate loan"""
    schedule = []
    
    # Calculate total interest
    total_interest = calculate_flat_interest(principal, rate, term_months)
    
    # Calculate per-period amounts
    principal_per_period = principal / Decimal(str(term_months))
    interest_per_period = total_interest / Decimal(str(term_months))
    
    remaining_balance = principal
    current_date = start_date + timedelta(days=grace_period_days)
    
    for i in range(1, term_months + 1):
        # Calculate due date
        due_date = calculate_next_payment_date(current_date, payment_frequency)
        
        # For last installment, use remaining balance
        if i == term_months:
            principal_amount = remaining_balance
        else:
            principal_amount = principal_per_period
        
        interest_amount = interest_per_period
        total_amount = principal_amount + interest_amount
        remaining_balance -= principal_amount
        
        schedule.append({
            'installment_number': i,
            'due_date': due_date,
            'principal': principal_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'interest': interest_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'total': total_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'balance': max(remaining_balance, Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        })
        
        current_date = due_date
    
    return schedule


def _generate_reducing_balance_schedule(principal, rate, term_months, start_date,
                                       payment_frequency, grace_period_days):
    """Generate schedule for reducing balance loan"""
    schedule = []
    
    # Calculate EMI
    emi = calculate_monthly_emi(principal, rate, term_months)
    
    # Monthly interest rate
    monthly_rate = (Decimal(str(rate)) / Decimal('100')) / Decimal('12')
    
    remaining_balance = principal
    current_date = start_date + timedelta(days=grace_period_days)
    
    for i in range(1, term_months + 1):
        # Calculate due date
        due_date = calculate_next_payment_date(current_date, payment_frequency)
        
        # Calculate interest on remaining balance
        interest_amount = (remaining_balance * monthly_rate).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        
        # Principal is EMI minus interest
        principal_amount = emi - interest_amount
        
        # For last installment, adjust to clear remaining balance
        if i == term_months:
            principal_amount = remaining_balance
            total_amount = principal_amount + interest_amount
        else:
            total_amount = emi
        
        remaining_balance -= principal_amount
        
        schedule.append({
            'installment_number': i,
            'due_date': due_date,
            'principal': principal_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'interest': interest_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'total': total_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'balance': max(remaining_balance, Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        })
        
        current_date = due_date
    
    return schedule


def _generate_compound_schedule(principal, rate, term_months, start_date,
                               payment_frequency, grace_period_days):
    """Generate schedule for compound interest loan"""
    # For compound interest, use reducing balance method
    # The difference is in how interest is calculated and compounded
    return _generate_reducing_balance_schedule(
        principal, rate, term_months, start_date,
        payment_frequency, grace_period_days
    )


def calculate_next_payment_date(current_date, payment_frequency):
    """
    Calculate next payment date based on frequency.
    
    Args:
        current_date (date): Current payment date
        payment_frequency (str): Payment frequency
    
    Returns:
        date: Next payment date
    """
    if payment_frequency == 'DAILY':
        return current_date + timedelta(days=1)
    elif payment_frequency == 'WEEKLY':
        return current_date + timedelta(weeks=1)
    elif payment_frequency == 'BI_WEEKLY':
        return current_date + timedelta(weeks=2)
    elif payment_frequency == 'MONTHLY':
        return current_date + relativedelta(months=1)
    elif payment_frequency == 'QUARTERLY':
        return current_date + relativedelta(months=3)
    elif payment_frequency == 'ANNUALLY':
        return current_date + relativedelta(years=1)
    else:
        return current_date + relativedelta(months=1)  # Default to monthly


# =============================================================================
# FEE CALCULATIONS
# =============================================================================

def calculate_processing_fee(loan_amount, fee_percentage):
    """
    Calculate loan processing fee.
    
    Formula: Fee = (Loan Amount × Fee Percentage) / 100
    
    Args:
        loan_amount (Decimal): Loan amount
        fee_percentage (Decimal): Fee percentage
    
    Returns:
        Decimal: Processing fee amount
    
    Example:
        >>> calculate_processing_fee(Decimal('100000'), Decimal('2'))
        Decimal('2000.00')
    """
    try:
        amount = Decimal(str(loan_amount))
        fee_pct = Decimal(str(fee_percentage)) / Decimal('100')
        
        fee = amount * fee_pct
        
        return fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating processing fee: {e}")
        return Decimal('0.00')


def calculate_insurance_fee(loan_amount, insurance_percentage):
    """
    Calculate loan insurance fee.
    
    Args:
        loan_amount (Decimal): Loan amount
        insurance_percentage (Decimal): Insurance percentage
    
    Returns:
        Decimal: Insurance fee amount
    """
    return calculate_processing_fee(loan_amount, insurance_percentage)


def calculate_early_repayment_penalty(outstanding_balance, penalty_percentage):
    """
    Calculate early repayment penalty.
    
    Args:
        outstanding_balance (Decimal): Outstanding loan balance
        penalty_percentage (Decimal): Penalty percentage
    
    Returns:
        Decimal: Penalty amount
    
    Example:
        >>> calculate_early_repayment_penalty(Decimal('50000'), Decimal('3'))
        Decimal('1500.00')
    """
    try:
        balance = Decimal(str(outstanding_balance))
        penalty_pct = Decimal(str(penalty_percentage)) / Decimal('100')
        
        penalty = balance * penalty_pct
        
        return penalty.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating early repayment penalty: {e}")
        return Decimal('0.00')


def calculate_late_payment_penalty(overdue_amount, penalty_rate, days_overdue):
    """
    Calculate late payment penalty.
    
    Formula: Penalty = (Overdue Amount × Penalty Rate × Days) / (365 × 100)
    
    Args:
        overdue_amount (Decimal): Amount overdue
        penalty_rate (Decimal): Annual penalty rate (percentage)
        days_overdue (int): Number of days overdue
    
    Returns:
        Decimal: Penalty amount
    
    Example:
        >>> calculate_late_payment_penalty(Decimal('10000'), Decimal('5'), 30)
        Decimal('41.10')
    """
    try:
        amount = Decimal(str(overdue_amount))
        rate = Decimal(str(penalty_rate)) / Decimal('100')
        days = Decimal(str(days_overdue))
        
        penalty = (amount * rate * days) / Decimal('365')
        
        return penalty.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.error(f"Error calculating late payment penalty: {e}")
        return Decimal('0.00')


# =============================================================================
# PAYMENT ALLOCATION
# =============================================================================

def allocate_payment(payment_amount, outstanding_fees, outstanding_penalties,
                    outstanding_interest, outstanding_principal):
    """
    Allocate payment amount to different loan components.
    
    Standard allocation order: Fees → Penalties → Interest → Principal
    
    Args:
        payment_amount (Decimal): Total payment amount
        outstanding_fees (Decimal): Outstanding fees
        outstanding_penalties (Decimal): Outstanding penalties
        outstanding_interest (Decimal): Outstanding interest
        outstanding_principal (Decimal): Outstanding principal
    
    Returns:
        dict: Allocation breakdown
            {
                'fee_amount': Decimal,
                'penalty_amount': Decimal,
                'interest_amount': Decimal,
                'principal_amount': Decimal,
                'excess_amount': Decimal  # If payment > total outstanding
            }
    
    Example:
        >>> allocate_payment(
        ...     Decimal('10000'),
        ...     Decimal('100'), Decimal('200'),
        ...     Decimal('500'), Decimal('9000')
        ... )
        {'fee_amount': Decimal('100.00'), 'penalty_amount': Decimal('200.00'), ...}
    """
    try:
        amount = Decimal(str(payment_amount))
        remaining = amount
        
        allocation = {
            'fee_amount': Decimal('0.00'),
            'penalty_amount': Decimal('0.00'),
            'interest_amount': Decimal('0.00'),
            'principal_amount': Decimal('0.00'),
            'excess_amount': Decimal('0.00')
        }
        
        # 1. Allocate to fees first
        if remaining > 0 and outstanding_fees > 0:
            fee_payment = min(remaining, Decimal(str(outstanding_fees)))
            allocation['fee_amount'] = fee_payment
            remaining -= fee_payment
        
        # 2. Allocate to penalties
        if remaining > 0 and outstanding_penalties > 0:
            penalty_payment = min(remaining, Decimal(str(outstanding_penalties)))
            allocation['penalty_amount'] = penalty_payment
            remaining -= penalty_payment
        
        # 3. Allocate to interest
        if remaining > 0 and outstanding_interest > 0:
            interest_payment = min(remaining, Decimal(str(outstanding_interest)))
            allocation['interest_amount'] = interest_payment
            remaining -= interest_payment
        
        # 4. Allocate to principal
        if remaining > 0 and outstanding_principal > 0:
            principal_payment = min(remaining, Decimal(str(outstanding_principal)))
            allocation['principal_amount'] = principal_payment
            remaining -= principal_payment
        
        # 5. Any excess
        if remaining > 0:
            allocation['excess_amount'] = remaining
        
        # Round all values
        for key in allocation:
            allocation[key] = allocation[key].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        return allocation
        
    except Exception as e:
        logger.error(f"Error allocating payment: {e}")
        return {
            'fee_amount': Decimal('0.00'),
            'penalty_amount': Decimal('0.00'),
            'interest_amount': Decimal('0.00'),
            'principal_amount': Decimal('0.00'),
            'excess_amount': Decimal('0.00')
        }


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_loan_amount(amount, loan_product):
    """
    Validate loan amount against product limits.
    
    Args:
        amount (Decimal): Requested loan amount
        loan_product: LoanProduct instance
    
    Returns:
        tuple: (is_valid: bool, message: str)
    
    Example:
        >>> validate_loan_amount(Decimal('50000'), product)
        (True, 'Amount is valid')
    """
    try:
        amt = Decimal(str(amount))
    except (ValueError, TypeError):
        return False, "Invalid loan amount"
    
    if amt < loan_product.min_amount:
        from core.utils import format_money
        return False, f"Amount below minimum of {format_money(loan_product.min_amount)}"
    
    if amt > loan_product.max_amount:
        from core.utils import format_money
        return False, f"Amount exceeds maximum of {format_money(loan_product.max_amount)}"
    
    return True, "Amount is valid"


def validate_loan_term(term_months, loan_product):
    """
    Validate loan term against product limits.
    
    Args:
        term_months (int): Requested term in months
        loan_product: LoanProduct instance
    
    Returns:
        tuple: (is_valid: bool, message: str)
    """
    try:
        term = int(term_months)
    except (ValueError, TypeError):
        return False, "Invalid loan term"
    
    if term < loan_product.min_term:
        return False, f"Term below minimum of {loan_product.min_term} months"
    
    if term > loan_product.max_term:
        return False, f"Term exceeds maximum of {loan_product.max_term} months"
    
    return True, "Term is valid"


def validate_member_loan_eligibility(member, loan_product):
    """
    Validate member eligibility for loan.
    
    Checks:
    - Member status (must be ACTIVE)
    - Savings requirements
    - Share requirements
    - Existing loan count
    
    Args:
        member: Member instance
        loan_product: LoanProduct instance
    
    Returns:
        tuple: (is_eligible: bool, message: str)
    """
    # Check member status
    if hasattr(member, 'status') and member.status != 'ACTIVE':
        return False, "Member must be active to apply for loans"
    
    # Check existing loans
    from loans.models import Loan
    active_loans = Loan.objects.filter(
        member=member,
        loan_product=loan_product,
        status='ACTIVE'
    ).count()
    
    if active_loans >= loan_product.maximum_loans_per_member:
        return False, f"Member already has maximum allowed loans ({loan_product.maximum_loans_per_member}) for this product"
    
    # Check savings requirement
    if loan_product.minimum_savings_percentage > 0:
        # This would need to check member's savings
        # Placeholder for now
        pass
    
    # Check shares requirement
    if loan_product.minimum_shares_required > 0:
        # This would need to check member's shares
        # Placeholder for now
        pass
    
    return True, "Member is eligible"


def can_approve_loan_application(application):
    """
    Check if loan application can be approved.
    
    Args:
        application: LoanApplication instance
    
    Returns:
        tuple: (can_approve: bool, message: str)
    """
    if application.status not in ['SUBMITTED', 'UNDER_REVIEW']:
        return False, f"Cannot approve application with status: {application.get_status_display()}"
    
    # Check guarantors if required
    if application.loan_product.guarantor_required:
        approved_guarantors = application.guarantors.filter(status='APPROVED').count()
        required_guarantors = application.loan_product.number_of_guarantors
        
        if approved_guarantors < required_guarantors:
            return False, f"Insufficient guarantors ({approved_guarantors}/{required_guarantors} approved)"
    
    # Check collateral if required
    if application.loan_product.collateral_required:
        verified_collateral = application.collaterals.filter(is_verified=True).exists()
        
        if not verified_collateral:
            return False, "No verified collateral found"
    
    # Check processing fee if required
    if application.processing_fee_amount > 0 and not application.processing_fee_paid:
        return False, "Processing fee not paid"
    
    return True, "Application can be approved"


def can_disburse_loan(loan):
    """
    Check if loan can be disbursed.
    
    Args:
        loan: Loan instance
    
    Returns:
        tuple: (can_disburse: bool, message: str)
    """
    # Check if loan has application
    if hasattr(loan, 'application'):
        if loan.application and loan.application.status != 'APPROVED':
            return False, "Loan application is not approved"
    
    # Check loan status
    if loan.status != 'ACTIVE':
        return False, f"Cannot disburse loan with status: {loan.get_status_display()}"
    
    # Check if already disbursed
    if loan.disbursement_date and loan.disbursement_date <= timezone.now().date():
        return False, "Loan has already been disbursed"
    
    return True, "Loan can be disbursed"


# =============================================================================
# CALCULATION HELPERS
# =============================================================================

def calculate_total_repayment(principal, rate, term_months, interest_type='REDUCING_BALANCE'):
    """
    Calculate total amount to be repaid (principal + interest).
    
    Args:
        principal (Decimal): Loan principal
        rate (Decimal): Annual interest rate
        term_months (int): Loan term in months
        interest_type (str): Interest calculation method
    
    Returns:
        Decimal: Total repayment amount
    """
    if interest_type == 'FLAT':
        interest = calculate_flat_interest(principal, rate, term_months)
    else:
        interest = calculate_reducing_balance_interest(principal, rate, term_months)
    
    total = Decimal(str(principal)) + interest
    return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_loan_affordability(monthly_income, existing_loan_payments, requested_emi):
    """
    Calculate debt-to-income ratio and affordability.
    
    Args:
        monthly_income (Decimal): Member's monthly income
        existing_loan_payments (Decimal): Current monthly loan obligations
        requested_emi (Decimal): Requested EMI for new loan
    
    Returns:
        dict: Affordability analysis
            {
                'dti_ratio': Decimal,  # Debt-to-income ratio (%)
                'is_affordable': bool,
                'disposable_income': Decimal,
                'message': str
            }
    """
    try:
        income = Decimal(str(monthly_income))
        existing = Decimal(str(existing_loan_payments))
        new_emi = Decimal(str(requested_emi))
        
        # Calculate total monthly debt
        total_debt = existing + new_emi
        
        # Calculate DTI ratio
        if income > 0:
            dti_ratio = (total_debt / income) * Decimal('100')
        else:
            dti_ratio = Decimal('100')
        
        # Calculate disposable income
        disposable = income - total_debt
        
        # Standard threshold is 40% DTI
        is_affordable = dti_ratio <= Decimal('40')
        
        if is_affordable:
            message = f"Loan is affordable. DTI ratio: {dti_ratio:.2f}%"
        else:
            message = f"Loan may not be affordable. DTI ratio: {dti_ratio:.2f}% exceeds 40%"
        
        return {
            'dti_ratio': dti_ratio.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'is_affordable': is_affordable,
            'disposable_income': disposable.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'message': message
        }
        
    except Exception as e:
        logger.error(f"Error calculating loan affordability: {e}")
        return {
            'dti_ratio': Decimal('0.00'),
            'is_affordable': False,
            'disposable_income': Decimal('0.00'),
            'message': 'Error calculating affordability'
        }


def get_payment_frequency_count(payment_frequency, term_months):
    """
    Get number of payments for given frequency and term.
    
    Args:
        payment_frequency (str): Payment frequency
        term_months (int): Loan term in months
    
    Returns:
        int: Number of payments
    """
    if payment_frequency == 'DAILY':
        return term_months * 30  # Approximate
    elif payment_frequency == 'WEEKLY':
        return term_months * 4
    elif payment_frequency == 'BI_WEEKLY':
        return term_months * 2
    elif payment_frequency == 'MONTHLY':
        return term_months
    elif payment_frequency == 'QUARTERLY':
        return max(1, term_months // 3)
    elif payment_frequency == 'ANNUALLY':
        return max(1, term_months // 12)
    else:
        return term_months  # Default to monthly


# =============================================================================
# DATE UTILITIES
# =============================================================================

def calculate_days_between(start_date, end_date):
    """
    Calculate number of days between two dates.
    
    Args:
        start_date (date): Start date
        end_date (date): End date
    
    Returns:
        int: Number of days
    """
    try:
        return (end_date - start_date).days
    except (TypeError, AttributeError):
        return 0


def is_loan_overdue(next_payment_date):
    """
    Check if loan payment is overdue.
    
    Args:
        next_payment_date (date): Next payment due date
    
    Returns:
        tuple: (is_overdue: bool, days_overdue: int)
    """
    if not next_payment_date:
        return False, 0
    
    today = timezone.now().date()
    
    if next_payment_date < today:
        days_overdue = (today - next_payment_date).days
        return True, days_overdue
    
    return False, 0


def get_loan_age(disbursement_date):
    """
    Calculate loan age in various formats.
    
    Args:
        disbursement_date (date): Loan disbursement date
    
    Returns:
        dict: Age information
            {
                'days': int,
                'months': int,
                'years': int,
                'readable': str
            }
    """
    today = timezone.now().date()
    delta = today - disbursement_date
    
    days = delta.days
    years = days // 365
    months = (days % 365) // 30
    
    if years > 0:
        readable = f"{years} year(s) {months} month(s)"
    elif months > 0:
        readable = f"{months} month(s)"
    else:
        readable = f"{days} day(s)"
    
    return {
        'days': days,
        'months': days // 30,
        'years': years,
        'readable': readable
    }


