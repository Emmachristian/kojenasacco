# core/forms.py

from django import forms
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal
import json
import logging

# Import base form utilities
from utils.forms import (
    BootstrapFormMixin,
    DateRangeFormMixin,
    MoneyFieldsMixin,
    RequiredFieldsMixin,
    BaseFilterForm,
    DateRangeFilterForm,
    AmountRangeFilterForm,
    MoneyField,
    PercentageField,
    DatePickerInput,
    validate_positive_amount,
    validate_percentage,
)

from .models import (
    FinancialSettings,
    SaccoConfiguration,
    FiscalYear,
    FiscalPeriod,
    PaymentMethod,
    TaxRate,
    UnitOfMeasure,
)

logger = logging.getLogger(__name__)


# =============================================================================
# SACCO CONFIGURATION FORMS
# =============================================================================

class SaccoConfigurationForm(BootstrapFormMixin, RequiredFieldsMixin, forms.ModelForm):
    """Form for managing SACCO configuration with timezone support."""
    
    class Meta:
        model = SaccoConfiguration
        fields = [
            'period_system', 'periods_per_year', 'period_naming_convention',
            'custom_period_names', 'fiscal_year_type', 'fiscal_year_start_month',
            'fiscal_year_start_day', 'operational_timezone',  # ⭐ ADDED TIMEZONE
            'dividend_calculation_method', 'dividend_distribution_frequency',
            'enable_automatic_reminders', 'enable_sms', 'enable_email_notifications'
        ]
        widgets = {
            'period_system': forms.Select(attrs={'id': 'id_period_system'}),
            'periods_per_year': forms.NumberInput(attrs={
                'min': 1,
                'max': 52,
                'id': 'id_periods_per_year'
            }),
            'period_naming_convention': forms.Select(attrs={'id': 'id_period_naming_convention'}),
            'custom_period_names': forms.Textarea(attrs={
                'rows': 6,
                'id': 'id_custom_period_names',
                'placeholder': '{\n  "1": "First Quarter",\n  "2": "Second Quarter",\n  "3": "Third Quarter",\n  "4": "Fourth Quarter"\n}',
                'class': 'font-monospace'
            }),
            'fiscal_year_type': forms.Select(attrs={'id': 'id_fiscal_year_type'}),
            'fiscal_year_start_month': forms.Select(attrs={'id': 'id_fiscal_year_start_month'}),
            'fiscal_year_start_day': forms.NumberInput(attrs={
                'min': 1,
                'max': 31,
                'id': 'id_fiscal_year_start_day'
            }),
            'operational_timezone': forms.Select(attrs={  # ⭐ ADDED TIMEZONE WIDGET
                'id': 'id_operational_timezone',
                'class': 'form-select select2',  # Use select2 for searchable dropdown
                'data-placeholder': 'Select timezone...'
            }),
            'dividend_calculation_method': forms.Select(attrs={'id': 'id_dividend_calculation_method'}),
            'dividend_distribution_frequency': forms.Select(attrs={'id': 'id_dividend_distribution_frequency'}),
            'enable_automatic_reminders': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_enable_automatic_reminders'
            }),
            'enable_sms': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_enable_sms'
            }),
            'enable_email_notifications': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_enable_email_notifications'
            }),
        }
        help_texts = {
            'period_system': 'Choose the operational period structure for your SACCO',
            'periods_per_year': 'Will be auto-set based on period system (editable for custom)',
            'period_naming_convention': 'How periods should be named in the system',
            'custom_period_names': 'JSON format: {"1": "Name 1", "2": "Name 2", ...}',
            'fiscal_year_type': 'When your fiscal year typically runs',
            'fiscal_year_start_month': 'Month when fiscal year starts',
            'fiscal_year_start_day': 'Day of month when fiscal year starts',
            'operational_timezone': 'Timezone for fiscal periods, deadlines, and automated processes',  # ⭐ ADDED
            'dividend_calculation_method': 'How member dividends are calculated',
            'dividend_distribution_frequency': 'How often dividends are distributed',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # ⭐ POPULATE TIMEZONE CHOICES FROM MODEL
        from zoneinfo import available_timezones
        
        # Get all available timezones
        all_timezones = sorted(available_timezones())
        
        # Create choices - you can optionally group them by region
        timezone_choices = [(tz, tz) for tz in all_timezones]
        
        # Set choices for timezone field
        self.fields['operational_timezone'].widget.choices = timezone_choices
        
        # Optionally add popular East African timezones at the top
        popular_timezones = [
            ('Africa/Kampala', 'Africa/Kampala (Uganda - EAT)'),
            ('Africa/Nairobi', 'Africa/Nairobi (Kenya - EAT)'),
            ('Africa/Dar_es_Salaam', 'Africa/Dar_es_Salaam (Tanzania - EAT)'),
            ('Africa/Kigali', 'Africa/Kigali (Rwanda - CAT)'),
            ('Africa/Addis_Ababa', 'Africa/Addis_Ababa (Ethiopia - EAT)'),
            ('---', '--- All Timezones ---'),
        ]
        
        # Combine popular with all timezones
        self.fields['operational_timezone'].widget.choices = (
            popular_timezones + timezone_choices
        )
        
        # Make custom_period_names not required initially
        self.fields['custom_period_names'].required = False
        
        # Make periods_per_year read-only if not custom system
        if self.instance and self.instance.pk:
            if self.instance.period_system != 'custom':
                self.fields['periods_per_year'].widget.attrs['readonly'] = True
                self.fields['periods_per_year'].help_text = 'Auto-calculated based on period system'
        
        # Add dynamic help text for custom period names
        if self.instance and self.instance.pk:
            periods_count = self.instance.periods_per_year
            example = {}
            for i in range(1, min(periods_count + 1, 4)):
                example[str(i)] = f"Period {i}"
            
            self.fields['custom_period_names'].widget.attrs['placeholder'] = json.dumps(
                example, indent=2
            )
    
    def clean_periods_per_year(self):
        """Validate and auto-set periods_per_year based on period_system."""
        periods_per_year = self.cleaned_data.get('periods_per_year')
        period_system = self.cleaned_data.get('period_system')
        
        # Auto-set for non-custom systems
        if period_system and period_system != 'custom':
            system_periods = {
                'monthly': 12,
                'quarterly': 4,
                'biannual': 2,
                'annual': 1,
            }
            return system_periods.get(period_system, 12)
        
        # For custom systems, validate range
        if not periods_per_year:
            raise ValidationError('Periods per year is required for custom systems.')
        
        if not (1 <= periods_per_year <= 52):
            raise ValidationError('Periods per year must be between 1 and 52.')
        
        return periods_per_year
    
    def clean_operational_timezone(self):
        """Validate timezone."""
        timezone_str = self.cleaned_data.get('operational_timezone')
        
        if not timezone_str:
            return 'Africa/Kampala'  # Default
        
        # Validate that it's a valid timezone
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(timezone_str)
            return timezone_str
        except Exception:
            raise ValidationError(f"'{timezone_str}' is not a valid timezone identifier.")
    
    def clean_custom_period_names(self):
        """Validate and parse custom period names JSON."""
        data = self.cleaned_data.get('custom_period_names')
        naming_convention = self.cleaned_data.get('period_naming_convention')
        
        # Only required if using custom naming convention
        if naming_convention != 'custom':
            return {} if data is None else data
        
        # Custom naming requires data
        if not data:
            raise ValidationError(
                'Custom period names are required when using custom naming convention. '
                'Provide a JSON dictionary mapping period numbers to names.'
            )
        
        # Parse JSON if string
        try:
            if isinstance(data, str):
                if not data.strip():
                    raise ValidationError('Custom period names cannot be empty.')
                
                names = json.loads(data)
            else:
                names = data
            
            # Validate structure
            if not isinstance(names, dict):
                raise ValidationError(
                    'Custom period names must be a JSON object/dictionary, '
                    'e.g., {"1": "First Quarter", "2": "Second Quarter"}'
                )
            
            # Get periods_per_year
            period_system = self.cleaned_data.get('period_system')
            if period_system == 'custom':
                periods_per_year = self.cleaned_data.get('periods_per_year')
            else:
                system_periods = {
                    'monthly': 12, 'quarterly': 4, 'biannual': 2, 'annual': 1,
                }
                periods_per_year = system_periods.get(period_system, 12)
            
            if not periods_per_year:
                raise ValidationError('Cannot validate custom names without periods_per_year.')
            
            # Validate all required periods have names
            missing_periods = []
            empty_names = []
            
            for i in range(1, periods_per_year + 1):
                key = str(i)
                if key not in names:
                    missing_periods.append(key)
                elif not names[key] or not str(names[key]).strip():
                    empty_names.append(key)
            
            errors = []
            if missing_periods:
                errors.append(f'Missing names for period(s): {", ".join(missing_periods)}')
            if empty_names:
                errors.append(f'Empty names for period(s): {", ".join(empty_names)}')
            
            if errors:
                raise ValidationError(' | '.join(errors))
            
            # Clean up names
            cleaned_names = {}
            for key, value in names.items():
                if key.isdigit() and 1 <= int(key) <= periods_per_year:
                    cleaned_names[key] = str(value).strip()
            
            return cleaned_names
            
        except json.JSONDecodeError as e:
            raise ValidationError(
                f'Invalid JSON format: {str(e)}. '
                'Expected format: {"1": "Name 1", "2": "Name 2", ...}'
            )
    
    def clean_fiscal_year_start_day(self):
        """Validate fiscal year start day."""
        start_day = self.cleaned_data.get('fiscal_year_start_day')
        
        if not start_day:
            return 1
        
        if not (1 <= start_day <= 31):
            raise ValidationError('Day must be between 1 and 31.')
        
        return start_day
    
    def clean(self):
        """Cross-field validation."""
        cleaned_data = super().clean()
        
        # Validate fiscal year start date
        start_month = cleaned_data.get('fiscal_year_start_month')
        start_day = cleaned_data.get('fiscal_year_start_day')
        
        if start_month and start_day:
            try:
                from datetime import date
                date(2024, start_month, start_day)
            except ValueError:
                self.add_error(
                    'fiscal_year_start_day',
                    f'Invalid date: Month {start_month} does not have day {start_day}.'
                )
        
        # Validate periods_per_year matches custom period names count
        if cleaned_data.get('period_naming_convention') == 'custom':
            custom_names = cleaned_data.get('custom_period_names', {})
            periods_per_year = cleaned_data.get('periods_per_year')
            
            if custom_names and periods_per_year:
                provided_count = len([k for k in custom_names.keys() if k.isdigit()])
                if provided_count != periods_per_year:
                    self.add_error(
                        'custom_period_names',
                        f'Expected {periods_per_year} period names, but got {provided_count}.'
                    )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save with singleton pattern enforcement."""
        instance = super().save(commit=False)
        
        # Ensure singleton pattern
        instance.pk = 1
        
        if commit:
            instance.save()
        
        return instance


# =============================================================================
# FINANCIAL SETTINGS FORMS
# =============================================================================

class FinancialSettingsForm(BootstrapFormMixin, MoneyFieldsMixin, RequiredFieldsMixin, forms.ModelForm):
    """Form for managing SACCO financial settings with CharField currency."""
    
    default_interest_rate = PercentageField(label='Default Interest Rate')
    late_payment_penalty_rate = PercentageField(label='Late Payment Penalty Rate')
    savings_interest_rate = PercentageField(label='Savings Interest Rate')
    minimum_loan_amount = MoneyField(label='Minimum Loan Amount')
    maximum_loan_amount = MoneyField(label='Maximum Loan Amount')
    minimum_savings_balance = MoneyField(label='Minimum Savings Balance')
    share_value = MoneyField(label='Share Value')
    withdrawal_approval_limit = MoneyField(label='Withdrawal Approval Limit')
    
    class Meta:
        model = FinancialSettings
        fields = [
            # Currency Configuration
            'sacco_currency', 'currency_position', 'decimal_places', 'use_thousand_separator',
            
            # Loan Settings
            'default_loan_term_days', 'default_interest_rate', 'late_payment_penalty_rate',
            'grace_period_days', 'minimum_loan_amount', 'maximum_loan_amount',
            
            # Savings Settings
            'minimum_savings_balance', 'savings_interest_rate',
            
            # Share Capital Settings
            'share_value', 'minimum_shares',
            
            # Workflow Settings
            'loan_approval_required', 'withdrawal_approval_required', 'withdrawal_approval_limit',
            
            # Communication Settings
            'send_transaction_notifications', 'send_loan_reminders', 'send_dividend_notifications',
        ]
        
        widgets = {
            'sacco_currency': forms.Select(attrs={  # ⭐ CHANGED TO SELECT
                'class': 'form-select select2',
                'data-placeholder': 'Select currency...'
            }),
            'currency_position': forms.Select(),
            'decimal_places': forms.NumberInput(attrs={'min': 0, 'max': 4}),
            'use_thousand_separator': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'default_loan_term_days': forms.NumberInput(attrs={'min': 1}),
            'grace_period_days': forms.NumberInput(attrs={'min': 0}),
            'minimum_shares': forms.NumberInput(attrs={'min': 1}),
            'loan_approval_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'withdrawal_approval_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'send_transaction_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'send_loan_reminders': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'send_dividend_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        
        help_texts = {
            'sacco_currency': 'Primary currency for this SACCO (ISO 4217 code)',
            'currency_position': 'How to display currency symbols',
            'default_loan_term_days': 'Default repayment period for loans',
            'default_interest_rate': 'Default annual interest rate percentage',
            'late_payment_penalty_rate': 'Monthly penalty rate for late payments',
            'grace_period_days': 'Days before penalties apply',
            'minimum_loan_amount': 'Minimum amount members can borrow',
            'maximum_loan_amount': 'Maximum amount members can borrow',
            'minimum_savings_balance': 'Minimum required balance in savings',
            'savings_interest_rate': 'Annual interest rate on savings',
            'share_value': 'Value of one share',
            'minimum_shares': 'Minimum shares required for membership',
            'withdrawal_approval_limit': 'Withdrawals above this amount require approval',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # ⭐ POPULATE CURRENCY CHOICES FROM MODEL METHOD
        currency_choices = FinancialSettings.get_currency_choices()
        self.fields['sacco_currency'].widget.choices = currency_choices
        
        # Get current currency for dynamic display (CharField now!)
        currency = self.instance.sacco_currency if self.instance and self.instance.sacco_currency else 'UGX'
        # ⭐ NO .code NEEDED - it's already a string!
        
        # Dynamic currency position choices
        self.fields['currency_position'].choices = [
            ('BEFORE', f'Before amount ({currency} 100.00)'),
            ('AFTER', f'After amount (100.00 {currency})'),
            ('BEFORE_NO_SPACE', f'Before, no space ({currency}100.00)'),
            ('AFTER_NO_SPACE', f'After, no space (100.00{currency})'),
        ]
    
    def clean_sacco_currency(self):
        """Validate currency code."""
        currency = self.cleaned_data.get('sacco_currency')
        
        if not currency:
            return 'UGX'
        
        # Normalize to uppercase
        currency = currency.upper()
        
        # Validate it's 3 characters
        if len(currency) != 3:
            raise ValidationError('Currency code must be 3 characters (ISO 4217)')
        
        # Optionally validate against pycountry
        try:
            import pycountry
            currency_obj = pycountry.currencies.get(alpha_3=currency)
            if not currency_obj:
                raise ValidationError(f"'{currency}' is not a valid ISO 4217 currency code")
        except ImportError:
            # If pycountry not available, just check basic format
            if not currency.isalpha():
                raise ValidationError('Currency code must contain only letters')
        
        return currency
    
    def clean(self):
        """Additional validation for financial settings"""
        cleaned_data = super().clean()
        
        # Validate loan amounts
        min_loan = cleaned_data.get('minimum_loan_amount')
        max_loan = cleaned_data.get('maximum_loan_amount')
        
        if min_loan and max_loan:
            if min_loan >= max_loan:
                self.add_error('maximum_loan_amount', 
                             'Maximum loan amount must be greater than minimum')
        
        # Validate interest rates
        default_rate = cleaned_data.get('default_interest_rate')
        penalty_rate = cleaned_data.get('late_payment_penalty_rate')
        savings_rate = cleaned_data.get('savings_interest_rate')
        
        if default_rate is not None:
            validate_percentage(default_rate)
        
        if penalty_rate is not None:
            validate_percentage(penalty_rate)
        
        if savings_rate is not None:
            validate_percentage(savings_rate)
        
        # Validate share value
        share_value = cleaned_data.get('share_value')
        if share_value is not None:
            validate_positive_amount(share_value)
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save with singleton pattern enforcement."""
        instance = super().save(commit=False)
        
        # Ensure singleton pattern
        instance.pk = 1
        
        if commit:
            instance.save()
        
        return instance
    
# =============================================================================
# FISCAL YEAR FORMS
# =============================================================================

class FiscalYearForm(BootstrapFormMixin, RequiredFieldsMixin, forms.ModelForm):
    """Form for creating and editing fiscal years with smart suggestions."""
    
    start_date = forms.DateField(widget=DatePickerInput())
    end_date = forms.DateField(widget=DatePickerInput())
    
    class Meta:
        model = FiscalYear
        fields = [
            'name', 'code', 'start_date', 'end_date',
            'is_active', 'description'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': '2024/2025'}),
            'code': forms.TextInput(attrs={'placeholder': 'FY2025'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional description...'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False
        
        config = SaccoConfiguration.get_instance()
        
        if not self.instance.pk and config:
            # Smart suggestions for new fiscal year
            latest_fy = FiscalYear.objects.order_by('-end_date').first()
            
            if latest_fy and latest_fy.end_date:
                suggested_start = latest_fy.end_date + timedelta(days=1)
                suggested_end = suggested_start + relativedelta(years=1) - timedelta(days=1)
                
                self.fields['start_date'].widget.attrs['placeholder'] = suggested_start.strftime('%Y-%m-%d')
                self.fields['start_date'].help_text = f'💡 Suggested: {suggested_start.strftime("%B %d, %Y")}'
                
                self.fields['end_date'].widget.attrs['placeholder'] = suggested_end.strftime('%Y-%m-%d')
                self.fields['end_date'].help_text = f'💡 Suggested: {suggested_end.strftime("%B %d, %Y")}'
                
                suggested_name = f'{suggested_start.year}/{suggested_end.year}'
                suggested_code = f'FY{suggested_end.year}'
                
                self.fields['name'].widget.attrs['placeholder'] = suggested_name
                self.fields['code'].widget.attrs['placeholder'] = suggested_code
    
    def clean(self):
        cleaned_data = super().clean()
        
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise ValidationError({'end_date': 'End date must be after start date.'})
            
            # Check for overlapping fiscal years
            from django.db.models import Q
            overlapping = FiscalYear.objects.filter(
                Q(start_date__lte=end_date) & Q(end_date__gte=start_date)
            )
            
            if self.instance.pk:
                overlapping = overlapping.exclude(pk=self.instance.pk)
            
            if overlapping.exists():
                raise ValidationError(
                    f'This fiscal year overlaps with: {", ".join([str(fy) for fy in overlapping])}'
                )
        
        return cleaned_data


class FiscalYearFilterForm(DateRangeFilterForm):
    """Filter form for fiscal year search"""
    
    status = forms.ChoiceField(
        label='Status',
        choices=[('', 'All Statuses')] + list(FiscalYear.STATUS_CHOICES),
        required=False
    )
    
    is_active = forms.NullBooleanField(
        label='Active Status',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Active'),
            ('false', 'Inactive')
        ])
    )
    
    is_closed = forms.NullBooleanField(
        label='Closed Status',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Closed'),
            ('false', 'Open')
        ])
    )
    
    is_locked = forms.NullBooleanField(
        label='Locked Status',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Locked'),
            ('false', 'Unlocked')
        ])
    )
    
    # Override date fields for specific naming
    date_from = forms.DateField(
        label='Start Date (From)',
        required=False,
        widget=DatePickerInput()
    )
    
    date_to = forms.DateField(
        label='Start Date (To)',
        required=False,
        widget=DatePickerInput()
    )


