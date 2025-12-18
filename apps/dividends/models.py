from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
import uuid

from sacco_settings.models import FinancialYear, GeneralLedgerAccount, Currency
from members.models import Member
from savings.models import SavingsAccount
from user_management.models import User

class DividendPeriod(models.Model):
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
    
    name = models.CharField(max_length=100)
    financial_year = models.ForeignKey(
        FinancialYear, 
        on_delete=models.PROTECT, 
        related_name='dividend_periods'
    )
    start_date = models.DateField()
    end_date = models.DateField()
    declaration_date = models.DateField(null=True, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    record_date = models.DateField(help_text="Date for determining eligible shareholders")
    
    total_dividend_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    dividend_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        validators=[MinValueValidator(0)],
        help_text="Dividend rate in percentage"
    )
    
    status = models.CharField(max_length=15, choices=PERIOD_STATUS, default='DRAFT')
    description = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    
    # Approval tracking
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='approved_dividend_periods'
    )
    approval_date = models.DateTimeField(null=True, blank=True)
    
    # Calculation settings
    calculation_method = models.CharField(
        max_length=20, 
        choices=[
            ('FLAT_RATE', 'Flat Rate'),
            ('WEIGHTED_AVERAGE', 'Weighted Average'),
            ('TIERED', 'Tiered By Share Amount'),
            ('PROGRESSIVE', 'Progressive Rate'),
        ],
        default='FLAT_RATE'
    )
    
    # Tax settings
    withholding_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    apply_withholding_tax = models.BooleanField(default=True)
    
    # General Ledger accounts
    gl_account_dividend = models.ForeignKey(
        GeneralLedgerAccount, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='dividend_periods'
    )
    gl_account_tax = models.ForeignKey(
        GeneralLedgerAccount, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='dividend_tax_periods'
    )
    
    # Disbursement settings
    default_disbursement_method = models.CharField(
        max_length=20, 
        choices=[
            ('SAVINGS_ACCOUNT', 'Savings Account'),
            ('BANK_TRANSFER', 'Bank Transfer'),
            ('MOBILE_MONEY', 'Mobile Money'),
            ('CHEQUE', 'Cheque'),
            ('CASH', 'Cash'),
            ('SHARES', 'Additional Shares'),
        ],
        default='SAVINGS_ACCOUNT'
    )
    
    allow_member_choice = models.BooleanField(default=False)
    minimum_payout_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='created_dividend_periods'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.start_date} to {self.end_date})"
    
    class Meta:
        db_table = 'dividend_periods'
        ordering = ['-end_date']
        
class DividendCalculation(models.Model):
    """Overall dividend calculation for a period"""
    dividend_period = models.OneToOneField(
        DividendPeriod, 
        on_delete=models.CASCADE, 
        related_name='calculation'
    )
    
    calculation_date = models.DateTimeField()
    calculated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='dividend_calculations'
    )
    
    # Summary amounts
    total_shares_count = models.PositiveIntegerField(default=0)
    total_shares_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_dividend_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_net_dividend = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Member counts
    eligible_members_count = models.PositiveIntegerField(default=0)
    members_receiving_dividend_count = models.PositiveIntegerField(default=0)
    
    # Status
    is_finalized = models.BooleanField(default=False)
    finalized_date = models.DateTimeField(null=True, blank=True)
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='finalized_dividend_calculations'
    )
    
    # For recalculations
    version = models.PositiveIntegerField(default=1)
    previous_calculation = models.OneToOneField(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='new_calculation'
    )
    recalculation_reason = models.TextField(null=True, blank=True)
    
    calculation_details = models.JSONField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Calculation for {self.dividend_period} (Version {self.version})"
    
    class Meta:
        db_table = 'dividend_calculations'
        ordering = ['-calculation_date']

