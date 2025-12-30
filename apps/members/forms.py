# members/forms.py

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django_countries import countries
from django.contrib.auth import get_user_model
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
    PhoneNumberField,
    DatePickerInput,
    MoneyInput,
    PercentageInput,
    PhoneInput,
    validate_age,
    validate_phone_number,
    validate_positive_amount,
)

from .models import (
    Member, 
    MemberPaymentMethod, 
    NextOfKin, 
    MemberAdditionalContact,
    MemberGroup,
    GroupMembership
)
import re
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


# =============================================================================
# MEMBER FILTER FORMS (NEW - FOR HTMX SEARCH)
# =============================================================================

from django.urls import reverse_lazy

class MemberFilterForm(DateRangeFilterForm, AmountRangeFilterForm):
    """Filter form for member HTMX search"""

    # Add search field
    q = forms.CharField(
        label='Search',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, number, phone, or email...',
            'autocomplete': 'off'
        })
    )
    
    status = forms.ChoiceField(
        label='Status',
        choices=[('', 'All Statuses')] + list(Member.STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    member_category = forms.ChoiceField(
        label='Category',
        choices=[('', 'All Categories')] + list(Member.MEMBER_CATEGORY_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    membership_plan = forms.ChoiceField(
        label='Plan',
        choices=[('', 'All Plans')] + list(Member.MEMBERSHIP_PLAN_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    gender = forms.ChoiceField(
        label='Gender',
        choices=[('', 'All')] + list(Member.GENDER_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    employment_status = forms.ChoiceField(
        label='Employment Status',
        choices=[('', 'All Employment')] + list(Member.EMPLOYMENT_STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    kyc_status = forms.ChoiceField(
        label='KYC Status',
        choices=[('', 'All KYC Statuses')] + list(Member.KYC_STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    risk_rating = forms.ChoiceField(
        label='Risk Rating',
        choices=[('', 'All Risk Ratings')] + list(Member.RISK_RATING_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # Override to use proper field names
    date_from = forms.DateField(
        label='Member Since (From)',
        required=False,
        widget=DatePickerInput()
    )
    
    date_to = forms.DateField(
        label='Member Since (To)',
        required=False,
        widget=DatePickerInput()
    )
    
    # Income range
    min_income = MoneyField(
        label='Minimum Income',
        required=False
    )
    
    max_income = MoneyField(
        label='Maximum Income',
        required=False
    )
    
    # Credit score range
    min_credit_score = forms.IntegerField(
        label='Minimum Credit Score',
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 1000})
    )
    
    max_credit_score = forms.IntegerField(
        label='Maximum Credit Score',
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 1000})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Get the search URL
        search_url = reverse_lazy('members:member_search')
        
        # Add HTMX attributes to search field (text input)
        self.fields['q'].widget.attrs.update({
            'hx-get': str(search_url),
            'hx-trigger': 'input changed delay:100ms',
            'hx-target': '#member-results',
            'hx-include': '#searchForm',
        })
        
        # Add HTMX attributes to all select fields
        select_fields = [
            'status', 'member_category', 'membership_plan', 'gender',
            'employment_status', 'kyc_status', 'risk_rating'
        ]
        
        for field_name in select_fields:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({
                    'hx-get': str(search_url),
                    'hx-trigger': 'change',
                    'hx-target': '#member-results',
                    'hx-include': '#searchForm',
                })

class MemberPaymentMethodFilterForm(BaseFilterForm):
    """Filter form for payment method search"""
    
    method_type = forms.ChoiceField(
        label='Method Type',
        choices=[('', 'All Types')] + list(MemberPaymentMethod.METHOD_TYPE_CHOICES),
        required=False
    )
    
    is_primary = forms.NullBooleanField(
        label='Primary',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Primary'),
            ('false', 'Not Primary')
        ])
    )
    
    is_verified = forms.NullBooleanField(
        label='Verified',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Verified'),
            ('false', 'Not Verified')
        ])
    )
    
    is_active = forms.NullBooleanField(
        label='Active',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Active'),
            ('false', 'Inactive')
        ])
    )


class NextOfKinFilterForm(BaseFilterForm):
    """Filter form for next of kin search"""
    
    relation = forms.ChoiceField(
        label='Relationship',
        choices=[('', 'All Relationships')] + list(NextOfKin.RELATION_CHOICES),
        required=False
    )
    
    is_primary = forms.NullBooleanField(
        label='Primary',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Primary'),
            ('false', 'Not Primary')
        ])
    )
    
    is_beneficiary = forms.NullBooleanField(
        label='Beneficiary',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Beneficiary'),
            ('false', 'Not Beneficiary')
        ])
    )


class MemberGroupFilterForm(BaseFilterForm):
    """Filter form for member group search"""
    
    group_type = forms.ChoiceField(
        label='Group Type',
        choices=[('', 'All Types')] + list(MemberGroup.GROUP_TYPE_CHOICES),
        required=False
    )
    
    meeting_frequency = forms.ChoiceField(
        label='Meeting Frequency',
        choices=[('', 'All')] + list(MemberGroup.MEETING_FREQUENCY_CHOICES),
        required=False
    )
    
    is_active = forms.NullBooleanField(
        label='Active',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Active'),
            ('false', 'Inactive')
        ])
    )
    
    is_full = forms.NullBooleanField(
        label='Full',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Full'),
            ('false', 'Not Full')
        ])
    )


