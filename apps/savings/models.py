# savings/models.py 

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
import uuid
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from django.db.models import Q, Sum, Count, F

from utils.models import BaseModel
from core.utils import get_base_currency, format_money, get_active_fiscal_period

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# SAVINGS PRODUCTS - CONFIGURATION FOR DIFFERENT SAVINGS TYPES
# =============================================================================

class SavingsProduct(BaseModel):
    """
    Savings products offered by the SACCO.
    Integrated with SaccoConfiguration for base currency and settings.
    """
    
    INTEREST_CALCULATION_METHODS = [
        ('SIMPLE', _('Simple Interest')),
        ('COMPOUND', _('Compound Interest')),
        ('AVERAGE_BALANCE', _('Average Balance')),
        ('MINIMUM_BALANCE', _('Minimum Balance')),
        ('TIERED', _('Tiered Interest')),
        ('DAILY_BALANCE', _('Daily Balance')),
    ]
    
    INTEREST_CALCULATION_FREQUENCY = [
        ('DAILY', _('Daily')),
        ('WEEKLY', _('Weekly')),
        ('MONTHLY', _('Monthly')),
        ('QUARTERLY', _('Quarterly')),
        ('ANNUALLY', _('Annually')),
    ]
    
    INTEREST_POSTING_FREQUENCY = [
        ('MONTHLY', _('Monthly')),
        ('QUARTERLY', _('Quarterly')),
        ('SEMI_ANNUALLY', _('Semi-Annually')),
        ('ANNUALLY', _('Annually')),
    ]
    
    # Basic Product Information
    name = models.CharField(
        _("Product Name"),
        max_length=100,
        help_text=_("Name of the savings product")
    )
    
    code = models.CharField(
        _("Product Code"),
        max_length=20,
        unique=True,
        help_text=_("Unique code for this savings product")
    )
    
    description = models.TextField(
        _("Description"),
        help_text=_("Detailed description of the savings product")
    )
    
    # Interest Configuration
    interest_rate = models.DecimalField(
        _("Interest Rate (%)"),
        max_digits=8,
        decimal_places=5,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text=_("Annual interest rate in percentage")
    )
    
    interest_calculation_method = models.CharField(
        _("Interest Calculation Method"),
        max_length=20,
        choices=INTEREST_CALCULATION_METHODS,
        default='SIMPLE'
    )
    
    interest_calculation_frequency = models.CharField(
        _("Interest Calculation Frequency"),
        max_length=15,
        choices=INTEREST_CALCULATION_FREQUENCY,
        default='MONTHLY'
    )
    
    interest_posting_frequency = models.CharField(
        _("Interest Posting Frequency"),
        max_length=15,
        choices=INTEREST_POSTING_FREQUENCY,
        default='MONTHLY'
    )
    
    # Balance Requirements
    minimum_opening_balance = models.DecimalField(
        _("Minimum Opening Balance"),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text=_("Minimum amount required to open account")
    )
    
    minimum_balance = models.DecimalField(
        _("Minimum Balance"),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text=_("Minimum balance to maintain")
    )
    
    maximum_balance = models.DecimalField(
        _("Maximum Balance"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text=_("Maximum balance allowed (blank for no limit)")
    )
    
    # Transaction Limits
    minimum_deposit_amount = models.DecimalField(
        _("Minimum Deposit Amount"),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    
    minimum_withdrawal_amount = models.DecimalField(
        _("Minimum Withdrawal Amount"),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    
    maximum_withdrawal_amount = models.DecimalField(
        _("Maximum Withdrawal Amount"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text=_("Maximum withdrawal amount (blank for no limit)")
    )
    
    # Overdraft Configuration
    allow_overdraft = models.BooleanField(
        _("Allow Overdraft"),
        default=False,
        help_text=_("Whether this product allows overdrafts")
    )
    
    overdraft_limit = models.DecimalField(
        _("Overdraft Limit"),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text=_("Maximum overdraft amount allowed")
    )
    
    overdraft_interest_rate = models.DecimalField(
        _("Overdraft Interest Rate (%)"),
        max_digits=8,
        decimal_places=5,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))]
    )
    
    # Fee Structure
    withdrawal_fee_flat = models.DecimalField(
        _("Withdrawal Fee (Flat)"),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    
    withdrawal_fee_percentage = models.DecimalField(
        _("Withdrawal Fee (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))]
    )
    
    deposit_fee_flat = models.DecimalField(
        _("Deposit Fee (Flat)"),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    
    deposit_fee_percentage = models.DecimalField(
        _("Deposit Fee (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))]
    )
    
    # Account Maintenance
    dormancy_period_days = models.PositiveIntegerField(
        _("Dormancy Period (Days)"),
        default=90,
        validators=[MinValueValidator(1)],
        help_text=_("Days of inactivity before account becomes dormant")
    )
    
    account_maintenance_fee = models.DecimalField(
        _("Account Maintenance Fee"),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    
    maintenance_fee_frequency = models.CharField(
        _("Maintenance Fee Frequency"),
        max_length=15,
        choices=[
            ('NONE', _('None')),
            ('MONTHLY', _('Monthly')),
            ('QUARTERLY', _('Quarterly')),
            ('ANNUALLY', _('Annually')),
        ],
        default='NONE'
    )
    
    # Fixed Deposit Configuration
    is_fixed_deposit = models.BooleanField(
        _("Is Fixed Deposit"),
        default=False,
        help_text=_("Whether this is a fixed deposit product")
    )
    
    minimum_term_days = models.PositiveIntegerField(
        _("Minimum Term (Days)"),
        default=0,
        help_text=_("Minimum term in days for fixed deposits")
    )
    
    maximum_term_days = models.PositiveIntegerField(
        _("Maximum Term (Days)"),
        null=True,
        blank=True,
        help_text=_("Maximum term in days (blank for no limit)")
    )
    
    early_withdrawal_penalty_rate = models.DecimalField(
        _("Early Withdrawal Penalty (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text=_("Penalty as percentage of withdrawn amount")
    )
    
    # Product Status
    is_active = models.BooleanField(
        _("Is Active"),
        default=True,
        help_text=_("Whether this product is available for new accounts")
    )
    
    is_group_product = models.BooleanField(
        _("Is Group Product"),
        default=False,
        help_text=_("Whether this is a group savings product")
    )
    
    requires_approval = models.BooleanField(
        _("Requires Approval"),
        default=False,
        help_text=_("Whether new accounts require approval")
    )
    
    is_main_account = models.BooleanField(
        _("Is Main Account Product"),
        default=False,
        help_text=_("Whether this is the primary/main savings product")
    )
    
    # GL Integration
    gl_account_code = models.CharField(
        _("GL Account Code"),
        max_length=20,
        null=True,
        blank=True,
        help_text=_("General Ledger account code")
    )
    
    # Product Limits
    maximum_accounts_per_member = models.PositiveIntegerField(
        _("Maximum Accounts Per Member"),
        default=1,
        validators=[MinValueValidator(1)],
        help_text=_("Maximum number of accounts of this type per member")
    )
    
    @property
    def currency(self):
        """Get the currency for this product from SACCO configuration"""
        return get_base_currency()
    
    @property
    def formatted_minimum_balance(self):
        """Get formatted minimum balance"""
        return format_money(self.minimum_balance)
    
    @property
    def formatted_minimum_opening_balance(self):
        """Get formatted minimum opening balance"""
        return format_money(self.minimum_opening_balance)
    
    @property
    def formatted_maximum_balance(self):
        """Get formatted maximum balance"""
        return format_money(self.maximum_balance) if self.maximum_balance else _("No limit")
    
    def calculate_withdrawal_fee(self, amount):
        """Calculate withdrawal fee for given amount"""
        try:
            amount_decimal = Decimal(str(amount))
            flat_fee = self.withdrawal_fee_flat
            percentage_fee = (amount_decimal * self.withdrawal_fee_percentage) / Decimal('100')
            return flat_fee + percentage_fee
        except (ValueError, TypeError):
            return Decimal('0.00')
    
    def calculate_deposit_fee(self, amount):
        """Calculate deposit fee for given amount"""
        try:
            amount_decimal = Decimal(str(amount))
            flat_fee = self.deposit_fee_flat
            percentage_fee = (amount_decimal * self.deposit_fee_percentage) / Decimal('100')
            return flat_fee + percentage_fee
        except (ValueError, TypeError):
            return Decimal('0.00')
    
    def get_applicable_interest_rate(self, balance=None):
        """Get applicable interest rate based on balance tiers"""
        if self.interest_calculation_method != 'TIERED' or not balance:
            return self.interest_rate
        
        try:
            balance_decimal = Decimal(str(balance))
            
            # Check product-level tiers
            tier = self.interest_tiers.filter(
                is_active=True,
                min_balance__lte=balance_decimal
            ).filter(
                Q(max_balance__isnull=True) | Q(max_balance__gte=balance_decimal)
            ).order_by('-min_balance').first()
            
            return tier.interest_rate if tier else self.interest_rate
        except (ValueError, TypeError):
            return self.interest_rate
    
    @classmethod
    def get_active_products(cls):
        """Get all active savings products"""
        return cls.objects.filter(is_active=True).order_by('name')
    
    @classmethod
    def get_main_savings_product(cls):
        """Get the main/primary savings product"""
        return cls.objects.filter(is_main_account=True, is_active=True).first()
    
    def clean(self):
        """Validate product configuration"""
        super().clean()
        errors = {}
        
        if self.minimum_balance > self.minimum_opening_balance:
            errors['minimum_balance'] = _("Minimum balance cannot be greater than minimum opening balance")
        
        if self.maximum_balance and self.maximum_balance < self.minimum_opening_balance:
            errors['maximum_balance'] = _("Maximum balance must be greater than minimum opening balance")
        
        if self.is_fixed_deposit and self.minimum_term_days <= 0:
            errors['minimum_term_days'] = _("Fixed deposits must have a minimum term")
        
        if self.maximum_term_days and self.minimum_term_days > self.maximum_term_days:
            errors['maximum_term_days'] = _("Maximum term must be greater than minimum term")
        
        if errors:
            raise ValidationError(errors)
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    class Meta:
        verbose_name = _("Savings Product")
        verbose_name_plural = _("Savings Products")
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active', 'name']),
            models.Index(fields=['code']),
            models.Index(fields=['is_main_account']),
        ]


# =============================================================================
# INTEREST TIER MODEL
# =============================================================================

class InterestTier(BaseModel):
    """Interest rate tiers for tiered savings products"""
    
    savings_product = models.ForeignKey(
        SavingsProduct,
        on_delete=models.CASCADE,
        related_name='interest_tiers',
        help_text=_("Savings product this tier belongs to")
    )
    
    tier_name = models.CharField(
        _("Tier Name"),
        max_length=50,
        help_text=_("Name of this interest tier")
    )
    
    min_balance = models.DecimalField(
        _("Minimum Balance"),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    
    max_balance = models.DecimalField(
        _("Maximum Balance"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text=_("Maximum balance for this tier (blank for no upper limit)")
    )
    
    interest_rate = models.DecimalField(
        _("Interest Rate (%)"),
        max_digits=8,
        decimal_places=5,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))]
    )
    
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    
    @property
    def formatted_min_balance(self):
        """Get formatted minimum balance"""
        return format_money(self.min_balance)
    
    @property
    def formatted_max_balance(self):
        """Get formatted maximum balance"""
        return format_money(self.max_balance) if self.max_balance else _("No limit")
    
    def clean(self):
        """Validate tier"""
        super().clean()
        errors = {}
        
        if self.max_balance and self.min_balance >= self.max_balance:
            errors['max_balance'] = _("Maximum balance must be greater than minimum balance")
        
        if errors:
            raise ValidationError(errors)
    
    def __str__(self):
        max_display = self.formatted_max_balance
        return f"{self.tier_name}: {self.formatted_min_balance} - {max_display} ({self.interest_rate}%)"
    
    class Meta:
        verbose_name = _("Interest Tier")
        verbose_name_plural = _("Interest Tiers")
        ordering = ['savings_product', 'min_balance']
        indexes = [
            models.Index(fields=['savings_product', 'is_active']),
            models.Index(fields=['min_balance']),
        ]


# =============================================================================
# SAVINGS ACCOUNTS - MEMBER ACCOUNT MANAGEMENT
# =============================================================================

class SavingsAccount(BaseModel):
    """Individual member savings accounts"""
    
    STATUS_CHOICES = [
        ('ACTIVE', _('Active')),
        ('DORMANT', _('Dormant')),
        ('FROZEN', _('Frozen')),
        ('CLOSED', _('Closed')),
        ('PENDING_APPROVAL', _('Pending Approval')),
        ('SUSPENDED', _('Suspended')),
    ]
    
    # Account Identification
    account_number = models.CharField(
        _("Account Number"),
        max_length=30,
        unique=True,
        help_text=_("Unique account number")
    )
    
    # Relationships - Using string references for ForeignKeys
    member = models.ForeignKey(
        'members.Member',
        on_delete=models.CASCADE,
        related_name='savings_accounts',
        help_text=_("Member who owns this account")
    )
    
    group = models.ForeignKey(
        'members.MemberGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='group_savings_accounts',
        help_text=_("Group this account belongs to (if any)")
    )
    
    savings_product = models.ForeignKey(
        SavingsProduct,
        on_delete=models.PROTECT,
        related_name='accounts',
        help_text=_("Savings product type")
    )
    
    # Balance Information
    current_balance = models.DecimalField(
        _("Current Balance"),
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    available_balance = models.DecimalField(
        _("Available Balance"),
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Balance available for withdrawal (current - holds)")
    )
    
    hold_amount = models.DecimalField(
        _("Hold Amount"),
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Amount on hold (not available for withdrawal)")
    )
    
    overdraft_amount = models.DecimalField(
        _("Overdraft Amount"),
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Current overdraft balance")
    )
    
    accrued_interest = models.DecimalField(
        _("Accrued Interest"),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Interest earned but not yet posted")
    )
    
    # Account Status and Dates
    status = models.CharField(
        _("Account Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING_APPROVAL',
        db_index=True
    )
    
    opening_date = models.DateField(
        _("Opening Date"),
        default=timezone.now,
        help_text=_("Date when account was opened")
    )
    
    activated_date = models.DateField(
        _("Activated Date"),
        null=True,
        blank=True,
        help_text=_("Date when account was activated")
    )
    
    closure_date = models.DateField(
        _("Closure Date"),
        null=True,
        blank=True,
        help_text=_("Date when account was closed")
    )
    
    maturity_date = models.DateField(
        _("Maturity Date"),
        null=True,
        blank=True,
        help_text=_("For fixed deposits - when deposit matures")
    )
    
    # Interest Tracking
    last_interest_calculated_date = models.DateField(
        _("Last Interest Calculated"),
        null=True,
        blank=True
    )
    
    last_interest_posted_date = models.DateField(
        _("Last Interest Posted"),
        null=True,
        blank=True
    )
    
    total_interest_earned = models.DecimalField(
        _("Total Interest Earned"),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Total interest earned since opening")
    )
    
    # Fixed Deposit Specific Fields
    is_fixed_deposit = models.BooleanField(
        _("Is Fixed Deposit"),
        default=False
    )
    
    term_length_days = models.PositiveIntegerField(
        _("Term Length (Days)"),
        null=True,
        blank=True,
        help_text=_("Term length for fixed deposits")
    )
    
    fixed_deposit_amount = models.DecimalField(
        _("Fixed Deposit Amount"),
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Initial fixed deposit amount")
    )
    
    auto_renew = models.BooleanField(
        _("Auto Renew"),
        default=False,
        help_text=_("Whether to automatically renew fixed deposit")
    )
    
    # Account Settings
    overdraft_limit = models.DecimalField(
        _("Overdraft Limit"),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    overdraft_expiry_date = models.DateField(
        _("Overdraft Expiry Date"),
        null=True,
        blank=True
    )
    
    # UUID for external integrations
    account_uuid = models.UUIDField(
        _("Account UUID"),
        default=uuid.uuid4,
        editable=False,
        unique=True
    )
    
    @property
    def currency(self):
        """Get account currency from SACCO configuration"""
        return get_base_currency()
    
    @property
    def formatted_current_balance(self):
        """Get formatted current balance"""
        return format_money(self.current_balance)
    
    @property
    def formatted_available_balance(self):
        """Get formatted available balance"""
        return format_money(self.available_balance)
    
    @property
    def formatted_accrued_interest(self):
        """Get formatted accrued interest"""
        return format_money(self.accrued_interest)
    
    @property
    def last_transaction_date(self):
        """Get last transaction date for this account"""
        last_transaction = self.transactions.order_by('-transaction_date').first()
        return last_transaction.transaction_date.date() if last_transaction else None
    
    @property
    def effective_status(self):
        """Get effective account status considering member status"""
        if self.status in ['CLOSED', 'FROZEN', 'SUSPENDED']:
            return self.status
        
        # Check member status
        if hasattr(self.member, 'status'):
            if self.member.status == 'SUSPENDED':
                return 'FROZEN'
            elif self.member.status in ['DECEASED', 'TERMINATED']:
                return 'CLOSED'
            elif self.member.status == 'BLACKLISTED':
                return 'FROZEN'
        
        return self.status
    
    @property
    def is_matured(self):
        """Check if fixed deposit has matured"""
        if not self.is_fixed_deposit or not self.maturity_date:
            return False
        return self.maturity_date <= timezone.now().date()
    
    @property
    def days_to_maturity(self):
        """Days until fixed deposit matures"""
        if not self.is_fixed_deposit or not self.maturity_date:
            return None
        
        today = timezone.now().date()
        if self.maturity_date <= today:
            return 0
        
        return (self.maturity_date - today).days
    
    @property
    def account_age_days(self):
        """Get account age in days"""
        return (timezone.now().date() - self.opening_date).days
    
    @property
    def is_dormant_eligible(self):
        """Check if account is eligible to be marked as dormant"""
        if not self.last_transaction_date:
            return False
        
        days_inactive = (timezone.now().date() - self.last_transaction_date).days
        return days_inactive >= self.savings_product.dormancy_period_days
    
    @classmethod
    def get_member_total_balance(cls, member):
        """Get total balance across all member's savings accounts"""
        total = cls.objects.filter(
            member=member,
            status__in=['ACTIVE', 'DORMANT']
        ).aggregate(
            total=Sum('current_balance')
        )['total']
        
        return Decimal(total or 0)
    
    @classmethod
    def get_member_primary_account(cls, member):
        """Get member's primary/main savings account"""
        main_account = cls.objects.filter(
            member=member,
            savings_product__is_main_account=True,
            status__in=['ACTIVE', 'DORMANT']
        ).first()
        
        if main_account:
            return main_account
        
        return cls.objects.filter(
            member=member,
            status__in=['ACTIVE', 'DORMANT']
        ).order_by('opening_date').first()
    
    def approve_account(self):
        """Approve pending account"""
        if self.status != 'PENDING_APPROVAL':
            return False, _("Account is not pending approval")
        
        if hasattr(self.member, 'status') and self.member.status != 'ACTIVE':
            return False, _("Member must be active to approve account")
        
        if self.current_balance < self.savings_product.minimum_opening_balance:
            min_bal_formatted = format_money(self.savings_product.minimum_opening_balance)
            return False, _(f"Minimum opening balance of {min_bal_formatted} required")
        
        self.status = 'ACTIVE'
        self.activated_date = timezone.now().date()
        self.save()
        
        logger.info(f"Account {self.account_number} approved")
        return True, _("Account approved successfully")
    
    def is_withdrawal_allowed(self, amount):
        """Basic withdrawal validation"""
        try:
            amount_decimal = Decimal(str(amount))
        except (ValueError, TypeError):
            return False, _("Invalid amount")
        
        if self.effective_status not in ['ACTIVE', 'DORMANT']:
            return False, f"Account status is {self.get_status_display()}"
        
        if amount_decimal > self.available_balance:
            return False, _("Insufficient available balance")
        
        if amount_decimal < self.savings_product.minimum_withdrawal_amount:
            min_formatted = format_money(self.savings_product.minimum_withdrawal_amount)
            return False, _(f"Amount below minimum withdrawal of {min_formatted}")
        
        if self.savings_product.maximum_withdrawal_amount:
            if amount_decimal > self.savings_product.maximum_withdrawal_amount:
                max_formatted = format_money(self.savings_product.maximum_withdrawal_amount)
                return False, _(f"Amount exceeds maximum withdrawal of {max_formatted}")
        
        return True, _("Withdrawal allowed")
    
    def is_deposit_allowed(self, amount):
        """Basic deposit validation"""
        try:
            amount_decimal = Decimal(str(amount))
        except (ValueError, TypeError):
            return False, _("Invalid amount")
        
        if self.effective_status not in ['ACTIVE', 'DORMANT', 'PENDING_APPROVAL']:
            return False, f"Account status is {self.get_status_display()}"
        
        if amount_decimal < self.savings_product.minimum_deposit_amount:
            min_formatted = format_money(self.savings_product.minimum_deposit_amount)
            return False, _(f"Amount below minimum deposit of {min_formatted}")
        
        if self.savings_product.maximum_balance:
            if (self.current_balance + amount_decimal) > self.savings_product.maximum_balance:
                return False, _("Deposit would exceed maximum balance limit")
        
        return True, _("Deposit allowed")
    
    def update_available_balance(self):
        """Update available balance based on current balance and holds"""
        self.available_balance = max(self.current_balance - self.hold_amount, Decimal('0.00'))
        self.save(update_fields=['available_balance'])
    
    def __str__(self):
        return f"{self.account_number} - {self.member.get_full_name()}"
    
    class Meta:
        verbose_name = _("Savings Account")
        verbose_name_plural = _("Savings Accounts")
        ordering = ['-opening_date', 'account_number']
        indexes = [
            models.Index(fields=['account_number']),
            models.Index(fields=['member', 'status']),
            models.Index(fields=['savings_product', 'is_fixed_deposit']),
            models.Index(fields=['status', 'opening_date']),
        ]


# =============================================================================
# SAVINGS TRANSACTIONS
# =============================================================================

class SavingsTransaction(BaseModel):
    """Transactions on savings accounts"""
    
    TRANSACTION_TYPES = [
        ('DEPOSIT', _('Deposit')),
        ('WITHDRAWAL', _('Withdrawal')),
        ('TRANSFER_IN', _('Transfer In')),
        ('TRANSFER_OUT', _('Transfer Out')),
        ('INTEREST', _('Interest')),
        ('FEE', _('Fee')),
        ('TAX', _('Tax')),
        ('ADJUSTMENT', _('Adjustment')),
        ('REVERSAL', _('Reversal')),
        ('DIVIDEND', _('Dividend')),
        ('MAINTENANCE_FEE', _('Maintenance Fee')),
    ]
    
    # Transaction Identification
    transaction_id = models.CharField(
        _("Transaction ID"),
        max_length=30,
        unique=True,
        help_text=_("Unique transaction identifier")
    )
    
    # Core Transaction Details
    account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.CASCADE,
        related_name='transactions',
        help_text=_("Savings account this transaction belongs to")
    )
    
    transaction_type = models.CharField(
        _("Transaction Type"),
        max_length=20,
        choices=TRANSACTION_TYPES,
        db_index=True
    )
    
    amount = models.DecimalField(
        _("Transaction Amount"),
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    fees = models.DecimalField(
        _("Fees"),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    tax_amount = models.DecimalField(
        _("Tax Amount"),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Transaction Timing
    transaction_date = models.DateTimeField(
        _("Transaction Date"),
        default=timezone.now
    )
    
    post_date = models.DateField(
        _("Post Date"),
        default=timezone.now,
        help_text=_("Date transaction is posted to account")
    )
    
    value_date = models.DateField(
        _("Value Date"),
        default=timezone.now,
        help_text=_("Date from which interest is calculated")
    )
    
    # Payment Information
    payment_method = models.ForeignKey(
        'core.PaymentMethod',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='savings_transactions'
    )
    
    reference_number = models.CharField(
        _("Reference Number"),
        max_length=100,
        null=True,
        blank=True,
        help_text=_("External reference number (e.g., mobile money ref)")
    )
    
    description = models.TextField(
        _("Description"),
        null=True,
        blank=True
    )
    
    # Transfer Information
    linked_account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linked_transactions',
        help_text=_("Destination account for transfers")
    )
    
    linked_transaction = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linked_to',
        help_text=_("Linked transaction for transfers")
    )
    
    # Balance Information
    running_balance = models.DecimalField(
        _("Running Balance"),
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Account balance after this transaction")
    )
    
    # Financial Period Integration
    financial_period = models.ForeignKey(
        'core.FiscalPeriod',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='savings_transactions'
    )
    
    # Reversal Information
    is_reversed = models.BooleanField(
        _("Is Reversed"),
        default=False
    )
    
    reversal_reason = models.TextField(
        _("Reversal Reason"),
        null=True,
        blank=True
    )
    
    reversal_date = models.DateTimeField(
        _("Reversal Date"),
        null=True,
        blank=True
    )
    
    reversed_by_id = models.CharField(
        _("Reversed By"),
        max_length=50,
        null=True,
        blank=True,
        help_text=_("User ID who reversed the transaction")
    )
    
    original_transaction = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reversal_transactions',
        help_text=_("Original transaction being reversed")
    )
    
    def save(self, *args, **kwargs):
        """Generate transaction ID and set financial period"""
        if not self.transaction_id:
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            self.transaction_id = f"SAV-{timestamp}"
        
        # Set financial period if not set
        if not self.financial_period:
            self.financial_period = get_active_fiscal_period()
        
        super().save(*args, **kwargs)
    
    @property
    def currency(self):
        """Get currency from SACCO configuration"""
        return get_base_currency()
    
    @property
    def net_amount(self):
        """Get net transaction amount (amount - fees - taxes)"""
        if self.transaction_type in ['WITHDRAWAL', 'TRANSFER_OUT', 'FEE', 'TAX']:
            return self.amount - self.fees - self.tax_amount
        return self.amount
    
    @property
    def total_amount(self):
        """Get total transaction amount (amount + fees + taxes)"""
        if self.transaction_type in ['DEPOSIT', 'TRANSFER_IN']:
            return self.amount - self.fees - self.tax_amount
        return self.amount + self.fees + self.tax_amount
    
    @property
    def formatted_amount(self):
        """Get formatted transaction amount"""
        return format_money(self.amount)
    
    @property
    def formatted_running_balance(self):
        """Get formatted running balance"""
        return format_money(self.running_balance)
    
    def reverse(self, reason):
        """Reverse this transaction"""
        if self.is_reversed:
            return False, _("Transaction is already reversed")
        
        self.is_reversed = True
        self.reversal_reason = reason
        self.reversal_date = timezone.now()
        self.save()
        
        logger.info(f"Transaction {self.transaction_id} reversed")
        return True, _("Transaction reversed successfully")
    
    def __str__(self):
        return f"{self.transaction_id} - {self.get_transaction_type_display()} of {format_money(self.amount)}"
    
    class Meta:
        verbose_name = _("Savings Transaction")
        verbose_name_plural = _("Savings Transactions")
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['transaction_id']),
            models.Index(fields=['account', 'transaction_date']),
            models.Index(fields=['transaction_type', 'post_date']),
            models.Index(fields=['is_reversed']),
            models.Index(fields=['financial_period']),
        ]


# =============================================================================
# INTEREST CALCULATIONS
# =============================================================================

class InterestCalculation(BaseModel):
    """Record of interest calculations for savings accounts"""
    
    account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.CASCADE,
        related_name='interest_calculations',
        help_text=_("Account this calculation is for")
    )
    
    calculation_date = models.DateField(
        _("Calculation Date"),
        help_text=_("Date when interest was calculated")
    )
    
    period_start_date = models.DateField(
        _("Period Start Date")
    )
    
    period_end_date = models.DateField(
        _("Period End Date")
    )
    
    financial_period = models.ForeignKey(
        'core.FiscalPeriod',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='interest_calculations'
    )
    
    calculation_method = models.CharField(
        _("Calculation Method"),
        max_length=20,
        choices=SavingsProduct.INTEREST_CALCULATION_METHODS
    )
    
    # Balance information
    average_balance = models.DecimalField(
        _("Average Balance"),
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    opening_balance = models.DecimalField(
        _("Opening Balance"),
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    closing_balance = models.DecimalField(
        _("Closing Balance"),
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Interest calculation
    interest_rate = models.DecimalField(
        _("Interest Rate (%)"),
        max_digits=8,
        decimal_places=5
    )
    
    days_calculated = models.PositiveIntegerField(
        _("Days Calculated")
    )
    
    gross_interest = models.DecimalField(
        _("Gross Interest"),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Tax
    tax_rate = models.DecimalField(
        _("Tax Rate (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    withholding_tax = models.DecimalField(
        _("Withholding Tax"),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    net_interest = models.DecimalField(
        _("Net Interest"),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Posting status
    is_posted = models.BooleanField(
        _("Is Posted"),
        default=False
    )
    
    posted_date = models.DateField(
        _("Posted Date"),
        null=True,
        blank=True
    )
    
    transaction = models.ForeignKey(
        SavingsTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='interest_calculation'
    )
    
    @property
    def currency(self):
        """Get currency from SACCO configuration"""
        return get_base_currency()
    
    @property
    def formatted_gross_interest(self):
        """Get formatted gross interest"""
        return format_money(self.gross_interest)
    
    @property
    def formatted_net_interest(self):
        """Get formatted net interest"""
        return format_money(self.net_interest)
    
    def __str__(self):
        return f"Interest for {self.account.account_number} - {self.calculation_date}"
    
    class Meta:
        verbose_name = _("Interest Calculation")
        verbose_name_plural = _("Interest Calculations")
        ordering = ['-calculation_date']
        indexes = [
            models.Index(fields=['account', 'calculation_date']),
            models.Index(fields=['is_posted', 'posted_date']),
            models.Index(fields=['financial_period']),
        ]


# =============================================================================
# STANDING ORDERS
# =============================================================================

class StandingOrder(BaseModel):
    """Standing orders for automated transfers"""
    
    FREQUENCY_CHOICES = [
        ('DAILY', _('Daily')),
        ('WEEKLY', _('Weekly')),
        ('BIWEEKLY', _('Bi-Weekly')),
        ('MONTHLY', _('Monthly')),
        ('QUARTERLY', _('Quarterly')),
        ('ANNUALLY', _('Annually')),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', _('Active')),
        ('PAUSED', _('Paused')),
        ('COMPLETED', _('Completed')),
        ('FAILED', _('Failed')),
        ('CANCELLED', _('Cancelled')),
        ('PENDING_APPROVAL', _('Pending Approval')),
    ]
    
    # Source and destination
    source_account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.CASCADE,
        related_name='standing_orders_out',
        help_text=_("Account to transfer from")
    )
    
    destination_account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='standing_orders_in',
        help_text=_("Account to transfer to")
    )
    
    # Transfer details
    amount = models.DecimalField(
        _("Transfer Amount"),
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    frequency = models.CharField(
        _("Frequency"),
        max_length=15,
        choices=FREQUENCY_CHOICES
    )
    
    start_date = models.DateField(
        _("Start Date")
    )
    
    end_date = models.DateField(
        _("End Date"),
        null=True,
        blank=True,
        help_text=_("Leave blank for indefinite standing order")
    )
    
    next_run_date = models.DateField(
        _("Next Run Date")
    )
    
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING_APPROVAL',
        db_index=True
    )
    
    description = models.TextField(
        _("Description"),
        null=True,
        blank=True
    )
    
    # Execution tracking
    execution_count = models.PositiveIntegerField(
        _("Execution Count"),
        default=0
    )
    
    last_execution_date = models.DateField(
        _("Last Execution Date"),
        null=True,
        blank=True
    )
    
    last_execution_status = models.CharField(
        _("Last Execution Status"),
        max_length=20,
        null=True,
        blank=True
    )
    
    last_failure_reason = models.TextField(
        _("Last Failure Reason"),
        null=True,
        blank=True
    )
    
    @property
    def currency(self):
        """Get currency from SACCO configuration"""
        return get_base_currency()
    
    @property
    def formatted_amount(self):
        """Get formatted transfer amount"""
        return format_money(self.amount)
    
    def calculate_next_run_date(self):
        """Calculate the next run date based on frequency"""
        if not self.last_execution_date:
            return self.start_date
        
        last_date = self.last_execution_date
        
        if self.frequency == 'DAILY':
            return last_date + timedelta(days=1)
        elif self.frequency == 'WEEKLY':
            return last_date + timedelta(days=7)
        elif self.frequency == 'BIWEEKLY':
            return last_date + timedelta(days=14)
        elif self.frequency == 'MONTHLY':
            return last_date + relativedelta(months=1)
        elif self.frequency == 'QUARTERLY':
            return last_date + relativedelta(months=3)
        elif self.frequency == 'ANNUALLY':
            return last_date + relativedelta(years=1)
        
        return None
    
    @classmethod
    def get_due_standing_orders(cls, execution_date=None):
        """Get standing orders due for execution"""
        if execution_date is None:
            execution_date = timezone.now().date()
        
        return cls.objects.filter(
            status='ACTIVE',
            next_run_date__lte=execution_date
        ).order_by('next_run_date')
    
    def activate(self):
        """Activate standing order"""
        if self.status != 'PENDING_APPROVAL':
            return False, _("Only pending orders can be activated")
        
        self.status = 'ACTIVE'
        self.save()
        
        logger.info(f"Standing order activated: {self}")
        return True, _("Standing order activated")
    
    def pause(self):
        """Pause standing order"""
        if self.status != 'ACTIVE':
            return False, _("Only active orders can be paused")
        
        self.status = 'PAUSED'
        self.save()
        
        logger.info(f"Standing order paused: {self}")
        return True, _("Standing order paused")
    
    def resume(self):
        """Resume paused standing order"""
        if self.status != 'PAUSED':
            return False, _("Only paused orders can be resumed")
        
        self.status = 'ACTIVE'
        self.save()
        
        logger.info(f"Standing order resumed: {self}")
        return True, _("Standing order resumed")
    
    def __str__(self):
        return f"Standing Order: {self.source_account.account_number} -> {format_money(self.amount)} {self.get_frequency_display()}"
    
    class Meta:
        verbose_name = _("Standing Order")
        verbose_name_plural = _("Standing Orders")
        ordering = ['next_run_date']
        indexes = [
            models.Index(fields=['status', 'next_run_date']),
            models.Index(fields=['source_account', 'status']),
        ]


# =============================================================================
# SAVINGS GOALS
# =============================================================================

class SavingsGoal(BaseModel):
    """Savings goals for members"""
    
    GOAL_TYPE_CHOICES = [
        ('EDUCATION', _('Education')),
        ('HOUSING', _('Housing/Property')),
        ('BUSINESS', _('Business')),
        ('EMERGENCY', _('Emergency Fund')),
        ('RETIREMENT', _('Retirement')),
        ('TRAVEL', _('Travel')),
        ('WEDDING', _('Wedding')),
        ('VEHICLE', _('Vehicle Purchase')),
        ('OTHER', _('Other')),
    ]
    
    account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.CASCADE,
        related_name='savings_goals',
        help_text=_("Savings account linked to this goal")
    )
    
    name = models.CharField(
        _("Goal Name"),
        max_length=100
    )
    
    description = models.TextField(
        _("Description"),
        null=True,
        blank=True
    )
    
    goal_type = models.CharField(
        _("Goal Type"),
        max_length=20,
        choices=GOAL_TYPE_CHOICES
    )
    
    target_amount = models.DecimalField(
        _("Target Amount"),
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    current_amount = models.DecimalField(
        _("Current Amount"),
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    start_date = models.DateField(
        _("Start Date"),
        default=timezone.now
    )
    
    target_date = models.DateField(
        _("Target Date")
    )
    
    is_achieved = models.BooleanField(
        _("Is Achieved"),
        default=False
    )
    
    achievement_date = models.DateField(
        _("Achievement Date"),
        null=True,
        blank=True
    )
    
    progress_percentage = models.DecimalField(
        _("Progress Percentage"),
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    @property
    def currency(self):
        """Get currency from SACCO configuration"""
        return get_base_currency()
    
    @property
    def formatted_target_amount(self):
        """Get formatted target amount"""
        return format_money(self.target_amount)
    
    @property
    def formatted_current_amount(self):
        """Get formatted current amount"""
        return format_money(self.current_amount)
    
    @property
    def remaining_amount(self):
        """Get remaining amount to reach goal"""
        return max(self.target_amount - self.current_amount, Decimal('0.00'))
    
    @property
    def formatted_remaining_amount(self):
        """Get formatted remaining amount"""
        return format_money(self.remaining_amount)
    
    @property
    def days_remaining(self):
        """Get days remaining to target date"""
        if self.is_achieved:
            return 0
        
        today = timezone.now().date()
        if today >= self.target_date:
            return 0
        
        return (self.target_date - today).days
    
    def update_progress(self):
        """Update progress percentage"""
        if self.target_amount > 0:
            self.progress_percentage = (self.current_amount / self.target_amount) * 100
            
            # Check if goal is achieved
            if self.progress_percentage >= 100 and not self.is_achieved:
                self.is_achieved = True
                self.achievement_date = timezone.now().date()
        else:
            self.progress_percentage = Decimal('0.00')
        
        self.save()
    
    def clean(self):
        """Validate goal"""
        super().clean()
        errors = {}
        
        if self.target_date and self.start_date:
            if self.target_date <= self.start_date:
                errors['target_date'] = _("Target date must be after start date")
        
        if errors:
            raise ValidationError(errors)
    
    def __str__(self):
        return f"{self.name} - {format_money(self.current_amount)}/{format_money(self.target_amount)} ({self.progress_percentage:.1f}%)"
    
    class Meta:
        verbose_name = _("Savings Goal")
        verbose_name_plural = _("Savings Goals")
        ordering = ['target_date']
        indexes = [
            models.Index(fields=['account', 'is_achieved']),
            models.Index(fields=['target_date']),
        ]