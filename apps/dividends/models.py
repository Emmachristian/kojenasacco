# dividends/models.py

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
import uuid

from utils.models import BaseModel
from core.utils import get_base_currency, format_money, get_active_fiscal_period

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# DIVIDEND PERIOD MODEL
# =============================================================================

class DividendPeriod(BaseModel):
    """Dividend periods for calculating and distributing dividends"""
    
    PERIOD_STATUS = (
        ('DRAFT', 'Draft'),
        ('OPEN', 'Open'),
        ('CALCULATING', 'Calculating'),
        ('CALCULATED', 'Calculated'),
        ('APPROVED', 'Approved'),
        ('DISBURSING', 'Disbursing'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )
    
    CALCULATION_METHOD_CHOICES = [
        ('FLAT_RATE', 'Flat Rate'),
        ('WEIGHTED_AVERAGE', 'Weighted Average'),
        ('TIERED', 'Tiered By Share Amount'),
        ('PRO_RATA', 'Pro Rata Distribution'),
    ]
    
    # Basic Information
    name = models.CharField(
        "Period Name",
        max_length=100,
        help_text="Name of the dividend period (e.g., 'FY 2024 Dividends')"
    )
    
    financial_period = models.ForeignKey(
        'core.FiscalPeriod',
        on_delete=models.PROTECT,
        related_name='dividend_periods',
        help_text="Financial period this dividend relates to"
    )
    
    # Dates
    start_date = models.DateField(
        "Start Date",
        help_text="Start date of the dividend period"
    )
    
    end_date = models.DateField(
        "End Date",
        help_text="End date of the dividend period"
    )
    
    record_date = models.DateField(
        "Record Date",
        help_text="Date for determining eligible shareholders"
    )
    
    declaration_date = models.DateField(
        "Declaration Date",
        null=True,
        blank=True,
        help_text="Date when dividend was declared"
    )
    
    payment_date = models.DateField(
        "Payment Date",
        null=True,
        blank=True,
        help_text="Date when dividend will be/was paid"
    )
    
    # Dividend Configuration
    total_dividend_amount = models.DecimalField(
        "Total Dividend Amount",
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Total amount available for dividend distribution"
    )
    
    dividend_rate = models.DecimalField(
        "Dividend Rate (%)",
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text="Dividend rate in percentage"
    )
    
    calculation_method = models.CharField(
        "Calculation Method",
        max_length=20,
        choices=CALCULATION_METHOD_CHOICES,
        default='FLAT_RATE'
    )
    
    # Tax Configuration
    withholding_tax_rate = models.DecimalField(
        "Withholding Tax Rate (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text="Withholding tax rate to apply"
    )
    
    apply_withholding_tax = models.BooleanField(
        "Apply Withholding Tax",
        default=True,
        help_text="Whether to apply withholding tax on dividends"
    )
    
    # Disbursement Settings
    default_disbursement_method = models.CharField(
        "Default Disbursement Method",
        max_length=20,
        choices=[
            ('SAVINGS_ACCOUNT', 'Savings Account'),
            ('BANK_TRANSFER', 'Bank Transfer'),
            ('MOBILE_MONEY', 'Mobile Money'),
            ('CASH', 'Cash'),
        ],
        default='SAVINGS_ACCOUNT'
    )
    
    allow_member_choice = models.BooleanField(
        "Allow Member Choice",
        default=False,
        help_text="Allow members to choose disbursement method"
    )
    
    minimum_payout_amount = models.DecimalField(
        "Minimum Payout Amount",
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Minimum amount for dividend payout"
    )
    
    # Status
    status = models.CharField(
        "Status",
        max_length=15,
        choices=PERIOD_STATUS,
        default='DRAFT',
        db_index=True
    )
    
    is_approved = models.BooleanField(
        "Is Approved",
        default=False
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
        help_text="User ID who approved the dividend period"
    )
    
    # Statistics
    total_members = models.PositiveIntegerField(
        "Total Members",
        default=0,
        help_text="Number of members eligible for dividends"
    )
    
    total_shares = models.PositiveIntegerField(
        "Total Shares",
        default=0,
        help_text="Total number of shares in the period"
    )
    
    total_shares_value = models.DecimalField(
        "Total Shares Value",
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total value of all shares"
    )
    
    description = models.TextField(
        "Description",
        null=True,
        blank=True
    )
    
    notes = models.TextField(
        "Notes",
        null=True,
        blank=True
    )
    
    def clean(self):
        """Validate dividend period"""
        super().clean()
        errors = {}
        
        if self.start_date and self.end_date:
            if self.start_date >= self.end_date:
                errors['end_date'] = 'End date must be after start date'
        
        if self.record_date:
            if self.start_date and self.record_date < self.start_date:
                errors['record_date'] = 'Record date cannot be before start date'
            if self.end_date and self.record_date > self.end_date:
                errors['record_date'] = 'Record date cannot be after end date'
        
        if self.payment_date and self.declaration_date:
            if self.payment_date < self.declaration_date:
                errors['payment_date'] = 'Payment date cannot be before declaration date'
        
        if errors:
            raise ValidationError(errors)
    
    @property
    def currency(self):
        """Get currency from SACCO configuration"""
        return get_base_currency()
    
    @property
    def formatted_total_amount(self):
        """Get formatted total dividend amount"""
        return format_money(self.total_dividend_amount)
    
    @property
    def formatted_total_shares_value(self):
        """Get formatted total shares value"""
        return format_money(self.total_shares_value)
    
    @property
    def is_active(self):
        """Check if period is currently active"""
        return self.status in ['OPEN', 'CALCULATING', 'CALCULATED', 'APPROVED', 'DISBURSING']
    
    @property
    def is_disbursed(self):
        """Check if dividends have been disbursed"""
        return self.status == 'COMPLETED'
    
    @property
    def can_be_edited(self):
        """Check if period can be edited"""
        return self.status in ['DRAFT', 'OPEN']
    
    def approve(self):
        """Approve dividend period"""
        if self.status != 'CALCULATED':
            return False, "Only calculated dividend periods can be approved"
        
        self.status = 'APPROVED'
        self.is_approved = True
        self.approval_date = timezone.now()
        self.save()
        
        logger.info(f"Dividend period {self.name} approved")
        return True, "Dividend period approved successfully"
    
    def __str__(self):
        return f"{self.name} ({self.start_date} to {self.end_date})"
    
    class Meta:
        verbose_name = 'Dividend Period'
        verbose_name_plural = 'Dividend Periods'
        ordering = ['-end_date']
        indexes = [
            models.Index(fields=['status', 'end_date']),
            models.Index(fields=['financial_period']),
            models.Index(fields=['record_date']),
        ]


# =============================================================================
# MEMBER DIVIDEND MODEL
# =============================================================================

class MemberDividend(BaseModel):
    """Individual member dividend records"""
    
    STATUS_CHOICES = (
        ('CALCULATED', 'Calculated'),
        ('APPROVED', 'Approved'),
        ('PROCESSING', 'Processing Payment'),
        ('PAID', 'Paid'),
        ('FAILED', 'Payment Failed'),
        ('CANCELLED', 'Cancelled'),
    )
    
    DISBURSEMENT_METHOD_CHOICES = [
        ('SAVINGS_ACCOUNT', 'Savings Account'),
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('MOBILE_MONEY', 'Mobile Money'),
        ('CASH', 'Cash'),
    ]
    
    # Relationships - Using string references
    dividend_period = models.ForeignKey(
        DividendPeriod,
        on_delete=models.CASCADE,
        related_name='member_dividends',
        help_text="Dividend period this dividend belongs to"
    )
    
    member = models.ForeignKey(
        'members.Member',
        on_delete=models.CASCADE,
        related_name='dividends',
        help_text="Member receiving the dividend"
    )
    
    # Share Information
    shares_count = models.PositiveIntegerField(
        "Number of Shares",
        default=0,
        help_text="Number of shares owned by member"
    )
    
    shares_value = models.DecimalField(
        "Shares Value",
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total value of member's shares"
    )
    
    # Dividend Amounts
    gross_dividend = models.DecimalField(
        "Gross Dividend",
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Dividend before tax"
    )
    
    tax_amount = models.DecimalField(
        "Tax Amount",
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Withholding tax amount"
    )
    
    net_dividend = models.DecimalField(
        "Net Dividend",
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Dividend after tax"
    )
    
    # Dividend rate applied
    applied_rate = models.DecimalField(
        "Applied Rate (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Dividend rate applied to this member"
    )
    
    # Status
    status = models.CharField(
        "Status",
        max_length=15,
        choices=STATUS_CHOICES,
        default='CALCULATED',
        db_index=True
    )
    
    # Disbursement Details
    disbursement_method = models.CharField(
        "Disbursement Method",
        max_length=20,
        choices=DISBURSEMENT_METHOD_CHOICES,
        null=True,
        blank=True
    )
    
    disbursement_account = models.ForeignKey(
        'savings.SavingsAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dividend_disbursements',
        help_text="Savings account for disbursement"
    )
    
    disbursement_reference = models.CharField(
        "Disbursement Reference",
        max_length=100,
        null=True,
        blank=True,
        help_text="External reference for disbursement"
    )
    
    # Payment Tracking
    payment_date = models.DateTimeField(
        "Payment Date",
        null=True,
        blank=True
    )
    
    payment_reference = models.CharField(
        "Payment Reference",
        max_length=100,
        null=True,
        blank=True
    )
    
    payment_notes = models.TextField(
        "Payment Notes",
        null=True,
        blank=True
    )
    
    # Failure Tracking
    failure_reason = models.TextField(
        "Failure Reason",
        null=True,
        blank=True
    )
    
    retry_count = models.PositiveIntegerField(
        "Retry Count",
        default=0
    )
    
    def save(self, *args, **kwargs):
        """Calculate net dividend"""
        if self.gross_dividend is not None and self.tax_amount is not None:
            self.net_dividend = self.gross_dividend - self.tax_amount
        
        super().save(*args, **kwargs)
    
    @property
    def currency(self):
        """Get currency from SACCO configuration"""
        return get_base_currency()
    
    @property
    def formatted_gross_dividend(self):
        """Get formatted gross dividend"""
        return format_money(self.gross_dividend)
    
    @property
    def formatted_net_dividend(self):
        """Get formatted net dividend"""
        return format_money(self.net_dividend)
    
    @property
    def formatted_tax_amount(self):
        """Get formatted tax amount"""
        return format_money(self.tax_amount)
    
    @property
    def formatted_shares_value(self):
        """Get formatted shares value"""
        return format_money(self.shares_value)
    
    @property
    def is_paid(self):
        """Check if dividend has been paid"""
        return self.status == 'PAID'
    
    @property
    def is_pending(self):
        """Check if dividend is pending payment"""
        return self.status in ['CALCULATED', 'APPROVED', 'PROCESSING']
    
    def approve(self):
        """Approve member dividend"""
        if self.status != 'CALCULATED':
            return False, "Only calculated dividends can be approved"
        
        self.status = 'APPROVED'
        self.save()
        
        logger.info(f"Dividend for {self.member.get_full_name()} approved")
        return True, "Dividend approved"
    
    def mark_as_paid(self, payment_reference=None, notes=None):
        """Mark dividend as paid"""
        if self.status == 'PAID':
            return False, "Dividend is already paid"
        
        self.status = 'PAID'
        self.payment_date = timezone.now()
        if payment_reference:
            self.payment_reference = payment_reference
        if notes:
            self.payment_notes = notes
        self.save()
        
        logger.info(f"Dividend for {self.member.get_full_name()} marked as paid")
        return True, "Dividend marked as paid"
    
    def mark_as_failed(self, reason):
        """Mark dividend payment as failed"""
        self.status = 'FAILED'
        self.failure_reason = reason
        self.retry_count += 1
        self.save()
        
        logger.warning(f"Dividend payment failed for {self.member.get_full_name()}: {reason}")
        return True, "Dividend marked as failed"
    
    def __str__(self):
        return f"Dividend of {format_money(self.net_dividend)} for {self.member.get_full_name()} ({self.dividend_period.name})"
    
    class Meta:
        verbose_name = 'Member Dividend'
        verbose_name_plural = 'Member Dividends'
        unique_together = ('dividend_period', 'member')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['dividend_period', 'status']),
            models.Index(fields=['member', 'status']),
            models.Index(fields=['status', 'payment_date']),
        ]


