# dividends/forms.py

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal

# Import base form utilities
from utils.forms import (
    BootstrapFormMixin,
    HTMXFormMixin,
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
    DividendPeriod,
    MemberDividend,
    DividendRate,
    DividendDisbursement,
    DividendPayment,
    DividendPreference
)

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# DIVIDEND PERIOD FILTER FORMS
# =============================================================================

class DividendPeriodFilterForm(DateRangeFilterForm, AmountRangeFilterForm):
    """Filter form for dividend period search"""
    
    status = forms.ChoiceField(
        label='Status',
        choices=[('', 'All Statuses')] + list(DividendPeriod.PERIOD_STATUS),
        required=False
    )
    
    calculation_method = forms.ChoiceField(
        label='Calculation Method',
        choices=[('', 'All Methods')] + DividendPeriod.CALCULATION_METHOD_CHOICES,
        required=False
    )
    
    is_approved = forms.NullBooleanField(
        label='Approved',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Approved'),
            ('false', 'Not Approved')
        ])
    )
    
    # Override date fields for specific naming
    date_from = forms.DateField(
        label='Start Date (From)',
        required=False,
        widget=DatePickerInput()
    )
    
    date_to = forms.DateField(
        label='End Date (To)',
        required=False,
        widget=DatePickerInput()
    )


class MemberDividendFilterForm(BaseFilterForm):
    """Filter form for member dividend search"""
    
    status = forms.ChoiceField(
        label='Status',
        choices=[('', 'All Statuses')] + list(MemberDividend.STATUS_CHOICES),
        required=False
    )
    
    disbursement_method = forms.ChoiceField(
        label='Disbursement Method',
        choices=[('', 'All Methods')] + MemberDividend.DISBURSEMENT_METHOD_CHOICES,
        required=False
    )
    
    min_dividend = MoneyField(
        label='Minimum Dividend',
        required=False
    )
    
    max_dividend = MoneyField(
        label='Maximum Dividend',
        required=False
    )
    
    min_shares = forms.IntegerField(
        label='Minimum Shares',
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0})
    )
    
    max_shares = forms.IntegerField(
        label='Maximum Shares',
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0})
    )


class DividendDisbursementFilterForm(DateRangeFilterForm):
    """Filter form for dividend disbursement search"""
    
    status = forms.ChoiceField(
        label='Status',
        choices=[('', 'All Statuses')] + list(DividendDisbursement.STATUS_CHOICES),
        required=False
    )
    
    disbursement_method = forms.ChoiceField(
        label='Method',
        choices=[('', 'All Methods')] + DividendDisbursement.DISBURSEMENT_METHOD_CHOICES,
        required=False
    )
    
    date_from = forms.DateField(
        label='Disbursement Date (From)',
        required=False,
        widget=DatePickerInput()
    )
    
    date_to = forms.DateField(
        label='Disbursement Date (To)',
        required=False,
        widget=DatePickerInput()
    )


class DividendPaymentFilterForm(BaseFilterForm):
    """Filter form for dividend payment search"""
    
    status = forms.ChoiceField(
        label='Status',
        choices=[('', 'All Statuses')] + list(DividendPayment.STATUS_CHOICES),
        required=False
    )
    
    min_retry = forms.IntegerField(
        label='Minimum Retry Count',
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0})
    )


# =============================================================================
# DIVIDEND PERIOD FORMS
# =============================================================================

