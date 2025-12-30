# shares/utils.py

"""
Shares Utility Functions

Pure utility functions with NO side effects (no database writes):
- Share number generation logic
- Share value calculations
- Member share balance calculations
- Validation functions
- Transfer fee calculations
- Certificate number generation
- Helper functions for common operations

All functions are pure - they calculate and return values without modifying the database.
Database writes are handled by signals.py and services.py.
"""

from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from datetime import timedelta, date
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# NUMBER GENERATION
# =============================================================================

def generate_transaction_number(transaction_type):
    """
    Generate unique share transaction number.
    
    Format: TYPE-YYYYMMDDHHMMSS-XXXX
    
    Args:
        transaction_type (str): Transaction type (BUY, SELL, etc.)
    
    Returns:
        str: Unique transaction number
    
    Example:
        >>> generate_transaction_number('BUY')
        'SHB-20250129143025-0001'
    """
    from shares.models import ShareTransaction
    
    # Map transaction types to prefixes
    type_prefixes = {
        'BUY': 'SHB',
        'SELL': 'SHS',
        'TRANSFER_OUT': 'STO',
        'TRANSFER_IN': 'STI',
        'ADJUSTMENT': 'SHA',
    }
    
    prefix = type_prefixes.get(transaction_type, 'SHT')
    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
    base_id = f"{prefix}-{timestamp}"
    
    with transaction.atomic():
        # Check for existing transactions with this base ID
        existing_txns = ShareTransaction.objects.filter(
            transaction_number__startswith=base_id
        ).select_for_update()
        
        if existing_txns.exists():
            max_counter = 0
            for txn_num in existing_txns.values_list('transaction_number', flat=True):
                try:
                    counter = int(txn_num.split('-')[-1])
                    max_counter = max(max_counter, counter)
                except (ValueError, IndexError):
                    continue
            
            new_counter = max_counter + 1
        else:
            new_counter = 1
        
        # Format counter
        formatted_counter = f"{new_counter:04d}"
        transaction_number = f"{base_id}-{formatted_counter}"
        
        logger.info(f"Generated share transaction number: {transaction_number}")
        return transaction_number


def generate_certificate_number(prefix='SC'):
    """
    Generate unique share certificate number.
    
    Format: PREFIX-YYYYMMDD-XXXXXX
    
    Args:
        prefix (str): Certificate prefix
    
    Returns:
        str: Unique certificate number
    
    Example:
        >>> generate_certificate_number('SC')
        'SC-20250129-000001'
    """
    from shares.models import ShareCertificate
    
    date_str = timezone.now().strftime('%Y%m%d')
    base_id = f"{prefix}-{date_str}"
    
    with transaction.atomic():
        # Check for existing certificates with this base ID
        existing_certs = ShareCertificate.objects.filter(
            certificate_number__startswith=base_id
        ).select_for_update()
        
        if existing_certs.exists():
            max_counter = 0
            for cert_num in existing_certs.values_list('certificate_number', flat=True):
                try:
                    counter = int(cert_num.split('-')[-1])
                    max_counter = max(max_counter, counter)
                except (ValueError, IndexError):
                    continue
            
            new_counter = max_counter + 1
        else:
            new_counter = 1
        
        # Format counter
        formatted_counter = f"{new_counter:06d}"
        certificate_number = f"{base_id}-{formatted_counter}"
        
        logger.info(f"Generated certificate number: {certificate_number}")
        return certificate_number


def generate_transfer_request_number():
    """
    Generate unique share transfer request number.
    
    Format: STR-YYYYMMDD-XXXX
    
    Returns:
        str: Unique request number
    
    Example:
        >>> generate_transfer_request_number()
        'STR-20250129-0001'
    """
    from shares.models import ShareTransferRequest
    
    date_str = timezone.now().strftime('%Y%m%d')
    base_id = f"STR-{date_str}"
    
    with transaction.atomic():
        # Check for existing requests
        existing_requests = ShareTransferRequest.objects.filter(
            request_number__startswith=base_id
        ).select_for_update()
        
        if existing_requests.exists():
            max_counter = 0
            for req_num in existing_requests.values_list('request_number', flat=True):
                try:
                    counter = int(req_num.split('-')[-1])
                    max_counter = max(max_counter, counter)
                except (ValueError, IndexError):
                    continue
            
            new_counter = max_counter + 1
        else:
            new_counter = 1
        
        # Format counter
        formatted_counter = f"{new_counter:04d}"
        request_number = f"{base_id}-{formatted_counter}"
        
        logger.info(f"Generated transfer request number: {request_number}")
        return request_number


