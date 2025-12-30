# core/models.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from utils.models import BaseModel
from django.utils import timezone
from djmoney.models.fields import CurrencyField
import pycountry
from zoneinfo import available_timezones
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# SACCO CONFIGURATION MODEL
# =============================================================================

class SaccoConfiguration(BaseModel):
    """
    Enhanced configuration model for SACCO operational period systems.
    Supports flexible period structures (monthly, quarterly, annual, etc.).
    Singleton model - only one instance allowed per SACCO database.
    """
    
    # -------------------------------------------------------------------------
    # PERIOD SYSTEM CONFIGURATION
    # -------------------------------------------------------------------------
    
    PERIOD_SYSTEM_CHOICES = [
        ('monthly', 'Monthly (12 per year)'),
        ('quarterly', 'Quarterly (4 per year)'),
        ('biannual', 'Biannual (2 per year)'),
        ('annual', 'Annual (1 per year)'),
        ('custom', 'Custom System'),
    ]
    
    period_system = models.CharField(
        "Operational Period System",
        max_length=15,
        choices=PERIOD_SYSTEM_CHOICES,
        default='monthly',
        help_text="The operational period system used by the SACCO"
    )
    
    periods_per_year = models.PositiveIntegerField(
        "Periods Per Year",
        default=12,
        validators=[MinValueValidator(1), MaxValueValidator(52)],
        help_text="Number of operational periods in one fiscal year (1-52)"
    )
    
    # -------------------------------------------------------------------------
    # PERIOD NAMING CONFIGURATION
    # -------------------------------------------------------------------------
    
    period_naming_convention = models.CharField(
        "Period Naming Convention",
        max_length=20,
        choices=[
            ('numeric', 'Numeric (Period 1, Period 2, etc.)'),
            ('ordinal', 'Ordinal (First Period, Second Period, etc.)'),
            ('monthly', 'Monthly (January, February, etc.)'),
            ('quarterly', 'Quarterly (Q1, Q2, Q3, Q4)'),
            ('alpha', 'Alphabetical (Period A, Period B, etc.)'),
            ('roman', 'Roman Numerals (Period I, Period II, etc.)'),
            ('custom', 'Custom Names'),
        ],
        default='monthly'
    )
    
    custom_period_names = models.JSONField(
        "Custom Period Names",
        default=dict,
        blank=True,
        help_text='Custom names for each period position. E.g., {"1": "First Quarter", "2": "Second Quarter"}'
    )

    # -------------------------------------------------------------------------
    # TIMEZONE CONFIGURATION (ADD THIS SECTION)
    # -------------------------------------------------------------------------
    
    operational_timezone = models.CharField(
        "Operational Timezone",
        max_length=63,  # Max length of IANA timezone identifiers (e.g., 'America/Argentina/ComodRivadavia')
        default='Africa/Kampala',
        help_text="Timezone for fiscal periods, deadlines, and automated processes"
    )
    
    # -------------------------------------------------------------------------
    # FISCAL YEAR CONFIGURATION
    # -------------------------------------------------------------------------
    
    MONTH_CHOICES = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]
    
    FISCAL_YEAR_TYPE_CHOICES = [
        ('calendar', 'Calendar Year (Jan-Dec)'),
        ('financial_apr', 'Financial Year April (Apr-Mar)'),
        ('financial_jul', 'Financial Year July (Jul-Jun)'),
        ('financial_oct', 'Financial Year October (Oct-Sep)'),
        ('custom', 'Custom Year Dates'),
    ]
    
    fiscal_year_type = models.CharField(
        "Fiscal Year Type",
        max_length=15,
        choices=FISCAL_YEAR_TYPE_CHOICES,
        default='calendar',
        help_text="When your fiscal year typically runs"
    )
    
    fiscal_year_start_month = models.PositiveIntegerField(
        "Fiscal Year Start Month",
        choices=MONTH_CHOICES,
        default=1,  # January
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Month when fiscal year typically starts (1-12)"
    )
    
    fiscal_year_start_day = models.PositiveIntegerField(
        "Fiscal Year Start Day",
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        help_text="Day when fiscal year typically starts"
    )
    
    # -------------------------------------------------------------------------
    # DIVIDEND SETTINGS
    # -------------------------------------------------------------------------
    
    dividend_calculation_method = models.CharField(
        "Dividend Calculation Method",
        max_length=20,
        choices=[
            ('SHARE_BASED', 'Based on Share Capital'),
            ('SAVINGS_BASED', 'Based on Savings Balance'),
            ('COMBINED', 'Combined (Shares + Savings)'),
        ],
        default='SHARE_BASED',
        help_text="Method used to calculate member dividends"
    )
    
    dividend_distribution_frequency = models.CharField(
        "Dividend Distribution Frequency",
        max_length=15,
        choices=[
            ('ANNUAL', 'Annual'),
            ('BIANNUAL', 'Bi-annual'),
            ('QUARTERLY', 'Quarterly'),
        ],
        default='ANNUAL',
        help_text="How often dividends are distributed to members"
    )
    
    # -------------------------------------------------------------------------
    # COMMUNICATION CONFIGURATION
    # -------------------------------------------------------------------------
    
    enable_automatic_reminders = models.BooleanField(
        "Enable Automatic Reminders",
        default=True,
        help_text="Send automatic payment and deadline reminders"
    )

    enable_sms = models.BooleanField(
        "Enable SMS Notifications",
        default=True,
        help_text="Send SMS notifications to members"
    )

    enable_email_notifications = models.BooleanField(
        "Enable Email Notifications",
        default=True,
        help_text="Send email notifications"
    )
    
    # -------------------------------------------------------------------------
    # VALIDATION METHODS
    # -------------------------------------------------------------------------
    
    def clean(self):
        """Enhanced validation for the configuration"""
        super().clean()
        errors = {}
        
        # Validate periods_per_year matches period_system for non-custom systems
        if self.period_system != 'custom':
            expected_periods = self._get_system_period_count(self.period_system)
            if self.periods_per_year != expected_periods:
                # Auto-correct instead of raising error
                self.periods_per_year = expected_periods
        
        # Validate custom period names if using custom naming
        if self.period_naming_convention == 'custom':
            if not self.custom_period_names:
                errors['custom_period_names'] = 'Custom period names are required when using custom naming convention'
            else:
                # Ensure we have names for all periods
                missing_periods = []
                for i in range(1, self.periods_per_year + 1):
                    if str(i) not in self.custom_period_names:
                        missing_periods.append(str(i))
                
                if missing_periods:
                    errors['custom_period_names'] = f'Missing custom names for periods: {", ".join(missing_periods)}'
        
        # Validate fiscal year dates
        if self.fiscal_year_type == 'custom':
            try:
                # Test if the date is valid
                test_date = date(2024, self.fiscal_year_start_month, self.fiscal_year_start_day)
            except ValueError:
                errors['fiscal_year_start_day'] = 'Invalid fiscal year start date'

        # Validate timezone
        if self.operational_timezone:
            from zoneinfo import ZoneInfo
            try:
                # Try to create a ZoneInfo object to validate
                ZoneInfo(self.operational_timezone)
            except Exception as e:
                errors['operational_timezone'] = f"Invalid timezone: {self.operational_timezone}"
        
        if errors:
            raise ValidationError(errors)
    
    # -------------------------------------------------------------------------
    # HELPER METHODS - PERIOD SYSTEM
    # -------------------------------------------------------------------------
    
    def _get_system_period_count(self, system):
        """Get the standard period count for each system"""
        return {
            'monthly': 12,
            'quarterly': 4,
            'biannual': 2,
            'annual': 1,
            'custom': self.periods_per_year
        }.get(system, 12)
    
    def get_period_count(self):
        """Returns the number of periods per year"""
        if self.period_system == 'custom':
            return self.periods_per_year
        return self._get_system_period_count(self.period_system)
    
    # -------------------------------------------------------------------------
    # PERIOD NAMING METHODS
    # -------------------------------------------------------------------------
    
    def get_period_name(self, position, include_year=False, fiscal_year=None):
        """Enhanced period naming with more options"""
        # Handle None position
        if position is None:
            return None
        
        max_periods = self.get_period_count()
        
        if position > max_periods or position < 1:
            return None
        
        # Handle custom names first
        if self.period_naming_convention == 'custom' and self.custom_period_names:
            base_name = self.custom_period_names.get(str(position))
            if base_name:
                return self._format_period_name(base_name, include_year, fiscal_year)
        
        # Handle different naming conventions
        naming_methods = {
            'quarterly': self._get_quarterly_name,
            'ordinal': self._get_ordinal_name,
            'monthly': self._get_monthly_name,
            'alpha': self._get_alpha_name,
            'roman': self._get_roman_name,
        }
        
        method = naming_methods.get(self.period_naming_convention, self._get_numeric_name)
        base_name = method(position)
        
        return self._format_period_name(base_name, include_year, fiscal_year)
    
    def _format_period_name(self, base_name, include_year=False, fiscal_year=None):
        """Format the period name with optional year"""
        if include_year and fiscal_year:
            return f"{base_name} {fiscal_year}"
        return base_name
    
    def _get_quarterly_name(self, position):
        """Get quarterly naming (Q1, Q2, Q3, Q4)"""
        if self.get_period_count() == 4:
            return f"Q{position}"
        return f"{self._get_period_type_name()} {position}"
    
    def _get_ordinal_name(self, position):
        """Get ordinal names (First, Second, etc.)"""
        ordinals = ['', 'First', 'Second', 'Third', 'Fourth', 'Fifth', 
                   'Sixth', 'Seventh', 'Eighth', 'Ninth', 'Tenth',
                   'Eleventh', 'Twelfth']
        period_type = self._get_period_type_name()
        
        if position < len(ordinals):
            return f"{ordinals[position]} {period_type}"
        return f"{position}th {period_type}"
    
    def _get_monthly_name(self, position):
        """Get monthly names"""
        months = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                 'July', 'August', 'September', 'October', 'November', 'December']
        
        start_month = self.fiscal_year_start_month
        month_index = ((start_month - 1 + position - 1) % 12) + 1
        
        if month_index < len(months):
            return months[month_index]
        return self._get_numeric_name(position)
    
    def _get_alpha_name(self, position):
        """Get alphabetical names (A, B, C, etc.)"""
        import string
        period_type = self._get_period_type_name()
        
        if position <= 26:
            letter = string.ascii_uppercase[position - 1]
            return f"{period_type} {letter}"
        
        first_letter = string.ascii_uppercase[(position - 1) // 26]
        second_letter = string.ascii_uppercase[(position - 1) % 26]
        return f"{period_type} {first_letter}{second_letter}"
    
    def _get_roman_name(self, position):
        """Get Roman numeral names"""
        def int_to_roman(num):
            values = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
            symbols = ['M', 'CM', 'D', 'CD', 'C', 'XC', 'L', 'XL', 'X', 'IX', 'V', 'IV', 'I']
            result = ''
            for i, value in enumerate(values):
                count = num // value
                result += symbols[i] * count
                num -= value * count
            return result
        
        period_type = self._get_period_type_name()
        roman = int_to_roman(position)
        return f"{period_type} {roman}"
    
    def _get_numeric_name(self, position):
        """Get numeric names (Period 1, Period 2, etc.)"""
        period_type = self._get_period_type_name()
        return f"{period_type} {position}"
    
    def _get_period_type_name(self):
        """Period type name getter"""
        type_names = {
            'monthly': 'Month',
            'quarterly': 'Quarter',
            'biannual': 'Half',
            'annual': 'Year',
            'custom': 'Period'
        }
        return type_names.get(self.period_system, 'Period')
    
    def get_period_type_name(self):
        """Get the singular name for the period type"""
        return self._get_period_type_name()

    def get_period_type_name_plural(self):
        """Enhanced plural name getter"""
        singular = self.get_period_type_name()
        
        irregular_plurals = {
            'Month': 'Months',
            'Year': 'Years',
            'Half': 'Halves',
        }
        
        if singular in irregular_plurals:
            return irregular_plurals[singular]
        elif singular.endswith('y'):
            return singular[:-1] + 'ies'
        return singular + 's'
    
    # -------------------------------------------------------------------------
    # UTILITY METHODS
    # -------------------------------------------------------------------------
    
    def is_last_period(self, position):
        """Check if the period position is the last in the fiscal year"""
        return position == self.get_period_count()
    
    def validate_period_number(self, period_number):
        """Validate if a period number is valid for the current system"""
        return 1 <= period_number <= self.get_period_count()
    
    def get_all_period_names(self, include_year=False, fiscal_year=None):
        """Get all period names for the current system"""
        return [
            self.get_period_name(i, include_year, fiscal_year) 
            for i in range(1, self.get_period_count() + 1)
        ]
    
    # -------------------------------------------------------------------------
    # TIMEZONE HELPER METHODS (ADD THESE)
    # -------------------------------------------------------------------------
    
    @staticmethod
    def get_timezone_choices():
        """
        Get ALL available timezone choices from the system.
        Returns sorted list of all IANA timezones.
        
        Returns:
            list: List of tuples (timezone_name, timezone_name)
        """
        # Get all available timezones and sort alphabetically
        all_zones = sorted(available_timezones())
        
        # Return as choices for Django field
        return [(tz, tz) for tz in all_zones]
    
    def get_timezone(self):
        """
        Get the operational timezone as a ZoneInfo object.
        
        Returns:
            ZoneInfo: Timezone object for the configured operational timezone
        """
        from zoneinfo import ZoneInfo
        try:
            return ZoneInfo(self.operational_timezone)
        except Exception as e:
            logger.warning(f"Invalid timezone '{self.operational_timezone}': {e}. Falling back to Africa/Kampala")
            return ZoneInfo('Africa/Kampala')
    
    def get_current_time(self):
        """
        Get current time in SACCO's operational timezone.
        
        Returns:
            datetime: Current datetime in operational timezone
        """
        return timezone.now().astimezone(self.get_timezone())
    
    def get_today(self):
        """
        Get today's date in SACCO's operational timezone.
        
        Returns:
            date: Today's date in operational timezone
        """
        return self.get_current_time().date()
    
    def localize_datetime(self, dt):
        """
        Convert a datetime to SACCO's operational timezone.
        
        Args:
            dt: datetime object (naive or aware)
            
        Returns:
            datetime: Timezone-aware datetime in operational timezone
        """
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        return dt.astimezone(self.get_timezone())
    
    @classmethod
    def get_operational_timezone(cls):
        """
        Class method to get operational timezone.
        
        Returns:
            ZoneInfo: Timezone object for operational timezone
        """
        from zoneinfo import ZoneInfo
        config = cls.get_instance()
        return config.get_timezone() if config else ZoneInfo('Africa/Kampala')
    
    # -------------------------------------------------------------------------
    # SINGLETON PATTERN IMPLEMENTATION
    # -------------------------------------------------------------------------
    
    @classmethod
    def get_instance(cls):
        """
        Get or create the singleton instance of SaccoConfiguration.
        There should only be one SaccoConfiguration instance per SACCO database.
        """
        instance, created = cls.objects.get_or_create(
            pk=1,  # Always use pk=1 for the singleton
            defaults={
                'period_system': 'monthly',
                'periods_per_year': 12,
                'period_naming_convention': 'monthly',
                'custom_period_names': {},
                'fiscal_year_type': 'calendar',
                'fiscal_year_start_month': 1,
                'fiscal_year_start_day': 1,
                'operational_timezone': 'Africa/Kampala',  
                'dividend_calculation_method': 'SHARE_BASED',
                'dividend_distribution_frequency': 'ANNUAL',
                'enable_automatic_reminders': True,
                'enable_sms': True,
                'enable_email_notifications': True,
            }
        )
        return instance
    
    def save(self, *args, **kwargs):
        """
        Override save to ensure only one instance exists (singleton pattern).
        """
        self.pk = 1
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """
        Prevent deletion of the singleton instance.
        """
        pass
    
    @classmethod
    def load(cls):
        """
        Alternative method name for getting the instance.
        Alias for get_instance().
        """
        return cls.get_instance()
    
    @classmethod 
    def get_cached_instance(cls):
        """Get SACCO configuration instance with simple in-memory caching"""
        import threading
        if not hasattr(threading.current_thread(), '_sacco_config_cache'):
            threading.current_thread()._sacco_config_cache = None
        
        cached = threading.current_thread()._sacco_config_cache
        
        if cached is None:
            try:
                cached = cls.get_instance()
                threading.current_thread()._sacco_config_cache = cached
            except Exception as e:
                logger.error(f"Error fetching SACCO configuration: {e}")
                return None
        
        return cached

    @classmethod 
    def clear_cache(cls):
        """Clear the cached configuration instance"""
        import threading
        if hasattr(threading.current_thread(), '_sacco_config_cache'):
            threading.current_thread()._sacco_config_cache = None
    
    def __str__(self):
        return f"SACCO Configuration - {self.get_period_system_display()}"
    
    class Meta:
        verbose_name = "SACCO Configuration"
        verbose_name_plural = "SACCO Configurations"


# =============================================================================
# FINANCIAL SETTINGS MODEL
# =============================================================================

class FinancialSettings(BaseModel):
    """
    Model for managing core financial settings for the SACCO.
    Singleton pattern - only one instance per SACCO database.
    """

    # -------------------------------------------------------------------------
    # CHOICE FIELDS
    # -------------------------------------------------------------------------

    CURRENCY_POSITION_CHOICES = [
        ('BEFORE', 'Before amount (UGX 100.00)'),
        ('AFTER', 'After amount (100.00 UGX)'),
        ('BEFORE_NO_SPACE', 'Before, no space (UGX100.00)'),
        ('AFTER_NO_SPACE', 'After, no space (100.00UGX)'),
    ]

    # -------------------------------------------------------------------------
    # CORE CONFIGURATION
    # -------------------------------------------------------------------------

    sacco_currency = models.CharField(
        "SACCO Primary Currency",
        max_length=3,
        default='UGX',
        help_text="Primary currency for this SACCO (ISO 4217 code)"
    )

    currency_position = models.CharField(
        "Currency Position",
        max_length=20,
        choices=CURRENCY_POSITION_CHOICES,
        default='BEFORE'
    )

    decimal_places = models.PositiveIntegerField(
        "Decimal Places",
        default=2,
        validators=[MinValueValidator(0), MaxValueValidator(4)],
        help_text="Number of decimal places for currency display"
    )

    use_thousand_separator = models.BooleanField(
        "Use Thousand Separator",
        default=True
    )

    # -------------------------------------------------------------------------
    # LOAN SETTINGS
    # -------------------------------------------------------------------------

    default_loan_term_days = models.PositiveIntegerField(
        "Default Loan Term (Days)",
        default=365,
        help_text="Default loan repayment period in days"
    )

    default_interest_rate = models.DecimalField(
        "Default Interest Rate (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal('12.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text="Default annual interest rate percentage"
    )

    late_payment_penalty_rate = models.DecimalField(
        "Late Payment Penalty Rate (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal('2.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text="Monthly penalty rate for late loan payments"
    )

    grace_period_days = models.PositiveIntegerField(
        "Loan Grace Period (Days)",
        default=7,
        help_text="Grace period before late payment penalties apply"
    )

    minimum_loan_amount = models.DecimalField(
        "Minimum Loan Amount",
        max_digits=12,
        decimal_places=2,
        default=Decimal('50000.00'),
        help_text="Minimum amount for loan applications"
    )

    maximum_loan_amount = models.DecimalField(
        "Maximum Loan Amount",
        max_digits=12,
        decimal_places=2,
        default=Decimal('10000000.00'),
        help_text="Maximum amount for loan applications"
    )

    # -------------------------------------------------------------------------
    # SAVINGS SETTINGS
    # -------------------------------------------------------------------------

    minimum_savings_balance = models.DecimalField(
        "Minimum Savings Balance",
        max_digits=12,
        decimal_places=2,
        default=Decimal('10000.00'),
        help_text="Minimum balance required in savings account"
    )

    savings_interest_rate = models.DecimalField(
        "Savings Interest Rate (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal('5.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text="Annual interest rate on savings"
    )

    # -------------------------------------------------------------------------
    # SHARE CAPITAL SETTINGS
    # -------------------------------------------------------------------------

    share_value = models.DecimalField(
        "Share Value",
        max_digits=12,
        decimal_places=2,
        default=Decimal('5000.00'),
        help_text="Value of one share in SACCO currency"
    )

    minimum_shares = models.PositiveIntegerField(
        "Minimum Shares Required",
        default=1,
        help_text="Minimum number of shares a member must own"
    )

    # -------------------------------------------------------------------------
    # WORKFLOW SETTINGS
    # -------------------------------------------------------------------------

    loan_approval_required = models.BooleanField(
        "Loan Approval Required",
        default=True,
        help_text="Loans require approval before disbursement"
    )

    withdrawal_approval_required = models.BooleanField(
        "Withdrawal Approval Required",
        default=False,
        help_text="Large withdrawals require approval"
    )

    withdrawal_approval_limit = models.DecimalField(
        "Withdrawal Approval Limit",
        max_digits=12,
        decimal_places=2,
        default=Decimal('500000.00'),
        help_text="Withdrawals above this amount require approval"
    )

    # -------------------------------------------------------------------------
    # COMMUNICATION SETTINGS
    # -------------------------------------------------------------------------

    send_transaction_notifications = models.BooleanField(
        "Send Transaction Notifications",
        default=True,
        help_text="Send notifications for transactions"
    )

    send_loan_reminders = models.BooleanField(
        "Send Loan Payment Reminders",
        default=True,
        help_text="Send reminders for upcoming loan payments"
    )

    send_dividend_notifications = models.BooleanField(
        "Send Dividend Notifications",
        default=True,
        help_text="Send notifications when dividends are distributed"
    )

    # -------------------------------------------------------------------------
    # CURRENCY HELPER METHODS
    # -------------------------------------------------------------------------

    @staticmethod
    def get_currency_choices():
        """
        Dynamically generate currency choices from pycountry.
        Returns a list of tuples (currency_code, currency_name).
        """
        try:
            currencies = []
            for currency in pycountry.currencies:
                currencies.append((
                    currency.alpha_3,
                    f"{currency.name} ({currency.alpha_3})"
                ))
            return sorted(currencies, key=lambda x: x[1])
        except Exception as e:
            logger.warning(f"Could not load currencies from pycountry: {e}")
            # Fallback to common East African currencies
            return [
                ('UGX', 'Ugandan Shilling (UGX)'),
                ('USD', 'US Dollar (USD)'),
                ('EUR', 'Euro (EUR)'),
                ('GBP', 'British Pound (GBP)'),
                ('KES', 'Kenyan Shilling (KES)'),
                ('TZS', 'Tanzanian Shilling (TZS)'),
                ('RWF', 'Rwandan Franc (RWF)'),
                ('BIF', 'Burundian Franc (BIF)'),
            ]

    # -------------------------------------------------------------------------
    # CORE METHODS
    # -------------------------------------------------------------------------

    @classmethod
    def get_settings(cls):
        """Return the first financial settings instance"""
        return cls.objects.first()

    @classmethod
    def get_sacco_currency(cls):
        """Return SACCO currency code"""
        settings = cls.get_settings()
        return settings.sacco_currency if settings else 'UGX'

    @classmethod
    def get_currency_info(cls):
        """Return full currency configuration"""
        settings = cls.get_settings()
        if settings:
            return {
                'code': settings.sacco_currency,
                'decimal_places': settings.decimal_places,
                'position': settings.currency_position,
                'use_separator': settings.use_thousand_separator,
            }
        return {
            'code': 'UGX',
            'decimal_places': 2,
            'position': 'BEFORE',
            'use_separator': True,
        }

    def format_currency(self, amount, include_symbol=True):
        """Format amount based on SACCO settings"""
        try:
            amount = Decimal(str(amount or 0))
            formatted = f"{amount:,.{self.decimal_places}f}"

            if not self.use_thousand_separator:
                formatted = formatted.replace(',', '')

            if include_symbol:
                symbol = self.sacco_currency
                if self.currency_position == 'BEFORE':
                    return f"{symbol} {formatted}"
                elif self.currency_position == 'AFTER':
                    return f"{formatted} {symbol}"
                elif self.currency_position == 'BEFORE_NO_SPACE':
                    return f"{symbol}{formatted}"
                elif self.currency_position == 'AFTER_NO_SPACE':
                    return f"{formatted}{symbol}"
            return formatted

        except (ValueError, TypeError, InvalidOperation):
            return f"{self.sacco_currency} 0.{'0' * self.decimal_places}"

    @classmethod
    def format_amount(cls, amount, include_symbol=True):
        """Class method to format amount using current settings"""
        settings = cls.get_settings()
        return settings.format_currency(amount, include_symbol) if settings else f"UGX {amount:,.2f}"

    # -------------------------------------------------------------------------
    # VALIDATION METHODS
    # -------------------------------------------------------------------------

    def clean(self):
        """Validate financial settings"""
        super().clean()
        errors = {}

        # Validate currency code
        if self.sacco_currency:
            try:
                # Check if it's a valid ISO 4217 currency code
                currency = pycountry.currencies.get(alpha_3=self.sacco_currency.upper())
                if not currency:
                    errors['sacco_currency'] = f"'{self.sacco_currency}' is not a valid ISO 4217 currency code"
                else:
                    # Normalize to uppercase
                    self.sacco_currency = self.sacco_currency.upper()
            except Exception:
                # If pycountry fails, just ensure it's 3 characters
                if len(self.sacco_currency) != 3:
                    errors['sacco_currency'] = "Currency code must be 3 characters (ISO 4217)"
                else:
                    self.sacco_currency = self.sacco_currency.upper()

        if not (0 <= self.decimal_places <= 4):
            errors['decimal_places'] = "Decimal places must be between 0 and 4"

        if not (0 <= self.default_interest_rate <= 100):
            errors['default_interest_rate'] = "Interest rate must be between 0 and 100"

        if not (0 <= self.late_payment_penalty_rate <= 100):
            errors['late_payment_penalty_rate'] = "Penalty rate must be between 0 and 100"

        if self.minimum_loan_amount <= 0:
            errors['minimum_loan_amount'] = "Minimum loan amount must be positive"

        if self.maximum_loan_amount <= self.minimum_loan_amount:
            errors['maximum_loan_amount'] = "Maximum loan amount must be greater than minimum"

        if self.share_value <= 0:
            errors['share_value'] = "Share value must be positive"

        if errors:
            raise ValidationError(errors)

    # -------------------------------------------------------------------------
    # SINGLETON PATTERN IMPLEMENTATION
    # -------------------------------------------------------------------------
    
    @classmethod
    def get_instance(cls):
        """
        Get or create the singleton instance of FinancialSettings.
        There should only be one FinancialSettings instance per SACCO database.
        """
        instance, created = cls.objects.get_or_create(
            pk=1,  # Always use pk=1 for the singleton
            defaults={
                'sacco_currency': 'UGX',
                'currency_position': 'BEFORE',
                'decimal_places': 2,
                'use_thousand_separator': True,
                'default_loan_term_days': 365,
                'default_interest_rate': Decimal('12.00'),
                'late_payment_penalty_rate': Decimal('2.00'),
                'grace_period_days': 7,
                'minimum_loan_amount': Decimal('50000.00'),
                'maximum_loan_amount': Decimal('10000000.00'),
                'minimum_savings_balance': Decimal('10000.00'),
                'savings_interest_rate': Decimal('5.00'),
                'share_value': Decimal('5000.00'),
                'minimum_shares': 1,
                'loan_approval_required': True,
                'withdrawal_approval_required': False,
                'withdrawal_approval_limit': Decimal('500000.00'),
                'send_transaction_notifications': True,
                'send_loan_reminders': True,
                'send_dividend_notifications': True,
            }
        )
        return instance
    
    def save(self, *args, **kwargs):
        """
        Override save to ensure only one instance exists (singleton pattern).
        """
        self.pk = 1
        self.full_clean()
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """
        Prevent deletion of the singleton instance.
        """
        pass
    
    @classmethod
    def load(cls):
        """
        Alternative method name for getting the instance.
        Alias for get_instance().
        """
        return cls.get_instance()

    def __str__(self):
        return f"Financial Settings - {self.sacco_currency}"

    class Meta:
        verbose_name = "Financial Settings"
        verbose_name_plural = "Financial Settings"


# =============================================================================
# FISCAL YEAR MODEL
# =============================================================================

# FISCAL YEAR MODEL - UPDATED WITH SACCO TIMEZONE

class FiscalYear(BaseModel):
    """
    Fiscal year for SACCO operations.
    Represents the entire year with multiple periods within it.
    """
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('CLOSED', 'Closed'),
        ('LOCKED', 'Locked'),
    ]
    
    # Core fields
    name = models.CharField(
        "Fiscal Year Name",
        max_length=50,
        unique=True,
        help_text="e.g., '2024', '2024/2025', 'FY 2024-2025'"
    )
    
    code = models.CharField(
        "Fiscal Year Code",
        max_length=20,
        unique=True,
        help_text="Short code e.g., 'FY2024', '2024-25'"
    )
    
    # Date range
    start_date = models.DateField(
        "Start Date",
        db_index=True,
        help_text="When this fiscal year begins"
    )
    
    end_date = models.DateField(
        "End Date",
        db_index=True,
        help_text="When this fiscal year ends"
    )
    
    # Status
    status = models.CharField(
        "Status",
        max_length=10,
        choices=STATUS_CHOICES,
        default='DRAFT',
        db_index=True
    )
    
    is_active = models.BooleanField(
        "Is Active",
        default=False,
        db_index=True,
        help_text="Only one fiscal year can be active at a time"
    )
    
    is_closed = models.BooleanField(
        "Is Closed",
        default=False,
        help_text="Fiscal year has been closed and finalized"
    )
    
    is_locked = models.BooleanField(
        "Is Locked",
        default=False,
        help_text="Fiscal year is locked for editing (for auditing)"
    )
    
    # Metadata
    description = models.TextField(
        "Description",
        blank=True,
        help_text="Optional description or notes about this fiscal year"
    )
    
    closed_at = models.DateTimeField(
        "Closed At",
        null=True,
        blank=True,
        help_text="When this fiscal year was closed"
    )
    
    closed_by_id = models.CharField(
        "Closed By",
        max_length=50,
        null=True,
        blank=True,
        help_text="User ID who closed this fiscal year"
    )
    
    class Meta:
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['status']),
            models.Index(fields=['is_active']),
        ]
        verbose_name = "Fiscal Year"
        verbose_name_plural = "Fiscal Years"
    
    def __str__(self):
        return self.name
    
    def clean(self):
        """Validate fiscal year"""
        super().clean()
        errors = {}
        
        # Validate date range
        if self.start_date and self.end_date:
            if self.start_date >= self.end_date:
                errors['end_date'] = "End date must be after start date"
            
            # Check for overlapping fiscal years
            overlapping = FiscalYear.objects.filter(
                models.Q(start_date__lte=self.end_date) & models.Q(end_date__gte=self.start_date)
            ).exclude(pk=self.pk)
            
            if overlapping.exists():
                errors['start_date'] = f"This fiscal year overlaps with: {', '.join([str(fy) for fy in overlapping])}"
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Save with automatic status sync"""
        # Sync status field with boolean flags
        if self.is_locked:
            self.status = 'LOCKED'
        elif self.is_closed:
            self.status = 'CLOSED'
        elif self.is_active:
            self.status = 'ACTIVE'
        else:
            self.status = 'DRAFT'
        
        # Validate before saving
        self.full_clean()
        
        # If setting as active, deactivate other fiscal years
        if self.is_active:
            FiscalYear.objects.exclude(pk=self.pk).update(is_active=False)
        
        super().save(*args, **kwargs)
    
    # -------------------------------------------------------------------------
    # CLASS METHODS
    # -------------------------------------------------------------------------
    
    @classmethod
    def get_active_fiscal_year(cls):
        """Get the currently active fiscal year"""
        return cls.objects.filter(is_active=True).first()
    
    @classmethod
    def get_current_year_name(cls):
        """Get the current fiscal year name"""
        active = cls.get_active_fiscal_year()
        return active.name if active else None
    
    @classmethod
    def get_by_date(cls, check_date):
        """Get fiscal year that contains a specific date"""
        return cls.objects.filter(
            start_date__lte=check_date,
            end_date__gte=check_date
        ).first()

    # -------------------------------------------------------------------------
    # PROGRESS TRACKING METHODS (UPDATED TO USE SACCO TIMEZONE)
    # -------------------------------------------------------------------------

    def get_progress_percentage(self):
        """
        Calculate the progress percentage of this fiscal year using SACCO timezone.
        
        Returns:
            float: Progress percentage (0-100)
        """
        from core.utils import get_sacco_today  # Import here to avoid circular imports
        
        today = get_sacco_today()  # ⭐ USE SACCO TIMEZONE
        duration_days = self.get_duration_days()
        
        # If fiscal year hasn't started yet
        if today < self.start_date:
            return 0.0
        
        # If fiscal year has ended
        if today > self.end_date:
            return 100.0
        
        # Calculate progress
        if duration_days > 0:
            elapsed_days = (today - self.start_date).days
            progress = (elapsed_days / duration_days) * 100
            return round(min(progress, 100.0), 2)
        
        return 0.0
    
    def get_elapsed_days(self):
        """
        Get the number of days elapsed in this fiscal year using SACCO timezone.
        
        Returns:
            int: Days elapsed (0 if not started, duration if ended)
        """
        from core.utils import get_sacco_today  # Import here to avoid circular imports
        
        today = get_sacco_today()  # ⭐ USE SACCO TIMEZONE
        
        if today < self.start_date:
            return 0
        
        if today > self.end_date:
            return self.get_duration_days()
        
        return (today - self.start_date).days
    
    def get_remaining_days(self):
        """
        Get the number of days remaining in this fiscal year using SACCO timezone.
        
        Returns:
            int: Days remaining (0 if ended, duration if not started)
        """
        from core.utils import get_sacco_today  # Import here to avoid circular imports
        
        today = get_sacco_today()  # ⭐ USE SACCO TIMEZONE
        
        if today > self.end_date:
            return 0
        
        if today < self.start_date:
            return self.get_duration_days()
        
        return (self.end_date - today).days
    
    def is_current(self):
        """
        Check if today's date falls within this fiscal year using SACCO timezone.
        
        Returns:
            bool: True if current, False otherwise
        """
        from core.utils import get_sacco_today  # Import here to avoid circular imports
        
        today = get_sacco_today()  # ⭐ USE SACCO TIMEZONE
        return self.start_date <= today <= self.end_date
    
    def is_upcoming(self):
        """
        Check if this fiscal year is upcoming using SACCO timezone.
        (Starts in the future)
        
        Returns:
            bool: True if upcoming, False otherwise
        """
        from core.utils import get_sacco_today  # Import here to avoid circular imports
        
        today = get_sacco_today()  # ⭐ USE SACCO TIMEZONE
        return self.start_date > today
    
    def is_past(self):
        """
        Check if this fiscal year is in the past using SACCO timezone.
        (Already ended)
        
        Returns:
            bool: True if past, False otherwise
        """
        from core.utils import get_sacco_today  # Import here to avoid circular imports
        
        today = get_sacco_today()  # ⭐ USE SACCO TIMEZONE
        return self.end_date < today
    
    def get_status_display_class(self):
        """
        Get CSS class for status display.
        
        Returns:
            str: CSS class name
        """
        if self.is_locked:
            return 'status-locked'
        elif self.is_closed:
            return 'status-closed'
        elif self.is_active:
            return 'status-active'
        else:
            return 'status-draft'
    
    # -------------------------------------------------------------------------
    # INSTANCE METHODS
    # -------------------------------------------------------------------------
    
    def close_fiscal_year(self, user=None):
        """Close this fiscal year using SACCO timezone for timestamp"""
        if self.is_closed:
            return
        
        from core.utils import get_sacco_current_time  # Import here to avoid circular imports
        
        # Close all periods in this fiscal year
        for period in self.periods.all():
            if not period.is_closed:
                period.close_period(user)
        
        self.is_closed = True
        self.is_active = False
        self.status = 'CLOSED'
        self.closed_at = get_sacco_current_time()  # ⭐ USE SACCO TIMEZONE
        
        if user:
            self.closed_by_id = str(user.id) if hasattr(user, 'id') else str(user.pk)
        
        self.save()
    
    def lock_fiscal_year(self):
        """Lock this fiscal year for editing"""
        if not self.is_closed:
            raise ValidationError("Fiscal year must be closed before it can be locked")
        
        # Lock all periods in this fiscal year
        self.periods.all().update(is_locked=True, status='LOCKED')
        
        self.is_locked = True
        self.status = 'LOCKED'
        self.save()
    
    def unlock_fiscal_year(self):
        """Unlock this fiscal year"""
        # Unlock all periods in this fiscal year
        for period in self.periods.all():
            period.unlock_period()
        
        self.is_locked = False
        self.status = 'CLOSED' if self.is_closed else 'DRAFT'
        self.save()
    
    def is_date_in_year(self, check_date):
        """Check if a date falls within this fiscal year"""
        return self.start_date <= check_date <= self.end_date
    
    def get_duration_days(self):
        """Get the duration of this fiscal year in days"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0
    
    def get_duration_weeks(self):
        """Get the duration of this fiscal year in weeks"""
        days = self.get_duration_days()
        return days // 7 if days > 0 else 0
    
    def get_period_count(self):
        """Get the number of periods in this fiscal year"""
        return self.periods.count()
    
    def get_active_period(self):
        """Get the currently active period within this fiscal year"""
        return self.periods.filter(is_active=True).first()
    
    def get_all_periods(self):
        """Get all periods in this fiscal year, ordered by period number"""
        return self.periods.all().order_by('period_number')
    
    def can_be_deleted(self):
        """Check if this fiscal year can be deleted"""
        # Can't delete if it has periods
        return self.get_period_count() == 0
    
    def get_closed_by(self):
        """Get user who closed this fiscal year"""
        if not self.closed_by_id:
            return None
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            return User.objects.using('default').get(id=self.closed_by_id)
        except Exception as e:
            logger.error(f"Error fetching closed_by user: {e}")
            return None

    @property
    def closed_by_name(self):
        """Get name of user who closed fiscal year"""
        user = self.get_closed_by()
        if user:
            return user.get_full_name() or user.username
        return "System"

