# savings/models.py 

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from djmoney.models.fields import MoneyField
from djmoney.money import Money
from decimal import Decimal
import uuid
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from django.db.models import Q, Sum, Count, F

from sacco_settings.models import (
    BaseModel, 
    SaccoConfiguration, 
    FinancialPeriod, 
    PaymentMethod,
    TaxRate,
    get_sacco_config,
    format_money,
    get_base_currency
)
from members.models import Member, MemberGroup
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
    
    MAINTENANCE_FREQUENCY_CHOICES = [
        ('NONE', _('None')),
        ('WEEKLY', _('Weekly')),
        ('MONTHLY', _('Monthly')),
        ('QUARTERLY', _('Quarterly')),
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
        validators=[MinValueValidator(0), MaxValueValidator(100)],
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
    minimum_opening_balance = MoneyField(
        _("Minimum Opening Balance"),
        max_digits=12,
        decimal_places=2,
        default_currency='UGX',
        help_text=_("Minimum amount required to open account")
    )
    
    minimum_balance = MoneyField(
        _("Minimum Balance"),
        max_digits=12,
        decimal_places=2,
        default_currency='UGX',
        help_text=_("Minimum balance to maintain")
    )
    
    maximum_balance = MoneyField(
        _("Maximum Balance"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        default_currency='UGX',
        help_text=_("Maximum balance allowed (blank for no limit)")
    )
    
    # Transaction Limits
    minimum_deposit_amount = MoneyField(
        _("Minimum Deposit Amount"),
        max_digits=12,
        decimal_places=2,
        default_currency='UGX'
    )
    
    minimum_withdrawal_amount = MoneyField(
        _("Minimum Withdrawal Amount"),
        max_digits=12,
        decimal_places=2,
        default_currency='UGX'
    )
    
    maximum_withdrawal_amount = MoneyField(
        _("Maximum Withdrawal Amount"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        default_currency='UGX',
        help_text=_("Maximum withdrawal amount (blank for no limit)")
    )
    
    # Overdraft Configuration
    allow_overdraft = models.BooleanField(
        _("Allow Overdraft"),
        default=False,
        help_text=_("Whether this product allows overdrafts")
    )
    
    overdraft_limit = MoneyField(
        _("Overdraft Limit"),
        max_digits=12,
        decimal_places=2,
        default=Money(0, 'UGX'),
        help_text=_("Maximum overdraft amount allowed")
    )
    
    overdraft_interest_rate = models.DecimalField(
        _("Overdraft Interest Rate (%)"),
        max_digits=8,
        decimal_places=5,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Fee Structure
    withdrawal_fee_flat = MoneyField(
        _("Withdrawal Fee (Flat)"),
        max_digits=10,
        decimal_places=2,
        default=Money(0, 'UGX')
    )
    
    withdrawal_fee_percentage = models.DecimalField(
        _("Withdrawal Fee (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    deposit_fee_flat = MoneyField(
        _("Deposit Fee (Flat)"),
        max_digits=10,
        decimal_places=2,
        default=Money(0, 'UGX')
    )
    
    deposit_fee_percentage = models.DecimalField(
        _("Deposit Fee (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Account Maintenance
    dormancy_period_days = models.PositiveIntegerField(
        _("Dormancy Period (Days)"),
        default=90,
        help_text=_("Days of inactivity before account becomes dormant")
    )
    
    dormancy_fee = MoneyField(
        _("Dormancy Fee"),
        max_digits=10,
        decimal_places=2,
        default=Money(0, 'UGX')
    )
    
    account_maintenance_fee = MoneyField(
        _("Account Maintenance Fee"),
        max_digits=10,
        decimal_places=2,
        default=Money(0, 'UGX')
    )
    
    account_maintenance_frequency = models.CharField(
        _("Maintenance Fee Frequency"),
        max_length=15,
        choices=MAINTENANCE_FREQUENCY_CHOICES,
        default='NONE'
    )
    
    # Term-based Products (Fixed Deposits)
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
        help_text=_("Penalty as percentage of withdrawn amount")
    )
    
    # Tax Configuration
    withholding_tax_rate = models.DecimalField(
        _("Withholding Tax Rate (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_("Tax rate on interest earned")
    )
    
    # Product Status and Type
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
    
    is_fixed_deposit = models.BooleanField(
        _("Is Fixed Deposit"),
        default=False,
        help_text=_("Whether this is a fixed deposit product")
    )
    
    # Integration fields
    gl_account_code_savings = models.CharField(
        _("GL Account Code - Savings"),
        max_length=20,
        null=True,
        blank=True,
        help_text=_("General Ledger account code for savings")
    )
    
    gl_account_code_interest = models.CharField(
        _("GL Account Code - Interest"),
        max_length=20,
        null=True,
        blank=True,
        help_text=_("General Ledger account code for interest expense")
    )
    
    gl_account_code_fees = models.CharField(
        _("GL Account Code - Fees"),
        max_length=20,
        null=True,
        blank=True,
        help_text=_("General Ledger account code for fee income")
    )
    
    # Product Limits
    maximum_accounts_per_member = models.PositiveIntegerField(
        _("Maximum Accounts Per Member"),
        default=1,
        help_text=_("Maximum number of accounts of this type per member")
    )
    
    @property
    def currency(self):
        """Get the currency for this product from SACCO configuration"""
        try:
            return get_base_currency()
        except:
            return 'UGX'  # Fallback
    
    def get_applicable_interest_rate(self, balance=None, account=None):
        """Get applicable interest rate based on balance tiers"""
        if self.interest_calculation_method != 'TIERED':
            return self.interest_rate
        
        if not balance:
            return self.interest_rate
        
        # Check for custom account-specific tiers first
        if account:
            custom_tier = account.custom_interest_tiers.filter(
                is_active=True,
                min_balance__lte=balance.amount
            ).filter(
                models.Q(max_balance__isnull=True) | models.Q(max_balance__gte=balance.amount)
            ).order_by('-min_balance').first()
            
            if custom_tier:
                return custom_tier.interest_rate
        
        # Check product-level tiers
        tier = self.interest_tiers.filter(
            is_active=True,
            min_balance__lte=balance.amount
        ).filter(
            models.Q(max_balance__isnull=True) | models.Q(max_balance__gte=balance.amount)
        ).order_by('-min_balance').first()
        
        return tier.interest_rate if tier else self.interest_rate
    
    @classmethod
    def get_active_products(cls):
        """Get all active savings products"""
        return cls.objects.filter(is_active=True).order_by('name')
    
    @classmethod
    def get_main_savings_product(cls):
        """Get the main/primary savings product"""
        return cls.objects.filter(is_main_account=True, is_active=True).first()
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    class Meta:
        verbose_name = _("Savings Product")
        verbose_name_plural = _("Savings Products")
        ordering = ['name']


class InterestTier(BaseModel):
    """Interest rate tiers for tiered savings products"""
    
    savings_product = models.ForeignKey(
        SavingsProduct,
        on_delete=models.CASCADE,
        related_name='interest_tiers'
    )
    
    tier_name = models.CharField(
        _("Tier Name"),
        max_length=50,
        help_text=_("Name of this interest tier")
    )
    
    min_balance = MoneyField(
        _("Minimum Balance"),
        max_digits=12,
        decimal_places=2,
        default_currency='UGX'
    )
    
    max_balance = MoneyField(
        _("Maximum Balance"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        default_currency='UGX',
        help_text=_("Maximum balance for this tier (blank for no upper limit)")
    )
    
    interest_rate = models.DecimalField(
        _("Interest Rate (%)"),
        max_digits=8,
        decimal_places=5,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    
    def __str__(self):
        max_display = format_money(self.max_balance) if self.max_balance else "No limit"
        return f"{self.tier_name}: {format_money(self.min_balance)} - {max_display} ({self.interest_rate}%)"
    
    class Meta:
        verbose_name = _("Interest Tier")
        verbose_name_plural = _("Interest Tiers")
        ordering = ['min_balance']


# =============================================================================
# SAVINGS ACCOUNTS - MEMBER ACCOUNT MANAGEMENT
# =============================================================================

class SavingsAccount(BaseModel):
    """
    Individual member savings accounts.
    Integrated with Member model and SACCO configuration.
    """
    
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
    
    # Relationships
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name='savings_accounts'
    )
    
    group = models.ForeignKey(
        MemberGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='group_savings_accounts'
    )
    
    savings_product = models.ForeignKey(
        SavingsProduct,
        on_delete=models.PROTECT,
        related_name='accounts'
    )
    
    # Balance Information
    current_balance = MoneyField(
        _("Current Balance"),
        max_digits=15,
        decimal_places=2,
        default=Money(0, 'UGX')
    )
    
    available_balance = MoneyField(
        _("Available Balance"),
        max_digits=15,
        decimal_places=2,
        default=Money(0, 'UGX')
    )
    
    hold_amount = MoneyField(
        _("Hold Amount"),
        max_digits=15,
        decimal_places=2,
        default=Money(0, 'UGX')
    )
    
    overdraft_amount = MoneyField(
        _("Overdraft Amount"),
        max_digits=15,
        decimal_places=2,
        default=Money(0, 'UGX')
    )
    
    accrued_interest = MoneyField(
        _("Accrued Interest"),
        max_digits=12,
        decimal_places=2,
        default=Money(0, 'UGX')
    )
    
    # Account Status and Dates
    status = models.CharField(
        _("Account Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING_APPROVAL'
    )
    
    opening_date = models.DateField(
        _("Opening Date"),
        default=timezone.now
    )
    
    activated_date = models.DateField(
        _("Activated Date"),
        null=True,
        blank=True
    )
    
    closure_date = models.DateField(
        _("Closure Date"),
        null=True,
        blank=True
    )
    
    maturity_date = models.DateField(
        _("Maturity Date"),
        null=True,
        blank=True,
        help_text=_("For fixed deposits")
    )
    
    # Interest and Fee Tracking
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
    
    last_fee_charged_date = models.DateField(
        _("Last Fee Charged"),
        null=True,
        blank=True
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
    
    fixed_deposit_amount = MoneyField(
        _("Fixed Deposit Amount"),
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        default_currency='UGX'
    )
    
    auto_renew = models.BooleanField(
        _("Auto Renew"),
        default=False,
        help_text=_("Whether to automatically renew fixed deposit")
    )
    
    # Account Specific Settings
    nominated_transfer_account = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='nominated_from_accounts',
        help_text=_("Default account for transfers")
    )
    
    overdraft_limit = MoneyField(
        _("Overdraft Limit"),
        max_digits=12,
        decimal_places=2,
        default=Money(0, 'UGX')
    )
    
    overdraft_expiry_date = models.DateField(
        _("Overdraft Expiry Date"),
        null=True,
        blank=True
    )
    
    daily_withdrawal_limit = MoneyField(
        _("Daily Withdrawal Limit"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        default_currency='UGX'
    )
    
    withdrawals_remaining_today = models.PositiveIntegerField(
        _("Withdrawals Remaining Today"),
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
    
    # =============================================================================
    # COMPUTED PROPERTIES (Keep these as they're used in templates/views)
    # =============================================================================
    
    @property
    def currency(self):
        """Get account currency from SACCO configuration"""
        try:
            return get_base_currency()
        except:
            return 'UGX'
    
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
        """Days until fixed deposit matures - NEEDED by utils functions"""
        if not self.is_fixed_deposit or not self.maturity_date:
            return None
        
        today = timezone.now().date()
        if self.maturity_date <= today:
            return 0
        
        return (self.maturity_date - today).days
    
    # =============================================================================
    # CLASSMETHOD QUERIES (Keep these as they're commonly used)
    # =============================================================================
    
    @classmethod
    def get_member_total_balance(cls, member):
        """Get total balance across all member's savings accounts"""
        total = cls.objects.filter(
            member=member,
            status__in=['ACTIVE', 'DORMANT']
        ).aggregate(
            total=Sum('current_balance')
        )['total']
        
        if total:
            currency = get_base_currency()
            return Money(total, currency)
        
        return Money(0, get_base_currency())
    
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
    
    @classmethod
    def get_member_account_summary(cls, member):
        """Get comprehensive account summary - NEEDED by get_member_savings_summary() in utils"""
        accounts = cls.objects.filter(member=member)
        
        summary = {
            'total_accounts': accounts.count(),
            'active_accounts': accounts.filter(status='ACTIVE').count(),
            'dormant_accounts': accounts.filter(status='DORMANT').count(),
            'closed_accounts': accounts.filter(status='CLOSED').count(),
            'total_balance': cls.get_member_total_balance(member),
            'primary_account': cls.get_member_primary_account(member),
            'accounts': []
        }
        
        # Add detailed account information
        for account in accounts:
            summary['accounts'].append({
                'id': account.id,
                'account_number': account.account_number,
                'product': account.savings_product.name,
                'balance': account.current_balance,
                'available_balance': account.available_balance,
                'status': account.effective_status,
                'last_transaction': account.last_transaction_date,
                'is_fixed_deposit': account.is_fixed_deposit,
                'maturity_date': account.maturity_date,
                'days_to_maturity': account.days_to_maturity,
            })
        
        return summary
    
    # =============================================================================
    # ESSENTIAL METHODS (NEEDED BY UTILS.PY)
    # =============================================================================
    
    def approve_account(self, approved_by_user=None):
        """Approve pending account - NEEDED by approve_pending_accounts() in utils"""
        if self.status != 'PENDING_APPROVAL':
            return False, _("Account is not pending approval")
        
        # Check if member is active
        if self.member.status != 'ACTIVE':
            return False, _("Member must be active to approve account")
        
        # Check minimum balance requirement
        if self.current_balance < self.savings_product.minimum_opening_balance:
            return False, _(f"Minimum opening balance of {format_money(self.savings_product.minimum_opening_balance)} required")
        
        self.status = 'ACTIVE'
        self.activated_date = timezone.now().date()
        self.save()
        
        logger.info(f"Account {self.account_number} approved")
        return True, _("Account approved successfully")
    
    def update_dormancy_status(self):
        """Update dormancy status - NEEDED by update_dormancy_status() in utils"""
        if self.status in ['CLOSED', 'FROZEN', 'SUSPENDED']:
            return
        
        # Check transaction activity
        last_transaction = self.last_transaction_date
        if not last_transaction:
            is_dormant = True
        else:
            days_inactive = (timezone.now().date() - last_transaction).days
            is_dormant = days_inactive > self.savings_product.dormancy_period_days
        
        if is_dormant and self.status != 'DORMANT':
            self.status = 'DORMANT'
            self.save(update_fields=['status'])
            logger.info(f"Account {self.account_number} marked as dormant")
        elif not is_dormant and self.status == 'DORMANT':
            self.status = 'ACTIVE'
            self.save(update_fields=['status'])
            logger.info(f"Account {self.account_number} reactivated from dormancy")
    
    # Simple validation methods (keep basic ones)
    def is_withdrawal_allowed(self, amount):
        """Basic withdrawal validation - detailed logic moved to utils"""
        if not isinstance(amount, Money):
            amount = Money(amount, self.currency)
        
        if self.effective_status not in ['ACTIVE', 'DORMANT']:
            return False, f"Account status is {self.get_status_display()}"
        
        if amount > self.available_balance:
            return False, "Insufficient available balance"
        
        return True, "Withdrawal allowed"
    
    def is_deposit_allowed(self, amount):
        """Basic deposit validation - detailed logic moved to utils"""
        if not isinstance(amount, Money):
            amount = Money(amount, self.currency)
        
        if self.effective_status not in ['ACTIVE', 'DORMANT', 'PENDING_APPROVAL']:
            return False, f"Account status is {self.get_status_display()}"
        
        return True, "Deposit allowed"
    
    def __str__(self):
        return f"{self.account_number} - {self.member.full_name}"
    
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
    """
    Transactions on savings accounts.
    Integrated with PaymentMethod and TaxRate models from sacco_settings.
    """
    
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
        ('LOAN_REPAYMENT', _('Loan Repayment')),
        ('LOAN_DISBURSEMENT', _('Loan Disbursement')),
        ('PENALTY', _('Penalty')),
        ('MAINTENANCE_FEE', _('Maintenance Fee')),
        ('DORMANCY_FEE', _('Dormancy Fee')),
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
        related_name='transactions'
    )
    
    transaction_type = models.CharField(
        _("Transaction Type"),
        max_length=20,
        choices=TRANSACTION_TYPES
    )
    
    amount = MoneyField(
        _("Transaction Amount"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    fees = MoneyField(
        _("Fees"),
        max_digits=12,
        decimal_places=2,
        default=Money(0, 'UGX')
    )
    
    tax_amount = MoneyField(
        _("Tax Amount"),
        max_digits=12,
        decimal_places=2,
        default=Money(0, 'UGX')
    )
    
    # Transaction Timing
    transaction_date = models.DateTimeField(
        _("Transaction Date"),
        default=timezone.now
    )
    
    post_date = models.DateField(
        _("Post Date"),
        default=timezone.now
    )
    
    value_date = models.DateField(
        _("Value Date"),
        default=timezone.now,
        help_text=_("Date from which interest is calculated")
    )
    
    # Payment Information
    payment_method = models.ForeignKey(
        PaymentMethod,
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
        help_text=_("External reference number (e.g., cheque number, mobile money ref)")
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
    running_balance = MoneyField(
        _("Running Balance"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    # Processing Information
    receipt_number = models.CharField(
        _("Receipt Number"),
        max_length=50,
        null=True,
        blank=True
    )
    
    # Financial Period Integration
    financial_period = models.ForeignKey(
        FinancialPeriod,
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
    
    original_transaction = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reversal_transactions',
        help_text=_("Original transaction being reversed")
    )
    
    # Integration Fields
    gl_transaction_reference = models.CharField(
        _("GL Transaction Reference"),
        max_length=50,
        null=True,
        blank=True,
        help_text=_("General Ledger transaction reference")
    )
    
    @property
    def net_amount(self):
        """Get net transaction amount (amount - fees - taxes)"""
        return self.amount - self.fees - self.tax_amount
    
    @property
    def total_amount(self):
        """Get total transaction amount (amount + fees + taxes)"""
        return self.amount + self.fees + self.tax_amount
    
    # =============================================================================
    # ESSENTIAL METHODS (NEEDED BY UTILS.PY)
    # =============================================================================
    
    def reverse_transaction(self, reason, reversed_by_user=None):
        """Reverse this transaction - NEEDED by reverse_savings_transaction() in utils"""
        if self.is_reversed:
            return False, _("Transaction is already reversed")
        
        if self.transaction_type == 'REVERSAL':
            return False, _("Cannot reverse a reversal transaction")
        
        # Create reversal transaction
        reversal_type_map = {
            'DEPOSIT': 'WITHDRAWAL',
            'WITHDRAWAL': 'DEPOSIT',
            'TRANSFER_IN': 'TRANSFER_OUT',
            'TRANSFER_OUT': 'TRANSFER_IN',
            'INTEREST': 'ADJUSTMENT',
            'FEE': 'ADJUSTMENT',
        }
        
        reversal_type = reversal_type_map.get(self.transaction_type, 'REVERSAL')
        
        reversal_transaction = SavingsTransaction(
            account=self.account,
            transaction_type=reversal_type,
            amount=self.amount,
            fees=self.fees,
            tax_amount=self.tax_amount,
            payment_method=self.payment_method,
            description=f"Reversal of {self.transaction_id}: {reason}",
            original_transaction=self,
            linked_account=self.linked_account,
            financial_period=FinancialPeriod.get_period_for_date(timezone.now().date())
        )
        
        reversal_transaction.save()
        
        # Mark original transaction as reversed
        self.is_reversed = True
        self.reversal_reason = reason
        self.reversal_date = timezone.now()
        self.save(update_fields=['is_reversed', 'reversal_reason', 'reversal_date'])
        
        logger.info(f"Transaction {self.transaction_id} reversed")
        return True, _("Transaction reversed successfully")
    
    @classmethod
    def get_member_transaction_summary(cls, member, start_date=None, end_date=None):
        """Get transaction summary for member - NEEDED by generate_member_portfolio_analysis() in utils"""
        if not start_date:
            start_date = timezone.now().date() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now().date()
        
        transactions = cls.objects.filter(
            account__member=member,
            transaction_date__date__gte=start_date,
            transaction_date__date__lte=end_date,
            is_reversed=False
        )
        
        summary = {
            'period_start': start_date,
            'period_end': end_date,
            'total_transactions': transactions.count(),
        }
        
        # Calculate totals by transaction type
        for trans_type, display_name in cls.TRANSACTION_TYPES:
            type_transactions = transactions.filter(transaction_type=trans_type)
            summary[f'{trans_type.lower()}_count'] = type_transactions.count()
            summary[f'{trans_type.lower()}_amount'] = type_transactions.aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
        
        # Calculate net position
        credits = transactions.filter(
            transaction_type__in=['DEPOSIT', 'TRANSFER_IN', 'INTEREST', 'DIVIDEND']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        debits = transactions.filter(
            transaction_type__in=['WITHDRAWAL', 'TRANSFER_OUT', 'FEE', 'TAX', 'PENALTY']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        base_currency = get_base_currency()
        
        summary['total_credits'] = Money(credits, base_currency)
        summary['total_debits'] = Money(debits, base_currency)
        summary['net_amount'] = Money(credits - debits, base_currency)
        
        # Calculate fees and taxes
        summary['total_fees'] = Money(
            transactions.aggregate(total=Sum('fees'))['total'] or Decimal('0.00'),
            base_currency
        )
        summary['total_taxes'] = Money(
            transactions.aggregate(total=Sum('tax_amount'))['total'] or Decimal('0.00'),
            base_currency
        )
        
        return summary
    
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
# SUPPORTING MODELS (Simplified - complex logic moved to utils/signals)
# =============================================================================

class InterestCalculation(BaseModel):
    """Record of interest calculations for savings accounts."""
    
    account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.CASCADE,
        related_name='interest_calculations'
    )
    
    calculation_date = models.DateField(
        _("Calculation Date"),
        help_text=_("Date when interest was calculated")
    )
    
    period_start_date = models.DateField(
        _("Period Start Date"),
        help_text=_("Start date of interest calculation period")
    )
    
    period_end_date = models.DateField(
        _("Period End Date"),
        help_text=_("End date of interest calculation period")
    )
    
    financial_period = models.ForeignKey(
        FinancialPeriod,
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
    
    # Balance information used in calculation
    average_balance = MoneyField(
        _("Average Balance"),
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        default_currency='UGX'
    )
    
    minimum_balance = MoneyField(
        _("Minimum Balance"),
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        default_currency='UGX'
    )
    
    opening_balance = MoneyField(
        _("Opening Balance"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    closing_balance = MoneyField(
        _("Closing Balance"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    # Interest calculation details
    interest_rate = models.DecimalField(
        _("Interest Rate (%)"),
        max_digits=8,
        decimal_places=5,
        help_text=_("Interest rate used for calculation")
    )
    
    days_calculated = models.PositiveIntegerField(
        _("Days Calculated"),
        help_text=_("Number of days in calculation period")
    )
    
    gross_interest = MoneyField(
        _("Gross Interest"),
        max_digits=12,
        decimal_places=2,
        default_currency='UGX',
        help_text=_("Interest before tax")
    )
    
    # Tax calculation
    tax_rate = models.DecimalField(
        _("Tax Rate (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    withholding_tax = MoneyField(
        _("Withholding Tax"),
        max_digits=10,
        decimal_places=2,
        default=Money(0, 'UGX')
    )
    
    net_interest = MoneyField(
        _("Net Interest"),
        max_digits=12,
        decimal_places=2,
        default_currency='UGX',
        help_text=_("Interest after tax deduction")
    )
    
    # Posting status
    is_posted = models.BooleanField(
        _("Is Posted"),
        default=False,
        help_text=_("Whether interest has been posted to account")
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
        related_name='interest_calculation',
        help_text=_("Transaction created when interest was posted")
    )
    
    # =============================================================================
    # ESSENTIAL METHODS (NEEDED BY UTILS.PY)
    # =============================================================================
    
    def post_interest(self, posted_by_user=None):
        """Post calculated interest to accounts - NEEDED by post_calculated_interest() in utils"""
        if self.is_posted:
            return False, _("Interest has already been posted")
        
        if self.net_interest.amount <= 0:
            return False, _("No interest to post")
        
        # Create interest transaction
        interest_transaction = SavingsTransaction(
            account=self.account,
            transaction_type='INTEREST',
            amount=self.net_interest,
            tax_amount=self.withholding_tax,
            description=f"Interest for period {self.period_start_date} to {self.period_end_date}",
            financial_period=self.financial_period
        )
        
        interest_transaction.save()
        
        # Create tax transaction if there's withholding tax
        if self.withholding_tax.amount > 0:
            tax_transaction = SavingsTransaction(
                account=self.account,
                transaction_type='TAX',
                amount=self.withholding_tax,
                description=f"Withholding tax on interest for period {self.period_start_date} to {self.period_end_date}",
                financial_period=self.financial_period
            )
            tax_transaction.save()
        
        # Update calculation record
        self.is_posted = True
        self.posted_date = timezone.now().date()
        self.transaction = interest_transaction
        self.save()
        
        logger.info(f"Interest of {format_money(self.net_interest)} posted to account {self.account.account_number}")
        return True, _("Interest posted successfully")
    
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


class SavingsAccountFee(BaseModel):
    """Fees charged on savings accounts."""
    
    FEE_TYPE_CHOICES = [
        ('MAINTENANCE', _('Maintenance Fee')),
        ('WITHDRAWAL', _('Withdrawal Fee')),
        ('DEPOSIT', _('Deposit Fee')),
        ('DORMANCY', _('Dormancy Fee')),
        ('STATEMENT', _('Statement Fee')),
        ('BELOW_MIN_BALANCE', _('Below Minimum Balance Fee')),
        ('CHEQUE_BOOK', _('Cheque Book Fee')),
        ('ATM_CARD', _('ATM Card Fee')),
        ('LEDGER_FEE', _('Ledger Fee')),
        ('SMS_ALERT', _('SMS Alert Fee')),
        ('EARLY_WITHDRAWAL', _('Early Withdrawal Penalty')),
        ('ACCOUNT_CLOSURE', _('Account Closure Fee')),
        ('OTHER', _('Other Fee')),
    ]
    
    account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.CASCADE,
        related_name='fees'
    )
    
    fee_date = models.DateField(
        _("Fee Date"),
        default=timezone.now
    )
    
    fee_type = models.CharField(
        _("Fee Type"),
        max_length=20,
        choices=FEE_TYPE_CHOICES
    )
    
    amount = MoneyField(
        _("Fee Amount"),
        max_digits=12,
        decimal_places=2,
        default_currency='UGX'
    )
    
    description = models.TextField(
        _("Description"),
        null=True,
        blank=True
    )
    
    # Charging status
    is_charged = models.BooleanField(
        _("Is Charged"),
        default=False,
        help_text=_("Whether fee has been charged to account")
    )
    
    charged_date = models.DateField(
        _("Charged Date"),
        null=True,
        blank=True
    )
    
    transaction = models.ForeignKey(
        SavingsTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fee_record'
    )
    
    # Waiver information
    is_waived = models.BooleanField(
        _("Is Waived"),
        default=False
    )
    
    waiver_reason = models.TextField(
        _("Waiver Reason"),
        null=True,
        blank=True
    )
    
    waiver_date = models.DateTimeField(
        _("Waiver Date"),
        null=True,
        blank=True
    )
    
    financial_period = models.ForeignKey(
        FinancialPeriod,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='savings_fees'
    )
    
    # =============================================================================
    # ESSENTIAL METHODS (NEEDED BY UTILS.PY)
    # =============================================================================
    
    def charge_fee(self, charged_by_user=None):
        """Charge fee to savings account - NEEDED by charge_maintenance_fees() in utils"""
        if self.is_charged:
            return False, _("Fee has already been charged")
        
        if self.is_waived:
            return False, _("Fee has been waived")
        
        if self.amount.amount <= 0:
            return False, _("Invalid fee amount")
        
        # Create fee transaction
        fee_transaction = SavingsTransaction(
            account=self.account,
            transaction_type='FEE',
            amount=self.amount,
            description=f"{self.get_fee_type_display()}: {self.description or ''}",
            financial_period=self.financial_period
        )
        
        fee_transaction.save()
        
        # Update fee record
        self.is_charged = True
        self.charged_date = timezone.now().date()
        self.transaction = fee_transaction
        self.save()
        
        logger.info(f"Fee of {format_money(self.amount)} charged to account {self.account.account_number}")
        return True, _("Fee charged successfully")
    
    def __str__(self):
        return f"{self.get_fee_type_display()} - {format_money(self.amount)} for {self.account.account_number}"
    
    class Meta:
        verbose_name = _("Savings Account Fee")
        verbose_name_plural = _("Savings Account Fees")
        ordering = ['-fee_date']
        indexes = [
            models.Index(fields=['account', 'fee_date']),
            models.Index(fields=['fee_type', 'is_charged']),
            models.Index(fields=['financial_period']),
        ]


class StandingOrder(BaseModel):
    """Standing orders for automated transfers."""
    
    FREQUENCY_CHOICES = [
        ('DAILY', _('Daily')),
        ('WEEKLY', _('Weekly')),
        ('BIWEEKLY', _('Bi-Weekly')),
        ('MONTHLY', _('Monthly')),
        ('QUARTERLY', _('Quarterly')),
        ('SEMI_ANNUALLY', _('Semi-Annually')),
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
    
    DESTINATION_TYPE_CHOICES = [
        ('INTERNAL_ACCOUNT', _('Internal Savings Account')),
        ('BANK_ACCOUNT', _('Bank Account')),
        ('MOBILE_MONEY', _('Mobile Money')),
        ('LOAN_ACCOUNT', _('Loan Account')),
        ('GROUP_CONTRIBUTION', _('Group Contribution')),
        ('EXTERNAL_TRANSFER', _('External Transfer')),
    ]
    
    # Source and destination
    source_account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.CASCADE,
        related_name='standing_orders_out'
    )
    
    destination_type = models.CharField(
        _("Destination Type"),
        max_length=20,
        choices=DESTINATION_TYPE_CHOICES
    )
    
    destination_account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='standing_orders_in'
    )
    
    destination_reference = models.CharField(
        _("Destination Reference"),
        max_length=100,
        null=True,
        blank=True,
        help_text=_("External account reference when destination is not internal")
    )
    
    # Transfer details
    amount = MoneyField(
        _("Transfer Amount"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
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
        default='PENDING_APPROVAL'
    )
    
    description = models.TextField(
        _("Description"),
        null=True,
        blank=True
    )
    
    priority = models.PositiveIntegerField(
        _("Priority"),
        default=1,
        help_text=_("Execution priority when multiple orders exist")
    )
    
    # Transfer handling options
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='standing_orders'
    )
    
    transfer_fee = MoneyField(
        _("Transfer Fee"),
        max_digits=10,
        decimal_places=2,
        default=Money(0, 'UGX')
    )
    
    skip_on_insufficient_funds = models.BooleanField(
        _("Skip on Insufficient Funds"),
        default=False,
        help_text=_("Skip execution if insufficient funds, otherwise fail")
    )
    
    maximum_attempts = models.PositiveIntegerField(
        _("Maximum Attempts"),
        default=3
    )
    
    current_attempt = models.PositiveIntegerField(
        _("Current Attempt"),
        default=0
    )
    
    # Execution statistics
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
        max_length=10,
        choices=[
            ('SUCCESS', _('Success')),
            ('FAILED', _('Failed')),
            ('SKIPPED', _('Skipped')),
            ('PENDING', _('Pending'))
        ],
        null=True,
        blank=True
    )
    
    last_execution_message = models.TextField(
        _("Last Execution Message"),
        null=True,
        blank=True
    )
    
    # =============================================================================
    # ESSENTIAL METHODS (NEEDED BY UTILS.PY)
    # =============================================================================
    
    def execute_transfer(self, execution_user=None):
        """Execute the standing order transfer - NEEDED by process_due_standing_orders() in utils"""
        if self.status != 'ACTIVE':
            return False, f"Standing order status is {self.get_status_display()}"
        
        # Check if source account has sufficient funds
        total_amount = self.amount + self.transfer_fee
        can_withdraw, message = self.source_account.is_withdrawal_allowed(total_amount)
        
        if not can_withdraw:
            if self.skip_on_insufficient_funds:
                self.last_execution_status = 'SKIPPED'
                self.last_execution_message = f"Skipped: {message}"
                self.last_execution_date = timezone.now().date()
                self.next_run_date = self.calculate_next_run_date()
                self.save()
                return True, f"Transfer skipped: {message}"
            else:
                self.current_attempt += 1
                self.last_execution_status = 'FAILED'
                self.last_execution_message = f"Failed: {message}"
                
                if self.current_attempt >= self.maximum_attempts:
                    self.status = 'FAILED'
                
                self.save()
                return False, f"Transfer failed: {message}"
        
        try:
            # Create withdrawal transaction
            withdrawal_transaction = SavingsTransaction(
                account=self.source_account,
                transaction_type='TRANSFER_OUT',
                amount=self.amount,
                fees=self.transfer_fee,
                payment_method=self.payment_method,
                linked_account=self.destination_account,
                description=f"Standing order transfer: {self.description or ''}",
                reference_number=f"SO-{self.id}-{timezone.now().strftime('%Y%m%d')}"
            )
            
            withdrawal_transaction.save()
            
            # Create deposit transaction if internal transfer
            if self.destination_type == 'INTERNAL_ACCOUNT' and self.destination_account:
                deposit_transaction = SavingsTransaction(
                    account=self.destination_account,
                    transaction_type='TRANSFER_IN',
                    amount=self.amount,
                    payment_method=self.payment_method,
                    linked_account=self.source_account,
                    linked_transaction=withdrawal_transaction,
                    description=f"Standing order transfer from {self.source_account.account_number}",
                    reference_number=withdrawal_transaction.reference_number
                )
                
                deposit_transaction.save()
                
                # Link transactions
                withdrawal_transaction.linked_transaction = deposit_transaction
                withdrawal_transaction.save()
            
            # Update standing order status
            self.execution_count += 1
            self.current_attempt = 0  # Reset attempts on success
            self.last_execution_date = timezone.now().date()
            self.last_execution_status = 'SUCCESS'
            self.last_execution_message = 'Transfer executed successfully'
            self.next_run_date = self.calculate_next_run_date()
            
            # Check if we've reached the end date
            if self.end_date and self.next_run_date > self.end_date:
                self.status = 'COMPLETED'
            
            self.save()
            
            logger.info(f"Standing order {self.id} executed successfully")
            return True, "Transfer executed successfully"
            
        except Exception as e:
            # Handle execution error
            self.current_attempt += 1
            self.last_execution_status = 'FAILED'
            self.last_execution_message = f"Error: {str(e)}"
            
            if self.current_attempt >= self.maximum_attempts:
                self.status = 'FAILED'
            
            self.save()
            logger.error(f"Standing order {self.id} execution failed: {e}")
            return False, f"Transfer failed: {str(e)}"
    
    def calculate_next_run_date(self):
        """Calculate the next run date based on frequency - NEEDED by execute_transfer()"""
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
        elif self.frequency == 'SEMI_ANNUALLY':
            return last_date + relativedelta(months=6)
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
        ).order_by('priority', 'next_run_date')
    
    def __str__(self):
        return f"Standing Order: {self.source_account.account_number} -> {format_money(self.amount)} {self.get_frequency_display()}"
    
    class Meta:
        verbose_name = _("Standing Order")
        verbose_name_plural = _("Standing Orders")
        ordering = ['priority', 'next_run_date']
        indexes = [
            models.Index(fields=['status', 'next_run_date']),
            models.Index(fields=['source_account', 'status']),
            models.Index(fields=['priority']),
        ]


# =============================================================================
# REMAINING MODELS (Simplified - keep only essential fields and methods)
# =============================================================================
          
class SavingsAccountStatement(BaseModel):
    """Generated account statements."""
    
    STATEMENT_TYPE_CHOICES = [
        ('MONTHLY', _('Monthly Statement')),
        ('QUARTERLY', _('Quarterly Statement')),
        ('ANNUAL', _('Annual Statement')),
        ('CUSTOM', _('Custom Period Statement')),
        ('ON_DEMAND', _('On-Demand Statement')),
    ]
    
    account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.CASCADE,
        related_name='statements'
    )
    
    statement_type = models.CharField(
        _("Statement Type"),
        max_length=15,
        choices=STATEMENT_TYPE_CHOICES,
        default='MONTHLY'
    )
    
    statement_date = models.DateField(
        _("Statement Date"),
        help_text=_("Date when statement was generated")
    )
    
    period_start_date = models.DateField(
        _("Period Start Date")
    )
    
    period_end_date = models.DateField(
        _("Period End Date")
    )
    
    financial_period = models.ForeignKey(
        FinancialPeriod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='savings_statements'
    )
    
    # Balance information
    opening_balance = MoneyField(
        _("Opening Balance"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    closing_balance = MoneyField(
        _("Closing Balance"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    # Transaction summaries
    total_deposits = MoneyField(
        _("Total Deposits"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    total_withdrawals = MoneyField(
        _("Total Withdrawals"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    total_fees = MoneyField(
        _("Total Fees"),
        max_digits=12,
        decimal_places=2,
        default_currency='UGX'
    )
    
    total_interest = MoneyField(
        _("Total Interest"),
        max_digits=12,
        decimal_places=2,
        default_currency='UGX'
    )
    
    total_taxes = MoneyField(
        _("Total Taxes"),
        max_digits=12,
        decimal_places=2,
        default_currency='UGX'
    )
    
    transaction_count = models.PositiveIntegerField(
        _("Transaction Count"),
        default=0
    )
    
    # File and delivery
    statement_file = models.FileField(
        _("Statement File"),
        upload_to='account_statements/',
        null=True,
        blank=True
    )
    
    is_delivered = models.BooleanField(
        _("Is Delivered"),
        default=False
    )
    
    delivery_date = models.DateTimeField(
        _("Delivery Date"),
        null=True,
        blank=True
    )
    
    def __str__(self):
        return f"Statement for {self.account.account_number} - {self.period_start_date} to {self.period_end_date}"
    
    class Meta:
        verbose_name = _("Savings Account Statement")
        verbose_name_plural = _("Savings Account Statements")
        ordering = ['-statement_date']


class SavingsAccountClosure(BaseModel):
    """Record of closed savings accounts."""
    
    CLOSURE_REASON_CHOICES = [
        ('MEMBER_REQUEST', _('Member Request')),
        ('TRANSFER', _('Transfer to Another Account')),
        ('DORMANCY', _('Long-term Dormancy')),
        ('DEATH', _('Death of Member')),
        ('FRAUD', _('Fraud/Compliance')),
        ('REGULATORY', _('Regulatory Requirement')),
        ('SYSTEM', _('System Closure')),
        ('MIGRATION', _('System Migration')),
        ('OTHER', _('Other Reason')),
    ]
    
    account = models.OneToOneField(
        SavingsAccount,
        on_delete=models.CASCADE,
        related_name='closure_record'
    )
    
    closure_date = models.DateField(
        _("Closure Date")
    )
    
    # Balance information at closure
    closing_balance = MoneyField(
        _("Closing Balance"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    net_amount = MoneyField(
        _("Net Amount"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    reason = models.CharField(
        _("Closure Reason"),
        max_length=20,
        choices=CLOSURE_REASON_CHOICES
    )
    
    details = models.TextField(
        _("Closure Details"),
        null=True,
        blank=True
    )
    
    # Related transactions
    closure_transaction = models.ForeignKey(
        SavingsTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='account_closure'
    )
    
    financial_period = models.ForeignKey(
        FinancialPeriod,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='account_closures'
    )
    
    def __str__(self):
        return f"Closure of {self.account.account_number} on {self.closure_date}"
    
    class Meta:
        verbose_name = _("Savings Account Closure")
        verbose_name_plural = _("Savings Account Closures")
        ordering = ['-closure_date']


class DepositMaturity(BaseModel):
    """Maturity handling for fixed deposits."""
    
    DISPOSITION_CHOICES = [
        ('PENDING', _('Pending')),
        ('RENEWED', _('Renewed')),
        ('TRANSFERRED', _('Transferred to Savings')),
        ('WITHDRAWN', _('Withdrawn')),
        ('PARTIAL_RENEWAL', _('Partially Renewed')),
        ('AUTO_RENEWED', _('Auto Renewed')),
    ]
    
    account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.CASCADE,
        related_name='maturity_records'
    )
    
    maturity_date = models.DateField(
        _("Maturity Date")
    )
    
    # Maturity amounts
    principal_amount = MoneyField(
        _("Principal Amount"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    interest_amount = MoneyField(
        _("Interest Amount"),
        max_digits=12,
        decimal_places=2,
        default_currency='UGX'
    )
    
    maturity_amount = MoneyField(
        _("Net Maturity Amount"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    # Disposition details
    disposition = models.CharField(
        _("Disposition"),
        max_length=20,
        choices=DISPOSITION_CHOICES,
        default='PENDING'
    )
    
    disposition_date = models.DateField(
        _("Disposition Date"),
        null=True,
        blank=True
    )
    
    # Processing status
    is_processed = models.BooleanField(
        _("Is Processed"),
        default=False
    )
    
    financial_period = models.ForeignKey(
        FinancialPeriod,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='deposit_maturities'
    )
    
    def __str__(self):
        return f"Maturity for {self.account.account_number} on {self.maturity_date}"
    
    class Meta:
        verbose_name = _("Deposit Maturity")
        verbose_name_plural = _("Deposit Maturities")
        ordering = ['maturity_date']


class SavingsHold(BaseModel):
    """Holds placed on savings accounts."""
    
    HOLD_REASON_CHOICES = [
        ('LOAN_COLLATERAL', _('Loan Collateral')),
        ('LEGAL_HOLD', _('Legal Hold')),
        ('CHECK_CLEARING', _('Check Clearing')),
        ('PENDING_TRANSFER', _('Pending Transfer')),
        ('DISPUTE', _('Account Dispute')),
        ('DORMANCY', _('Dormancy Hold')),
        ('REGULATORY', _('Regulatory Hold')),
        ('FRAUD_INVESTIGATION', _('Fraud Investigation')),
        ('COURT_ORDER', _('Court Order')),
        ('OTHER', _('Other')),
    ]
    
    account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.CASCADE,
        related_name='holds'
    )
    
    hold_date = models.DateField(
        _("Hold Date"),
        default=timezone.now
    )
    
    release_date = models.DateField(
        _("Release Date"),
        null=True,
        blank=True
    )
    
    amount = MoneyField(
        _("Hold Amount"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    
    reason = models.CharField(
        _("Hold Reason"),
        max_length=25,
        choices=HOLD_REASON_CHOICES
    )
    
    description = models.TextField(
        _("Description"),
        null=True,
        blank=True
    )
    
    # Expiry for temporary holds
    expiry_date = models.DateField(
        _("Expiry Date"),
        null=True,
        blank=True,
        help_text=_("Date when hold automatically expires")
    )
    
    financial_period = models.ForeignKey(
        FinancialPeriod,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='savings_holds'
    )
    
    @classmethod
    def check_expired_holds(cls):
        """Check for and auto-release expired holds"""
        today = timezone.now().date()
        expired_holds = cls.objects.filter(
            is_active=True,
            expiry_date__lt=today
        )
        
        released_count = 0
        for hold in expired_holds:
            hold.is_active = False
            hold.release_date = today
            hold.save()
            released_count += 1
        
        return released_count
    
    def __str__(self):
        return f"Hold of {format_money(self.amount)} on {self.account.account_number} - {self.get_reason_display()}"
    
    class Meta:
        verbose_name = _("Savings Hold")
        verbose_name_plural = _("Savings Holds")
        ordering = ['-hold_date']


class MinimumBalanceAlert(BaseModel):
    """Alerts for accounts below minimum balance."""
    
    NOTIFICATION_METHOD_CHOICES = [
        ('SMS', _('SMS')),
        ('EMAIL', _('Email')),
        ('BOTH', _('Both SMS and Email')),
        ('NONE', _('No Notification')),
    ]
    
    account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.CASCADE,
        related_name='minimum_balance_alerts'
    )
    
    alert_date = models.DateField(
        _("Alert Date"),
        default=timezone.now
    )
    
    current_balance = MoneyField(
        _("Current Balance"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    minimum_required = MoneyField(
        _("Minimum Required"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    shortfall = MoneyField(
        _("Shortfall Amount"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    # Alert status
    is_resolved = models.BooleanField(
        _("Is Resolved"),
        default=False
    )
    
    resolved_date = models.DateField(
        _("Resolved Date"),
        null=True,
        blank=True
    )
    
    # Notification tracking
    notification_sent = models.BooleanField(
        _("Notification Sent"),
        default=False
    )
    
    notification_date = models.DateTimeField(
        _("Notification Date"),
        null=True,
        blank=True
    )
    
    notification_method = models.CharField(
        _("Notification Method"),
        max_length=10,
        choices=NOTIFICATION_METHOD_CHOICES,
        default='NONE'
    )
    
    notification_count = models.PositiveIntegerField(
        _("Notification Count"),
        default=0,
        help_text=_("Number of notifications sent")
    )
    
    financial_period = models.ForeignKey(
        FinancialPeriod,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='balance_alerts'
    )
    
    # =============================================================================
    # ESSENTIAL METHODS (NEEDED BY SIGNALS)
    # =============================================================================
    
    def send_notification(self, method='SMS', sent_by_user=None):
        """Send notification to member - NEEDED by signals"""
        try:
            config = get_sacco_config()
            
            if method in ['SMS', 'BOTH'] and config.enable_sms_notifications:
                # Send SMS notification
                self._send_sms_notification()
            
            if method in ['EMAIL', 'BOTH'] and config.enable_email_notifications:
                # Send email notification
                self._send_email_notification()
            
            self.notification_sent = True
            self.notification_date = timezone.now()
            self.notification_method = method
            self.notification_count += 1
            
            self.save()
            
            logger.info(f"Minimum balance alert sent to {self.account.member.full_name}")
            return True, _("Notification sent successfully")
            
        except Exception as e:
            logger.error(f"Failed to send minimum balance alert: {e}")
            return False, f"Failed to send notification: {str(e)}"
    
    def _send_sms_notification(self):
        """Send SMS notification"""
        message = (
            f"Dear {self.account.member.first_name}, your savings account "
            f"{self.account.account_number} balance is {format_money(self.current_balance)}. "
            f"Minimum balance required is {format_money(self.minimum_required)}. "
            f"Please top up by {format_money(self.shortfall)}."
        )
        
        # Integration with SMS service would go here
        logger.info(f"SMS sent: {message}")

    def _send_email_notification(self):
        """Send email notification"""
        subject = "Minimum Balance Alert"
        message = (
            f"Dear {self.account.member.full_name},\n\n"
            f"Your savings account {self.account.account_number} has fallen below "
            f"the minimum balance requirement.\n\n"
            f"Current Balance: {format_money(self.current_balance)}\n"
            f"Minimum Required: {format_money(self.minimum_required)}\n"
            f"Shortfall: {format_money(self.shortfall)}\n\n"
            f"Please deposit the shortfall amount to avoid fees."
        )
        
        # Integration with email service would go here
        logger.info(f"Email sent: {subject}")
    
    @classmethod
    def check_minimum_balances(cls):
        """Check all accounts for minimum balance violations"""
        alerts_created = 0
        
        active_accounts = SavingsAccount.objects.filter(status='ACTIVE')
        
        for account in active_accounts:
            min_balance = account.savings_product.minimum_balance
            
            if account.current_balance < min_balance:
                existing_alert = cls.objects.filter(
                    account=account,
                    alert_date=timezone.now().date(),
                    is_resolved=False
                ).exists()
                
                if not existing_alert:
                    cls.objects.create(
                        account=account,
                        current_balance=account.current_balance,
                        minimum_required=min_balance
                    )
                    alerts_created += 1
        
        return alerts_created
    
    def __str__(self):
        return f"Minimum Balance Alert for {self.account.account_number} on {self.alert_date}"
    
    class Meta:
        verbose_name = _("Minimum Balance Alert")
        verbose_name_plural = _("Minimum Balance Alerts")
        ordering = ['-alert_date']


class TransactionReceipt(BaseModel):
    """Receipts for savings transactions."""
    
    transaction = models.OneToOneField(
        SavingsTransaction,
        on_delete=models.CASCADE,
        related_name='receipt'
    )
    
    receipt_number = models.CharField(
        _("Receipt Number"),
        max_length=50,
        unique=True
    )
    
    receipt_date = models.DateTimeField(
        _("Receipt Date"),
        default=timezone.now
    )
    
    # Transaction details snapshot
    member_name = models.CharField(
        _("Member Name"),
        max_length=200
    )
    
    account_number = models.CharField(
        _("Account Number"),
        max_length=30
    )
    
    transaction_type = models.CharField(
        _("Transaction Type"),
        max_length=20
    )
    
    amount = MoneyField(
        _("Transaction Amount"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    total_amount = MoneyField(
        _("Total Amount"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    running_balance = MoneyField(
        _("Running Balance"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    # Receipt handling
    is_printed = models.BooleanField(
        _("Is Printed"),
        default=False
    )
    
    print_date = models.DateTimeField(
        _("Print Date"),
        null=True,
        blank=True
    )
    
    def __str__(self):
        return f"Receipt #{self.receipt_number} for {self.transaction_type}"
    
    class Meta:
        verbose_name = _("Transaction Receipt")
        verbose_name_plural = _("Transaction Receipts")
        ordering = ['-receipt_date']


class GroupSavings(BaseModel):
    """Group savings contribution tracking."""
    
    CONTRIBUTION_CYCLE_CHOICES = [
        ('DAILY', _('Daily')),
        ('WEEKLY', _('Weekly')),
        ('BIWEEKLY', _('Bi-Weekly')),
        ('MONTHLY', _('Monthly')),
        ('QUARTERLY', _('Quarterly')),
    ]
    
    group = models.ForeignKey(
        MemberGroup,
        on_delete=models.CASCADE,
        related_name='savings_contributions'
    )
    
    group_account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.CASCADE,
        related_name='group_contributions'
    )
    
    contribution_date = models.DateField(
        _("Contribution Date"),
        default=timezone.now
    )
    
    total_contribution = MoneyField(
        _("Total Contribution"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    contribution_cycle = models.CharField(
        _("Contribution Cycle"),
        max_length=15,
        choices=CONTRIBUTION_CYCLE_CHOICES
    )
    
    # Meeting information
    is_complete = models.BooleanField(
        _("Is Complete"),
        default=False
    )
    
    members_present = models.PositiveIntegerField(
        _("Members Present"),
        default=0
    )
    
    members_absent = models.PositiveIntegerField(
        _("Members Absent"),
        default=0
    )
    
    financial_period = models.ForeignKey(
        FinancialPeriod,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='group_savings'
    )
    
    def __str__(self):
        return f"Group Contribution for {self.group.name} on {self.contribution_date}"
    
    class Meta:
        verbose_name = _("Group Savings")
        verbose_name_plural = _("Group Savings")
        ordering = ['-contribution_date']
        unique_together = ('group', 'contribution_date')


class GroupSavingsContribution(BaseModel):
    """Individual member contributions to group savings."""
    
    CONTRIBUTION_METHOD_CHOICES = [
        ('CASH', _('Cash')),
        ('TRANSFER', _('Account Transfer')),
        ('MOBILE_MONEY', _('Mobile Money')),
        ('BANK_TRANSFER', _('Bank Transfer')),
        ('CHEQUE', _('Cheque')),
        ('DEDUCTION', _('Salary Deduction')),
    ]
    
    group_savings = models.ForeignKey(
        GroupSavings,
        on_delete=models.CASCADE,
        related_name='member_contributions'
    )
    
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name='group_contributions'
    )
    
    # Contribution amounts
    contribution_amount = MoneyField(
        _("Contribution Amount"),
        max_digits=12,
        decimal_places=2,
        default_currency='UGX'
    )
    
    expected_amount = MoneyField(
        _("Expected Amount"),
        max_digits=12,
        decimal_places=2,
        default_currency='UGX'
    )
    
    variance = MoneyField(
        _("Variance"),
        max_digits=12,
        decimal_places=2,
        default_currency='UGX'
    )
    
    # Attendance and method
    is_present = models.BooleanField(
        _("Is Present"),
        default=True
    )
    
    contribution_method = models.CharField(
        _("Contribution Method"),
        max_length=15,
        choices=CONTRIBUTION_METHOD_CHOICES,
        default='CASH'
    )
    
    receipt_number = models.CharField(
        _("Receipt Number"),
        max_length=50,
        null=True,
        blank=True
    )
    
    # Related transaction
    transaction = models.ForeignKey(
        SavingsTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='group_contribution'
    )
    
    # =============================================================================
    # ESSENTIAL METHODS (NEEDED BY SIGNALS)
    # =============================================================================
    
    def create_savings_transaction(self, processed_by_user=None):
        """Create corresponding savings transaction - NEEDED by signals"""
        if self.transaction or self.contribution_amount.amount <= 0:
            return None
        
        transaction = SavingsTransaction(
            account=self.group_savings.group_account,
            transaction_type='DEPOSIT',
            amount=self.contribution_amount,
            description=f"Group contribution by {self.member.full_name}",
            reference_number=self.receipt_number,
            financial_period=self.group_savings.financial_period
        )
        
        transaction.save()
        
        self.transaction = transaction
        self.save(update_fields=['transaction'])
        
        return transaction
    
    def __str__(self):
        return f"Contribution of {format_money(self.contribution_amount)} by {self.member.full_name}"
    
    class Meta:
        verbose_name = _("Group Savings Contribution")
        verbose_name_plural = _("Group Savings Contributions")
        unique_together = ('group_savings', 'member')


class SavingsGoal(BaseModel):
    """Savings goals for members."""
    
    GOAL_TYPE_CHOICES = [
        ('EDUCATION', _('Education')),
        ('HOUSING', _('Housing/Property')),
        ('VEHICLE', _('Vehicle')),
        ('BUSINESS', _('Business')),
        ('EMERGENCY', _('Emergency Fund')),
        ('RETIREMENT', _('Retirement')),
        ('VACATION', _('Vacation')),
        ('WEDDING', _('Wedding')),
        ('MEDICAL', _('Medical Expenses')),
        ('FARMING', _('Farming/Agriculture')),
        ('OTHER', _('Other')),
    ]
    
    FREQUENCY_CHOICES = [
        ('DAILY', _('Daily')),
        ('WEEKLY', _('Weekly')),
        ('BIWEEKLY', _('Bi-Weekly')),
        ('MONTHLY', _('Monthly')),
        ('QUARTERLY', _('Quarterly')),
    ]
    
    account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.CASCADE,
        related_name='savings_goals'
    )
    
    # Goal details
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
    
    # Target information
    target_amount = MoneyField(
        _("Target Amount"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    current_amount = MoneyField(
        _("Current Amount"),
        max_digits=15,
        decimal_places=2,
        default=Money(0, 'UGX')
    )
    
    start_date = models.DateField(
        _("Start Date"),
        default=timezone.now
    )
    
    target_date = models.DateField(
        _("Target Date")
    )
    
    # Achievement tracking
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
    
    # Contribution settings
    contribution_frequency = models.CharField(
        _("Contribution Frequency"),
        max_length=15,
        choices=FREQUENCY_CHOICES,
        default='MONTHLY'
    )
    
    recommended_contribution = MoneyField(
        _("Recommended Contribution"),
        max_digits=12,
        decimal_places=2,
        default_currency='UGX'
    )
    
    # Auto-contribution
    enable_auto_contribution = models.BooleanField(
        _("Enable Auto Contribution"),
        default=False
    )
    
    auto_contribution_amount = MoneyField(
        _("Auto Contribution Amount"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        default_currency='UGX'
    )
    
    auto_contribution_source = models.ForeignKey(
        SavingsAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='auto_contribution_goals'
    )
    
    # Progress tracking
    last_contribution_date = models.DateField(
        _("Last Contribution Date"),
        null=True,
        blank=True
    )
    
    last_contribution_amount = MoneyField(
        _("Last Contribution Amount"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        default_currency='UGX'
    )
    
    total_contributions = models.PositiveIntegerField(
        _("Total Contributions"),
        default=0
    )
    
    # =============================================================================
    # ESSENTIAL METHODS (NEEDED BY SIGNALS)
    # =============================================================================
    
    def add_contribution(self, amount, contribution_date=None):
        """Add a contribution to the goal - NEEDED by SavingsGoalService in signals"""
        if contribution_date is None:
            contribution_date = timezone.now().date()
        
        if not isinstance(amount, Money):
            amount = Money(amount, self.account.currency)
        
        self.current_amount += amount
        self.last_contribution_date = contribution_date
        self.last_contribution_amount = amount
        self.total_contributions += 1
        
        self.save()
        
        logger.info(f"Contribution of {format_money(amount)} added to goal {self.name}")
    
    def __str__(self):
        return f"{self.name} - {format_money(self.current_amount)}/{format_money(self.target_amount)} ({self.progress_percentage:.1f}%)"
    
    class Meta:
        verbose_name = _("Savings Goal")
        verbose_name_plural = _("Savings Goals")
        ordering = ['target_date']


class SavingsTransactionLimit(BaseModel):
    """Transaction limits for savings accounts and products."""
    
    LIMIT_TYPE_CHOICES = [
        ('WITHDRAWAL_DAILY', _('Daily Withdrawal')),
        ('WITHDRAWAL_WEEKLY', _('Weekly Withdrawal')),
        ('WITHDRAWAL_MONTHLY', _('Monthly Withdrawal')),
        ('DEPOSIT_DAILY', _('Daily Deposit')),
        ('DEPOSIT_WEEKLY', _('Weekly Deposit')),
        ('DEPOSIT_MONTHLY', _('Monthly Deposit')),
        ('TRANSFER_DAILY', _('Daily Transfer')),
        ('TRANSFER_WEEKLY', _('Weekly Transfer')),
        ('TRANSFER_MONTHLY', _('Monthly Transfer')),
        ('TRANSACTION_DAILY', _('Daily Transaction Count')),
        ('TRANSACTION_WEEKLY', _('Weekly Transaction Count')),
        ('TRANSACTION_MONTHLY', _('Monthly Transaction Count')),
    ]
    
    SCOPE_CHOICES = [
        ('PRODUCT', _('Product Level')),
        ('ACCOUNT', _('Account Level')),
        ('MEMBER', _('Member Level')),
    ]
    
    # Scope definition
    scope = models.CharField(
        _("Scope"),
        max_length=10,
        choices=SCOPE_CHOICES,
        default='PRODUCT'
    )
    
    savings_product = models.ForeignKey(
        SavingsProduct,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='transaction_limits'
    )
    
    account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='transaction_limits'
    )
    
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='savings_transaction_limits'
    )
    
    # Limit definition
    limit_type = models.CharField(
        _("Limit Type"),
        max_length=25,
        choices=LIMIT_TYPE_CHOICES
    )
    
    transaction_count_limit = models.PositiveIntegerField(
        _("Transaction Count Limit"),
        null=True,
        blank=True,
        help_text=_("Maximum number of transactions")
    )
    
    amount_limit = MoneyField(
        _("Amount Limit"),
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        default_currency='UGX',
        help_text=_("Maximum amount per period")
    )
    
    # Effective period
    effective_from = models.DateField(
        _("Effective From"),
        default=timezone.now
    )
    
    effective_to = models.DateField(
        _("Effective To"),
        null=True,
        blank=True,
        help_text=_("Leave blank for permanent limit")
    )
    
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    
    # Override settings
    is_hard_limit = models.BooleanField(
        _("Is Hard Limit"),
        default=True,
        help_text=_("Whether limit can be overridden with approval")
    )
    
    def __str__(self):
        scope_name = self.get_scope_display()
        if self.scope == 'PRODUCT':
            scope_detail = self.savings_product.name if self.savings_product else "Unknown"
        elif self.scope == 'ACCOUNT':
            scope_detail = self.account.account_number if self.account else "Unknown"
        elif self.scope == 'MEMBER':
            scope_detail = self.member.full_name if self.member else "Unknown"
        else:
            scope_detail = "Unknown"
        
        return f"{self.get_limit_type_display()} - {scope_name}: {scope_detail}"
    
    class Meta:
        verbose_name = _("Savings Transaction Limit")
        verbose_name_plural = _("Savings Transaction Limits")
        unique_together = (
            ('scope', 'savings_product', 'limit_type'),
            ('scope', 'account', 'limit_type'),
            ('scope', 'member', 'limit_type'),
        )


class SavingsInterestTier(BaseModel):
    """Custom interest rate tiers for individual accounts."""
    
    account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.CASCADE,
        related_name='custom_interest_tiers'
    )
    
    tier_name = models.CharField(
        _("Tier Name"),
        max_length=50,
        help_text=_("Name of this custom interest tier")
    )
    
    min_balance = MoneyField(
        _("Minimum Balance"),
        max_digits=15,
        decimal_places=2,
        default_currency='UGX'
    )
    
    max_balance = MoneyField(
        _("Maximum Balance"),
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        default_currency='UGX',
        help_text=_("Maximum balance for this tier (blank for no upper limit)")
    )
    
    interest_rate = models.DecimalField(
        _("Interest Rate (%)"),
        max_digits=8,
        decimal_places=5,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    is_active = models.BooleanField(
        _("Is Active"),
        default=True
    )
    
    # Effective period
    start_date = models.DateField(
        _("Start Date"),
        default=timezone.now
    )
    
    end_date = models.DateField(
        _("End Date"),
        null=True,
        blank=True,
        help_text=_("Leave blank for permanent tier")
    )
    
    # Approval information
    is_approved = models.BooleanField(
        _("Is Approved"),
        default=False
    )
    
    approval_date = models.DateTimeField(
        _("Approval Date"),
        null=True,
        blank=True
    )
    
    reason = models.TextField(
        _("Reason"),
        null=True,
        blank=True,
        help_text=_("Reason for custom interest rate")
    )
    
    financial_period = models.ForeignKey(
        FinancialPeriod,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='custom_interest_tiers'
    )
    
    def __str__(self):
        max_display = format_money(self.max_balance) if self.max_balance else "No limit"
        return f"{self.tier_name}: {format_money(self.min_balance)} - {max_display} ({self.interest_rate}%)"
    
    class Meta:
        verbose_name = _("Savings Interest Tier")
        verbose_name_plural = _("Savings Interest Tiers")
        ordering = ['min_balance']