class GroupMembershipFilterForm(BaseFilterForm):
    """Filter form for group membership search"""
    
    role = forms.ChoiceField(
        label='Role',
        choices=[('', 'All Roles')] + list(GroupMembership.ROLE_CHOICES),
        required=False
    )
    
    status = forms.ChoiceField(
        label='Status',
        choices=[('', 'All Statuses')] + list(GroupMembership.STATUS_CHOICES),
        required=False
    )
    
    is_active = forms.NullBooleanField(
        label='Active',
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            ('true', 'Active'),
            ('false', 'Inactive')
        ])
    )


# =============================================================================
# STEP 1: BASIC INFORMATION FORM (UPDATED WITH MIXINS)
# =============================================================================

class MemberBasicInfoForm(BootstrapFormMixin, RequiredFieldsMixin, forms.ModelForm):
    """Step 1: Basic member information and identification"""

    gender = forms.ChoiceField(
        label="Gender",
        choices=Member.GENDER_CHOICES,
        widget=forms.RadioSelect(),
        required=True
    )
    
    class Meta:
        model = Member
        fields = [
            'title', 'first_name', 'middle_name', 'last_name', 
            'id_type', 'id_number', 'date_of_birth', 'place_of_birth',
            'gender', 'marital_status', 'nationality', 'religious_affiliation'
        ]
        widgets = {
            'title': forms.Select(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Legal first name as per ID'
            }),
            'middle_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Middle name (optional)'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Legal last name as per ID'
            }),
            'id_type': forms.Select(attrs={'class': 'form-control'}),
            'id_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'National ID / Passport Number'
            }),
            'date_of_birth': DatePickerInput(),
            'place_of_birth': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Place of birth'
            }),
            'marital_status': forms.Select(attrs={'class': 'form-control'}),
            'nationality': forms.Select(attrs={'class': 'form-control'}),
            'religious_affiliation': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set required fields
        required_fields = ['first_name', 'last_name', 'id_number', 'date_of_birth', 'gender', 'marital_status']
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True
    
    def clean_first_name(self):
        value = self.cleaned_data.get('first_name')
        if value:
            value = ' '.join(value.strip().split()).title()
            if len(value) < 2:
                raise ValidationError("First name must be at least 2 characters long.")
        return value
    
    def clean_last_name(self):
        value = self.cleaned_data.get('last_name')
        if value:
            value = ' '.join(value.strip().split()).title()
            if len(value) < 2:
                raise ValidationError("Last name must be at least 2 characters long.")
        return value
    
    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            validate_age(dob, min_age=16, max_age=120)
        return dob
    
    def clean_id_number(self):
        value = self.cleaned_data.get('id_number')
        if value:
            value = value.strip().upper()
            # Check if ID number already exists
            if Member.objects.filter(id_number=value).exclude(pk=self.instance.pk if self.instance else None).exists():
                raise ValidationError("A member with this ID number already exists.")
        return value


# =============================================================================
# STEP 2: CONTACT INFORMATION FORM (UPDATED)
# =============================================================================