class DividendPeriodForm(BootstrapFormMixin, MoneyFieldsMixin, RequiredFieldsMixin, forms.ModelForm):
    """Form for creating/editing dividend periods"""
    
    total_dividend_amount = MoneyField(label='Total Dividend Amount')
    dividend_rate = PercentageField(label='Dividend Rate')
    withholding_tax_rate = PercentageField(label='Withholding Tax Rate', required=False)
    minimum_payout_amount = MoneyField(label='Minimum Payout Amount', required=False)
    
    class Meta:
        model = DividendPeriod
        fields = [
            'name',
            'financial_period',
            'start_date',
            'end_date',
            'record_date',
            'declaration_date',
            'payment_date',
            'total_dividend_amount',
            'dividend_rate',
            'calculation_method',
            'withholding_tax_rate',
            'apply_withholding_tax',
            'default_disbursement_method',
            'allow_member_choice',
            'minimum_payout_amount',
            'status',
            'description',
            'notes',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., FY 2024 Dividends'
            }),
            'financial_period': forms.Select(attrs={'class': 'form-select'}),
            'start_date': DatePickerInput(),
            'end_date': DatePickerInput(),
            'record_date': DatePickerInput(),
            'declaration_date': DatePickerInput(),
            'payment_date': DatePickerInput(),
            'calculation_method': forms.Select(attrs={'class': 'form-select'}),
            'apply_withholding_tax': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'default_disbursement_method': forms.Select(attrs={'class': 'form-select'}),
            'allow_member_choice': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description of the dividend period'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Additional notes'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set required fields
        required_fields = [
            'name', 'financial_period', 'start_date', 'end_date',
            'record_date', 'total_dividend_amount', 'dividend_rate'
        ]
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True
        
        # Filter financial periods to active ones
        from core.models import FiscalPeriod
        self.fields['financial_period'].queryset = FiscalPeriod.objects.filter(
            is_closed=False
        ).order_by('-start_date')
    
    def clean(self):
        """Validate dividend period"""
        cleaned_data = super().clean()
        
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        record_date = cleaned_data.get('record_date')
        declaration_date = cleaned_data.get('declaration_date')
        payment_date = cleaned_data.get('payment_date')
        
        errors = {}
        
        # Validate date ranges
        if start_date and end_date:
            if start_date >= end_date:
                errors['end_date'] = 'End date must be after start date'
        
        if record_date:
            if start_date and record_date < start_date:
                errors['record_date'] = 'Record date cannot be before start date'
            if end_date and record_date > end_date:
                errors['record_date'] = 'Record date cannot be after end date'
        
        if payment_date and declaration_date:
            if payment_date < declaration_date:
                errors['payment_date'] = 'Payment date cannot be before declaration date'
        
        # Validate amounts
        total_amount = cleaned_data.get('total_dividend_amount')
        if total_amount:
            validate_positive_amount(total_amount)
        
        dividend_rate = cleaned_data.get('dividend_rate')
        if dividend_rate:
            validate_percentage(dividend_rate)
        
        if errors:
            raise ValidationError(errors)
        
        return cleaned_data


class DividendPeriodQuickForm(BootstrapFormMixin, MoneyFieldsMixin, forms.ModelForm):
    """Quick form for creating basic dividend periods"""
    
    total_dividend_amount = MoneyField(label='Total Dividend Amount')
    dividend_rate = PercentageField(label='Dividend Rate')
    
    class Meta:
        model = DividendPeriod
        fields = [
            'name',
            'financial_period',
            'start_date',
            'end_date',
            'record_date',
            'total_dividend_amount',
            'dividend_rate',
            'calculation_method',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'financial_period': forms.Select(attrs={'class': 'form-select'}),
            'start_date': DatePickerInput(),
            'end_date': DatePickerInput(),
            'record_date': DatePickerInput(),
            'calculation_method': forms.Select(attrs={'class': 'form-select'}),
        }


class DividendPeriodApprovalForm(BootstrapFormMixin, forms.Form):
    """Form for approving dividend periods"""
    
    confirm_approval = forms.BooleanField(
        label='I confirm that I have reviewed the dividend calculations',
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    approval_notes = forms.CharField(
        label='Approval Notes',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional notes about the approval'
        })
    )


# =============================================================================
# MEMBER DIVIDEND FORMS
# =============================================================================

