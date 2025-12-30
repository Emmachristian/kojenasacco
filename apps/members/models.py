# members/models.py

from django.db import models
from django_countries.fields import CountryField
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from utils.models import BaseModel
from decimal import Decimal
from django.db.models import Q
import logging

# Import central utilities
from core.utils import get_base_currency, format_money, get_active_fiscal_period

logger = logging.getLogger(__name__)


# =============================================================================
# CORE MEMBER MODEL
# =============================================================================

class Member(BaseModel):
    """
    Streamlined member model for SACCO-specific databases.
    This is the single source of truth for core member data within each SACCO.
    Additional contact details, payment methods, and next of kin are in separate models.
    """
    
    # =============================================================================
    # MEMBER CATEGORIES AND CHOICES
    # =============================================================================
    
    MEMBER_CATEGORY_CHOICES = (
        ('REGULAR', 'Regular Member'),
        ('PREMIUM', 'Premium Member'),
        ('SENIOR', 'Senior Member'),
        ('YOUTH', 'Youth Member'),
        ('BUSINESS', 'Business Member'),
        ('VIP', 'VIP Member'),
        ('STUDENT', 'Student Member'),
        ('PENSIONER', 'Pensioner Member'),
    )
    
    MEMBERSHIP_PLAN_CHOICES = (
        ('BASIC', 'Basic Plan'),
        ('STANDARD', 'Standard Plan'),
        ('PREMIUM', 'Premium Plan'),
        ('CORPORATE', 'Corporate Plan'),
        ('ENTERPRISE', 'Enterprise Plan'),
        ('FAMILY', 'Family Plan'),
        ('STUDENT', 'Student Plan'),
    )
    
    STATUS_CHOICES = (
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('ACTIVE', 'Active'),
        ('DORMANT', 'Dormant'),
        ('SUSPENDED', 'Suspended'),
        ('ON_HOLD', 'On Hold'),
        ('BLACKLISTED', 'Blacklisted'),
        ('DECEASED', 'Deceased'),
        ('WITHDRAWN', 'Withdrawn'),
        ('GRADUATED', 'Graduated to Higher Tier'),
        ('DELINQUENT', 'Delinquent'),
        ('TERMINATED', 'Terminated'),
    )
    
    RISK_RATING_CHOICES = (
        ('VERY_LOW', 'Very Low Risk'),
        ('LOW', 'Low Risk'),
        ('MEDIUM', 'Medium Risk'),
        ('HIGH', 'High Risk'),
        ('VERY_HIGH', 'Very High Risk'),
        ('UNKNOWN', 'Unknown'),
    )
    
    EMPLOYMENT_STATUS_CHOICES = (
        ('EMPLOYED', 'Employed'),
        ('SELF_EMPLOYED', 'Self-Employed'),
        ('UNEMPLOYED', 'Unemployed'),
        ('STUDENT', 'Student'),
        ('RETIRED', 'Retired'),
        ('HOUSEWIFE', 'Housewife/Househusband'),
        ('CASUAL_WORKER', 'Casual Worker'),
    )
    
    GENDER_CHOICES = (
        ('MALE', 'Male'),
        ('FEMALE', 'Female'),
    )
    
    MARITAL_STATUS_CHOICES = (
        ('SINGLE', 'Single'),
        ('MARRIED', 'Married'),
        ('DIVORCED', 'Divorced'),
        ('WIDOWED', 'Widowed'),
        ('SEPARATED', 'Separated'),
        ('COHABITING', 'Cohabiting'),
    )

    RELIGIOUS_AFFILIATION_CHOICES = (
        ('catholic', 'Catholic'),
        ('protestant', 'Protestant'),
        ('anglican', 'Anglican'),
        ('baptist', 'Baptist'),
        ('pentecostal', 'Pentecostal'),
        ('evangelical', 'Evangelical'),
        ('adventist', 'Adventist'),
        ('islam', 'Islam'),
        ('hindu', 'Hindu'),
        ('buddhist', 'Buddhist'),
        ('jewish', 'Jewish'),
        ('traditional', 'Traditional'),
        ('none', 'No Religion'),
        ('other', 'Other'),
    )
    
    KYC_STATUS_CHOICES = (
        ('PENDING', 'Pending Verification'),
        ('IN_PROGRESS', 'In Progress'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired'),
        ('REQUIRES_UPDATE', 'Requires Update'),
    )
    
    # =============================================================================
    # CORE IDENTIFICATION
    # =============================================================================
    
    member_number = models.CharField(
        max_length=20, 
        unique=True,
        help_text="Unique member number within this SACCO"
    )
    
    id_number = models.CharField(
        max_length=30, 
        unique=True,
        help_text="National ID, passport, or other government ID number"
    )
    
    id_type = models.CharField(
        max_length=20,
        choices=[
            ('NATIONAL_ID', 'National ID'),
            ('PASSPORT', 'Passport'),
            ('DRIVERS_LICENSE', 'Driver\'s License'),
            ('VOTER_ID', 'Voter ID'),
            ('OTHER', 'Other'),
        ],
        default='NATIONAL_ID'
    )
    
    # =============================================================================
    # PERSONAL INFORMATION (OFFICIAL/LEGAL DATA)
    # =============================================================================
    
    title = models.CharField(
        max_length=10,
        choices=[
            ('MR', 'Mr.'),
            ('MRS', 'Mrs.'),
            ('MS', 'Ms.'),
            ('DR', 'Dr.'),
            ('PROF', 'Prof.'),
            ('HON', 'Hon.'),
        ],
        blank=True,
        null=True
    )
    
    first_name = models.CharField(
        max_length=100,
        help_text="Legal first name as per ID document"
    )
    
    last_name = models.CharField(
        max_length=100,
        help_text="Legal last name as per ID document"
    )
    
    middle_name = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Legal middle name as per ID document"
    )
    
    date_of_birth = models.DateField(help_text="Date of birth as per ID document")
    place_of_birth = models.CharField(max_length=100, blank=True, null=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES)
    marital_status = models.CharField(max_length=15, choices=MARITAL_STATUS_CHOICES)
    nationality = CountryField(blank_label='(select nationality)', default='UG')
    religious_affiliation = models.CharField("Religious Affiliation", max_length=20, choices=RELIGIOUS_AFFILIATION_CHOICES, blank=True)
    
    # =============================================================================
    # MEMBERSHIP INFORMATION
    # =============================================================================
    
    member_category = models.CharField(
        max_length=20, 
        choices=MEMBER_CATEGORY_CHOICES, 
        default='REGULAR'
    )
    
    membership_plan = models.CharField(
        max_length=20, 
        choices=MEMBERSHIP_PLAN_CHOICES, 
        default='BASIC'
    )
    
    membership_date = models.DateField(
        help_text="Date when member joined the SACCO"
    )
    
    membership_application_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when membership application was submitted"
    )
    
    membership_approved_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when membership was approved"
    )
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='PENDING_APPROVAL'
    )
    
    status_changed_date = models.DateTimeField(auto_now_add=True)
    status_changed_reason = models.TextField(blank=True, null=True)
    
    # Membership benefits and limits
    maximum_loan_multiplier = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('3.0'),
        validators=[MinValueValidator(0), MaxValueValidator(20)],
        help_text="Maximum loan as multiple of savings balance"
    )
    
    loan_interest_discount = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.0'),
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text="Interest rate discount percentage for this member"
    )
    
    special_privileges = models.JSONField(
        default=list,
        blank=True,
        help_text="Special privileges or benefits for this member"
    )
    
    # =============================================================================
    # EMPLOYMENT AND FINANCIAL INFORMATION
    # =============================================================================
    
    occupation = models.CharField(max_length=100, blank=True, null=True)
    employer = models.CharField(max_length=200, blank=True, null=True)
    employer_address = models.TextField(blank=True, null=True)
    employment_status = models.CharField(max_length=20, choices=EMPLOYMENT_STATUS_CHOICES)
    
    monthly_income = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Estimated monthly income"
    )
    
    income_source = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Primary source of income"
    )
    
    other_income_sources = models.TextField(
        blank=True, 
        null=True,
        help_text="Other sources of income"
    )
    
    # =============================================================================
    # PRIMARY CONTACT INFORMATION
    # =============================================================================
    
    personal_email = models.EmailField(
        blank=True, 
        null=True,
        help_text="Primary email for official correspondence"
    )
    
    phone_primary = models.CharField(
        max_length=20,
        help_text="Primary phone number for official contact"
    )
    
    # =============================================================================
    # PRIMARY ADDRESS INFORMATION
    # =============================================================================
    
    physical_address = models.TextField(
        help_text="Current residential address for official records"
    )
    
    postal_address = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Postal address for correspondence"
    )
    
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state_province = models.CharField(max_length=100, blank=True, null=True)
    country = CountryField(blank_label='(select country)', default='UG')
    
    # =============================================================================
    # TAX AND COMPLIANCE INFORMATION
    # =============================================================================
    
    tax_id = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        help_text="Tax identification number"
    )
    
    tax_exemption_status = models.BooleanField(
        default=False,
        help_text="Whether member is exempt from taxes"
    )
    
    tax_exemption_reason = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Reason for tax exemption"
    )
    
    # KYC (Know Your Customer) compliance
    kyc_status = models.CharField(
        max_length=20,
        choices=KYC_STATUS_CHOICES,
        default='PENDING'
    )
    
    kyc_verified_date = models.DateTimeField(blank=True, null=True)
    kyc_expiry_date = models.DateTimeField(blank=True, null=True)
    kyc_documents_uploaded = models.BooleanField(default=False)
    kyc_notes = models.TextField(blank=True, null=True)

    # =============================================================================
    # RISK AND CREDIT INFORMATION
    # =============================================================================
    
    credit_score = models.IntegerField(
        default=500, 
        validators=[MinValueValidator(0), MaxValueValidator(1000)],
        help_text="Credit score range: 0-1000"
    )
    
    risk_rating = models.CharField(
        max_length=20, 
        choices=RISK_RATING_CHOICES, 
        default='UNKNOWN'
    )
    
    risk_assessment_date = models.DateTimeField(blank=True, null=True)
    risk_assessment_notes = models.TextField(blank=True, null=True)
    
    # =============================================================================
    # DOCUMENT MANAGEMENT
    # =============================================================================
    
    member_photo = models.ImageField(
        upload_to='members/photos', 
        blank=True, 
        null=True,
        help_text="Member's photograph"
    )
    
    # =============================================================================
    # PROPERTIES (INCLUDING MONETARY FORMATTING)
    # =============================================================================
    
    @property
    def currency(self):
        """Get currency from SACCO configuration"""
        return get_base_currency()
    
    @property
    def formatted_monthly_income(self):
        """Get formatted monthly income"""
        return format_money(self.monthly_income) if self.monthly_income else None
    
    @property
    def annual_income(self):
        """Calculate annual income from monthly income"""
        return self.monthly_income * 12 if self.monthly_income else None
    
    @property
    def formatted_annual_income(self):
        """Get formatted annual income"""
        return format_money(self.annual_income) if self.annual_income else None
    
    @property
    def age(self):
        """Calculate member's current age"""
        from datetime import date
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )
    
    @property
    def membership_duration_days(self):
        """Calculate membership duration in days"""
        return (timezone.now().date() - self.membership_date).days
    
    @property
    def membership_duration_years(self):
        """Calculate membership duration in years"""
        return self.membership_duration_days / 365.25
    
    @property
    def display_name(self):
        """Return display name for UI"""
        if self.title:
            return f"{self.title} {self.first_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_active(self):
        """Check if member has active status"""
        return self.status == 'ACTIVE'
    
    @property
    def is_kyc_verified(self):
        """Check if KYC is verified"""
        return self.kyc_status == 'VERIFIED'
    
    @property
    def kyc_needs_update(self):
        """Check if KYC needs update"""
        if self.kyc_expiry_date:
            return self.kyc_expiry_date < timezone.now()
        return False
    
    # =============================================================================
    # FINANCIAL AGGREGATION METHODS (WITH FORMATTING)
    # =============================================================================
    
    def get_total_savings(self):
        """Get total savings across all savings accounts"""
        try:
            total = self.savings_accounts.filter(
                status__in=['ACTIVE', 'DORMANT']
            ).aggregate(
                total=models.Sum('current_balance')
            )['total']
            return Decimal(total or 0)
        except Exception as e:
            logger.error(f"Error calculating total savings for member {self.member_number}: {e}")
            return Decimal('0.00')
    
    @property
    def formatted_total_savings(self):
        """Get formatted total savings"""
        return format_money(self.get_total_savings())
    
    def get_total_loans(self):
        """Get total outstanding loan amount"""
        try:
            total = self.loans.filter(
                status='ACTIVE'
            ).aggregate(
                total=models.Sum('outstanding_total')
            )['total']
            return Decimal(total or 0)
        except Exception as e:
            logger.error(f"Error calculating total loans for member {self.member_number}: {e}")
            return Decimal('0.00')
    
    @property
    def formatted_total_loans(self):
        """Get formatted total loans"""
        return format_money(self.get_total_loans())
    
    def get_active_loans_count(self):
        """Get count of active loans"""
        return self.loans.filter(status='ACTIVE').count()
    
    def get_total_shares(self):
        """Get total share capital value"""
        # This would integrate with a shares model if you have one
        # For now, return 0
        return Decimal('0.00')
    
    @property
    def formatted_total_shares(self):
        """Get formatted total share capital"""
        return format_money(self.get_total_shares())
    
    def get_total_dividends(self):
        """Get total dividends earned"""
        try:
            total = self.dividends.filter(
                status='PAID'
            ).aggregate(
                total=models.Sum('net_dividend')
            )['total']
            return Decimal(total or 0)
        except Exception as e:
            logger.error(f"Error calculating total dividends for member {self.member_number}: {e}")
            return Decimal('0.00')
    
    @property
    def formatted_total_dividends(self):
        """Get formatted total dividends"""
        return format_money(self.get_total_dividends())
    
    # =============================================================================
    # INSTANCE HELPER METHODS
    # =============================================================================
    
    def get_full_name(self):
        """Return full legal name of the member"""
        parts = []
        if self.title:
            parts.append(self.title)
        parts.append(self.first_name)
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.last_name)
        return ' '.join(parts)
    
    def get_primary_payment_method(self):
        """Get the primary payment method"""
        return self.payment_methods.filter(is_primary=True).first()
    
    def get_primary_next_of_kin(self):
        """Get the primary next of kin"""
        return self.next_of_kin.filter(is_primary=True).first()
    
    def get_emergency_contact(self):
        """Get the emergency contact (next of kin marked as emergency)"""
        return self.next_of_kin.filter(is_emergency_contact=True).first()
    
    def can_apply_for_loan(self, loan_product):
        """Check if member can apply for a specific loan product"""
        if self.status != 'ACTIVE':
            return False, "Member must be active to apply for loans"
        
        # Check if member meets minimum savings requirement
        if loan_product.minimum_savings_percentage > 0:
            required_savings = (loan_product.min_amount * loan_product.minimum_savings_percentage) / Decimal('100.0')
            if self.get_total_savings() < required_savings:
                return False, f"Insufficient savings. Required: {format_money(required_savings)}"
        
        # Check if member has required shares
        if hasattr(loan_product, 'minimum_shares_required') and loan_product.minimum_shares_required > 0:
            total_shares = self.get_total_shares()
            if total_shares < loan_product.minimum_shares_required:
                return False, f"Insufficient shares. Required: {format_money(loan_product.minimum_shares_required)}"
        
        # Check maximum active loans
        active_loans = self.get_active_loans_count()
        if hasattr(loan_product, 'maximum_loans_per_member'):
            if active_loans >= loan_product.maximum_loans_per_member:
                return False, f"Maximum active loans reached ({loan_product.maximum_loans_per_member})"
        
        return True, "Eligible for loan"
    
    def update_credit_score(self):
        """Recalculate and update credit score based on member data"""
        base_score = 500
        
        # Age-based scoring
        if self.age >= 25 and self.age <= 55:
            base_score += 50
        elif self.age >= 18 and self.age < 25:
            base_score += 30
        
        # Employment status
        if self.employment_status == 'EMPLOYED':
            base_score += 75
        elif self.employment_status == 'SELF_EMPLOYED':
            base_score += 50
        elif self.employment_status == 'RETIRED':
            base_score += 40
        
        # Income level
        if self.monthly_income:
            if self.monthly_income >= 1000000:  # 1M UGX
                base_score += 100
            elif self.monthly_income >= 500000:
                base_score += 75
            elif self.monthly_income >= 200000:
                base_score += 50
        
        # Membership duration
        years = self.membership_duration_years
        if years >= 5:
            base_score += 75
        elif years >= 2:
            base_score += 50
        elif years >= 1:
            base_score += 25
        
        # KYC verification
        if self.kyc_status == 'VERIFIED':
            base_score += 50
        
        self.credit_score = min(1000, max(0, base_score))
        self.save(update_fields=['credit_score'])
    
    def update_risk_rating(self):
        """Update risk rating based on credit score"""
        if self.credit_score >= 800:
            self.risk_rating = 'VERY_LOW'
        elif self.credit_score >= 650:
            self.risk_rating = 'LOW'
        elif self.credit_score >= 500:
            self.risk_rating = 'MEDIUM'
        elif self.credit_score >= 350:
            self.risk_rating = 'HIGH'
        else:
            self.risk_rating = 'VERY_HIGH'
        
        self.risk_assessment_date = timezone.now()
        self.save(update_fields=['risk_rating', 'risk_assessment_date'])
    
    def activate(self):
        """Activate the member"""
        self.status = 'ACTIVE'
        self.status_changed_date = timezone.now()
        self.status_changed_reason = "Member activated"
        self.save(update_fields=['status', 'status_changed_date', 'status_changed_reason'])
    
    def suspend(self, reason):
        """Suspend the member"""
        self.status = 'SUSPENDED'
        self.status_changed_date = timezone.now()
        self.status_changed_reason = reason
        self.save(update_fields=['status', 'status_changed_date', 'status_changed_reason'])
    
    # =============================================================================
    # CLASS METHODS
    # =============================================================================
    
    @classmethod
    def get_active_members(cls):
        """Get all active members"""
        return cls.objects.filter(status='ACTIVE')
    
    @classmethod
    def get_pending_approval(cls):
        """Get members pending approval"""
        return cls.objects.filter(status='PENDING_APPROVAL')
    
    @classmethod
    def get_by_category(cls, category):
        """Get members by category"""
        return cls.objects.filter(member_category=category)
    
    @classmethod
    def get_high_risk_members(cls):
        """Get high-risk members"""
        return cls.objects.filter(risk_rating__in=['HIGH', 'VERY_HIGH'])
    
    # =============================================================================
    # VALIDATION AND SAVE METHODS
    # =============================================================================
    
    def clean(self):
        """Validate the member data"""
        super().clean()
        errors = {}
        
        # Age validation
        if self.date_of_birth:
            if self.age < 0:
                errors['date_of_birth'] = "Date of birth cannot be in the future"
            elif self.age > 120:
                errors['date_of_birth'] = "Invalid date of birth"
            elif self.age < 16:
                errors['date_of_birth'] = "Member must be at least 16 years old"
        
        # Membership date validation
        if self.membership_date and self.date_of_birth:
            membership_age = (self.membership_date - self.date_of_birth).days / 365.25
            if membership_age < 16:
                errors['membership_date'] = "Member must be at least 16 years old when joining"
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Enhanced save with automatic calculations"""
        # Set basic defaults for new members
        if not self.pk:
            # New member - set initial credit score
            if self.credit_score == 500:  # Default value
                base_score = 500
                
                # Simple scoring based on member data only
                if self.age >= 25 and self.age <= 55:
                    base_score += 50
                
                if self.employment_status == 'EMPLOYED':
                    base_score += 75
                elif self.employment_status == 'SELF_EMPLOYED':
                    base_score += 50
                
                if self.monthly_income:
                    if self.monthly_income >= 1000000:  # 1M UGX
                        base_score += 100
                    elif self.monthly_income >= 500000:
                        base_score += 75
                    elif self.monthly_income >= 200000:
                        base_score += 50
                
                self.credit_score = min(1000, max(0, base_score))
        
        # Validate before saving, but exclude member_number if it's not set yet
        # (the pre_save signal will generate it)
        if not self.member_number:
            self.full_clean(exclude=['member_number'])
        else:
            self.full_clean()
        
        # Call parent save
        super().save(*args, **kwargs)
    
    # =============================================================================
    # STRING REPRESENTATION
    # =============================================================================
    
    def __str__(self):
        return f"{self.get_full_name()} - {self.member_number}"
    
    # =============================================================================
    # META CLASS
    # =============================================================================
    
    class Meta:
        db_table = 'members'
        verbose_name = 'Member'
        verbose_name_plural = 'Members'
        ordering = ['-created_at']
        
        indexes = [
            models.Index(fields=['member_number']),
            models.Index(fields=['id_number']),
            models.Index(fields=['status']),
            models.Index(fields=['member_category']),
            models.Index(fields=['membership_date']),
            models.Index(fields=['kyc_status']),
            models.Index(fields=['risk_rating']),
            models.Index(fields=['created_at']),
            models.Index(fields=['first_name', 'last_name']),
            models.Index(fields=['phone_primary']),
            models.Index(fields=['personal_email']),
        ]
        
        constraints = [
            models.CheckConstraint(
                check=Q(credit_score__gte=0, credit_score__lte=1000),
                name='valid_credit_score'
            ),
            models.CheckConstraint(
                check=Q(maximum_loan_multiplier__gte=0, maximum_loan_multiplier__lte=20),
                name='valid_loan_multiplier'
            ),
        ]


# =============================================================================
# MEMBER PAYMENT METHOD MODEL
# =============================================================================

class MemberPaymentMethod(BaseModel):
    """
    Payment methods for members (bank accounts, mobile money, etc.)
    Replaces the multiple hardcoded bank and mobile money fields
    """
    
    METHOD_TYPE_CHOICES = (
        ('BANK_ACCOUNT', 'Bank Account'),
        ('MOBILE_MONEY', 'Mobile Money'),
        ('CASH', 'Cash'),
        ('CHEQUE', 'Cheque'),
    )
    
    MOBILE_MONEY_PROVIDERS = (
        ('MTN', 'MTN Mobile Money'),
        ('AIRTEL', 'Airtel Money'),
        ('AFRICELL', 'Africell Money'),
        ('UTL', 'UTL Mobile Money'),
        ('OTHER', 'Other Provider'),
    )
    
    BANK_ACCOUNT_TYPES = (
        ('SAVINGS', 'Savings Account'),
        ('CHECKING', 'Checking Account'),
        ('CURRENT', 'Current Account'),
        ('FIXED_DEPOSIT', 'Fixed Deposit'),
    )
    
    # -------------------------------------------------------------------------
    # RELATIONSHIPS
    # -------------------------------------------------------------------------
    
    member = models.ForeignKey(
        Member, 
        on_delete=models.CASCADE, 
        related_name='payment_methods',
        verbose_name="Member"
    )
    
    # -------------------------------------------------------------------------
    # PAYMENT METHOD DETAILS
    # -------------------------------------------------------------------------
    
    method_type = models.CharField(
        "Method Type",
        max_length=20, 
        choices=METHOD_TYPE_CHOICES
    )
    
    provider = models.CharField(
        "Provider/Bank Name",
        max_length=100,
        help_text="Bank name or mobile money provider"
    )
    
    account_number = models.CharField(
        "Account/Phone Number",
        max_length=50,
        help_text="Account number or mobile money number"
    )
    
    account_name = models.CharField(
        "Account Name",
        max_length=100,
        help_text="Name as registered on account"
    )
    
    account_type = models.CharField(
        "Account Type",
        max_length=20,
        choices=BANK_ACCOUNT_TYPES,
        blank=True,
        null=True,
        help_text="For bank accounts only"
    )
    
    branch = models.CharField(
        "Branch/Location",
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Bank branch or mobile money agent location"
    )
    
    # -------------------------------------------------------------------------
    # STATUS AND VERIFICATION
    # -------------------------------------------------------------------------
    
    is_primary = models.BooleanField(
        "Primary Method",
        default=False,
        help_text="Primary payment method for this member"
    )
    
    is_verified = models.BooleanField(
        "Verified",
        default=False,
        help_text="Whether this payment method has been verified"
    )
    
    verified_date = models.DateTimeField(
        "Verification Date",
        blank=True, 
        null=True
    )
    
    is_active = models.BooleanField(
        "Active",
        default=True,
        help_text="Whether this payment method is currently active"
    )
    
    # -------------------------------------------------------------------------
    # ADDITIONAL METADATA
    # -------------------------------------------------------------------------
    
    notes = models.TextField("Notes", blank=True, null=True)
    
    # -------------------------------------------------------------------------
    # PROPERTIES
    # -------------------------------------------------------------------------
    
    @property
    def masked_account_number(self):
        """Return masked account number for display"""
        if len(self.account_number) > 4:
            return f"****{self.account_number[-4:]}"
        return "****"
    
    # -------------------------------------------------------------------------
    # INSTANCE METHODS
    # -------------------------------------------------------------------------
    
    def verify(self):
        """Mark payment method as verified"""
        self.is_verified = True
        self.verified_date = timezone.now()
        self.save(update_fields=['is_verified', 'verified_date'])
    
    def make_primary(self):
        """Make this the primary payment method"""
        # Remove primary status from other methods
        MemberPaymentMethod.objects.filter(
            member=self.member,
            is_primary=True
        ).exclude(pk=self.pk).update(is_primary=False)
        
        self.is_primary = True
        self.save(update_fields=['is_primary'])
    
    # -------------------------------------------------------------------------
    # VALIDATION AND SAVE
    # -------------------------------------------------------------------------
    
    def clean(self):
        """Validate payment method data"""
        super().clean()
        errors = {}
        
        # Validate account type for bank accounts
        if self.method_type == 'BANK_ACCOUNT' and not self.account_type:
            errors['account_type'] = "Account type is required for bank accounts"
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Enhanced save with primary handling"""
        self.full_clean()
        
        # If setting as primary, unset other primary methods
        if self.is_primary:
            MemberPaymentMethod.objects.filter(
                member=self.member,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        
        super().save(*args, **kwargs)
    
    # -------------------------------------------------------------------------
    # STRING REPRESENTATION
    # -------------------------------------------------------------------------
    
    def __str__(self):
        return f"{self.member.get_full_name()} - {self.get_method_type_display()} ({self.provider})"
    
    # -------------------------------------------------------------------------
    # META CLASS
    # -------------------------------------------------------------------------
    
    class Meta:
        db_table = 'member_payment_methods'
        verbose_name = 'Payment Method'
        verbose_name_plural = 'Payment Methods'
        ordering = ['-is_primary', '-is_verified', 'provider']
        
        indexes = [
            models.Index(fields=['member', 'is_primary']),
            models.Index(fields=['member', 'method_type']),
            models.Index(fields=['is_verified']),
            models.Index(fields=['is_active']),
        ]
        
        constraints = [
            models.UniqueConstraint(
                fields=['member', 'method_type', 'account_number'],
                name='unique_member_payment_method'
            )
        ]


# =============================================================================
# NEXT OF KIN MODEL
# =============================================================================

class NextOfKin(BaseModel):
    """
    Next of kin for members with priority and beneficiary information
    Replaces all hardcoded next of kin fields
    """
    
    RELATION_CHOICES = (
        ('SPOUSE', 'Spouse'),
        ('FATHER', 'Father'),
        ('MOTHER', 'Mother'),
        ('SON', 'Son'),
        ('DAUGHTER', 'Daughter'),
        ('BROTHER', 'Brother'),
        ('SISTER', 'Sister'),
        ('UNCLE', 'Uncle'),
        ('AUNT', 'Aunt'),
        ('NEPHEW', 'Nephew'),
        ('NIECE', 'Niece'),
        ('GRANDPARENT', 'Grandparent'),
        ('GRANDCHILD', 'Grandchild'),
        ('COUSIN', 'Cousin'),
        ('GUARDIAN', 'Guardian'),
        ('FRIEND', 'Friend'),
        ('PARTNER', 'Partner'),
        ('IN_LAW', 'In-law'),
        ('COLLEAGUE', 'Colleague'),
        ('OTHER', 'Other'),
    )
    
    # -------------------------------------------------------------------------
    # RELATIONSHIPS
    # -------------------------------------------------------------------------
    
    member = models.ForeignKey(
        Member, 
        on_delete=models.CASCADE, 
        related_name='next_of_kin',
        verbose_name="Member"
    )
    
    # -------------------------------------------------------------------------
    # NEXT OF KIN DETAILS
    # -------------------------------------------------------------------------
    
    name = models.CharField(
        "Full Name",
        max_length=100,
        help_text="Full name of next of kin"
    )
    
    relation = models.CharField(
        "Relationship",
        max_length=50, 
        choices=RELATION_CHOICES,
        help_text="Relationship to member"
    )
    
    contact = models.CharField(
        "Phone Number",
        max_length=15,
        help_text="Primary phone number"
    )
    
    email = models.EmailField(
        "Email Address",
        blank=True, 
        null=True,
        help_text="Email address"
    )
    
    address = models.TextField(
        "Physical Address",
        blank=True, 
        null=True,
        help_text="Residential address"
    )
    
    id_number = models.CharField(
        "ID Number",
        max_length=30, 
        blank=True, 
        null=True,
        help_text="National ID or other identification number"
    )
    
    date_of_birth = models.DateField(
        "Date of Birth",
        null=True,
        blank=True,
        help_text="Date of birth"
    )
    
    # -------------------------------------------------------------------------
    # DESIGNATION FLAGS
    # -------------------------------------------------------------------------
    
    is_primary = models.BooleanField(
        "Primary Next of Kin",
        default=False,
        help_text="Primary next of kin"
    )
    
    is_emergency_contact = models.BooleanField(
        "Emergency Contact",
        default=False,
        help_text="Can be contacted in case of emergency"
    )
    
    is_beneficiary = models.BooleanField(
        "Beneficiary",
        default=False,
        help_text="Beneficiary of member's estate/benefits"
    )
    
    beneficiary_percentage = models.DecimalField(
        "Beneficiary Percentage",
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of benefits allocated to this next of kin"
    )
    
    # -------------------------------------------------------------------------
    # ADDITIONAL METADATA
    # -------------------------------------------------------------------------
    
    notes = models.TextField("Notes", blank=True, null=True)
    
    # -------------------------------------------------------------------------
    # PROPERTIES
    # -------------------------------------------------------------------------
    
    @property
    def age(self):
        """Calculate age if date of birth is provided"""
        if not self.date_of_birth:
            return None
        
        from datetime import date
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )
    
    @property
    def formatted_beneficiary_percentage(self):
        """Get formatted beneficiary percentage"""
        return f"{self.beneficiary_percentage}%"
    
    # -------------------------------------------------------------------------
    # INSTANCE METHODS
    # -------------------------------------------------------------------------
    
    def make_primary(self):
        """Make this the primary next of kin"""
        # Remove primary status from other next of kin
        NextOfKin.objects.filter(
            member=self.member,
            is_primary=True
        ).exclude(pk=self.pk).update(is_primary=False)
        
        self.is_primary = True
        self.save(update_fields=['is_primary'])
    
    # -------------------------------------------------------------------------
    # VALIDATION AND SAVE
    # -------------------------------------------------------------------------
    
    def clean(self):
        """Validate next of kin data"""
        super().clean()
        errors = {}
        
        # Validate beneficiary percentage
        if self.is_beneficiary and self.beneficiary_percentage <= 0:
            errors['beneficiary_percentage'] = "Beneficiary percentage must be greater than 0"
        
        # Validate total beneficiary percentage doesn't exceed 100%
        if self.is_beneficiary:
            total_percentage = NextOfKin.objects.filter(
                member=self.member,
                is_beneficiary=True
            ).exclude(pk=self.pk).aggregate(
                total=models.Sum('beneficiary_percentage')
            )['total'] or Decimal('0.00')
            
            if total_percentage + self.beneficiary_percentage > 100:
                errors['beneficiary_percentage'] = f"Total beneficiary allocation would exceed 100% (current: {total_percentage}%)"
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Enhanced save with primary handling"""
        self.full_clean()
        
        # If setting as primary, unset other primary next of kin
        if self.is_primary:
            NextOfKin.objects.filter(
                member=self.member,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        
        super().save(*args, **kwargs)
    
    # -------------------------------------------------------------------------
    # STRING REPRESENTATION
    # -------------------------------------------------------------------------
    
    def __str__(self):
        return f"{self.name} ({self.get_relation_display()}) - Next of Kin for {self.member.get_full_name()}"
    
    # -------------------------------------------------------------------------
    # META CLASS
    # -------------------------------------------------------------------------
    
    class Meta:
        db_table = 'member_next_of_kin'
        verbose_name = 'Next of Kin'
        verbose_name_plural = 'Next of Kin'
        ordering = ['-is_primary', '-is_emergency_contact', 'name']
        
        indexes = [
            models.Index(fields=['member', 'is_primary']),
            models.Index(fields=['member', 'is_emergency_contact']),
            models.Index(fields=['member', 'is_beneficiary']),
            models.Index(fields=['contact']),
        ]


# =============================================================================
# MEMBER ADDITIONAL CONTACT MODEL
# =============================================================================

class MemberAdditionalContact(BaseModel):
    """
    Additional contact methods for members (work email, secondary phone, etc.)
    Replaces multiple hardcoded email and phone fields
    """
    
    CONTACT_TYPE_CHOICES = (
        ('WORK_EMAIL', 'Work Email'),
        ('ALTERNATE_EMAIL', 'Alternate Email'),
        ('SECONDARY_PHONE', 'Secondary Phone'),
        ('WORK_PHONE', 'Work Phone'),
        ('FAX', 'Fax'),
        ('WHATSAPP', 'WhatsApp'),
        ('TELEGRAM', 'Telegram'),
    )
    
    # -------------------------------------------------------------------------
    # RELATIONSHIPS
    # -------------------------------------------------------------------------
    
    member = models.ForeignKey(
        Member, 
        on_delete=models.CASCADE, 
        related_name='additional_contacts',
        verbose_name="Member"
    )
    
    # -------------------------------------------------------------------------
    # CONTACT DETAILS
    # -------------------------------------------------------------------------
    
    contact_type = models.CharField(
        "Contact Type",
        max_length=20, 
        choices=CONTACT_TYPE_CHOICES
    )
    
    contact_value = models.CharField(
        "Contact Value",
        max_length=100,
        help_text="Email address or phone number"
    )
    
    # -------------------------------------------------------------------------
    # VERIFICATION AND STATUS
    # -------------------------------------------------------------------------
    
    is_verified = models.BooleanField(
        "Verified",
        default=False,
        help_text="Whether this contact has been verified"
    )
    
    verified_date = models.DateTimeField(
        "Verification Date",
        blank=True, 
        null=True
    )
    
    is_active = models.BooleanField(
        "Active",
        default=True
    )
    
    # -------------------------------------------------------------------------
    # ADDITIONAL METADATA
    # -------------------------------------------------------------------------
    
    notes = models.CharField(
        "Notes",
        max_length=200, 
        blank=True, 
        null=True
    )
    
    # -------------------------------------------------------------------------
    # INSTANCE METHODS
    # -------------------------------------------------------------------------
    
    def verify(self):
        """Mark contact as verified"""
        self.is_verified = True
        self.verified_date = timezone.now()
        self.save(update_fields=['is_verified', 'verified_date'])
    
    # -------------------------------------------------------------------------
    # VALIDATION
    # -------------------------------------------------------------------------
    
    def clean(self):
        """Validate contact data"""
        super().clean()
        errors = {}
        
        # Validate email format for email types
        if 'EMAIL' in self.contact_type:
            from django.core.validators import validate_email
            try:
                validate_email(self.contact_value)
            except ValidationError:
                errors['contact_value'] = "Invalid email address"
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Save with validation"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    # -------------------------------------------------------------------------
    # STRING REPRESENTATION
    # -------------------------------------------------------------------------
    
    def __str__(self):
        return f"{self.member.get_full_name()} - {self.get_contact_type_display()}: {self.contact_value}"
    
    # -------------------------------------------------------------------------
    # META CLASS
    # -------------------------------------------------------------------------
    
    class Meta:
        db_table = 'member_additional_contacts'
        verbose_name = 'Additional Contact'
        verbose_name_plural = 'Additional Contacts'
        ordering = ['contact_type']
        
        indexes = [
            models.Index(fields=['member', 'contact_type']),
            models.Index(fields=['is_verified']),
        ]
        
        constraints = [
            models.UniqueConstraint(
                fields=['member', 'contact_type', 'contact_value'],
                name='unique_member_contact'
            )
        ]


# =============================================================================
# MEMBER GROUP MODELS 
# =============================================================================

class MemberGroup(BaseModel):
    """Groups of members for specific purposes like lending circles, committees, etc."""
    
    GROUP_TYPE_CHOICES = (
        ('LENDING_CIRCLE', 'Lending Circle'),
        ('SAVINGS_GROUP', 'Savings Group'),
        ('COMMITTEE', 'Committee'),
        ('SPECIAL_INTEREST', 'Special Interest Group'),
        ('PROJECT_GROUP', 'Project Group'),
        ('INVESTMENT_CLUB', 'Investment Club'),
        ('TRAINING_GROUP', 'Training Group'),
        ('OTHER', 'Other'),
    )
    
    MEETING_FREQUENCY_CHOICES = (
        ('WEEKLY', 'Weekly'),
        ('BI_WEEKLY', 'Bi-weekly'),
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('AS_NEEDED', 'As Needed'),
    )
    
    DAY_CHOICES = (
        ('MONDAY', 'Monday'),
        ('TUESDAY', 'Tuesday'),
        ('WEDNESDAY', 'Wednesday'),
        ('THURSDAY', 'Thursday'),
        ('FRIDAY', 'Friday'),
        ('SATURDAY', 'Saturday'),
        ('SUNDAY', 'Sunday'),
    )
    
    # -------------------------------------------------------------------------
    # BASIC INFORMATION
    # -------------------------------------------------------------------------
    
    name = models.CharField("Group Name", max_length=100)
    description = models.TextField("Description")
    
    group_type = models.CharField(
        "Group Type",
        max_length=20,
        choices=GROUP_TYPE_CHOICES,
        default='LENDING_CIRCLE'
    )
    
    # -------------------------------------------------------------------------
    # LEADERSHIP
    # -------------------------------------------------------------------------
    
    group_leader = models.ForeignKey(
        Member, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='led_groups',
        verbose_name="Group Leader"
    )
    
    group_secretary = models.ForeignKey(
        Member, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='secretary_of_groups',
        verbose_name="Group Secretary"
    )
    
    group_treasurer = models.ForeignKey(
        Member, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='treasurer_of_groups',
        verbose_name="Group Treasurer"
    )
    
    # -------------------------------------------------------------------------
    # GROUP DETAILS
    # -------------------------------------------------------------------------
    
    formation_date = models.DateField("Formation Date")
    
    meeting_frequency = models.CharField(
        "Meeting Frequency",
        max_length=20,
        choices=MEETING_FREQUENCY_CHOICES,
        default='MONTHLY'
    )
    
    meeting_day = models.CharField(
        "Meeting Day",
        max_length=10,
        choices=DAY_CHOICES,
        blank=True,
        null=True
    )
    
    meeting_time = models.TimeField("Meeting Time", blank=True, null=True)
    meeting_location = models.CharField("Meeting Location", max_length=200, blank=True, null=True)
    
    # -------------------------------------------------------------------------
    # FINANCIAL PARAMETERS
    # -------------------------------------------------------------------------
    
    minimum_contribution = models.DecimalField(
        "Minimum Contribution",
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Minimum monthly contribution"
    )
    
    maximum_loan_amount = models.DecimalField(
        "Maximum Loan Amount",
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Maximum loan amount for group members"
    )
    
    interest_rate = models.DecimalField(
        "Interest Rate",
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Monthly interest rate percentage"
    )
    
    # -------------------------------------------------------------------------
    # GROUP RULES
    # -------------------------------------------------------------------------
    
    maximum_members = models.PositiveIntegerField(
        "Maximum Members",
        default=20,
        help_text="Maximum number of members allowed"
    )
    
    minimum_members = models.PositiveIntegerField(
        "Minimum Members",
        default=5,
        help_text="Minimum number of members required"
    )
    
    # -------------------------------------------------------------------------
    # STATUS
    # -------------------------------------------------------------------------
    
    is_active = models.BooleanField("Active", default=True)
    is_full = models.BooleanField("Full", default=False)
    
    # -------------------------------------------------------------------------
    # RELATIONSHIP TO MEMBERS
    # -------------------------------------------------------------------------
    
    members = models.ManyToManyField(
        Member, 
        through='GroupMembership', 
        related_name='member_groups'
    )
    
    # -------------------------------------------------------------------------
    # RULES AND REGULATIONS
    # -------------------------------------------------------------------------
    
    terms_and_conditions = models.TextField("Terms and Conditions", blank=True, null=True)
    group_rules = models.TextField("Group Rules", blank=True, null=True)
    
    # -------------------------------------------------------------------------
    # PROPERTIES (INCLUDING MONETARY FORMATTING)
    # -------------------------------------------------------------------------
    
    @property
    def currency(self):
        """Get currency from SACCO configuration"""
        return get_base_currency()
    
    @property
    def formatted_minimum_contribution(self):
        """Get formatted minimum contribution"""
        return format_money(self.minimum_contribution)
    
    @property
    def formatted_maximum_loan_amount(self):
        """Get formatted maximum loan amount"""
        return format_money(self.maximum_loan_amount)
    
    @property
    def member_count(self):
        """Get current number of active members"""
        return self.groupmembership_set.filter(is_active=True).count()
    
    @property
    def available_slots(self):
        """Get number of available slots"""
        return max(0, self.maximum_members - self.member_count)
    
    @property
    def group_age_days(self):
        """Get age of group in days"""
        return (timezone.now().date() - self.formation_date).days
    
    def get_total_group_savings(self):
        """Get total savings from all group members"""
        try:
            # Get all active members in this group
            member_ids = self.memberships.filter(is_active=True).values_list('member_id', flat=True)
            
            # Sum their savings
            from savings.models import SavingsAccount
            total = SavingsAccount.objects.filter(
                member_id__in=member_ids,
                status__in=['ACTIVE', 'DORMANT']
            ).aggregate(
                total=models.Sum('current_balance')
            )['total']
            
            return Decimal(total or 0)
        except Exception as e:
            logger.error(f"Error calculating group savings for {self.name}: {e}")
            return Decimal('0.00')
    
    @property
    def formatted_total_group_savings(self):
        """Get formatted total group savings"""
        return format_money(self.get_total_group_savings())
    
    # -------------------------------------------------------------------------
    # INSTANCE METHODS
    # -------------------------------------------------------------------------
    
    def can_add_member(self):
        """Check if group can accept new members"""
        return self.is_active and not self.is_full and self.member_count < self.maximum_members
    
    def update_full_status(self):
        """Update is_full status based on member count"""
        self.is_full = self.member_count >= self.maximum_members
        self.save(update_fields=['is_full'])
    
    def get_leadership_positions(self):
        """Get all leadership positions"""
        return {
            'leader': self.group_leader,
            'secretary': self.group_secretary,
            'treasurer': self.group_treasurer,
        }
    
    def get_active_members(self):
        """Get all active members"""
        return self.members.filter(
            groupmembership__is_active=True
        ).select_related('groupmembership')
    
    # -------------------------------------------------------------------------
    # STRING REPRESENTATION
    # -------------------------------------------------------------------------
    
    def __str__(self):
        return f"{self.name} ({self.get_group_type_display()})"
    
    # -------------------------------------------------------------------------
    # META CLASS
    # -------------------------------------------------------------------------
    
    class Meta:
        db_table = 'member_groups'
        verbose_name = 'Member Group'
        verbose_name_plural = 'Member Groups'
        ordering = ['-created_at']
        
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['group_type']),
            models.Index(fields=['is_active']),
            models.Index(fields=['formation_date']),
            models.Index(fields=['is_full']),
        ]


# =============================================================================
# GROUP MEMBERSHIP MODEL
# =============================================================================

class GroupMembership(BaseModel):
    """Relationship between members and groups with additional details"""
    
    ROLE_CHOICES = (
        ('MEMBER', 'Member'),
        ('LEADER', 'Leader'),
        ('SECRETARY', 'Secretary'),
        ('TREASURER', 'Treasurer'),
        ('COMMITTEE_MEMBER', 'Committee Member'),
        ('COORDINATOR', 'Coordinator'),
        ('MENTOR', 'Mentor'),
    )
    
    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspended'),
        ('RESIGNED', 'Resigned'),
        ('EXPELLED', 'Expelled'),
        ('ON_LEAVE', 'On Leave'),
    )
    
    # -------------------------------------------------------------------------
    # RELATIONSHIPS
    # -------------------------------------------------------------------------
    
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    group = models.ForeignKey(MemberGroup, on_delete=models.CASCADE)
    
    # -------------------------------------------------------------------------
    # MEMBERSHIP DETAILS
    # -------------------------------------------------------------------------
    
    role = models.CharField(
        "Role",
        max_length=20, 
        choices=ROLE_CHOICES, 
        default='MEMBER'
    )
    
    # -------------------------------------------------------------------------
    # MEMBERSHIP TIMELINE
    # -------------------------------------------------------------------------
    
    join_date = models.DateField("Join Date")
    exit_date = models.DateField("Exit Date", null=True, blank=True)
    
    # -------------------------------------------------------------------------
    # STATUS
    # -------------------------------------------------------------------------
    
    status = models.CharField(
        "Status",
        max_length=15,
        choices=STATUS_CHOICES,
        default='ACTIVE'
    )
    
    is_active = models.BooleanField("Active", default=True)
    
    # -------------------------------------------------------------------------
    # FINANCIAL COMMITMENTS
    # -------------------------------------------------------------------------
    
    monthly_contribution = models.DecimalField(
        "Monthly Contribution",
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Monthly contribution amount"
    )
    
    total_contributions = models.DecimalField(
        "Total Contributions",
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total amount contributed to this group"
    )
    
    # -------------------------------------------------------------------------
    # PERFORMANCE TRACKING
    # -------------------------------------------------------------------------
    
    meeting_attendance_rate = models.DecimalField(
        "Meeting Attendance Rate",
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of meetings attended"
    )
    
    last_meeting_attended = models.DateField("Last Meeting Attended", blank=True, null=True)
    
    # -------------------------------------------------------------------------
    # NOTES AND COMMENTS
    # -------------------------------------------------------------------------
    
    notes = models.TextField("Notes", blank=True, null=True)
    exit_reason = models.TextField("Exit Reason", blank=True, null=True)
    
    # -------------------------------------------------------------------------
    # PROPERTIES (INCLUDING MONETARY FORMATTING)
    # -------------------------------------------------------------------------
    
    @property
    def currency(self):
        """Get currency from SACCO configuration"""
        return get_base_currency()
    
    @property
    def formatted_monthly_contribution(self):
        """Get formatted monthly contribution"""
        return format_money(self.monthly_contribution)
    
    @property
    def formatted_total_contributions(self):
        """Get formatted total contributions"""
        return format_money(self.total_contributions)
    
    @property
    def membership_duration_days(self):
        """Calculate membership duration in days"""
        end_date = self.exit_date or timezone.now().date()
        return (end_date - self.join_date).days
    
    @property
    def membership_duration_months(self):
        """Calculate membership duration in months"""
        return self.membership_duration_days / 30.44
    
    # -------------------------------------------------------------------------
    # INSTANCE METHODS
    # -------------------------------------------------------------------------
    
    def calculate_attendance_rate(self):
        """Calculate meeting attendance rate"""
        # This would integrate with a meetings model if you have one
        return self.meeting_attendance_rate
    
    def leave_group(self, reason=None):
        """Mark member as having left the group"""
        self.is_active = False
        self.status = 'RESIGNED'
        self.exit_date = timezone.now().date()
        if reason:
            self.exit_reason = reason
        self.save()
        
        # Update group's full status
        self.group.update_full_status()
    
    def rejoin_group(self):
        """Rejoin the group (if allowed)"""
        if self.group.can_add_member():
            self.is_active = True
            self.status = 'ACTIVE'
            self.exit_date = None
            self.exit_reason = None
            self.save()
            
            # Update group's full status
            self.group.update_full_status()
            return True
        return False
    
    def suspend(self, reason=None):
        """Suspend membership"""
        self.status = 'SUSPENDED'
        if reason:
            self.notes = f"{self.notes or ''}\nSuspended: {reason}".strip()
        self.save()
    
    def reactivate(self):
        """Reactivate suspended membership"""
        if self.status == 'SUSPENDED':
            self.status = 'ACTIVE'
            self.save()
    
    # -------------------------------------------------------------------------
    # STRING REPRESENTATION
    # -------------------------------------------------------------------------
    
    def __str__(self):
        return f"{self.member.get_full_name()} - {self.group.name} ({self.get_role_display()})"
    
    # -------------------------------------------------------------------------
    # META CLASS
    # -------------------------------------------------------------------------
    
    class Meta:
        unique_together = ('member', 'group')
        db_table = 'member_group_memberships'
        verbose_name = 'Group Membership'
        verbose_name_plural = 'Group Memberships'
        ordering = ['-is_active', '-join_date']
        
        indexes = [
            models.Index(fields=['member', 'group']),
            models.Index(fields=['status']),
            models.Index(fields=['is_active']),
            models.Index(fields=['join_date']),
            models.Index(fields=['role']),
        ]