class MemberContactInfoForm(BootstrapFormMixin, RequiredFieldsMixin, forms.Form):
    """Step 2: Contact and address information"""
    
    personal_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'email@example.com'
        })
    )
    
    phone_primary = PhoneNumberField(
        label='Primary Phone',
        required=True
    )
    
    physical_address = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Current residential address'
        })
    )
    
    postal_address = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'P.O. Box (optional)'
        })
    )
    
    postal_code = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Postal code'
        })
    )
    
    city = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'City/Town'
        })
    )
    
    state_province = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'State/Province/Region'
        })
    )
    
    country = forms.ChoiceField(
        choices=[('UG', 'Uganda')] + [(code, name) for code, name in countries if code != 'UG'],
        initial='UG',
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def clean_city(self):
        value = self.cleaned_data.get('city')
        if value:
            value = ' '.join(value.strip().split()).title()
        return value


# =============================================================================
# STEP 3: EMPLOYMENT & FINANCIAL INFORMATION FORM (UPDATED)
# =============================================================================

class MemberEmploymentInfoForm(BootstrapFormMixin, MoneyFieldsMixin, forms.Form):
    """Step 3: Employment and financial information"""
    
    employment_status = forms.ChoiceField(
        choices=Member.EMPLOYMENT_STATUS_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    occupation = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Job title/occupation'
        })
    )
    
    employer = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Employer name'
        })
    )
    
    employer_address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Employer address'
        })
    )
    
    monthly_income = MoneyField(
        label='Monthly Income',
        required=False
    )
    
    income_source = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Primary source of income'
        })
    )
    
    other_income_sources = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Other income sources (if any)'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        employment_status = cleaned_data.get('employment_status')
        occupation = cleaned_data.get('occupation')
        employer = cleaned_data.get('employer')
        
        # If employed, require occupation and employer
        if employment_status == 'EMPLOYED':
            if not occupation:
                self.add_error('occupation', 'Occupation is required for employed members.')
            if not employer:
                self.add_error('employer', 'Employer is required for employed members.')
        
        return cleaned_data


# =============================================================================
# STEP 4: MEMBERSHIP INFORMATION FORM (UPDATED)
# =============================================================================

class MemberMembershipInfoForm(BootstrapFormMixin, forms.Form):
    """Step 4: Membership details and categorization"""
    
    member_category = forms.ChoiceField(
        choices=Member.MEMBER_CATEGORY_CHOICES,
        required=True,
        initial='REGULAR',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    membership_plan = forms.ChoiceField(
        choices=Member.MEMBERSHIP_PLAN_CHOICES,
        required=True,
        initial='BASIC',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    membership_date = forms.DateField(
        required=True,
        widget=DatePickerInput(),
        help_text="Date when member joined the SACCO"
    )
    
    membership_application_date = forms.DateField(
        required=False,
        widget=DatePickerInput(),
        help_text="Date when application was submitted"
    )
    
    status = forms.ChoiceField(
        choices=Member.STATUS_CHOICES,
        required=True,
        initial='PENDING_APPROVAL',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    tax_id = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tax Identification Number (TIN)'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set default membership date
        if not self.is_bound:
            self.fields['membership_date'].initial = timezone.now().date()
    
    def clean_membership_date(self):
        date = self.cleaned_data.get('membership_date')
        if date:
            today = timezone.now().date()
            if date > today:
                raise ValidationError("Membership date cannot be in the future.")
        return date


# =============================================================================
# STEP 5: NEXT OF KIN FORM (UPDATED)
# =============================================================================

class MemberNextOfKinForm(BootstrapFormMixin, forms.Form):
    """Step 5: Next of kin information"""
    
    nok_option = forms.ChoiceField(
        choices=[
            ('skip', 'Skip for now (add next of kin later)'),
            ('new', 'Add Primary Next of Kin')
        ],
        required=True,
        widget=forms.RadioSelect(),
        initial='new',
        label="Next of Kin Option"
    )
    
    nok_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Full name of next of kin'
        }),
        label="Name"
    )
    
    nok_relation = forms.ChoiceField(
        choices=[('', 'Select Relationship')] + list(NextOfKin.RELATION_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Relationship"
    )
    
    nok_contact = PhoneNumberField(
        label="Phone Number",
        required=False
    )
    
    nok_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'email@example.com'
        }),
        label="Email Address"
    )
    
    nok_address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Residential address'
        }),
        label="Address"
    )
    
    nok_id_number = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ID number'
        }),
        label="ID Number"
    )
    
    nok_is_emergency_contact = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Use as emergency contact",
        initial=True
    )
    
    def clean(self):
        cleaned_data = super().clean()
        nok_option = cleaned_data.get('nok_option')
        
        if nok_option == 'new':
            # Validate required fields for new next of kin
            required_fields = ['nok_name', 'nok_relation', 'nok_contact']
            errors = {}
            
            for field in required_fields:
                if not cleaned_data.get(field):
                    field_display = field.replace('nok_', '').replace('_', ' ').title()
                    errors[field] = f'{field_display} is required when adding next of kin.'
            
            if errors:
                raise ValidationError(errors)
        
        return cleaned_data


