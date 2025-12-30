# shares/models.py

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
# SHARE CAPITAL MODEL
# =============================================================================

class ShareCapital(BaseModel):
    """Share capital configuration and settings"""
    
    # Basic Information
    name = models.CharField(
        "Share Capital Name",
        max_length=100,
        help_text="Name/description of this share capital configuration"
    )
    
    share_price = models.DecimalField(
        "Share Price",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Price per share"
    )
    
    # Share Limits
    minimum_shares = models.PositiveIntegerField(
        "Minimum Shares",
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Minimum shares a member must own"
    )
    
    maximum_shares = models.PositiveIntegerField(
        "Maximum Shares",
        null=True,
        blank=True,
        help_text="Maximum shares a member can own (blank for no limit)"
    )
    
    # Purchase/Sale Configuration
    allow_fractional_shares = models.BooleanField(
        "Allow Fractional Shares",
        default=False,
        help_text="Whether fractional shares are allowed"
    )
    
    minimum_purchase_shares = models.PositiveIntegerField(
        "Minimum Purchase Shares",
        default=1,
        help_text="Minimum shares per purchase transaction"
    )
    
    maximum_purchase_shares = models.PositiveIntegerField(
        "Maximum Purchase Shares",
        null=True,
        blank=True,
        help_text="Maximum shares per purchase transaction"
    )
    
    # Redemption Configuration
    allow_redemption = models.BooleanField(
        "Allow Redemption",
        default=True,
        help_text="Whether members can redeem (sell back) shares"
    )
    
    redemption_notice_period_days = models.PositiveIntegerField(
        "Redemption Notice Period (Days)",
        default=30,
        help_text="Notice period required before share redemption"
    )
    
    early_redemption_penalty = models.DecimalField(
        "Early Redemption Penalty (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text="Penalty for early redemption as percentage"
    )
    
    minimum_holding_period_days = models.PositiveIntegerField(
        "Minimum Holding Period (Days)",
        default=0,
        help_text="Minimum days shares must be held before redemption"
    )
    
    # Transfer Configuration
    allow_transfers = models.BooleanField(
        "Allow Transfers",
        default=True,
        help_text="Whether share transfers between members are allowed"
    )
    
    transfer_fee = models.DecimalField(
        "Transfer Fee",
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text="Fixed fee for share transfers"
    )
    
    transfer_fee_percentage = models.DecimalField(
        "Transfer Fee (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text="Transfer fee as percentage of transaction value"
    )
    
    require_transfer_approval = models.BooleanField(
        "Require Transfer Approval",
        default=True,
        help_text="Whether transfers require approval"
    )
    
    # Certificate Configuration
    issue_certificates = models.BooleanField(
        "Issue Certificates",
        default=True,
        help_text="Whether to issue share certificates"
    )
    
    certificate_prefix = models.CharField(
        "Certificate Prefix",
        max_length=10,
        default="SC",
        help_text="Prefix for certificate numbers"
    )
    
    # Status
    is_active = models.BooleanField(
        "Is Active",
        default=True,
        help_text="Whether this share capital configuration is active"
    )
    
    effective_date = models.DateField(
        "Effective Date",
        help_text="Date when this configuration becomes effective"
    )
    
    # GL Account
    gl_account_code = models.CharField(
        "GL Account Code",
        max_length=20,
        null=True,
        blank=True,
        help_text="General Ledger account code for share capital"
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
        """Validate share capital configuration"""
        super().clean()
        errors = {}
        
        if self.maximum_shares and self.minimum_shares >= self.maximum_shares:
            errors['maximum_shares'] = 'Maximum shares must be greater than minimum shares'
        
        if self.maximum_purchase_shares and self.minimum_purchase_shares >= self.maximum_purchase_shares:
            errors['maximum_purchase_shares'] = 'Maximum purchase shares must be greater than minimum'
        
        if errors:
            raise ValidationError(errors)
    
    @property
    def currency(self):
        """Get currency from SACCO configuration"""
        return get_base_currency()
    
    @property
    def formatted_share_price(self):
        """Get formatted share price"""
        return format_money(self.share_price)
    
    @property
    def minimum_investment(self):
        """Calculate minimum investment required"""
        return self.share_price * self.minimum_shares
    
    @property
    def formatted_minimum_investment(self):
        """Get formatted minimum investment"""
        return format_money(self.minimum_investment)
    
    def calculate_transfer_fee(self, shares_count):
        """Calculate transfer fee for given share count"""
        transaction_value = self.share_price * Decimal(str(shares_count))
        
        # Fixed fee
        fee = self.transfer_fee
        
        # Percentage fee
        if self.transfer_fee_percentage > 0:
            percentage_fee = (transaction_value * self.transfer_fee_percentage) / Decimal('100')
            fee += percentage_fee
        
        return fee.quantize(Decimal('0.01'))
    
    @classmethod
    def get_active_share_capital(cls):
        """Get currently active share capital configuration"""
        return cls.objects.filter(
            is_active=True,
            effective_date__lte=timezone.now().date()
        ).order_by('-effective_date').first()
    
    def __str__(self):
        return f"{self.name} - {format_money(self.share_price)} per share"
    
    class Meta:
        verbose_name = 'Share Capital'
        verbose_name_plural = 'Share Capital'
        ordering = ['-effective_date']
        indexes = [
            models.Index(fields=['is_active', 'effective_date']),
        ]


# =============================================================================
# SHARE TRANSACTION MODEL
# =============================================================================

class ShareTransaction(BaseModel):
    """Share transactions (buy, sell, transfer)"""
    
    TRANSACTION_TYPES = (
        ('BUY', 'Purchase'),
        ('SELL', 'Sale/Redemption'),
        ('TRANSFER_OUT', 'Transfer Out'),
        ('TRANSFER_IN', 'Transfer In'),
        ('ADJUSTMENT', 'Adjustment'),
    )
    
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('COMPLETED', 'Completed'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
        ('REVERSED', 'Reversed'),
    )
    
    # Identification
    transaction_number = models.CharField(
        "Transaction Number",
        max_length=20,
        unique=True,
        editable=False,
        help_text="Unique transaction number"
    )
    
    # Relationships
    member = models.ForeignKey(
        'members.Member',
        on_delete=models.CASCADE,
        related_name='share_transactions',
        help_text="Member involved in this transaction"
    )
    
    share_capital = models.ForeignKey(
        ShareCapital,
        on_delete=models.PROTECT,
        help_text="Share capital configuration at time of transaction"
    )
    
    # Transaction Details
    transaction_type = models.CharField(
        "Transaction Type",
        max_length=15,
        choices=TRANSACTION_TYPES,
        db_index=True
    )
    
    transaction_date = models.DateTimeField(
        "Transaction Date",
        default=timezone.now,
        db_index=True
    )
    
    shares_count = models.DecimalField(
        "Number of Shares",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Number of shares in this transaction"
    )
    
    price_per_share = models.DecimalField(
        "Price Per Share",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Price per share for this transaction"
    )
    
    total_amount = models.DecimalField(
        "Total Amount",
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total transaction amount"
    )
    
    # Payment Information
    payment_method = models.ForeignKey(
        'core.PaymentMethod',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='share_transactions',
        help_text="Payment method used"
    )
    
    reference_number = models.CharField(
        "Reference Number",
        max_length=100,
        null=True,
        blank=True,
        help_text="External reference (e.g., receipt number, transaction ID)"
    )
    
    # Transfer-specific fields
    transfer_from = models.ForeignKey(
        'members.Member',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='share_transfers_out',
        help_text="Member transferring shares (for transfers)"
    )
    
    transfer_to = models.ForeignKey(
        'members.Member',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='share_transfers_in',
        help_text="Member receiving shares (for transfers)"
    )
    
    transfer_fee = models.DecimalField(
        "Transfer Fee",
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Fee charged for transfer"
    )
    
    linked_transaction = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linked_transactions',
        help_text="Linked transaction (e.g., corresponding transfer)"
    )
    
    # Status
    status = models.CharField(
        "Status",
        max_length=15,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )
    
    approval_required = models.BooleanField(
        "Approval Required",
        default=False
    )
    
    approved_date = models.DateTimeField(
        "Approved Date",
        null=True,
        blank=True
    )
    
    approved_by_id = models.CharField(
        "Approved By",
        max_length=50,
        null=True,
        blank=True,
        help_text="User ID who approved the transaction"
    )
    
    # Reversal
    is_reversed = models.BooleanField(
        "Is Reversed",
        default=False,
        db_index=True
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
        help_text="User ID who reversed the transaction"
    )
    
    reversal_transaction = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='original_transaction',
        help_text="Reversal transaction reference"
    )
    
    # Financial Period
    financial_period = models.ForeignKey(
        'core.FiscalPeriod',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='share_transactions',
        help_text="Financial period when transaction occurred"
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
    
    def save(self, *args, **kwargs):
        """Calculate total amount"""
        if self.shares_count and self.price_per_share:
            self.total_amount = self.shares_count * self.price_per_share
        
        # Set financial period if not set
        if not self.financial_period:
            self.financial_period = get_active_fiscal_period()
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate transaction"""
        super().clean()
        errors = {}
        
        # Validate transfer fields
        if self.transaction_type in ['TRANSFER_OUT', 'TRANSFER_IN']:
            if not self.transfer_from or not self.transfer_to:
                errors['__all__'] = 'Transfer requires both transfer_from and transfer_to members'
            
            if self.transfer_from == self.transfer_to:
                errors['__all__'] = 'Cannot transfer shares to the same member'
        
        if errors:
            raise ValidationError(errors)
    
    @property
    def currency(self):
        """Get currency from SACCO configuration"""
        return get_base_currency()
    
    @property
    def formatted_total_amount(self):
        """Get formatted total amount"""
        return format_money(self.total_amount)
    
    @property
    def formatted_price_per_share(self):
        """Get formatted price per share"""
        return format_money(self.price_per_share)
    
    @property
    def is_completed(self):
        """Check if transaction is completed"""
        return self.status == 'COMPLETED'
    
    @property
    def is_pending(self):
        """Check if transaction is pending"""
        return self.status in ['PENDING', 'APPROVED']
    
    @property
    def affects_balance(self):
        """Check if transaction affects member's share balance"""
        return self.status == 'COMPLETED' and not self.is_reversed
    
    def approve(self, approved_by=None):
        """Approve transaction"""
        if self.status != 'PENDING':
            return False, "Only pending transactions can be approved"
        
        self.status = 'APPROVED'
        self.approved_date = timezone.now()
        if approved_by:
            self.approved_by_id = str(approved_by.id)
        self.save()
        
        logger.info(f"Share transaction {self.transaction_number} approved")
        return True, "Transaction approved"
    
    def complete(self):
        """Complete transaction"""
        if self.status not in ['PENDING', 'APPROVED']:
            return False, f"Cannot complete transaction with status: {self.get_status_display()}"
        
        self.status = 'COMPLETED'
        self.save()
        
        logger.info(f"Share transaction {self.transaction_number} completed")
        return True, "Transaction completed"
    
    def reject(self, reason):
        """Reject transaction"""
        if self.status != 'PENDING':
            return False, "Only pending transactions can be rejected"
        
        self.status = 'REJECTED'
        self.notes = f"{self.notes or ''}\nRejection: {reason}".strip()
        self.save()
        
        logger.info(f"Share transaction {self.transaction_number} rejected")
        return True, "Transaction rejected"
    
    def reverse(self, reason, reversed_by=None):
        """Reverse transaction"""
        if self.is_reversed:
            return False, "Transaction is already reversed"
        
        if self.status != 'COMPLETED':
            return False, "Only completed transactions can be reversed"
        
        self.is_reversed = True
        self.reversal_reason = reason
        self.reversal_date = timezone.now()
        if reversed_by:
            self.reversed_by_id = str(reversed_by.id)
        self.save()
        
        logger.info(f"Share transaction {self.transaction_number} reversed")
        return True, "Transaction reversed"
    
    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.shares_count} shares @ {format_money(self.price_per_share)} ({self.transaction_number})"
    
    class Meta:
        verbose_name = 'Share Transaction'
        verbose_name_plural = 'Share Transactions'
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['member', 'transaction_type', 'status']),
            models.Index(fields=['transaction_date', 'status']),
            models.Index(fields=['status', 'is_reversed']),
            models.Index(fields=['transaction_number']),
        ]


