# members/utils.py

"""
Members Utility Functions

Pure utility functions with NO side effects (no database writes):
- Member number generation logic
- Credit score calculations
- Risk rating calculations
- Eligibility validations
- Financial calculations
- Age and date utilities
- Helper functions for common operations

All functions are pure - they calculate and return values without modifying the database.
Database writes are handled by signals.py and services.py.
"""

from django.db import transaction
from django.db.models import Sum, Avg, Count
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# MEMBER NUMBER GENERATION
# =============================================================================

def generate_member_number(prefix='MBR', width=4):
    """
    Generate sequential member number.

    Format: PREFIX + zero-padded number
    Example:
        MBR0001
        MBR0002
    """
    from members.models import Member

    with transaction.atomic():
        # Lock the table rows to prevent race conditions
        last_member = (
            Member.objects
            .select_for_update()
            .filter(member_number__startswith=prefix)
            .order_by('-member_number')
            .first()
        )

        if last_member:
            last_number = int(last_member.member_number.replace(prefix, ''))
            next_number = last_number + 1
        else:
            next_number = 1

        member_number = f"{prefix}{str(next_number).zfill(width)}"

        logger.info(f"Generated member number: {member_number}")
        return member_number


# =============================================================================
# CREDIT SCORE CALCULATIONS
# =============================================================================

def calculate_credit_score(member_data):
    """
    Calculate credit score based on member data.
    
    Args:
        member_data (dict): Dictionary with member information
            {
                'age': int,
                'employment_status': str,
                'monthly_income': Decimal,
                'membership_years': float,
                'kyc_verified': bool,
                'savings_balance': Decimal,
                'loans_count': int,
                'loan_defaults': int,
                'payment_history_score': int (0-100)
            }
    
    Returns:
        int: Credit score (0-1000)
    
    Example:
        >>> calculate_credit_score({
        ...     'age': 35,
        ...     'employment_status': 'EMPLOYED',
        ...     'monthly_income': Decimal('1000000'),
        ...     'membership_years': 3.5,
        ...     'kyc_verified': True,
        ...     'savings_balance': Decimal('5000000'),
        ...     'loans_count': 2,
        ...     'loan_defaults': 0,
        ...     'payment_history_score': 85
        ... })
        750
    """
    base_score = 500
    
    # Age-based scoring (max 50 points)
    age = member_data.get('age', 0)
    if 25 <= age <= 55:
        base_score += 50
    elif 18 <= age < 25:
        base_score += 30
    elif 55 < age <= 65:
        base_score += 40
    
    # Employment status (max 75 points)
    employment = member_data.get('employment_status', '')
    if employment == 'EMPLOYED':
        base_score += 75
    elif employment == 'SELF_EMPLOYED':
        base_score += 50
    elif employment == 'RETIRED':
        base_score += 40
    elif employment == 'STUDENT':
        base_score += 20
    
    # Income level (max 100 points)
    income = member_data.get('monthly_income', Decimal('0'))
    if income >= 2000000:  # 2M UGX
        base_score += 100
    elif income >= 1000000:  # 1M UGX
        base_score += 75
    elif income >= 500000:  # 500K UGX
        base_score += 50
    elif income >= 200000:  # 200K UGX
        base_score += 25
    
    # Membership duration (max 75 points)
    years = member_data.get('membership_years', 0)
    if years >= 5:
        base_score += 75
    elif years >= 3:
        base_score += 60
    elif years >= 2:
        base_score += 50
    elif years >= 1:
        base_score += 25
    
    # KYC verification (50 points)
    if member_data.get('kyc_verified', False):
        base_score += 50
    
    # Savings balance (max 100 points)
    savings = member_data.get('savings_balance', Decimal('0'))
    if savings >= 10000000:  # 10M UGX
        base_score += 100
    elif savings >= 5000000:  # 5M UGX
        base_score += 75
    elif savings >= 2000000:  # 2M UGX
        base_score += 50
    elif savings >= 1000000:  # 1M UGX
        base_score += 25
    
    # Loan history (max 100 points)
    loans_count = member_data.get('loans_count', 0)
    loan_defaults = member_data.get('loan_defaults', 0)
    
    if loans_count > 0:
        if loan_defaults == 0:
            base_score += 100
        elif loan_defaults == 1:
            base_score += 50
        elif loan_defaults == 2:
            base_score += 25
        else:
            base_score -= 50
    
    # Payment history (max 50 points)
    payment_score = member_data.get('payment_history_score', 0)
    if payment_score >= 90:
        base_score += 50
    elif payment_score >= 80:
        base_score += 40
    elif payment_score >= 70:
        base_score += 30
    elif payment_score >= 60:
        base_score += 20
    
    # Ensure score is within valid range
    credit_score = max(0, min(1000, base_score))
    
    return credit_score


