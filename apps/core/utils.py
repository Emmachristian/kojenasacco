# core/utils.py

"""
Central utilities for SACCO operations
Prevents code duplication and ensures consistency
"""
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponse
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# CURRENCY & MONEY FORMATTING
# =============================================================================

def get_base_currency():
    """
    Get base currency from SACCO configuration.
    Safe method that handles circular imports and missing config.
    
    Returns:
        str: Currency code (defaults to 'UGX')
    """
    try:
        from core.models import FinancialSettings
        settings = FinancialSettings.get_instance()
        return settings.sacco_currency if settings else 'UGX'
    except Exception as e:
        logger.warning(f"Could not fetch currency from settings: {e}")
        return 'UGX'


def format_money(amount, include_symbol=True):
    """
    Format money amount according to SACCO financial settings.
    
    Args:
        amount: Decimal or numeric value to format
        include_symbol: Whether to include currency symbol
        
    Returns:
        str: Formatted money string
    """
    try:
        from core.models import FinancialSettings
        settings = FinancialSettings.get_instance()
        if settings:
            return settings.format_currency(amount, include_symbol)
    except Exception as e:
        logger.warning(f"Could not format using settings: {e}")
    
    # Fallback formatting
    try:
        amount_decimal = Decimal(str(amount or 0))
        formatted = f"{amount_decimal:,.2f}"
        return f"UGX {formatted}" if include_symbol else formatted
    except (ValueError, TypeError):
        return "UGX 0.00" if include_symbol else "0.00"