# =============================================================================
# SHARE VALUE CALCULATIONS
# =============================================================================

def calculate_share_value(shares_count, share_price):
    """
    Calculate total value of shares.
    
    Formula: Total Value = Shares Count × Share Price
    
    Args:
        shares_count (Decimal/int): Number of shares
        share_price (Decimal): Price per share
    
    Returns:
        Decimal: Total value
    
    Example:
        >>> calculate_share_value(100, Decimal('1000'))
        Decimal('100000.00')
    """
    try:
        count = Decimal(str(shares_count))
        price = Decimal(str(share_price))
        
        if count < 0 or price < 0:
            logger.warning("Negative values in share value calculation")
            return Decimal('0.00')
        
        total_value = count * price
        
        return total_value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating share value: {e}")
        return Decimal('0.00')


def calculate_transaction_amount(shares_count, price_per_share):
    """
    Calculate transaction amount.
    
    Args:
        shares_count (Decimal): Number of shares
        price_per_share (Decimal): Price per share
    
    Returns:
        Decimal: Transaction amount
    """
    return calculate_share_value(shares_count, price_per_share)


def calculate_transfer_fee(shares_count, share_price, fixed_fee, percentage_fee):
    """
    Calculate transfer fee.
    
    Formula: Fee = Fixed Fee + (Transaction Value × Percentage / 100)
    
    Args:
        shares_count (Decimal): Number of shares
        share_price (Decimal): Share price
        fixed_fee (Decimal): Fixed fee amount
        percentage_fee (Decimal): Percentage fee
    
    Returns:
        Decimal: Transfer fee
    
    Example:
        >>> calculate_transfer_fee(
        ...     Decimal('100'), Decimal('1000'),
        ...     Decimal('500'), Decimal('1')
        ... )
        Decimal('1500.00')
    """
    try:
        count = Decimal(str(shares_count))
        price = Decimal(str(share_price))
        fixed = Decimal(str(fixed_fee))
        pct = Decimal(str(percentage_fee))
        
        # Calculate transaction value
        transaction_value = count * price
        
        # Calculate percentage fee
        pct_fee = (transaction_value * pct) / Decimal('100')
        
        # Total fee
        total_fee = fixed + pct_fee
        
        return total_fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.error(f"Error calculating transfer fee: {e}")
        return Decimal('0.00')


def calculate_early_redemption_penalty(shares_value, penalty_rate):
    """
    Calculate early redemption penalty.
    
    Formula: Penalty = (Shares Value × Penalty Rate) / 100
    
    Args:
        shares_value (Decimal): Value of shares being redeemed
        penalty_rate (Decimal): Penalty rate percentage
    
    Returns:
        Decimal: Penalty amount
    
    Example:
        >>> calculate_early_redemption_penalty(Decimal('100000'), Decimal('5'))
        Decimal('5000.00')
    """
    try:
        value = Decimal(str(shares_value))
        rate = Decimal(str(penalty_rate)) / Decimal('100')
        
        if value < 0 or rate < 0:
            logger.warning("Negative values in penalty calculation")
            return Decimal('0.00')
        
        penalty = value * rate
        
        return penalty.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating redemption penalty: {e}")
        return Decimal('0.00')


# =============================================================================
# MEMBER SHARE BALANCE CALCULATIONS
# =============================================================================