class MemberDividend(models.Model):
    """Individual member dividend records"""
    STATUS_CHOICES = (
        ('CALCULATED', 'Calculated'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('PROCESSING', 'Processing Payment'),
        ('PAID', 'Paid'),
        ('FAILED', 'Payment Failed'),
        ('CANCELLED', 'Cancelled'),
    )
    
    dividend_period = models.ForeignKey(
        DividendPeriod, 
        on_delete=models.CASCADE, 
        related_name='member_dividends'
    )
    calculation = models.ForeignKey(
        DividendCalculation, 
        on_delete=models.CASCADE, 
        related_name='member_dividends'
    )
    member = models.ForeignKey(
        Member, 
        on_delete=models.CASCADE, 
        related_name='dividends'
    )
    
    # Share information
    shares_count = models.PositiveIntegerField()
    shares_value = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Dividend amounts
    gross_dividend = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_dividend = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Dividend rate applied (might differ if tiered/progressive)
    applied_rate = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Payment status
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='CALCULATED')
    
    # Disbursement details
    disbursement_method = models.CharField(
        max_length=20, 
        choices=[
            ('SAVINGS_ACCOUNT', 'Savings Account'),
            ('BANK_TRANSFER', 'Bank Transfer'),
            ('MOBILE_MONEY', 'Mobile Money'),
            ('CHEQUE', 'Cheque'),
            ('CASH', 'Cash'),
            ('SHARES', 'Additional Shares'),
        ],
        null=True, 
        blank=True
    )
    disbursement_account = models.ForeignKey(
        SavingsAccount, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='dividend_disbursements'
    )
    disbursement_reference = models.CharField(max_length=100, null=True, blank=True)
    
    # Payment tracking
    payment_date = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, null=True, blank=True)
    payment_notes = models.TextField(null=True, blank=True)
    
    # Member preference if allowed
    member_preference_set = models.BooleanField(default=False)
    member_preference_date = models.DateTimeField(null=True, blank=True)
    
    # For reinvested dividends
    shares_purchased = models.PositiveIntegerField(null=True, blank=True)
    share_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    #System fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        # Calculate net dividend
        if self.gross_dividend is not None and self.tax_amount is not None:
            self.net_dividend = self.gross_dividend - self.tax_amount
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Dividend of {self.net_dividend} for {self.member} ({self.dividend_period})"
    
    class Meta:
        db_table = 'member_dividends'
        unique_together = ('dividend_period', 'member')
        ordering = ['-created_at']

class DividendRate(models.Model):
    """Tiered or progressive dividend rates"""
    dividend_period = models.ForeignKey(
        DividendPeriod, 
        on_delete=models.CASCADE, 
        related_name='dividend_rates'
    )
    tier_name = models.CharField(max_length=100)
    min_shares = models.PositiveIntegerField(default=0)
    max_shares = models.PositiveIntegerField(null=True, blank=True)
    
    # Either specify min/max shares or min/max value
    min_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    max_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        validators=[MinValueValidator(0)],
        help_text="Dividend rate for this tier in percentage"
    )
    
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.tier_name} - {self.rate}% ({self.dividend_period})"
    
    class Meta:
        db_table = 'dividend_rates'
        ordering = ['min_shares', 'min_value']

class DividendDisbursement(models.Model):
    """Batch dividend disbursement records"""
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('PARTIALLY_COMPLETED', 'Partially Completed'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    )
    
    dividend_period = models.ForeignKey(
        DividendPeriod, 
        on_delete=models.CASCADE, 
        related_name='disbursements'
    )
    disbursement_date = models.DateField()
    disbursement_method = models.CharField(
        max_length=20, 
        choices=[
            ('SAVINGS_ACCOUNT', 'Savings Account'),
            ('BANK_TRANSFER', 'Bank Transfer'),
            ('MOBILE_MONEY', 'Mobile Money'),
            ('CHEQUE', 'Cheque'),
            ('CASH', 'Cash'),
            ('SHARES', 'Additional Shares'),
        ],
    )
    
    batch_number = models.CharField(max_length=50, unique=True)
    description = models.TextField(null=True, blank=True)
    
    # Processing stats
    total_members = models.PositiveIntegerField(default=0)
    processed_members = models.PositiveIntegerField(default=0)
    successful_members = models.PositiveIntegerField(default=0)
    failed_members = models.PositiveIntegerField(default=0)
    
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    processed_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Processing info
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='initiated_disbursements'
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='processed_disbursements'
    )
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    
    gl_transaction_reference = models.CharField(max_length=100, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.batch_number:
            # Generate batch number
            date_str = timezone.now().strftime('%Y%m%d')
            random_digits = str(uuid.uuid4().int)[:6]
            self.batch_number = f"DIV{date_str}{random_digits}"
            
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Disbursement #{self.batch_number} - {self.get_disbursement_method_display()} ({self.dividend_period})"
    
    class Meta:
        db_table = 'dividend_disbursements'
        ordering = ['-disbursement_date']

class DividendPayment(models.Model):
    """Individual dividend payment records"""
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    )
    
    member_dividend = models.ForeignKey(
        MemberDividend, 
        on_delete=models.CASCADE, 
        related_name='payments'
    )
    disbursement = models.ForeignKey(
        DividendDisbursement, 
        on_delete=models.CASCADE, 
        related_name='payments'
    )
    
    payment_date = models.DateTimeField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    
    # Payment details
    payment_reference = models.CharField(max_length=100, null=True, blank=True)
    receipt_number = models.CharField(max_length=50, null=True, blank=True)
    
    # Account information based on method
    savings_account = models.ForeignKey(
        SavingsAccount, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='dividend_payments'
    )
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    bank_account = models.CharField(max_length=100, null=True, blank=True)
    mobile_number = models.CharField(max_length=20, null=True, blank=True)
    
    # For share purchases
    shares_purchased = models.PositiveIntegerField(null=True, blank=True)
    
    # Transaction details
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    transaction_date = models.DateTimeField(null=True, blank=True)
    
    # Error handling
    failure_reason = models.TextField(null=True, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    last_retry_date = models.DateTimeField(null=True, blank=True)
    
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='processed_dividend_payments'
    )
    notes = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Payment of {self.amount} to {self.member_dividend.member} ({self.get_status_display()})"
    
    class Meta:
        db_table = 'dividend_payments'
        ordering = ['-payment_date']

