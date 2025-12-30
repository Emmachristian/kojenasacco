# loans/forms.py

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
    LoanProduct,
    LoanApplication,
    Loan,
    LoanPayment,
    LoanGuarantor,
    LoanCollateral,
    LoanSchedule,
    LoanDocument
)

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# LOAN PRODUCT FILTER FORMS
# =============================================================================

class LoanProductFilterForm(BaseFilterForm):
    """Filter form for loan product search"""
    
    is_active = forms.NullBooleanField(
        label=_('Active'),
        required=False,
        widget=forms.Select(choices=[
            ('', _('All')),
            ('true', _('Active')),
            ('false', _('Inactive'))
        ])
    )
    
    interest_type = forms.ChoiceField(
        label=_('Interest Type'),
        choices=[('', _('All Types'))] + list(LoanProduct.INTEREST_TYPES),
        required=False
    )
    
    repayment_cycle = forms.ChoiceField(
        label=_('Repayment Cycle'),
        choices=[('', _('All'))] + list(LoanProduct.REPAYMENT_CYCLE),
        required=False
    )
    
    guarantor_required = forms.NullBooleanField(
        label=_('Guarantor Required'),
        required=False,
        widget=forms.Select(choices=[
            ('', _('All')),
            ('true', _('Yes')),
            ('false', _('No'))
        ])
    )
    
    collateral_required = forms.NullBooleanField(
        label=_('Collateral Required'),
        required=False,
        widget=forms.Select(choices=[
            ('', _('All')),
            ('true', _('Yes')),
            ('false', _('No'))
        ])
    )
    
    allow_top_up = forms.NullBooleanField(
        label=_('Allow Top Up'),
        required=False,
        widget=forms.Select(choices=[
            ('', _('All')),
            ('true', _('Yes')),
            ('false', _('No'))
        ])
    )
    
    allow_early_repayment = forms.NullBooleanField(
        label=_('Allow Early Repayment'),
        required=False,
        widget=forms.Select(choices=[
            ('', _('All')),
            ('true', _('Yes')),
            ('false', _('No'))
        ])
    )
    
    min_interest_rate = PercentageField(
        label=_('Minimum Interest Rate'),
        required=False
    )
    
    max_interest_rate = PercentageField(
        label=_('Maximum Interest Rate'),
        required=False
    )


class LoanApplicationFilterForm(DateRangeFilterForm, AmountRangeFilterForm):
    """Filter form for loan application search"""
    
    status = forms.ChoiceField(
        label=_('Status'),
        choices=[('', _('All Statuses'))] + list(LoanApplication.STATUS_CHOICES),
        required=False
    )
    
    loan_product = forms.ModelChoiceField(
        label=_('Loan Product'),
        queryset=LoanProduct.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    processing_fee_paid = forms.NullBooleanField(
        label=_('Processing Fee Paid'),
        required=False,
        widget=forms.Select(choices=[
            ('', _('All')),
            ('true', _('Paid')),
            ('false', _('Not Paid'))
        ])
    )
    
    # Override date fields
    date_from = forms.DateField(
        label=_('Application Date From'),
        required=False,
        widget=DatePickerInput()
    )
    
    date_to = forms.DateField(
        label=_('Application Date To'),
        required=False,
        widget=DatePickerInput()
    )


class LoanFilterForm(DateRangeFilterForm, AmountRangeFilterForm):
    """Filter form for loan search"""
    
    status = forms.ChoiceField(
        label=_('Status'),
        choices=[('', _('All Statuses'))] + list(Loan.STATUS_CHOICES),
        required=False
    )
    
    loan_product = forms.ModelChoiceField(
        label=_('Loan Product'),
        queryset=LoanProduct.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    overdue = forms.NullBooleanField(
        label=_('Overdue'),
        required=False,
        widget=forms.Select(choices=[
            ('', _('All')),
            ('true', _('Overdue')),
            ('false', _('Current'))
        ])
    )
    
    fully_paid = forms.NullBooleanField(
        label=_('Fully Paid'),
        required=False,
        widget=forms.Select(choices=[
            ('', _('All')),
            ('true', _('Fully Paid')),
            ('false', _('Outstanding Balance'))
        ])
    )
    
    min_days_in_arrears = forms.IntegerField(
        label=_('Minimum Days in Arrears'),
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0})
    )
    
    # Override date fields
    date_from = forms.DateField(
        label=_('Disbursement Date From'),
        required=False,
        widget=DatePickerInput()
    )
    
    date_to = forms.DateField(
        label=_('Disbursement Date To'),
        required=False,
        widget=DatePickerInput()
    )