# =============================================================================
# SHARE CERTIFICATE MODEL
# =============================================================================

class ShareCertificate(BaseModel):
    """Share ownership certificates"""
    
    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('CANCELLED', 'Cancelled'),
        ('TRANSFERRED', 'Transferred'),
        ('LOST', 'Lost'),
        ('REISSUED', 'Reissued'),
    )
    
    # Identification
    certificate_number = models.CharField(
        "Certificate Number",
        max_length=20,
        unique=True,
        editable=False,
        help_text="Unique certificate number"
    )
    
    # Relationships
    member = models.ForeignKey(
        'members.Member',
        on_delete=models.CASCADE,
        related_name='share_certificates',
        help_text="Member who owns these shares"
    )
    
    share_capital = models.ForeignKey(
        ShareCapital,
        on_delete=models.PROTECT,
        help_text="Share capital configuration"
    )
    
    # Share Details
    shares_count = models.DecimalField(
        "Number of Shares",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Number of shares on this certificate"
    )
    
    share_price = models.DecimalField(
        "Share Price",
        max_digits=12,
        decimal_places=2,
        help_text="Price per share at time of issue"
    )
    
    total_value = models.DecimalField(
        "Total Value",
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total value of shares on certificate"
    )
    
    # Dates
    issue_date = models.DateField(
        "Issue Date",
        help_text="Date when certificate was issued"
    )
    
    # Status
    status = models.CharField(
        "Status",
        max_length=15,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        db_index=True
    )
    
    is_valid = models.BooleanField(
        "Is Valid",
        default=True,
        help_text="Whether this certificate is currently valid"
    )
    
    # Cancellation
    cancellation_date = models.DateField(
        "Cancellation Date",
        null=True,
        blank=True
    )
    
    cancellation_reason = models.TextField(
        "Cancellation Reason",
        null=True,
        blank=True
    )
    
    # Replacement
    replaced_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replaces',
        help_text="Certificate that replaced this one"
    )
    
    # Digital Certificate
    certificate_file = models.FileField(
        "Certificate File",
        upload_to='share_certificates/',
        null=True,
        blank=True,
        help_text="Digital copy of the certificate"
    )
    
    notes = models.TextField(
        "Notes",
        null=True,
        blank=True
    )
    
    def save(self, *args, **kwargs):
        """Calculate total value"""
        if self.shares_count and self.share_price:
            self.total_value = self.shares_count * self.share_price
        
        super().save(*args, **kwargs)
    
    @property
    def currency(self):
        """Get currency from SACCO configuration"""
        return get_base_currency()
    
    @property
    def formatted_total_value(self):
        """Get formatted total value"""
        return format_money(self.total_value)
    
    @property
    def formatted_share_price(self):
        """Get formatted share price"""
        return format_money(self.share_price)
    
    @property
    def is_active(self):
        """Check if certificate is active"""
        return self.status == 'ACTIVE' and self.is_valid
    
    def cancel(self, reason):
        """Cancel certificate"""
        if not self.is_active:
            return False, "Certificate is not active"
        
        self.status = 'CANCELLED'
        self.is_valid = False
        self.cancellation_date = timezone.now().date()
        self.cancellation_reason = reason
        self.save()
        
        logger.info(f"Share certificate {self.certificate_number} cancelled")
        return True, "Certificate cancelled"
    
    def __str__(self):
        return f"Certificate {self.certificate_number} - {self.member.get_full_name()} ({self.shares_count} shares)"
    
    class Meta:
        verbose_name = 'Share Certificate'
        verbose_name_plural = 'Share Certificates'
        ordering = ['-issue_date']
        indexes = [
            models.Index(fields=['member', 'status']),
            models.Index(fields=['certificate_number']),
            models.Index(fields=['status', 'is_valid']),
        ]


