# dividends/utils.py

"""
Dividends Utility Functions

Pure utility functions with NO side effects (no database writes):
- Dividend calculation methods (flat rate, weighted average, tiered, pro-rata)
- Tax calculations
- Share value calculations
- Distribution validations
- Date utilities
- Helper functions for common operations

All functions are pure - they calculate and return values without modifying the database.
Database writes are handled by signals.py and services.py.
"""

from django.db import transaction
from django.db.models import Max, Sum
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from datetime import timedelta, date
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# DIVIDEND CALCULATION METHODS
# =============================================================================

def calculate_flat_rate_dividend(shares_value, dividend_rate):
    """
    Calculate dividend using flat rate method.
    
    Formula: Dividend = (Shares Value × Rate) / 100
    
    Args:
        shares_value (Decimal): Total value of member's shares
        dividend_rate (Decimal): Dividend rate percentage
    
    Returns:
        Decimal: Gross dividend amount
    
    Example:
        >>> calculate_flat_rate_dividend(Decimal('100000'), Decimal('5'))
        Decimal('5000.00')
    """
    try:
        value = Decimal(str(shares_value))
        rate = Decimal(str(dividend_rate)) / Decimal('100')
        
        if value < 0 or rate < 0:
            logger.warning("Negative values in flat rate dividend calculation")
            return Decimal('0.00')
        
        dividend = value * rate
        
        return dividend.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.error(f"Error calculating flat rate dividend: {e}")
        return Decimal('0.00')


def calculate_weighted_average_dividend(shares_value, total_shares_value, 
                                       total_dividend_pool):
    """
    Calculate dividend using weighted average method.
    
    Each member gets dividend proportional to their share of total shares.
    Formula: Dividend = (Member Shares Value / Total Shares Value) × Total Pool
    
    Args:
        shares_value (Decimal): Member's shares value
        total_shares_value (Decimal): Total value of all shares
        total_dividend_pool (Decimal): Total dividend pool to distribute
    
    Returns:
        Decimal: Gross dividend amount
    
    Example:
        >>> calculate_weighted_average_dividend(
        ...     Decimal('50000'), Decimal('1000000'), Decimal('100000')
        ... )
        Decimal('5000.00')
    """
    try:
        member_value = Decimal(str(shares_value))
        total_value = Decimal(str(total_shares_value))
        pool = Decimal(str(total_dividend_pool))
        
        if total_value <= 0:
            logger.warning("Total shares value is zero or negative")
            return Decimal('0.00')
        
        if member_value < 0 or pool < 0:
            logger.warning("Negative values in weighted average calculation")
            return Decimal('0.00')
        
        # Calculate member's proportion
        proportion = member_value / total_value
        
        # Calculate dividend
        dividend = proportion * pool
        
        return dividend.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.error(f"Error calculating weighted average dividend: {e}")
        return Decimal('0.00')