class LoanPaymentFilterForm(DateRangeFilterForm, AmountRangeFilterForm):
    """Filter form for loan payment search"""
    
    payment_method = forms.ChoiceField(
        label=_('Payment Method'),
        choices=[('', _('All Methods'))] + list(LoanPayment.PAYMENT_METHODS),
        required=False
    )
    
    is_reversed = forms.NullBooleanField(
        label=_('Reversed'),
        required=False,
        widget=forms.Select(choices=[
            ('', _('All')),
            ('true', _('Reversed')),
            ('false', _('Active'))
        ])
    )
    
    # Override date fields
    date_from = forms.DateField(
        label=_('Payment Date From'),
        required=False,
        widget=DatePickerInput()
    )
    
    date_to = forms.DateField(
        label=_('Payment Date To'),
        required=False,
        widget=DatePickerInput()
    )


class LoanGuarantorFilterForm(BaseFilterForm):
    """Filter form for loan guarantor search"""
    
    status = forms.ChoiceField(
        label=_('Status'),
        choices=[('', _('All Statuses'))] + list(LoanGuarantor.STATUS_CHOICES),
        required=False
    )


class LoanCollateralFilterForm(BaseFilterForm):
    """Filter form for loan collateral search"""
    
    collateral_type = forms.ChoiceField(
        label=_('Collateral Type'),
        choices=[('', _('All Types'))] + list(LoanCollateral.COLLATERAL_TYPES),
        required=False
    )
    
    is_verified = forms.NullBooleanField(
        label=_('Verified'),
        required=False,
        widget=forms.Select(choices=[
            ('', _('All')),
            ('true', _('Verified')),
            ('false', _('Not Verified'))
        ])
    )
    
    is_insured = forms.NullBooleanField(
        label=_('Insured'),
        required=False,
        widget=forms.Select(choices=[
            ('', _('All')),
            ('true', _('Insured')),
            ('false', _('Not Insured'))
        ])
    )


class LoanScheduleFilterForm(DateRangeFilterForm):
    """Filter form for loan schedule search"""
    
    status = forms.ChoiceField(
        label=_('Status'),
        choices=[('', _('All Statuses'))] + list(LoanSchedule.STATUS_CHOICES),
        required=False
    )
    
    overdue = forms.NullBooleanField(
        label=_('Overdue'),
        required=False,
        widget=forms.Select(choices=[
            ('', _('All')),
            ('true', _('Overdue')),
            ('false', _('Not Overdue'))
        ])
    )
    
    # Override date fields
    date_from = forms.DateField(
        label=_('Due Date From'),
        required=False,
        widget=DatePickerInput()
    )
    
    date_to = forms.DateField(
        label=_('Due Date To'),
        required=False,
        widget=DatePickerInput()
    )


# =============================================================================
# LOAN PRODUCT FORMS
# =============================================================================