# =============================================================================
# PERIOD FORMS
# =============================================================================

class FiscalPeriodForm(BootstrapFormMixin, RequiredFieldsMixin, forms.ModelForm):
    """Form for creating and editing periods with smart suggestions."""
    
    start_date = forms.DateField(widget=DatePickerInput())
    end_date = forms.DateField(widget=DatePickerInput())
    
    class Meta:
        model = FiscalPeriod
        fields = [
            'fiscal_year', 'name', 'period_number',
            'start_date', 'end_date', 'is_active', 'description'
        ]
        widgets = {
            'fiscal_year': forms.Select(),
            'name': forms.TextInput(attrs={'placeholder': 'January'}),
            'period_number': forms.NumberInput(attrs={'min': 1}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False
        
        # Filter fiscal years to only show non-locked ones
        self.fields['fiscal_year'].queryset = FiscalYear.objects.filter(
            is_locked=False
        ).order_by('-start_date')
        
        config = SaccoConfiguration.get_instance()
        if config:
            max_periods = config.periods_per_year
            self.fields['period_number'].help_text = f'Period number (1-{max_periods})'
    
    def clean(self):
        cleaned_data = super().clean()
        
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        fiscal_year = cleaned_data.get('fiscal_year')
        period_number = cleaned_data.get('period_number')
        
        errors = {}
        
        if start_date and end_date and start_date >= end_date:
            errors['end_date'] = 'End date must be after start date.'
        
        # Validate period falls within fiscal year
        if fiscal_year and start_date and end_date:
            if start_date < fiscal_year.start_date:
                errors['start_date'] = f'Period must start on or after {fiscal_year.start_date}'
            if end_date > fiscal_year.end_date:
                errors['end_date'] = f'Period must end on or before {fiscal_year.end_date}'
        
        # Validate period number
        if period_number:
            config = SaccoConfiguration.get_instance()
            if config and not config.validate_period_number(period_number):
                errors['period_number'] = f'Period number must be between 1 and {config.get_period_count()}'
            
            # Check if period number already used
            if fiscal_year:
                existing = FiscalPeriod.objects.filter(
                    fiscal_year=fiscal_year,
                    period_number=period_number
                )
                if self.instance.pk:
                    existing = existing.exclude(pk=self.instance.pk)
                
                if existing.exists():
                    errors['period_number'] = f'Period number {period_number} already used'
        
        # Check for overlapping periods
        if fiscal_year and start_date and end_date:
            overlapping = FiscalPeriod.objects.filter(
                fiscal_year=fiscal_year,
                start_date__lt=end_date,
                end_date__gt=start_date
            )
            
            if self.instance.pk:
                overlapping = overlapping.exclude(pk=self.instance.pk)
            
            if overlapping.exists():
                errors['start_date'] = f'Overlaps with: {", ".join([str(p) for p in overlapping])}'
        
        if errors:
            raise ValidationError(errors)
        
        return cleaned_data


class FiscalPeriodFilterForm(DateRangeFilterForm):
    """Filter form for fiscal period search"""
    
    fiscal_year = forms.ModelChoiceField(
        label='Fiscal Year',
        queryset=FiscalYear.objects.all().order_by('-start_date'),
        required=False,
        empty_label='All Fiscal Years'
    )
    
    status = forms.ChoiceField(
        label='Status',
        choices=[('', 'All Statuses')] + list(FiscalPeriod.STATUS_CHOICES),
        required=False
    )
    
    is_active = forms.NullBooleanField(
        label='Active Status',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Active'),
            ('false', 'Inactive')
        ])
    )
    
    is_closed = forms.NullBooleanField(
        label='Closed Status',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Closed'),
            ('false', 'Open')
        ])
    )
    
    is_locked = forms.NullBooleanField(
        label='Locked Status',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Locked'),
            ('false', 'Unlocked')
        ])
    )
    
    min_period_number = forms.IntegerField(
        label='Min Period Number',
        required=False,
        widget=forms.NumberInput(attrs={'min': 1})
    )
    
    max_period_number = forms.IntegerField(
        label='Max Period Number',
        required=False,
        widget=forms.NumberInput(attrs={'min': 1})
    )
    
    # Override date fields for specific naming
    date_from = forms.DateField(
        label='Start Date (From)',
        required=False,
        widget=DatePickerInput()
    )
    
    date_to = forms.DateField(
        label='Start Date (To)',
        required=False,
        widget=DatePickerInput()
    )