def calculate_tiered_dividend(shares_value, shares_count, dividend_rates):
    """
    Calculate dividend using tiered rates.
    
    Different rates apply based on share count or value tiers.
    
    Args:
        shares_value (Decimal): Member's shares value
        shares_count (int): Member's share count
        dividend_rates (list): List of tier dictionaries with structure:
            [
                {
                    'min_shares': int,
                    'max_shares': int or None,
                    'min_value': Decimal or None,
                    'max_value': Decimal or None,
                    'rate': Decimal
                },
                ...
            ]
    
    Returns:
        tuple: (dividend_amount: Decimal, applied_rate: Decimal)
    
    Example:
        >>> tiers = [
        ...     {'min_shares': 0, 'max_shares': 100, 'rate': Decimal('3')},
        ...     {'min_shares': 101, 'max_shares': None, 'rate': Decimal('5')}
        ... ]
        >>> calculate_tiered_dividend(Decimal('150000'), 150, tiers)
        (Decimal('7500.00'), Decimal('5.00'))
    """
    try:
        value = Decimal(str(shares_value))
        count = int(shares_count)
        
        if not dividend_rates:
            logger.warning("No dividend rates provided for tiered calculation")
            return Decimal('0.00'), Decimal('0.00')
        
        # Find applicable tier
        applicable_rate = None
        
        for tier in sorted(dividend_rates, key=lambda x: x.get('min_shares', 0)):
            # Check share count criteria
            if 'min_shares' in tier and 'max_shares' in tier:
                min_shares = tier['min_shares']
                max_shares = tier['max_shares']
                
                if max_shares is None:
                    # No upper limit
                    if count >= min_shares:
                        applicable_rate = Decimal(str(tier['rate']))
                        break
                else:
                    # Has upper limit
                    if min_shares <= count <= max_shares:
                        applicable_rate = Decimal(str(tier['rate']))
                        break
            
            # Check value criteria
            elif 'min_value' in tier and tier['min_value'] is not None:
                min_value = Decimal(str(tier['min_value']))
                max_value = Decimal(str(tier['max_value'])) if tier.get('max_value') else None
                
                if max_value is None:
                    # No upper limit
                    if value >= min_value:
                        applicable_rate = Decimal(str(tier['rate']))
                        break
                else:
                    # Has upper limit
                    if min_value <= value <= max_value:
                        applicable_rate = Decimal(str(tier['rate']))
                        break
        
        if applicable_rate is None:
            logger.warning(f"No applicable tier found for shares: {count}, value: {value}")
            return Decimal('0.00'), Decimal('0.00')
        
        # Calculate dividend
        dividend = calculate_flat_rate_dividend(value, applicable_rate)
        
        return dividend, applicable_rate
        
    except Exception as e:
        logger.error(f"Error calculating tiered dividend: {e}")
        return Decimal('0.00'), Decimal('0.00')


def calculate_pro_rata_dividend(shares_value, total_shares_value, 
                                total_dividend_pool, minimum_payout=None):
    """
    Calculate pro-rata dividend distribution.
    
    Similar to weighted average but with minimum payout threshold.
    
    Args:
        shares_value (Decimal): Member's shares value
        total_shares_value (Decimal): Total value of all shares
        total_dividend_pool (Decimal): Total dividend pool
        minimum_payout (Decimal, optional): Minimum payout threshold
    
    Returns:
        tuple: (dividend_amount: Decimal, meets_minimum: bool)
    
    Example:
        >>> calculate_pro_rata_dividend(
        ...     Decimal('10000'), Decimal('1000000'), 
        ...     Decimal('100000'), Decimal('500')
        ... )
        (Decimal('1000.00'), True)
    """
    try:
        # Calculate weighted average
        dividend = calculate_weighted_average_dividend(
            shares_value, 
            total_shares_value, 
            total_dividend_pool
        )
        
        # Check minimum payout
        meets_minimum = True
        if minimum_payout:
            min_payout = Decimal(str(minimum_payout))
            meets_minimum = dividend >= min_payout
        
        return dividend, meets_minimum
        
    except Exception as e:
        logger.error(f"Error calculating pro-rata dividend: {e}")
        return Decimal('0.00'), False


# =============================================================================
# TAX CALCULATIONS
# =============================================================================

def calculate_withholding_tax(gross_dividend, tax_rate):
    """
    Calculate withholding tax on dividend.
    
    Formula: Tax = (Gross Dividend × Tax Rate) / 100
    
    Args:
        gross_dividend (Decimal): Gross dividend amount
        tax_rate (Decimal): Tax rate percentage
    
    Returns:
        Decimal: Tax amount
    
    Example:
        >>> calculate_withholding_tax(Decimal('10000'), Decimal('15'))
        Decimal('1500.00')
    """
    try:
        gross = Decimal(str(gross_dividend))
        rate = Decimal(str(tax_rate)) / Decimal('100')
        
        if gross < 0 or rate < 0:
            logger.warning("Negative values in tax calculation")
            return Decimal('0.00')
        
        tax = gross * rate
        
        return tax.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.error(f"Error calculating withholding tax: {e}")
        return Decimal('0.00')


def calculate_net_dividend(gross_dividend, tax_amount):
    """
    Calculate net dividend after tax.
    
    Formula: Net = Gross - Tax
    
    Args:
        gross_dividend (Decimal): Gross dividend
        tax_amount (Decimal): Tax amount
    
    Returns:
        Decimal: Net dividend
    
    Example:
        >>> calculate_net_dividend(Decimal('10000'), Decimal('1500'))
        Decimal('8500.00')
    """
    try:
        gross = Decimal(str(gross_dividend))
        tax = Decimal(str(tax_amount))
        
        net = gross - tax
        
        # Ensure not negative
        if net < 0:
            logger.warning("Net dividend is negative, returning zero")
            return Decimal('0.00')
        
        return net.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating net dividend: {e}")
        return Decimal('0.00')