# =============================================================================
# DIVIDEND RATE MODEL (FOR TIERED CALCULATION)
# =============================================================================

class DividendRate(BaseModel):
    """Tiered dividend rates for different share levels"""
    
    dividend_period = models.ForeignKey(
        DividendPeriod,
        on_delete=models.CASCADE,
        related_name='dividend_rates',
        help_text="Dividend period this rate applies to"
    )
    
    tier_name = models.CharField(
        "Tier Name",
        max_length=100,
        help_text="Name of this tier (e.g., 'Bronze', 'Silver', 'Gold')"
    )
    
    # Share-based tiers
    min_shares = models.PositiveIntegerField(
        "Minimum Shares",
        default=0,
        help_text="Minimum number of shares for this tier"
    )
    
    max_shares = models.PositiveIntegerField(
        "Maximum Shares",
        null=True,
        blank=True,
        help_text="Maximum number of shares (blank for no limit)"
    )
    
    # Value-based tiers
    min_value = models.DecimalField(
        "Minimum Value",
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Minimum share value for this tier"
    )
    
    max_value = models.DecimalField(
        "Maximum Value",
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Maximum share value (blank for no limit)"
    )
    
    # Rate
    rate = models.DecimalField(
        "Rate (%)",
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text="Dividend rate for this tier in percentage"
    )
    
    description = models.TextField(
        "Description",
        null=True,
        blank=True
    )
    
    is_active = models.BooleanField(
        "Is Active",
        default=True
    )
    
    def clean(self):
        """Validate tier configuration"""
        super().clean()
        errors = {}
        
        # Must have either share-based or value-based criteria
        has_shares = self.min_shares > 0 or self.max_shares is not None
        has_value = self.min_value is not None or self.max_value is not None
        
        if not has_shares and not has_value:
            errors['__all__'] = 'Must specify either share count or value criteria'
        
        # Validate share ranges
        if self.max_shares is not None and self.min_shares >= self.max_shares:
            errors['max_shares'] = 'Maximum shares must be greater than minimum shares'
        
        # Validate value ranges
        if self.min_value is not None and self.max_value is not None:
            if self.min_value >= self.max_value:
                errors['max_value'] = 'Maximum value must be greater than minimum value'
        
        if errors:
            raise ValidationError(errors)
    
    @property
    def formatted_min_value(self):
        """Get formatted minimum value"""
        return format_money(self.min_value) if self.min_value else None
    
    @property
    def formatted_max_value(self):
        """Get formatted maximum value"""
        return format_money(self.max_value) if self.max_value else "No limit"
    
    def __str__(self):
        return f"{self.tier_name} - {self.rate}% ({self.dividend_period.name})"
    
    class Meta:
        verbose_name = 'Dividend Rate'
        verbose_name_plural = 'Dividend Rates'
        ordering = ['dividend_period', 'min_shares', 'min_value']
        indexes = [
            models.Index(fields=['dividend_period', 'is_active']),
        ]