class LoanProductForm(BootstrapFormMixin, MoneyFieldsMixin, RequiredFieldsMixin, forms.ModelForm):
    """Form for creating/editing loan products"""
    
    min_amount = MoneyField(label=_('Minimum Loan Amount'))
    max_amount = MoneyField(label=_('Maximum Loan Amount'))
    interest_rate = PercentageField(label=_('Interest Rate'))
    loan_processing_fee = PercentageField(label=_('Processing Fee'), required=False)
    insurance_fee = PercentageField(label=_('Insurance Fee'), required=False)
    minimum_savings_percentage = PercentageField(label=_('Minimum Savings Required'), required=False)
    early_repayment_fee = PercentageField(label=_('Early Repayment Fee'), required=False)
    penalty_rate = PercentageField(label=_('Penalty Rate'), required=False)
    
    class Meta:
        model = LoanProduct
        fields = [
            'name',
            'code',
            'description',
            'min_amount',
            'max_amount',
            'interest_rate',
            'interest_type',
            'interest_calculation',
            'loan_processing_fee',
            'insurance_fee',
            'min_term',
            'max_term',
            'repayment_cycle',
            'grace_period',
            'minimum_savings_percentage',
            'minimum_shares_required',
            'guarantor_required',
            'number_of_guarantors',
            'collateral_required',
            'allow_top_up',
            'allow_early_repayment',
            'early_repayment_fee',
            'penalty_rate',
            'penalty_grace_period',
            'penalty_frequency',
            'is_active',
            'gl_account_code',
            'maximum_loans_per_member',
            'requires_approval',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., Personal Loan')
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., PERS-001')
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Description of the loan product')
            }),
            'interest_type': forms.Select(attrs={'class': 'form-select'}),
            'interest_calculation': forms.Select(attrs={'class': 'form-select'}),
            'min_term': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'max_term': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'repayment_cycle': forms.Select(attrs={'class': 'form-select'}),
            'grace_period': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'minimum_shares_required': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'guarantor_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'number_of_guarantors': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'collateral_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allow_top_up': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allow_early_repayment': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'penalty_grace_period': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'penalty_frequency': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'gl_account_code': forms.TextInput(attrs={'class': 'form-control'}),
            'maximum_loans_per_member': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'requires_approval': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set required fields
        required_fields = [
            'name', 'code', 'description', 'min_amount', 'max_amount',
            'interest_rate', 'min_term', 'max_term'
        ]
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True
    
    def clean(self):
        """Validate loan product"""
        cleaned_data = super().clean()
        
        min_amount = cleaned_data.get('min_amount')
        max_amount = cleaned_data.get('max_amount')
        min_term = cleaned_data.get('min_term')
        max_term = cleaned_data.get('max_term')
        guarantor_required = cleaned_data.get('guarantor_required')
        number_of_guarantors = cleaned_data.get('number_of_guarantors')
        
        errors = {}
        
        # Validate amount range
        if min_amount and max_amount:
            if min_amount >= max_amount:
                errors['max_amount'] = _(
                    "Maximum amount must be greater than minimum amount"
                )
        
        # Validate term range
        if min_term and max_term:
            if min_term >= max_term:
                errors['max_term'] = _(
                    "Maximum term must be greater than minimum term"
                )
        
        # Validate guarantor requirement
        if guarantor_required and number_of_guarantors == 0:
            errors['number_of_guarantors'] = _(
                "Number of guarantors required when guarantors are mandatory"
            )
        
        if errors:
            raise ValidationError(errors)
        
        return cleaned_data


# =============================================================================
# LOAN APPLICATION FORMS
# =============================================================================