# =============================================================================
# SHARE VALUE CALCULATIONS
# =============================================================================

def calculate_total_shares_value(share_count, share_price):
    """
    Calculate total value of shares.
    
    Formula: Total Value = Share Count × Share Price
    
    Args:
        share_count (int): Number of shares
        share_price (Decimal): Price per share
    
    Returns:
        Decimal: Total shares value
    
    Example:
        >>> calculate_total_shares_value(100, Decimal('1000'))
        Decimal('100000.00')
    """
    try:
        count = int(share_count)
        price = Decimal(str(share_price))
        
        if count < 0 or price < 0:
            logger.warning("Negative values in shares value calculation")
            return Decimal('0.00')
        
        total = Decimal(str(count)) * price
        
        return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating shares value: {e}")
        return Decimal('0.00')


def calculate_dividend_yield(dividend_amount, shares_value):
    """
    Calculate dividend yield percentage.
    
    Formula: Yield = (Dividend / Shares Value) × 100
    
    Args:
        dividend_amount (Decimal): Dividend amount
        shares_value (Decimal): Total shares value
    
    Returns:
        Decimal: Dividend yield percentage
    
    Example:
        >>> calculate_dividend_yield(Decimal('5000'), Decimal('100000'))
        Decimal('5.00')
    """
    try:
        dividend = Decimal(str(dividend_amount))
        value = Decimal(str(shares_value))
        
        if value <= 0:
            logger.warning("Shares value is zero or negative")
            return Decimal('0.00')
        
        yield_pct = (dividend / value) * Decimal('100')
        
        return yield_pct.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.error(f"Error calculating dividend yield: {e}")
        return Decimal('0.00')


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_dividend_period_dates(start_date, end_date, record_date, 
                                   payment_date=None, declaration_date=None):
    """
    Validate dividend period dates.
    
    Args:
        start_date (date): Period start date
        end_date (date): Period end date
        record_date (date): Record date
        payment_date (date, optional): Payment date
        declaration_date (date, optional): Declaration date
    
    Returns:
        tuple: (is_valid: bool, errors: dict)
    
    Example:
        >>> validate_dividend_period_dates(
        ...     date(2024, 1, 1), date(2024, 12, 31),
        ...     date(2024, 12, 15), date(2025, 1, 15)
        ... )
        (True, {})
    """
    errors = {}
    
    # Start date must be before end date
    if start_date >= end_date:
        errors['end_date'] = 'End date must be after start date'
    
    # Record date must be within period
    if record_date < start_date:
        errors['record_date'] = 'Record date cannot be before start date'
    
    if record_date > end_date:
        errors['record_date'] = 'Record date cannot be after end date'
    
    # Payment date validations
    if payment_date:
        if declaration_date and payment_date < declaration_date:
            errors['payment_date'] = 'Payment date cannot be before declaration date'
        
        if payment_date < record_date:
            errors['payment_date'] = 'Payment date should not be before record date'
    
    is_valid = len(errors) == 0
    
    return is_valid, errors


def validate_total_dividend_allocation(member_dividends_total, period_total_amount):
    """
    Validate that total allocated dividends don't exceed available amount.
    
    Args:
        member_dividends_total (Decimal): Total of all member dividends
        period_total_amount (Decimal): Total dividend pool
    
    Returns:
        tuple: (is_valid: bool, difference: Decimal, message: str)
    
    Example:
        >>> validate_total_dividend_allocation(
        ...     Decimal('95000'), Decimal('100000')
        ... )
        (True, Decimal('5000.00'), 'Allocation is valid')
    """
    try:
        allocated = Decimal(str(member_dividends_total))
        available = Decimal(str(period_total_amount))
        
        difference = available - allocated
        
        if allocated > available:
            message = f"Over-allocated by {abs(difference)}"
            return False, difference, message
        
        if difference > Decimal('0.01'):
            message = f"Under-allocated by {difference}"
            return True, difference, message
        
        message = "Allocation is valid"
        return True, difference, message
        
    except Exception as e:
        logger.error(f"Error validating dividend allocation: {e}")
        return False, Decimal('0.00'), str(e)


