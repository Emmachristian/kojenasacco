# savings/forms.py

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from datetime import timedelta
from dateutil.relativedelta import relativedelta

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
    SavingsProduct,
    InterestTier,
    SavingsAccount,
    SavingsTransaction,
    InterestCalculation,
    StandingOrder,
    SavingsGoal
)

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# SAVINGS PRODUCT FILTER FORMS
# =============================================================================

class SavingsProductFilterForm(BaseFilterForm):
    """Filter form for savings product search"""
    
    is_active = forms.NullBooleanField(
        label='Active',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Active'),
            ('false', 'Inactive')
        ])
    )
    
    is_fixed_deposit = forms.NullBooleanField(
        label='Fixed Deposit',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Fixed Deposit'),
            ('false', 'Regular Savings')
        ])
    )
    
    is_group_product = forms.NullBooleanField(
        label='Group Product',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Group'),
            ('false', 'Individual')
        ])
    )
    
    interest_calculation_method = forms.ChoiceField(
        label='Calculation Method',
        choices=[('', 'All Methods')] + list(SavingsProduct.INTEREST_CALCULATION_METHODS),
        required=False
    )
    
    interest_posting_frequency = forms.ChoiceField(
        label='Posting Frequency',
        choices=[('', 'All')] + list(SavingsProduct.INTEREST_POSTING_FREQUENCY),
        required=False
    )
    
    allow_overdraft = forms.NullBooleanField(
        label='Allow Overdraft',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Yes'),
            ('false', 'No')
        ])
    )
    
    min_interest_rate = PercentageField(
        label='Minimum Interest Rate',
        required=False
    )
    
    max_interest_rate = PercentageField(
        label='Maximum Interest Rate',
        required=False
    )


class SavingsAccountFilterForm(DateRangeFilterForm, AmountRangeFilterForm):
    """Filter form for savings account search"""
    
    status = forms.ChoiceField(
        label='Status',
        choices=[('', 'All Statuses')] + list(SavingsAccount.STATUS_CHOICES),
        required=False
    )
    
    savings_product = forms.ModelChoiceField(
        label='Product',
        queryset=SavingsProduct.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    is_fixed_deposit = forms.NullBooleanField(
        label='Fixed Deposit',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Fixed Deposit'),
            ('false', 'Regular Savings')
        ])
    )
    
    # Override date fields for account opening dates
    date_from = forms.DateField(
        label='Opened From',
        required=False,
        widget=DatePickerInput()
    )
    
    date_to = forms.DateField(
        label='Opened To',
        required=False,
        widget=DatePickerInput()
    )


class SavingsTransactionFilterForm(DateRangeFilterForm, AmountRangeFilterForm):
    """Filter form for savings transaction search"""
    
    transaction_type = forms.ChoiceField(
        label='Transaction Type',
        choices=[('', 'All Types')] + list(SavingsTransaction.TRANSACTION_TYPES),
        required=False
    )
    
    is_reversed = forms.NullBooleanField(
        label='Reversed',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Reversed'),
            ('false', 'Active')
        ])
    )
    
    # Override date fields for transaction dates
    date_from = forms.DateField(
        label='Transaction From',
        required=False,
        widget=DatePickerInput()
    )
    
    date_to = forms.DateField(
        label='Transaction To',
        required=False,
        widget=DatePickerInput()
    )


class StandingOrderFilterForm(BaseFilterForm):
    """Filter form for standing order search"""
    
    status = forms.ChoiceField(
        label='Status',
        choices=[('', 'All Statuses')] + list(StandingOrder.STATUS_CHOICES),
        required=False
    )
    
    frequency = forms.ChoiceField(
        label='Frequency',
        choices=[('', 'All')] + list(StandingOrder.FREQUENCY_CHOICES),
        required=False
    )


class SavingsGoalFilterForm(BaseFilterForm):
    """Filter form for savings goal search"""
    
    goal_type = forms.ChoiceField(
        label='Goal Type',
        choices=[('', 'All Types')] + list(SavingsGoal.GOAL_TYPE_CHOICES),
        required=False
    )
    
    is_achieved = forms.NullBooleanField(
        label='Achieved',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Achieved'),
            ('false', 'In Progress')
        ])
    )


