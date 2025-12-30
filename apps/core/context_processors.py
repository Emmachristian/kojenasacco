# core/context_processors.py

from django.utils import timezone
from datetime import timedelta
from core.models import (
    FinancialSettings,
    SaccoConfiguration,
    FiscalYear,
    FiscalPeriod,
    PaymentMethod,
    TaxRate,
    UnitOfMeasure
)
import logging

logger = logging.getLogger(__name__)


def financial_settings(request):
    """
    Provides SACCO financial settings context for all templates.
    Includes currency configuration, loan/savings settings, and formatting options.
    """
    context = {
        'financial_settings': None,
        'sacco_currency': 'UGX',
        'currency_symbol': 'UGX',
        'decimal_places': 2,
        'use_thousand_separator': True,
        'default_loan_term_days': 365,
        'default_interest_rate': 12.00,
        'minimum_savings_balance': 10000.00,
    }
    
    try:
        settings = FinancialSettings.get_instance()
        if settings:
            context['financial_settings'] = settings
            context['sacco_currency'] = settings.sacco_currency 
            context['currency_symbol'] = settings.sacco_currency  
            context['decimal_places'] = settings.decimal_places
            context['use_thousand_separator'] = settings.use_thousand_separator
            context['currency_position'] = settings.currency_position
            
            # Loan settings
            context['default_loan_term_days'] = settings.default_loan_term_days
            context['default_interest_rate'] = settings.default_interest_rate
            context['late_payment_penalty_rate'] = settings.late_payment_penalty_rate
            context['grace_period_days'] = settings.grace_period_days
            context['minimum_loan_amount'] = settings.minimum_loan_amount
            context['maximum_loan_amount'] = settings.maximum_loan_amount
            context['loan_approval_required'] = settings.loan_approval_required
            
            # Savings settings
            context['minimum_savings_balance'] = settings.minimum_savings_balance
            context['savings_interest_rate'] = settings.savings_interest_rate
            
            # Share capital settings
            context['share_value'] = settings.share_value
            context['minimum_shares'] = settings.minimum_shares
            
            # Workflow settings
            context['withdrawal_approval_required'] = settings.withdrawal_approval_required
            context['withdrawal_approval_limit'] = settings.withdrawal_approval_limit
            
            # Communication settings
            context['send_transaction_notifications'] = settings.send_transaction_notifications
            context['send_loan_reminders'] = settings.send_loan_reminders
            context['send_dividend_notifications'] = settings.send_dividend_notifications
            
    except Exception as e:
        logger.error(f"Error loading financial settings: {e}")
    
    return context


def sacco_configuration(request):
    """
    Provides SACCO configuration context including period system and dividend settings.
    """
    context = {
        'sacco_config': None,
        'period_system': 'monthly',
        'periods_per_year': 12,
        'period_type_name': 'Month',
        'period_type_name_plural': 'Months',
        'fiscal_year_start_month': 1,
        'dividend_calculation_method': 'SHARE_BASED',
        'dividend_distribution_frequency': 'ANNUAL',
    }
    
    try:
        config = SaccoConfiguration.get_instance()
        if config:
            context['sacco_config'] = config
            context['period_system'] = config.period_system
            context['periods_per_year'] = config.periods_per_year
            context['period_type_name'] = config.get_period_type_name()
            context['period_type_name_plural'] = config.get_period_type_name_plural()
            context['period_naming_convention'] = config.period_naming_convention
            context['fiscal_year_type'] = config.fiscal_year_type
            context['fiscal_year_start_month'] = config.fiscal_year_start_month
            context['fiscal_year_start_day'] = config.fiscal_year_start_day
            
            # SACCO-specific settings
            context['dividend_calculation_method'] = config.dividend_calculation_method
            context['dividend_distribution_frequency'] = config.dividend_distribution_frequency
            
            # Communication settings
            context['enable_automatic_reminders'] = config.enable_automatic_reminders
            context['enable_sms'] = config.enable_sms
            context['enable_email_notifications'] = config.enable_email_notifications
            
    except Exception as e:
        logger.error(f"Error loading SACCO configuration: {e}")
    
    return context


