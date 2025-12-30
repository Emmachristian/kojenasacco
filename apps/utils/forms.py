# utils/forms.py

"""
Base form utilities and mixins for consistent form handling across the application.
Provides reusable form components, widgets, and validation helpers.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from datetime import date, datetime
import re
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# CUSTOM WIDGETS
# =============================================================================

class DatePickerInput(forms.DateInput):
    """Date picker widget with HTML5 date input"""
    input_type = 'date'
    
    def __init__(self, attrs=None, format=None):
        default_attrs = {'class': 'form-control'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs, format=format or '%Y-%m-%d')


class DateTimePickerInput(forms.DateTimeInput):
    """DateTime picker widget with HTML5 datetime-local input"""
    input_type = 'datetime-local'
    
    def __init__(self, attrs=None, format=None):
        default_attrs = {'class': 'form-control'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs, format=format or '%Y-%m-%dT%H:%M')


class MoneyInput(forms.NumberInput):
    """Money input widget with proper formatting"""
    
    def __init__(self, attrs=None):
        default_attrs = {
            'class': 'form-control money-input',
            'step': '0.01',
            'min': '0',
            'placeholder': '0.00'
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


class PercentageInput(forms.NumberInput):
    """Percentage input widget"""
    
    def __init__(self, attrs=None):
        default_attrs = {
            'class': 'form-control percentage-input',
            'step': '0.01',
            'min': '0',
            'max': '100',
            'placeholder': '0.00'
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


class PhoneInput(forms.TextInput):
    """Phone number input widget"""
    
    def __init__(self, attrs=None):
        default_attrs = {
            'class': 'form-control phone-input',
            'placeholder': '+256700000000',
            'pattern': r'^\+?1?\d{9,15}$'
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


class SearchInput(forms.TextInput):
    """Search input widget"""
    
    def __init__(self, attrs=None):
        default_attrs = {
            'class': 'form-control search-input',
            'placeholder': 'Search...',
            'type': 'search'
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


# =============================================================================
# CUSTOM FORM FIELDS
# =============================================================================

class MoneyField(forms.DecimalField):
    """Custom field for money amounts with proper validation"""
    
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_digits', 15)
        kwargs.setdefault('decimal_places', 2)
        kwargs.setdefault('min_value', Decimal('0.00'))
        kwargs.setdefault('widget', MoneyInput())
        super().__init__(*args, **kwargs)
    
    def clean(self, value):
        """Clean and validate money value"""
        if value in self.empty_values:
            return super().clean(value)
        
        # Remove currency symbols and commas
        if isinstance(value, str):
            value = re.sub(r'[^\d.-]', '', value)
        
        try:
            value = Decimal(value)
        except (ValueError, InvalidOperation):
            raise ValidationError('Enter a valid amount.')
        
        return super().clean(value)


class PercentageField(forms.DecimalField):
    """Custom field for percentage values"""
    
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_digits', 5)
        kwargs.setdefault('decimal_places', 2)
        kwargs.setdefault('min_value', Decimal('0.00'))
        kwargs.setdefault('max_value', Decimal('100.00'))
        kwargs.setdefault('widget', PercentageInput())
        super().__init__(*args, **kwargs)


class PhoneNumberField(forms.CharField):
    """Custom field for phone numbers with validation"""
    
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 20)
        kwargs.setdefault('widget', PhoneInput())
        super().__init__(*args, **kwargs)
    
    def clean(self, value):
        """Clean and validate phone number"""
        value = super().clean(value)
        
        if value in self.empty_values:
            return value
        
        # Remove spaces and special characters except +
        cleaned = re.sub(r'[^\d+]', '', value)
        
        # Validate format
        if not re.match(r'^\+?1?\d{9,15}$', cleaned):
            raise ValidationError('Enter a valid phone number.')
        
        return cleaned


# =============================================================================
# FORM MIXINS
# =============================================================================

class BootstrapFormMixin:
    """Mixin to add Bootstrap classes to form fields"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap_classes()
    
    def apply_bootstrap_classes(self):
        """Apply Bootstrap classes to all form fields"""
        for field_name, field in self.fields.items():
            # Add form-control class to input fields
            if isinstance(field.widget, (
                forms.TextInput,
                forms.NumberInput,
                forms.EmailInput,
                forms.PasswordInput,
                forms.Textarea,
                forms.Select,
                forms.DateInput,
                forms.DateTimeInput,
                forms.TimeInput,
                forms.URLInput,
            )):
                existing_classes = field.widget.attrs.get('class', '')
                if 'form-control' not in existing_classes:
                    field.widget.attrs['class'] = f"{existing_classes} form-control".strip()
            
            # Add form-check-input class to checkboxes and radios
            elif isinstance(field.widget, (forms.CheckboxInput, forms.RadioSelect)):
                existing_classes = field.widget.attrs.get('class', '')
                if 'form-check-input' not in existing_classes:
                    field.widget.attrs['class'] = f"{existing_classes} form-check-input".strip()
            
            # Add form-select class to select fields
            elif isinstance(field.widget, forms.Select):
                existing_classes = field.widget.attrs.get('class', '')
                if 'form-select' not in existing_classes:
                    field.widget.attrs['class'] = f"{existing_classes} form-select".strip()
            
            # Add placeholder if field has help_text
            if field.help_text and not field.widget.attrs.get('placeholder'):
                if isinstance(field.widget, (forms.TextInput, forms.EmailInput, forms.NumberInput)):
                    field.widget.attrs['placeholder'] = field.help_text