def calculate_simple_credit_score(age, employment_status, monthly_income):
    """
    Calculate simple credit score for new members.
    
    Args:
        age (int): Member age
        employment_status (str): Employment status
        monthly_income (Decimal): Monthly income
    
    Returns:
        int: Credit score (0-1000)
    """
    base_score = 500
    
    # Age-based scoring
    if 25 <= age <= 55:
        base_score += 50
    elif 18 <= age < 25:
        base_score += 30
    
    # Employment status
    if employment_status == 'EMPLOYED':
        base_score += 75
    elif employment_status == 'SELF_EMPLOYED':
        base_score += 50
    
    # Income level
    if monthly_income:
        if monthly_income >= 1000000:
            base_score += 100
        elif monthly_income >= 500000:
            base_score += 75
        elif monthly_income >= 200000:
            base_score += 50
    
    return max(0, min(1000, base_score))


# =============================================================================
# RISK RATING CALCULATIONS
# =============================================================================

def calculate_risk_rating(credit_score):
    """
    Calculate risk rating based on credit score.
    
    Args:
        credit_score (int): Credit score (0-1000)
    
    Returns:
        str: Risk rating
            - VERY_LOW: 800+
            - LOW: 650-799
            - MEDIUM: 500-649
            - HIGH: 350-499
            - VERY_HIGH: 0-349
    
    Example:
        >>> calculate_risk_rating(750)
        'LOW'
    """
    if credit_score >= 800:
        return 'VERY_LOW'
    elif credit_score >= 650:
        return 'LOW'
    elif credit_score >= 500:
        return 'MEDIUM'
    elif credit_score >= 350:
        return 'HIGH'
    else:
        return 'VERY_HIGH'


# =============================================================================
# AGE AND DATE CALCULATIONS
# =============================================================================

def calculate_age(date_of_birth):
    """
    Calculate age from date of birth.
    
    Args:
        date_of_birth (date): Date of birth
    
    Returns:
        int: Age in years
    
    Example:
        >>> calculate_age(date(1990, 1, 15))
        35
    """
    today = date.today()
    age = today.year - date_of_birth.year
    
    # Adjust if birthday hasn't occurred this year
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1
    
    return age


def calculate_membership_duration(membership_date):
    """
    Calculate membership duration.
    
    Args:
        membership_date (date): Membership start date
    
    Returns:
        dict: Duration breakdown
            {
                'days': int,
                'months': float,
                'years': float
            }
    
    Example:
        >>> calculate_membership_duration(date(2020, 1, 1))
        {'days': 1855, 'months': 61.0, 'years': 5.08}
    """
    today = timezone.now().date()
    days = (today - membership_date).days
    months = days / 30.44
    years = days / 365.25
    
    return {
        'days': days,
        'months': round(months, 2),
        'years': round(years, 2)
    }


def is_kyc_expired(kyc_expiry_date):
    """
    Check if KYC has expired.
    
    Args:
        kyc_expiry_date (datetime): KYC expiry date
    
    Returns:
        tuple: (is_expired: bool, days_remaining: int)
    """
    if not kyc_expiry_date:
        return False, None
    
    now = timezone.now()
    
    if kyc_expiry_date < now:
        days_expired = (now - kyc_expiry_date).days
        return True, -days_expired
    else:
        days_remaining = (kyc_expiry_date - now).days
        return False, days_remaining


# =============================================================================
# ELIGIBILITY VALIDATIONS
# =============================================================================

def validate_minimum_age(date_of_birth, minimum_age=16):
    """
    Validate if member meets minimum age requirement.
    
    Args:
        date_of_birth (date): Date of birth
        minimum_age (int): Minimum age requirement
    
    Returns:
        tuple: (is_valid: bool, message: str, age: int)
    """
    age = calculate_age(date_of_birth)
    
    if age < minimum_age:
        return False, f"Member must be at least {minimum_age} years old", age
    
    return True, f"Age requirement met ({age} years)", age