# =============================================================================
# STEP 6: CONFIRMATION FORM
# =============================================================================

class MemberConfirmationForm(BootstrapFormMixin, forms.Form):
    """
    Step 6: Final confirmation
    
    Note: Member number fields removed since member numbers are automatically
    generated by the pre_save signal in signals.py
    """
    
    confirm_creation = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="I confirm that all the information provided is correct"
    )
    
    additional_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Any additional notes or comments (optional)'
        }),
        help_text="Optional notes for internal record keeping"
    )

# =============================================================================
# WIZARD CONFIGURATION
# =============================================================================

MEMBER_WIZARD_FORMS = [
    ("basic_info", MemberBasicInfoForm),
    ("contact_info", MemberContactInfoForm),
    ("employment_info", MemberEmploymentInfoForm),
    ("membership_info", MemberMembershipInfoForm),
    ("next_of_kin", MemberNextOfKinForm),
    ("confirmation", MemberConfirmationForm),
]

MEMBER_WIZARD_STEP_NAMES = {
    'basic_info': 'Personal Information',
    'contact_info': 'Contact & Address',
    'employment_info': 'Employment & Income',
    'membership_info': 'Membership Details',
    'next_of_kin': 'Next of Kin',
    'confirmation': 'Review & Confirmation'
}


# =============================================================================
# GENERAL MEMBER FORM (UPDATED WITH MIXINS)
# =============================================================================