def calculate_member_share_balance(member, as_of_date=None):
    """
    Calculate member's current share balance.
    
    Args:
        member: Member instance
        as_of_date (date, optional): Calculate balance as of this date
    
    Returns:
        dict: Balance information
            {
                'shares_bought': Decimal,
                'shares_sold': Decimal,
                'net_shares': Decimal,
                'current_share_price': Decimal,
                'total_value': Decimal
            }
    
    Example:
        >>> calculate_member_share_balance(member)
        {'shares_bought': Decimal('150'), 'shares_sold': Decimal('0'), ...}
    """
    from shares.models import ShareTransaction, ShareCapital
    
    try:
        calculation_date = as_of_date or timezone.now().date()
        
        # Get completed, non-reversed transactions
        transactions = ShareTransaction.objects.filter(
            member=member,
            status='COMPLETED',
            is_reversed=False,
            transaction_date__lte=timezone.make_aware(
                timezone.datetime.combine(calculation_date, timezone.datetime.max.time())
            )
        )
        
        # Calculate shares bought
        shares_bought = transactions.filter(
            transaction_type__in=['BUY', 'TRANSFER_IN']
        ).aggregate(
            total=Sum('shares_count')
        )['total'] or Decimal('0.00')
        
        # Calculate shares sold
        shares_sold = transactions.filter(
            transaction_type__in=['SELL', 'TRANSFER_OUT']
        ).aggregate(
            total=Sum('shares_count')
        )['total'] or Decimal('0.00')
        
        # Calculate net shares
        net_shares = shares_bought - shares_sold
        
        # Get current share price
        share_capital = ShareCapital.get_active_share_capital()
        current_price = share_capital.share_price if share_capital else Decimal('0.00')
        
        # Calculate total value
        total_value = calculate_share_value(net_shares, current_price)
        
        return {
            'shares_bought': shares_bought.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'shares_sold': shares_sold.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'net_shares': net_shares.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'current_share_price': current_price,
            'total_value': total_value
        }
        
    except Exception as e:
        logger.error(f"Error calculating member share balance: {e}")
        return {
            'shares_bought': Decimal('0.00'),
            'shares_sold': Decimal('0.00'),
            'net_shares': Decimal('0.00'),
            'current_share_price': Decimal('0.00'),
            'total_value': Decimal('0.00')
        }


def get_member_share_history(member, start_date=None, end_date=None):
    """
    Get member's share transaction history.
    
    Args:
        member: Member instance
        start_date (date, optional): Start date
        end_date (date, optional): End date
    
    Returns:
        QuerySet: Share transactions
    """
    from shares.models import ShareTransaction
    
    try:
        transactions = ShareTransaction.objects.filter(
            member=member,
            status='COMPLETED',
            is_reversed=False
        )
        
        if start_date:
            transactions = transactions.filter(
                transaction_date__gte=timezone.make_aware(
                    timezone.datetime.combine(start_date, timezone.datetime.min.time())
                )
            )
        
        if end_date:
            transactions = transactions.filter(
                transaction_date__lte=timezone.make_aware(
                    timezone.datetime.combine(end_date, timezone.datetime.max.time())
                )
            )
        
        return transactions.order_by('-transaction_date')
        
    except Exception as e:
        logger.error(f"Error getting member share history: {e}")
        return ShareTransaction.objects.none()


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_share_purchase(member, shares_count, share_capital):
    """
    Validate share purchase transaction.
    
    Args:
        member: Member instance
        shares_count (Decimal): Number of shares to purchase
        share_capital: ShareCapital instance
    
    Returns:
        tuple: (is_valid: bool, message: str)
    
    Example:
        >>> validate_share_purchase(member, Decimal('10'), share_capital)
        (True, 'Purchase is valid')
    """
    try:
        shares = Decimal(str(shares_count))
    except (ValueError, TypeError):
        return False, "Invalid share count"
    
    # Check minimum purchase
    if shares < share_capital.minimum_purchase_shares:
        return False, f"Minimum purchase is {share_capital.minimum_purchase_shares} shares"
    
    # Check maximum purchase
    if share_capital.maximum_purchase_shares:
        if shares > share_capital.maximum_purchase_shares:
            return False, f"Maximum purchase is {share_capital.maximum_purchase_shares} shares"
    
    # Check if fractional shares allowed
    if not share_capital.allow_fractional_shares:
        if shares != int(shares):
            return False, "Fractional shares are not allowed"
    
    # Check member's total shares after purchase
    balance = calculate_member_share_balance(member)
    total_after_purchase = balance['net_shares'] + shares
    
    # Check maximum shares per member
    if share_capital.maximum_shares:
        if total_after_purchase > share_capital.maximum_shares:
            return False, f"Purchase would exceed maximum shares limit of {share_capital.maximum_shares}"
    
    return True, "Purchase is valid"