def validate_loan_eligibility(member_data, loan_amount):
    """
    Validate if member is eligible for loan.
    
    Args:
        member_data (dict): Member information
            {
                'status': str,
                'total_savings': Decimal,
                'total_shares': Decimal,
                'active_loans_count': int,
                'credit_score': int,
                'kyc_verified': bool,
                'maximum_loan_multiplier': Decimal
            }
        loan_amount (Decimal): Requested loan amount
    
    Returns:
        tuple: (is_eligible: bool, message: str, max_eligible_amount: Decimal)
    """
    # Check member status
    if member_data.get('status') != 'ACTIVE':
        return False, "Member must be active to apply for loans", Decimal('0.00')
    
    # Check KYC verification
    if not member_data.get('kyc_verified', False):
        return False, "KYC verification required to apply for loans", Decimal('0.00')
    
    # Check credit score
    credit_score = member_data.get('credit_score', 0)
    if credit_score < 350:
        return False, f"Credit score too low ({credit_score})", Decimal('0.00')
    
    # Calculate maximum eligible loan
    total_savings = member_data.get('total_savings', Decimal('0'))
    total_shares = member_data.get('total_shares', Decimal('0'))
    multiplier = member_data.get('maximum_loan_multiplier', Decimal('3.0'))
    
    max_eligible = (total_savings + total_shares) * multiplier
    
    if loan_amount > max_eligible:
        return False, f"Loan amount exceeds maximum eligible: {max_eligible}", max_eligible
    
    return True, "Eligible for loan", max_eligible


def validate_savings_withdrawal(current_balance, withdrawal_amount, minimum_balance=Decimal('0')):
    """
    Validate savings withdrawal.
    
    Args:
        current_balance (Decimal): Current account balance
        withdrawal_amount (Decimal): Withdrawal amount
        minimum_balance (Decimal): Minimum required balance
    
    Returns:
        tuple: (is_valid: bool, message: str, remaining_balance: Decimal)
    """
    if withdrawal_amount <= 0:
        return False, "Withdrawal amount must be greater than zero", current_balance
    
    if withdrawal_amount > current_balance:
        return False, f"Insufficient balance. Available: {current_balance}", current_balance
    
    remaining = current_balance - withdrawal_amount
    
    if remaining < minimum_balance:
        return False, f"Withdrawal would leave balance below minimum ({minimum_balance})", current_balance
    
    return True, "Withdrawal is valid", remaining


# =============================================================================
# FINANCIAL CALCULATIONS
# =============================================================================

def calculate_debt_to_income_ratio(total_loan_payments, monthly_income):
    """
    Calculate debt-to-income ratio.
    
    Args:
        total_loan_payments (Decimal): Total monthly loan payments
        monthly_income (Decimal): Monthly income
    
    Returns:
        Decimal: DTI ratio as percentage
    
    Example:
        >>> calculate_debt_to_income_ratio(Decimal('200000'), Decimal('1000000'))
        Decimal('20.00')
    """
    if not monthly_income or monthly_income <= 0:
        return Decimal('0.00')
    
    dti = (total_loan_payments / monthly_income) * Decimal('100')
    return dti.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_maximum_loan_amount(total_savings, total_shares, multiplier):
    """
    Calculate maximum loan amount based on savings and shares.
    
    Formula: Max Loan = (Savings + Shares) × Multiplier
    
    Args:
        total_savings (Decimal): Total savings balance
        total_shares (Decimal): Total share value
        multiplier (Decimal): Loan multiplier
    
    Returns:
        Decimal: Maximum loan amount
    
    Example:
        >>> calculate_maximum_loan_amount(
        ...     Decimal('1000000'), Decimal('500000'), Decimal('3.0')
        ... )
        Decimal('4500000.00')
    """
    max_loan = (total_savings + total_shares) * multiplier
    return max_loan.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_net_worth(savings, shares, loans):
    """
    Calculate member's net worth.
    
    Formula: Net Worth = (Savings + Shares) - Outstanding Loans
    
    Args:
        savings (Decimal): Total savings
        shares (Decimal): Total share value
        loans (Decimal): Outstanding loans
    
    Returns:
        Decimal: Net worth
    """
    net_worth = (savings + shares) - loans
    return net_worth.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# =============================================================================
# GROUP VALIDATIONS
# =============================================================================

