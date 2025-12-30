# accounts/forms.py

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django_countries.widgets import CountrySelectWidget
from django_countries import countries
from zoneinfo import available_timezones
from .models import UserProfile, Sacco, MemberAccount
import re


# =============================================================================
# LOGIN FORM
# =============================================================================

class LoginForm(AuthenticationForm):
    """Custom login form using email instead of username"""
    
    username = forms.EmailField(
        label=_('Email'),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'id': 'userEmail',
            'placeholder': 'Enter your email address',
            'autofocus': True
        })
    )
    password = forms.CharField(
        label=_('Password'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'userPassword',
            'placeholder': 'Enter your password'
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        label=_('Remember me'),
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'rememberMe'
        })
    )
    
    error_messages = {
        'invalid_login': _(
            "Please enter a correct email and password. Note that both "
            "fields may be case-sensitive."
        ),
        'inactive': _("This account is inactive."),
    }


# =============================================================================
# USER REGISTRATION FORM
# =============================================================================

class UserRegistrationForm(UserCreationForm):
    """Form for registering new users"""
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'email@example.com'
        })
    )
    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First Name'
        })
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last Name'
        })
    )
    
    # Profile fields
    role = forms.ChoiceField(
        choices=UserProfile.USER_ROLES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    sacco = forms.ModelChoiceField(
        queryset=Sacco.objects.filter(is_active_subscription=True),
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    mobile = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+256700000000'
        })
    )
    date_of_birth = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    gender = forms.ChoiceField(
        choices=[('', '--- Select ---')] + list(UserProfile.GENDER_CHOICES),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Username'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Customize password fields
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Create a strong password',
            'autocomplete': 'new-password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm your password',
            'autocomplete': 'new-password'
        })
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError(_('A user with this email already exists.'))
        return email.lower()
    
    def clean_mobile(self):
        mobile = self.cleaned_data.get('mobile')
        if mobile:
            # Remove spaces and dashes
            mobile = re.sub(r'[\s-]', '', mobile)
            # Basic validation for phone format
            if not re.match(r'^\+?1?\d{9,15}$', mobile):
                raise ValidationError(_('Enter a valid phone number.'))
        return mobile
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        
        if commit:
            user.save()
            
            # Create UserProfile
            UserProfile.objects.create(
                user=user,
                sacco=self.cleaned_data['sacco'],
                role=self.cleaned_data['role'],
                mobile=self.cleaned_data.get('mobile', ''),
                date_of_birth=self.cleaned_data.get('date_of_birth'),
                gender=self.cleaned_data.get('gender', ''),
            )
        
        return user


# =============================================================================
# USER PROFILE FORM
# =============================================================================