def active_fiscal_period(request):
    """
    Provides active fiscal year and period context.
    Includes warnings for missing or ending fiscal years/periods.
    """
    # Get current date
    today = timezone.now().date()
    
    context = {
        'today': today,
        'active_fiscal_year': None,
        'active_period': None,
        'fiscal_year_name': None,
        'period_name': None,
        'fiscal_year_progress': 0,
        'period_progress': 0,
        'fiscal_year_status': None,
        'period_status': None,
        'fiscal_year_ending_soon': False,
        'period_ending_soon': False,
        'days_until_fy_end': None,
        'days_until_period_end': None,
    }
    
    try:
        # Get active fiscal year
        fiscal_year = FiscalYear.get_active_fiscal_year()
        if fiscal_year:
            context['active_fiscal_year'] = fiscal_year
            context['fiscal_year_name'] = fiscal_year.name
            context['fiscal_year_code'] = fiscal_year.code
            context['fiscal_year_start_date'] = fiscal_year.start_date
            context['fiscal_year_end_date'] = fiscal_year.end_date
            context['fiscal_year_progress'] = fiscal_year.get_progress_percentage()
            context['fiscal_year_status'] = fiscal_year.status
            context['fiscal_year_is_closed'] = fiscal_year.is_closed
            context['fiscal_year_is_locked'] = fiscal_year.is_locked
            context['fiscal_year_remaining_days'] = fiscal_year.get_remaining_days()
            context['fiscal_year_elapsed_days'] = fiscal_year.get_elapsed_days()
            context['fiscal_year_is_current'] = fiscal_year.is_current()
            
            # Calculate if fiscal year is ending soon (90 days warning)
            days_until_end = (fiscal_year.end_date - today).days
            context['days_until_fy_end'] = days_until_end
            if days_until_end <= 90 and days_until_end > 0:
                context['fiscal_year_ending_soon'] = True
        
        # Get active period
        period = FiscalPeriod.get_active_period()
        if period:
            context['active_period'] = period
            context['period_name'] = period.name
            context['period_number'] = period.period_number
            context['period_start_date'] = period.start_date
            context['period_end_date'] = period.end_date
            context['period_progress'] = period.get_progress_percentage()
            context['period_status'] = period.status
            context['period_is_closed'] = period.is_closed
            context['period_is_locked'] = period.is_locked
            context['period_remaining_days'] = period.get_remaining_days()
            context['period_elapsed_days'] = period.get_elapsed_days()
            context['period_is_current'] = period.is_current()
            context['period_is_last'] = period.is_last_period()
            
            # Calculate if period is ending soon (14 days warning)
            days_until_period_end = (period.end_date - today).days
            context['days_until_period_end'] = days_until_period_end
            if days_until_period_end <= 14 and days_until_period_end > 0:
                context['period_ending_soon'] = True
                
    except Exception as e:
        logger.error(f"Error loading active fiscal period: {e}")
    
    return context


def payment_methods_context(request):
    """
    Provides available payment methods for SACCO transactions.
    """
    context = {
        'payment_methods': [], 
        'active_payment_methods': [],
        'default_payment_method': None,
        'cash_payment_method': None,
        'mobile_money_methods': [],
        'payment_methods_count': 0,
    }
    
    try:
        # Get all active payment methods
        active_methods = PaymentMethod.get_active_methods()
        context['active_payment_methods'] = active_methods
        context['payment_methods'] = active_methods 
        
        # Get default payment method
        context['default_payment_method'] = PaymentMethod.get_default_method()
        
        # Get cash payment method
        context['cash_payment_method'] = PaymentMethod.get_cash_method()
        
        # Get mobile money methods (very common in SACCOs)
        context['mobile_money_methods'] = PaymentMethod.get_mobile_money_methods()
        
        # Count payment methods
        context['payment_methods_count'] = active_methods.count()
        context['mobile_money_count'] = context['mobile_money_methods'].count()
        
    except Exception as e:
        logger.error(f"Error loading payment methods: {e}")
    
    return context


def tax_rates_context(request):
    """
    Provides current tax rates for SACCO operations.
    """
    context = {
        'wht_interest_rate': None,
        'wht_dividend_rate': None,
        'corporate_tax_rate': None,
        'vat_rate': None,
    }
    
    try:
        today = timezone.now().date()
        
        # Get current tax rates
        context['wht_interest_rate'] = TaxRate.get_wht_interest_rate(today)
        context['wht_dividend_rate'] = TaxRate.get_wht_dividend_rate(today)
        context['corporate_tax_rate'] = TaxRate.get_corporate_tax_rate(today)
        context['vat_rate'] = TaxRate.get_vat_rate(today)
        
    except Exception as e:
        logger.error(f"Error loading tax rates: {e}")
    
    return context