# =============================================================================
# PERIOD MODEL
# =============================================================================

class FiscalPeriod(BaseModel):
    """
    Financial period within a fiscal year.
    Represents subdivisions like months, quarters, etc.
    """
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('CLOSED', 'Closed'),
        ('LOCKED', 'Locked'),
    ]
    
    # Foreign key to fiscal year
    fiscal_year = models.ForeignKey(
        FiscalYear,
        on_delete=models.PROTECT,
        related_name='periods',
        help_text="The fiscal year this period belongs to"
    )
    
    # Core fields
    name = models.CharField(
        "Period Name",
        max_length=100,
        help_text="e.g., 'January', 'Q1', 'Month 1'"
    )
    
    period_number = models.PositiveIntegerField(
        "Period Number",
        validators=[MinValueValidator(1)],
        db_index=True,
        help_text="Sequential number within the fiscal year (1, 2, 3, etc.)"
    )
    
    # Date range
    start_date = models.DateField(
        "Start Date",
        db_index=True,
        help_text="When this period begins"
    )
    
    end_date = models.DateField(
        "End Date",
        db_index=True,
        help_text="When this period ends"
    )
    
    # Status
    status = models.CharField(
        "Status",
        max_length=10,
        choices=STATUS_CHOICES,
        default='DRAFT',
        db_index=True
    )
    
    is_active = models.BooleanField(
        "Is Active",
        default=False,
        db_index=True,
        help_text="Only one period can be active at a time across all fiscal years"
    )
    
    is_closed = models.BooleanField(
        "Is Closed",
        default=False,
        help_text="Period has been closed and finalized"
    )
    
    is_locked = models.BooleanField(
        "Is Locked",
        default=False,
        help_text="Period is locked for editing (for auditing)"
    )
    
    # Metadata
    description = models.TextField(
        "Description",
        blank=True,
        help_text="Optional description or notes about this period"
    )
    
    closed_at = models.DateTimeField(
        "Closed At",
        null=True,
        blank=True,
        help_text="When this period was closed"
    )
    
    closed_by_id = models.CharField(
        "Closed By",
        max_length=50,
        null=True,
        blank=True,
        help_text="User ID who closed this period"
    )
    
    class Meta:
        ordering = ['-fiscal_year__start_date', 'period_number']
        unique_together = [['fiscal_year', 'period_number']]
        indexes = [
            models.Index(fields=['fiscal_year', 'period_number']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['status']),
            models.Index(fields=['is_active']),
        ]
        verbose_name = "Period"
        verbose_name_plural = "Periods"
    
    def __str__(self):
        return f"{self.name} ({self.fiscal_year.name})"
    
    def clean(self):
        """Validate period"""
        super().clean()
        errors = {}
        
        # Validate date range
        if self.start_date and self.end_date:
            if self.start_date >= self.end_date:
                errors['end_date'] = "End date must be after start date"
        
        # Validate period falls within fiscal year
        if self.fiscal_year and self.start_date and self.end_date:
            if self.start_date < self.fiscal_year.start_date:
                errors['start_date'] = f"Period must start on or after fiscal year start date ({self.fiscal_year.start_date})"
            if self.end_date > self.fiscal_year.end_date:
                errors['end_date'] = f"Period must end on or before fiscal year end date ({self.fiscal_year.end_date})"
        
        # Validate period number
        if self.period_number:
            config = SaccoConfiguration.get_instance()
            if config and not config.validate_period_number(self.period_number):
                errors['period_number'] = f"Period number must be between 1 and {config.get_period_count()}"
        
        # Check for overlapping periods within same fiscal year
        if self.fiscal_year and self.start_date and self.end_date:
            overlapping = FiscalPeriod.objects.filter(
                fiscal_year=self.fiscal_year,
                start_date__lt=self.end_date,
                end_date__gt=self.start_date
            ).exclude(pk=self.pk)
            
            if overlapping.exists():
                errors['start_date'] = f"This period overlaps with: {', '.join([str(p) for p in overlapping])}"
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Save with automatic status sync"""
        # Sync status field with boolean flags
        if self.is_locked:
            self.status = 'LOCKED'
        elif self.is_closed:
            self.status = 'CLOSED'
        elif self.is_active:
            self.status = 'ACTIVE'
        else:
            self.status = 'DRAFT'
        
        # Validate before saving
        self.full_clean()
        
        # If setting as active, deactivate other periods
        if self.is_active:
            FiscalPeriod.objects.exclude(pk=self.pk).update(is_active=False)
        
        super().save(*args, **kwargs)
    
    # -------------------------------------------------------------------------
    # CLASS METHODS
    # -------------------------------------------------------------------------
    
    @classmethod
    def get_active_period(cls):
        """Get the currently active period"""
        return cls.objects.filter(is_active=True).first()
    
    @classmethod
    def get_current_fiscal_year(cls):
        """Get the fiscal year of the currently active period"""
        active = cls.get_active_period()
        return active.fiscal_year if active else None
    
    @classmethod
    def get_by_date(cls, check_date):
        """Get period that contains a specific date"""
        return cls.objects.filter(
            start_date__lte=check_date,
            end_date__gte=check_date
        ).first()
    
    @classmethod
    def get_periods_for_year(cls, fiscal_year):
        """Get all periods for a specific fiscal year"""
        return cls.objects.filter(fiscal_year=fiscal_year).order_by('period_number')
    
    # -------------------------------------------------------------------------
    # PROGRESS TRACKING METHODS (UPDATED TO USE SACCO TIMEZONE)
    # -------------------------------------------------------------------------
    
    def get_progress_percentage(self):
        """
        Calculate the progress percentage of this period using SACCO timezone.
        
        Returns:
            float: Progress percentage (0-100)
        """
        from core.utils import get_sacco_today  # Import here to avoid circular imports
        
        today = get_sacco_today()  # ⭐ USE SACCO TIMEZONE
        duration_days = self.get_duration_days()
        
        # If period hasn't started yet
        if today < self.start_date:
            return 0.0
        
        # If period has ended
        if today > self.end_date:
            return 100.0
        
        # Calculate progress
        if duration_days > 0:
            elapsed_days = (today - self.start_date).days
            progress = (elapsed_days / duration_days) * 100
            return round(min(progress, 100.0), 2)
        
        return 0.0
    
    def get_elapsed_days(self):
        """
        Get the number of days elapsed in this period using SACCO timezone.
        
        Returns:
            int: Days elapsed (0 if not started, duration if ended)
        """
        from core.utils import get_sacco_today  # Import here to avoid circular imports
        
        today = get_sacco_today()  # ⭐ USE SACCO TIMEZONE
        
        if today < self.start_date:
            return 0
        
        if today > self.end_date:
            return self.get_duration_days()
        
        return (today - self.start_date).days
    
    def get_remaining_days(self):
        """
        Get the number of days remaining in this period using SACCO timezone.
        
        Returns:
            int: Days remaining (0 if ended, duration if not started)
        """
        from core.utils import get_sacco_today  # Import here to avoid circular imports
        
        today = get_sacco_today()  # ⭐ USE SACCO TIMEZONE
        
        if today > self.end_date:
            return 0
        
        if today < self.start_date:
            return self.get_duration_days()
        
        return (self.end_date - today).days
    
    def is_current_period(self):
        """
        Check if this is the current period using SACCO timezone.
        (Today falls within date range and is active)
        
        Returns:
            bool: True if current period, False otherwise
        """
        from core.utils import get_sacco_today  # Import here to avoid circular imports
        
        today = get_sacco_today()  # ⭐ USE SACCO TIMEZONE
        return self.start_date <= today <= self.end_date and self.is_active
    
    def is_current(self):
        """
        Alias for is_current_period() for consistency.
        
        Returns:
            bool: True if current, False otherwise
        """
        return self.is_current_period()
    
    def is_upcoming(self):
        """
        Check if this period is upcoming using SACCO timezone.
        (Starts in the future)
        
        Returns:
            bool: True if upcoming, False otherwise
        """
        from core.utils import get_sacco_today  # Import here to avoid circular imports
        
        today = get_sacco_today()  # ⭐ USE SACCO TIMEZONE
        return self.start_date > today
    
    def is_past(self):
        """
        Check if this period is in the past using SACCO timezone.
        (Already ended)
        
        Returns:
            bool: True if past, False otherwise
        """
        from core.utils import get_sacco_today  # Import here to avoid circular imports
        
        today = get_sacco_today()  # ⭐ USE SACCO TIMEZONE
        return self.end_date < today
    
    def get_status_display_class(self):
        """
        Get CSS class for status display.
        
        Returns:
            str: CSS class name
        """
        if self.is_locked:
            return 'status-locked'
        elif self.is_closed:
            return 'status-closed'
        elif self.is_active:
            return 'status-active'
        else:
            return 'status-draft'
    
    # -------------------------------------------------------------------------
    # INSTANCE METHODS
    # -------------------------------------------------------------------------
    
    def close_period(self, user=None):
        """Close this period using SACCO timezone for timestamp"""
        if self.is_closed:
            return
        
        from core.utils import get_sacco_current_time  # Import here to avoid circular imports
        
        self.is_closed = True
        self.is_active = False
        self.status = 'CLOSED'
        self.closed_at = get_sacco_current_time()  # ⭐ USE SACCO TIMEZONE
        
        if user:
            self.closed_by_id = str(user.id) if hasattr(user, 'id') else str(user.pk)
        
        self.save()
    
    def lock_period(self):
        """Lock this period for editing"""
        if not self.is_closed:
            raise ValidationError("Period must be closed before it can be locked")
        
        self.is_locked = True
        self.status = 'LOCKED'
        self.save()
    
    def unlock_period(self):
        """Unlock this period"""
        self.is_locked = False
        self.status = 'CLOSED' if self.is_closed else 'DRAFT'
        self.save()
    
    def is_date_in_period(self, check_date):
        """Check if a date falls within this period"""
        return self.start_date <= check_date <= self.end_date
    
    def get_duration_days(self):
        """Get the duration of this period in days"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0
    
    def get_duration_weeks(self):
        """Get the duration of this period in weeks"""
        days = self.get_duration_days()
        return days // 7 if days > 0 else 0
    
    def is_last_period(self):
        """Check if this is the last period in the fiscal year"""
        config = SaccoConfiguration.get_instance()
        if config:
            return self.period_number == config.get_period_count()
        return False
    
    def get_next_period(self):
        """Get the next period in sequence"""
        return FiscalPeriod.objects.filter(
            fiscal_year=self.fiscal_year,
            period_number=self.period_number + 1
        ).first()
    
    def get_previous_period(self):
        """Get the previous period in sequence"""
        return FiscalPeriod.objects.filter(
            fiscal_year=self.fiscal_year,
            period_number=self.period_number - 1
        ).first()
    
    def can_be_deleted(self):
        """Check if this period can be deleted"""
        # Can't delete if closed or locked
        if self.is_closed or self.is_locked:
            return False
        # Additional checks for transactions should be added here
        return True
    
    def get_closed_by(self):
        """Get user who closed this period"""
        if not self.closed_by_id:
            return None
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            return User.objects.using('default').get(id=self.closed_by_id)
        except Exception as e:
            logger.error(f"Error fetching closed_by user: {e}")
            return None

    @property
    def closed_by_name(self):
        """Get name of user who closed period"""
        user = self.get_closed_by()
        if user:
            return user.get_full_name() or user.username
        return "System"
    