def can_calculate_dividends(dividend_period):
    """
    Check if dividend period is ready for calculation.
    
    Args:
        dividend_period: DividendPeriod instance
    
    Returns:
        tuple: (can_calculate: bool, message: str)
    """
    if dividend_period.status not in ['DRAFT', 'OPEN']:
        return False, f"Cannot calculate dividends for period with status: {dividend_period.get_status_display()}"
    
    if dividend_period.total_dividend_amount <= 0:
        return False, "Total dividend amount must be greater than zero"
    
    if dividend_period.dividend_rate <= 0 and dividend_period.calculation_method == 'FLAT_RATE':
        return False, "Dividend rate must be greater than zero for flat rate calculation"
    
    # Check record date is in the past
    if dividend_period.record_date > timezone.now().date():
        return False, "Cannot calculate dividends before record date"
    
    return True, "Period is ready for calculation"


def can_approve_dividend_period(dividend_period):
    """
    Check if dividend period can be approved.
    
    Args:
        dividend_period: DividendPeriod instance
    
    Returns:
        tuple: (can_approve: bool, message: str)
    """
    if dividend_period.status != 'CALCULATED':
        return False, "Only calculated dividend periods can be approved"
    
    if dividend_period.is_approved:
        return False, "Dividend period is already approved"
    
    # Check that member dividends exist
    if not dividend_period.member_dividends.exists():
        return False, "No member dividends found for this period"
    
    return True, "Period can be approved"


def can_disburse_dividends(dividend_period):
    """
    Check if dividends can be disbursed.
    
    Args:
        dividend_period: DividendPeriod instance
    
    Returns:
        tuple: (can_disburse: bool, message: str)
    """
    if dividend_period.status != 'APPROVED':
        return False, "Only approved dividend periods can be disbursed"
    
    if not dividend_period.payment_date:
        return False, "Payment date must be set before disbursement"
    
    # Check that approved member dividends exist
    approved_count = dividend_period.member_dividends.filter(
        status='APPROVED'
    ).count()
    
    if approved_count == 0:
        return False, "No approved member dividends found"
    
    return True, "Dividends can be disbursed"


# =============================================================================
# BATCH NUMBER GENERATION
# =============================================================================

def generate_disbursement_batch_number():
    """
    Generate unique disbursement batch number.
    
    Format: DIV-YYYYMMDD-XXXXXX (random 6 digits)
    
    Returns:
        str: Unique batch number
    
    Example:
        >>> generate_disbursement_batch_number()
        'DIV-20250129-847291'
    """
    from dividends.models import DividendDisbursement
    import uuid
    
    date_str = timezone.now().strftime('%Y%m%d')
    
    with transaction.atomic():
        # Get existing batches for today
        existing_batches = DividendDisbursement.objects.filter(
            batch_number__startswith=f"DIV-{date_str}"
        ).select_for_update()
        
        # Generate unique suffix
        max_attempts = 10
        for _ in range(max_attempts):
            random_digits = str(uuid.uuid4().int)[:6]
            batch_number = f"DIV-{date_str}-{random_digits}"
            
            # Check if exists
            if not existing_batches.filter(batch_number=batch_number).exists():
                logger.info(f"Generated disbursement batch number: {batch_number}")
                return batch_number
        
        # Fallback: use timestamp
        timestamp = timezone.now().strftime('%H%M%S')
        batch_number = f"DIV-{date_str}-{timestamp}"
        logger.warning(f"Used fallback batch number: {batch_number}")
        return batch_number


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_eligible_members(dividend_period):
    """
    Get members eligible for dividends based on record date.
    
    Args:
        dividend_period: DividendPeriod instance
    
    Returns:
        list: List of dictionaries with member and share info
            [
                {
                    'member': Member instance,
                    'shares_count': int,
                    'shares_value': Decimal
                },
                ...
            ]
    """
    from members.models import Member
    from shares.models import ShareTransaction
    
    try:
        eligible_members = []
        
        # Get all active members
        members = Member.objects.filter(status='ACTIVE')
        
        for member in members:
            # Calculate shares as of record date
            shares_transactions = ShareTransaction.objects.filter(
                member=member,
                transaction_date__lte=dividend_period.record_date,
                is_reversed=False
            )
            
            # Calculate total shares
            shares_bought = shares_transactions.filter(
                transaction_type='BUY'
            ).aggregate(
                total=Sum('shares_count')
            )['total'] or 0
            
            shares_sold = shares_transactions.filter(
                transaction_type='SELL'
            ).aggregate(
                total=Sum('shares_count')
            )['total'] or 0
            
            net_shares = shares_bought - shares_sold
            
            if net_shares > 0:
                # Get share price (you may need to adjust this based on your setup)
                from shares.models import ShareCapital
                share_capital = ShareCapital.objects.filter(
                    is_active=True
                ).first()
                
                if share_capital:
                    shares_value = calculate_total_shares_value(
                        net_shares,
                        share_capital.share_price
                    )
                    
                    eligible_members.append({
                        'member': member,
                        'shares_count': net_shares,
                        'shares_value': shares_value
                    })
        
        logger.info(f"Found {len(eligible_members)} eligible members for dividend period {dividend_period.name}")
        
        return eligible_members
        
    except Exception as e:
        logger.error(f"Error getting eligible members: {e}")
        return []