class LoanApplicationForm(BootstrapFormMixin, MoneyFieldsMixin, RequiredFieldsMixin, forms.ModelForm):
    """Form for creating/editing loan applications"""
    
    amount_requested = MoneyField(label=_('Amount Requested'))
    
    class Meta:
        model = LoanApplication
        fields = [
            'member',
            'loan_product',
            'amount_requested',
            'purpose',
            'term_months',
            'disbursement_method',
            'disbursement_account',
            'notes',
        ]
        widgets = {
            'member': forms.Select(attrs={'class': 'form-select'}),
            'loan_product': forms.Select(attrs={'class': 'form-select'}),
            'purpose': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Purpose for which loan is being requested')
            }),
            'term_months': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': _('Loan term in months')
            }),
            'disbursement_method': forms.Select(attrs={'class': 'form-select'}),
            'disbursement_account': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Account number or phone number')
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _('Additional notes (optional)')
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter members to active ones
        from members.models import Member
        self.fields['member'].queryset = Member.objects.filter(
            status='ACTIVE'
        ).order_by('last_name', 'first_name')
        
        # Filter loan products to active ones
        self.fields['loan_product'].queryset = LoanProduct.objects.filter(
            is_active=True
        ).order_by('name')
        
        # Set required fields
        required_fields = ['member', 'loan_product', 'amount_requested', 'purpose', 'term_months']
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True
    
    def clean(self):
        """Validate application"""
        cleaned_data = super().clean()
        
        loan_product = cleaned_data.get('loan_product')
        amount_requested = cleaned_data.get('amount_requested')
        term_months = cleaned_data.get('term_months')
        
        errors = {}
        
        if loan_product and amount_requested:
            # Validate amount
            if amount_requested < loan_product.min_amount:
                errors['amount_requested'] = _(
                    f"Amount below product minimum of {loan_product.formatted_min_amount}"
                )
            
            if amount_requested > loan_product.max_amount:
                errors['amount_requested'] = _(
                    f"Amount exceeds product maximum of {loan_product.formatted_max_amount}"
                )
        
        if loan_product and term_months:
            # Validate term
            if term_months < loan_product.min_term:
                errors['term_months'] = _(
                    f"Term below product minimum of {loan_product.min_term} months"
                )
            
            if term_months > loan_product.max_term:
                errors['term_months'] = _(
                    f"Term exceeds product maximum of {loan_product.max_term} months"
                )
        
        if errors:
            raise ValidationError(errors)
        
        return cleaned_data