class DividendPreference(models.Model):
    """Member preferences for dividend disbursement"""
    member = models.ForeignKey(
        Member, 
        on_delete=models.CASCADE, 
        related_name='dividend_preferences'
    )
    dividend_period = models.ForeignKey(
        DividendPeriod, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='member_preferences'
    )
    
    # Null dividend_period means this is the default preference
    is_default = models.BooleanField(default=False)
    
    preference_method = models.CharField(
        max_length=20, 
        choices=[
            ('SAVINGS_ACCOUNT', 'Savings Account'),
            ('BANK_TRANSFER', 'Bank Transfer'),
            ('MOBILE_MONEY', 'Mobile Money'),
            ('CHEQUE', 'Cheque'),
            ('CASH', 'Cash'),
            ('SHARES', 'Additional Shares'),
        ],
    )
    
    savings_account = models.ForeignKey(
        SavingsAccount, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='dividend_preferences'
    )
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    bank_account = models.CharField(max_length=100, null=True, blank=True)
    bank_branch = models.CharField(max_length=100, null=True, blank=True)
    mobile_number = models.CharField(max_length=20, null=True, blank=True)
    
    # For partial reinvestment
    reinvest_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True,
        help_text="Percentage to reinvest in shares"
    )
    
    set_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='set_dividend_preferences'
    )
    set_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        period_str = f" for {self.dividend_period}" if self.dividend_period else " (Default)"
        return f"{self.member}'s preference: {self.get_preference_method_display()}{period_str}"
    
    class Meta:
        db_table = 'dividend_preferences'
        unique_together = ('member', 'dividend_period')
        ordering = ['-set_date']

class DividendAudit(models.Model):
    """Audit trail for dividend operations"""
    ACTION_CHOICES = (
        ('CREATE_PERIOD', 'Create Dividend Period'),
        ('EDIT_PERIOD', 'Edit Dividend Period'),
        ('CALCULATE', 'Calculate Dividends'),
        ('RECALCULATE', 'Recalculate Dividends'),
        ('APPROVE', 'Approve Dividends'),
        ('REJECT', 'Reject Dividends'),
        ('DISBURSE', 'Disburse Dividends'),
        ('CANCEL', 'Cancel Dividends'),
        ('EDIT_MEMBER', 'Edit Member Dividend'),
        ('SET_PREFERENCE', 'Set Preference'),
        ('OTHER', 'Other'),
    )
    
    dividend_period = models.ForeignKey(
        DividendPeriod, 
        on_delete=models.CASCADE, 
        related_name='audit_logs',
        null=True,
        blank=True
    )
    member_dividend = models.ForeignKey(
        MemberDividend, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='audit_logs'
    )
    
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    action_date = models.DateTimeField(default=timezone.now)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='dividend_audit_logs'
    )
    
    previous_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.get_action_display()} on {self.action_date} by {self.performed_by}"
    
    class Meta:
        db_table = 'dividend_audits'
        ordering = ['-action_date']

class DividendSummary(models.Model):
    """Summary statistics for dividend periods"""
    dividend_period = models.OneToOneField(
        DividendPeriod, 
        on_delete=models.CASCADE, 
        related_name='summary'
    )
    
    # Member statistics
    total_eligible_members = models.PositiveIntegerField(default=0)
    paid_members = models.PositiveIntegerField(default=0)
    unpaid_members = models.PositiveIntegerField(default=0)
    
    # Amount statistics
    total_shares_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_shares_count = models.PositiveIntegerField(default=0)
    total_dividend_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_tax_withheld = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_disbursed = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Disbursement method breakdown
    savings_account_count = models.PositiveIntegerField(default=0)
    savings_account_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    bank_transfer_count = models.PositiveIntegerField(default=0)
    bank_transfer_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    mobile_money_count = models.PositiveIntegerField(default=0)
    mobile_money_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    cheque_count = models.PositiveIntegerField(default=0)
    cheque_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    cash_count = models.PositiveIntegerField(default=0)
    cash_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    shares_count = models.PositiveIntegerField(default=0)
    shares_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Summary for {self.dividend_period}"
    
    class Meta:
        db_table = 'dividend_summaries'
        verbose_name_plural = "Dividend Summaries"