# =============================================================================
# SAVINGS PRODUCT FORMS
# =============================================================================

class SavingsProductForm(BootstrapFormMixin, MoneyFieldsMixin, RequiredFieldsMixin, forms.ModelForm):
    """Form for creating/editing savings products"""
    
    interest_rate = PercentageField(label=_('Interest Rate'))
    minimum_opening_balance = MoneyField(label=_('Minimum Opening Balance'), required=False)
    minimum_balance = MoneyField(label=_('Minimum Balance'), required=False)
    maximum_balance = MoneyField(label=_('Maximum Balance'), required=False)
    minimum_deposit_amount = MoneyField(label=_('Minimum Deposit'), required=False)
    minimum_withdrawal_amount = MoneyField(label=_('Minimum Withdrawal'), required=False)
    maximum_withdrawal_amount = MoneyField(label=_('Maximum Withdrawal'), required=False)
    overdraft_limit = MoneyField(label=_('Overdraft Limit'), required=False)
    overdraft_interest_rate = PercentageField(label=_('Overdraft Interest Rate'), required=False)
    withdrawal_fee_flat = MoneyField(label=_('Withdrawal Fee (Flat)'), required=False)
    withdrawal_fee_percentage = PercentageField(label=_('Withdrawal Fee (%)'), required=False)
    deposit_fee_flat = MoneyField(label=_('Deposit Fee (Flat)'), required=False)
    deposit_fee_percentage = PercentageField(label=_('Deposit Fee (%)'), required=False)
    account_maintenance_fee = MoneyField(label=_('Maintenance Fee'), required=False)
    early_withdrawal_penalty_rate = PercentageField(label=_('Early Withdrawal Penalty'), required=False)
    
    class Meta:
        model = SavingsProduct
        fields = [
            'name',
            'code',
            'description',
            'interest_rate',
            'interest_calculation_method',
            'interest_calculation_frequency',
            'interest_posting_frequency',
            'minimum_opening_balance',
            'minimum_balance',
            'maximum_balance',
            'minimum_deposit_amount',
            'minimum_withdrawal_amount',
            'maximum_withdrawal_amount',
            'allow_overdraft',
            'overdraft_limit',
            'overdraft_interest_rate',
            'withdrawal_fee_flat',
            'withdrawal_fee_percentage',
            'deposit_fee_flat',
            'deposit_fee_percentage',
            'dormancy_period_days',
            'account_maintenance_fee',
            'maintenance_fee_frequency',
            'is_fixed_deposit',
            'minimum_term_days',
            'maximum_term_days',
            'early_withdrawal_penalty_rate',
            'is_active',
            'is_group_product',
            'requires_approval',
            'is_main_account',
            'gl_account_code',
            'maximum_accounts_per_member',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., Regular Savings')
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., SAV-REG')
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Description of the savings product')
            }),
            'interest_calculation_method': forms.Select(attrs={'class': 'form-select'}),
            'interest_calculation_frequency': forms.Select(attrs={'class': 'form-select'}),
            'interest_posting_frequency': forms.Select(attrs={'class': 'form-select'}),
            'allow_overdraft': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'dormancy_period_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'maintenance_fee_frequency': forms.Select(attrs={'class': 'form-select'}),
            'is_fixed_deposit': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'minimum_term_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'maximum_term_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_group_product': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'requires_approval': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_main_account': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'gl_account_code': forms.TextInput(attrs={'class': 'form-control'}),
            'maximum_accounts_per_member': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set required fields
        required_fields = [
            'name', 'code', 'description', 'interest_rate',
            'interest_calculation_method'
        ]
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True
    
    def clean(self):
        """Validate product configuration"""
        cleaned_data = super().clean()
        
        minimum_balance = cleaned_data.get('minimum_balance')
        minimum_opening_balance = cleaned_data.get('minimum_opening_balance')
        maximum_balance = cleaned_data.get('maximum_balance')
        is_fixed_deposit = cleaned_data.get('is_fixed_deposit')
        minimum_term_days = cleaned_data.get('minimum_term_days')
        maximum_term_days = cleaned_data.get('maximum_term_days')
        
        errors = {}
        
        # Validate balance requirements
        if minimum_balance and minimum_opening_balance:
            if minimum_balance > minimum_opening_balance:
                errors['minimum_balance'] = _(
                    "Minimum balance cannot be greater than minimum opening balance"
                )
        
        if maximum_balance and minimum_opening_balance:
            if maximum_balance < minimum_opening_balance:
                errors['maximum_balance'] = _(
                    "Maximum balance must be greater than minimum opening balance"
                )
        
        # Validate fixed deposit configuration
        if is_fixed_deposit:
            if not minimum_term_days or minimum_term_days <= 0:
                errors['minimum_term_days'] = _(
                    "Fixed deposits must have a minimum term"
                )
        
        if maximum_term_days and minimum_term_days:
            if minimum_term_days > maximum_term_days:
                errors['maximum_term_days'] = _(
                    "Maximum term must be greater than minimum term"
                )
        
        if errors:
            raise ValidationError(errors)
        
        return cleaned_data


