# accounts/models.py

from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField
from django.core.validators import RegexValidator, MaxValueValidator, MinValueValidator
from datetime import date
import logging
from zoneinfo import available_timezones

# Import DefaultDatabaseModel from utils
from utils.models import DefaultDatabaseModel

logger = logging.getLogger(__name__)


# =============================================================================
# SACCO MODEL
# =============================================================================

class Sacco(DefaultDatabaseModel):
    """SACCO Model to represent different SACCOs in the system"""
    
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
    
    MEMBERSHIP_TYPE_CHOICES = (
        ('OPEN', 'Open Membership'),
        ('RESTRICTED', 'Restricted Membership'),
        ('CLOSED', 'Closed Membership'),
    )
    
    COMMON_BOND_CHOICES = (
        ('GEOGRAPHICAL', 'Geographical Area'),
        ('OCCUPATIONAL', 'Same Occupation'),
        ('ASSOCIATIONAL', 'Same Association'),
        ('MIXED', 'Mixed Common Bond'),
    )

    SUBSCRIPTION_PLANS = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
        ('multi_year', 'Multi-Year'),
        ('lifetime', 'Lifetime'),
    ]
    
    # Basic information
    full_name = models.CharField(max_length=191, unique=True)
    short_name = models.CharField(max_length=50, blank=True, null=True)
    abbreviation = models.CharField(max_length=20, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    # Email domain and database
    domain = models.CharField(
        max_length=191, 
        unique=True,
        help_text="Email domain e.g. mysacco.org"
    )
    database_alias = models.CharField(
        max_length=50, 
        unique=True, 
        help_text="Database key e.g. mysacco_db"
    )
    
    # SACCO classification
    sacco_type = models.CharField(max_length=30, choices=SACCO_TYPE_CHOICES)
    membership_type = models.CharField(max_length=15, choices=MEMBERSHIP_TYPE_CHOICES, default='OPEN')
    common_bond = models.CharField(max_length=15, choices=COMMON_BOND_CHOICES, default='GEOGRAPHICAL')
    
    # Contact details
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state_province = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    country = CountryField(blank_label='(select country)', default='UG')
    contact_phone = models.CharField(max_length=15)
    alternative_contact = models.CharField(max_length=15, null=True, blank=True)
    
    # System configuration
    timezone = models.CharField(
        max_length=50,
        choices=[(tz, tz) for tz in sorted(available_timezones())],
        default='UTC'
    )
    
    # Digital presence
    website = models.URLField(blank=True, null=True)
    facebook_page = models.URLField(blank=True, null=True)
    twitter_handle = models.CharField(max_length=50, blank=True, null=True)
    instagram_handle = models.CharField(max_length=50, blank=True, null=True)
    
    # Visual branding
    sacco_logo = models.ImageField(
        upload_to='sacco_logos/', 
        null=True, 
        blank=True,
        help_text="SACCO logo (recommended: 512x512px PNG with transparent background)"
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
        help_text="Brand colors as JSON: {'primary': '#hex', 'secondary': '#hex', 'accent': '#hex'}"
    )
    
    # Administrative details
    established_date = models.DateField()
    registration_number = models.CharField(max_length=50, blank=True, null=True)
    license_number = models.CharField(max_length=50, blank=True, null=True)
    operating_hours = models.CharField(max_length=100, help_text="e.g., Mon-Fri 8:00-17:00")
    
    # Subscription fields
    subscription_plan = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_PLANS,
        default='monthly'
    )
    subscription_start = models.DateField(null=True, blank=True)
    subscription_end = models.DateField(null=True, blank=True)
    is_active_subscription = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'saccos'
        verbose_name = "SACCO"
        verbose_name_plural = "SACCOs"
        ordering = ['full_name']
    
    def __str__(self):
        return self.full_name
    
    @property
    def active_users_count(self):
        """Get count of active users in this SACCO"""
        return UserProfile.objects.filter(sacco=self, user__is_active=True).count()
    
    def get_currency(self):
        """Get this SACCO's currency from FinancialSettings"""
        try:
            from core.models import FinancialSettings
            from kojenasacco.managers import set_current_db
            
            with set_current_db(self.database_alias):
                settings = FinancialSettings.get_settings()
                return settings.sacco_currency.code if settings else 'UGX'
        except Exception as e:
            logger.warning(f"Could not get currency for SACCO {self.full_name}: {e}")
            return 'UGX'
    
    def get_financial_settings(self):
        """Get this SACCO's financial settings"""
        try:
            from core.models import FinancialSettings
            from kojenasacco.managers import set_current_db
            
            with set_current_db(self.database_alias):
                return FinancialSettings.get_settings()
        except Exception as e:
            logger.warning(f"Could not get financial settings for SACCO {self.full_name}: {e}")
            return None


