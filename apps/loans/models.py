# loans/models.py

from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal

from utils.models import BaseModel
from core.utils import get_base_currency, format_money, get_active_fiscal_period

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# LOAN PRODUCT MODEL
# =============================================================================

class LoanProduct(BaseModel):
    """Loan products offered by the SACCO"""
    
    INTEREST_TYPES = (
        ('FLAT', 'Flat Rate'),
        ('REDUCING_BALANCE', 'Reducing Balance'),
        ('COMPOUND', 'Compound Interest'),
    )
    
    INTEREST_CALCULATION = (
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('ANNUALLY', 'Annually'),
    )
    
    REPAYMENT_CYCLE = (
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('BI_WEEKLY', 'Bi-Weekly'),
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('ANNUALLY', 'Annually'),
    )
    
    # Basic Information
    name = models.CharField(
        "Product Name",
        max_length=100,
        help_text="Name of the loan product"
    )
    
    code = models.CharField(
        "Product Code",
        max_length=20,
        unique=True,
        help_text="Unique code for this loan product"
    )
    
    description = models.TextField(
        "Description",
        help_text="Detailed description of the loan product"
    )
    
    # Loan Amounts
    min_amount = models.DecimalField(
        "Minimum Loan Amount",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Minimum loan amount that can be requested"
    )
    
    max_amount = models.DecimalField(
        "Maximum Loan Amount",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Maximum loan amount that can be requested"
    )
    
    # Interest Configuration
    interest_rate = models.DecimalField(
        "Interest Rate (%)",
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text="Annual interest rate in percentage"
    )
    
    interest_type = models.CharField(
        "Interest Type",
        max_length=20,
        choices=INTEREST_TYPES,
        default='REDUCING_BALANCE'
    )
    
    interest_calculation = models.CharField(
        "Interest Calculation Frequency",
        max_length=20,
        choices=INTEREST_CALCULATION,
        default='MONTHLY'
    )
    
    # Fees (as percentages)
    loan_processing_fee = models.DecimalField(
        "Processing Fee (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text="Processing fee as percentage of loan amount"
    )
    
    insurance_fee = models.DecimalField(
        "Insurance Fee (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text="Insurance fee as percentage of loan amount"
    )
    
    # Loan Terms
    min_term = models.PositiveIntegerField(
        "Minimum Term (Months)",
        validators=[MinValueValidator(1)],
        help_text="Minimum loan term in months"
    )
    
    max_term = models.PositiveIntegerField(
        "Maximum Term (Months)",
        validators=[MinValueValidator(1)],
        help_text="Maximum loan term in months"
    )
    
    repayment_cycle = models.CharField(
        "Repayment Cycle",
        max_length=20,
        choices=REPAYMENT_CYCLE,
        default='MONTHLY'
    )
    
    grace_period = models.PositiveIntegerField(
        "Grace Period (Days)",
        default=0,
        help_text="Grace period in days before first payment is due"
    )
    
    # Requirements
    minimum_savings_percentage = models.DecimalField(
        "Minimum Savings Required (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text="Minimum savings required as percentage of loan amount"
    )
    
    minimum_shares_required = models.PositiveIntegerField(
        "Minimum Shares Required",
        default=0,
        help_text="Minimum number of shares member must own"
    )
    
    # Guarantor Configuration
    guarantor_required = models.BooleanField(
        "Guarantor Required",
        default=False,
        help_text="Whether guarantors are required for this product"
    )
    
    number_of_guarantors = models.PositiveIntegerField(
        "Number of Guarantors",
        default=0,
        help_text="Number of guarantors required"
    )
    
    collateral_required = models.BooleanField(
        "Collateral Required",
        default=False,
        help_text="Whether collateral is required"
    )
    
    # Loan Features
    allow_top_up = models.BooleanField(
        "Allow Top Up",
        default=False,
        help_text="Allow members to top up existing loans"
    )
    
    allow_early_repayment = models.BooleanField(
        "Allow Early Repayment",
        default=True,
        help_text="Allow early/advance loan repayment"
    )
    
    early_repayment_fee = models.DecimalField(
        "Early Repayment Fee (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text="Early repayment penalty as percentage"
    )
    
    # Penalty Configuration
    penalty_rate = models.DecimalField(
        "Penalty Rate (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text="Late payment penalty percentage"
    )
    
    penalty_grace_period = models.PositiveIntegerField(
        "Penalty Grace Period (Days)",
        default=0,
        help_text="Days before penalty applies after due date"
    )
    
    penalty_frequency = models.CharField(
        "Penalty Frequency",
        max_length=20,
        choices=INTEREST_CALCULATION,
        default='MONTHLY',
        help_text="How often penalty is calculated and applied"
    )
    
    # Status
    is_active = models.BooleanField(
        "Is Active",
        default=True,
        help_text="Whether this product is available for new loans"
    )
    
    # GL Account Code
    gl_account_code = models.CharField(
        "GL Account Code",
        max_length=20,
        null=True,
        blank=True,
        help_text="General Ledger account code for this product"
    )
    
    # Additional Settings
    maximum_loans_per_member = models.PositiveIntegerField(
        "Maximum Loans Per Member",
        default=1,
        help_text="Maximum active loans a member can have of this type"
    )
    
    requires_approval = models.BooleanField(
        "Requires Approval",
        default=True,
        help_text="Whether loan applications require approval"
    )
    
    def clean(self):
        """Validate loan product"""
        super().clean()
        errors = {}
        
        if self.min_amount >= self.max_amount:
            errors['max_amount'] = 'Maximum amount must be greater than minimum amount'
        
        if self.min_term >= self.max_term:
            errors['max_term'] = 'Maximum term must be greater than minimum term'
        
        if self.guarantor_required and self.number_of_guarantors == 0:
            errors['number_of_guarantors'] = 'Number of guarantors required when guarantors are mandatory'
        
        if errors:
            raise ValidationError(errors)
    
    def calculate_processing_fee(self, loan_amount):
        """Calculate processing fee for given loan amount"""
        try:
            amount = Decimal(str(loan_amount))
            return (amount * self.loan_processing_fee) / Decimal('100.0')
        except (ValueError, TypeError):
            return Decimal('0.00')
    
    def calculate_insurance_fee(self, loan_amount):
        """Calculate insurance fee for given loan amount"""
        try:
            amount = Decimal(str(loan_amount))
            return (amount * self.insurance_fee) / Decimal('100.0')
        except (ValueError, TypeError):
            return Decimal('0.00')
    
    def calculate_total_fees(self, loan_amount):
        """Calculate total fees for given loan amount"""
        return self.calculate_processing_fee(loan_amount) + self.calculate_insurance_fee(loan_amount)
    
    @property
    def currency(self):
        """Get currency from SACCO configuration"""
        return get_base_currency()
    
    @property
    def formatted_min_amount(self):
        """Get formatted minimum amount"""
        return format_money(self.min_amount)
    
    @property
    def formatted_max_amount(self):
        """Get formatted maximum amount"""
        return format_money(self.max_amount)
    
    @classmethod
    def get_active_products(cls):
        """Get all active loan products"""
        return cls.objects.filter(is_active=True).order_by('name')
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    class Meta:
        verbose_name = 'Loan Product'
        verbose_name_plural = 'Loan Products'
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active', 'name']),
            models.Index(fields=['code']),
        ]