# =============================================================================
# PAYMENT METHOD MODEL
# =============================================================================

class PaymentMethod(BaseModel):
    """
    Payment methods available for SACCO transactions.
    Supports cash, mobile money, bank transfers, and other payment channels.
    """
    
    METHOD_TYPE_CHOICES = [
        ('CASH', 'Cash'),
        ('MOBILE_MONEY', 'Mobile Money'),
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('CHEQUE', 'Cheque'),
        ('CARD', 'Card Payment'),
        ('DIRECT_DEBIT', 'Direct Debit'),
        ('STANDING_ORDER', 'Standing Order'),
        ('OTHER', 'Other'),
    ]
    
    MOBILE_MONEY_PROVIDER_CHOICES = [
        ('MTN', 'MTN Mobile Money'),
        ('AIRTEL', 'Airtel Money'),
        ('AFRICELL', 'Africell Money'),
        ('OTHER', 'Other Provider'),
    ]
    
    # Core fields
    name = models.CharField(
        "Payment Method Name",
        max_length=100,
        help_text="e.g., 'MTN Mobile Money', 'Cash', 'Bank Transfer - Stanbic'"
    )
    
    method_type = models.CharField(
        "Method Type",
        max_length=20,
        choices=METHOD_TYPE_CHOICES,
        db_index=True
    )
    
    code = models.CharField(
        "Method Code",
        max_length=20,
        unique=True,
        help_text="Unique code for this payment method (e.g., 'MTN_MM', 'CASH', 'BNK_STANBIC')"
    )
    
    # Mobile Money specific fields
    mobile_money_provider = models.CharField(
        "Mobile Money Provider",
        max_length=20,
        choices=MOBILE_MONEY_PROVIDER_CHOICES,
        blank=True,
        null=True,
        help_text="Only for mobile money payment methods"
    )
    
    # Bank specific fields
    bank_name = models.CharField(
        "Bank Name",
        max_length=100,
        blank=True,
        help_text="Bank name for bank transfer methods"
    )
    
    bank_account_number = models.CharField(
        "Bank Account Number",
        max_length=50,
        blank=True,
        help_text="SACCO's bank account number for this method"
    )
    
    bank_branch = models.CharField(
        "Bank Branch",
        max_length=100,
        blank=True
    )
    
    swift_code = models.CharField(
        "SWIFT/BIC Code",
        max_length=20,
        blank=True,
        help_text="For international transfers"
    )
    
    # Status and configuration
    is_active = models.BooleanField(
        "Is Active",
        default=True,
        db_index=True,
        help_text="Whether this payment method is currently available"
    )
    
    is_default = models.BooleanField(
        "Is Default",
        default=False,
        help_text="Default payment method for transactions"
    )
    
    requires_approval = models.BooleanField(
        "Requires Approval",
        default=False,
        help_text="Transactions using this method require approval"
    )
    
    # Transaction limits
    minimum_amount = models.DecimalField(
        "Minimum Transaction Amount",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Minimum amount for transactions using this method"
    )
    
    maximum_amount = models.DecimalField(
        "Maximum Transaction Amount",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Maximum amount for transactions using this method"
    )
    
    daily_limit = models.DecimalField(
        "Daily Transaction Limit",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Total daily limit for this payment method"
    )
    
    # Fees and charges
    has_transaction_fee = models.BooleanField(
        "Has Transaction Fee",
        default=False,
        help_text="Whether this payment method incurs transaction fees"
    )
    
    transaction_fee_type = models.CharField(
        "Transaction Fee Type",
        max_length=20,
        choices=[
            ('FIXED', 'Fixed Amount'),
            ('PERCENTAGE', 'Percentage of Amount'),
            ('TIERED', 'Tiered (Based on Amount)'),
        ],
        blank=True,
        null=True
    )
    
    transaction_fee_amount = models.DecimalField(
        "Transaction Fee Amount",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Fixed fee amount or percentage rate"
    )
    
    fee_bearer = models.CharField(
        "Fee Bearer",
        max_length=20,
        choices=[
            ('MEMBER', 'Member Pays'),
            ('SACCO', 'SACCO Pays'),
            ('SHARED', 'Shared'),
        ],
        default='MEMBER',
        blank=True
    )
    
    # Processing information
    processing_time = models.CharField(
        "Processing Time",
        max_length=100,
        blank=True,
        help_text="e.g., 'Instant', '1-2 business days', '3-5 working days'"
    )
    
    requires_reference = models.BooleanField(
        "Requires Reference Number",
        default=False,
        help_text="Transactions require a reference/transaction ID"
    )
    
    # API/Integration fields
    api_enabled = models.BooleanField(
        "API Enabled",
        default=False,
        help_text="Payment method has API integration"
    )
    
    api_endpoint = models.URLField(
        "API Endpoint",
        blank=True,
        help_text="API endpoint for this payment method"
    )
    
    api_key = models.CharField(
        "API Key",
        max_length=255,
        blank=True,
        help_text="Encrypted API key for integration"
    )
    
    # Display and UI
    icon = models.CharField(
        "Icon CSS Class",
        max_length=50,
        blank=True,
        help_text="CSS class for payment method icon (e.g., 'fa-mobile', 'fa-money-bill')"
    )
    
    color_code = models.CharField(
        "Color Code",
        max_length=7,
        blank=True,
        help_text="Hex color code for UI display (e.g., '#FFCB05' for MTN yellow)"
    )
    
    display_order = models.PositiveIntegerField(
        "Display Order",
        default=0,
        help_text="Order in which to display this payment method"
    )
    
    # Instructions and help text
    instructions = models.TextField(
        "Payment Instructions",
        blank=True,
        help_text="Instructions for members on how to use this payment method"
    )
    
    notes = models.TextField(
        "Internal Notes",
        blank=True,
        help_text="Internal notes about this payment method (not shown to members)"
    )
    
    class Meta:
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['method_type', 'is_active']),
            models.Index(fields=['is_active', 'display_order']),
            models.Index(fields=['code']),
        ]
        verbose_name = "Payment Method"
        verbose_name_plural = "Payment Methods"
    
    def __str__(self):
        return f"{self.name} ({self.get_method_type_display()})"
    
    def clean(self):
        """Validate payment method"""
        super().clean()
        errors = {}
        
        # Validate mobile money provider for mobile money methods
        if self.method_type == 'MOBILE_MONEY' and not self.mobile_money_provider:
            errors['mobile_money_provider'] = "Mobile money provider is required for mobile money payment methods"
        
        # CHANGED: Make bank fields optional - they can be added later
        if self.method_type == 'BANK_TRANSFER':
            # Bank fields are now optional
            pass
        
        # Validate transaction limits
        if self.minimum_amount and self.maximum_amount:
            if self.minimum_amount >= self.maximum_amount:
                errors['maximum_amount'] = "Maximum amount must be greater than minimum amount"
        
        # Validate transaction fee configuration
        if self.has_transaction_fee:
            if not self.transaction_fee_type:
                errors['transaction_fee_type'] = "Transaction fee type is required when fees are enabled"
            if not self.transaction_fee_amount:
                errors['transaction_fee_amount'] = "Transaction fee amount is required when fees are enabled"
        
        # Validate color code format
        if self.color_code:
            import re
            if not re.match(r'^#[0-9A-Fa-f]{6}$', self.color_code):
                errors['color_code'] = "Color code must be a valid hex color (e.g., #FFCB05)"
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Save with validation and auto-uppercase code"""
        # Auto-uppercase the code
        if self.code:
            self.code = self.code.upper().replace(' ', '_')
        
        # If setting as default, unset other defaults
        if self.is_default:
            PaymentMethod.objects.exclude(pk=self.pk).update(is_default=False)
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    # -------------------------------------------------------------------------
    # QUERY METHODS
    # -------------------------------------------------------------------------
    
    @classmethod
    def get_active_methods(cls):
        """Get all active payment methods"""
        return cls.objects.filter(is_active=True).order_by('display_order', 'name')
    
    @classmethod
    def get_default_method(cls):
        """Get the default payment method"""
        return cls.objects.filter(is_active=True, is_default=True).first()
    
    @classmethod
    def get_mobile_money_methods(cls):
        """Get all active mobile money payment methods"""
        return cls.objects.filter(
            method_type='MOBILE_MONEY',
            is_active=True
        ).order_by('display_order')
    
    @classmethod
    def get_cash_method(cls):
        """Get cash payment method"""
        return cls.objects.filter(method_type='CASH', is_active=True).first()
    
    @classmethod
    def get_by_code(cls, code):
        """Get payment method by code"""
        return cls.objects.filter(code=code.upper(), is_active=True).first()
    
    # -------------------------------------------------------------------------
    # TRANSACTION FEE METHODS
    # -------------------------------------------------------------------------
    
    def calculate_transaction_fee(self, amount):
        """
        Calculate transaction fee for a given amount.
        
        Args:
            amount: Transaction amount
            
        Returns:
            Decimal: Transaction fee amount
        """
        if not self.has_transaction_fee:
            return Decimal('0.00')
        
        amount = Decimal(str(amount))
        
        if self.transaction_fee_type == 'FIXED':
            return self.transaction_fee_amount or Decimal('0.00')
        
        elif self.transaction_fee_type == 'PERCENTAGE':
            rate = (self.transaction_fee_amount or Decimal('0.00')) / Decimal('100')
            return (amount * rate).quantize(Decimal('0.01'))
        
        elif self.transaction_fee_type == 'TIERED':
            # For tiered fees, implement based on your fee structure
            return Decimal('0.00')
        
        return Decimal('0.00')
    
    def get_total_amount_with_fee(self, amount):
        """
        Get total amount including transaction fee.
        
        Args:
            amount: Base transaction amount
            
        Returns:
            tuple: (total_amount, fee_amount)
        """
        fee = self.calculate_transaction_fee(amount)
        
        if self.fee_bearer == 'MEMBER':
            total = Decimal(str(amount)) + fee
            return total, fee
        else:
            return Decimal(str(amount)), fee
    
    # -------------------------------------------------------------------------
    # VALIDATION METHODS
    # -------------------------------------------------------------------------
    
    def validate_transaction_amount(self, amount):
        """
        Validate if transaction amount is within limits.
        
        Args:
            amount: Transaction amount to validate
            
        Returns:
            tuple: (is_valid, error_message)
        """
        amount = Decimal(str(amount))
        
        if self.minimum_amount and amount < self.minimum_amount:
            return False, f"Amount is below minimum of {self.minimum_amount}"
        
        if self.maximum_amount and amount > self.maximum_amount:
            return False, f"Amount exceeds maximum of {self.maximum_amount}"
        
        return True, None
    
    def is_available_for_amount(self, amount):
        """Check if payment method is available for given amount"""
        if not self.is_active:
            return False
        
        is_valid, _ = self.validate_transaction_amount(amount)
        return is_valid
    
    def can_process_transaction(self):
        """Check if payment method can currently process transactions"""
        return self.is_active and not self.requires_approval
    
    # -------------------------------------------------------------------------
    # DISPLAY METHODS
    # -------------------------------------------------------------------------
    
    def get_display_name(self):
        """Get formatted display name for UI"""
        if self.method_type == 'MOBILE_MONEY' and self.mobile_money_provider:
            return f"{self.get_mobile_money_provider_display()}"
        return self.name
    
    def get_icon_html(self):
        """Get HTML for payment method icon"""
        if self.icon:
            style = f"color: {self.color_code};" if self.color_code else ""
            return f'<i class="{self.icon}" style="{style}"></i>'
        return ''
    
    def get_fee_display(self):
        """Get human-readable fee information"""
        if not self.has_transaction_fee:
            return "No fees"
        
        if self.transaction_fee_type == 'FIXED':
            return f"Fee: {self.transaction_fee_amount}"
        elif self.transaction_fee_type == 'PERCENTAGE':
            return f"Fee: {self.transaction_fee_amount}%"
        elif self.transaction_fee_type == 'TIERED':
            return "Tiered fees apply"
        
        return "Fees apply"


# =============================================================================
# TAX RATE MODEL
# =============================================================================

class TaxRate(BaseModel):
    """Tax rate configuration for SACCO operations"""
    
    TAX_TYPE_CHOICES = [
        ('WHT_INTEREST', 'Withholding Tax on Interest'),
        ('WHT_DIVIDEND', 'Withholding Tax on Dividend'),
        ('CORPORATE', 'Corporate Income Tax'),
        ('VAT', 'Value Added Tax'),
        ('LOCAL_SERVICE', 'Local Service Tax'),
        ('STAMP_DUTY', 'Stamp Duty'),
        ('OTHER', 'Other Tax'),
    ]
    
    # Core fields
    name = models.CharField(
        "Tax Name",
        max_length=100,
        help_text="e.g., 'WHT on Savings Interest', 'Corporate Tax Rate'"
    )
    
    tax_type = models.CharField(
        "Tax Type",
        max_length=20,
        choices=TAX_TYPE_CHOICES,
        db_index=True
    )
    
    rate = models.DecimalField(
        "Tax Rate (%)",
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text="Tax rate as percentage (e.g., 15.00 for 15%)"
    )
    
    # Validity period
    effective_from = models.DateField(
        "Effective From",
        db_index=True,
        help_text="Date when this tax rate becomes effective"
    )
    
    effective_to = models.DateField(
        "Effective To",
        null=True,
        blank=True,
        db_index=True,
        help_text="Date when this tax rate expires (leave blank for indefinite)"
    )
    
    # Status
    is_active = models.BooleanField(
        "Is Active",
        default=True,
        db_index=True,
        help_text="Whether this tax rate is currently in use"
    )
    
    # Additional configuration
    applies_to_members = models.BooleanField(
        "Applies to Members",
        default=True,
        help_text="Tax applies to member transactions"
    )
    
    applies_to_sacco = models.BooleanField(
        "Applies to SACCO",
        default=False,
        help_text="Tax applies to SACCO operations"
    )
    
    # Metadata
    description = models.TextField(
        "Description",
        blank=True,
        help_text="Additional details about this tax rate"
    )
    
    legal_reference = models.CharField(
        "Legal Reference",
        max_length=255,
        blank=True,
        help_text="Legal or regulatory reference for this tax"
    )
    
    class Meta:
        ordering = ['-effective_from', 'tax_type']
        indexes = [
            models.Index(fields=['tax_type', 'effective_from']),
            models.Index(fields=['is_active', 'effective_from']),
        ]
        verbose_name = "Tax Rate"
        verbose_name_plural = "Tax Rates"
    
    def __str__(self):
        return f"{self.name} - {self.rate}%"
    
    def clean(self):
        """Validate tax rate"""
        super().clean()
        errors = {}
        
        # Validate rate
        if not (0 <= self.rate <= 100):
            errors['rate'] = "Tax rate must be between 0 and 100"
        
        # Validate date range
        if self.effective_to and self.effective_from:
            if self.effective_to <= self.effective_from:
                errors['effective_to'] = "Effective to date must be after effective from date"
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Save with validation"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    @classmethod
    def get_active_rate(cls, tax_type, as_of_date=None):
        """Get the active tax rate for a specific type"""
        if as_of_date is None:
            as_of_date = timezone.now().date()
        
        return cls.objects.filter(
            tax_type=tax_type,
            is_active=True,
            effective_from__lte=as_of_date
        ).filter(
            models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=as_of_date)
        ).first()
    
    @classmethod
    def get_wht_interest_rate(cls, as_of_date=None):
        """Get WHT rate on interest"""
        rate_obj = cls.get_active_rate('WHT_INTEREST', as_of_date)
        return rate_obj.rate if rate_obj else Decimal('15.00')  # Default 15%
    
    @classmethod
    def get_wht_dividend_rate(cls, as_of_date=None):
        """Get WHT rate on dividends"""
        rate_obj = cls.get_active_rate('WHT_DIVIDEND', as_of_date)
        return rate_obj.rate if rate_obj else Decimal('15.00')  # Default 15%
    
    @classmethod
    def get_corporate_tax_rate(cls, as_of_date=None):
        """Get corporate tax rate"""
        rate_obj = cls.get_active_rate('CORPORATE', as_of_date)
        return rate_obj.rate if rate_obj else Decimal('30.00')  # Default 30%
    
    @classmethod
    def get_vat_rate(cls, as_of_date=None):
        """Get VAT rate"""
        rate_obj = cls.get_active_rate('VAT', as_of_date)
        return rate_obj.rate if rate_obj else Decimal('18.00')  # Default 18%
    
    def is_valid_on_date(self, check_date):
        """Check if this tax rate is valid on a specific date"""
        if not self.is_active:
            return False
        
        if check_date < self.effective_from:
            return False
        
        if self.effective_to and check_date > self.effective_to:
            return False
        
        return True
    
    def is_effective(self, check_date=None):
        """
        Check if this tax rate is currently effective.
        Alias for is_valid_on_date() for better readability.
        
        Args:
            check_date: Date to check (defaults to today)
            
        Returns:
            bool: True if effective on the given date, False otherwise
        """
        if check_date is None:
            check_date = timezone.now().date()
        
        return self.is_valid_on_date(check_date)
    
    def get_rate_decimal(self):
        """Get rate as decimal (for calculations)"""
        return self.rate / Decimal('100')
    
    def calculate_tax(self, amount):
        """Calculate tax for given amount"""
        try:
            amount = Decimal(str(amount))
            return (amount * self.get_rate_decimal()).quantize(Decimal('0.01'))
        except (ValueError, InvalidOperation):
            return Decimal('0.00')
    
    def get_status_display_class(self):
        """
        Get CSS class for status display based on effectiveness.
        
        Returns:
            str: CSS class name
        """
        if not self.is_active:
            return 'status-inactive'
        elif self.is_effective():
            return 'status-effective'
        else:
            return 'status-scheduled'


# =============================================================================
# UNITS OF MEASURE
# =============================================================================

class UnitOfMeasure(BaseModel):
    """Model for different units of measurement used by the SACCO"""
    
    UOM_TYPE_CHOICES = [
        ('LENGTH', 'Length'),
        ('WEIGHT', 'Weight'),
        ('VOLUME', 'Volume'),
        ('AREA', 'Area'), 
        ('QUANTITY', 'Quantity'),
        ('TIME', 'Time'),
        ('OTHER', 'Other')
    ]
    
    # Basic information
    name = models.CharField("Name", max_length=50)
    abbreviation = models.CharField("Abbreviation", max_length=10)
    symbol = models.CharField("Symbol", max_length=10, blank=True, null=True)
    description = models.TextField("Description", blank=True, null=True)
    
    # Categorization
    uom_type = models.CharField("UOM Type", max_length=20, choices=UOM_TYPE_CHOICES)
    
    # Conversion information
    base_unit = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='derived_units',
        verbose_name="Base Unit",
        help_text="The base unit this unit is derived from"
    )
    conversion_factor = models.DecimalField(
        "Conversion Factor",
        max_digits=16, 
        decimal_places=6, 
        default=1.0,
        validators=[MinValueValidator(Decimal('0.000001'))],
        help_text="Multiply by this factor to convert to the base unit"
    )
    
    # Status
    is_active = models.BooleanField("Is Active", default=True)
    
    def clean(self):
        """Enhanced validation"""
        super().clean()
        errors = {}
        
        # Cannot be its own base unit
        if self.base_unit == self:
            errors['base_unit'] = 'Unit cannot be its own base unit'
        
        # Conversion factor must be positive
        if self.conversion_factor <= 0:
            errors['conversion_factor'] = 'Conversion factor must be positive'
        
        if errors:
            raise ValidationError(errors)
    
    def convert_to_base(self, value):
        """Convert a value from this unit to the base unit"""
        if not self.base_unit:
            return value
        return float(value) * float(self.conversion_factor)
    
    def convert_from_base(self, value):
        """Convert a value from the base unit to this unit"""
        if not self.base_unit:
            return value
        return float(value) / float(self.conversion_factor)
    
    def convert_to_unit(self, value, target_unit):
        """Convert a value from this unit to another unit of the same type"""
        if not isinstance(target_unit, UnitOfMeasure):
            return None
        
        if self.uom_type != target_unit.uom_type:
            return None
        
        base_value = self.convert_to_base(value)
        return target_unit.convert_from_base(base_value)
    
    def __str__(self):
        return f"{self.name} ({self.abbreviation})"
    
    class Meta:
        ordering = ['uom_type', 'name']
        verbose_name = "Unit of Measure"
        verbose_name_plural = "Units of Measure"
        indexes = [
            models.Index(fields=['uom_type', 'is_active']),
            models.Index(fields=['base_unit', 'uom_type']),
            models.Index(fields=['is_active', 'uom_type']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(conversion_factor__gt=0),
                name='positive_conversion_factor'
            ),
        ]