class UserProfileForm(forms.ModelForm):
    """Form for editing user profile"""
    
    # User fields - read-only
    email = forms.EmailField(
        required=False,
        disabled=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'readonly': 'readonly'
        })
    )
    username = forms.CharField(
        required=False,
        disabled=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': 'readonly'
        })
    )
    
    # User fields - editable
    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First Name'
        })
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last Name'
        })
    )
    
    class Meta:
        model = UserProfile
        fields = [
            'photo',
            'mobile',
            'date_of_birth',
            'gender',
            'address',
            'city',
            'country',
            'language',
            'timezone',
            'employee_id',
            'department',
            'position',
        ]
        widgets = {
            'photo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'mobile': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+256700000000'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'gender': forms.Select(attrs={
                'class': 'form-control'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Full address'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City'
            }),
            'country': CountrySelectWidget(attrs={
                'class': 'form-control'
            }),
            'language': forms.Select(attrs={
                'class': 'form-control'
            }),
            'timezone': forms.Select(attrs={
                'class': 'form-control'
            }),

        }
    
    def __init__(self, *args, **kwargs):
        # Extract custom parameters before calling super()
        self.user = kwargs.pop('user', None)  # NEW LINE - Extract user parameter
        
        super().__init__(*args, **kwargs)
        
        # Make employee_id read-only
        self.fields['employee_id'].disabled = True
        
        # Populate timezone choices
        self.fields['timezone'].choices = [(tz, tz) for tz in sorted(available_timezones())]
        
        # Populate user fields if editing existing profile
        if self.instance and self.instance.pk:
            # Use self.user if provided, otherwise use instance.user
            user = self.user or self.instance.user
            if user:
                self.fields['email'].initial = user.email
                self.fields['username'].initial = user.username
                self.fields['first_name'].initial = user.first_name
                self.fields['last_name'].initial = user.last_name
    
    def clean_mobile(self):
        mobile = self.cleaned_data.get('mobile')
        if mobile:
            mobile = re.sub(r'[\s-]', '', mobile)
            if not re.match(r'^\+?1?\d{9,15}$', mobile):
                raise ValidationError(_('Enter a valid phone number.'))
        return mobile
    
    def clean_emergency_contact_phone(self):
        phone = self.cleaned_data.get('emergency_contact_phone')
        if phone:
            phone = re.sub(r'[\s-]', '', phone)
            if not re.match(r'^\+?1?\d{9,15}$', phone):
                raise ValidationError(_('Enter a valid phone number.'))
        return phone
    
    def save(self, commit=True):
        profile = super().save(commit=False)
        
        # Update the associated user
        if profile.user:
            user = profile.user
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            
            if commit:
                user.save()
        
        if commit:
            profile.save()
        
        return profile


# =============================================================================
# PASSWORD CHANGE FORM
# =============================================================================

class CustomPasswordChangeForm(PasswordChangeForm):
    """Custom password change form with styling"""
    
    old_password = forms.CharField(
        label=_('Current Password'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter current password',
            'autocomplete': 'current-password'
        })
    )
    new_password1 = forms.CharField(
        label=_('New Password'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new password',
            'autocomplete': 'new-password'
        }),
        help_text=_('Password must be at least 8 characters long.')
    )
    new_password2 = forms.CharField(
        label=_('Confirm New Password'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password',
            'autocomplete': 'new-password'
        })
    )


# =============================================================================
# SACCO FORM
# =============================================================================

class SaccoForm(forms.ModelForm):
    """Form for creating/editing SACCO"""
    
    class Meta:
        model = Sacco
        fields = [
            'full_name', 'short_name', 'abbreviation', 'description',
            'domain', 'database_alias',
            'sacco_type', 'membership_type', 'common_bond',
            'address', 'city', 'state_province', 'postal_code', 'country',
            'contact_phone', 'alternative_contact',
            'website', 'facebook_page', 'twitter_handle', 'instagram_handle',
            'sacco_logo', 'favicon', 'brand_colors',
            'established_date', 'registration_number', 'license_number',
            'operating_hours', 'timezone',
            'subscription_plan', 'subscription_start', 'subscription_end',
            'is_active_subscription'
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full SACCO Name'
            }),
            'short_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Short Name'
            }),
            'abbreviation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Abbreviation'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Brief description of the SACCO'
            }),
            'domain': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'mysacco.org'
            }),
            'database_alias': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'mysacco_db'
            }),
            'sacco_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'membership_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'common_bond': forms.Select(attrs={
                'class': 'form-control'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Full address'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City'
            }),
            'state_province': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'State/Province'
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Postal Code'
            }),
            'country': CountrySelectWidget(attrs={
                'class': 'form-control'
            }),
            'contact_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+256700000000'
            }),
            'alternative_contact': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+256700000000'
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://www.mysacco.org'
            }),
            'facebook_page': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://facebook.com/mysacco'
            }),
            'twitter_handle': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '@mysacco'
            }),
            'instagram_handle': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '@mysacco'
            }),
            'sacco_logo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'favicon': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/x-icon,image/png'
            }),
            'brand_colors': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '{"primary": "#007bff", "secondary": "#6c757d", "accent": "#28a745"}'
            }),
            'established_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'registration_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Registration Number'
            }),
            'license_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'License Number'
            }),
            'operating_hours': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Mon-Fri 8:00-17:00'
            }),
            'timezone': forms.Select(attrs={
                'class': 'form-control'
            }),
            'subscription_plan': forms.Select(attrs={
                'class': 'form-control'
            }),
            'subscription_start': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'subscription_end': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'is_active_subscription': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate timezone choices
        self.fields['timezone'].choices = [(tz, tz) for tz in sorted(available_timezones())]
    
    def clean_domain(self):
        domain = self.cleaned_data.get('domain')
        if domain:
            # Remove http://, https://, and www.
            domain = re.sub(r'^(https?://)?(www\.)?', '', domain)
            # Remove trailing slash
            domain = domain.rstrip('/')
        return domain
    
    def clean_contact_phone(self):
        phone = self.cleaned_data.get('contact_phone')
        if phone:
            phone = re.sub(r'[\s-]', '', phone)
            if not re.match(r'^\+?1?\d{9,15}$', phone):
                raise ValidationError(_('Enter a valid phone number.'))
        return phone
    
    def clean_alternative_contact(self):
        phone = self.cleaned_data.get('alternative_contact')
        if phone:
            phone = re.sub(r'[\s-]', '', phone)
            if not re.match(r'^\+?1?\d{9,15}$', phone):
                raise ValidationError(_('Enter a valid phone number.'))
        return phone