class MemberDividendForm(BootstrapFormMixin, MoneyFieldsMixin, forms.ModelForm):
    """Form for creating/editing member dividends"""
    
    gross_dividend = MoneyField(label='Gross Dividend')
    tax_amount = MoneyField(label='Tax Amount', required=False)
    net_dividend = MoneyField(label='Net Dividend', required=False)
    shares_value = MoneyField(label='Shares Value', required=False)
    applied_rate = PercentageField(label='Applied Rate', required=False)
    
    class Meta:
        model = MemberDividend
        fields = [
            'dividend_period',
            'member',
            'shares_count',
            'shares_value',
            'gross_dividend',
            'tax_amount',
            'net_dividend',
            'applied_rate',
            'status',
            'disbursement_method',
            'disbursement_account',
            'disbursement_reference',
        ]
        widgets = {
            'dividend_period': forms.Select(attrs={'class': 'form-select'}),
            'member': forms.Select(attrs={'class': 'form-select'}),
            'shares_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'disbursement_method': forms.Select(attrs={'class': 'form-select'}),
            'disbursement_account': forms.Select(attrs={'class': 'form-select'}),
            'disbursement_reference': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'External reference'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter dividend periods to active ones
        self.fields['dividend_period'].queryset = DividendPeriod.objects.filter(
            status__in=['OPEN', 'CALCULATING', 'CALCULATED']
        ).order_by('-end_date')
        
        # Filter members to active ones
        from members.models import Member
        self.fields['member'].queryset = Member.objects.filter(
            status='ACTIVE'
        ).order_by('last_name', 'first_name')
        
        # Filter savings accounts
        from savings.models import SavingsAccount
        self.fields['disbursement_account'].queryset = SavingsAccount.objects.filter(
            status='ACTIVE'
        )


class BulkDividendCalculationForm(BootstrapFormMixin, forms.Form):
    """Form for bulk dividend calculation"""
    
    dividend_period = forms.ModelChoiceField(
        label='Dividend Period',
        queryset=DividendPeriod.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Select the dividend period to calculate'
    )
    
    recalculate = forms.BooleanField(
        label='Recalculate existing dividends',
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Check to recalculate dividends that have already been calculated'
    )
    
    member_category = forms.ChoiceField(
        label='Member Category (Optional)',
        choices=[('', 'All Members')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Filter by member category'
    )
    
    confirm_calculation = forms.BooleanField(
        label='I confirm that I want to calculate dividends',
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Populate dividend period choices
        self.fields['dividend_period'].queryset = DividendPeriod.objects.filter(
            status__in=['OPEN', 'CALCULATING']
        ).order_by('-end_date')
        
        # Populate member category choices
        from members.models import Member
        categories = [('', 'All Members')] + list(Member.MEMBER_CATEGORY_CHOICES)
        self.fields['member_category'].choices = categories


# =============================================================================
# DIVIDEND RATE FORMS
# =============================================================================

class DividendRateForm(BootstrapFormMixin, MoneyFieldsMixin, forms.ModelForm):
    """Form for creating/editing dividend rates"""
    
    rate = PercentageField(label='Rate')
    min_value = MoneyField(label='Minimum Value', required=False)
    max_value = MoneyField(label='Maximum Value', required=False)
    
    class Meta:
        model = DividendRate
        fields = [
            'dividend_period',
            'tier_name',
            'min_shares',
            'max_shares',
            'min_value',
            'max_value',
            'rate',
            'description',
            'is_active',
        ]
        widgets = {
            'dividend_period': forms.Select(attrs={'class': 'form-select'}),
            'tier_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Bronze, Silver, Gold'
            }),
            'min_shares': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'max_shares': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Description of this tier'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter dividend periods
        self.fields['dividend_period'].queryset = DividendPeriod.objects.filter(
            calculation_method='TIERED'
        ).order_by('-end_date')
    
    def clean(self):
        """Validate dividend rate"""
        cleaned_data = super().clean()
        
        min_shares = cleaned_data.get('min_shares')
        max_shares = cleaned_data.get('max_shares')
        min_value = cleaned_data.get('min_value')
        max_value = cleaned_data.get('max_value')
        
        errors = {}
        
        # Must have either share-based or value-based criteria
        has_shares = min_shares > 0 or max_shares is not None
        has_value = min_value is not None or max_value is not None
        
        if not has_shares and not has_value:
            errors['__all__'] = 'Must specify either share count or value criteria'
        
        # Validate share ranges
        if max_shares is not None and min_shares >= max_shares:
            errors['max_shares'] = 'Maximum shares must be greater than minimum shares'
        
        # Validate value ranges
        if min_value is not None and max_value is not None:
            if min_value >= max_value:
                errors['max_value'] = 'Maximum value must be greater than minimum value'
        
        if errors:
            raise ValidationError(errors)
        
        return cleaned_data


# =============================================================================
# DIVIDEND DISBURSEMENT FORMS
# =============================================================================

class DividendDisbursementForm(BootstrapFormMixin, MoneyFieldsMixin, forms.ModelForm):
    """Form for creating dividend disbursements"""
    
    total_amount = MoneyField(label='Total Amount', required=False)
    
    class Meta:
        model = DividendDisbursement
        fields = [
            'dividend_period',
            'disbursement_date',
            'disbursement_method',
            'description',
            'notes',
        ]
        widgets = {
            'dividend_period': forms.Select(attrs={'class': 'form-select'}),
            'disbursement_date': DatePickerInput(),
            'disbursement_method': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Description of this disbursement batch'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Additional notes'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter dividend periods to approved ones
        self.fields['dividend_period'].queryset = DividendPeriod.objects.filter(
            status='APPROVED'
        ).order_by('-end_date')
        
        # Set default disbursement date
        if not self.is_bound:
            self.fields['disbursement_date'].initial = timezone.now().date()


class BatchDisbursementForm(BootstrapFormMixin, forms.Form):
    """Form for creating batch disbursements"""
    
    dividend_period = forms.ModelChoiceField(
        label='Dividend Period',
        queryset=DividendPeriod.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    disbursement_method = forms.ChoiceField(
        label='Disbursement Method',
        choices=DividendDisbursement.DISBURSEMENT_METHOD_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    disbursement_date = forms.DateField(
        label='Disbursement Date',
        widget=DatePickerInput()
    )
    
    filter_by_status = forms.MultipleChoiceField(
        label='Include Dividends with Status',
        choices=MemberDividend.STATUS_CHOICES,
        initial=['APPROVED'],
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        help_text='Select which dividend statuses to include in this batch'
    )
    
    min_amount = MoneyField(
        label='Minimum Amount',
        required=False,
        help_text='Only include dividends above this amount'
    )
    
    confirm_disbursement = forms.BooleanField(
        label='I confirm that I want to create this disbursement batch',
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter dividend periods
        self.fields['dividend_period'].queryset = DividendPeriod.objects.filter(
            status='APPROVED'
        ).order_by('-end_date')
        
        # Set default date
        if not self.is_bound:
            self.fields['disbursement_date'].initial = timezone.now().date()


# =============================================================================
# DIVIDEND PAYMENT FORMS
# =============================================================================

class DividendPaymentForm(BootstrapFormMixin, MoneyFieldsMixin, forms.ModelForm):
    """Form for creating/editing dividend payments"""
    
    amount = MoneyField(label='Amount')
    
    class Meta:
        model = DividendPayment
        fields = [
            'member_dividend',
            'disbursement',
            'payment_date',
            'amount',
            'status',
            'payment_reference',
            'receipt_number',
            'savings_account',
            'bank_name',
            'bank_account',
            'mobile_number',
            'transaction_id',
            'notes',
        ]
        widgets = {
            'member_dividend': forms.Select(attrs={'class': 'form-select'}),
            'disbursement': forms.Select(attrs={'class': 'form-select'}),
            'payment_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'payment_reference': forms.TextInput(attrs={'class': 'form-control'}),
            'receipt_number': forms.TextInput(attrs={'class': 'form-control'}),
            'savings_account': forms.Select(attrs={'class': 'form-select'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_account': forms.TextInput(attrs={'class': 'form-control'}),
            'mobile_number': forms.TextInput(attrs={'class': 'form-control'}),
            'transaction_id': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class PaymentConfirmationForm(BootstrapFormMixin, forms.Form):
    """Form for confirming payment"""
    
    payment_reference = forms.CharField(
        label='Payment Reference',
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Transaction/Payment reference number'
        })
    )
    
    transaction_id = forms.CharField(
        label='Transaction ID',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'External transaction ID'
        })
    )
    
    notes = forms.CharField(
        label='Notes',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Additional notes'
        })
    )
    
    confirm_payment = forms.BooleanField(
        label='I confirm that this payment has been completed',
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class PaymentFailureForm(BootstrapFormMixin, forms.Form):
    """Form for marking payment as failed"""
    
    failure_reason = forms.CharField(
        label='Failure Reason',
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Explain why the payment failed'
        })
    )
    
    allow_retry = forms.BooleanField(
        label='Allow retry',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Check if this payment should be retried'
    )


# =============================================================================
# DIVIDEND PREFERENCE FORMS
# =============================================================================

class DividendPreferenceForm(BootstrapFormMixin, forms.ModelForm):
    """Form for setting dividend preferences"""
    
    class Meta:
        model = DividendPreference
        fields = [
            'member',
            'dividend_period',
            'is_default',
            'preference_method',
            'savings_account',
            'bank_name',
            'bank_account',
            'bank_branch',
            'mobile_number',
            'mobile_provider',
            'notes',
        ]
        widgets = {
            'member': forms.Select(attrs={'class': 'form-select'}),
            'dividend_period': forms.Select(attrs={'class': 'form-select'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'preference_method': forms.Select(attrs={'class': 'form-select'}),
            'savings_account': forms.Select(attrs={'class': 'form-select'}),
            'bank_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Bank name'
            }),
            'bank_account': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Account number'
            }),
            'bank_branch': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Branch name'
            }),
            'mobile_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+256xxxxxxxxx',
                'type': 'tel'
            }),
            'mobile_provider': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., MTN, Airtel'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Additional notes'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter members to active ones
        from members.models import Member
        self.fields['member'].queryset = Member.objects.filter(
            status='ACTIVE'
        ).order_by('last_name', 'first_name')
        
        # Filter dividend periods to future/current ones
        self.fields['dividend_period'].queryset = DividendPeriod.objects.filter(
            status__in=['DRAFT', 'OPEN', 'CALCULATING', 'CALCULATED', 'APPROVED']
        ).order_by('-end_date')
        
        # Filter savings accounts
        from savings.models import SavingsAccount
        self.fields['savings_account'].queryset = SavingsAccount.objects.filter(
            status='ACTIVE'
        )
    
    def clean(self):
        """Validate preference"""
        cleaned_data = super().clean()
        
        preference_method = cleaned_data.get('preference_method')
        savings_account = cleaned_data.get('savings_account')
        bank_name = cleaned_data.get('bank_name')
        bank_account = cleaned_data.get('bank_account')
        mobile_number = cleaned_data.get('mobile_number')
        
        errors = {}
        
        # Validate account information based on method
        if preference_method == 'SAVINGS_ACCOUNT' and not savings_account:
            errors['savings_account'] = 'Savings account required for this method'
        
        if preference_method == 'BANK_TRANSFER':
            if not bank_name:
                errors['bank_name'] = 'Bank name required for bank transfer'
            if not bank_account:
                errors['bank_account'] = 'Bank account number required for bank transfer'
        
        if preference_method == 'MOBILE_MONEY' and not mobile_number:
            errors['mobile_number'] = 'Mobile number required for mobile money'
        
        if errors:
            raise ValidationError(errors)
        
        return cleaned_data