class MemberForm(BootstrapFormMixin, MoneyFieldsMixin, forms.ModelForm):
    """Complete member form for editing existing members"""

    country = forms.ChoiceField(
        choices=[('UG', 'Uganda')] + [(code, name) for code, name in countries if code != 'UG'],
        initial='UG',
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Use custom fields
    phone_primary = PhoneNumberField(label='Primary Phone')
    monthly_income = MoneyField(label='Monthly Income', required=False)
    maximum_loan_multiplier = PercentageField(label='Loan Multiplier', required=False)
    loan_interest_discount = PercentageField(label='Interest Discount', required=False)
    
    class Meta:
        model = Member
        fields = [
            # Basic Information
            'member_number',
            'id_number',
            'id_type',
            'title',
            'first_name',
            'middle_name',
            'last_name',
            'date_of_birth',
            'place_of_birth',
            'gender',
            'marital_status',
            'nationality',
            'religious_affiliation',
            
            # Membership Information
            'member_category',
            'membership_plan',
            'membership_date',
            'membership_application_date',
            'membership_approved_date',
            'status',
            'status_changed_reason',
            'maximum_loan_multiplier',
            'loan_interest_discount',
            
            # Employment & Financial
            'employment_status',
            'occupation',
            'employer',
            'employer_address',
            'monthly_income',
            'income_source',
            'other_income_sources',
            
            # Contact Information
            'personal_email',
            'phone_primary',
            'physical_address',
            'postal_address',
            'postal_code',
            'city',
            'state_province',
            'country',
            
            # Tax & Compliance
            'tax_id',
            'tax_exemption_status',
            'tax_exemption_reason',
            'kyc_status',
            'kyc_notes',
            
            # Risk & Credit
            'credit_score',
            'risk_rating',
            'risk_assessment_notes',
            
            # Documents
            'member_photo',
        ]
        
        widgets = {
            'member_number': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'id_number': forms.TextInput(attrs={'class': 'form-control'}),
            'id_type': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.Select(attrs={'class': 'form-select'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth': DatePickerInput(),
            'place_of_birth': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'marital_status': forms.Select(attrs={'class': 'form-select'}),
            'nationality': forms.Select(attrs={'class': 'form-select'}),
            'religious_affiliation': forms.Select(attrs={'class': 'form-select'}),
            'member_category': forms.Select(attrs={'class': 'form-select'}),
            'membership_plan': forms.Select(attrs={'class': 'form-select'}),
            'membership_date': DatePickerInput(),
            'membership_application_date': DatePickerInput(),
            'membership_approved_date': DatePickerInput(),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'status_changed_reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'employment_status': forms.Select(attrs={'class': 'form-select'}),
            'occupation': forms.TextInput(attrs={'class': 'form-control'}),
            'employer': forms.TextInput(attrs={'class': 'form-control'}),
            'employer_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'income_source': forms.TextInput(attrs={'class': 'form-control'}),
            'other_income_sources': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'personal_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'physical_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'postal_address': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state_province': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.Select(attrs={'class': 'form-select'}),
            'tax_id': forms.TextInput(attrs={'class': 'form-control'}),
            'tax_exemption_status': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tax_exemption_reason': forms.TextInput(attrs={'class': 'form-control'}),
            'kyc_status': forms.Select(attrs={'class': 'form-select'}),
            'kyc_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'credit_score': forms.NumberInput(attrs={'class': 'form-control'}),
            'risk_rating': forms.Select(attrs={'class': 'form-select'}),
            'risk_assessment_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'member_photo': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set required fields
        required_fields = [
            'member_number', 'id_number', 'first_name', 'last_name',
            'date_of_birth', 'gender', 'marital_status', 'membership_date',
            'phone_primary', 'physical_address', 'employment_status', 'status'
        ]
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True
        
        # Make member_number readonly for existing members
        if self.instance.pk:
            self.fields['member_number'].widget.attrs['readonly'] = True


# =============================================================================
# MEMBER PAYMENT METHOD FORM (UPDATED)
# =============================================================================

class MemberPaymentMethodForm(BootstrapFormMixin, forms.ModelForm):
    """Form for adding/editing payment methods"""
    
    class Meta:
        model = MemberPaymentMethod
        fields = [
            'method_type',
            'provider',
            'account_number',
            'account_name',
            'account_type',
            'branch',
            'is_primary',
            'is_verified',
            'notes',
        ]
        widgets = {
            'method_type': forms.Select(attrs={'class': 'form-select'}),
            'provider': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Bank name or mobile money provider'
            }),
            'account_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Account or phone number'
            }),
            'account_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Name as registered on account'
            }),
            'account_type': forms.Select(attrs={'class': 'form-select'}),
            'branch': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Branch or location'
            }),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_verified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Additional notes'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.member = kwargs.pop('member', None)
        super().__init__(*args, **kwargs)
        
        # Make required fields
        self.fields['method_type'].required = True
        self.fields['provider'].required = True
        self.fields['account_number'].required = True
        self.fields['account_name'].required = True


# =============================================================================
# NEXT OF KIN FORM (UPDATED)
# =============================================================================

class NextOfKinForm(BootstrapFormMixin, forms.ModelForm):
    """Form for adding/editing next of kin"""
    
    contact = PhoneNumberField(label='Phone Number')
    beneficiary_percentage = PercentageField(label='Beneficiary Percentage', required=False)
    
    class Meta:
        model = NextOfKin
        fields = [
            'name',
            'relation',
            'contact',
            'email',
            'address',
            'id_number',
            'date_of_birth',
            'is_primary',
            'is_emergency_contact',
            'is_beneficiary',
            'beneficiary_percentage',
            'notes',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full name'
            }),
            'relation': forms.Select(attrs={'class': 'form-select'}),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@example.com'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Residential address'
            }),
            'id_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ID number'
            }),
            'date_of_birth': DatePickerInput(),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_emergency_contact': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_beneficiary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Additional notes'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.member = kwargs.pop('member', None)
        super().__init__(*args, **kwargs)
        
        # Make required fields
        self.fields['name'].required = True
        self.fields['relation'].required = True
        self.fields['contact'].required = True


# =============================================================================
# MEMBER ADDITIONAL CONTACT FORM (UPDATED)
# =============================================================================