class LoanApplicationQuickForm(BootstrapFormMixin, MoneyFieldsMixin, forms.Form):
    """Quick form for loan applications"""
    
    member = forms.ModelChoiceField(
        label=_('Member'),
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    loan_product = forms.ModelChoiceField(
        label=_('Loan Product'),
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    amount_requested = MoneyField(
        label=_('Amount Requested')
    )
    
    term_months = forms.IntegerField(
        label=_('Loan Term (Months)'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1})
    )
    
    purpose = forms.CharField(
        label=_('Loan Purpose'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': _('Purpose for which loan is being requested')
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter members
        from members.models import Member
        self.fields['member'].queryset = Member.objects.filter(
            status='ACTIVE'
        ).order_by('last_name', 'first_name')
        
        # Filter loan products
        self.fields['loan_product'].queryset = LoanProduct.objects.filter(
            is_active=True
        ).order_by('name')


class LoanApplicationApprovalForm(BootstrapFormMixin, MoneyFieldsMixin, forms.Form):
    """Form for approving loan applications"""
    
    decision = forms.ChoiceField(
        label=_('Decision'),
        choices=[
            ('', _('-- Select Decision --')),
            ('APPROVE', _('Approve')),
            ('REJECT', _('Reject')),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    approved_amount = MoneyField(
        label=_('Approved Amount'),
        required=False,
        help_text=_('Leave blank to use requested amount')
    )
    
    approved_term = forms.IntegerField(
        label=_('Approved Term (Months)'),
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        help_text=_('Leave blank to use requested term')
    )
    
    approved_interest_rate = PercentageField(
        label=_('Approved Interest Rate'),
        required=False,
        help_text=_('Leave blank to use product rate')
    )
    
    rejection_reason = forms.CharField(
        label=_('Rejection Reason'),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Required if rejecting')
        })
    )
    
    notes = forms.CharField(
        label=_('Notes'),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': _('Additional notes (optional)')
        })
    )
    
    def clean(self):
        """Validate approval form"""
        cleaned_data = super().clean()
        
        decision = cleaned_data.get('decision')
        rejection_reason = cleaned_data.get('rejection_reason')
        
        if not decision:
            raise ValidationError({'decision': _('Please select a decision')})
        
        if decision == 'REJECT' and not rejection_reason:
            raise ValidationError({
                'rejection_reason': _('Rejection reason is required when rejecting')
            })
        
        return cleaned_data


# =============================================================================
# LOAN FORMS
# =============================================================================

class LoanDisbursementForm(BootstrapFormMixin, MoneyFieldsMixin, forms.Form):
    """Form for disbursing approved loans"""
    
    disbursement_date = forms.DateField(
        label=_('Disbursement Date'),
        widget=DatePickerInput()
    )
    
    disbursement_method = forms.ModelChoiceField(
        label=_('Disbursement Method'),
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    disbursement_reference = forms.CharField(
        label=_('Reference Number'),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('External reference (optional)')
        })
    )
    
    first_payment_date = forms.DateField(
        label=_('First Payment Date'),
        widget=DatePickerInput(),
        help_text=_('Date when first installment is due')
    )
    
    notes = forms.CharField(
        label=_('Notes'),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': _('Additional notes (optional)')
        })
    )
    
    confirm_disbursement = forms.BooleanField(
        label=_('I confirm that I want to disburse this loan'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter payment methods
        from core.models import PaymentMethod
        self.fields['disbursement_method'].queryset = PaymentMethod.objects.filter(
            is_active=True
        )
        
        # Set default dates
        if not self.is_bound:
            self.fields['disbursement_date'].initial = timezone.now().date()
            # First payment typically 30 days after disbursement
            self.fields['first_payment_date'].initial = (
                timezone.now().date() + timedelta(days=30)
            )


# =============================================================================
# LOAN PAYMENT FORMS
# =============================================================================

class LoanPaymentForm(BootstrapFormMixin, MoneyFieldsMixin, forms.ModelForm):
    """Form for recording loan payments"""
    
    amount = MoneyField(label=_('Payment Amount'))
    principal_amount = MoneyField(label=_('Principal Amount'), required=False)
    interest_amount = MoneyField(label=_('Interest Amount'), required=False)
    penalty_amount = MoneyField(label=_('Penalty Amount'), required=False)
    fee_amount = MoneyField(label=_('Fee Amount'), required=False)
    
    class Meta:
        model = LoanPayment
        fields = [
            'loan',
            'payment_date',
            'amount',
            'principal_amount',
            'interest_amount',
            'penalty_amount',
            'fee_amount',
            'payment_method',
            'payment_method_ref',
            'reference_number',
            'receipt_number',
            'notes',
        ]
        widgets = {
            'loan': forms.Select(attrs={'class': 'form-select'}),
            'payment_date': DatePickerInput(),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'payment_method_ref': forms.Select(attrs={'class': 'form-select'}),
            'reference_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('External reference')
            }),
            'receipt_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Receipt number')
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _('Additional notes (optional)')
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter loans to active ones
        self.fields['loan'].queryset = Loan.objects.filter(
            status='ACTIVE'
        )
        
        # Filter payment methods
        from core.models import PaymentMethod
        self.fields['payment_method_ref'].queryset = PaymentMethod.objects.filter(
            is_active=True
        )
        
        # Set default payment date
        if not self.is_bound:
            self.fields['payment_date'].initial = timezone.now().date()
        
        # Set required fields
        required_fields = ['loan', 'payment_date', 'amount', 'payment_method']
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True