# =============================================================================
# SHARE TRANSFER REQUEST MODEL
# =============================================================================

class ShareTransferRequest(BaseModel):
    """Requests for share transfers between members"""
    
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )
    
    # Identification
    request_number = models.CharField(
        "Request Number",
        max_length=20,
        unique=True,
        editable=False,
        help_text="Unique request number"
    )
    
    # Transfer Details
    from_member = models.ForeignKey(
        'members.Member',
        on_delete=models.CASCADE,
        related_name='share_transfers_from',
        help_text="Member transferring shares"
    )
    
    to_member = models.ForeignKey(
        'members.Member',
        on_delete=models.CASCADE,
        related_name='share_transfers_to',
        help_text="Member receiving shares"
    )
    
    shares_count = models.DecimalField(
        "Number of Shares",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Number of shares to transfer"
    )
    
    share_price = models.DecimalField(
        "Share Price",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Agreed price per share"
    )
    
    total_amount = models.DecimalField(
        "Total Amount",
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total transfer value"
    )
    
    transfer_fee = models.DecimalField(
        "Transfer Fee",
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Fee for this transfer"
    )
    
    # Dates
    request_date = models.DateField(
        "Request Date",
        auto_now_add=True
    )
    
    approval_date = models.DateTimeField(
        "Approval Date",
        null=True,
        blank=True
    )
    
    completion_date = models.DateTimeField(
        "Completion Date",
        null=True,
        blank=True
    )
    
    # Status
    status = models.CharField(
        "Status",
        max_length=15,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )
    
    approved_by_id = models.CharField(
        "Approved By",
        max_length=50,
        null=True,
        blank=True,
        help_text="User ID who approved the transfer"
    )
    
    rejection_reason = models.TextField(
        "Rejection Reason",
        null=True,
        blank=True
    )
    
    # Transaction References
    transfer_out_transaction = models.ForeignKey(
        ShareTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transfer_out_requests',
        help_text="Transfer out transaction"
    )
    
    transfer_in_transaction = models.ForeignKey(
        ShareTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transfer_in_requests',
        help_text="Transfer in transaction"
    )
    
    reason = models.TextField(
        "Reason for Transfer",
        help_text="Reason for requesting transfer"
    )
    
    notes = models.TextField(
        "Notes",
        null=True,
        blank=True
    )
    
    def save(self, *args, **kwargs):
        """Calculate total amount"""
        if self.shares_count and self.share_price:
            self.total_amount = self.shares_count * self.share_price
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate transfer request"""
        super().clean()
        errors = {}
        
        if self.from_member == self.to_member:
            errors['to_member'] = 'Cannot transfer shares to the same member'
        
        if errors:
            raise ValidationError(errors)
    
    @property
    def currency(self):
        """Get currency from SACCO configuration"""
        return get_base_currency()
    
    @property
    def formatted_total_amount(self):
        """Get formatted total amount"""
        return format_money(self.total_amount)
    
    @property
    def is_pending(self):
        """Check if request is pending"""
        return self.status == 'PENDING'
    
    @property
    def is_approved(self):
        """Check if request is approved"""
        return self.status in ['APPROVED', 'COMPLETED']
    
    def approve(self, approved_by=None):
        """Approve transfer request"""
        if self.status != 'PENDING':
            return False, "Only pending requests can be approved"
        
        self.status = 'APPROVED'
        self.approval_date = timezone.now()
        if approved_by:
            self.approved_by_id = str(approved_by.id)
        self.save()
        
        logger.info(f"Share transfer request {self.request_number} approved")
        return True, "Transfer request approved"
    
    def reject(self, reason):
        """Reject transfer request"""
        if self.status != 'PENDING':
            return False, "Only pending requests can be rejected"
        
        self.status = 'REJECTED'
        self.rejection_reason = reason
        self.save()
        
        logger.info(f"Share transfer request {self.request_number} rejected")
        return True, "Transfer request rejected"
    
    def cancel(self):
        """Cancel transfer request"""
        if self.status not in ['PENDING', 'APPROVED']:
            return False, f"Cannot cancel request with status: {self.get_status_display()}"
        
        self.status = 'CANCELLED'
        self.save()
        
        logger.info(f"Share transfer request {self.request_number} cancelled")
        return True, "Transfer request cancelled"
    
    def __str__(self):
        return f"Transfer {self.request_number}: {self.from_member.get_full_name()} → {self.to_member.get_full_name()} ({self.shares_count} shares)"
    
    class Meta:
        verbose_name = 'Share Transfer Request'
        verbose_name_plural = 'Share Transfer Requests'
        ordering = ['-request_date']
        indexes = [
            models.Index(fields=['from_member', 'status']),
            models.Index(fields=['to_member', 'status']),
            models.Index(fields=['status', 'request_date']),
            models.Index(fields=['request_number']),
        ]