class HTMXFormMixin:
    """Mixin to add HTMX attributes to forms"""
    
    htmx_post = None  # URL to post to
    htmx_target = None  # Target element ID
    htmx_swap = 'innerHTML'  # Swap method
    htmx_trigger = 'submit'  # Trigger event
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_htmx_attributes()
    
    def apply_htmx_attributes(self):
        """Apply HTMX attributes to form"""
        if self.htmx_post:
            self.attrs = getattr(self, 'attrs', {})
            self.attrs['hx-post'] = self.htmx_post
            
            if self.htmx_target:
                self.attrs['hx-target'] = f"#{self.htmx_target}"
            
            if self.htmx_swap:
                self.attrs['hx-swap'] = self.htmx_swap
            
            if self.htmx_trigger != 'submit':
                self.attrs['hx-trigger'] = self.htmx_trigger


class DateRangeFormMixin:
    """Mixin for forms with date range fields"""
    
    def clean(self):
        """Validate date range"""
        cleaned_data = super().clean()
        
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError({
                    'end_date': 'End date must be after start date.'
                })
        
        return cleaned_data


class MoneyFieldsMixin:
    """Mixin for forms with money fields to ensure proper formatting"""
    
    def clean(self):
        """Clean money fields"""
        cleaned_data = super().clean()
        
        # Find all money fields
        for field_name, field in self.fields.items():
            if isinstance(field, (forms.DecimalField, MoneyField)):
                value = cleaned_data.get(field_name)
                if value is not None:
                    # Ensure it's a Decimal
                    if not isinstance(value, Decimal):
                        try:
                            cleaned_data[field_name] = Decimal(str(value))
                        except (ValueError, InvalidOperation):
                            self.add_error(field_name, 'Invalid amount.')
        
        return cleaned_data