class MemberAdditionalContactForm(BootstrapFormMixin, forms.ModelForm):
    """Form for adding additional contact methods"""
    
    class Meta:
        model = MemberAdditionalContact
        fields = [
            'contact_type',
            'contact_value',
            'is_verified',
            'notes',
        ]
        widgets = {
            'contact_type': forms.Select(attrs={'class': 'form-select'}),
            'contact_value': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email or phone number'
            }),
            'is_verified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Additional notes'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.member = kwargs.pop('member', None)
        super().__init__(*args, **kwargs)
        
        # Make required fields
        self.fields['contact_type'].required = True
        self.fields['contact_value'].required = True


# =============================================================================
# MEMBER GROUP FORM (UPDATED)
# =============================================================================

class MemberGroupForm(BootstrapFormMixin, MoneyFieldsMixin, forms.ModelForm):
    """Form for creating/editing member groups"""
    
    minimum_contribution = MoneyField(label='Minimum Contribution', required=False)
    maximum_loan_amount = MoneyField(label='Maximum Loan Amount', required=False)
    interest_rate = PercentageField(label='Interest Rate', required=False)
    
    class Meta:
        model = MemberGroup
        fields = [
            'name',
            'description',
            'group_type',
            'group_leader',
            'group_secretary',
            'group_treasurer',
            'formation_date',
            'meeting_frequency',
            'meeting_day',
            'meeting_time',
            'meeting_location',
            'minimum_contribution',
            'maximum_loan_amount',
            'interest_rate',
            'maximum_members',
            'minimum_members',
            'is_active',
            'terms_and_conditions',
            'group_rules',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'group_type': forms.Select(attrs={'class': 'form-select'}),
            'group_leader': forms.Select(attrs={'class': 'form-select'}),
            'group_secretary': forms.Select(attrs={'class': 'form-select'}),
            'group_treasurer': forms.Select(attrs={'class': 'form-select'}),
            'formation_date': DatePickerInput(),
            'meeting_frequency': forms.Select(attrs={'class': 'form-select'}),
            'meeting_day': forms.Select(attrs={'class': 'form-select'}),
            'meeting_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'meeting_location': forms.TextInput(attrs={'class': 'form-control'}),
            'maximum_members': forms.NumberInput(attrs={'class': 'form-control'}),
            'minimum_members': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'terms_and_conditions': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'group_rules': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter leadership choices to active members only
        self.fields['group_leader'].queryset = Member.objects.filter(status='ACTIVE')
        self.fields['group_secretary'].queryset = Member.objects.filter(status='ACTIVE')
        self.fields['group_treasurer'].queryset = Member.objects.filter(status='ACTIVE')
        
        # Set required fields
        required_fields = ['name', 'description', 'group_type', 'formation_date']
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True


# =============================================================================
# GROUP MEMBERSHIP FORM (UPDATED)
# =============================================================================

class GroupMembershipForm(BootstrapFormMixin, MoneyFieldsMixin, forms.ModelForm):
    """Form for adding members to groups"""
    
    monthly_contribution = MoneyField(label='Monthly Contribution', required=False)
    
    class Meta:
        model = GroupMembership
        fields = [
            'member',
            'group',
            'role',
            'join_date',
            'status',
            'monthly_contribution',
            'notes',
        ]
        widgets = {
            'member': forms.Select(attrs={'class': 'form-select'}),
            'group': forms.Select(attrs={'class': 'form-select'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'join_date': DatePickerInput(),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter to active members and groups
        self.fields['member'].queryset = Member.objects.filter(status='ACTIVE')
        self.fields['group'].queryset = MemberGroup.objects.filter(is_active=True)
        
        # Set default join date
        if not self.is_bound:
            self.fields['join_date'].initial = timezone.now().date()
        
        # Make required fields
        required_fields = ['member', 'group', 'join_date']
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True 
    
    def clean(self):
        """Validate group membership"""
        cleaned_data = super().clean()
        member = cleaned_data.get('member')
        group = cleaned_data.get('group')
        
        # Check if group can accept new members
        if group and not group.can_add_member():
            raise ValidationError({
                'group': f"Group '{group.name}' is full and cannot accept new members."
            })
        
        # Check if member is already in this group
        if member and group:
            existing = GroupMembership.objects.filter(
                member=member,
                group=group,
                is_active=True
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                raise ValidationError({
                    'member': f"{member.get_full_name()} is already an active member of {group.name}."
                })
        
        return cleaned_data