# =============================================================================
# USER PROFILE MODEL
# =============================================================================

class UserProfile(DefaultDatabaseModel):
    """Extended profile information for users"""
    
    USER_ROLES = [
        ('SUPER_ADMIN', 'Super Administrator'),
        ('SACCO_ADMIN', 'SACCO Administrator'),
        ('MANAGER', 'Manager'),
        ('LOAN_OFFICER', 'Loan Officer'),
        ('ACCOUNTANT', 'Accountant'),
        ('CUSTOMER_SERVICE', 'Customer Service'),
        ('TELLER', 'Teller'),
    ]
    
    EMPLOYMENT_TYPE_CHOICES = [
        ('FULL_TIME', 'Full Time'),
        ('PART_TIME', 'Part Time'),
        ('CONTRACT', 'Contract'),
    ]
    
    GENDER_CHOICES = (
        ('MALE', 'Male'),
        ('FEMALE', 'Female'),
        ('OTHER', 'Other'),
        ('PREFER_NOT_TO_SAY', 'Prefer not to say'),
    )
    
    LANGUAGE_CHOICES = (
        ('en', 'English'),
        ('fr', 'French'),
        ('es', 'Spanish'),
        ('sw', 'Swahili'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    sacco = models.ForeignKey(
        Sacco,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='staff_profiles'
    )
    role = models.CharField(max_length=30, choices=USER_ROLES)
    
    # Profile information
    photo = models.ImageField(
        upload_to='user_photos/',
        null=True,
        blank=True
    )
    mobile = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$')]
    )
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, null=True, blank=True)
    
    # Location
    address = models.TextField(null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    country = CountryField(blank_label='(select country)', default='UG')
    
    # Localization
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='en')
    timezone = models.CharField(
        max_length=50,
        choices=[(tz, tz) for tz in sorted(available_timezones())],
        default='UTC'
    )
    
    # Employment details
    employee_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    position = models.CharField(max_length=100, blank=True, null=True)
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, default='FULL_TIME')
    date_of_appointment = models.DateField(null=True, blank=True)
    qualification = models.CharField(max_length=200, blank=True, null=True)
    
    # Reporting structure
    reports_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subordinates'
    )
    
    # Emergency contact
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=15, blank=True, null=True)
    
    # Theme preferences
    theme_color = models.CharField(
        max_length=50,
        choices=[
            ('app-theme-white', 'White Theme'),
            ('app-theme-gray', 'Gray Theme'),
        ],
        default='app-theme-white'
    )
    fixed_header = models.BooleanField(default=False)
    fixed_sidebar = models.BooleanField(default=False)
    fixed_footer = models.BooleanField(default=False)
    
    header_class = models.CharField(max_length=100, blank=True, default='')
    sidebar_class = models.CharField(max_length=100, blank=True, default='')
    page_tabs_style = models.CharField(
        max_length=50,
        choices=[
            ('body-tabs-shadow', 'Shadow Style'),
            ('body-tabs-line', 'Line Style'),
        ],
        default='body-tabs-shadow'
    )
    
    # Security fields
    password_changed_at = models.DateTimeField(null=True, blank=True)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    account_locked_until = models.DateTimeField(null=True, blank=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    two_factor_enabled = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"{self.user.username} - {self.role}"
    
    @property
    def sacco_name(self):
        """Get SACCO name"""
        return self.sacco.full_name if self.sacco else None
    
    def get_sacco_users(self):
        """Get all users in the same SACCO"""
        if self.sacco:
            return User.objects.filter(profile__sacco=self.sacco, is_active=True)
        return User.objects.none()
    
    # Permission helper methods
    def is_admin_user(self):
        return self.role in ['SUPER_ADMIN', 'SACCO_ADMIN'] or self.user.is_superuser
    
    def can_approve_loans(self):
        return self.role in ['SUPER_ADMIN', 'SACCO_ADMIN', 'MANAGER', 'LOAN_OFFICER'] or self.user.is_superuser
    
    def can_manage_finances(self):
        return self.role in ['SUPER_ADMIN', 'SACCO_ADMIN', 'ACCOUNTANT'] or self.user.is_superuser
    
    def can_manage_members(self):
        return self.role in ['SUPER_ADMIN', 'SACCO_ADMIN', 'MANAGER', 'CUSTOMER_SERVICE'] or self.user.is_superuser


# =============================================================================
# MEMBER ACCOUNT MODEL
# =============================================================================

class MemberAccount(DefaultDatabaseModel):
    """Links system users to SACCO member profiles"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspended'),
        ('TERMINATED', 'Terminated'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='member_accounts')
    sacco = models.ForeignKey(Sacco, on_delete=models.CASCADE, related_name='member_accounts')
    
    member_number = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    membership_date = models.DateField(default=date.today)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'member_accounts'
        unique_together = ('sacco', 'member_number')
        verbose_name = 'Member Account'
        verbose_name_plural = 'Member Accounts'
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.member_number}"
    
    def get_member_profile(self):
        """Get member profile from SACCO database"""
        try:
            from members.models import Member
            return Member.objects.using(self.sacco.database_alias).filter(
                member_number=self.member_number
            ).first()
        except Exception as e:
            logger.warning(f"Could not fetch member profile: {e}")
            return None


# =============================================================================
# USER MANAGEMENT SETTINGS
# =============================================================================

class UserManagementSettings(DefaultDatabaseModel):
    """Configuration model for user management system"""
    
    # Password Policy
    min_password_length = models.PositiveIntegerField(
        default=8,
        validators=[MinValueValidator(6), MaxValueValidator(128)]
    )
    require_uppercase = models.BooleanField(default=True)
    require_lowercase = models.BooleanField(default=True)
    require_numbers = models.BooleanField(default=True)
    require_special_chars = models.BooleanField(default=True)
    
    password_expiry_days = models.PositiveIntegerField(
        default=90,
        validators=[MinValueValidator(30), MaxValueValidator(365)]
    )
    password_history_count = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(24)]
    )
    
    # Session Management
    default_session_timeout_minutes = models.PositiveIntegerField(
        default=480,
        validators=[MinValueValidator(15), MaxValueValidator(1440)]
    )
    max_concurrent_sessions = models.PositiveIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    session_warning_minutes = models.PositiveIntegerField(
        default=15,
        validators=[MinValueValidator(5), MaxValueValidator(60)]
    )
    
    # Account Security
    max_failed_login_attempts = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(3), MaxValueValidator(20)]
    )
    account_lockout_duration_minutes = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(5), MaxValueValidator(1440)]
    )
    enable_two_factor_default = models.BooleanField(default=False)
    force_password_change_on_first_login = models.BooleanField(default=True)
    
    # User Registration
    allow_user_registration = models.BooleanField(default=False)
    require_admin_approval = models.BooleanField(default=True)
    
    # Notifications
    send_welcome_emails = models.BooleanField(default=True)
    send_password_expiry_warnings = models.BooleanField(default=True)
    password_expiry_warning_days = models.PositiveIntegerField(
        default=7,
        validators=[MinValueValidator(1), MaxValueValidator(30)]
    )
    
    # Audit & Logging
    log_login_attempts = models.BooleanField(default=True)
    log_permission_changes = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'user_management_settings'
        verbose_name = 'User Management Settings'
        verbose_name_plural = 'User Management Settings'
    
    def __str__(self):
        return "User Management Settings"