# =============================================================================
# PAYMENT METHOD FORMS
# =============================================================================

class PaymentMethodForm(BootstrapFormMixin, MoneyFieldsMixin, RequiredFieldsMixin, forms.ModelForm):
    """Form for creating and editing payment methods."""
    
    minimum_amount = MoneyField(label='Minimum Amount', required=False)
    maximum_amount = MoneyField(label='Maximum Amount', required=False)
    daily_limit = MoneyField(label='Daily Limit', required=False)
    transaction_fee_amount = MoneyField(label='Transaction Fee Amount', required=False)
    
    class Meta:
        model = PaymentMethod
        fields = [
            'name', 'method_type', 'code', 'mobile_money_provider',
            'bank_name', 'bank_account_number', 'bank_branch', 'swift_code',
            'is_active', 'is_default', 'requires_approval',
            'minimum_amount', 'maximum_amount', 'daily_limit',
            'has_transaction_fee', 'transaction_fee_type',
            'transaction_fee_amount', 'fee_bearer',
            'processing_time', 'requires_reference',
            'icon', 'color_code', 'display_order',
            'instructions', 'notes'
        ]
        widgets = {
            'name': forms.TextInput(),
            'method_type': forms.Select(),
            'code': forms.TextInput(attrs={'placeholder': 'MTN_MM'}),
            'mobile_money_provider': forms.Select(),
            'bank_name': forms.TextInput(),
            'bank_account_number': forms.TextInput(),
            'bank_branch': forms.TextInput(),
            'swift_code': forms.TextInput(),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'requires_approval': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'has_transaction_fee': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'transaction_fee_type': forms.Select(),
            'fee_bearer': forms.Select(),
            'processing_time': forms.TextInput(),
            'requires_reference': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'icon': forms.TextInput(),
            'color_code': forms.TextInput(attrs={'type': 'color'}),
            'display_order': forms.NumberInput(),
            'instructions': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make optional fields
        optional_fields = [
            'mobile_money_provider', 'bank_name', 'bank_account_number',
            'bank_branch', 'swift_code', 'minimum_amount', 'maximum_amount',
            'daily_limit', 'transaction_fee_type', 'transaction_fee_amount', 
            'processing_time', 'icon', 'color_code', 'instructions', 'notes'
        ]
        for field in optional_fields:
            self.fields[field].required = False


class PaymentMethodFilterForm(BaseFilterForm):
    """Filter form for payment method search"""
    
    method_type = forms.ChoiceField(
        label='Method Type',
        choices=[('', 'All Types')] + list(PaymentMethod.METHOD_TYPE_CHOICES),
        required=False
    )
    
    mobile_money_provider = forms.ChoiceField(
        label='Mobile Money Provider',
        choices=[('', 'All Providers')] + list(PaymentMethod.MOBILE_MONEY_PROVIDER_CHOICES),
        required=False
    )
    
    is_active = forms.NullBooleanField(
        label='Active Status',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Active'),
            ('false', 'Inactive')
        ])
    )
    
    is_default = forms.NullBooleanField(
        label='Default Status',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Default'),
            ('false', 'Not Default')
        ])
    )
    
    requires_approval = forms.NullBooleanField(
        label='Requires Approval',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Requires Approval'),
            ('false', 'No Approval Needed')
        ])
    )
    
    has_transaction_fee = forms.NullBooleanField(
        label='Has Transaction Fee',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Has Fee'),
            ('false', 'No Fee')
        ])
    )