def validate_group_membership(member_data, group_data):
    """
    Validate if member can join a group.
    
    Args:
        member_data (dict): Member information
            {
                'status': str,
                'active_groups_count': int
            }
        group_data (dict): Group information
            {
                'is_active': bool,
                'is_full': bool,
                'current_members': int,
                'maximum_members': int
            }
    
    Returns:
        tuple: (can_join: bool, message: str)
    """
    # Check member status
    if member_data.get('status') != 'ACTIVE':
        return False, "Member must be active to join groups"
    
    # Check group status
    if not group_data.get('is_active', False):
        return False, "Group is not active"
    
    # Check if group is full
    if group_data.get('is_full', False):
        return False, "Group is full"
    
    current = group_data.get('current_members', 0)
    maximum = group_data.get('maximum_members', 0)
    
    if current >= maximum:
        return False, f"Group has reached maximum capacity ({maximum})"
    
    return True, "Member can join group"


def calculate_group_contribution_total(monthly_contribution, months):
    """
    Calculate total contribution for a period.
    
    Args:
        monthly_contribution (Decimal): Monthly contribution amount
        months (int): Number of months
    
    Returns:
        Decimal: Total contribution
    """
    total = monthly_contribution * Decimal(str(months))
    return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def mask_id_number(id_number):
    """
    Mask ID number for display.
    
    Args:
        id_number (str): Full ID number
    
    Returns:
        str: Masked ID number
    
    Example:
        >>> mask_id_number('CM12345678901234')
        '************1234'
    """
    if not id_number or len(id_number) < 4:
        return "****"
    
    return f"{'*' * (len(id_number) - 4)}{id_number[-4:]}"


def format_phone_number(phone_number, country_code='+256'):
    """
    Format phone number with country code.
    
    Args:
        phone_number (str): Phone number
        country_code (str): Country code
    
    Returns:
        str: Formatted phone number
    
    Example:
        >>> format_phone_number('0700123456')
        '+256700123456'
    """
    # Remove spaces and hyphens
    cleaned = phone_number.replace(' ', '').replace('-', '')
    
    # Remove leading zero if present
    if cleaned.startswith('0'):
        cleaned = cleaned[1:]
    
    # Remove country code if already present
    if cleaned.startswith('+'):
        return cleaned
    
    if cleaned.startswith(country_code.replace('+', '')):
        return f"+{cleaned}"
    
    return f"{country_code}{cleaned}"


def generate_member_statement_summary(member_data):
    """
    Generate member account summary.
    
    Args:
        member_data (dict): Member financial data
            {
                'total_savings': Decimal,
                'total_shares': Decimal,
                'total_loans': Decimal,
                'total_dividends': Decimal,
                'active_loans_count': int,
                'membership_years': float
            }
    
    Returns:
        dict: Summary information
    """
    from core.utils import format_money
    
    total_savings = member_data.get('total_savings', Decimal('0'))
    total_shares = member_data.get('total_shares', Decimal('0'))
    total_loans = member_data.get('total_loans', Decimal('0'))
    total_dividends = member_data.get('total_dividends', Decimal('0'))
    
    net_worth = calculate_net_worth(total_savings, total_shares, total_loans)
    
    return {
        'total_savings': format_money(total_savings),
        'total_shares': format_money(total_shares),
        'total_loans': format_money(total_loans),
        'total_dividends': format_money(total_dividends),
        'net_worth': format_money(net_worth),
        'active_loans': member_data.get('active_loans_count', 0),
        'membership_years': round(member_data.get('membership_years', 0), 2)
    }


def calculate_member_statistics(members_queryset):
    """
    Calculate statistics for a group of members.
    
    Args:
        members_queryset: QuerySet of Member instances
    
    Returns:
        dict: Statistics
    """
    stats = members_queryset.aggregate(
        total_members=Count('id'),
        avg_age=Avg('date_of_birth'),
        avg_credit_score=Avg('credit_score')
    )
    
    # Count by status
    status_counts = {}
    for status, label in [
        ('ACTIVE', 'Active'),
        ('PENDING_APPROVAL', 'Pending'),
        ('DORMANT', 'Dormant'),
        ('SUSPENDED', 'Suspended')
    ]:
        status_counts[status] = members_queryset.filter(status=status).count()
    
    return {
        'total_members': stats['total_members'] or 0,
        'average_age': stats['avg_age'],
        'average_credit_score': round(stats['avg_credit_score'] or 0, 2),
        'status_breakdown': status_counts
    }

