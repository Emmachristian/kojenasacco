# members/models.py

from django.db import models
from django.conf import settings
from django_countries.fields import CountryField
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from sacco_settings.models import BaseModel
from decimal import Decimal
import uuid
import os
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# CORE MEMBER MODEL
# =============================================================================

def member_photo_upload_path(instance, filename):
    """Enhanced upload path for member photos with privacy and organization"""
    ext = filename.split('.')[-1].lower()
    
    # Validate extension
    allowed_extensions = ['jpg', 'jpeg', 'png', 'webp']
    if ext not in allowed_extensions:
        ext = 'jpg'  # Default fallback
    
    # Create date-based directory structure
    now = timezone.now()
    year = now.year
    month = now.strftime('%m')
    
    # Generate secure filename using member number (not name for privacy)
    if instance.member_number:
        base_name = f"photo_{instance.member_number}"
    elif instance.pk:
        base_name = f"photo_id_{instance.pk}"
    else:
        base_name = f"photo_temp_{now.strftime('%Y%m%d_%H%M%S')}"
    
    # Add unique identifier to prevent conflicts
    unique_id = uuid.uuid4().hex[:8]
    filename = f"{base_name}_{unique_id}.{ext}"
    
    return os.path.join('member_photos', str(year), month, filename)


def member_id_document_upload_path(instance, filename):
    """Upload path for ID documents (front/back) with enhanced security"""
    ext = filename.split('.')[-1].lower()
    
    # Validate extension for ID documents
    allowed_extensions = ['jpg', 'jpeg', 'png', 'pdf']
    if ext not in allowed_extensions:
        ext = 'jpg'
    
    now = timezone.now()
    year = now.year
    month = now.strftime('%m')
    
    # Use member number for organization
    member_id = instance.member_number or f"temp_{instance.pk}"
    
    # Add timestamp and unique ID for security
    timestamp = now.strftime('%Y%m%d_%H%M%S')
    unique_id = uuid.uuid4().hex[:8]
    filename = f"id_{member_id}_{timestamp}_{unique_id}.{ext}"
    
    return os.path.join('member_documents', 'id_cards', str(year), month, filename)


def member_signature_upload_path(instance, filename):
    """Upload path for signature specimens"""
    ext = filename.split('.')[-1].lower()
    
    # Signature files should typically be images
    allowed_extensions = ['jpg', 'jpeg', 'png', 'svg']
    if ext not in allowed_extensions:
        ext = 'png'
    
    now = timezone.now()
    member_id = instance.member_number or f"temp_{instance.pk}"
    unique_id = uuid.uuid4().hex[:8]
    
    filename = f"signature_{member_id}_{unique_id}.{ext}"
    
    return os.path.join('member_signatures', str(now.year), filename)


def member_document_upload_path(document_type):
    """Factory function for different document types (proof of residence, income, etc.)"""
    def upload_path(instance, filename):
        ext = filename.split('.')[-1].lower()
        
        # Allow common document formats
        allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']
        if ext not in allowed_extensions:
            ext = 'pdf'  # Default for documents
        
        now = timezone.now()
        year = now.year
        month = now.strftime('%m')
        
        # Use member number for organization
        member_id = instance.member_number or f"temp_{instance.pk}"
        
        # Create filename with document type
        timestamp = now.strftime('%Y%m%d_%H%M%S')
        unique_id = uuid.uuid4().hex[:8]
        filename = f"{document_type}_{member_id}_{timestamp}_{unique_id}.{ext}"
        
        return os.path.join('member_documents', document_type, str(year), month, filename)
    
    return upload_path


def sacco_aware_upload_path(document_type):
    """Multi-tenant aware upload path for SACCO system"""
    def upload_path(instance, filename):
        from database_registry.routers import get_current_db
        
        ext = filename.split('.')[-1].lower()
        allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']
        if ext not in allowed_extensions:
            ext = 'pdf'
        
        # Get current SACCO database
        current_db = get_current_db()
        sacco_id = current_db if current_db != 'default' else 'main'
        
        now = timezone.now()
        member_id = instance.member_number or f"temp_{instance.pk}"
        unique_id = uuid.uuid4().hex[:8]
        
        filename = f"{member_id}_{unique_id}.{ext}"
        
        return os.path.join('sacco_files', sacco_id, 'members', document_type, 
                          str(now.year), str(now.month).zfill(2), filename)
    
    return upload_path