class SavingsProductQuickForm(BootstrapFormMixin, MoneyFieldsMixin, forms.ModelForm):
    """Quick form for creating basic savings products"""
    
    interest_rate = PercentageField(label=_('Interest Rate'))
    minimum_opening_balance = MoneyField(label=_('Minimum Opening Balance'), required=False)
    
    class Meta:
        model = SavingsProduct
        fields = [
            'name',
            'code',
            'description',
            'interest_rate',
            'minimum_opening_balance',
            'is_fixed_deposit',
            'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'is_fixed_deposit': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# =============================================================================
# INTEREST TIER FORMS
# =============================================================================

class InterestTierForm(BootstrapFormMixin, MoneyFieldsMixin, forms.ModelForm):
    """Form for creating/editing interest tiers"""
    
    min_balance = MoneyField(label=_('Minimum Balance'))
    max_balance = MoneyField(label=_('Maximum Balance'), required=False)
    interest_rate = PercentageField(label=_('Interest Rate'))
    
    class Meta:
        model = InterestTier
        fields = [
            'savings_product',
            'tier_name',
            'min_balance',
            'max_balance',
            'interest_rate',
            'is_active',
        ]
        widgets = {
            'savings_product': forms.Select(attrs={'class': 'form-select'}),
            'tier_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., Bronze, Silver, Gold')
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter to tiered products only
        self.fields['savings_product'].queryset = SavingsProduct.objects.filter(
            interest_calculation_method='TIERED',
            is_active=True
        )
    
    def clean(self):
        """Validate tier"""
        cleaned_data = super().clean()
        
        min_balance = cleaned_data.get('min_balance')
        max_balance = cleaned_data.get('max_balance')
        
        if max_balance and min_balance:
            if min_balance >= max_balance:
                raise ValidationError({
                    'max_balance': _("Maximum balance must be greater than minimum balance")
                })
        
        return cleaned_data


# =============================================================================
# SAVINGS ACCOUNT FORMS
# =============================================================================

class SavingsAccountForm(BootstrapFormMixin, MoneyFieldsMixin, RequiredFieldsMixin, forms.ModelForm):
    """Form for creating/editing savings accounts"""
    
    current_balance = MoneyField(label=_('Opening Balance'), required=False)
    overdraft_limit = MoneyField(label=_('Overdraft Limit'), required=False)
    fixed_deposit_amount = MoneyField(label=_('Fixed Deposit Amount'), required=False)
    
    class Meta:
        model = SavingsAccount
        fields = [
            'account_number',
            'member',
            'group',
            'savings_product',
            'current_balance',
            'status',
            'opening_date',
            'is_fixed_deposit',
            'term_length_days',
            'fixed_deposit_amount',
            'maturity_date',
            'auto_renew',
            'overdraft_limit',
            'overdraft_expiry_date',
        ]
        widgets = {
            'account_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Leave blank to auto-generate')
            }),
            'member': forms.Select(attrs={'class': 'form-select'}),
            'group': forms.Select(attrs={'class': 'form-select'}),
            'savings_product': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'opening_date': DatePickerInput(),
            'is_fixed_deposit': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'term_length_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'maturity_date': DatePickerInput(),
            'auto_renew': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'overdraft_expiry_date': DatePickerInput(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter members to active ones
        from members.models import Member
        self.fields['member'].queryset = Member.objects.filter(
            status='ACTIVE'
        ).order_by('last_name', 'first_name')
        
        # Filter groups to active ones
        from members.models import MemberGroup
        self.fields['group'].queryset = MemberGroup.objects.filter(
            is_active=True
        )
        
        # Filter savings products to active ones
        self.fields['savings_product'].queryset = SavingsProduct.objects.filter(
            is_active=True
        ).order_by('name')
        
        # Set default opening date
        if not self.is_bound:
            self.fields['opening_date'].initial = timezone.now().date()
    
    def clean(self):
        """Validate account"""
        cleaned_data = super().clean()
        
        savings_product = cleaned_data.get('savings_product')
        current_balance = cleaned_data.get('current_balance')
        is_fixed_deposit = cleaned_data.get('is_fixed_deposit')
        term_length_days = cleaned_data.get('term_length_days')
        fixed_deposit_amount = cleaned_data.get('fixed_deposit_amount')
        
        errors = {}
        
        # Validate opening balance
        if savings_product and current_balance:
            if current_balance < savings_product.minimum_opening_balance:
                errors['current_balance'] = _(
                    f"Minimum opening balance is {savings_product.formatted_minimum_opening_balance}"
                )
        
        # Validate fixed deposit
        if is_fixed_deposit:
            if not term_length_days:
                errors['term_length_days'] = _("Term length is required for fixed deposits")
            if not fixed_deposit_amount:
                errors['fixed_deposit_amount'] = _("Deposit amount is required for fixed deposits")
        
        if errors:
            raise ValidationError(errors)
        
        return cleaned_data


class SavingsAccountQuickOpenForm(BootstrapFormMixin, MoneyFieldsMixin, forms.Form):
    """Quick form for opening a savings account"""
    
    member = forms.ModelChoiceField(
        label=_('Member'),
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    savings_product = forms.ModelChoiceField(
        label=_('Savings Product'),
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    opening_balance = MoneyField(
        label=_('Opening Balance'),
        help_text=_('Initial deposit amount')
    )
    
    payment_method = forms.ModelChoiceField(
        label=_('Payment Method'),
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    reference_number = forms.CharField(
        label=_('Reference Number'),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('External reference (optional)')
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter members
        from members.models import Member
        self.fields['member'].queryset = Member.objects.filter(
            status='ACTIVE'
        ).order_by('last_name', 'first_name')
        
        # Filter savings products
        self.fields['savings_product'].queryset = SavingsProduct.objects.filter(
            is_active=True
        ).order_by('name')
        
        # Filter payment methods
        from core.models import PaymentMethod
        self.fields['payment_method'].queryset = PaymentMethod.objects.filter(
            is_active=True
        )


class SavingsAccountApprovalForm(BootstrapFormMixin, forms.Form):
    """Form for approving savings accounts"""
    
    confirm_approval = forms.BooleanField(
        label=_('I confirm that I want to approve this account'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    notes = forms.CharField(
        label=_('Approval Notes'),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': _('Optional notes')
        })
    )


# =============================================================================
# SAVINGS TRANSACTION FORMS
# =============================================================================

class SavingsTransactionForm(BootstrapFormMixin, MoneyFieldsMixin, forms.ModelForm):
    """Form for creating savings transactions"""
    
    amount = MoneyField(label=_('Amount'))
    fees = MoneyField(label=_('Fees'), required=False)
    tax_amount = MoneyField(label=_('Tax Amount'), required=False)
    
    class Meta:
        model = SavingsTransaction
        fields = [
            'account',
            'transaction_type',
            'amount',
            'fees',
            'tax_amount',
            'transaction_date',
            'payment_method',
            'reference_number',
            'description',
            'linked_account',
        ]
        widgets = {
            'account': forms.Select(attrs={'class': 'form-select'}),
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'transaction_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'reference_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('External reference')
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _('Transaction description')
            }),
            'linked_account': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter accounts to active ones
        self.fields['account'].queryset = SavingsAccount.objects.filter(
            status__in=['ACTIVE', 'DORMANT']
        )
        
        self.fields['linked_account'].queryset = SavingsAccount.objects.filter(
            status__in=['ACTIVE', 'DORMANT']
        )
        
        # Filter payment methods
        from core.models import PaymentMethod
        self.fields['payment_method'].queryset = PaymentMethod.objects.filter(
            is_active=True
        )
        
        # Set default transaction date
        if not self.is_bound:
            self.fields['transaction_date'].initial = timezone.now()


class DepositForm(BootstrapFormMixin, MoneyFieldsMixin, forms.Form):
    """Quick deposit form"""
    
    account = forms.ModelChoiceField(
        label=_('Account'),
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    amount = MoneyField(
        label=_('Deposit Amount')
    )
    
    payment_method = forms.ModelChoiceField(
        label=_('Payment Method'),
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    reference_number = forms.CharField(
        label=_('Reference Number'),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('External reference (optional)')
        })
    )
    
    description = forms.CharField(
        label=_('Description'),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': _('Transaction description (optional)')
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.member = kwargs.pop('member', None)
        super().__init__(*args, **kwargs)
        
        # Filter accounts
        if self.member:
            self.fields['account'].queryset = SavingsAccount.objects.filter(
                member=self.member,
                status__in=['ACTIVE', 'DORMANT', 'PENDING_APPROVAL']
            )
        else:
            self.fields['account'].queryset = SavingsAccount.objects.filter(
                status__in=['ACTIVE', 'DORMANT', 'PENDING_APPROVAL']
            )
        
        # Filter payment methods
        from core.models import PaymentMethod
        self.fields['payment_method'].queryset = PaymentMethod.objects.filter(
            is_active=True
        )


class WithdrawalForm(BootstrapFormMixin, MoneyFieldsMixin, forms.Form):
    """Quick withdrawal form"""
    
    account = forms.ModelChoiceField(
        label=_('Account'),
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    amount = MoneyField(
        label=_('Withdrawal Amount')
    )
    
    payment_method = forms.ModelChoiceField(
        label=_('Payment Method'),
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    reference_number = forms.CharField(
        label=_('Reference Number'),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('External reference (optional)')
        })
    )
    
    description = forms.CharField(
        label=_('Description'),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': _('Transaction description (optional)')
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.member = kwargs.pop('member', None)
        super().__init__(*args, **kwargs)
        
        # Filter accounts
        if self.member:
            self.fields['account'].queryset = SavingsAccount.objects.filter(
                member=self.member,
                status='ACTIVE'
            )
        else:
            self.fields['account'].queryset = SavingsAccount.objects.filter(
                status='ACTIVE'
            )
        
        # Filter payment methods
        from core.models import PaymentMethod
        self.fields['payment_method'].queryset = PaymentMethod.objects.filter(
            is_active=True
        )
    
    def clean(self):
        """Validate withdrawal"""
        cleaned_data = super().clean()
        
        account = cleaned_data.get('account')
        amount = cleaned_data.get('amount')
        
        if account and amount:
            is_allowed, message = account.is_withdrawal_allowed(amount)
            if not is_allowed:
                raise ValidationError({'amount': message})
        
        return cleaned_data


class TransferForm(BootstrapFormMixin, MoneyFieldsMixin, forms.Form):
    """Account transfer form"""
    
    source_account = forms.ModelChoiceField(
        label=_('From Account'),
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    destination_account = forms.ModelChoiceField(
        label=_('To Account'),
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    amount = MoneyField(
        label=_('Transfer Amount')
    )
    
    description = forms.CharField(
        label=_('Description'),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': _('Transfer description (optional)')
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.member = kwargs.pop('member', None)
        super().__init__(*args, **kwargs)
        
        # Filter accounts
        if self.member:
            self.fields['source_account'].queryset = SavingsAccount.objects.filter(
                member=self.member,
                status='ACTIVE'
            )
            self.fields['destination_account'].queryset = SavingsAccount.objects.filter(
                status='ACTIVE'
            )
        else:
            self.fields['source_account'].queryset = SavingsAccount.objects.filter(
                status='ACTIVE'
            )
            self.fields['destination_account'].queryset = SavingsAccount.objects.filter(
                status='ACTIVE'
            )
    
    def clean(self):
        """Validate transfer"""
        cleaned_data = super().clean()
        
        source_account = cleaned_data.get('source_account')
        destination_account = cleaned_data.get('destination_account')
        amount = cleaned_data.get('amount')
        
        errors = {}
        
        # Check if accounts are different
        if source_account and destination_account:
            if source_account == destination_account:
                errors['destination_account'] = _(
                    "Source and destination accounts must be different"
                )
        
        # Validate withdrawal from source
        if source_account and amount:
            is_allowed, message = source_account.is_withdrawal_allowed(amount)
            if not is_allowed:
                errors['amount'] = message
        
        # Validate deposit to destination
        if destination_account and amount:
            is_allowed, message = destination_account.is_deposit_allowed(amount)
            if not is_allowed:
                errors['amount'] = message
        
        if errors:
            raise ValidationError(errors)
        
        return cleaned_data


class TransactionReversalForm(BootstrapFormMixin, forms.Form):
    """Form for reversing transactions"""
    
    reversal_reason = forms.CharField(
        label=_('Reversal Reason'),
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Explain why this transaction is being reversed')
        })
    )
    
    confirm_reversal = forms.BooleanField(
        label=_('I confirm that I want to reverse this transaction'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


# =============================================================================
# STANDING ORDER FORMS
# =============================================================================

class StandingOrderForm(BootstrapFormMixin, MoneyFieldsMixin, forms.ModelForm):
    """Form for creating/editing standing orders"""
    
    amount = MoneyField(label=_('Transfer Amount'))
    
    class Meta:
        model = StandingOrder
        fields = [
            'source_account',
            'destination_account',
            'amount',
            'frequency',
            'start_date',
            'end_date',
            'description',
        ]
        widgets = {
            'source_account': forms.Select(attrs={'class': 'form-select'}),
            'destination_account': forms.Select(attrs={'class': 'form-select'}),
            'frequency': forms.Select(attrs={'class': 'form-select'}),
            'start_date': DatePickerInput(),
            'end_date': DatePickerInput(),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _('Description of this standing order')
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.member = kwargs.pop('member', None)
        super().__init__(*args, **kwargs)
        
        # Filter accounts
        if self.member:
            self.fields['source_account'].queryset = SavingsAccount.objects.filter(
                member=self.member,
                status='ACTIVE'
            )
        else:
            self.fields['source_account'].queryset = SavingsAccount.objects.filter(
                status='ACTIVE'
            )
        
        self.fields['destination_account'].queryset = SavingsAccount.objects.filter(
            status='ACTIVE'
        )
        
        # Set default start date
        if not self.is_bound:
            self.fields['start_date'].initial = timezone.now().date()
    
    def clean(self):
        """Validate standing order"""
        cleaned_data = super().clean()
        
        source_account = cleaned_data.get('source_account')
        destination_account = cleaned_data.get('destination_account')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        errors = {}
        
        # Check if accounts are different
        if source_account and destination_account:
            if source_account == destination_account:
                errors['destination_account'] = _(
                    "Source and destination accounts must be different"
                )
        
        # Validate dates
        if start_date and end_date:
            if start_date >= end_date:
                errors['end_date'] = _("End date must be after start date")
        
        if errors:
            raise ValidationError(errors)
        
        return cleaned_data


# =============================================================================
# SAVINGS GOAL FORMS
# =============================================================================

class SavingsGoalForm(BootstrapFormMixin, MoneyFieldsMixin, forms.ModelForm):
    """Form for creating/editing savings goals"""
    
    target_amount = MoneyField(label=_('Target Amount'))
    current_amount = MoneyField(label=_('Current Amount'), required=False)
    
    class Meta:
        model = SavingsGoal
        fields = [
            'account',
            'name',
            'description',
            'goal_type',
            'target_amount',
            'current_amount',
            'start_date',
            'target_date',
        ]
        widgets = {
            'account': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., New Car, House Down Payment')
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _('Description of your goal')
            }),
            'goal_type': forms.Select(attrs={'class': 'form-select'}),
            'start_date': DatePickerInput(),
            'target_date': DatePickerInput(),
        }
    
    def __init__(self, *args, **kwargs):
        self.member = kwargs.pop('member', None)
        super().__init__(*args, **kwargs)
        
        # Filter accounts
        if self.member:
            self.fields['account'].queryset = SavingsAccount.objects.filter(
                member=self.member,
                status__in=['ACTIVE', 'DORMANT']
            )
        else:
            self.fields['account'].queryset = SavingsAccount.objects.filter(
                status__in=['ACTIVE', 'DORMANT']
            )
        
        # Set default dates
        if not self.is_bound:
            self.fields['start_date'].initial = timezone.now().date()
    
    def clean(self):
        """Validate goal"""
        cleaned_data = super().clean()
        
        start_date = cleaned_data.get('start_date')
        target_date = cleaned_data.get('target_date')
        target_amount = cleaned_data.get('target_amount')
        
        errors = {}
        
        # Validate dates
        if start_date and target_date:
            if target_date <= start_date:
                errors['target_date'] = _("Target date must be after start date")
        
        # Validate amount
        if target_amount:
            validate_positive_amount(target_amount)
        
        if errors:
            raise ValidationError(errors)
        
        return cleaned_data


# =============================================================================
# BULK OPERATION FORMS
# =============================================================================

class BulkInterestCalculationForm(BootstrapFormMixin, forms.Form):
    """Form for bulk interest calculation"""
    
    calculation_date = forms.DateField(
        label=_('Calculation Date'),
        widget=DatePickerInput(),
        help_text=_('Date to calculate interest up to')
    )
    
    savings_product = forms.ModelChoiceField(
        label=_('Savings Product (Optional)'),
        queryset=SavingsProduct.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text=_('Leave blank to calculate for all products')
    )
    
    recalculate_existing = forms.BooleanField(
        label=_('Recalculate existing calculations'),
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    confirm_calculation = forms.BooleanField(
        label=_('I confirm that I want to calculate interest'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set default calculation date
        if not self.is_bound:
            self.fields['calculation_date'].initial = timezone.now().date()


class BulkInterestPostingForm(BootstrapFormMixin, forms.Form):
    """Form for bulk interest posting"""
    
    posting_date = forms.DateField(
        label=_('Posting Date'),
        widget=DatePickerInput()
    )
    
    period_start = forms.DateField(
        label=_('Period Start'),
        widget=DatePickerInput(),
        required=False,
        help_text=_('Optional: Post interest calculated from this date')
    )
    
    period_end = forms.DateField(
        label=_('Period End'),
        widget=DatePickerInput(),
        required=False,
        help_text=_('Optional: Post interest calculated up to this date')
    )
    
    confirm_posting = forms.BooleanField(
        label=_('I confirm that I want to post interest'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set default posting date
        if not self.is_bound:
            self.fields['posting_date'].initial = timezone.now().date()


# =============================================================================
# REPORTING FORMS
# =============================================================================

class SavingsReportForm(BootstrapFormMixin, DateRangeFormMixin, forms.Form):
    """Form for generating savings reports"""
    
    report_type = forms.ChoiceField(
        label=_('Report Type'),
        choices=[
            ('ACCOUNT_SUMMARY', _('Account Summary')),
            ('TRANSACTION_REPORT', _('Transaction Report')),
            ('INTEREST_REPORT', _('Interest Report')),
            ('PRODUCT_PERFORMANCE', _('Product Performance')),
            ('DORMANT_ACCOUNTS', _('Dormant Accounts')),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    savings_product = forms.ModelChoiceField(
        label=_('Savings Product'),
        queryset=SavingsProduct.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text=_('Leave blank for all products')
    )
    
    start_date = forms.DateField(
        label=_('Start Date'),
        required=False,
        widget=DatePickerInput()
    )
    
    end_date = forms.DateField(
        label=_('End Date'),
        required=False,
        widget=DatePickerInput()
    )
    
    format = forms.ChoiceField(
        label=_('Format'),
        choices=[
            ('PDF', 'PDF'),
            ('EXCEL', 'Excel'),
            ('CSV', 'CSV'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )