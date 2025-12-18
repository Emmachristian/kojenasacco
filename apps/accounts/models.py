# user_management/models.py

from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.utils import timezone as django_timezone
from django_countries.fields import CountryField
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.core.validators import MaxValueValidator, MinValueValidator
from datetime import date
import logging
from zoneinfo import available_timezones

# Import from refactored SACCO settings

logger = logging.getLogger(__name__)

class Sacco(models.Model):
    """Sacco Model to represent different SACCOs in the system"""
    SACCO_TYPE_CHOICES = (
        ('SAVINGS_CREDIT', 'Savings and Credit'),
        ('AGRICULTURAL', 'Agricultural SACCO'),
        ('TRANSPORT', 'Transport SACCO'),
        ('TEACHERS', 'Teachers SACCO'),
        ('HEALTH_WORKERS', 'Health Workers SACCO'),
        ('MARKET_VENDORS', 'Market Vendors SACCO'),
        ('WOMEN_GROUP', 'Women Group SACCO'),
        ('YOUTH_GROUP', 'Youth Group SACCO'),
        ('MIXED_COMMON_BOND', 'Mixed Common Bond'),
        ('COMMUNITY_BASED', 'Community Based'),
        ('WORKPLACE_BASED', 'Workplace Based'),
        ('ASSOCIATION_BASED', 'Association Based'),
        ('OTHER', 'Other'),
    )
    
    # UPDATED: Add UUID primary key for consistency
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Basic sacco information
    name = models.CharField(max_length=200, help_text="Full SACCO name")
    short_name = models.CharField(max_length=50, help_text="Shortened version of SACCO name")
    abbreviation = models.CharField(max_length=10, help_text="SACCO abbreviation (e.g., ABC)")
    sacco_type = models.CharField(max_length=30, choices=SACCO_TYPE_CHOICES)
    address = models.TextField()
    country = CountryField(blank_label='(select country)')
    contact_phone = models.CharField(max_length=15)
    alternative_contact = models.CharField(max_length=15, null=True, blank=True)
    
    # Visual branding
    sacco_logo = models.ImageField(
        upload_to='sacco_logos/', 
        null=True, 
        blank=True,
        help_text="SACCO logo image (recommended: 512x512px PNG with transparent background)"
    )
    favicon = models.ImageField(
        upload_to='sacco_favicons/',
        null=True,
        blank=True,
        help_text="SACCO favicon (recommended: 32x32px ICO or PNG format)"
    )
    brand_colors = models.JSONField(
        default=dict,
        blank=True,
        help_text="SACCO brand colors as JSON: {'primary': '#hex', 'secondary': '#hex', 'accent': '#hex'}"
    )
    
    # Administrative details
    established_date = models.DateField()
    is_registered = models.BooleanField(default=False, help_text="Whether SACCO is officially registered")
    registration_number = models.CharField(max_length=50, blank=True, null=True)
    registration_details = models.TextField(blank=True, null=True)
    license_number = models.CharField(max_length=50, blank=True, null=True)
    member_capacity = models.PositiveIntegerField(default=0, help_text="Maximum number of members")
    operating_hours = models.CharField(max_length=100, help_text="e.g., Mon-Fri 8:00-17:00")
    
    # System configuration
    email_domain = models.CharField(
        max_length=100, 
        help_text="Email domain for this SACCO (e.g., mysacco.org)"
    )
    db_name = models.CharField(
        max_length=100, 
        unique=True, 
        help_text="Database name for this SACCO"
    )
    is_active = models.BooleanField(
        default=True, 
        help_text="Whether this SACCO is active in the system"
    )
    
    # Financial system details
    BASE_CURRENCY_CHOICES = (
        ('UGX', 'Ugandan Shilling'),
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
        ('KES', 'Kenyan Shilling'),
        ('TZS', 'Tanzanian Shilling'),
        ('SSP', 'South Sudanese Pound'),
        ('RWF', 'Rwandan Franc'),
    )
    base_currency = models.CharField(
        max_length=3, 
        choices=BASE_CURRENCY_CHOICES, 
        default='UGX',
        help_text="Primary currency used by the SACCO"
    )
    
    # SACCO business model
    MEMBERSHIP_TYPE_CHOICES = (
        ('OPEN', 'Open Membership'),
        ('RESTRICTED', 'Restricted Membership'),
        ('CLOSED', 'Closed Membership'),
    )
    membership_type = models.CharField(max_length=15, choices=MEMBERSHIP_TYPE_CHOICES, default='OPEN')
    
    COMMON_BOND_CHOICES = (
        ('GEOGRAPHICAL', 'Geographical Area'),
        ('OCCUPATIONAL', 'Same Occupation'),
        ('ASSOCIATIONAL', 'Same Association'),
        ('MIXED', 'Mixed Common Bond'),
    )
    common_bond = models.CharField(max_length=15, choices=COMMON_BOND_CHOICES, default='GEOGRAPHICAL')
    
    # Performance metrics
    current_members = models.PositiveIntegerField(default=0, help_text="Current number of active members")
    total_assets = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Total assets in base currency")
    
    # Contact information for different departments
    finance_office_email = models.EmailField(blank=True, null=True)
    loans_office_email = models.EmailField(blank=True, null=True)
    membership_email = models.EmailField(blank=True, null=True)
    general_email = models.EmailField(blank=True, null=True)
    
    # Digital presence
    website = models.URLField(blank=True, null=True)
    facebook_page = models.URLField(blank=True, null=True)
    twitter_handle = models.CharField(max_length=50, blank=True, null=True)
    instagram_handle = models.CharField(max_length=50, blank=True, null=True)
    linkedin_page = models.URLField(blank=True, null=True)
    
    # Timezone configuration
    TIMEZONE_CHOICES = [(tz, tz) for tz in sorted(available_timezones())]
    timezone = models.CharField(max_length=50, choices=TIMEZONE_CHOICES, default='UTC')
    
    # Regulatory and compliance
    regulatory_body = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., Uganda Microfinance Regulatory Authority")
    compliance_status = models.CharField(max_length=50, blank=True, null=True)
    last_audit_date = models.DateField(blank=True, null=True)
    next_audit_due = models.DateField(blank=True, null=True)
    
    # Security and audit
    created_by_superuser = models.BooleanField(
        default=True, 
        editable=False, 
        help_text="Flag to ensure only superusers can create SACCOs"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        db_table = 'saccos_table'
        verbose_name = "SACCO"
        verbose_name_plural = "SACCOs"
        ordering = ['name']

# =============================================================================
# ENHANCED USER MANAGER WITH SMART DEFAULTS
# =============================================================================

class UserManager(BaseUserManager):
    """Enhanced model manager for User model with smart defaults and no username field."""

    def _create_user(self, email, password=None, **extra_fields):
        """Create and save a User with the given email and password."""
        if not email:
            raise ValueError('The Email field must be set')
        
        email = self.normalize_email(email)
        
        # For regular users, try to get an active SACCO but don't create one
        if not extra_fields.get('is_superuser', False):
            try:
                active_sacco = Sacco.objects.using('default').filter(is_active=True).first()
                if active_sacco:
                    extra_fields.setdefault('sacco', active_sacco)
            except Exception as e:
                logger.warning(f"Could not assign default SACCO: {e}")
                pass
        
        # Set smart default user_type based on email domain or other criteria
        if 'user_type' not in extra_fields or not extra_fields['user_type']:
            # Smart defaults based on email patterns
            if email.endswith('@admin.sacco.com') or 'admin' in email.lower():
                extra_fields['user_type'] = 'SACCO_ADMIN'
            elif email.endswith('@manager.sacco.com') or 'manager' in email.lower():
                extra_fields['user_type'] = 'MANAGER'
            elif email.endswith('@loans.sacco.com') or 'loans' in email.lower():
                extra_fields['user_type'] = 'LOAN_OFFICER'
            elif email.endswith('@finance.sacco.com') or 'finance' in email.lower():
                extra_fields['user_type'] = 'ACCOUNTANT'
            else:
                extra_fields['user_type'] = 'CUSTOMER_SERVICE'  # Safe default
        
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """Create a regular user."""
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('is_active', True)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('user_type', 'SUPER_ADMIN')
        
        # Superusers don't need a SACCO initially - they can manage all SACCOs
        extra_fields.setdefault('sacco', None)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)
    
    def get_by_natural_key(self, email):
        """Get user by email (natural key)."""
        return self.get(email__iexact=email)

# =============================================================================
# STREAMLINED USER MODEL - CORE AUTH AND PROFILE ONLY
# =============================================================================