class MemberDividendPreferenceForm(BootstrapFormMixin, forms.ModelForm):
    """Simplified form for members to set their own preference"""
    
    class Meta:
        model = DividendPreference
        fields = [
            'preference_method',
            'savings_account',
            'bank_name',
            'bank_account',
            'bank_branch',
            'mobile_number',
            'mobile_provider',
        ]
        widgets = {
            'preference_method': forms.Select(attrs={'class': 'form-select'}),
            'savings_account': forms.Select(attrs={'class': 'form-select'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_account': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_branch': forms.TextInput(attrs={'class': 'form-control'}),
            'mobile_number': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'tel'
            }),
            'mobile_provider': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.member = kwargs.pop('member', None)
        super().__init__(*args, **kwargs)
        
        # Filter savings accounts to member's own accounts
        if self.member:
            from savings.models import SavingsAccount
            self.fields['savings_account'].queryset = SavingsAccount.objects.filter(
                member=self.member,
                status='ACTIVE'
            )
        
        # Make preference method required
        self.fields['preference_method'].required = True


# =============================================================================
# REPORTING FORMS
# =============================================================================

class DividendReportForm(BootstrapFormMixin, DateRangeFormMixin, forms.Form):
    """Form for generating dividend reports"""
    
    report_type = forms.ChoiceField(
        label='Report Type',
        choices=[
            ('SUMMARY', 'Summary Report'),
            ('DETAILED', 'Detailed Report'),
            ('BY_MEMBER', 'By Member'),
            ('BY_PERIOD', 'By Period'),
            ('PAYMENT_STATUS', 'Payment Status'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    dividend_period = forms.ModelChoiceField(
        label='Dividend Period',
        queryset=DividendPeriod.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Leave blank for all periods'
    )
    
    start_date = forms.DateField(
        label='Start Date',
        required=False,
        widget=DatePickerInput()
    )
    
    end_date = forms.DateField(
        label='End Date',
        required=False,
        widget=DatePickerInput()
    )
    
    format = forms.ChoiceField(
        label='Format',
        choices=[
            ('PDF', 'PDF'),
            ('EXCEL', 'Excel'),
            ('CSV', 'CSV'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Order dividend periods
        self.fields['dividend_period'].queryset = DividendPeriod.objects.all().order_by(
            '-end_date'
        )