# =============================================================================
# LOAN APPLICATION MODEL
# =============================================================================

class LoanApplication(BaseModel):
    """Loan applications from members"""
    
    STATUS_CHOICES = (
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
        ('DISBURSED', 'Disbursed'),
    )
    
    # Identification
    application_number = models.CharField(
        "Application Number",
        max_length=20,
        unique=True,
        editable=False,
        help_text="Unique application number"
    )
    
    # Relationships - Using string references
    member = models.ForeignKey(
        'members.Member',
        on_delete=models.CASCADE,
        related_name='loan_applications',
        help_text="Member applying for the loan"
    )
    
    loan_product = models.ForeignKey(
        LoanProduct,
        on_delete=models.PROTECT,
        help_text="Loan product being applied for"
    )
    
    # Application Details
    amount_requested = models.DecimalField(
        "Amount Requested",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Loan amount being requested"
    )
    
    purpose = models.TextField(
        "Loan Purpose",
        help_text="Purpose for which loan is being requested"
    )
    
    term_months = models.PositiveIntegerField(
        "Loan Term (Months)",
        validators=[MinValueValidator(1)],
        help_text="Requested loan term in months"
    )
    
    # Status
    status = models.CharField(
        "Application Status",
        max_length=15,
        choices=STATUS_CHOICES,
        default='DRAFT',
        db_index=True
    )
    
    application_date = models.DateField(
        "Application Date",
        auto_now_add=True,
        help_text="Date when application was created"
    )
    
    submission_date = models.DateField(
        "Submission Date",
        null=True,
        blank=True,
        help_text="Date when application was submitted for review"
    )
    
    # Fees
    processing_fee_paid = models.BooleanField(
        "Processing Fee Paid",
        default=False,
        help_text="Whether processing fee has been paid"
    )
    
    processing_fee_amount = models.DecimalField(
        "Processing Fee Amount",
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    insurance_fee_amount = models.DecimalField(
        "Insurance Fee Amount",
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Approval Details
    approved_amount = models.DecimalField(
        "Approved Amount",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Final approved loan amount (may differ from requested)"
    )
    
    approved_term = models.PositiveIntegerField(
        "Approved Term (Months)",
        null=True,
        blank=True,
        help_text="Final approved loan term"
    )
    
    approved_interest_rate = models.DecimalField(
        "Approved Interest Rate (%)",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Final approved interest rate"
    )
    
    rejection_reason = models.TextField(
        "Rejection Reason",
        null=True,
        blank=True
    )
    
    # Tracking
    reviewed_date = models.DateTimeField(
        "Reviewed Date",
        null=True,
        blank=True
    )
    
    reviewed_by_id = models.CharField(
        "Reviewed By",
        max_length=50,
        null=True,
        blank=True,
        help_text="User ID who reviewed the application"
    )
    
    approval_date = models.DateTimeField(
        "Approval Date",
        null=True,
        blank=True
    )
    
    approved_by_id = models.CharField(
        "Approved By",
        max_length=50,
        null=True,
        blank=True,
        help_text="User ID who approved the application"
    )
    
    # Disbursement
    disbursement_method = models.CharField(
        "Disbursement Method",
        max_length=20,
        choices=[
            ('BANK_TRANSFER', 'Bank Transfer'),
            ('MOBILE_MONEY', 'Mobile Money'),
            ('CASH', 'Cash'),
            ('SAVINGS_ACCOUNT', 'Savings Account'),
        ],
        null=True,
        blank=True
    )
    
    disbursement_account = models.CharField(
        "Disbursement Account",
        max_length=100,
        null=True,
        blank=True,
        help_text="Account number or phone number for disbursement"
    )
    
    # Financial Period
    financial_period = models.ForeignKey(
        'core.FiscalPeriod',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='loan_applications',
        help_text="Financial period when application was submitted"
    )
    
    notes = models.TextField(
        "Notes",
        null=True,
        blank=True,
        help_text="Additional notes about the application"
    )
    
    def save(self, *args, **kwargs):
        """Generate application number and calculate fees"""
        if not self.application_number:
            # Generate unique application number
            prefix = self.loan_product.code[:3].upper()
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            self.application_number = f"LA-{prefix}-{timestamp}"
        
        # Calculate fees if not already set
        if self.loan_product and not self.processing_fee_amount:
            self.processing_fee_amount = self.loan_product.calculate_processing_fee(self.amount_requested)
            self.insurance_fee_amount = self.loan_product.calculate_insurance_fee(self.amount_requested)
        
        # Set financial period if not set
        if not self.financial_period:
            self.financial_period = get_active_fiscal_period()
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate application"""
        super().clean()
        errors = {}
        
        # Validate amount
        if self.amount_requested < self.loan_product.min_amount:
            errors['amount_requested'] = f'Amount below product minimum of {format_money(self.loan_product.min_amount)}'
        
        if self.amount_requested > self.loan_product.max_amount:
            errors['amount_requested'] = f'Amount exceeds product maximum of {format_money(self.loan_product.max_amount)}'
        
        # Validate term
        if self.term_months < self.loan_product.min_term:
            errors['term_months'] = f'Term below product minimum of {self.loan_product.min_term} months'
        
        if self.term_months > self.loan_product.max_term:
            errors['term_months'] = f'Term exceeds product maximum of {self.loan_product.max_term} months'
        
        if errors:
            raise ValidationError(errors)
    
    @property
    def formatted_amount_requested(self):
        """Get formatted requested amount"""
        return format_money(self.amount_requested)
    
    @property
    def formatted_approved_amount(self):
        """Get formatted approved amount"""
        return format_money(self.approved_amount) if self.approved_amount else None
    
    @property
    def total_fees(self):
        """Calculate total fees"""
        return self.processing_fee_amount + self.insurance_fee_amount
    
    @property
    def formatted_total_fees(self):
        """Get formatted total fees"""
        return format_money(self.total_fees)
    
    @property
    def is_pending(self):
        """Check if application is pending"""
        return self.status in ['DRAFT', 'SUBMITTED', 'UNDER_REVIEW']
    
    @property
    def is_approved(self):
        """Check if application is approved"""
        return self.status == 'APPROVED'
    
    @property
    def can_be_edited(self):
        """Check if application can be edited"""
        return self.status == 'DRAFT'
    
    def submit(self):
        """Submit application for review"""
        if self.status != 'DRAFT':
            return False, "Only draft applications can be submitted"
        
        self.status = 'SUBMITTED'
        self.submission_date = timezone.now().date()
        self.save()
        
        logger.info(f"Loan application {self.application_number} submitted")
        return True, "Application submitted successfully"
    
    def approve(self, approved_amount=None, approved_term=None, approved_rate=None):
        """Approve the loan application"""
        if self.status not in ['SUBMITTED', 'UNDER_REVIEW']:
            return False, "Only submitted applications can be approved"
        
        self.status = 'APPROVED'
        self.approval_date = timezone.now()
        
        # Use approved values or defaults
        self.approved_amount = approved_amount or self.amount_requested
        self.approved_term = approved_term or self.term_months
        self.approved_interest_rate = approved_rate or self.loan_product.interest_rate
        
        self.save()
        
        logger.info(f"Loan application {self.application_number} approved")
        return True, "Application approved successfully"
    
    def reject(self, reason):
        """Reject the loan application"""
        if self.status not in ['SUBMITTED', 'UNDER_REVIEW']:
            return False, "Only submitted applications can be rejected"
        
        self.status = 'REJECTED'
        self.rejection_reason = reason
        self.reviewed_date = timezone.now()
        self.save()
        
        logger.info(f"Loan application {self.application_number} rejected")
        return True, "Application rejected"
    
    def __str__(self):
        return f"Application #{self.application_number} - {self.member.get_full_name()} ({self.get_status_display()})"
    
    class Meta:
        verbose_name = 'Loan Application'
        verbose_name_plural = 'Loan Applications'
        ordering = ['-application_date']
        indexes = [
            models.Index(fields=['status', 'application_date']),
            models.Index(fields=['member', 'status']),
            models.Index(fields=['loan_product', 'status']),
            models.Index(fields=['application_number']),
        ]


# =============================================================================
# LOAN MODEL
# =============================================================================

class Loan(BaseModel):
    """Active loans"""
    
    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('PAID', 'Paid'),
        ('DEFAULTED', 'Defaulted'),
        ('WRITTEN_OFF', 'Written Off'),
        ('RESTRUCTURED', 'Restructured'),
        ('SUSPENDED', 'Suspended'),
    )
    
    # Identification
    loan_number = models.CharField(
        "Loan Number",
        max_length=20,
        unique=True,
        help_text="Unique loan number"
    )
    
    # Relationships - Using string references
    member = models.ForeignKey(
        'members.Member',
        on_delete=models.CASCADE,
        related_name='loans',
        help_text="Member who received the loan"
    )
    
    loan_product = models.ForeignKey(
        LoanProduct,
        on_delete=models.PROTECT,
        help_text="Loan product type"
    )
    
    application = models.OneToOneField(
        LoanApplication,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_loan',
        help_text="Original loan application"
    )
    
    # Loan Details
    principal_amount = models.DecimalField(
        "Principal Amount",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Original loan amount disbursed"
    )
    
    interest_rate = models.DecimalField(
        "Interest Rate (%)",
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Annual interest rate percentage"
    )
    
    term_months = models.PositiveIntegerField(
        "Loan Term (Months)",
        validators=[MinValueValidator(1)],
        help_text="Loan term in months"
    )
    
    payment_frequency = models.CharField(
        "Payment Frequency",
        max_length=20,
        choices=LoanProduct.REPAYMENT_CYCLE,
        help_text="How often payments are due"
    )
    
    # Important Dates
    disbursement_date = models.DateField(
        "Disbursement Date",
        help_text="Date when loan was disbursed"
    )
    
    first_payment_date = models.DateField(
        "First Payment Date",
        help_text="Date when first payment is due"
    )
    
    expected_end_date = models.DateField(
        "Expected End Date",
        help_text="Expected final payment date"
    )
    
    actual_end_date = models.DateField(
        "Actual End Date",
        null=True,
        blank=True,
        help_text="Actual date when loan was fully paid"
    )
    
    # Status
    status = models.CharField(
        "Loan Status",
        max_length=15,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        db_index=True
    )
    
    # Calculated Totals
    total_interest = models.DecimalField(
        "Total Interest",
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total interest to be paid over loan term"
    )
    
    total_fees = models.DecimalField(
        "Total Fees",
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total fees charged (processing, insurance, etc.)"
    )
    
    total_payable = models.DecimalField(
        "Total Payable",
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total amount to be repaid (principal + interest + fees)"
    )
    
    # Paid Amounts
    total_paid = models.DecimalField(
        "Total Paid",
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total amount paid so far"
    )
    
    total_paid_principal = models.DecimalField(
        "Total Paid Principal",
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    total_paid_interest = models.DecimalField(
        "Total Paid Interest",
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    total_paid_penalties = models.DecimalField(
        "Total Paid Penalties",
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    total_paid_fees = models.DecimalField(
        "Total Paid Fees",
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Outstanding Balances
    outstanding_principal = models.DecimalField(
        "Outstanding Principal",
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    outstanding_interest = models.DecimalField(
        "Outstanding Interest",
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    outstanding_penalties = models.DecimalField(
        "Outstanding Penalties",
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    outstanding_fees = models.DecimalField(
        "Outstanding Fees",
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    outstanding_total = models.DecimalField(
        "Outstanding Total",
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Payment Tracking
    days_in_arrears = models.PositiveIntegerField(
        "Days in Arrears",
        default=0,
        help_text="Number of days payment is overdue"
    )
    
    last_payment_date = models.DateField(
        "Last Payment Date",
        null=True,
        blank=True
    )
    
    next_payment_date = models.DateField(
        "Next Payment Date",
        null=True,
        blank=True
    )
    
    next_payment_amount = models.DecimalField(
        "Next Payment Amount",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Financial Period
    financial_period = models.ForeignKey(
        'core.FiscalPeriod',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='loans',
        help_text="Financial period when loan was disbursed"
    )
    
    # Disbursement Details
    disbursement_method = models.ForeignKey(
        'core.PaymentMethod',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='disbursed_loans',
        help_text="Method used for loan disbursement"
    )
    
    disbursement_reference = models.CharField(
        "Disbursement Reference",
        max_length=100,
        null=True,
        blank=True
    )
    
    # Additional Notes
    notes = models.TextField(
        "Notes",
        null=True,
        blank=True
    )
    
    def save(self, *args, **kwargs):
        """Generate loan number and update balances"""
        if not self.loan_number:
            prefix = self.loan_product.code[:3].upper()
            member_id = str(self.member.id)[:8] if hasattr(self.member, 'id') else 'NEW'
            timestamp = timezone.now().strftime('%Y%m%d')
            self.loan_number = f"LN-{prefix}-{member_id}-{timestamp}"
        
        # Initialize outstanding amounts if new loan
        if not self.pk:
            self.outstanding_principal = self.principal_amount
            self.outstanding_interest = self.total_interest
        
        # Calculate outstanding total
        self.outstanding_total = (
            self.outstanding_principal +
            self.outstanding_interest +
            self.outstanding_penalties +
            self.outstanding_fees
        )
        
        # Update status based on outstanding balance
        if self.outstanding_total <= 0 and self.status == 'ACTIVE':
            self.status = 'PAID'
            if not self.actual_end_date:
                self.actual_end_date = timezone.now().date()
        
        # Set financial period if not set
        if not self.financial_period:
            self.financial_period = get_active_fiscal_period()
        
        super().save(*args, **kwargs)
    
    @property
    def currency(self):
        """Get currency from SACCO configuration"""
        return get_base_currency()
    
    @property
    def formatted_principal(self):
        """Get formatted principal amount"""
        return format_money(self.principal_amount)
    
    @property
    def formatted_total_payable(self):
        """Get formatted total payable"""
        return format_money(self.total_payable)
    
    @property
    def formatted_outstanding(self):
        """Get formatted outstanding amount"""
        return format_money(self.outstanding_total)
    
    @property
    def formatted_total_paid(self):
        """Get formatted total paid"""
        return format_money(self.total_paid)
    
    @property
    def payment_progress_percentage(self):
        """Get payment progress as percentage"""
        if self.total_payable > 0:
            return (self.total_paid / self.total_payable) * 100
        return Decimal('0.00')
    
    @property
    def is_overdue(self):
        """Check if loan has overdue payments"""
        return self.days_in_arrears > 0
    
    @property
    def is_fully_paid(self):
        """Check if loan is fully paid"""
        return self.outstanding_total <= 0
    
    @property
    def loan_duration_days(self):
        """Get loan duration in days since disbursement"""
        return (timezone.now().date() - self.disbursement_date).days
    
    @property
    def remaining_term_months(self):
        """Get remaining months in loan term"""
        if self.status == 'PAID':
            return 0
        
        today = timezone.now().date()
        if today >= self.expected_end_date:
            return 0
        
        days_remaining = (self.expected_end_date - today).days
        return days_remaining / 30.44  # Average days per month
    
    @classmethod
    def get_active_loans(cls):
        """Get all active loans"""
        return cls.objects.filter(status='ACTIVE')
    
    @classmethod
    def get_overdue_loans(cls):
        """Get all loans with overdue payments"""
        return cls.objects.filter(status='ACTIVE', days_in_arrears__gt=0).order_by('-days_in_arrears')
    
    @classmethod
    def get_member_active_loans(cls, member):
        """Get all active loans for a member"""
        return cls.objects.filter(member=member, status='ACTIVE')
    
    def __str__(self):
        return f"Loan #{self.loan_number} - {self.member.get_full_name()} ({format_money(self.principal_amount)})"
    
    class Meta:
        verbose_name = 'Loan'
        verbose_name_plural = 'Loans'
        ordering = ['-disbursement_date']
        indexes = [
            models.Index(fields=['status', 'disbursement_date']),
            models.Index(fields=['member', 'status']),
            models.Index(fields=['loan_product', 'status']),
            models.Index(fields=['days_in_arrears']),
            models.Index(fields=['loan_number']),
            models.Index(fields=['next_payment_date']),
        ]


# =============================================================================
# LOAN PAYMENT MODEL
# =============================================================================

class LoanPayment(BaseModel):
    """Loan payments"""
    
    PAYMENT_METHODS = (
        ('CASH', 'Cash'),
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('MOBILE_MONEY', 'Mobile Money'),
        ('SAVINGS_ACCOUNT', 'Savings Account Transfer'),
        ('CHEQUE', 'Cheque'),
    )
    
    # Identification
    payment_number = models.CharField(
        "Payment Number",
        max_length=20,
        unique=True,
        help_text="Unique payment identifier"
    )
    
    # Relationships
    loan = models.ForeignKey(
        Loan,
        on_delete=models.CASCADE,
        related_name='payments',
        help_text="Loan this payment is for"
    )
    
    payment_date = models.DateField(
        "Payment Date",
        help_text="Date when payment was made"
    )
    
    # Payment Amounts
    amount = models.DecimalField(
        "Total Payment Amount",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Total amount paid"
    )
    
    principal_amount = models.DecimalField(
        "Principal Amount",
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount applied to principal"
    )
    
    interest_amount = models.DecimalField(
        "Interest Amount",
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount applied to interest"
    )
    
    penalty_amount = models.DecimalField(
        "Penalty Amount",
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount applied to penalties"
    )
    
    fee_amount = models.DecimalField(
        "Fee Amount",
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount applied to fees"
    )
    
    # Payment Method
    payment_method = models.CharField(
        "Payment Method",
        max_length=20,
        choices=PAYMENT_METHODS
    )
    
    payment_method_ref = models.ForeignKey(
        'core.PaymentMethod',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loan_payments',
        help_text="Payment method configuration reference"
    )
    
    reference_number = models.CharField(
        "Reference Number",
        max_length=100,
        null=True,
        blank=True,
        help_text="External reference (e.g., mobile money transaction ID)"
    )
    
    receipt_number = models.CharField(
        "Receipt Number",
        max_length=50,
        null=True,
        blank=True
    )
    
    notes = models.TextField(
        "Notes",
        null=True,
        blank=True
    )
    
    # Reversal
    is_reversed = models.BooleanField(
        "Is Reversed",
        default=False
    )
    
    reversal_reason = models.TextField(
        "Reversal Reason",
        null=True,
        blank=True
    )
    
    reversal_date = models.DateTimeField(
        "Reversal Date",
        null=True,
        blank=True
    )
    
    reversed_by_id = models.CharField(
        "Reversed By",
        max_length=50,
        null=True,
        blank=True,
        help_text="User ID who reversed the payment"
    )
    
    # Financial Period
    financial_period = models.ForeignKey(
        'core.FiscalPeriod',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='loan_payments',
        help_text="Financial period when payment was made"
    )
    
    def save(self, *args, **kwargs):
        """Generate payment number and update loan"""
        if not self.payment_number:
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            self.payment_number = f"PMT-{timestamp}"
        
        # Set financial period if not set
        if not self.financial_period:
            self.financial_period = get_active_fiscal_period()
        
        super().save(*args, **kwargs)
        
        # Update loan balances if not reversed
        if not self.is_reversed:
            self.update_loan_balances()
    
    def update_loan_balances(self):
        """Update loan balances after payment"""
        loan = self.loan
        
        # Update paid amounts
        loan.total_paid += self.amount
        loan.total_paid_principal += self.principal_amount
        loan.total_paid_interest += self.interest_amount
        loan.total_paid_penalties += self.penalty_amount
        loan.total_paid_fees += self.fee_amount
        
        # Update outstanding amounts
        loan.outstanding_principal -= self.principal_amount
        loan.outstanding_interest -= self.interest_amount
        loan.outstanding_penalties -= self.penalty_amount
        loan.outstanding_fees -= self.fee_amount
        
        # Ensure no negative balances
        loan.outstanding_principal = max(loan.outstanding_principal, Decimal('0.00'))
        loan.outstanding_interest = max(loan.outstanding_interest, Decimal('0.00'))
        loan.outstanding_penalties = max(loan.outstanding_penalties, Decimal('0.00'))
        loan.outstanding_fees = max(loan.outstanding_fees, Decimal('0.00'))
        
        # Update payment tracking
        loan.last_payment_date = self.payment_date
        
        loan.save()
        
        logger.info(f"Payment {self.payment_number} processed for loan {loan.loan_number}")
    
    def reverse(self, reason):
        """Reverse this payment"""
        if self.is_reversed:
            return False, "Payment is already reversed"
        
        loan = self.loan
        
        # Reverse the amounts on the loan
        loan.total_paid -= self.amount
        loan.total_paid_principal -= self.principal_amount
        loan.total_paid_interest -= self.interest_amount
        loan.total_paid_penalties -= self.penalty_amount
        loan.total_paid_fees -= self.fee_amount
        
        loan.outstanding_principal += self.principal_amount
        loan.outstanding_interest += self.interest_amount
        loan.outstanding_penalties += self.penalty_amount
        loan.outstanding_fees += self.fee_amount
        
        loan.save()
        
        # Mark as reversed
        self.is_reversed = True
        self.reversal_reason = reason
        self.reversal_date = timezone.now()
        self.save()
        
        logger.info(f"Payment {self.payment_number} reversed")
        return True, "Payment reversed successfully"
    
    @property
    def currency(self):
        """Get currency from SACCO configuration"""
        return get_base_currency()
    
    @property
    def formatted_amount(self):
        """Get formatted payment amount"""
        return format_money(self.amount)
    
    @property
    def formatted_principal_amount(self):
        """Get formatted principal amount"""
        return format_money(self.principal_amount)
    
    @property
    def formatted_interest_amount(self):
        """Get formatted interest amount"""
        return format_money(self.interest_amount)
    
    def __str__(self):
        return f"Payment #{self.payment_number} for {self.loan.loan_number} - {format_money(self.amount)}"
    
    class Meta:
        verbose_name = 'Loan Payment'
        verbose_name_plural = 'Loan Payments'
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['loan', 'payment_date']),
            models.Index(fields=['payment_method', 'payment_date']),
            models.Index(fields=['is_reversed']),
            models.Index(fields=['payment_number']),
        ]


# =============================================================================
# LOAN GUARANTOR MODEL
# =============================================================================

class LoanGuarantor(BaseModel):
    """Guarantors for loan applications"""
    
    STATUS_CHOICES = (
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
        ('EXPIRED', 'Expired'),
    )
    
    # Relationships
    loan_application = models.ForeignKey(
        LoanApplication,
        on_delete=models.CASCADE,
        related_name='guarantors',
        help_text="Loan application being guaranteed"
    )
    
    guarantor = models.ForeignKey(
        'members.Member',
        on_delete=models.CASCADE,
        related_name='guarantor_for',
        help_text="Member acting as guarantor"
    )
    
    guarantee_amount = models.DecimalField(
        "Guarantee Amount",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Amount being guaranteed"
    )
    
    relationship = models.CharField(
        "Relationship to Applicant",
        max_length=100,
        null=True,
        blank=True,
        help_text="Relationship between guarantor and applicant"
    )
    
    status = models.CharField(
        "Guarantor Status",
        max_length=10,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )
    
    request_date = models.DateTimeField(
        "Request Date",
        auto_now_add=True
    )
    
    response_date = models.DateTimeField(
        "Response Date",
        null=True,
        blank=True
    )
    
    notes = models.TextField(
        "Notes",
        null=True,
        blank=True
    )
    
    def clean(self):
        """Validate guarantor"""
        super().clean()
        errors = {}
        
        if self.guarantor == self.loan_application.member:
            errors['guarantor'] = 'Guarantor cannot be the loan applicant'
        
        # Validate guarantor has sufficient capacity
        if hasattr(self, 'guarantor') and self.guarantor:
            # Check guarantor's total guarantees
            existing_guarantees = LoanGuarantor.objects.filter(
                guarantor=self.guarantor,
                status='APPROVED'
            ).exclude(pk=self.pk).aggregate(
                total=models.Sum('guarantee_amount')
            )['total'] or Decimal('0.00')
            
            # Add current guarantee
            total_guarantees = existing_guarantees + self.guarantee_amount
            
            # You can add limit checks here based on guarantor's savings
            # Example: if total_guarantees > guarantor's savings * 3
        
        if errors:
            raise ValidationError(errors)
    
    def approve(self):
        """Approve guarantor"""
        if self.status != 'PENDING':
            return False, "Only pending guarantors can be approved"
        
        self.status = 'APPROVED'
        self.response_date = timezone.now()
        self.save()
        
        logger.info(f"Guarantor {self.guarantor.get_full_name()} approved for application {self.loan_application.application_number}")
        return True, "Guarantor approved"
    
    def reject(self, reason=None):
        """Reject guarantor"""
        if self.status != 'PENDING':
            return False, "Only pending guarantors can be rejected"
        
        self.status = 'REJECTED'
        self.response_date = timezone.now()
        if reason:
            self.notes = f"{self.notes or ''}\nRejection reason: {reason}".strip()
        self.save()
        
        logger.info(f"Guarantor {self.guarantor.get_full_name()} rejected for application {self.loan_application.application_number}")
        return True, "Guarantor rejected"
    
    @property
    def formatted_guarantee_amount(self):
        """Get formatted guarantee amount"""
        return format_money(self.guarantee_amount)
    
    def __str__(self):
        return f"{self.guarantor.get_full_name()} for {self.loan_application.application_number} - {self.get_status_display()}"
    
    class Meta:
        unique_together = ('loan_application', 'guarantor')
        verbose_name = 'Loan Guarantor'
        verbose_name_plural = 'Loan Guarantors'
        ordering = ['-request_date']
        indexes = [
            models.Index(fields=['status', 'request_date']),
            models.Index(fields=['guarantor', 'status']),
        ]


# =============================================================================
# LOAN COLLATERAL MODEL
# =============================================================================

class LoanCollateral(BaseModel):
    """Collateral for loan applications"""
    
    COLLATERAL_TYPES = (
        ('REAL_ESTATE', 'Real Estate'),
        ('VEHICLE', 'Vehicle'),
        ('EQUIPMENT', 'Equipment/Machinery'),
        ('FIXED_DEPOSIT', 'Fixed Deposit'),
        ('SHARES', 'Company Shares'),
        ('INVENTORY', 'Business Inventory'),
        ('RECEIVABLES', 'Accounts Receivable'),
        ('OTHER', 'Other Assets'),
    )
    
    # Relationships
    loan_application = models.ForeignKey(
        LoanApplication,
        on_delete=models.CASCADE,
        related_name='collaterals',
        help_text="Loan application this collateral is for"
    )
    
    collateral_type = models.CharField(
        "Collateral Type",
        max_length=15,
        choices=COLLATERAL_TYPES
    )
    
    description = models.TextField(
        "Description",
        help_text="Detailed description of the collateral"
    )
    
    # Valuation
    estimated_value = models.DecimalField(
        "Estimated Value",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Estimated market value"
    )
    
    appraised_value = models.DecimalField(
        "Appraised Value",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Professional appraisal value"
    )
    
    forced_sale_value = models.DecimalField(
        "Forced Sale Value",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Estimated value in forced sale scenario"
    )
    
    valuation_date = models.DateField(
        "Valuation Date",
        help_text="Date when valuation was done"
    )
    
    location = models.TextField(
        "Location",
        null=True,
        blank=True,
        help_text="Physical location of the collateral"
    )
    
    # Ownership Details
    owner_name = models.CharField(
        "Owner Name",
        max_length=200,
        help_text="Legal owner of the collateral"
    )
    
    ownership_document_number = models.CharField(
        "Ownership Document Number",
        max_length=100,
        null=True,
        blank=True,
        help_text="Title deed, registration number, etc."
    )
    
    # Documents
    ownership_document = models.FileField(
        "Ownership Document",
        upload_to='collateral_documents/',
        null=True,
        blank=True
    )
    
    photo = models.ImageField(
        "Photo",
        upload_to='collateral_photos/',
        null=True,
        blank=True
    )
    
    appraisal_report = models.FileField(
        "Appraisal Report",
        upload_to='collateral_appraisals/',
        null=True,
        blank=True
    )
    
    # Verification
    is_verified = models.BooleanField(
        "Is Verified",
        default=False
    )
    
    verification_date = models.DateTimeField(
        "Verification Date",
        null=True,
        blank=True
    )
    
    verified_by_id = models.CharField(
        "Verified By",
        max_length=50,
        null=True,
        blank=True,
        help_text="User ID who verified the collateral"
    )
    
    verification_notes = models.TextField(
        "Verification Notes",
        null=True,
        blank=True
    )
    
    # Insurance
    is_insured = models.BooleanField(
        "Is Insured",
        default=False
    )
    
    insurance_policy_number = models.CharField(
        "Insurance Policy Number",
        max_length=100,
        null=True,
        blank=True
    )
    
    insurance_expiry_date = models.DateField(
        "Insurance Expiry Date",
        null=True,
        blank=True
    )
    
    @property
    def formatted_estimated_value(self):
        """Get formatted estimated value"""
        return format_money(self.estimated_value)
    
    @property
    def formatted_appraised_value(self):
        """Get formatted appraised value"""
        return format_money(self.appraised_value) if self.appraised_value else None
    
    def verify(self, notes=None):
        """Verify collateral"""
        self.is_verified = True
        self.verification_date = timezone.now()
        if notes:
            self.verification_notes = notes
        self.save()
        
        logger.info(f"Collateral verified for application {self.loan_application.application_number}")
        return True, "Collateral verified"
    
    def __str__(self):
        return f"{self.get_collateral_type_display()} for {self.loan_application.application_number} - {format_money(self.estimated_value)}"
    
    class Meta:
        verbose_name = 'Loan Collateral'
        verbose_name_plural = 'Loan Collaterals'
        ordering = ['-valuation_date']
        indexes = [
            models.Index(fields=['loan_application', 'is_verified']),
            models.Index(fields=['collateral_type']),
        ]


# =============================================================================
# LOAN SCHEDULE MODEL
# =============================================================================

class LoanSchedule(BaseModel):
    """Loan repayment schedule"""
    
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('WAIVED', 'Waived'),
    )
    
    # Relationships
    loan = models.ForeignKey(
        Loan,
        on_delete=models.CASCADE,
        related_name='schedule',
        help_text="Loan this installment is for"
    )
    
    installment_number = models.PositiveIntegerField(
        "Installment Number",
        validators=[MinValueValidator(1)],
        help_text="Sequential installment number"
    )
    
    due_date = models.DateField(
        "Due Date",
        help_text="Date when payment is due"
    )
    
    # Scheduled Amounts
    principal_amount = models.DecimalField(
        "Principal Amount",
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    interest_amount = models.DecimalField(
        "Interest Amount",
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    total_amount = models.DecimalField(
        "Total Amount",
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Paid Amounts
    paid_amount = models.DecimalField(
        "Paid Amount",
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    paid_principal = models.DecimalField(
        "Paid Principal",
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    paid_interest = models.DecimalField(
        "Paid Interest",
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Balance and Status
    balance = models.DecimalField(
        "Balance",
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    status = models.CharField(
        "Status",
        max_length=15,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )
    
    paid_date = models.DateField(
        "Paid Date",
        null=True,
        blank=True
    )
    
    days_late = models.IntegerField(
        "Days Late",
        default=0,
        help_text="Number of days overdue"
    )
    
    # Financial Period
    financial_period = models.ForeignKey(
        'core.FiscalPeriod',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='loan_schedules',
        help_text="Financial period this installment falls in"
    )
    
    def save(self, *args, **kwargs):
        """Calculate totals and update status"""
        # Calculate total
        self.total_amount = self.principal_amount + self.interest_amount
        
        # Calculate balance
        self.balance = self.total_amount - self.paid_amount
        
        # Update status
        if self.balance <= 0:
            self.status = 'PAID'
            if not self.paid_date:
                self.paid_date = timezone.now().date()
        elif self.paid_amount > 0:
            self.status = 'PARTIALLY_PAID'
        elif self.due_date < timezone.now().date():
            self.status = 'OVERDUE'
            self.days_late = (timezone.now().date() - self.due_date).days
        else:
            self.status = 'PENDING'
        
        super().save(*args, **kwargs)
    
    @property
    def currency(self):
        """Get currency from SACCO configuration"""
        return get_base_currency()
    
    @property
    def formatted_total_amount(self):
        """Get formatted total amount"""
        return format_money(self.total_amount)
    
    @property
    def formatted_balance(self):
        """Get formatted balance"""
        return format_money(self.balance)
    
    @property
    def is_overdue(self):
        """Check if installment is overdue"""
        return self.status == 'OVERDUE'
    
    @property
    def is_paid(self):
        """Check if installment is paid"""
        return self.status == 'PAID'
    
    def __str__(self):
        return f"Installment #{self.installment_number} for {self.loan.loan_number} - Due: {self.due_date}"
    
    class Meta:
        unique_together = ('loan', 'installment_number')
        ordering = ['loan', 'installment_number']
        verbose_name = 'Loan Schedule'
        verbose_name_plural = 'Loan Schedules'
        indexes = [
            models.Index(fields=['due_date', 'status']),
            models.Index(fields=['status', 'days_late']),
            models.Index(fields=['loan', 'status']),
        ]


# =============================================================================
# LOAN DOCUMENT MODEL
# =============================================================================

class LoanDocument(BaseModel):
    """Documents for loan applications and loans"""
    
    DOCUMENT_TYPES = (
        ('APPLICATION_FORM', 'Application Form'),
        ('ID_DOCUMENT', 'ID Document'),
        ('PAYSLIP', 'Payslip'),
        ('BANK_STATEMENT', 'Bank Statement'),
        ('BUSINESS_REGISTRATION', 'Business Registration'),
        ('TAX_RETURNS', 'Tax Returns'),
        ('COLLATERAL_DOC', 'Collateral Document'),
        ('APPRAISAL_REPORT', 'Appraisal Report'),
        ('CONTRACT', 'Loan Contract'),
        ('PROMISSORY_NOTE', 'Promissory Note'),
        ('GUARANTOR_FORM', 'Guarantor Form'),
        ('OTHER', 'Other Document'),
    )
    
    # Relationships
    loan = models.ForeignKey(
        Loan,
        on_delete=models.CASCADE,
        related_name='documents',
        null=True,
        blank=True,
        help_text="Loan this document belongs to"
    )
    
    application = models.ForeignKey(
        LoanApplication,
        on_delete=models.CASCADE,
        related_name='documents',
        null=True,
        blank=True,
        help_text="Application this document belongs to"
    )
    
    document_type = models.CharField(
        "Document Type",
        max_length=25,
        choices=DOCUMENT_TYPES
    )
    
    document = models.FileField(
        "Document File",
        upload_to='loan_documents/'
    )
    
    title = models.CharField(
        "Document Title",
        max_length=100
    )
    
    description = models.TextField(
        "Description",
        null=True,
        blank=True
    )
    
    # Verification
    is_required = models.BooleanField(
        "Is Required",
        default=False,
        help_text="Whether this document is mandatory"
    )
    
    is_verified = models.BooleanField(
        "Is Verified",
        default=False
    )
    
    verification_date = models.DateTimeField(
        "Verification Date",
        null=True,
        blank=True
    )
    
    verified_by_id = models.CharField(
        "Verified By",
        max_length=50,
        null=True,
        blank=True,
        help_text="User ID who verified the document"
    )
    
    verification_notes = models.TextField(
        "Verification Notes",
        null=True,
        blank=True
    )
    
    # Expiry (for documents like IDs, licenses)
    expiry_date = models.DateField(
        "Expiry Date",
        null=True,
        blank=True,
        help_text="Document expiry date (if applicable)"
    )
    
    def clean(self):
        """Validate document"""
        super().clean()
        errors = {}
        
        if not self.loan and not self.application:
            errors['__all__'] = 'Document must be associated with either a loan or application'
        
        if self.loan and self.application:
            errors['__all__'] = 'Document cannot be associated with both loan and application'
        
        if errors:
            raise ValidationError(errors)
    
    def verify(self, notes=None):
        """Verify document"""
        self.is_verified = True
        self.verification_date = timezone.now()
        if notes:
            self.verification_notes = notes
        self.save()
        
        logger.info(f"Document '{self.title}' verified")
        return True, "Document verified"
    
    @property
    def is_expired(self):
        """Check if document is expired"""
        if not self.expiry_date:
            return False
        return self.expiry_date < timezone.now().date()
    
    def __str__(self):
        entity = self.loan or self.application
        return f"{self.get_document_type_display()} - {self.title} for {entity}"
    
    class Meta:
        verbose_name = 'Loan Document'
        verbose_name_plural = 'Loan Documents'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['document_type']),
            models.Index(fields=['is_verified']),
            models.Index(fields=['is_required', 'is_verified']),
        ]