class QuickLoanPaymentForm(BootstrapFormMixin, MoneyFieldsMixin, forms.Form):
    """Quick form for loan payments"""
    
    loan = forms.ModelChoiceField(
        label=_('Loan'),
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    amount = MoneyField(
        label=_('Payment Amount')
    )
    
    payment_method = forms.ChoiceField(
        label=_('Payment Method'),
        choices=LoanPayment.PAYMENT_METHODS,
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
        self.member = kwargs.pop('member', None)
        super().__init__(*args, **kwargs)
        
        # Filter loans
        if self.member:
            self.fields['loan'].queryset = Loan.objects.filter(
                member=self.member,
                status='ACTIVE'
            )
        else:
            self.fields['loan'].queryset = Loan.objects.filter(
                status='ACTIVE'
            )


class PaymentReversalForm(BootstrapFormMixin, forms.Form):
    """Form for reversing loan payments"""
    
    reversal_reason = forms.CharField(
        label=_('Reversal Reason'),
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Explain why this payment is being reversed')
        })
    )
    
    confirm_reversal = forms.BooleanField(
        label=_('I confirm that I want to reverse this payment'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


# =============================================================================
# LOAN GUARANTOR FORMS
# =============================================================================

class LoanGuarantorForm(BootstrapFormMixin, MoneyFieldsMixin, forms.ModelForm):
    """Form for adding/editing loan guarantors"""
    
    guarantee_amount = MoneyField(label=_('Guarantee Amount'))
    
    class Meta:
        model = LoanGuarantor
        fields = [
            'loan_application',
            'guarantor',
            'guarantee_amount',
            'relationship',
            'notes',
        ]
        widgets = {
            'loan_application': forms.Select(attrs={'class': 'form-select'}),
            'guarantor': forms.Select(attrs={'class': 'form-select'}),
            'relationship': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., Spouse, Sibling, Friend')
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _('Additional notes (optional)')
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter loan applications
        self.fields['loan_application'].queryset = LoanApplication.objects.filter(
            status__in=['DRAFT', 'SUBMITTED', 'UNDER_REVIEW']
        )
        
        # Filter guarantors to active members
        from members.models import Member
        self.fields['guarantor'].queryset = Member.objects.filter(
            status='ACTIVE'
        ).order_by('last_name', 'first_name')
    
    def clean(self):
        """Validate guarantor"""
        cleaned_data = super().clean()
        
        guarantor = cleaned_data.get('guarantor')
        loan_application = cleaned_data.get('loan_application')
        
        if guarantor and loan_application:
            if guarantor == loan_application.member:
                raise ValidationError({
                    'guarantor': _('Guarantor cannot be the loan applicant')
                })
        
        return cleaned_data


# =============================================================================
# LOAN COLLATERAL FORMS
# =============================================================================

class LoanCollateralForm(BootstrapFormMixin, MoneyFieldsMixin, forms.ModelForm):
    """Form for adding/editing loan collateral"""
    
    estimated_value = MoneyField(label=_('Estimated Value'))
    appraised_value = MoneyField(label=_('Appraised Value'), required=False)
    forced_sale_value = MoneyField(label=_('Forced Sale Value'), required=False)
    
    class Meta:
        model = LoanCollateral
        fields = [
            'loan_application',
            'collateral_type',
            'description',
            'estimated_value',
            'appraised_value',
            'forced_sale_value',
            'valuation_date',
            'location',
            'owner_name',
            'ownership_document_number',
            'ownership_document',
            'photo',
            'appraisal_report',
            'is_insured',
            'insurance_policy_number',
            'insurance_expiry_date',
        ]
        widgets = {
            'loan_application': forms.Select(attrs={'class': 'form-select'}),
            'collateral_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Detailed description of the collateral')
            }),
            'valuation_date': DatePickerInput(),
            'location': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _('Physical location of the collateral')
            }),
            'owner_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Legal owner of the collateral')
            }),
            'ownership_document_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Title deed, registration number, etc.')
            }),
            'ownership_document': forms.FileInput(attrs={'class': 'form-control'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
            'appraisal_report': forms.FileInput(attrs={'class': 'form-control'}),
            'is_insured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'insurance_policy_number': forms.TextInput(attrs={'class': 'form-control'}),
            'insurance_expiry_date': DatePickerInput(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter loan applications
        self.fields['loan_application'].queryset = LoanApplication.objects.filter(
            status__in=['DRAFT', 'SUBMITTED', 'UNDER_REVIEW']
        )
        
        # Set default valuation date
        if not self.is_bound:
            self.fields['valuation_date'].initial = timezone.now().date()


class CollateralVerificationForm(BootstrapFormMixin, forms.Form):
    """Form for verifying collateral"""
    
    is_verified = forms.BooleanField(
        label=_('Collateral is verified'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    verification_notes = forms.CharField(
        label=_('Verification Notes'),
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Notes about the verification')
        })
    )


# =============================================================================
# LOAN DOCUMENT FORMS
# =============================================================================

class LoanDocumentForm(BootstrapFormMixin, forms.ModelForm):
    """Form for uploading loan documents"""
    
    class Meta:
        model = LoanDocument
        fields = [
            'loan',
            'application',
            'document_type',
            'title',
            'description',
            'document',
            'is_required',
            'expiry_date',
        ]
        widgets = {
            'loan': forms.Select(attrs={'class': 'form-select'}),
            'application': forms.Select(attrs={'class': 'form-select'}),
            'document_type': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Document title')
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _('Description (optional)')
            }),
            'document': forms.FileInput(attrs={'class': 'form-control'}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'expiry_date': DatePickerInput(),
        }
    
    def clean(self):
        """Validate document"""
        cleaned_data = super().clean()
        
        loan = cleaned_data.get('loan')
        application = cleaned_data.get('application')
        
        if not loan and not application:
            raise ValidationError(
                _('Document must be associated with either a loan or application')
            )
        
        if loan and application:
            raise ValidationError(
                _('Document cannot be associated with both loan and application')
            )
        
        return cleaned_data


class DocumentVerificationForm(BootstrapFormMixin, forms.Form):
    """Form for verifying documents"""
    
    is_verified = forms.BooleanField(
        label=_('Document is verified'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    verification_notes = forms.CharField(
        label=_('Verification Notes'),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': _('Notes about the verification (optional)')
        })
    )


# =============================================================================
# BULK OPERATION FORMS
# =============================================================================

class BulkLoanDisbursementForm(BootstrapFormMixin, forms.Form):
    """Form for bulk loan disbursement"""
    
    disbursement_date = forms.DateField(
        label=_('Disbursement Date'),
        widget=DatePickerInput()
    )
    
    loan_product = forms.ModelChoiceField(
        label=_('Loan Product (Optional)'),
        queryset=LoanProduct.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text=_('Leave blank to disburse all approved applications')
    )
    
    confirm_disbursement = forms.BooleanField(
        label=_('I confirm that I want to disburse these loans'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set default disbursement date
        if not self.is_bound:
            self.fields['disbursement_date'].initial = timezone.now().date()


# =============================================================================
# REPORTING FORMS
# =============================================================================

class LoanReportForm(BootstrapFormMixin, DateRangeFormMixin, forms.Form):
    """Form for generating loan reports"""
    
    report_type = forms.ChoiceField(
        label=_('Report Type'),
        choices=[
            ('PORTFOLIO_SUMMARY', _('Portfolio Summary')),
            ('DISBURSEMENT_REPORT', _('Disbursement Report')),
            ('REPAYMENT_REPORT', _('Repayment Report')),
            ('ARREARS_REPORT', _('Arrears Report')),
            ('PRODUCT_PERFORMANCE', _('Product Performance')),
            ('DEFAULTERS', _('Defaulters Report')),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    loan_product = forms.ModelChoiceField(
        label=_('Loan Product'),
        queryset=LoanProduct.objects.all(),
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
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Order loan products
        self.fields['loan_product'].queryset = LoanProduct.objects.all().order_by('name')