def validate_share_sale(member, shares_count, share_capital):
    """
    Validate share sale/redemption transaction.
    
    Args:
        member: Member instance
        shares_count (Decimal): Number of shares to sell
        share_capital: ShareCapital instance
    
    Returns:
        tuple: (is_valid: bool, message: str)
    """
    # Check if redemption allowed
    if not share_capital.allow_redemption:
        return False, "Share redemption is not allowed"
    
    try:
        shares = Decimal(str(shares_count))
    except (ValueError, TypeError):
        return False, "Invalid share count"
    
    if shares <= 0:
        return False, "Share count must be greater than zero"
    
    # Check member's current balance
    balance = calculate_member_share_balance(member)
    
    if shares > balance['net_shares']:
        return False, f"Insufficient shares. Current balance: {balance['net_shares']}"
    
    # Check minimum shares requirement
    remaining_shares = balance['net_shares'] - shares
    if remaining_shares < share_capital.minimum_shares and remaining_shares != 0:
        return False, f"Sale would leave balance below minimum required shares of {share_capital.minimum_shares}"
    
    return True, "Sale is valid"


def validate_share_transfer(from_member, to_member, shares_count, share_capital):
    """
    Validate share transfer transaction.
    
    Args:
        from_member: Member transferring shares
        to_member: Member receiving shares
        shares_count (Decimal): Number of shares to transfer
        share_capital: ShareCapital instance
    
    Returns:
        tuple: (is_valid: bool, message: str)
    """
    # Check if transfers allowed
    if not share_capital.allow_transfers:
        return False, "Share transfers are not allowed"
    
    # Check same member
    if from_member == to_member:
        return False, "Cannot transfer shares to the same member"
    
    try:
        shares = Decimal(str(shares_count))
    except (ValueError, TypeError):
        return False, "Invalid share count"
    
    if shares <= 0:
        return False, "Share count must be greater than zero"
    
    # Check from_member's balance
    from_balance = calculate_member_share_balance(from_member)
    
    if shares > from_balance['net_shares']:
        return False, f"Insufficient shares. Current balance: {from_balance['net_shares']}"
    
    # Check minimum shares requirement for from_member
    remaining_shares = from_balance['net_shares'] - shares
    if remaining_shares < share_capital.minimum_shares and remaining_shares != 0:
        return False, f"Transfer would leave sender below minimum required shares of {share_capital.minimum_shares}"
    
    # Check maximum shares for to_member
    to_balance = calculate_member_share_balance(to_member)
    total_after_transfer = to_balance['net_shares'] + shares
    
    if share_capital.maximum_shares:
        if total_after_transfer > share_capital.maximum_shares:
            return False, f"Transfer would put receiver above maximum shares limit of {share_capital.maximum_shares}"
    
    return True, "Transfer is valid"


def can_issue_certificate(member):
    """
    Check if certificate can be issued to member.
    
    Args:
        member: Member instance
    
    Returns:
        tuple: (can_issue: bool, message: str)
    """
    # Check member status
    if hasattr(member, 'status') and member.status != 'ACTIVE':
        return False, "Member must be active to receive certificates"
    
    # Check share balance
    balance = calculate_member_share_balance(member)
    
    if balance['net_shares'] <= 0:
        return False, "Member has no shares"
    
    return True, "Certificate can be issued"


def validate_holding_period(transaction_date, minimum_holding_days):
    """
    Validate if minimum holding period has been met.
    
    Args:
        transaction_date (datetime): Original transaction date
        minimum_holding_days (int): Minimum holding period in days
    
    Returns:
        tuple: (is_valid: bool, days_held: int, message: str)
    """
    try:
        today = timezone.now()
        
        # Calculate days held
        days_held = (today - transaction_date).days
        
        if days_held < minimum_holding_days:
            days_remaining = minimum_holding_days - days_held
            message = f"Minimum holding period not met. {days_remaining} days remaining"
            return False, days_held, message
        
        message = f"Holding period met ({days_held} days)"
        return True, days_held, message
        
    except Exception as e:
        logger.error(f"Error validating holding period: {e}")
        return False, 0, str(e)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_share_price_at_date(transaction_date):
    """
    Get share price that was effective at a given date.
    
    Args:
        transaction_date (date): Date to get price for
    
    Returns:
        Decimal: Share price at that date
    """
    from shares.models import ShareCapital
    
    try:
        share_capital = ShareCapital.objects.filter(
            is_active=True,
            effective_date__lte=transaction_date
        ).order_by('-effective_date').first()
        
        if share_capital:
            return share_capital.share_price
        
        logger.warning(f"No share capital found for date {transaction_date}")
        return Decimal('0.00')
        
    except Exception as e:
        logger.error(f"Error getting share price at date: {e}")
        return Decimal('0.00')