def kyc_document_upload_path(instance, filename):
    """Specialized path for KYC documents with compliance considerations"""
    ext = filename.split('.')[-1].lower()
    
    now = timezone.now()
    member_id = instance.member_number or f"temp_{instance.pk}"
    
    # KYC documents need extra security
    kyc_folder = f"kyc_{now.year}"
    unique_id = uuid.uuid4().hex
    filename = f"kyc_{member_id}_{unique_id}.{ext}"
    
    return os.path.join('member_documents', 'kyc', kyc_folder, 
                       str(now.month).zfill(2), filename)


def member_category_aware_upload_path(instance, filename):
    """Upload path that considers member category for organization"""
    ext = filename.split('.')[-1].lower()
    
    now = timezone.now()
    member_id = instance.member_number or f"temp_{instance.pk}"
    
    # Organize by member category
    category = instance.member_category.lower() if instance.member_category else 'regular'
    
    unique_id = uuid.uuid4().hex[:8]
    filename = f"{member_id}_{unique_id}.{ext}"
    
    return os.path.join('member_documents', category, str(now.year), filename)

class Member(BaseModel):
    """
    Comprehensive member model for SACCO-specific databases.
    This is the single source of truth for member data within each SACCO.
    Supports both digital and physical-only members.
    Note: System access is managed separately via User model and MemberAccount bridge.
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
        ('OTHER', 'Other'),
        ('PREFER_NOT_TO_SAY', 'Prefer not to say'),
    )
    
    MARITAL_STATUS_CHOICES = (
        ('SINGLE', 'Single'),
        ('MARRIED', 'Married'),
        ('DIVORCED', 'Divorced'),
        ('WIDOWED', 'Widowed'),
        ('SEPARATED', 'Separated'),
        ('COHABITING', 'Cohabiting'),
    )

    NEXT_OF_KIN_RELATION_CHOICES = (
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
    
    member_uuid = models.UUIDField(
        default=uuid.uuid4, 
        editable=False, 
        unique=True,
        help_text="Universal unique identifier for this member"
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
    maiden_name = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Maiden name (if applicable)"
    )
    
    date_of_birth = models.DateField(help_text="Date of birth as per ID document")
    place_of_birth = models.CharField(max_length=100, blank=True, null=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES)
    marital_status = models.CharField(max_length=15, choices=MARITAL_STATUS_CHOICES)
    nationality = CountryField(blank_label='(select nationality)', default='UG')
    religion = models.CharField(max_length=50, blank=True, null=True)
    
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
    
    annual_income = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Estimated annual income"
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
    # CONTACT INFORMATION (OFFICIAL RECORDS)
    # =============================================================================
    
    personal_email = models.EmailField(
        blank=True, 
        null=True,
        help_text="Primary email for official correspondence"
    )
    
    work_email = models.EmailField(
        blank=True, 
        null=True,
        help_text="Work email address"
    )
    
    alternative_email = models.EmailField(
        blank=True, 
        null=True,
        help_text="Alternative email address"
    )
    
    phone_primary = models.CharField(
        max_length=20,
        help_text="Primary phone number for official contact"
    )
    
    phone_secondary = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        help_text="Secondary phone number"
    )
    
    work_phone = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        help_text="Work phone number"
    )
    
    # Address information (official residence)
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
    
    # Work address
    work_address = models.TextField(blank=True, null=True)
    work_city = models.CharField(max_length=100, blank=True, null=True)
    
    # Emergency contact (different from next of kin)
    emergency_contact_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Emergency contact person"
    )
    
    emergency_contact_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Emergency contact phone number"
    )
    
    emergency_contact_relationship = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Relationship to emergency contact"
    )
    
    # =============================================================================
    # NEXT OF KIN INFORMATION
    # =============================================================================
    
    next_of_kin_name = models.CharField(
        max_length=100,
        help_text="Full name of next of kin"
    )
    
    next_of_kin_relation = models.CharField(
        max_length=50, 
        choices=NEXT_OF_KIN_RELATION_CHOICES,
        help_text="Relationship to next of kin"
    )
    
    next_of_kin_contact = models.CharField(
        max_length=15,
        help_text="Next of kin phone number"
    )
    
    next_of_kin_email = models.EmailField(
        blank=True, 
        null=True,
        help_text="Next of kin email address"
    )
    
    next_of_kin_address = models.TextField(
        blank=True, 
        null=True,
        help_text="Next of kin address"
    )
    
    next_of_kin_id_number = models.CharField(
        max_length=30, 
        blank=True, 
        null=True,
        help_text="Next of kin's ID number"
    )
    
    next_of_kin_date_of_birth = models.DateField(
        null=True,
        blank=True,
        help_text="Next of kin's date of birth"
    )
    
    # Alternative next of kin
    alternative_next_of_kin_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Alternative next of kin"
    )
    
    alternative_next_of_kin_contact = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        help_text="Alternative next of kin phone"
    )
    
    alternative_next_of_kin_relation = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Relationship to alternative next of kin"
    )
    
    # =============================================================================
    # BANKING AND FINANCIAL INFORMATION
    # =============================================================================
    
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    bank_branch = models.CharField(max_length=100, blank=True, null=True)
    bank_account_number = models.CharField(max_length=50, blank=True, null=True)
    bank_account_name = models.CharField(max_length=100, blank=True, null=True)
    bank_account_type = models.CharField(
        max_length=20,
        choices=[
            ('SAVINGS', 'Savings Account'),
            ('CHECKING', 'Checking Account'),
            ('CURRENT', 'Current Account'),
            ('FIXED_DEPOSIT', 'Fixed Deposit'),
        ],
        blank=True,
        null=True
    )
    
    # Mobile money information
    mobile_money_number = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        help_text="Mobile money account number"
    )
    
    mobile_money_provider = models.CharField(
        max_length=50, 
        choices=[
            ('MTN', 'MTN Mobile Money'),
            ('AIRTEL', 'Airtel Money'),
            ('AFRICELL', 'Africell Money'),
            ('UTL', 'UTL Mobile Money'),
            ('OTHER', 'Other Provider'),
        ],
        blank=True, 
        null=True,
        help_text="Mobile money service provider"
    )
    
    # Alternative mobile money
    alternative_mobile_money_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Alternative mobile money number"
    )
    
    alternative_mobile_money_provider = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Alternative mobile money provider"
    )
    
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

    # Additional KYC documents with specialized paths
    kyc_document_1 = models.FileField(
        upload_to=kyc_document_upload_path,
        blank=True,
        null=True,
        help_text="Additional KYC document"
    )
    
    kyc_document_2 = models.FileField(
        upload_to=kyc_document_upload_path,
        blank=True,
        null=True,
        help_text="Additional KYC document"
    )
    
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
        upload_to=member_photo_upload_path, 
        blank=True, 
        null=True,
        help_text="Member's photograph"
    )
    
    id_document_front = models.ImageField(
        upload_to=member_id_document_upload_path, 
        blank=True, 
        null=True,
        help_text="Front side of ID document"
    )
    
    id_document_back = models.ImageField(
        upload_to=member_id_document_upload_path,  
        blank=True, 
        null=True,
        help_text="Back side of ID document"
    )
    
    signature_specimen = models.ImageField(
        upload_to=member_signature_upload_path,  
        blank=True,
        null=True,
        help_text="Member's signature specimen"
    )
    
    proof_of_residence = models.FileField(
        upload_to=member_document_upload_path('residence_proof'), 
        blank=True,
        null=True,
        help_text="Proof of residence document"
    )
    
    income_proof = models.FileField(
        upload_to=member_document_upload_path('income_proof'), 
        blank=True,
        null=True,
        help_text="Proof of income document"
    )
    
    # =============================================================================
    # ACTIVITY TRACKING (MEMBER-SPECIFIC ONLY)
    # =============================================================================
    
    last_meeting_attendance = models.DateTimeField(
        blank=True, 
        null=True,
        help_text="Date of last meeting attendance"
    )
    
    # Communication preferences (for all members - digital and physical)
    preferred_communication_method = models.CharField(
        max_length=20,
        choices=[
            ('EMAIL', 'Email'),
            ('SMS', 'SMS'),
            ('PHONE', 'Phone Call'),
            ('LETTER', 'Physical Letter'),
            ('WHATSAPP', 'WhatsApp'),
        ],
        default='SMS',
        help_text="Preferred method for SACCO communications"
    )
    
    # =============================================================================
    # NOTES AND COMMENTS
    # =============================================================================
    
    member_notes = models.TextField(
        blank=True,
        null=True,
        help_text="Internal notes about this member"
    )
    
    special_instructions = models.TextField(
        blank=True,
        null=True,
        help_text="Special instructions for handling this member"
    )
    
    # =============================================================================
    # MODEL METHODS (MEMBER-ONLY LOGIC)
    # =============================================================================
    
    def __str__(self):
        return f"{self.get_full_name()} - {self.member_number}"
    
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
    
    def get_display_name(self):
        """Return display name for UI"""
        if self.title:
            return f"{self.title} {self.first_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"
    
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
    
    def get_sacco_name(self):
        """Get the name of the current SACCO"""
        try:
            from database_registry.routers import get_current_db
            from database_registry.models import Sacco
            
            current_db = get_current_db()
            if current_db != 'default':
                sacco = Sacco.objects.filter(db_name=current_db, is_active=True).first()
                if sacco:
                    return sacco.name
        except:
            pass
        return "SACCO"
    
    # =============================================================================
    # SYSTEM USER INTEGRATION METHODS (NO CIRCULAR IMPORTS)
    # =============================================================================
    
    def get_system_user(self):
        """Get associated system user if exists - via MemberAccount bridge"""
        try:
            # Use string imports to avoid circular dependencies
            from django.apps import apps
            MemberAccount = apps.get_model('user_management', 'MemberAccount')
            Sacco = apps.get_model('database_registry', 'Sacco')
            from database_registry.routers import get_current_db
            
            current_db = get_current_db()
            if current_db == 'default':
                return None  # We're not in a SACCO database
                
            # Get SACCO info to find the right MemberAccount
            sacco = Sacco.objects.filter(db_name=current_db, is_active=True).first()
            if not sacco:
                return None
                
            # Look up MemberAccount in default database
            member_account = MemberAccount.objects.using('default').filter(
                member_number=self.member_number,
                sacco=sacco,
                is_active=True
            ).first()
            
            return member_account.user if member_account else None
            
        except Exception as e:
            logger.warning(f"Could not fetch system user for member {self.member_number}: {e}")
            return None
    
    def has_system_access(self):
        """Check if member has active system access"""
        user = self.get_system_user()
        if not user:
            return False
            
        # Check if user is active and can access this SACCO
        if not user.is_active:
            return False
            
        try:
            from django.apps import apps
            Sacco = apps.get_model('database_registry', 'Sacco')
            from database_registry.routers import get_current_db
            
            current_db = get_current_db()
            if current_db == 'default':
                return False
                
            sacco = Sacco.objects.filter(db_name=current_db, is_active=True).first()
            if not sacco:
                return False
                
            return user.can_access_sacco(sacco)
            
        except Exception as e:
            logger.warning(f"Error checking system access for member {self.member_number}: {e}")
            return False
    
    def get_digital_access_status(self):
        """Get current digital access status (computed from system user)"""
        user = self.get_system_user()
        if not user:
            return 'NOT_REQUESTED'
        
        try:
            from django.apps import apps
            MemberAccount = apps.get_model('user_management', 'MemberAccount')
            Sacco = apps.get_model('database_registry', 'Sacco')
            from database_registry.routers import get_current_db
            
            current_db = get_current_db()
            if current_db == 'default':
                return 'NOT_REQUESTED'
                
            sacco = Sacco.objects.filter(db_name=current_db, is_active=True).first()
            if not sacco:
                return 'NOT_REQUESTED'
                
            member_account = MemberAccount.objects.using('default').filter(
                member_number=self.member_number,
                sacco=sacco,
                is_active=True
            ).first()
            
            if not member_account:
                return 'NOT_REQUESTED'
                
            return member_account.digital_access_status
            
        except Exception as e:
            logger.warning(f"Error getting digital access status for member {self.member_number}: {e}")
            return 'UNKNOWN'
    
    def request_digital_access(self, email, user_data=None):
        """Request digital access - creates MemberAccount with request status"""
        try:
            from django.apps import apps
            MemberAccount = apps.get_model('user_management', 'MemberAccount')
            Sacco = apps.get_model('database_registry', 'Sacco')
            from database_registry.routers import get_current_db
            
            current_db = get_current_db()
            if current_db == 'default':
                return False, "Cannot request access from default database"
                
            sacco = Sacco.objects.filter(db_name=current_db, is_active=True).first()
            if not sacco:
                return False, "SACCO not found"
            
            # Check if already has access or pending request
            existing_account = MemberAccount.objects.using('default').filter(
                member_number=self.member_number,
                sacco=sacco
            ).first()
            
            if existing_account and existing_account.digital_access_status in ['ACTIVE', 'REQUESTED']:
                return False, "Digital access already requested or active"
            
            # Create or update MemberAccount with request status
            if existing_account:
                existing_account.digital_access_status = 'REQUESTED'
                existing_account.access_requested_date = timezone.now()
                existing_account.save()
            else:
                MemberAccount.objects.using('default').create(
                    member_number=self.member_number,
                    sacco=sacco,
                    membership_date=self.membership_date,
                    digital_access_status='REQUESTED',
                    access_requested_date=timezone.now()
                )
            
            logger.info(f"Digital access requested for member {self.member_number}")
            return True, "Digital access request submitted"
            
        except Exception as e:
            logger.error(f"Error requesting digital access for member {self.member_number}: {e}")
            return False, f"Error requesting access: {str(e)}"
    
    def get_effective_communication_prefs(self):
        """Get effective communication preferences, merging with User prefs if available"""
        base_prefs = {
            'method': self.preferred_communication_method,
            'email': self.personal_email,
            'phone': self.phone_primary,
        }
        
        # If user has system access, merge with their digital preferences
        user = self.get_system_user()
        if user:
            # User digital preferences can override member preferences
            if user.email:
                base_prefs['email'] = user.email
                base_prefs['method'] = 'EMAIL'
        
        return base_prefs
    
    # =============================================================================
    # BASIC STATUS MANAGEMENT (NO EXTERNAL DEPENDENCIES)
    # =============================================================================
    
    def approve_membership(self, approved_by_user=None, reason=None):
        """Approve membership and update status"""
        if self.status == 'PENDING_APPROVAL':
            self.status = 'ACTIVE'
            self.membership_approved_date = timezone.now().date()
            self.status_changed_date = timezone.now()
            self.status_changed_reason = reason or 'Membership approved'
            self.save()
            logger.info(f"Membership approved for member {self.member_number}")
            return True
        return False
    
    def update_membership_status_by_duration(self):
        """Update member status based on membership duration (basic logic only)"""
        try:
            # Only update if currently active and very old membership with no recent updates
            if self.status == 'ACTIVE' and self.membership_duration_days > 365 * 5:  # 5 years
                # This is just membership-based logic, not transaction-based
                if not self.status_changed_date or (
                    timezone.now() - self.status_changed_date
                ).days > 365:  # No status change in a year
                    # Could potentially be dormant, but we don't check transactions here
                    # That logic should be in views where you have access to savings models
                    pass
                    
        except Exception as e:
            logger.error(f"Error updating status for member {self.member_number}: {e}")
    
    # =============================================================================
    # VALIDATION METHODS (NO EXTERNAL DEPENDENCIES)
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
        
        # Email validation
        if self.personal_email and self.work_email:
            if self.personal_email == self.work_email:
                errors['work_email'] = "Work email must be different from personal email"
        
        # Phone validation
        if self.phone_primary and self.phone_secondary:
            if self.phone_primary == self.phone_secondary:
                errors['phone_secondary'] = "Secondary phone must be different from primary phone"
        
        # Income validation
        if self.monthly_income and self.annual_income:
            expected_annual = self.monthly_income * 12
            if abs(self.annual_income - expected_annual) > expected_annual * 0.5:  # 50% tolerance
                errors['annual_income'] = "Annual income seems inconsistent with monthly income"
        
        # Membership date validation
        if self.membership_date and self.date_of_birth:
            membership_age = (self.membership_date - self.date_of_birth).days / 365.25
            if membership_age < 16:
                errors['membership_date'] = "Member must be at least 16 years old when joining"
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Basic save method with member-only logic"""
        # Set basic defaults for new members
        if not self.pk:
            # New member - set basic credit score
            if self.credit_score == 500:  # Default value
                base_score = 500
                
                # Simple scoring based on member data only (no external dependencies)
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
        
        # Call parent save
        super().save(*args, **kwargs)
    
    class Meta:
        db_table = 'members'
        verbose_name = 'Member'
        verbose_name_plural = 'Members'
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
        ]