class User(AbstractUser):
    """
    REFACTORED: Streamlined Custom User Model focused on core authentication and profile.
    All UI preferences and detailed notifications moved to separate UserPreferences model.
    """
    
    # Enhanced user type choices with clear hierarchy
    USER_TYPE_CHOICES = (
        ('SUPER_ADMIN', _('Super Administrator')),           # Level 10
        ('ADMINISTRATOR', _('System Administrator')),        # Level 9
        ('SACCO_ADMIN', _('SACCO Administrator')),          # Level 8
        ('MANAGER', _('Manager')),                          # Level 7
        ('ASSISTANT_MANAGER', _('Assistant Manager')),      # Level 6.5
        ('LOAN_OFFICER', _('Loan Officer')),                # Level 6
        ('SENIOR_ACCOUNTANT', _('Senior Accountant')),      # Level 6
        ('ACCOUNTANT', _('Accountant')),                    # Level 5
        ('CREDIT_ANALYST', _('Credit Analyst')),            # Level 5
        ('CUSTOMER_SERVICE', _('Customer Service')),        # Level 4
        ('TELLER', _('Teller')),                           # Level 4
        ('AUDITOR', _('Auditor')),                         # Level 6
        ('COMPLIANCE_OFFICER', _('Compliance Officer')),    # Level 6
        ('SUPPORT', _('Support Staff')),                    # Level 3
        ('MEMBER', _('Member')),                           # Level 2
        ('GUEST', _('Guest User')),                        # Level 1
        ('API_USER', _('API User')),                       # Level 1
    )

    # Remove username field - use email instead
    username = None
    email = models.EmailField(
        _('Email Address'), 
        max_length=254, 
        unique=True,
        help_text=_('Required. Primary email for system login and notifications')
    )
    
    user_type = models.CharField(
        _('User Type'),
        max_length=25, 
        choices=USER_TYPE_CHOICES,
        default='CUSTOMER_SERVICE',
        help_text=_('The type/role of this user in the system')
    )
    
    # Primary SACCO association
    sacco = models.ForeignKey(
        Sacco, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='users',
        help_text=_('Primary SACCO this user belongs to')
    )
    
    # Organizational hierarchy
    reports_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subordinates',
        help_text=_('Direct supervisor/manager')
    )
    
    # =============================================================================
    # CORE PROFILE FIELDS (ESSENTIAL ONLY)
    # =============================================================================
    
    # Display names (can be different from legal names in Member model)
    first_name = models.CharField(
        _('Display First Name'),
        max_length=150,
        help_text=_('First name for display in system')
    )
    last_name = models.CharField(
        _('Display Last Name'),
        max_length=150,
        help_text=_('Last name for display in system')
    )
    
    profile_pic = models.ImageField(
        _('Profile Picture'),
        upload_to='profile_pics/', 
        null=True, 
        blank=True,
        help_text=_('Profile picture for the user interface')
    )
    
    # Essential contact information
    mobile = models.CharField(
        _('Mobile Number'),
        max_length=15, 
        null=True, 
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message=_('Enter a valid mobile number.')
            )
        ],
        help_text=_('Primary mobile number for notifications')
    )
    
    alternative_mobile = models.CharField(
        _('Alternative Mobile'),
        max_length=15, 
        null=True, 
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message=_('Enter a valid mobile number.')
            )
        ],
        help_text=_('Alternative mobile number')
    )
    
    # Basic address information
    address = models.TextField(
        _('Address'), 
        null=True, 
        blank=True,
        help_text=_('Primary address')
    )
    city = models.CharField(_('City'), max_length=100, null=True, blank=True)
    state_province = models.CharField(_('State/Province'), max_length=100, null=True, blank=True)
    postal_code = models.CharField(_('Postal Code'), max_length=20, null=True, blank=True)
    country = CountryField(_('Country'), blank_label='(select country)', default='UG')
    
    # Essential personal information
    date_of_birth = models.DateField(
        _('Date of Birth'),
        null=True,
        blank=True,
        help_text=_('Date of birth')
    )
    
    GENDER_CHOICES = (
        ('MALE', _('Male')),
        ('FEMALE', _('Female')),
        ('OTHER', _('Other')),
        ('PREFER_NOT_TO_SAY', _('Prefer not to say')),
    )
    gender = models.CharField(
        _('Gender'),
        max_length=20,
        choices=GENDER_CHOICES,
        null=True,
        blank=True
    )
    
    # =============================================================================
    # CORE LOCALIZATION SETTINGS (ESSENTIAL ONLY)
    # =============================================================================
    
    LANGUAGE_CHOICES = (
        ('en', _('English')),
        ('sw', _('Swahili')),
        ('lg', _('Luganda')),
        ('luo', _('Luo')),
        ('rn', _('Runyankole')),
        ('fr', _('French')),
        ('es', _('Spanish')),
        ('ar', _('Arabic')),
    )
    language = models.CharField(
        _('Preferred Language'),
        max_length=10, 
        choices=LANGUAGE_CHOICES, 
        default='en'
    )

    # Timezone field - all available timezones
    TIMEZONE_CHOICES = [(tz, tz) for tz in sorted(available_timezones())]
    timezone = models.CharField(max_length=50, choices=TIMEZONE_CHOICES, default='Africa/Kampala')
    
    # =============================================================================
    # ENHANCED TIMESTAMP FIELDS
    # =============================================================================
    
    date_joined = models.DateTimeField(_('Date Joined'), default=django_timezone.now)
    last_login = models.DateTimeField(_('Last Login'), null=True, blank=True)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    # =============================================================================
    # SECURITY FIELDS
    # =============================================================================
    
    password_changed_at = models.DateTimeField(
        _('Password Changed At'),
        null=True,
        blank=True,
        help_text=_('When the password was last changed')
    )
    
    failed_login_attempts = models.PositiveIntegerField(
        _('Failed Login Attempts'),
        default=0,
        help_text=_('Number of consecutive failed login attempts')
    )
    
    account_locked_until = models.DateTimeField(
        _('Account Locked Until'),
        null=True,
        blank=True,
        help_text=_('Account is locked until this time')
    )
    
    last_activity = models.DateTimeField(
        _('Last Activity'),
        null=True,
        blank=True,
        help_text=_('Last time user performed any action in system')
    )
    
    login_ip_address = models.GenericIPAddressField(
        _('Last Login IP'),
        null=True,
        blank=True,
        help_text=_('IP address of last login')
    )
    
    # Two-factor authentication
    two_factor_enabled = models.BooleanField(
        _('Two-Factor Authentication'),
        default=False,
        help_text=_('Whether 2FA is enabled for this user')
    )
    
    two_factor_secret = models.CharField(
        _('2FA Secret'),
        max_length=32,
        null=True,
        blank=True,
        help_text=_('Secret key for 2FA (encrypted)')
    )
    
    # Session management
    force_password_change = models.BooleanField(
        _('Force Password Change'),
        default=False,
        help_text=_('User must change password on next login')
    )
    
    session_timeout_minutes = models.PositiveIntegerField(
        _('Session Timeout (Minutes)'),
        default=60,
        help_text=_('Session timeout for this user in minutes')
    )
    
    # =============================================================================
    # API ACCESS FIELDS
    # =============================================================================
    
    api_access_enabled = models.BooleanField(
        _('API Access'),
        default=False,
        help_text=_('Whether user can access API endpoints')
    )
    
    api_rate_limit = models.PositiveIntegerField(
        _('API Rate Limit (per hour)'),
        default=1000,
        help_text=_('API requests per hour limit')
    )
    
    # Access restrictions
    access_start_time = models.TimeField(
        _('Access Start Time'),
        null=True,
        blank=True,
        help_text=_('Earliest time user can access system')
    )
    
    access_end_time = models.TimeField(
        _('Access End Time'),
        null=True,
        blank=True,
        help_text=_('Latest time user can access system')
    )
    
    allowed_ip_addresses = models.TextField(
        _('Allowed IP Addresses'),
        null=True,
        blank=True,
        help_text=_('Comma-separated list of allowed IP addresses/ranges')
    )
    
    # =============================================================================
    # FIX FOR DJANGO AUTH CONFLICTS
    # =============================================================================
    
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name=_('groups'),
        blank=True,
        help_text=_(
            'The groups this user belongs to. A user will get all permissions '
            'granted to each of their groups.'
        ),
        related_name='user_management_user_set',
        related_query_name='user_management_user',
    )
    
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name=_('user permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name='user_management_user_set',
        related_query_name='user_management_user',
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'user_type']

    # =============================================================================
    # CORE MODEL METHODS
    # =============================================================================

    def __str__(self):
        """String representation of the user."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name} ({self.get_user_type_display()})"
        return f"{self.email} ({self.get_user_type_display()})"

    def get_full_name(self):
        """Return the display full name of the user."""
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name or self.email.split('@')[0]
    
    def get_display_name(self):
        """Return appropriate display name for UI."""
        if self.first_name or self.last_name:
            return self.get_full_name()
        return self.email
    
    @property
    def age(self):
        """Calculate user's age if date of birth is provided."""
        if self.date_of_birth:
            today = date.today()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None
    
    # =============================================================================
    # HIERARCHICAL PERMISSION SYSTEM
    # =============================================================================
    
    def get_user_type_level(self):
        """Get numerical level for user type hierarchy"""
        hierarchy = {
            'SUPER_ADMIN': 10,
            'ADMINISTRATOR': 9,
            'SACCO_ADMIN': 8,
            'MANAGER': 7,
            'ASSISTANT_MANAGER': 6.5,
            'LOAN_OFFICER': 6,
            'SENIOR_ACCOUNTANT': 6,
            'AUDITOR': 6,
            'COMPLIANCE_OFFICER': 6,
            'ACCOUNTANT': 5,
            'CREDIT_ANALYST': 5,
            'CUSTOMER_SERVICE': 4,
            'TELLER': 4,
            'SUPPORT': 3,
            'MEMBER': 2,
            'GUEST': 1,
            'API_USER': 1,
        }
        return hierarchy.get(self.user_type, 0)
    
    def is_admin_user(self):
        """Check if user is an administrator level user"""
        return self.user_type in ['SUPER_ADMIN', 'ADMINISTRATOR', 'SACCO_ADMIN'] or self.is_superuser
    
    def is_management_user(self):
        """Check if user is in management"""
        return self.user_type in [
            'SUPER_ADMIN', 'ADMINISTRATOR', 'SACCO_ADMIN', 'MANAGER', 'ASSISTANT_MANAGER'
        ] or self.is_superuser
    
    # =============================================================================
    # GRANULAR SACCO PERMISSION METHODS
    # =============================================================================
    
    def can_view_member_data(self):
        """Check if user can view member data"""
        return self.user_type in [
            'SUPER_ADMIN', 'ADMINISTRATOR', 'SACCO_ADMIN', 'MANAGER', 
            'ASSISTANT_MANAGER', 'LOAN_OFFICER', 'CUSTOMER_SERVICE', 
            'CREDIT_ANALYST', 'COMPLIANCE_OFFICER'
        ] or self.is_superuser
    
    def can_edit_member_data(self):
        """Check if user can edit member data"""
        return self.user_type in [
            'SUPER_ADMIN', 'ADMINISTRATOR', 'SACCO_ADMIN', 'MANAGER', 'ASSISTANT_MANAGER'
        ] or self.is_superuser
    
    def can_create_member_accounts(self):
        """Check if user can create new member accounts"""
        return self.user_type in [
            'SUPER_ADMIN', 'ADMINISTRATOR', 'SACCO_ADMIN', 'MANAGER', 
            'ASSISTANT_MANAGER', 'CUSTOMER_SERVICE'
        ] or self.is_superuser
    
    def can_blacklist_members(self):
        """Check if user can blacklist/unblacklist members"""
        return self.user_type in [
            'SUPER_ADMIN', 'ADMINISTRATOR', 'SACCO_ADMIN', 'MANAGER'
        ] or self.is_superuser
    
    def can_approve_loans(self):
        """Check if user can approve loans"""
        return self.user_type in [
            'SUPER_ADMIN', 'ADMINISTRATOR', 'SACCO_ADMIN', 'MANAGER', 
            'ASSISTANT_MANAGER', 'LOAN_OFFICER'
        ] or self.is_superuser
    
    def can_disburse_loans(self):
        """Check if user can disburse approved loans"""
        return self.user_type in [
            'SUPER_ADMIN', 'ADMINISTRATOR', 'SACCO_ADMIN', 'MANAGER', 
            'LOAN_OFFICER', 'TELLER'
        ] or self.is_superuser
    
    def can_view_financial_reports(self):
        """Check if user can view financial reports"""
        return self.user_type in [
            'SUPER_ADMIN', 'ADMINISTRATOR', 'SACCO_ADMIN', 'MANAGER', 
            'ASSISTANT_MANAGER', 'SENIOR_ACCOUNTANT', 'ACCOUNTANT', 'AUDITOR'
        ] or self.is_superuser
    
    def can_edit_financial_data(self):
        """Check if user can edit financial data"""
        return self.user_type in [
            'SUPER_ADMIN', 'ADMINISTRATOR', 'SACCO_ADMIN', 'SENIOR_ACCOUNTANT', 'ACCOUNTANT'
        ] or self.is_superuser
    
    def can_manage_transactions(self):
        """Check if user can manage transactions"""
        return self.user_type in [
            'SUPER_ADMIN', 'ADMINISTRATOR', 'SACCO_ADMIN', 'MANAGER',
            'SENIOR_ACCOUNTANT', 'ACCOUNTANT', 'TELLER'
        ] or self.is_superuser
    
    def can_reverse_transactions(self):
        """Check if user can reverse transactions"""
        return self.user_type in [
            'SUPER_ADMIN', 'ADMINISTRATOR', 'SACCO_ADMIN', 'MANAGER'
        ] or self.is_superuser
    
    def can_view_audit_logs(self):
        """Check if user can view audit logs"""
        return self.user_type in [
            'SUPER_ADMIN', 'ADMINISTRATOR', 'SACCO_ADMIN', 'MANAGER', 
            'AUDITOR', 'COMPLIANCE_OFFICER'
        ] or self.is_superuser
    
    def can_export_data(self):
        """Check if user can export data"""
        return self.user_type in [
            'SUPER_ADMIN', 'ADMINISTRATOR', 'SACCO_ADMIN', 'MANAGER',
            'SENIOR_ACCOUNTANT', 'AUDITOR'
        ] or self.is_superuser
    
    def can_manage_sacco_settings(self):
        """Check if user can manage SACCO settings"""
        return self.user_type in [
            'SUPER_ADMIN', 'ADMINISTRATOR', 'SACCO_ADMIN'
        ] or self.is_superuser
    
    def can_view_system_reports(self):
        """Check if user can view system-wide reports"""
        return self.user_type in [
            'SUPER_ADMIN', 'ADMINISTRATOR'
        ] or self.is_superuser
    
    def get_sacco_permissions(self):
        """Get all SACCO-specific permissions for this user"""
        return {
            'can_view_member_data': self.can_view_member_data(),
            'can_edit_member_data': self.can_edit_member_data(),
            'can_create_member_accounts': self.can_create_member_accounts(),
            'can_blacklist_members': self.can_blacklist_members(),
            'can_approve_loans': self.can_approve_loans(),
            'can_disburse_loans': self.can_disburse_loans(),
            'can_view_financial_reports': self.can_view_financial_reports(),
            'can_edit_financial_data': self.can_edit_financial_data(),
            'can_manage_transactions': self.can_manage_transactions(),
            'can_reverse_transactions': self.can_reverse_transactions(),
            'can_view_audit_logs': self.can_view_audit_logs(),
            'can_export_data': self.can_export_data(),
            'can_manage_sacco_settings': self.can_manage_sacco_settings(),
            'can_view_system_reports': self.can_view_system_reports(),
        }
    
    # =============================================================================
    # ORGANIZATIONAL HIERARCHY METHODS
    # =============================================================================
    
    def get_direct_subordinates(self):
        """Get all direct subordinates"""
        return User.objects.filter(reports_to=self, is_active=True)
    
    def get_all_subordinates(self):
        """Get all subordinates recursively"""
        subordinates = list(self.get_direct_subordinates())
        for subordinate in list(subordinates):  # Create a copy to avoid modification during iteration
            subordinates.extend(subordinate.get_all_subordinates())
        return subordinates
    
    def can_manage_subordinate(self, target_user):
        """Check if user can manage a specific subordinate"""
        if self.is_superuser:
            return True
        return target_user in self.get_all_subordinates()
    
    def get_supervision_chain(self):
        """Get the chain of command up to top level"""
        chain = []
        current_supervisor = self.reports_to
        while current_supervisor and current_supervisor not in chain:  # Prevent infinite loops
            chain.append(current_supervisor)
            current_supervisor = current_supervisor.reports_to
        return chain
    
    # =============================================================================
    # USER MANAGEMENT METHODS (ENHANCED)
    # =============================================================================

    def can_manage_users(self):
        """Check if user has permission to manage other users"""
        return self.is_admin_user()

    def can_create_user_type(self, target_user_type):
        """Check if user can create a user of specific type based on hierarchy"""
        if self.is_superuser:
            return True
        
        if not self.can_manage_users():
            return False
        
        # Get hierarchy levels
        my_level = self.get_user_type_level()
        
        # Find target user type level
        hierarchy = {
            'SUPER_ADMIN': 10, 'ADMINISTRATOR': 9, 'SACCO_ADMIN': 8,
            'MANAGER': 7, 'ASSISTANT_MANAGER': 6.5, 'LOAN_OFFICER': 6,
            'SENIOR_ACCOUNTANT': 6, 'AUDITOR': 6, 'COMPLIANCE_OFFICER': 6,
            'ACCOUNTANT': 5, 'CREDIT_ANALYST': 5, 'CUSTOMER_SERVICE': 4,
            'TELLER': 4, 'SUPPORT': 3, 'MEMBER': 2, 'GUEST': 1, 'API_USER': 1
        }
        target_level = hierarchy.get(target_user_type, 0)
        
        # Can only create users at lower hierarchy levels
        return my_level > target_level
    
    def can_edit_user(self, target_user):
        """Check if user can edit another user"""
        if self.is_superuser:
            return True
        
        if not self.can_manage_users():
            return False
        
        if target_user.is_superuser and not self.is_superuser:
            return False
        
        # Can edit users at lower hierarchy levels or subordinates
        return (self.get_user_type_level() > target_user.get_user_type_level() or 
                self.can_manage_subordinate(target_user))
    
    def can_delete_user(self, target_user):
        """Check if user can delete another user"""
        if target_user == self:  # Can't delete yourself
            return False
        return self.can_edit_user(target_user)
    
    # =============================================================================
    # MEMBER INTEGRATION METHODS
    # =============================================================================
    
    def get_member_profile(self, sacco=None):
        """Get member profile from specific SACCO"""
        if sacco is None:
            sacco = self.sacco
        
        try:
            member_account = self.member_accounts.get(sacco=sacco, is_active=True)
            return member_account.get_member_profile()
        except:
            return None
    
    def get_all_member_profiles(self):
        """Get all member profiles across all SACCOs"""
        profiles = []
        for member_account in self.member_accounts.filter(is_active=True):
            profile = member_account.get_member_profile()
            if profile:
                profiles.append({
                    'sacco': member_account.sacco,
                    'member_account': member_account,
                    'member_profile': profile
                })
        return profiles
    
    # =============================================================================
    # NOTIFICATION METHODS (USING PREFERENCES MODEL)
    # =============================================================================
    
    def can_receive_notification(self, notification_type):
        """Check if user can receive specific type of notification."""
        if not hasattr(self, 'preferences'):
            # Fallback to basic contact methods if no preferences set
            return notification_type in ['email', 'security'] and bool(self.email)
            
        prefs = self.preferences
        notification_preferences = {
            'email': prefs.email_notifications,
            'sms': prefs.sms_notifications,
            'push': prefs.push_notifications,
            'transactions': prefs.transaction_notifications,
            'loans': prefs.loan_notifications,
            'security': prefs.security_alerts,
            'marketing': prefs.marketing_notifications,
            'system': prefs.system_notifications,
        }
        
        return notification_preferences.get(notification_type, False)
    
    def get_preferred_contact_method(self):
        """Get user's preferred contact method."""
        if not hasattr(self, 'preferences'):
            return 'email' if self.email else 'sms' if self.mobile else None
            
        prefs = self.preferences
        if prefs.email_notifications and self.email:
            return 'email'
        elif prefs.sms_notifications and self.mobile:
            return 'sms'
        elif prefs.push_notifications:
            return 'push'
        return None
    
    def get_notification_frequency(self, method='email'):
        """Get notification frequency preference"""
        if not hasattr(self, 'preferences'):
            return 'IMMEDIATE'
        
        prefs = self.preferences
        if method == 'email':
            return prefs.email_frequency
        elif method == 'sms':
            return prefs.sms_frequency
        return 'IMMEDIATE'
    
    def is_in_quiet_hours(self):
        """Check if current time is within user's quiet hours"""
        if not hasattr(self, 'preferences'):
            return False
        
        return self.preferences.is_quiet_hours()
    
    # =============================================================================
    # SACCO ACCESS METHODS
    # =============================================================================
    
    def can_access_sacco(self, sacco):
        """Check if user can access a specific SACCO."""
        if self.is_superuser or self.user_type in ['SUPER_ADMIN', 'ADMINISTRATOR']:
            return True
        
        # Check primary SACCO
        if self.sacco == sacco:
            return True
        
        # Check member accounts
        return self.member_accounts.filter(sacco=sacco, is_active=True).exists()
    
    def get_accessible_saccos(self):
        """Get all SACCOs this user can access."""
        if self.is_superuser or self.user_type in ['SUPER_ADMIN', 'ADMINISTRATOR']:
            return Sacco.objects.filter(is_active=True)
        
        accessible_saccos = set()
        
        # Add primary SACCO
        if self.sacco and self.sacco.is_active:
            accessible_saccos.add(self.sacco)
        
        # Add SACCOs from member accounts
        member_saccos = self.member_accounts.filter(
            is_active=True,
            sacco__is_active=True
        ).values_list('sacco', flat=True)
        
        for sacco_id in member_saccos:
            try:
                sacco = Sacco.objects.get(id=sacco_id, is_active=True)
                accessible_saccos.add(sacco)
            except Sacco.DoesNotExist:
                pass
        
        return list(accessible_saccos)
    
    def has_sacco_permission(self, permission, sacco=None):
        """Check if user has specific permission within a SACCO context."""
        if self.is_superuser:
            return True
        
        # Use current SACCO if none specified
        if sacco is None:
            sacco = self.sacco
        
        if not sacco or not self.can_access_sacco(sacco):
            return False
        
        # Permission logic based on user type
        return self.has_perm(permission)
    
    # =============================================================================
    # SECURITY METHODS
    # =============================================================================
    
    def is_account_locked(self):
        """Check if the account is currently locked."""
        if self.account_locked_until:
            return django_timezone.now() < self.account_locked_until
        return False
    
    def unlock_account(self):
        """Unlock the user account."""
        self.account_locked_until = None
        self.failed_login_attempts = 0
        self.save(update_fields=['account_locked_until', 'failed_login_attempts'])
        logger.info(f"Account unlocked for user: {self.email}")
    
    def lock_account(self, duration_minutes=30, reason="Multiple failed login attempts"):
        """Lock the user account for specified duration."""
        from datetime import timedelta
        self.account_locked_until = django_timezone.now() + timedelta(minutes=duration_minutes)
        self.save(update_fields=['account_locked_until'])
        logger.warning(f"Account locked for user: {self.email}. Reason: {reason}")
    
    def record_failed_login(self):
        """Record a failed login attempt."""
        self.failed_login_attempts += 1
        
        # Auto-lock after too many failed attempts
        from django.conf import settings
        max_attempts = getattr(settings, 'MAX_LOGIN_ATTEMPTS', 5)
        
        if self.failed_login_attempts >= max_attempts:
            lockout_duration = getattr(settings, 'ACCOUNT_LOCKOUT_DURATION_MINUTES', 30)
            self.lock_account(lockout_duration)
        
        self.save(update_fields=['failed_login_attempts'])
    
    def record_successful_login(self, ip_address=None):
        """Record a successful login."""
        self.failed_login_attempts = 0
        self.last_login = django_timezone.now()
        self.last_activity = django_timezone.now()
        if ip_address:
            self.login_ip_address = ip_address
        self.save(update_fields=['failed_login_attempts', 'last_login', 'last_activity', 'login_ip_address'])
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = django_timezone.now()
        self.save(update_fields=['last_activity'])
    
    def needs_password_change(self):
        """Check if user needs to change password."""
        if self.force_password_change:
            return True
        
        if not self.password_changed_at:
            return True
        
        # Check password age
        from django.conf import settings
        from datetime import timedelta
        
        max_age_days = getattr(settings, 'PASSWORD_EXPIRY_DAYS', 90)
        if max_age_days > 0:
            password_age = django_timezone.now() - self.password_changed_at
            return password_age > timedelta(days=max_age_days)
        
        return False
    
    def set_password(self, raw_password):
        """Override to track password changes."""
        super().set_password(raw_password)
        self.password_changed_at = django_timezone.now()
        self.force_password_change = False
    
    # =============================================================================
    # VALIDATION METHODS
    # =============================================================================
    
    def clean(self):
        """Validate the user data."""
        super().clean()
        errors = {}
        
        # Email validation
        if self.email:
            if User.objects.filter(email__iexact=self.email).exclude(pk=self.pk).exists():
                errors['email'] = _('A user with this email already exists.')
        
        # Date validations
        if self.date_of_birth and self.date_of_birth > date.today():
            errors['date_of_birth'] = _('Date of birth cannot be in the future.')
        
        # Age validation for certain user types
        if self.date_of_birth and self.user_type in ['MEMBER']:
            age = self.age
            if age and age < 16:
                errors['date_of_birth'] = _('Members must be at least 16 years old.')
        
        # Access time validation
        if self.access_start_time and self.access_end_time:
            if self.access_start_time >= self.access_end_time:
                errors['access_end_time'] = _('End time must be after start time.')
        
        # SACCO validation for staff
        staff_types = ['SACCO_ADMIN', 'MANAGER', 'ASSISTANT_MANAGER', 'LOAN_OFFICER', 
                      'SENIOR_ACCOUNTANT', 'ACCOUNTANT', 'CUSTOMER_SERVICE', 'TELLER', 
                      'CREDIT_ANALYST', 'AUDITOR', 'COMPLIANCE_OFFICER']
        if self.user_type in staff_types and not self.sacco:
            errors['sacco'] = _('Staff users must be assigned to a SACCO.')
        
        # Hierarchy validation
        if self.reports_to:
            if self.reports_to == self:
                errors['reports_to'] = _('User cannot report to themselves.')
            elif self.reports_to.get_user_type_level() <= self.get_user_type_level():
                errors['reports_to'] = _('User can only report to someone at a higher hierarchy level.')
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Enhanced save method with automatic field updates."""
        # Set staff status based on user type
        staff_types = [
            'SUPER_ADMIN', 'ADMINISTRATOR', 'SACCO_ADMIN', 'MANAGER', 'ASSISTANT_MANAGER',
            'LOAN_OFFICER', 'SENIOR_ACCOUNTANT', 'ACCOUNTANT', 'CUSTOMER_SERVICE', 'TELLER', 
            'CREDIT_ANALYST', 'AUDITOR', 'COMPLIANCE_OFFICER', 'SUPPORT'
        ]
        
        if self.user_type in staff_types:
            self.is_staff = True
        
        # Superuser permissions
        if self.user_type in ['SUPER_ADMIN', 'ADMINISTRATOR']:
            self.is_superuser = True
            self.is_staff = True
        
        super().save(*args, **kwargs)
        
        # Create user preferences if they don't exist
        if not hasattr(self, 'preferences'):
            UserPreferences.objects.create(user=self)
        
    class Meta:
        db_table = 'users'
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        ordering = ['first_name', 'last_name']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['user_type']),
            models.Index(fields=['sacco']),
            models.Index(fields=['is_active']),
            models.Index(fields=['created_at']),
            models.Index(fields=['last_login']),
            models.Index(fields=['reports_to']),
        ]


# =============================================================================
# CONSOLIDATED USER PREFERENCES MODEL
# =============================================================================

class UserPreferences(models.Model):
    """
    CONSOLIDATED: All user preferences in one place - UI themes, notifications, settings.
    Replaces scattered fields from User model and UserNotificationPreference model.
    """
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='preferences'
    )
    
    # =============================================================================
    # UI/THEME PREFERENCES (MOVED FROM USER MODEL)
    # =============================================================================
    
    theme_color = models.CharField(
        _('Theme Color'),
        max_length=20,
        choices=[
            ('app-theme-white', _('Light Theme')),
            ('app-theme-dark', _('Dark Theme')),
            ('app-theme-gray', _('Gray Theme')),
            ('app-theme-blue', _('Blue Theme')),
            ('app-theme-green', _('Green Theme')),
        ],
        default='app-theme-white'
    )
    
    header_class = models.CharField(
        _('Header Theme'),
        max_length=100,
        default='navbar-dark bg-primary',
        help_text=_('CSS classes for header styling')
    )
    
    sidebar_class = models.CharField(
        _('Sidebar Theme'),
        max_length=100,
        default='sidebar-dark-primary',
        help_text=_('CSS classes for sidebar styling')
    )
    
    fixed_header = models.BooleanField(_('Fixed Header'), default=True)
    fixed_sidebar = models.BooleanField(_('Fixed Sidebar'), default=True)
    fixed_footer = models.BooleanField(_('Fixed Footer'), default=False)
    
    page_tabs_style = models.CharField(
        _('Page Tabs Style'),
        max_length=30,
        default='body-tabs-shadow',
        help_text=_('Style for page tabs')
    )
    
    dashboard_layout = models.CharField(
        _('Dashboard Layout'),
        max_length=20,
        choices=[
            ('grid', _('Grid Layout')),
            ('list', _('List Layout')),
            ('cards', _('Card Layout')),
            ('compact', _('Compact Layout')),
        ],
        default='grid'
    )
    
    items_per_page = models.PositiveIntegerField(
        _('Items Per Page'),
        default=25,
        choices=[(10, '10'), (25, '25'), (50, '50'), (100, '100')],
        help_text=_('Number of items to display per page')
    )
    
    # Date and time format preferences
    date_format = models.CharField(
        _('Date Format'),
        max_length=10,
        choices=[
            ('Y-m-d', _('YYYY-MM-DD')),
            ('d/m/Y', _('DD/MM/YYYY')),
            ('m/d/Y', _('MM/DD/YYYY')),
            ('d-m-Y', _('DD-MM-YYYY')),
            ('d.m.Y', _('DD.MM.YYYY')),
        ],
        default='d/m/Y'
    )
    
    time_format = models.CharField(
        _('Time Format'),
        max_length=10,
        choices=[
            ('H:i', _('24-hour (HH:MM)')),
            ('g:i A', _('12-hour (H:MM AM/PM)')),
            ('H:i:s', _('24-hour with seconds')),
            ('g:i:s A', _('12-hour with seconds')),
        ],
        default='H:i'
    )
    
    # =============================================================================
    # CONSOLIDATED NOTIFICATION PREFERENCES
    # =============================================================================
    
    # Email notifications
    email_notifications = models.BooleanField(
        _('Email Notifications'),
        default=True,
        help_text=_('Receive notifications via email')
    )
    
    email_frequency = models.CharField(
        _('Email Frequency'),
        max_length=20,
        choices=[
            ('IMMEDIATE', _('Immediate')),
            ('HOURLY', _('Hourly Digest')),
            ('DAILY', _('Daily Digest')),
            ('WEEKLY', _('Weekly Digest')),
        ],
        default='IMMEDIATE'
    )
    
    # SMS notifications
    sms_notifications = models.BooleanField(
        _('SMS Notifications'),
        default=True,
        help_text=_('Receive SMS notifications')
    )
    
    sms_frequency = models.CharField(
        _('SMS Frequency'),
        max_length=20,
        choices=[
            ('IMMEDIATE', _('Immediate')),
            ('DAILY', _('Daily Summary')),
        ],
        default='IMMEDIATE'
    )
    
    # Push notifications
    push_notifications = models.BooleanField(
        _('Push Notifications'),
        default=True,
        help_text=_('Receive push notifications in browser/mobile app')
    )
    
    # =============================================================================
    # SPECIFIC NOTIFICATION TYPES
    # =============================================================================
    
    transaction_notifications = models.BooleanField(
        _('Transaction Notifications'),
        default=True,
        help_text=_('Receive notifications for transactions')
    )
    
    loan_notifications = models.BooleanField(
        _('Loan Notifications'),
        default=True,
        help_text=_('Receive notifications for loan-related updates')
    )
    
    member_notifications = models.BooleanField(
        _('Member Notifications'),
        default=True,
        help_text=_('Receive notifications about member activities')
    )
    
    system_notifications = models.BooleanField(
        _('System Notifications'),
        default=True,
        help_text=_('Receive system and administrative notifications')
    )
    
    security_alerts = models.BooleanField(
        _('Security Alerts'),
        default=True,
        help_text=_('Receive security-related notifications (always recommended)')
    )
    
    account_updates = models.BooleanField(
        _('Account Updates'),
        default=True,
        help_text=_('Receive notifications about account changes')
    )
    
    newsletter = models.BooleanField(
        _('Newsletter'),
        default=False,
        help_text=_('Receive newsletter emails')
    )
    
    marketing_notifications = models.BooleanField(
        _('Marketing Communications'),
        default=False,
        help_text=_('Receive marketing emails and promotions')
    )
    
    # =============================================================================
    # QUIET HOURS SETTINGS
    # =============================================================================
    
    quiet_hours_enabled = models.BooleanField(
        _('Enable Quiet Hours'),
        default=False,
        help_text=_('Disable non-urgent notifications during specified hours')
    )
    
    quiet_start_time = models.TimeField(
        _('Quiet Hours Start'),
        null=True,
        blank=True,
        help_text=_('Start of quiet hours (e.g., 22:00)')
    )
    
    quiet_end_time = models.TimeField(
        _('Quiet Hours End'),
        null=True,
        blank=True,
        help_text=_('End of quiet hours (e.g., 08:00)')
    )
    
    # =============================================================================
    # ADVANCED PREFERENCES
    # =============================================================================
    
    # Custom preferences as JSON for extensibility
    custom_preferences = models.JSONField(
        _('Custom Preferences'),
        default=dict,
        blank=True,
        help_text=_('Additional custom preferences as JSON')
    )
    
    # Auto-logout settings
    auto_logout_enabled = models.BooleanField(
        _('Auto Logout'),
        default=False,
        help_text=_('Automatically logout after period of inactivity')
    )
    
    auto_logout_minutes = models.PositiveIntegerField(
        _('Auto Logout (Minutes)'),
        default=60,
        help_text=_('Minutes of inactivity before auto logout')
    )
    
    # Data export preferences
    default_export_format = models.CharField(
        _('Default Export Format'),
        max_length=10,
        choices=[
            ('CSV', _('CSV')),
            ('EXCEL', _('Excel')),
            ('PDF', _('PDF')),
        ],
        default='CSV'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_preferences'
        verbose_name = _('User Preference')
        verbose_name_plural = _('User Preferences')
    
    def __str__(self):
        return f"{self.user.get_full_name()} - Preferences"
    
    def can_send_notification(self, notification_type, method='email'):
        """Check if notification can be sent based on preferences"""
        # Check if method is enabled
        if method == 'email' and not self.email_notifications:
            return False
        elif method == 'sms' and not self.sms_notifications:
            return False
        elif method == 'push' and not self.push_notifications:
            return False
        
        # Check notification type preferences
        type_preferences = {
            'transaction': self.transaction_notifications,
            'loan': self.loan_notifications,
            'member': self.member_notifications,
            'system': self.system_notifications,
            'security': self.security_alerts,
            'account': self.account_updates,
            'newsletter': self.newsletter,
            'marketing': self.marketing_notifications,
        }
        
        if notification_type in type_preferences:
            return type_preferences[notification_type]
        
        return True  # Default to allow if type not specified
    
    def is_quiet_hours(self):
        """Check if current time is within quiet hours"""
        if not self.quiet_hours_enabled or not self.quiet_start_time or not self.quiet_end_time:
            return False
        
        now = django_timezone.localtime().time()
        
        if self.quiet_start_time <= self.quiet_end_time:
            # Normal case: 22:00 to 08:00
            return self.quiet_start_time <= now <= self.quiet_end_time
        else:
            # Overnight case: 22:00 to 08:00 (crosses midnight)
            return now >= self.quiet_start_time or now <= self.quiet_end_time
    
    def should_send_notification(self, notification_type, method='email', is_urgent=False):
        """Complete check if notification should be sent"""
        # Always allow urgent notifications (security alerts, etc.)
        if is_urgent and notification_type in ['security']:
            return True
        
        # Check basic preferences
        if not self.can_send_notification(notification_type, method):
            return False
        
        # Check quiet hours for non-urgent notifications
        if not is_urgent and self.is_quiet_hours():
            return False
        
        return True
    
    def get_theme_css_classes(self):
        """Get complete CSS classes for theming"""
        return {
            'theme_color': self.theme_color,
            'header_class': self.header_class,
            'sidebar_class': self.sidebar_class,
            'page_tabs_style': self.page_tabs_style,
            'layout_options': {
                'fixed_header': self.fixed_header,
                'fixed_sidebar': self.fixed_sidebar,
                'fixed_footer': self.fixed_footer,
            }
        }
    
    def clean(self):
        """Validate preferences"""
        super().clean()
        errors = {}
        
        # Validate quiet hours
        if self.quiet_hours_enabled:
            if not self.quiet_start_time or not self.quiet_end_time:
                errors['quiet_hours_enabled'] = _('Quiet hours start and end times are required when quiet hours are enabled')
        
        # Validate auto logout
        if self.auto_logout_enabled and self.auto_logout_minutes < 5:
            errors['auto_logout_minutes'] = _('Auto logout must be at least 5 minutes')
        
        if errors:
            raise ValidationError(errors)


# =============================================================================
# ENHANCED MEMBER ACCOUNT MODEL (STREAMLINED)
# =============================================================================

class MemberAccount(models.Model):
    """
    STREAMLINED: Bridge model linking system users to SACCO-specific member profiles.
    Focuses on essential digital access management.
    """
    
    DIGITAL_ACCESS_STATUS_CHOICES = (
        ('NOT_REQUESTED', _('Not Requested')),
        ('REQUESTED', _('Requested')),
        ('APPROVED', _('Approved')),
        ('ACTIVE', _('Active')),
        ('SUSPENDED', _('Suspended')),
        ('REVOKED', _('Revoked')),
        ('EXPIRED', _('Expired')),
    )
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='member_accounts'
    )
    
    sacco = models.ForeignKey(
        Sacco, 
        on_delete=models.CASCADE, 
        related_name='member_accounts'
    )
    
    member_number = models.CharField(
        _('Member Number'),
        max_length=20,
        help_text=_('Unique member number within this SACCO')
    )
    
    # Basic membership info
    is_active = models.BooleanField(
        _('Is Active'),
        default=True,
        help_text=_('Whether this membership is currently active')
    )
    
    membership_date = models.DateField(
        _('Membership Date'),
        default=date.today,
        help_text=_('Date when user became a member of this SACCO')
    )
    
    # Status tracking
    STATUS_CHOICES = [
        ('PENDING', _('Pending Approval')),
        ('ACTIVE', _('Active')),
        ('SUSPENDED', _('Suspended')),
        ('TERMINATED', _('Terminated')),
        ('WITHDRAWN', _('Withdrawn')),
    ]
    
    status = models.CharField(
        _('Membership Status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    
    status_changed_date = models.DateTimeField(auto_now_add=True)
    status_changed_reason = models.TextField(blank=True, null=True)
    
    # Membership details
    MEMBERSHIP_CATEGORY_CHOICES = [
        ('REGULAR', _('Regular')),
        ('PREMIUM', _('Premium')),
        ('CORPORATE', _('Corporate')),
        ('STUDENT', _('Student')),
        ('SENIOR', _('Senior')),
    ]
    
    membership_category = models.CharField(
        _('Membership Category'),
        max_length=20,
        choices=MEMBERSHIP_CATEGORY_CHOICES,
        default='REGULAR'
    )
    
    # Digital access management
    digital_access_status = models.CharField(
        _('Digital Access Status'),
        max_length=20,
        choices=DIGITAL_ACCESS_STATUS_CHOICES,
        default='NOT_REQUESTED',
        help_text="Status of digital access request"
    )
    
    access_requested_date = models.DateTimeField(
        _('Access Requested Date'),
        null=True,
        blank=True,
        help_text="When digital access was requested"
    )
    
    access_approved_date = models.DateTimeField(
        _('Access Approved Date'),
        null=True,
        blank=True,
        help_text="When digital access was approved"
    )
    
    access_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_member_accounts',
        help_text="Staff user who approved digital access"
    )
    
    # Referral information
    referred_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referred_members',
        help_text=_('User who referred this member')
    )
    
    # Notes and tracking
    notes = models.TextField(
        _('Notes'),
        blank=True,
        null=True,
        help_text="Internal notes about this member account"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'member_accounts'
        unique_together = ('sacco', 'member_number')
        verbose_name = _('Member Account')
        verbose_name_plural = _('Member Accounts')
        indexes = [
            models.Index(fields=['user', 'sacco']),
            models.Index(fields=['member_number']),
            models.Index(fields=['is_active', 'status']),
            models.Index(fields=['digital_access_status']),
            models.Index(fields=['membership_date']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.member_number} ({self.sacco.name})"
    
    def get_member_profile(self):
        """Get the detailed member profile from the SACCO database."""
        try:
            # Import here to avoid circular imports
            from members.models import Member
            
            # Use the SACCO's database
            return Member.objects.using(self.sacco.db_name).filter(
                member_number=self.member_number
            ).first()
        except Exception as e:
            logger.warning(f"Could not fetch member profile for {self.member_number}: {e}")
            return None
    
    def approve_digital_access(self, approved_by_user):
        """Approve digital access for this member account"""
        if self.digital_access_status != 'REQUESTED':
            return False, "Digital access must be in REQUESTED status"
        
        self.digital_access_status = 'ACTIVE'
        self.access_approved_date = django_timezone.now()
        self.access_approved_by = approved_by_user
        self.save(update_fields=[
            'digital_access_status', 
            'access_approved_date', 
            'access_approved_by'
        ])
        
        logger.info(f"Digital access approved for member {self.member_number} by {approved_by_user.email}")
        return True, "Digital access approved successfully"
    
    def revoke_digital_access(self, reason=None):
        """Revoke digital access for this member account"""
        old_status = self.digital_access_status
        self.digital_access_status = 'REVOKED'
        self.status_changed_reason = reason or "Digital access revoked"
        self.save(update_fields=['digital_access_status', 'status_changed_reason'])
        
        logger.info(f"Digital access revoked for member {self.member_number}. Previous status: {old_status}")
        return True, "Digital access revoked successfully"
    
    @property
    def has_active_digital_access(self):
        """Check if member account has active digital access"""
        return (
            self.digital_access_status == 'ACTIVE' and 
            self.user.is_active and 
            self.is_active and 
            self.status == 'ACTIVE'
        )
    
    def clean(self):
        """Validate member account"""
        super().clean()
        errors = {}
        
        # Validate member number
        if self.sacco and self.member_number:
            existing = MemberAccount.objects.filter(
                sacco=self.sacco,
                member_number=self.member_number
            ).exclude(pk=self.pk)
            
            if existing.exists():
                errors['member_number'] = _('Member number must be unique within SACCO')
        
        if errors:
            raise ValidationError(errors)


# =============================================================================
# STREAMLINED USER PROFILE MODEL
# =============================================================================

class UserProfile(models.Model):
    """
    STREAMLINED: Essential profile information for system users.
    Focuses on employment and professional details only.
    """
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        related_name='profile'
    )
    
    # Employment details
    employee_id = models.CharField(
        _('Employee ID'),
        max_length=20, 
        unique=True, 
        null=True, 
        blank=True,
        help_text=_('Unique employee identifier')
    )
    
    date_of_appointment = models.DateField(
        _('Date of Appointment'),
        null=True, 
        blank=True,
        help_text=_('Date when employee was hired')
    )
    
    department = models.CharField(
        _('Department'),
        max_length=100, 
        blank=True, 
        null=True,
        help_text=_('Department or division')
    )
    
    position = models.CharField(
        _('Position'),
        max_length=100, 
        blank=True, 
        null=True,
        help_text=_('Job position or title')
    )
    
    # SACCO-specific fields
    branch = models.CharField(
        _('Branch'),
        max_length=100, 
        blank=True, 
        null=True,
        help_text=_('SACCO branch where user is based')
    )
    
    workstation = models.CharField(
        _('Workstation'),
        max_length=50, 
        blank=True, 
        null=True,
        help_text=_('Physical workstation or desk assignment')
    )          
                
    cash_limit = models.DecimalField(
        _('Cash Handling Limit'),
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text=_('Maximum cash amount user can handle per transaction')
    )
    
    daily_transaction_limit = models.DecimalField(
        _('Daily Transaction Limit'),
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text=_('Maximum total transactions user can process per day')
    )
    
    # Professional details
    qualifications = models.TextField(
        _('Qualifications'),
        blank=True,
        null=True,
        help_text=_('Educational and professional qualifications')
    )
    
    certifications = models.TextField(
        _('Certifications'),
        blank=True,
        null=True,
        help_text=_('Professional certifications and licenses')
    )
    
    specialization = models.CharField(
        _('Specialization'),
        max_length=200, 
        blank=True, 
        null=True,
        help_text=_('Area of expertise or specialization')
    )
    
    years_of_experience = models.PositiveIntegerField(
        _('Years of Experience'),
        null=True, 
        blank=True,
        help_text=_('Total years of relevant work experience')
    )
    
    # Employment type and compensation
    EMPLOYMENT_TYPE_CHOICES = [
        ('FULL_TIME', _('Full Time')),
        ('PART_TIME', _('Part Time')),
        ('CONTRACT', _('Contract')),
        ('CONSULTANT', _('Consultant')),
        ('INTERN', _('Intern')),
        ('VOLUNTEER', _('Volunteer')),
    ]
    employment_type = models.CharField(
        _('Employment Type'),
        max_length=50, 
        choices=EMPLOYMENT_TYPE_CHOICES, 
        default='FULL_TIME'
    )
    
    salary = models.DecimalField(
        _('Monthly Salary'),
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text=_('Monthly salary amount')
    )
    
    # Emergency contact details
    emergency_contact_name = models.CharField(
        _('Emergency Contact Name'),
        max_length=100, 
        blank=True, 
        null=True
    )
    
    emergency_contact_relationship = models.CharField(
        _('Emergency Contact Relationship'),
        max_length=50, 
        blank=True, 
        null=True
    )
    
    emergency_contact_phone = models.CharField(
        _('Emergency Contact Phone'),
        max_length=15, 
        blank=True, 
        null=True
    )
    
    emergency_contact_email = models.EmailField(
        _('Emergency Contact Email'),
        blank=True, 
        null=True
    )
    
    # Work schedule and access
    work_schedule = models.JSONField(
        _('Work Schedule'),
        default=dict, 
        blank=True,
        help_text=_('Weekly work schedule as JSON (e.g., {"monday": "9:00-17:00"})')
    )
    
    ACCESS_LEVEL_CHOICES = [
        ('BASIC', _('Basic Access')),
        ('INTERMEDIATE', _('Intermediate Access')),
        ('ADVANCED', _('Advanced Access')),
        ('FULL', _('Full Access')),
    ]
    access_level = models.CharField(
        _('Access Level'),
        max_length=20, 
        choices=ACCESS_LEVEL_CHOICES, 
        default='BASIC',
        help_text=_('System access level for this user')
    )
    
    # Performance tracking
    PERFORMANCE_RATING_CHOICES = [
        ('EXCELLENT', _('Excellent')),
        ('GOOD', _('Good')),
        ('SATISFACTORY', _('Satisfactory')),
        ('NEEDS_IMPROVEMENT', _('Needs Improvement')),
        ('UNSATISFACTORY', _('Unsatisfactory')),
    ]
    performance_rating = models.CharField(
        _('Performance Rating'),
        max_length=20, 
        choices=PERFORMANCE_RATING_CHOICES, 
        blank=True, 
        null=True,
        help_text=_('Latest performance rating')
    )
    
    last_performance_review = models.DateField(
        _('Last Performance Review'),
        null=True, 
        blank=True,
        help_text=_('Date of last performance review')
    )
    
    next_performance_review = models.DateField(
        _('Next Performance Review'),
        null=True, 
        blank=True,
        help_text=_('Scheduled date for next performance review')
    )
    
    # Additional information
    bio = models.TextField(
        _('Biography'),
        blank=True, 
        null=True, 
        help_text=_('Professional biography or summary')
    )
    
    notes = models.TextField(
        _('Internal Notes'),
        blank=True, 
        null=True, 
        help_text=_('Internal notes about the user (not visible to user)')
    )
    
    # Skills and competencies
    technical_skills = models.JSONField(
        _('Technical Skills'),
        default=list,
        blank=True,
        help_text=_('List of technical skills and competencies')
    )
    
    languages = models.JSONField(
        _('Languages'),
        default=list,
        blank=True,
        help_text=_('Languages spoken and proficiency levels')
    )
    
    # Training and development
    training_completed = models.JSONField(
        _('Training Completed'),
        default=list,
        blank=True,
        help_text=_('List of completed training programs')
    )
    
    training_required = models.JSONField(
        _('Training Required'),
        default=list,
        blank=True,
        help_text=_('List of required/planned training')
    )
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_profiles'
        verbose_name = _('User Profile')
        verbose_name_plural = _('User Profiles')
        indexes = [
            models.Index(fields=['employee_id']),
            models.Index(fields=['branch']),
            models.Index(fields=['department']),
            models.Index(fields=['employment_type']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - Profile"
    
    def get_employment_status(self):
        """Get formatted employment status"""
        if self.employment_type:
            return self.get_employment_type_display()
        return _("Not specified")
    
    def get_full_position(self):
        """Get full position including department"""
        parts = []
        if self.position:
            parts.append(self.position)
        if self.department:
            parts.append(f"({self.department})")
        return ' '.join(parts) if parts else _("Not specified")
    
    def is_due_for_review(self):
        """Check if user is due for performance review"""
        if not self.next_performance_review:
            return False
        return date.today() >= self.next_performance_review

    def days_until_review(self):
        """Get days until next performance review"""
        if not self.next_performance_review:
            return None
        delta = self.next_performance_review - date.today()
        return delta.days if delta.days > 0 else 0
    
    def has_required_training(self):
        """Check if user has completed all required training"""
        return len(self.training_required) == 0
    
    def get_training_completion_rate(self):
        """Get percentage of required training completed"""
        if not self.training_required:
            return 100.0
        
        completed_count = len(self.training_completed)
        required_count = len(self.training_required)
        total_training = completed_count + required_count
        
        if total_training == 0:
            return 100.0
        
        return (completed_count / total_training) * 100.0
    
    def generate_employee_id(self):
        """Generate unique employee ID if not set"""
        if self.employee_id:
            return self.employee_id
            
        import random
        import string
        
        # Get prefix from user's SACCO or default
        prefix = 'EMP'
        if self.user.sacco:
            prefix = self.user.sacco.code or self.user.sacco.name[:3].upper()
        
        # Generate unique ID
        while True:
            suffix = ''.join(random.choices(string.digits, k=4))
            employee_id = f"{prefix}{suffix}"
            
            if not UserProfile.objects.filter(employee_id=employee_id).exists():
                self.employee_id = employee_id
                self.save(update_fields=['employee_id'])
                return employee_id
    
    def clean(self):
        """Validate user profile"""
        super().clean()
        errors = {}
        
        # Validate cash limits
        if self.cash_limit and self.daily_transaction_limit:
            if self.cash_limit > self.daily_transaction_limit:
                errors['daily_transaction_limit'] = _('Daily limit must be greater than single transaction limit')
        
        # Validate review dates
        if self.last_performance_review and self.next_performance_review:
            if self.next_performance_review <= self.last_performance_review:
                errors['next_performance_review'] = _('Next review date must be after last review date')
        
        if errors:
            raise ValidationError(errors)


# =============================================================================
# USER SESSION TRACKING (STREAMLINED)
# =============================================================================

class UserSession(models.Model):
    """
    STREAMLINED: Session tracking for security and audit purposes.
    Focused on essential security information only.
    """
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='sessions'
    )
    
    session_key = models.CharField(
        _('Session Key'),
        max_length=40, 
        unique=True
    )
    
    ip_address = models.GenericIPAddressField(_('IP Address'))
    user_agent = models.TextField(_('User Agent'), blank=True, null=True)
    
    # Location information (optional)
    country = models.CharField(_('Country'), max_length=100, blank=True, null=True)
    city = models.CharField(_('City'), max_length=100, blank=True, null=True)
    
    # Device information
    DEVICE_TYPE_CHOICES = [
        ('DESKTOP', _('Desktop')),
        ('MOBILE', _('Mobile')),
        ('TABLET', _('Tablet')),
        ('UNKNOWN', _('Unknown')),
    ]
    
    device_type = models.CharField(
        _('Device Type'),
        max_length=20,
        choices=DEVICE_TYPE_CHOICES,
        default='UNKNOWN'
    )
    
    browser = models.CharField(_('Browser'), max_length=100, blank=True, null=True)
    operating_system = models.CharField(_('Operating System'), max_length=100, blank=True, null=True)
    
    # Session details
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    last_activity = models.DateTimeField(_('Last Activity'), auto_now=True)
    is_active = models.BooleanField(_('Is Active'), default=True)
    
    # Security tracking
    LOGIN_METHOD_CHOICES = [
        ('PASSWORD', _('Password')),
        ('TWO_FACTOR', _('Two Factor Auth')),
        ('SSO', _('Single Sign On')),
        ('API_KEY', _('API Key')),
    ]
    
    login_method = models.CharField(
        _('Login Method'),
        max_length=20,
        choices=LOGIN_METHOD_CHOICES,
        default='PASSWORD'
    )
    
    is_suspicious = models.BooleanField(
        _('Is Suspicious'),
        default=False,
        help_text=_('Flagged as suspicious activity')
    )
    
    risk_score = models.PositiveIntegerField(
        _('Risk Score'),
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text=_('Risk score from 0-100 based on login patterns')
    )
    
    # Session termination
    LOGOUT_REASON_CHOICES = [
        ('USER_LOGOUT', _('User Logout')),
        ('TIMEOUT', _('Session Timeout')),
        ('SECURITY', _('Security Logout')),
        ('ADMIN', _('Admin Logout')),
        ('SYSTEM', _('System Logout')),
        ('CONCURRENT_LOGIN', _('Concurrent Login Limit')),
    ]
    
    logout_reason = models.CharField(
        _('Logout Reason'),
        max_length=50,
        choices=LOGOUT_REASON_CHOICES,
        blank=True,
        null=True
    )
    
    logout_time = models.DateTimeField(_('Logout Time'), blank=True, null=True)
    
    # Activity tracking
    page_views = models.PositiveIntegerField(_('Page Views'), default=0)
    actions_performed = models.PositiveIntegerField(_('Actions Performed'), default=0)
    
    class Meta:
        db_table = 'user_sessions'
        verbose_name = _('User Session')
        verbose_name_plural = _('User Sessions')
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key']),
            models.Index(fields=['created_at']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['is_suspicious']),
            models.Index(fields=['last_activity']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.ip_address} ({self.created_at})"
    
    def terminate_session(self, reason='ADMIN'):
        """Terminate this session"""
        self.is_active = False
        self.logout_reason = reason
        self.logout_time = django_timezone.now()
        self.save(update_fields=['is_active', 'logout_reason', 'logout_time'])
        
        logger.info(f"Session terminated for {self.user.email} from {self.ip_address}. Reason: {reason}")
    
    def calculate_session_duration(self):
        """Calculate session duration in minutes"""
        end_time = self.logout_time or django_timezone.now()
        duration = end_time - self.created_at
        return int(duration.total_seconds() / 60)
    
    def update_activity(self, action_type='page_view'):
        """Update session activity"""
        self.last_activity = django_timezone.now()
        
        if action_type == 'page_view':
            self.page_views += 1
        elif action_type == 'action':
            self.actions_performed += 1
            
        self.save(update_fields=['last_activity', 'page_views', 'actions_performed'])
    
    def is_expired(self, timeout_minutes=60):
        """Check if session is expired based on inactivity"""
        if not self.is_active:
            return True
            
        from datetime import timedelta
        timeout_threshold = django_timezone.now() - timedelta(minutes=timeout_minutes)
        return self.last_activity < timeout_threshold
    
    def flag_as_suspicious(self, reason=None):
        """Flag session as suspicious"""
        self.is_suspicious = True
        self.risk_score = min(100, self.risk_score + 25)
        self.save(update_fields=['is_suspicious', 'risk_score'])
        
        logger.warning(f"Session flagged as suspicious for {self.user.email}: {reason}")


# =============================================================================
# USER LOGIN HISTORY (STREAMLINED)
# =============================================================================

class UserLoginHistory(models.Model):
    """
    STREAMLINED: Track all login attempts for security auditing.
    Focused on essential security information.
    """
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='login_history',
        null=True,  # Allow null for failed login attempts where user might not exist
        blank=True
    )
    
    email_attempted = models.EmailField(
        _('Email Attempted'),
        help_text=_('Email address used in login attempt')
    )
    
    LOGIN_STATUS_CHOICES = [
        ('SUCCESS', _('Successful')),
        ('FAILED_PASSWORD', _('Failed - Wrong Password')),
        ('FAILED_USER', _('Failed - User Not Found')),
        ('FAILED_INACTIVE', _('Failed - Account Inactive')),
        ('FAILED_LOCKED', _('Failed - Account Locked')),
        ('FAILED_2FA', _('Failed - Two Factor Authentication')),
        ('BLOCKED_IP', _('Blocked - Suspicious IP')),
        ('BLOCKED_RATE', _('Blocked - Rate Limited')),
    ]
    
    status = models.CharField(
        _('Login Status'),
        max_length=20,
        choices=LOGIN_STATUS_CHOICES
    )
    
    # Location and device info
    ip_address = models.GenericIPAddressField(_('IP Address'))
    user_agent = models.TextField(_('User Agent'), blank=True, null=True)
    country = models.CharField(_('Country'), max_length=100, blank=True, null=True)
    city = models.CharField(_('City'), max_length=100, blank=True, null=True)
    device_type = models.CharField(_('Device Type'), max_length=20, blank=True, null=True)
    
    # Timing
    attempted_at = models.DateTimeField(_('Attempted At'), auto_now_add=True)
    
    # Additional security info
    risk_factors = models.JSONField(
        _('Risk Factors'),
        default=list,
        blank=True,
        help_text=_('List of risk factors identified during login attempt')
    )
    
    notes = models.TextField(
        _('Notes'),
        blank=True,
        null=True,
        help_text=_('Additional notes about the login attempt')
    )
    
    class Meta:
        db_table = 'user_login_history'
        verbose_name = _('User Login History')
        verbose_name_plural = _('User Login Histories')
        indexes = [
            models.Index(fields=['user', 'attempted_at']),
            models.Index(fields=['email_attempted', 'attempted_at']),
            models.Index(fields=['ip_address', 'attempted_at']),
            models.Index(fields=['status']),
            models.Index(fields=['attempted_at']),
        ]
        ordering = ['-attempted_at']
    
    def __str__(self):
        return f"{self.email_attempted} - {self.get_status_display()} ({self.attempted_at})"
    
    @classmethod
    def log_attempt(cls, email, status, ip_address, user_agent=None, user=None, **kwargs):
        """Log a login attempt"""
        return cls.objects.create(
            user=user,
            email_attempted=email,
            status=status,
            ip_address=ip_address,
            user_agent=user_agent or '',
            **kwargs
        )
    
    @classmethod
    def get_recent_failed_attempts(cls, email, minutes=15):
        """Get recent failed login attempts for an email"""
        from datetime import timedelta
        cutoff_time = django_timezone.now() - timedelta(minutes=minutes)
        
        return cls.objects.filter(
            email_attempted=email,
            attempted_at__gte=cutoff_time,
            status__startswith='FAILED'
        ).count()
    
    @classmethod
    def get_suspicious_ips(cls, hours=24):
        """Get IPs with multiple failed attempts in recent hours"""
        from datetime import timedelta
        from django.db.models import Count
        
        cutoff_time = django_timezone.now() - timedelta(hours=hours)
        
        return cls.objects.filter(
            attempted_at__gte=cutoff_time,
            status__startswith='FAILED'
        ).values('ip_address').annotate(
            failed_count=Count('id')
        ).filter(failed_count__gte=5).order_by('-failed_count')
    
    def is_successful(self):
        """Check if this login attempt was successful"""
        return self.status == 'SUCCESS'
    
    def is_failed(self):
        """Check if this login attempt failed"""
        return self.status.startswith('FAILED')
    
    def is_blocked(self):
        """Check if this login attempt was blocked"""
        return self.status.startswith('BLOCKED')


# =============================================================================
# USER ACTIVITY LOG (STREAMLINED)
# =============================================================================

class UserActivityLog(models.Model):
    """
    STREAMLINED: Activity logging for audit purposes.
    Focused on essential business operations.
    """
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='activity_logs'
    )
    
    ACTION_CATEGORIES = [
        ('AUTH', _('Authentication')),
        ('MEMBER', _('Member Management')),
        ('LOAN', _('Loan Management')),
        ('TRANSACTION', _('Transaction')),
        ('REPORT', _('Report Generation')),
        ('SYSTEM', _('System Administration')),
        ('PROFILE', _('Profile Management')),
        ('SETTINGS', _('Settings Change')),
        ('EXPORT', _('Data Export')),
        ('IMPORT', _('Data Import')),
        ('DELETE', _('Data Deletion')),
        ('SECURITY', _('Security Event')),
    ]
    
    category = models.CharField(
        _('Action Category'),
        max_length=20,
        choices=ACTION_CATEGORIES
    )
    
    action = models.CharField(
        _('Action'),
        max_length=100,
        help_text=_('Specific action performed')
    )
    
    description = models.TextField(
        _('Description'),
        help_text=_('Detailed description of the action')
    )
    
    # Context information
    target_object_type = models.CharField(
        _('Target Object Type'),
        max_length=50,
        blank=True,
        null=True,
        help_text=_('Type of object affected (e.g., Member, Loan)')
    )
    
    target_object_id = models.CharField(
        _('Target Object ID'),
        max_length=100,
        blank=True,
        null=True,
        help_text=_('ID of the affected object')
    )
    
    # Changes made (for audit trail)
    changes = models.JSONField(
        _('Changes'),
        default=dict,
        blank=True,
        help_text=_('Before and after values for changes made')
    )
    
    # Technical details
    ip_address = models.GenericIPAddressField(_('IP Address'), blank=True, null=True)
    user_agent = models.TextField(_('User Agent'), blank=True, null=True)
    session_key = models.CharField(_('Session Key'), max_length=40, blank=True, null=True)
    
    # Status and results
    STATUS_CHOICES = [
        ('SUCCESS', _('Success')),
        ('PARTIAL', _('Partial Success')),
        ('FAILED', _('Failed')),
        ('ERROR', _('Error')),
    ]
    
    status = models.CharField(
        _('Status'),
        max_length=10,
        choices=STATUS_CHOICES,
        default='SUCCESS'
    )
    
    error_message = models.TextField(
        _('Error Message'),
        blank=True,
        null=True,
        help_text=_('Error message if action failed')
    )
    
    # Timing
    timestamp = models.DateTimeField(_('Timestamp'), auto_now_add=True)
    duration_ms = models.PositiveIntegerField(
        _('Duration (ms)'),
        null=True,
        blank=True,
        help_text=_('Action duration in milliseconds')
    )
    
    class Meta:
        db_table = 'user_activity_logs'
        verbose_name = _('User Activity Log')
        verbose_name_plural = _('User Activity Logs')
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['category', 'timestamp']),
            models.Index(fields=['target_object_type', 'target_object_id']),
            models.Index(fields=['status']),
            models.Index(fields=['timestamp']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.action} ({self.timestamp})"
    
    @classmethod
    def log_activity(cls, user, category, action, description, **kwargs):
        """Convenience method to log user activity"""
        return cls.objects.create(
            user=user,
            category=category,
            action=action,
            description=description,
            **kwargs
        )
    
    @classmethod
    def log_member_action(cls, user, action, member, description, **kwargs):
        """Log member-related actions"""
        return cls.log_activity(
            user=user,
            category='MEMBER',
            action=action,
            description=description,
            target_object_type='Member',
            target_object_id=str(member.member_number) if member else None,
            **kwargs
        )
    
    @classmethod
    def log_transaction_action(cls, user, action, transaction, description, **kwargs):
        """Log transaction-related actions"""
        return cls.log_activity(
            user=user,
            category='TRANSACTION',
            action=action,
            description=description,
            target_object_type='Transaction',
            target_object_id=str(transaction.id) if transaction else None,
            **kwargs
        )
    
    @classmethod
    def log_security_event(cls, user, action, description, **kwargs):
        """Log security-related events"""
        return cls.log_activity(
            user=user,
            category='SECURITY',
            action=action,
            description=description,
            **kwargs
        )
    
    def get_formatted_changes(self):
        """Get formatted string of changes made"""
        if not self.changes:
            return _("No changes recorded")
        
        formatted = []
        for field, change_info in self.changes.items():
            if isinstance(change_info, dict) and 'old' in change_info and 'new' in change_info:
                formatted.append(f"{field}: {change_info['old']} → {change_info['new']}")
            else:
                formatted.append(f"{field}: {change_info}")
        
        return "; ".join(formatted)
    
    def is_successful(self):
        """Check if the action was successful"""
        return self.status in ['SUCCESS', 'PARTIAL']
    
    def is_failed(self):
        """Check if the action failed"""
        return self.status in ['FAILED', 'ERROR']


# =============================================================================
# CONVENIENCE FUNCTIONS AND UTILITIES
# =============================================================================

def create_user_with_preferences(email, password=None, **user_fields):
    """
    Convenience function to create a user with default preferences.
    
    Usage:
        user = create_user_with_preferences(
            email='john@example.com',
            password='password123',
            first_name='John',
            last_name='Doe',
            user_type='CUSTOMER_SERVICE'
        )
    """
    user = User.objects.create_user(email=email, password=password, **user_fields)
    
    # UserPreferences will be created automatically in User.save()
    # But we can customize preferences here if needed
    if hasattr(user, 'preferences'):
        prefs = user.preferences
        # Set any custom preferences based on user type
        if user.user_type in ['SUPER_ADMIN', 'ADMINISTRATOR', 'SACCO_ADMIN']:
            prefs.theme_color = 'app-theme-dark'
            prefs.dashboard_layout = 'compact'
            prefs.items_per_page = 50
            prefs.save()
    
    return user

def bulk_update_user_preferences(users, **preferences):
    """
    Bulk update preferences for multiple users.
    
    Usage:
        managers = User.objects.filter(user_type='MANAGER')
        bulk_update_user_preferences(
            managers,
            theme_color='app-theme-blue',
            email_frequency='DAILY'
        )
    """
    preference_objects = []
    
    for user in users:
        if hasattr(user, 'preferences'):
            prefs = user.preferences
            for key, value in preferences.items():
                if hasattr(prefs, key):
                    setattr(prefs, key, value)
            preference_objects.append(prefs)
    
    if preference_objects:
        UserPreferences.objects.bulk_update(
            preference_objects,
            list(preferences.keys())
        )

def get_users_by_permission(permission_method):
    """
    Get users who have a specific permission.
    
    Usage:
        loan_approvers = get_users_by_permission('can_approve_loans')
        admins = get_users_by_permission('can_manage_sacco_settings')
    """
    users = []
    for user in User.objects.filter(is_active=True):
        if hasattr(user, permission_method):
            method = getattr(user, permission_method)
            if callable(method) and method():
                users.append(user)
    return users

def get_user_dashboard_context(user):
    """
    Get complete context for user dashboard including preferences, permissions, etc.
    
    Usage:
        context = get_user_dashboard_context(request.user)
        return render(request, 'dashboard.html', context)
    """
    context = {
        'user': user,
        'preferences': getattr(user, 'preferences', None),
        'profile': getattr(user, 'profile', None),
        'permissions': user.get_sacco_permissions(),
        'accessible_saccos': user.get_accessible_saccos(),
        'member_accounts': user.member_accounts.filter(is_active=True),
        'subordinates_count': user.get_direct_subordinates().count(),
        'recent_activity': user.activity_logs.all()[:10],
        'active_sessions': user.sessions.filter(is_active=True).count(),
    }
    
    # Add theme context if preferences exist
    if context['preferences']:
        context['theme'] = context['preferences'].get_theme_css_classes()
        context['notifications_enabled'] = {
            'email': context['preferences'].email_notifications,
            'sms': context['preferences'].sms_notifications,
            'push': context['preferences'].push_notifications,
        }
    
    return context

def cleanup_inactive_sessions(days_old=7):
    """
    Clean up old inactive sessions.
    
    Usage:
        cleanup_inactive_sessions(days_old=7)  # Run this as a periodic task
    """
    from datetime import timedelta
    cutoff_date = django_timezone.now() - timedelta(days=days_old)
    
    # Mark old sessions as inactive
    old_sessions = UserSession.objects.filter(
        last_activity__lt=cutoff_date,
        is_active=True
    )
    
    count = old_sessions.count()
    old_sessions.update(
        is_active=False,
        logout_reason='TIMEOUT',
        logout_time=django_timezone.now()
    )
    
    logger.info(f"Cleaned up {count} inactive sessions older than {days_old} days")
    return count

def get_security_summary(user, days=30):
    """
    Get security summary for a user over the specified period.
    
    Usage:
        summary = get_security_summary(user, days=30)
    """
    from datetime import timedelta
    cutoff_date = django_timezone.now() - timedelta(days=days)
    
    login_history = user.login_history.filter(attempted_at__gte=cutoff_date)
    
    summary = {
        'total_logins': login_history.filter(status='SUCCESS').count(),
        'failed_logins': login_history.filter(status__startswith='FAILED').count(),
        'blocked_attempts': login_history.filter(status__startswith='BLOCKED').count(),
        'unique_ips': login_history.values('ip_address').distinct().count(),
        'suspicious_sessions': user.sessions.filter(
            created_at__gte=cutoff_date,
            is_suspicious=True
        ).count(),
        'password_changed': user.password_changed_at and user.password_changed_at >= cutoff_date.date(),
        'two_factor_enabled': user.two_factor_enabled,
        'account_locked': user.is_account_locked(),
    }
    
    return summary

# =============================================================================
# SIGNAL HANDLERS FOR AUTOMATIC MODEL CREATION
# =============================================================================

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_dependencies(sender, instance, created, **kwargs):
    """
    Automatically create UserPreferences and UserProfile when User is created.
    """
    if created:
        # Create UserPreferences with defaults based on user type
        preferences_defaults = {}
        
        # Customize defaults based on user type
        if instance.user_type in ['SUPER_ADMIN', 'ADMINISTRATOR', 'SACCO_ADMIN']:
            preferences_defaults.update({
                'theme_color': 'app-theme-dark',
                'dashboard_layout': 'compact',
                'items_per_page': 50,
                'email_frequency': 'IMMEDIATE',
            })
        elif instance.user_type in ['MANAGER', 'ASSISTANT_MANAGER']:
            preferences_defaults.update({
                'theme_color': 'app-theme-blue',
                'dashboard_layout': 'grid',
                'items_per_page': 25,
                'email_frequency': 'HOURLY',
            })
        
        UserPreferences.objects.create(user=instance, **preferences_defaults)
        
        # Create UserProfile
        UserProfile.objects.create(user=instance)
        
        logger.info(f"Created preferences and profile for user: {instance.email}")

@receiver(post_save, sender=UserPreferences)
def log_preference_changes(sender, instance, created, **kwargs):
    """
    Log when user preferences are changed for audit purposes.
    """
    if not created:  # Only log updates, not creation
        UserActivityLog.log_activity(
            user=instance.user,
            category='PROFILE',
            action='UPDATE_PREFERENCES',
            description=f"Updated user preferences",
            target_object_type='UserPreferences',
            target_object_id=str(instance.id),
        )