def calculate_total_shares_issued(as_of_date=None):
    """
    Calculate total shares issued to all members.
    
    Args:
        as_of_date (date, optional): Calculate as of this date
    
    Returns:
        dict: Total shares information
            {
                'total_shares': Decimal,
                'total_value': Decimal,
                'member_count': int
            }
    """
    from shares.models import ShareTransaction, ShareCapital
    from members.models import Member
    
    try:
        calculation_date = as_of_date or timezone.now().date()
        
        # Get all completed transactions
        transactions = ShareTransaction.objects.filter(
            status='COMPLETED',
            is_reversed=False,
            transaction_date__lte=timezone.make_aware(
                timezone.datetime.combine(calculation_date, timezone.datetime.max.time())
            )
        )
        
        # Calculate total bought
        total_bought = transactions.filter(
            transaction_type__in=['BUY', 'TRANSFER_IN']
        ).aggregate(
            total=Sum('shares_count')
        )['total'] or Decimal('0.00')
        
        # Calculate total sold
        total_sold = transactions.filter(
            transaction_type__in=['SELL', 'TRANSFER_OUT']
        ).aggregate(
            total=Sum('shares_count')
        )['total'] or Decimal('0.00')
        
        # Net shares
        total_shares = total_bought - total_sold
        
        # Get current price
        share_capital = ShareCapital.get_active_share_capital()
        current_price = share_capital.share_price if share_capital else Decimal('0.00')
        
        # Calculate total value
        total_value = calculate_share_value(total_shares, current_price)
        
        # Count members with shares
        members_with_shares = Member.objects.filter(
            share_transactions__status='COMPLETED',
            share_transactions__is_reversed=False
        ).distinct().count()
        
        return {
            'total_shares': total_shares.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'total_value': total_value,
            'member_count': members_with_shares
        }
        
    except Exception as e:
        logger.error(f"Error calculating total shares issued: {e}")
        return {
            'total_shares': Decimal('0.00'),
            'total_value': Decimal('0.00'),
            'member_count': 0
        }


def format_share_statement(member, start_date=None, end_date=None):
    """
    Format member's share statement.
    
    Args:
        member: Member instance
        start_date (date, optional): Statement start date
        end_date (date, optional): Statement end date
    
    Returns:
        dict: Formatted statement
    """
    from core.utils import format_money
    
    try:
        # Get opening balance
        opening_balance = Decimal('0.00')
        if start_date:
            opening_balance_info = calculate_member_share_balance(
                member,
                as_of_date=start_date - timedelta(days=1)
            )
            opening_balance = opening_balance_info['net_shares']
        
        # Get transactions
        transactions = get_member_share_history(member, start_date, end_date)
        
        # Get closing balance
        closing_balance_info = calculate_member_share_balance(member, as_of_date=end_date)
        closing_balance = closing_balance_info['net_shares']
        
        # Format transactions
        formatted_transactions = []
        running_balance = opening_balance
        
        for txn in transactions:
            if txn.transaction_type in ['BUY', 'TRANSFER_IN']:
                running_balance += txn.shares_count
            else:
                running_balance -= txn.shares_count
            
            formatted_transactions.append({
                'date': txn.transaction_date.strftime('%Y-%m-%d'),
                'transaction_number': txn.transaction_number,
                'type': txn.get_transaction_type_display(),
                'shares': float(txn.shares_count),
                'price': format_money(txn.price_per_share),
                'amount': format_money(txn.total_amount),
                'balance': float(running_balance)
            })
        
        return {
            'member': member.get_full_name(),
            'member_number': member.member_number,
            'period_start': start_date.strftime('%Y-%m-%d') if start_date else 'Beginning',
            'period_end': end_date.strftime('%Y-%m-%d') if end_date else 'Today',
            'opening_balance': float(opening_balance),
            'closing_balance': float(closing_balance),
            'closing_value': format_money(closing_balance_info['total_value']),
            'transactions': formatted_transactions
        }
        
    except Exception as e:
        logger.error(f"Error formatting share statement: {e}")
        return {}