# =============================================================================
# TAX RATE FORMS
# =============================================================================

class TaxRateForm(BootstrapFormMixin, RequiredFieldsMixin, forms.ModelForm):
    """Form for creating and editing tax rates."""
    
    rate = PercentageField(label='Tax Rate')
    effective_from = forms.DateField(widget=DatePickerInput())
    effective_to = forms.DateField(widget=DatePickerInput(), required=False)
    
    class Meta:
        model = TaxRate
        fields = [
            'name', 'tax_type', 'rate', 'effective_from', 'effective_to',
            'is_active', 'applies_to_members', 'applies_to_sacco',
            'description', 'legal_reference'
        ]
        widgets = {
            'name': forms.TextInput(),
            'tax_type': forms.Select(),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'applies_to_members': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'applies_to_sacco': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'legal_reference': forms.TextInput(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['effective_to'].required = False
        self.fields['description'].required = False
        self.fields['legal_reference'].required = False


class TaxRateFilterForm(DateRangeFilterForm):
    """Filter form for tax rate search"""
    
    tax_type = forms.ChoiceField(
        label='Tax Type',
        choices=[('', 'All Types')] + list(TaxRate.TAX_TYPE_CHOICES),
        required=False
    )
    
    is_active = forms.NullBooleanField(
        label='Active Status',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Active'),
            ('false', 'Inactive')
        ])
    )
    
    applies_to_members = forms.NullBooleanField(
        label='Applies to Members',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Applies to Members'),
            ('false', 'Does Not Apply')
        ])
    )
    
    applies_to_sacco = forms.NullBooleanField(
        label='Applies to SACCO',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Applies to SACCO'),
            ('false', 'Does Not Apply')
        ])
    )
    
    min_rate = PercentageField(
        label='Minimum Rate',
        required=False
    )
    
    max_rate = PercentageField(
        label='Maximum Rate',
        required=False
    )
    
    # Override date fields for specific naming
    date_from = forms.DateField(
        label='Effective From (After)',
        required=False,
        widget=DatePickerInput()
    )
    
    date_to = forms.DateField(
        label='Effective To (Before)',
        required=False,
        widget=DatePickerInput()
    )
    
    def clean(self):
        """Validate rate range"""
        cleaned_data = super().clean()
        
        min_rate = cleaned_data.get('min_rate')
        max_rate = cleaned_data.get('max_rate')
        
        if min_rate and max_rate:
            if min_rate > max_rate:
                raise ValidationError({
                    'max_rate': 'Maximum rate must be greater than minimum rate.'
                })
        
        return cleaned_data