# =============================================================================
# MEMBER ACCOUNT FORM
# =============================================================================

class MemberAccountForm(forms.ModelForm):
    """Form for linking users to member accounts"""
    
    class Meta:
        model = MemberAccount
        fields = ['user', 'sacco', 'member_number', 'status', 'membership_date', 'is_active']
        widgets = {
            'user': forms.Select(attrs={
                'class': 'form-control'
            }),
            'sacco': forms.Select(attrs={
                'class': 'form-control'
            }),
            'member_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Member Number'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
            'membership_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter only active users and SACCOs
        self.fields['user'].queryset = User.objects.filter(is_active=True)
        self.fields['sacco'].queryset = Sacco.objects.filter(is_active_subscription=True)


# =============================================================================
# USER SEARCH/FILTER FORM
# =============================================================================

class UserSearchForm(forms.Form):
    """Form for searching and filtering users"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, email, or username...'
        })
    )
    role = forms.ChoiceField(
        choices=[('', 'All Roles')] + list(UserProfile.USER_ROLES),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    sacco = forms.ModelChoiceField(
        queryset=Sacco.objects.filter(is_active_subscription=True),
        required=False,
        empty_label='All SACCOs',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    is_active = forms.ChoiceField(
        choices=[('', 'All'), ('true', 'Active'), ('false', 'Inactive')],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    employment_type = forms.ChoiceField(
        choices=[('', 'All Types')] + list(UserProfile.EMPLOYMENT_TYPE_CHOICES),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )


# =============================================================================
# STAFF CREATION FORM (for admins to create staff)
# =============================================================================

class StaffCreationForm(UserCreationForm):
    """Form for admins to create staff accounts"""
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'email@example.com'
        })
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2', 'is_staff', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Username'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First Name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last Name'
            }),
            'is_staff': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    # Profile fields
    sacco = forms.ModelChoiceField(
        queryset=Sacco.objects.filter(is_active_subscription=True),
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    role = forms.ChoiceField(
        choices=UserProfile.USER_ROLES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    employee_id = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Employee ID'
        })
    )
    department = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Department'
        })
    )
    position = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Position/Job Title'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Password',
            'autocomplete': 'new-password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm Password',
            'autocomplete': 'new-password'
        })
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError(_('A user with this email already exists.'))
        return email.lower()
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        
        if commit:
            user.save()
            
            # Create UserProfile
            UserProfile.objects.create(
                user=user,
                sacco=self.cleaned_data['sacco'],
                role=self.cleaned_data['role'],
                employee_id=self.cleaned_data.get('employee_id', ''),
                department=self.cleaned_data.get('department', ''),
                position=self.cleaned_data.get('position', ''),
            )
        
        return user