# =============================================================================
# MEMBER GROUP MODELS (UNCHANGED - NO CIRCULAR DEPENDENCIES)
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
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    group_type = models.CharField(
        max_length=20,
        choices=GROUP_TYPE_CHOICES,
        default='LENDING_CIRCLE'
    )
    
    # Leadership
    group_leader = models.ForeignKey(
        Member, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='led_groups'
    )
    group_secretary = models.ForeignKey(
        Member, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='secretary_of_groups'
    )
    group_treasurer = models.ForeignKey(
        Member, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='treasurer_of_groups'
    )
    
    # Group details
    formation_date = models.DateField()
    meeting_frequency = models.CharField(
        max_length=20,
        choices=[
            ('WEEKLY', 'Weekly'),
            ('BI_WEEKLY', 'Bi-weekly'),
            ('MONTHLY', 'Monthly'),
            ('QUARTERLY', 'Quarterly'),
            ('AS_NEEDED', 'As Needed'),
        ],
        default='MONTHLY'
    )
    meeting_day = models.CharField(
        max_length=10,
        choices=[
            ('MONDAY', 'Monday'),
            ('TUESDAY', 'Tuesday'),
            ('WEDNESDAY', 'Wednesday'),
            ('THURSDAY', 'Thursday'),
            ('FRIDAY', 'Friday'),
            ('SATURDAY', 'Saturday'),
            ('SUNDAY', 'Sunday'),
        ],
        blank=True,
        null=True
    )
    meeting_time = models.TimeField(blank=True, null=True)
    meeting_location = models.CharField(max_length=200, blank=True, null=True)
    
    # Financial parameters
    minimum_contribution = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    maximum_loan_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Monthly interest rate percentage"
    )
    
    # Group rules
    maximum_members = models.PositiveIntegerField(
        default=20,
        help_text="Maximum number of members allowed in this group"
    )
    minimum_members = models.PositiveIntegerField(
        default=5,
        help_text="Minimum number of members required"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_full = models.BooleanField(default=False)
    
    # Relationship to members
    members = models.ManyToManyField(
        Member, 
        through='GroupMembership', 
        related_name='member_groups'
    )
    
    # Rules and regulations
    terms_and_conditions = models.TextField(blank=True, null=True)
    group_rules = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_group_type_display()})"
    
    @property
    def member_count(self):
        """Get current number of active members"""
        return self.groupmembership_set.filter(is_active=True).count()
    
    @property
    def available_slots(self):
        """Get number of available slots"""
        return max(0, self.maximum_members - self.member_count)
    
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
    
    class Meta:
        db_table = 'member_groups'
        verbose_name = 'Member Group'
        verbose_name_plural = 'Member Groups'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['group_type']),
            models.Index(fields=['is_active']),
            models.Index(fields=['formation_date']),
        ]


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
    
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    group = models.ForeignKey(MemberGroup, on_delete=models.CASCADE)
    
    role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES, 
        default='MEMBER'
    )
    
    # Membership timeline
    join_date = models.DateField()
    exit_date = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='ACTIVE'
    )
    is_active = models.BooleanField(default=True)
    
    # Financial commitments
    monthly_contribution = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    total_contributions = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total amount contributed to this group"
    )
    
    # Performance tracking
    meeting_attendance_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Percentage of meetings attended"
    )
    last_meeting_attended = models.DateField(blank=True, null=True)
    
    # Notes and comments
    notes = models.TextField(blank=True, null=True)
    exit_reason = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.member.get_full_name()} - {self.group.name} ({self.get_role_display()})"
    
    @property
    def membership_duration_days(self):
        """Calculate membership duration in days"""
        end_date = self.exit_date or timezone.now().date()
        return (end_date - self.join_date).days
    
    def calculate_attendance_rate(self):
        """Calculate meeting attendance rate"""
        # This would integrate with a meetings model if you have one
        # For now, return the stored value
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
    
    class Meta:
        unique_together = ('member', 'group')
        db_table = 'group_memberships'
        verbose_name = 'Group Membership'
        verbose_name_plural = 'Group Memberships'
        indexes = [
            models.Index(fields=['member', 'group']),
            models.Index(fields=['status']),
            models.Index(fields=['is_active']),
            models.Index(fields=['join_date']),
            models.Index(fields=['role']),
        ]