# =============================================================================
# UNIT OF MEASURE FORMS
# =============================================================================

class UnitOfMeasureForm(BootstrapFormMixin, RequiredFieldsMixin, forms.ModelForm):
    """Form for creating and editing units of measure."""
    
    class Meta:
        model = UnitOfMeasure
        fields = [
            'name', 'abbreviation', 'symbol', 'description',
            'uom_type', 'base_unit', 'conversion_factor', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(),
            'abbreviation': forms.TextInput(),
            'symbol': forms.TextInput(),
            'description': forms.Textarea(attrs={'rows': 2}),
            'uom_type': forms.Select(),
            'base_unit': forms.Select(),
            'conversion_factor': forms.NumberInput(attrs={'step': '0.000001'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['symbol'].required = False
        self.fields['description'].required = False
        self.fields['base_unit'].required = False


class UnitOfMeasureFilterForm(BaseFilterForm):
    """Filter form for unit of measure search"""
    
    uom_type = forms.ChoiceField(
        label='UOM Type',
        choices=[('', 'All Types')] + list(UnitOfMeasure.UOM_TYPE_CHOICES),
        required=False
    )
    
    base_unit = forms.ModelChoiceField(
        label='Base Unit',
        queryset=UnitOfMeasure.objects.filter(base_unit__isnull=True).order_by('name'),
        required=False,
        empty_label='All Base Units'
    )
    
    is_active = forms.NullBooleanField(
        label='Active Status',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Active'),
            ('false', 'Inactive')
        ])
    )
    
    has_base_unit = forms.NullBooleanField(
        label='Has Base Unit',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Has Base Unit'),
            ('false', 'Is Base Unit')
        ])
    )