# =============================================================================
# DIVIDEND DISBURSEMENT MODEL
# =============================================================================

class DividendDisbursement(BaseModel):
    """Batch dividend disbursement records"""
    
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    )
    
    DISBURSEMENT_METHOD_CHOICES = [
        ('SAVINGS_ACCOUNT', 'Savings Account'),
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('MOBILE_MONEY', 'Mobile Money'),
        ('CASH', 'Cash'),
    ]
    
    # Relationships
    dividend_period = models.ForeignKey(
        DividendPeriod,
        on_delete=models.CASCADE,
        related_name='disbursements',
        help_text="Dividend period for this disbursement"
    )
    
    # Disbursement Details
    disbursement_date = models.DateField(
        "Disbursement Date",
        help_text="Date when disbursement was/will be made"
    )
    
    disbursement_method = models.CharField(
        "Disbursement Method",
        max_length=20,
        choices=DISBURSEMENT_METHOD_CHOICES
    )
    
    batch_number = models.CharField(
        "Batch Number",
        max_length=50,
        unique=True,
        help_text="Unique batch identifier"
    )
    
    description = models.TextField(
        "Description",
        null=True,
        blank=True
    )
    
    # Processing Statistics
    total_members = models.PositiveIntegerField(
        "Total Members",
        default=0,
        help_text="Total number of members in this batch"
    )
    
    processed_members = models.PositiveIntegerField(
        "Processed Members",
        default=0,
        help_text="Number of members processed"
    )
    
    successful_members = models.PositiveIntegerField(
        "Successful Members",
        default=0,
        help_text="Number of successful payments"
    )
    
    failed_members = models.PositiveIntegerField(
        "Failed Members",
        default=0,
        help_text="Number of failed payments"
    )
    
    total_amount = models.DecimalField(
        "Total Amount",
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total amount to disburse"
    )
    
    processed_amount = models.DecimalField(
        "Processed Amount",
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Amount successfully processed"
    )
    
    # Status
    status = models.CharField(
        "Status",
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )
    
    # Processing Times
    start_time = models.DateTimeField(
        "Start Time",
        null=True,
        blank=True
    )
    
    end_time = models.DateTimeField(
        "End Time",
        null=True,
        blank=True
    )
    
    notes = models.TextField(
        "Notes",
        null=True,
        blank=True
    )
    
    def save(self, *args, **kwargs):
        """Generate batch number if not provided"""
        if not self.batch_number:
            date_str = timezone.now().strftime('%Y%m%d')
            random_digits = str(uuid.uuid4().int)[:6]
            self.batch_number = f"DIV-{date_str}-{random_digits}"
        
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
    def formatted_processed_amount(self):
        """Get formatted processed amount"""
        return format_money(self.processed_amount)
    
    @property
    def completion_percentage(self):
        """Get completion percentage"""
        if self.total_members > 0:
            return (self.processed_members / self.total_members) * 100
        return Decimal('0.00')
    
    @property
    def success_rate(self):
        """Get success rate percentage"""
        if self.processed_members > 0:
            return (self.successful_members / self.processed_members) * 100
        return Decimal('0.00')
    
    @property
    def is_completed(self):
        """Check if disbursement is completed"""
        return self.status == 'COMPLETED'
    
    @property
    def processing_duration(self):
        """Get processing duration"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    def start_processing(self):
        """Start processing disbursement"""
        if self.status != 'PENDING':
            return False, "Only pending disbursements can be started"
        
        self.status = 'PROCESSING'
        self.start_time = timezone.now()
        self.save()
        
        logger.info(f"Disbursement batch {self.batch_number} started")
        return True, "Disbursement started"
    
    def complete_processing(self):
        """Complete processing disbursement"""
        if self.status != 'PROCESSING':
            return False, "Only processing disbursements can be completed"
        
        self.status = 'COMPLETED'
        self.end_time = timezone.now()
        self.save()
        
        logger.info(f"Disbursement batch {self.batch_number} completed")
        return True, "Disbursement completed"
    
    def __str__(self):
        return f"Disbursement #{self.batch_number} - {self.get_disbursement_method_display()} ({self.dividend_period.name})"
    
    class Meta:
        verbose_name = 'Dividend Disbursement'
        verbose_name_plural = 'Dividend Disbursements'
        ordering = ['-disbursement_date']
        indexes = [
            models.Index(fields=['dividend_period', 'status']),
            models.Index(fields=['batch_number']),
            models.Index(fields=['disbursement_date']),
            models.Index(fields=['status']),
        ]


# =============================================================================
# DIVIDEND PAYMENT MODEL
# =============================================================================

class DividendPayment(BaseModel):
    """Individual dividend payment records"""
    
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    )
    
    # Relationships
    member_dividend = models.ForeignKey(
        MemberDividend,
        on_delete=models.CASCADE,
        related_name='payments',
        help_text="Member dividend this payment is for"
    )
    
    disbursement = models.ForeignKey(
        DividendDisbursement,
        on_delete=models.CASCADE,
        related_name='payments',
        help_text="Disbursement batch this payment belongs to"
    )
    
    # Payment Details
    payment_date = models.DateTimeField(
        "Payment Date",
        help_text="Date when payment was made"
    )
    
    amount = models.DecimalField(
        "Amount",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Payment amount"
    )
    
    status = models.CharField(
        "Status",
        max_length=15,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )
    
    payment_reference = models.CharField(
        "Payment Reference",
        max_length=100,
        null=True,
        blank=True,
        help_text="Payment reference number"
    )
    
    receipt_number = models.CharField(
        "Receipt Number",
        max_length=50,
        null=True,
        blank=True
    )
    
    # Account Information
    savings_account = models.ForeignKey(
        'savings.SavingsAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dividend_payments',
        help_text="Savings account payment was made to"
    )
    
    bank_name = models.CharField(
        "Bank Name",
        max_length=100,
        null=True,
        blank=True
    )
    
    bank_account = models.CharField(
        "Bank Account",
        max_length=100,
        null=True,
        blank=True
    )
    
    mobile_number = models.CharField(
        "Mobile Number",
        max_length=20,
        null=True,
        blank=True
    )
    
    # Transaction Details
    transaction_id = models.CharField(
        "Transaction ID",
        max_length=100,
        null=True,
        blank=True,
        help_text="External transaction ID"
    )
    
    transaction_date = models.DateTimeField(
        "Transaction Date",
        null=True,
        blank=True
    )
    
    # Error Handling
    failure_reason = models.TextField(
        "Failure Reason",
        null=True,
        blank=True
    )
    
    retry_count = models.PositiveIntegerField(
        "Retry Count",
        default=0
    )
    
    last_retry_date = models.DateTimeField(
        "Last Retry Date",
        null=True,
        blank=True
    )
    
    notes = models.TextField(
        "Notes",
        null=True,
        blank=True
    )
    
    @property
    def currency(self):
        """Get currency from SACCO configuration"""
        return get_base_currency()
    
    @property
    def formatted_amount(self):
        """Get formatted payment amount"""
        return format_money(self.amount)
    
    @property
    def is_successful(self):
        """Check if payment was successful"""
        return self.status == 'COMPLETED'
    
    @property
    def is_failed(self):
        """Check if payment failed"""
        return self.status == 'FAILED'
    
    @property
    def can_retry(self):
        """Check if payment can be retried"""
        return self.status == 'FAILED' and self.retry_count < 3
    
    def mark_as_completed(self, transaction_id=None):
        """Mark payment as completed"""
        self.status = 'COMPLETED'
        self.transaction_date = timezone.now()
        if transaction_id:
            self.transaction_id = transaction_id
        self.save()
        
        # Update member dividend status
        self.member_dividend.mark_as_paid(
            payment_reference=self.payment_reference,
            notes=f"Paid via {self.disbursement.batch_number}"
        )
        
        logger.info(f"Payment completed for {self.member_dividend.member.get_full_name()}")
        return True, "Payment completed"
    
    def mark_as_failed(self, reason):
        """Mark payment as failed"""
        self.status = 'FAILED'
        self.failure_reason = reason
        self.retry_count += 1
        self.last_retry_date = timezone.now()
        self.save()
        
        # Update member dividend status
        self.member_dividend.mark_as_failed(reason)
        
        logger.warning(f"Payment failed for {self.member_dividend.member.get_full_name()}: {reason}")
        return True, "Payment marked as failed"
    
    def __str__(self):
        return f"Payment of {format_money(self.amount)} to {self.member_dividend.member.get_full_name()} ({self.get_status_display()})"
    
    class Meta:
        verbose_name = 'Dividend Payment'
        verbose_name_plural = 'Dividend Payments'
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['status', 'payment_date']),
            models.Index(fields=['disbursement', 'status']),
            models.Index(fields=['member_dividend']),
        ]


# =============================================================================
# DIVIDEND PREFERENCE MODEL
# =============================================================================

class DividendPreference(BaseModel):
    """Member preferences for dividend disbursement"""
    
    PREFERENCE_METHOD_CHOICES = [
        ('SAVINGS_ACCOUNT', 'Savings Account'),
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('MOBILE_MONEY', 'Mobile Money'),
        ('CASH', 'Cash'),
    ]
    
    # Relationships
    member = models.ForeignKey(
        'members.Member',
        on_delete=models.CASCADE,
        related_name='dividend_preferences',
        help_text="Member who set this preference"
    )
    
    dividend_period = models.ForeignKey(
        DividendPeriod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='member_preferences',
        help_text="Specific dividend period (null = default preference)"
    )
    
    # Null dividend_period means this is the default preference
    is_default = models.BooleanField(
        "Is Default",
        default=False,
        help_text="Whether this is the default preference"
    )
    
    # Preference Details
    preference_method = models.CharField(
        "Preference Method",
        max_length=20,
        choices=PREFERENCE_METHOD_CHOICES
    )
    
    # Account Information
    savings_account = models.ForeignKey(
        'savings.SavingsAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dividend_preferences',
        help_text="Preferred savings account"
    )
    
    bank_name = models.CharField(
        "Bank Name",
        max_length=100,
        null=True,
        blank=True
    )
    
    bank_account = models.CharField(
        "Bank Account",
        max_length=100,
        null=True,
        blank=True
    )
    
    bank_branch = models.CharField(
        "Bank Branch",
        max_length=100,
        null=True,
        blank=True
    )
    
    mobile_number = models.CharField(
        "Mobile Number",
        max_length=20,
        null=True,
        blank=True
    )
    
    mobile_provider = models.CharField(
        "Mobile Provider",
        max_length=50,
        null=True,
        blank=True,
        help_text="Mobile money provider (MTN, Airtel, etc.)"
    )
    
    notes = models.TextField(
        "Notes",
        null=True,
        blank=True
    )
    
    def clean(self):
        """Validate preference"""
        super().clean()
        errors = {}
        
        # Validate account information based on method
        if self.preference_method == 'SAVINGS_ACCOUNT' and not self.savings_account:
            errors['savings_account'] = 'Savings account required for this method'
        
        if self.preference_method == 'BANK_TRANSFER':
            if not self.bank_name:
                errors['bank_name'] = 'Bank name required for bank transfer'
            if not self.bank_account:
                errors['bank_account'] = 'Bank account number required for bank transfer'
        
        if self.preference_method == 'MOBILE_MONEY' and not self.mobile_number:
            errors['mobile_number'] = 'Mobile number required for mobile money'
        
        # Only one default preference per member
        if self.is_default and not self.dividend_period:
            existing_default = DividendPreference.objects.filter(
                member=self.member,
                is_default=True,
                dividend_period__isnull=True
            ).exclude(pk=self.pk).exists()
            
            if existing_default:
                errors['is_default'] = 'Member already has a default preference'
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Save with validation"""
        # If setting as default, clear other defaults
        if self.is_default and not self.dividend_period:
            DividendPreference.objects.filter(
                member=self.member,
                is_default=True,
                dividend_period__isnull=True
            ).exclude(pk=self.pk).update(is_default=False)
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    @classmethod
    def get_member_preference(cls, member, dividend_period=None):
        """Get member's preference for a dividend period"""
        # Try to get period-specific preference
        if dividend_period:
            preference = cls.objects.filter(
                member=member,
                dividend_period=dividend_period
            ).first()
            if preference:
                return preference
        
        # Fall back to default preference
        return cls.objects.filter(
            member=member,
            is_default=True,
            dividend_period__isnull=True
        ).first()
    
    def __str__(self):
        period_str = f" for {self.dividend_period.name}" if self.dividend_period else " (Default)"
        return f"{self.member.get_full_name()}'s preference: {self.get_preference_method_display()}{period_str}"
    
    class Meta:
        verbose_name = 'Dividend Preference'
        verbose_name_plural = 'Dividend Preferences'
        unique_together = ('member', 'dividend_period')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['member', 'is_default']),
            models.Index(fields=['member', 'dividend_period']),
        ]