class RequiredFieldsMixin:
    """Mixin to mark required fields with asterisk in label"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mark_required_fields()
    
    def mark_required_fields(self):
        """Add asterisk to required field labels"""
        for field_name, field in self.fields.items():
            if field.required and field.label:
                field.label = f"{field.label} *"


# =============================================================================
# BASE FILTER FORM
# =============================================================================

class BaseFilterForm(BootstrapFormMixin, forms.Form):
    """Base form for HTMX search/filter forms"""
    
    q = forms.CharField(
        label='Search',
        required=False,
        widget=SearchInput(attrs={
            'hx-get': '',  # Set by view
            'hx-trigger': 'keyup changed delay:500ms',
            'hx-target': '#results',
            'hx-include': '[name]',
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Apply HTMX attributes to all fields
        for field_name, field in self.fields.items():
            if field_name != 'q':
                field.widget.attrs.update({
                    'hx-get': '',  # Set by view
                    'hx-trigger': 'change',
                    'hx-target': '#results',
                    'hx-include': '[name]',
                })


# =============================================================================
# DATE RANGE FILTER FORM
# =============================================================================

class DateRangeFilterForm(BaseFilterForm, DateRangeFormMixin):
    """Filter form with date range"""
    
    date_from = forms.DateField(
        label='From Date',
        required=False,
        widget=DatePickerInput()
    )
    
    date_to = forms.DateField(
        label='To Date',
        required=False,
        widget=DatePickerInput()
    )


# =============================================================================
# AMOUNT RANGE FILTER FORM
# =============================================================================

class AmountRangeFilterForm(BaseFilterForm):
    """Filter form with amount range"""
    
    min_amount = MoneyField(
        label='Minimum Amount',
        required=False
    )
    
    max_amount = MoneyField(
        label='Maximum Amount',
        required=False
    )
    
    def clean(self):
        """Validate amount range"""
        cleaned_data = super().clean()
        
        min_amount = cleaned_data.get('min_amount')
        max_amount = cleaned_data.get('max_amount')
        
        if min_amount and max_amount:
            if min_amount > max_amount:
                raise ValidationError({
                    'max_amount': 'Maximum amount must be greater than minimum amount.'
                })
        
        return cleaned_data


# =============================================================================
# VALIDATION HELPERS
# =============================================================================

def validate_future_date(value):
    """Validate that date is not in the future"""
    if value > date.today():
        raise ValidationError('Date cannot be in the future.')


def validate_past_date(value):
    """Validate that date is not in the past"""
    if value < date.today():
        raise ValidationError('Date cannot be in the past.')


def validate_age(date_of_birth, min_age=18, max_age=120):
    """Validate age based on date of birth"""
    if not date_of_birth:
        return
    
    today = date.today()
    age = today.year - date_of_birth.year - (
        (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    )
    
    if age < min_age:
        raise ValidationError(f'Must be at least {min_age} years old.')
    
    if age > max_age:
        raise ValidationError(f'Age cannot exceed {max_age} years.')


def validate_phone_number(value):
    """Validate phone number format"""
    if not value:
        return
    
    cleaned = re.sub(r'[^\d+]', '', value)
    
    if not re.match(r'^\+?1?\d{9,15}$', cleaned):
        raise ValidationError('Enter a valid phone number.')


def validate_positive_amount(value):
    """Validate that amount is positive"""
    if value is not None and value <= 0:
        raise ValidationError('Amount must be greater than zero.')


def validate_percentage(value):
    """Validate percentage value"""
    if value is not None:
        if value < 0 or value > 100:
            raise ValidationError('Percentage must be between 0 and 100.')


def validate_id_number(value):
    """Validate ID number format (customize based on your country)"""
    if not value:
        return
    
    # Example validation for Uganda National ID (NIN)
    # Format: CMXXXXXXXXXX (CM followed by 12 digits)
    if not re.match(r'^[A-Z]{2}\d{12}$', value.upper()):
        raise ValidationError('Enter a valid ID number.')


# =============================================================================
# FORM HELPERS
# =============================================================================

def get_form_errors_as_dict(form):
    """Convert form errors to a dictionary for JSON responses"""
    errors = {}
    
    for field, error_list in form.errors.items():
        errors[field] = [str(error) for error in error_list]
    
    return errors


def get_form_errors_as_string(form):
    """Convert form errors to a formatted string"""
    error_messages = []
    
    for field, error_list in form.errors.items():
        field_label = form.fields[field].label if field in form.fields else field
        for error in error_list:
            error_messages.append(f"{field_label}: {error}")
    
    return '\n'.join(error_messages)


def set_form_field_order(form, field_order):
    """Reorder form fields"""
    if not field_order:
        return form
    
    fields = form.fields
    ordered_fields = {}
    
    for field_name in field_order:
        if field_name in fields:
            ordered_fields[field_name] = fields[field_name]
    
    # Add remaining fields
    for field_name, field in fields.items():
        if field_name not in ordered_fields:
            ordered_fields[field_name] = field
    
    form.fields = ordered_fields
    return form


def disable_form_fields(form, field_names):
    """Disable specific form fields"""
    for field_name in field_names:
        if field_name in form.fields:
            form.fields[field_name].widget.attrs['disabled'] = 'disabled'
            form.fields[field_name].required = False


def make_fields_readonly(form, field_names):
    """Make specific form fields readonly"""
    for field_name in field_names:
        if field_name in form.fields:
            form.fields[field_name].widget.attrs['readonly'] = 'readonly'


# =============================================================================
# FORMSET HELPERS
# =============================================================================

def create_formset_with_initial(formset_class, queryset=None, initial_data=None, extra=1):
    """Create a formset with initial data"""
    if queryset is not None:
        formset = formset_class(queryset=queryset)
    elif initial_data is not None:
        formset = formset_class(initial=initial_data)
    else:
        formset = formset_class()
    
    formset.extra = extra
    return formset


def get_formset_errors(formset):
    """Get all errors from a formset"""
    errors = []
    
    # Non-form errors
    if formset.non_form_errors():
        errors.extend(formset.non_form_errors())
    
    # Form errors
    for i, form in enumerate(formset):
        if form.errors:
            for field, error_list in form.errors.items():
                for error in error_list:
                    errors.append(f"Form {i+1} - {field}: {error}")
    
    return errors


# =============================================================================
# COMMON FORM PATTERNS
# =============================================================================

class ConfirmationForm(BootstrapFormMixin, forms.Form):
    """Simple confirmation form"""
    
    confirm = forms.BooleanField(
        label='I confirm this action',
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    reason = forms.CharField(
        label='Reason (optional)',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3})
    )


class CommentForm(BootstrapFormMixin, forms.Form):
    """Simple comment/notes form"""
    
    comment = forms.CharField(
        label='Comment',
        required=True,
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Enter your comment...'})
    )


class ApprovalForm(BootstrapFormMixin, forms.Form):
    """Approval form with approve/reject options"""
    
    DECISION_CHOICES = [
        ('', '-- Select Decision --'),
        ('APPROVE', 'Approve'),
        ('REJECT', 'Reject'),
    ]
    
    decision = forms.ChoiceField(
        label='Decision',
        choices=DECISION_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    notes = forms.CharField(
        label='Notes',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3})
    )
    
    def clean_decision(self):
        """Ensure a decision is selected"""
        decision = self.cleaned_data.get('decision')
        if not decision:
            raise ValidationError('Please select a decision.')
        return decision