def units_of_measure_context(request):
    """
    Provides active units of measure organized by type.
    """
    context = {
        'active_uoms': [],
        'uom_types': [],
        'uoms_by_type': {},
    }
    
    try:
        # Get all active units
        active_uoms = UnitOfMeasure.objects.filter(is_active=True).order_by('uom_type', 'name')
        context['active_uoms'] = active_uoms
        
        # Get distinct UOM types
        uom_types = active_uoms.values_list('uom_type', flat=True).distinct()
        context['uom_types'] = list(uom_types)
        
        # Organize by type
        for uom_type in uom_types:
            context['uoms_by_type'][uom_type] = active_uoms.filter(uom_type=uom_type)
            
    except Exception as e:
        logger.error(f"Error loading units of measure: {e}")
    
    return context


def member_financial_summary(request):
    """
    Provides high-level financial summary for SACCO dashboard.
    Only loads for authenticated users with appropriate permissions.
    """
    context = {
        'show_financial_summary': False,
        'financial_period_open': False,
        'can_manage_finances': False,
        'can_approve_loans': False,
        'can_process_transactions': False,
    }
    
    if request.user.is_authenticated:
        # Check permissions safely
        is_staff_or_super = request.user.is_staff or request.user.is_superuser
        
        # Try to get profile permissions if available
        try:
            profile = getattr(request.user, 'profile', None)
            if profile:
                # SACCO-specific permissions
                if hasattr(profile, 'can_manage_finances'):
                    context['can_manage_finances'] = profile.can_manage_finances()
                else:
                    context['can_manage_finances'] = is_staff_or_super
                
                if hasattr(profile, 'can_approve_loans'):
                    context['can_approve_loans'] = profile.can_approve_loans()
                else:
                    context['can_approve_loans'] = is_staff_or_super
                
                if hasattr(profile, 'can_process_transactions'):
                    context['can_process_transactions'] = profile.can_process_transactions()
                else:
                    context['can_process_transactions'] = is_staff_or_super
            else:
                context['can_manage_finances'] = is_staff_or_super
                context['can_approve_loans'] = is_staff_or_super
                context['can_process_transactions'] = is_staff_or_super
        except Exception as e:
            logger.debug(f"Error checking profile permissions: {e}")
            context['can_manage_finances'] = is_staff_or_super
            context['can_approve_loans'] = is_staff_or_super
            context['can_process_transactions'] = is_staff_or_super
        
        # Only show summary if user has permissions
        if context['can_manage_finances'] or context['can_approve_loans'] or context['can_process_transactions']:
            context['show_financial_summary'] = True
            
            try:
                # Check if fiscal period is open
                active_period = FiscalPeriod.get_active_period()
                context['financial_period_open'] = (
                    active_period is not None and 
                    not active_period.is_closed and 
                    not active_period.is_locked
                )
                
                # Add current fiscal year info
                active_fiscal_year = FiscalYear.get_active_fiscal_year()
                if active_fiscal_year:
                    context['current_fiscal_year'] = active_fiscal_year.name
                    context['fiscal_year_open'] = not active_fiscal_year.is_closed
                    
            except Exception as e:
                logger.error(f"Error loading financial summary: {e}")
    
    return context


def formatting_helpers(request):
    """
    Provides formatting helper functions for templates.
    """
    def format_currency(amount, include_symbol=True):
        """Format amount as currency using SACCO financial settings"""
        try:
            settings = FinancialSettings.get_instance()
            if settings:
                return settings.format_currency(amount, include_symbol)
            return f"UGX {amount:,.2f}" if include_symbol else f"{amount:,.2f}"
        except Exception as e:
            logger.debug(f"Error formatting currency: {e}")
            return f"UGX {amount:,.2f}" if include_symbol else f"{amount:,.2f}"
    
    def format_percentage(value, decimal_places=2):
        """Format value as percentage"""
        try:
            return f"{float(value):.{decimal_places}f}%"
        except Exception:
            return "0.00%"
    
    def format_number(value, decimal_places=2):
        """Format number with thousand separators"""
        try:
            return f"{float(value):,.{decimal_places}f}"
        except Exception:
            return "0.00"
    
    def format_shares(shares):
        """Format share count"""
        try:
            return f"{int(shares):,}"
        except Exception:
            return "0"
    
    return {
        'format_currency': format_currency,
        'format_percentage': format_percentage,
        'format_number': format_number,
        'format_shares': format_shares,
    }