def calculate_period_statistics(member_dividends):
    """
    Calculate statistics for dividend period from member dividends.
    
    Args:
        member_dividends: QuerySet of MemberDividend instances
    
    Returns:
        dict: Statistics
            {
                'total_members': int,
                'total_shares': int,
                'total_shares_value': Decimal,
                'total_gross_dividend': Decimal,
                'total_tax': Decimal,
                'total_net_dividend': Decimal,
                'average_dividend': Decimal
            }
    """
    try:
        from django.db.models import Sum, Avg, Count
        
        stats = member_dividends.aggregate(
            total_members=Count('id'),
            total_shares=Sum('shares_count'),
            total_shares_value=Sum('shares_value'),
            total_gross=Sum('gross_dividend'),
            total_tax=Sum('tax_amount'),
            total_net=Sum('net_dividend'),
            avg_dividend=Avg('net_dividend')
        )
        
        return {
            'total_members': stats['total_members'] or 0,
            'total_shares': stats['total_shares'] or 0,
            'total_shares_value': stats['total_shares_value'] or Decimal('0.00'),
            'total_gross_dividend': stats['total_gross'] or Decimal('0.00'),
            'total_tax': stats['total_tax'] or Decimal('0.00'),
            'total_net_dividend': stats['total_net'] or Decimal('0.00'),
            'average_dividend': stats['avg_dividend'] or Decimal('0.00')
        }
        
    except Exception as e:
        logger.error(f"Error calculating period statistics: {e}")
        return {
            'total_members': 0,
            'total_shares': 0,
            'total_shares_value': Decimal('0.00'),
            'total_gross_dividend': Decimal('0.00'),
            'total_tax': Decimal('0.00'),
            'total_net_dividend': Decimal('0.00'),
            'average_dividend': Decimal('0.00')
        }


def format_disbursement_summary(disbursement):
    """
    Format disbursement summary for display.
    
    Args:
        disbursement: DividendDisbursement instance
    
    Returns:
        dict: Formatted summary
    """
    from core.utils import format_money
    
    try:
        duration = None
        if disbursement.start_time and disbursement.end_time:
            duration = disbursement.end_time - disbursement.start_time
            duration_str = str(duration).split('.')[0]  # Remove microseconds
        else:
            duration_str = "In progress" if disbursement.start_time else "Not started"
        
        return {
            'batch_number': disbursement.batch_number,
            'status': disbursement.get_status_display(),
            'disbursement_date': disbursement.disbursement_date.strftime('%Y-%m-%d'),
            'method': disbursement.get_disbursement_method_display(),
            'total_members': disbursement.total_members,
            'processed_members': disbursement.processed_members,
            'successful_members': disbursement.successful_members,
            'failed_members': disbursement.failed_members,
            'total_amount': format_money(disbursement.total_amount),
            'processed_amount': format_money(disbursement.processed_amount),
            'completion_percentage': f"{disbursement.completion_percentage:.2f}%",
            'success_rate': f"{disbursement.success_rate:.2f}%",
            'duration': duration_str
        }
        
    except Exception as e:
        logger.error(f"Error formatting disbursement summary: {e}")
        return {}