def validate_amount_in_currency(amount, currency_code=None):
    """
    Validate that an amount is appropriate for the SACCO's currency.
    
    Args:
        amount: Amount to validate
        currency_code: Optional currency code to check against
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if currency_code is None:
        currency_code = get_base_currency()
    
    try:
        amount_decimal = Decimal(str(amount))
        
        if amount_decimal < 0:
            return False, "Amount cannot be negative"
        
        # Add currency-specific validations here if needed
        
        return True, None
        
    except (ValueError, TypeError):
        return False, "Invalid amount format"


# =============================================================================
# FISCAL PERIOD & YEAR UTILITIES
# =============================================================================

def get_active_fiscal_period():
    """
    Get the currently active fiscal period.
    
    Returns:
        FiscalPeriod or None: Active fiscal period
    """
    try:
        from core.models import FiscalPeriod
        return FiscalPeriod.get_active_period()
    except Exception as e:
        logger.error(f"Error fetching active fiscal period: {e}")
        return None


def get_active_fiscal_year():
    """
    Get the currently active fiscal year.
    
    Returns:
        FiscalYear or None: Active fiscal year
    """
    try:
        from core.models import FiscalYear
        return FiscalYear.get_active_fiscal_year()
    except Exception as e:
        logger.error(f"Error fetching active fiscal year: {e}")
        return None


# =============================================================================
# TIMEZONE UTILITY FUNCTIONS
# =============================================================================

def get_sacco_timezone():
    """
    Get the SACCO's operational timezone.
    
    This is the central timezone utility for all SACCO operations.
    Use this consistently across the application to ensure all date/time
    calculations use the correct timezone.
    
    Returns:
        ZoneInfo: SACCO's operational timezone
    
    Example:
        >>> from core.utils import get_sacco_timezone
        >>> tz = get_sacco_timezone()
        >>> now = datetime.now(tz=tz)
        >>> print(f"Current time in SACCO timezone: {now}")
    """
    from zoneinfo import ZoneInfo
    try:
        from core.models import SaccoConfiguration
        config = SaccoConfiguration.get_instance()
        return config.get_timezone() if config else ZoneInfo('Africa/Kampala')
    except Exception as e:
        logger.error(f"Error getting SACCO timezone: {e}")
        return ZoneInfo('Africa/Kampala')


def get_sacco_current_time():
    """
    Get current time in SACCO's operational timezone.
    
    Use this when you need the current timestamp with timezone awareness.
    Perfect for logging, audit trails, and transaction timestamps.
    
    Returns:
        datetime: Current datetime in SACCO's timezone
    
    Example:
        >>> from core.utils import get_sacco_current_time
        >>> current_time = get_sacco_current_time()
        >>> transaction.timestamp = current_time
        >>> print(f"Transaction time: {current_time}")
    """
    from django.utils import timezone
    return timezone.now().astimezone(get_sacco_timezone())


def get_sacco_today():
    """
    Get today's date in SACCO's operational timezone.
    
    **CRITICAL**: Always use this instead of date.today() or timezone.now().date()
    for any business logic that depends on dates!
    
    This is essential for:
    - Fiscal period boundary checks (is period active today?)
    - Loan due date calculations (is payment overdue?)
    - Report date ranges (transactions for today)
    - Dividend calculations (contributions as of today)
    - Any date-based business logic
    
    Why? Because "today" depends on timezone:
    - In Uganda (EAT/UTC+3), it might be Jan 15
    - In New York (EST/UTC-5), it might still be Jan 14
    - Using UTC would give wrong results for local business operations
    
    Returns:
        date: Today's date in SACCO's timezone
    
    Example:
        >>> from core.utils import get_sacco_today
        >>> today = get_sacco_today()
        >>> 
        >>> # Check if period is active
        >>> if period.start_date <= today <= period.end_date:
        >>>     print("Period is active today")
        >>> 
        >>> # Check if loan payment is overdue
        >>> if loan.due_date < today:
        >>>     print("Payment is overdue")
        >>> 
        >>> # Get today's transactions
        >>> transactions = Transaction.objects.filter(date=today)
    """
    return get_sacco_current_time().date()


def localize_datetime(dt):
    """
    Convert a datetime to SACCO's operational timezone.
    
    Use this to convert UTC or naive datetimes to the SACCO's timezone
    for display or calculations.
    
    Args:
        dt: datetime object (naive or aware)
        
    Returns:
        datetime: Timezone-aware datetime in SACCO's operational timezone
    
    Example:
        >>> from core.utils import localize_datetime
        >>> utc_time = timezone.now()  # In UTC
        >>> local_time = localize_datetime(utc_time)
        >>> print(f"Local time: {local_time}")
    """
    from django.utils import timezone
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt.astimezone(get_sacco_timezone())


# =============================================================================
# PAGINATION & FILTERING
# =============================================================================

def paginate_queryset(request, queryset, per_page=20):
    """
    Paginate a queryset with sensible defaults.
    
    Args:
        request: HTTP request object
        queryset: Django queryset to paginate
        per_page: Items per page (default: 20)
        
    Returns:
        tuple: (page_obj, paginator)
    """
    paginator = Paginator(queryset, per_page)
    page = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    return page_obj, paginator


def parse_filters(request, filter_keys):
    """
    Extract filter values from request.GET.
    
    Args:
        request: HTTP request object
        filter_keys: list of filter names to extract
        
    Returns:
        dict: {key: value or None}
    """
    filters = {}
    for key in filter_keys:
        value = request.GET.get(key, '').strip()
        filters[key] = value if value else None
    return filters


# =============================================================================
# HTMX MODAL RESPONSES WITH SWEETALERT2
# =============================================================================

def create_sweetalert_response(html_content='', message='', alert_type='success', title=None, close_modal=True):
    """
    Create HTTP response with SweetAlert2 headers for HTMX modal actions.
    
    This helper standardizes the response format for modal operations across the entire application.
    The htmx-modal.js file reads these headers and displays appropriate SweetAlert2 notifications.
    
    Args:
        html_content (str): Updated HTML to swap into page (empty for delete operations)
        message (str): Alert message to display to user
        alert_type (str): Type of alert - 'success', 'error', 'warning', 'info', 'question'
        title (str|None): Optional custom alert title (uses defaults if None)
        close_modal (bool): Whether to close the modal after response (default: True)
        
    Returns:
        HttpResponse: Response object with custom headers
        
    Example Usage:
        # Success with updated content
        return create_sweetalert_response(
            html_content=render_to_string('app/_card.html', {'obj': obj}),
            message='Application approved successfully!',
            alert_type='success',
            title='Approved'
        )
        
        # Error without content update
        return create_sweetalert_response(
            html_content='',
            message='Unable to complete operation. Please try again.',
            alert_type='error',
            title='Operation Failed'
        )
        
        # Delete operation (no HTML content needed)
        return create_sweetalert_response(
            html_content='',  # Row removed by HTMX
            message=f"Product '{name}' deleted successfully.",
            alert_type='success'
        )
        
    Headers Set:
        HX-Alert-Message: The message text
        HX-Alert-Type: The alert type (success/error/warning/info)
        HX-Alert-Title: Custom title (optional)
        HX-Close-Modal: 'true' to close modal (optional)
    """
    response = HttpResponse(html_content)
    
    # Set alert headers if message provided
    if message:
        response['HX-Alert-Message'] = message
        response['HX-Alert-Type'] = alert_type or 'success'
        
        if title:
            response['HX-Alert-Title'] = title
    
    # Set modal close header
    if close_modal:
        response['HX-Close-Modal'] = 'true'
    
    return response


def create_success_response(html_content, message, title='Success'):
    """
    Shortcut for success responses.
    
    Args:
        html_content: Updated HTML
        message: Success message
        title: Optional title (default: 'Success')
        
    Returns:
        HttpResponse with success alert
    """
    return create_sweetalert_response(
        html_content=html_content,
        message=message,
        alert_type='success',
        title=title,
        close_modal=True
    )


def create_error_response(message, title='Error', close_modal=True):
    """
    Shortcut for error responses.
    
    Args:
        message: Error message
        title: Optional title (default: 'Error')
        close_modal: Whether to close modal (default: True)
        
    Returns:
        HttpResponse with error alert
    """
    return create_sweetalert_response(
        html_content='',
        message=message,
        alert_type='error',
        title=title,
        close_modal=close_modal
    )


def create_warning_response(message, title='Warning', close_modal=True):
    """
    Shortcut for warning responses.
    
    Args:
        message: Warning message
        title: Optional title (default: 'Warning')
        close_modal: Whether to close modal (default: True)
        
    Returns:
        HttpResponse with warning alert
    """
    return create_sweetalert_response(
        html_content='',
        message=message,
        alert_type='warning',
        title=title,
        close_modal=close_modal
    )


def create_info_response(message, title='Information', close_modal=True):
    """
    Shortcut for info responses.
    
    Args:
        message: Info message
        title: Optional title (default: 'Information')
        close_modal: Whether to close modal (default: True)
        
    Returns:
        HttpResponse with info alert
    """
    return create_sweetalert_response(
        html_content='',
        message=message,
        alert_type='info',
        title=title,
        close_modal=close_modal
    )


def create_redirect_response(redirect_url, message='', alert_type='success', title=None):
    """
    Create redirect response with SweetAlert notification for HTMX.
    
    This is typically used after delete operations or when you want to redirect
    to a different page (like a list view) after a successful modal action.
    
    Args:
        redirect_url (str): URL to redirect to
        message (str): Alert message to display before redirect
        alert_type (str): Type of alert - 'success', 'error', 'warning', 'info'
        title (str|None): Optional custom alert title
        
    Returns:
        HttpResponse: Response object with redirect and alert headers
        
    Example Usage:
        # After deleting an item
        return create_redirect_response(
            redirect_url='/savings/products/',
            message=f"Product '{product_name}' deleted successfully",
            title='Product Deleted'
        )
        
        # After an error that requires redirect
        return create_redirect_response(
            redirect_url='/savings/accounts/',
            message='Account not found or already deleted',
            alert_type='error',
            title='Not Found'
        )
        
    Headers Set:
        HX-Redirect: The URL to redirect to
        HX-Alert-Message: The message text (if provided)
        HX-Alert-Type: The alert type (if message provided)
        HX-Alert-Title: Custom title (if provided)
        HX-Close-Modal: Always 'true' for redirects
    """
    response = HttpResponse('')
    
    # Set redirect header (HTMX will perform client-side redirect)
    response['HX-Redirect'] = redirect_url
    
    # Set alert headers if message provided
    if message:
        response['HX-Alert-Message'] = message
        response['HX-Alert-Type'] = alert_type or 'success'
        
        if title:
            response['HX-Alert-Title'] = title
    
    # Always close modal on redirect
    response['HX-Close-Modal'] = 'true'
    
    return response