def system_status(request):
    """
    Provides SACCO system status and configuration alerts.
    """
    context = {
        'system_alerts': [],
        'configuration_complete': True,
        'needs_fiscal_year': False,
        'needs_period': False,
        'needs_payment_methods': False,
        'needs_tax_rates': False,
    }
    
    if request.user.is_authenticated:
        # Check admin status safely
        is_admin = request.user.is_staff or request.user.is_superuser
        
        try:
            profile = getattr(request.user, 'profile', None)
            if profile and hasattr(profile, 'is_admin_user'):
                is_admin = profile.is_admin_user()
        except Exception:
            pass
        
        if is_admin:
            try:
                # Check for active fiscal year
                if not FiscalYear.get_active_fiscal_year():
                    context['needs_fiscal_year'] = True
                    context['configuration_complete'] = False
                    context['system_alerts'].append({
                        'level': 'danger',
                        'message': 'No active fiscal year configured',
                        'action_url': '/core/fiscal-years/',
                        'action_text': 'Set up fiscal year'
                    })
                
                # Check for active period
                if not FiscalPeriod.get_active_period():
                    context['needs_period'] = True
                    # Don't mark as incomplete - periods might be in holiday/break
                    context['system_alerts'].append({
                        'level': 'info',
                        'message': 'No active period (might be holiday/break)',
                        'action_url': '/core/fiscal-years/',
                        'action_text': 'Manage periods'
                    })
                
                # Check for payment methods
                if PaymentMethod.get_active_methods().count() == 0:
                    context['needs_payment_methods'] = True
                    context['configuration_complete'] = False
                    context['system_alerts'].append({
                        'level': 'warning',
                        'message': 'No payment methods configured',
                        'action_url': '/core/payment-methods/',
                        'action_text': 'Add payment methods'
                    })
                
                # Check for WHT tax rates (important for SACCOs)
                wht_interest = TaxRate.get_active_rate('WHT_INTEREST')
                wht_dividend = TaxRate.get_active_rate('WHT_DIVIDEND')
                
                if not wht_interest or not wht_dividend:
                    context['needs_tax_rates'] = True
                    context['system_alerts'].append({
                        'level': 'warning',
                        'message': 'Withholding tax rates not configured',
                        'action_url': '/core/tax-rates/',
                        'action_text': 'Configure tax rates'
                    })
                
                # Check for locked periods that need attention
                locked_count = FiscalPeriod.objects.filter(is_locked=True).count()
                if locked_count > 0:
                    context['system_alerts'].append({
                        'level': 'info',
                        'message': f'{locked_count} period(s) are locked for auditing',
                        'action_url': '/core/fiscal-years/',
                        'action_text': 'View periods'
                    })
                
                # Check if fiscal year ending soon
                fiscal_year = FiscalYear.get_active_fiscal_year()
                if fiscal_year:
                    today = timezone.now().date()
                    days_until_end = (fiscal_year.end_date - today).days
                    
                    if 0 < days_until_end <= 90:
                        context['system_alerts'].append({
                            'level': 'warning',
                            'message': f'Fiscal year {fiscal_year.name} ends in {days_until_end} days',
                            'action_url': '/core/fiscal-years/',
                            'action_text': 'Prepare next fiscal year'
                        })
                    
            except Exception as e:
                logger.error(f"Error checking system status: {e}")
    
    return context


def quick_access_data(request):
    """
    Provides quick access data for common SACCO operations.
    """
    context = {
        'fiscal_years_count': 0,
        'periods_count': 0,
        'active_payment_methods_count': 0,
        'uom_count': 0,
        'active_tax_rates_count': 0,
    }
    
    if request.user.is_authenticated:
        try:
            context['fiscal_years_count'] = FiscalYear.objects.count()
            context['periods_count'] = FiscalPeriod.objects.count()
            context['active_payment_methods_count'] = PaymentMethod.objects.filter(is_active=True).count()
            context['uom_count'] = UnitOfMeasure.objects.filter(is_active=True).count()
            context['active_tax_rates_count'] = TaxRate.objects.filter(is_active=True).count()
        except Exception as e:
            logger.error(f"Error loading quick access data: {e}")
    
    return context


def sacco_branding(request):
    """
    Provides SACCO branding and identification context.
    This can be extended to include logo, colors, etc.
    """
    context = {
        'sacco_name': 'SACCO',  # Default, can be overridden from settings or database
        'system_name': 'SACCO Management System',
    }
    
    try:
        # Try to get SACCO name from configuration or settings
        # You can extend this to read from database or settings
        from django.conf import settings
        
        if hasattr(settings, 'SACCO_NAME'):
            context['sacco_name'] = settings.SACCO_NAME
        
        if hasattr(settings, 'SYSTEM_NAME'):
            context['system_name'] = settings.SYSTEM_NAME
            
    except Exception as e:
        logger.debug(f"Error loading SACCO branding: {e}")
    
    return context