# loans/models.py - Clean version with utilities moved to utils.py

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
import uuid
from dateutil.relativedelta import relativedelta
import os

from sacco_settings.models import (
    SaccoConfiguration, 
    get_sacco_config, 
    get_system_config,
    get_base_currency, 
    format_money,
    TaxRate,
    PaymentMethod,
    FinancialPeriod,
    ExchangeRate,
    BaseModel
)
from members.models import Member
from user_management.models import Member as UserMember
from savings.models import SavingsAccount

# =============================================================================
# ENHANCED LOAN PRODUCT MODEL WITH SACCO SETTINGS INTEGRATION
# =============================================================================

class LoanProduct(BaseModel):
    """Enhanced Loan products with SACCO configuration integration"""
    
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
        ('SEMI_ANNUALLY', 'Semi-Annually'),
        ('ANNUALLY', 'Annually'),
    )
    
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField()
    
    # Use SACCO's base currency for amounts
    min_amount = models.DecimalField(max_digits=12, decimal_places=2)
    max_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    interest_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        help_text="Annual interest rate in percentage"
    )
    interest_type = models.CharField(max_length=20, choices=INTEREST_TYPES)
    interest_calculation = models.CharField(
        max_length=20, 
        choices=INTEREST_CALCULATION, 
        default='MONTHLY'
    )
    
    # Fees as percentages
    loan_processing_fee = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        help_text="Percentage of loan amount"
    )
    insurance_fee = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0, 
        help_text="Percentage of loan amount"
    )
    
    min_term = models.PositiveIntegerField(help_text="Minimum term in months")
    max_term = models.PositiveIntegerField(help_text="Maximum term in months")
    repayment_cycle = models.CharField(max_length=20, choices=REPAYMENT_CYCLE)
    grace_period = models.PositiveIntegerField(default=0, help_text="Grace period in days")
    
    # Savings and guarantor requirements using SACCO settings
    minimum_savings_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        help_text="Minimum savings required as percentage of loan"
    )
    minimum_shares_required = models.PositiveIntegerField(default=0)
    
    # Use SACCO guarantor configuration
    guarantor_required = models.BooleanField(default=None, null=True, blank=True)
    number_of_guarantors = models.PositiveIntegerField(default=0)
    
    collateral_required = models.BooleanField(default=False)
    allow_top_up = models.BooleanField(default=False)
    allow_early_repayment = models.BooleanField(default=True)
    early_repayment_fee = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    penalty_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0, 
        help_text="Late payment penalty percentage"
    )
    penalty_grace_period = models.PositiveIntegerField(
        default=0, 
        help_text="Days before penalty applies"
    )
    penalty_frequency = models.CharField(
        max_length=20, 
        choices=INTEREST_CALCULATION, 
        default='MONTHLY'
    )
    
    status = models.CharField(
        max_length=10, 
        choices=[('ACTIVE', 'Active'), ('INACTIVE', 'Inactive'), ('DEPRECATED', 'Deprecated')],
        default='ACTIVE'
    )
    
    # GL Accounts - will be integrated with Chart of Accounts
    gl_account_principal_code = models.CharField(max_length=20, null=True, blank=True)
    gl_account_interest_code = models.CharField(max_length=20, null=True, blank=True)
    gl_account_penalties_code = models.CharField(max_length=20, null=True, blank=True)
    gl_account_fees_code = models.CharField(max_length=20, null=True, blank=True)
    
    require_bank_account = models.BooleanField(default=False)
    require_credit_check = models.BooleanField(default=True)
    min_credit_score = models.PositiveIntegerField(default=0)
    allow_restructuring = models.BooleanField(default=False)
    
    def clean(self):
        """Enhanced validation using SACCO configuration"""
        super().clean()
        errors = {}
        
        try:
            sacco_config = get_sacco_config()
            
            # Validate guarantor settings against SACCO configuration
            if self.guarantor_required is None:
                self.guarantor_required = sacco_config.allow_loan_guarantors
            
            if self.guarantor_required:
                if self.number_of_guarantors == 0:
                    self.number_of_guarantors = sacco_config.minimum_guarantors
                elif self.number_of_guarantors < sacco_config.minimum_guarantors:
                    errors['number_of_guarantors'] = f'Minimum guarantors required: {sacco_config.minimum_guarantors}'
                elif self.number_of_guarantors > sacco_config.maximum_guarantors:
                    errors['number_of_guarantors'] = f'Maximum guarantors allowed: {sacco_config.maximum_guarantors}'
            
            # Validate amounts against SACCO limits if configured
            if hasattr(sacco_config, 'maximum_loan_amount') and sacco_config.maximum_loan_amount:
                if self.max_amount > sacco_config.maximum_loan_amount.amount:
                    errors['max_amount'] = f'Maximum loan amount cannot exceed SACCO limit of {format_money(sacco_config.maximum_loan_amount)}'
            
            # Validate interest rate ranges
            if hasattr(sacco_config, 'maximum_interest_rate') and sacco_config.maximum_interest_rate:
                if self.interest_rate > sacco_config.maximum_interest_rate:
                    errors['interest_rate'] = f'Interest rate cannot exceed SACCO maximum of {sacco_config.maximum_interest_rate}%'
            
        except Exception as e:
            # Don't fail validation if SACCO config is not available
            pass
        
        # Standard validations
        if self.min_amount >= self.max_amount:
            errors['max_amount'] = 'Maximum amount must be greater than minimum amount'
        
        if self.min_term >= self.max_term:
            errors['max_term'] = 'Maximum term must be greater than minimum term'
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Enhanced save with SACCO configuration defaults"""
        # Apply SACCO defaults if not set
        try:
            sacco_config = get_sacco_config()
            
            if self.guarantor_required is None:
                self.guarantor_required = sacco_config.allow_loan_guarantors
            
            if self.guarantor_required and self.number_of_guarantors == 0:
                self.number_of_guarantors = sacco_config.minimum_guarantors
                
        except:
            pass
        
        super().save(*args, **kwargs)
    
    def get_formatted_min_amount(self):
        """Get formatted minimum amount using SACCO settings"""
        return format_money(self.min_amount)
    
    def get_formatted_max_amount(self):
        """Get formatted maximum amount using SACCO settings"""
        return format_money(self.max_amount)
    
    def calculate_processing_fee(self, loan_amount):
        """Calculate processing fee in SACCO's base currency"""
        fee_amount = (Decimal(str(loan_amount)) * self.loan_processing_fee) / Decimal('100.0')
        return fee_amount
    
    def calculate_insurance_fee(self, loan_amount):
        """Calculate insurance fee in SACCO's base currency"""
        fee_amount = (Decimal(str(loan_amount)) * self.insurance_fee) / Decimal('100.0')
        return fee_amount
    
    def is_member_eligible(self, member):
        """Check if member is eligible for this loan product"""
        try:
            sacco_config = get_sacco_config()
            
            # Check membership duration
            if hasattr(member, 'membership_date'):
                membership_duration = (timezone.now().date() - member.membership_date).days
                min_membership_days = getattr(sacco_config, 'minimum_membership_days', 0)
                if membership_duration < min_membership_days:
                    return False, f"Minimum membership period not met. Required: {min_membership_days} days"
            
            # Check savings requirement
            if self.minimum_savings_percentage > 0:
                required_savings = (self.min_amount * self.minimum_savings_percentage) / 100
                if hasattr(member, 'total_savings') and member.total_savings < required_savings:
                    return False, f"Insufficient savings. Required: {format_money(required_savings)}"
            
            # Check shares requirement
            if self.minimum_shares_required > 0:
                member_shares = getattr(member, 'total_shares', 0)
                if member_shares < self.minimum_shares_required:
                    return False, f"Insufficient shares. Required: {self.minimum_shares_required} shares"
            
            return True, "Eligible"
            
        except Exception as e:
            return True, "Eligibility check failed, defaulting to eligible"
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    class Meta:
        db_table = 'loan_products'
        verbose_name = 'Loan Product'
        verbose_name_plural = 'Loan Products'
        ordering = ['name']
        indexes = [
            models.Index(fields=['status', 'name']),
            models.Index(fields=['code']),
            models.Index(fields=['interest_rate']),
            models.Index(fields=['min_amount', 'max_amount']),
        ]


# =============================================================================
# ENHANCED LOAN APPLICATION WITH SACCO INTEGRATION
# =============================================================================

class LoanApplication(BaseModel):
    """Enhanced loan applications with SACCO configuration"""
    
    STATUS_CHOICES = (
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('UNDER_REVIEW', 'Under Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
        ('DISBURSED', 'Disbursed'),
    )
    
    application_number = models.CharField(max_length=20, unique=True, editable=False)
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='loan_applications')
    loan_product = models.ForeignKey(LoanProduct, on_delete=models.PROTECT)
    
    # Amounts in SACCO's base currency
    amount_requested = models.DecimalField(max_digits=12, decimal_places=2)
    purpose = models.TextField()
    term_months = models.PositiveIntegerField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='DRAFT')
    application_date = models.DateField(auto_now_add=True)
    
    # Fees calculated using SACCO configuration
    processing_fee_paid = models.BooleanField(default=False)
    processing_fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    insurance_fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Approval details
    approved_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    approved_term = models.PositiveIntegerField(null=True, blank=True)
    approved_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)
    
    # User tracking using BaseModel's string-based approach
    reviewed_by_id = models.CharField(max_length=100, null=True, blank=True)
    reviewed_date = models.DateTimeField(null=True, blank=True)
    approved_by_id = models.CharField(max_length=100, null=True, blank=True)
    approval_date = models.DateTimeField(null=True, blank=True)
    
    # Disbursement details
    disbursement_method = models.CharField(
        max_length=20, 
        choices=[
            ('BANK_TRANSFER', 'Bank Transfer'),
            ('MOBILE_MONEY', 'Mobile Money'),
            ('CASH', 'Cash'),
            ('CHEQUE', 'Cheque'),
            ('INTERNAL_TRANSFER', 'Internal Transfer'),
        ],
        null=True,
        blank=True
    )
    disbursement_account = models.CharField(max_length=100, null=True, blank=True)
    recommended_repayment_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        """Enhanced save with SACCO configuration"""
        if not self.application_number:
            # Generate application number using utility function
            from .utils import generate_application_number
            self.application_number = generate_application_number()
            
        # Calculate fees based on loan product and SACCO settings
        if self.loan_product and not self.processing_fee_amount:
            self.processing_fee_amount = self.loan_product.calculate_processing_fee(self.amount_requested)
            self.insurance_fee_amount = self.loan_product.calculate_insurance_fee(self.amount_requested)
            
        super().save(*args, **kwargs)
    
    def clean(self):
        """Enhanced validation using SACCO configuration"""
        super().clean()
        errors = {}
        
        try:
            sacco_config = get_sacco_config()
            
            # Validate against SACCO membership approval requirements
            if sacco_config.membership_approval_required:
                if not hasattr(self.member, 'is_approved') or not self.member.is_approved:
                    errors['member'] = 'Member must be approved before applying for loans'
            
            # Check if SACCO allows new applications
            if hasattr(sacco_config, 'loan_applications_suspended') and sacco_config.loan_applications_suspended:
                errors['__all__'] = 'Loan applications are currently suspended'
            
        except:
            pass
        
        # Validate amount against loan product limits
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
    
    def get_formatted_amount_requested(self):
        """Get formatted requested amount"""
        return format_money(self.amount_requested)
    
    def get_formatted_processing_fee(self):
        """Get formatted processing fee"""
        return format_money(self.processing_fee_amount)
    
    def get_total_fees(self):
        """Calculate total fees for this application"""
        return self.processing_fee_amount + self.insurance_fee_amount
    
    def get_formatted_total_fees(self):
        """Get formatted total fees"""
        return format_money(self.get_total_fees())
    
    def can_be_approved_by(self, user):
        """Check if user can approve this application based on SACCO configuration"""
        try:
            sacco_config = get_sacco_config()
            
            # Check if user has required role/permission
            if hasattr(sacco_config, 'loan_approval_limit'):
                user_limit = getattr(user, 'loan_approval_limit', 0)
                if self.amount_requested > user_limit:
                    return False, f'Amount exceeds your approval limit of {format_money(user_limit)}'
            
            return True, 'Can approve'
            
        except:
            return True, 'Can approve (config check failed)'
    
    def calculate_recommended_payment(self):
        """Calculate recommended payment amount using SACCO settings"""
        if not self.approved_amount or not self.approved_term or not self.approved_interest_rate:
            return None
        
        # Simple calculation - can be enhanced with complex amortization
        monthly_rate = (self.approved_interest_rate / 100) / 12
        if monthly_rate > 0:
            # Standard loan payment formula
            payment = (self.approved_amount * monthly_rate) / (1 - (1 + monthly_rate) ** -self.approved_term)
        else:
            payment = self.approved_amount / self.approved_term
        
        return payment
    
    def get_eligibility_summary(self):
        """Get comprehensive eligibility summary"""
        from .utils import check_application_requirements
        return check_application_requirements(self.id)
    
    def get_approval_readiness_score(self):
        """Calculate approval readiness score (0-100)"""
        score = 0
        
        # Member eligibility (30 points)
        is_eligible, _ = self.loan_product.is_member_eligible(self.member)
        if is_eligible:
            score += 30
        
        # Guarantors (25 points)
        if self.loan_product.guarantor_required:
            required = self.loan_product.number_of_guarantors
            approved = self.guarantors.filter(status='APPROVED').count()
            score += int((approved / required) * 25) if required > 0 else 25
        else:
            score += 25
        
        # Collateral (20 points)
        if self.loan_product.collateral_required:
            verified_collateral = self.collaterals.filter(is_verified=True).exists()
            if verified_collateral:
                score += 20
        else:
            score += 20
        
        # Documents (15 points)
        required_docs = self.documents.filter(is_required=True)
        if required_docs.exists():
            verified_docs = required_docs.filter(is_verified=True)
            score += int((verified_docs.count() / required_docs.count()) * 15)
        else:
            score += 15
        
        # Fees paid (10 points)
        if not self.loan_product.loan_processing_fee or self.processing_fee_paid:
            score += 10
        
        return min(score, 100)
    
    def validate_for_approval(self):
        """Validate application for approval"""
        errors = []
        
        # Check eligibility
        is_eligible, message = self.loan_product.is_member_eligible(self.member)
        if not is_eligible:
            errors.append(f"Member eligibility: {message}")
        
        # Check guarantors
        if self.loan_product.guarantor_required:
            required = self.loan_product.number_of_guarantors
            approved = self.guarantors.filter(status='APPROVED').count()
            if approved < required:
                errors.append(f"Need {required - approved} more guarantors")
        
        # Check documents
        required_docs = self.documents.filter(is_required=True, is_verified=False)
        if required_docs.exists():
            errors.append(f"{required_docs.count()} required documents not verified")
        
        # Check fees
        if self.loan_product.loan_processing_fee > 0 and not self.processing_fee_paid:
            errors.append("Processing fee not paid")
        
        return len(errors) == 0, errors
    
    @property
    def is_approvable(self):
        """Check if application can be approved"""
        valid, _ = self.validate_for_approval()
        return valid
    
    @property
    def approval_readiness_percentage(self):
        """Get approval readiness as percentage"""
        return self.get_approval_readiness_score()
    
    @property
    def days_since_application(self):
        """Get days since application was submitted"""
        return (timezone.now().date() - self.application_date).days
    
    def __str__(self):
        return f"Application #{self.application_number} - {self.member} ({self.get_status_display()})"
    
    class Meta:
        db_table = 'loan_applications'
        verbose_name = 'Loan Application'
        verbose_name_plural = 'Loan Applications'
        ordering = ['-application_date']
        indexes = [
            models.Index(fields=['status', 'application_date']),
            models.Index(fields=['member', 'status']),
            models.Index(fields=['loan_product', 'status']),
            models.Index(fields=['amount_requested']),
            models.Index(fields=['processing_fee_paid']),
        ]


# =============================================================================
# ENHANCED LOAN MODEL WITH FULL SACCO INTEGRATION
# =============================================================================

class Loan(BaseModel):
    """Enhanced active loans with comprehensive SACCO integration"""
    
    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('PAID', 'Paid'),
        ('DEFAULTED', 'Defaulted'),
        ('WRITTEN_OFF', 'Written Off'),
        ('RESTRUCTURED', 'Restructured'),
        ('FROZEN', 'Frozen'),
    )
    
    loan_number = models.CharField(max_length=20, unique=True)
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='loans')
    loan_product = models.ForeignKey(LoanProduct, on_delete=models.PROTECT)
    application = models.OneToOneField(
        LoanApplication, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_loan'
    )
    
    # Loan amounts in SACCO's base currency
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    term_months = models.PositiveIntegerField()
    payment_frequency = models.CharField(max_length=20, choices=LoanProduct.REPAYMENT_CYCLE)
    
    # Important dates
    disbursement_date = models.DateField()
    first_payment_date = models.DateField()
    last_payment_date = models.DateField(null=True, blank=True)
    expected_end_date = models.DateField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='ACTIVE')
    last_status_change = models.DateTimeField(null=True, blank=True)
    
    # Calculated Fields - all in SACCO's base currency
    total_interest = models.DecimalField(max_digits=12, decimal_places=2)
    total_fees = models.DecimalField(max_digits=10, decimal_places=2)
    total_payable = models.DecimalField(max_digits=12, decimal_places=2)
    total_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_paid_principal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_paid_interest = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_paid_penalties = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_paid_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Outstanding Balances
    outstanding_principal = models.DecimalField(max_digits=12, decimal_places=2)
    outstanding_interest = models.DecimalField(max_digits=12, decimal_places=2)
    outstanding_penalties = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    outstanding_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    outstanding_total = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Status tracking enhanced with SACCO business logic
    days_in_arrears = models.PositiveIntegerField(default=0)
    last_payment_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    next_payment_date = models.DateField(null=True, blank=True)
    next_payment_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # For restructured loans
    is_restructured = models.BooleanField(default=False)
    original_loan = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='restructured_to'
    )
    
    # Enhanced user tracking using BaseModel approach
    approved_by_id = models.CharField(max_length=100, null=True, blank=True)
    disbursed_by_id = models.CharField(max_length=100, null=True, blank=True)
    
    # Accounting integration
    gl_transaction_reference = models.CharField(max_length=50, null=True, blank=True)
    financial_period = models.ForeignKey(
        FinancialPeriod, 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True,
        help_text="Financial period when loan was disbursed"
    )
    
    def save(self, *args, **kwargs):
        """Enhanced save with SACCO configuration and business logic"""
        # Track status changes
        if self.pk:
            try:
                old_instance = Loan.objects.get(pk=self.pk)
                if old_instance.status != self.status:
                    self.last_status_change = timezone.now()
            except Loan.DoesNotExist:
                pass
        
        if not self.loan_number:
            # Use utility function for loan number generation
            from .utils import generate_loan_number
            self.loan_number = generate_loan_number(self.loan_product, self.member)
        
        # Set financial period if not set
        if not self.financial_period:
            try:
                self.financial_period = FinancialPeriod.get_period_for_date(
                    self.disbursement_date or timezone.now().date(),
                    period_type='MONTH'
                )
            except:
                pass
        
        # Calculate outstanding total
        self.outstanding_total = (
            self.outstanding_principal + 
            self.outstanding_interest + 
            self.outstanding_penalties + 
            self.outstanding_fees
        )
        
        # Update status based on balances and SACCO rules
        self.update_loan_status()
        
        super().save(*args, **kwargs)
    
    def update_loan_status(self):
        """Update loan status based on SACCO business rules"""
        try:
            sacco_config = get_sacco_config()
            
            # Check if loan is fully paid
            if self.outstanding_total <= 0:
                self.status = 'PAID'
                return
            
            # Check for default based on SACCO configuration
            default_days = getattr(sacco_config, 'loan_default_days', 90)
            if self.days_in_arrears >= default_days:
                self.status = 'DEFAULTED'
                return
            
            # Otherwise, keep as active
            if self.status not in ['WRITTEN_OFF', 'RESTRUCTURED', 'FROZEN']:
                self.status = 'ACTIVE'
                
        except:
            # Fallback logic if SACCO config is not available
            if self.outstanding_total <= 0:
                self.status = 'PAID'
            elif self.days_in_arrears >= 90:
                self.status = 'DEFAULTED'
            elif self.status not in ['WRITTEN_OFF', 'RESTRUCTURED', 'FROZEN']:
                self.status = 'ACTIVE'
    
    def calculate_penalty(self, as_of_date=None):
        """Calculate penalty based on SACCO configuration and loan product"""
        if not as_of_date:
            as_of_date = timezone.now().date()
        
        if self.days_in_arrears <= self.loan_product.penalty_grace_period:
            return Decimal('0.00')
        
        # Calculate penalty based on loan product settings
        overdue_days = self.days_in_arrears - self.loan_product.penalty_grace_period
        penalty_rate = self.loan_product.penalty_rate / 100
        
        # Calculate penalty on outstanding amount
        penalty_amount = self.outstanding_principal * penalty_rate
        
        # Adjust based on frequency
        if self.loan_product.penalty_frequency == 'DAILY':
            penalty_amount = penalty_amount * overdue_days / 365
        elif self.loan_product.penalty_frequency == 'WEEKLY':
            penalty_amount = penalty_amount * (overdue_days / 7) / 52
        elif self.loan_product.penalty_frequency == 'MONTHLY':
            penalty_amount = penalty_amount * (overdue_days / 30) / 12
        
        return penalty_amount
    
    def get_formatted_amounts(self):
        """Get all amounts formatted using SACCO configuration"""
        return {
            'principal': format_money(self.principal_amount),
            'total_payable': format_money(self.total_payable),
            'outstanding_total': format_money(self.outstanding_total),
            'outstanding_principal': format_money(self.outstanding_principal),
            'outstanding_interest': format_money(self.outstanding_interest),
            'total_paid': format_money(self.total_paid),
        }
    
    def get_payment_methods(self):
        """Get available payment methods for this loan"""
        return PaymentMethod.get_methods_for_amount(self.next_payment_amount or 0)
    
    def calculate_early_settlement(self, as_of_date=None):
        """Calculate early settlement amount including applicable fees"""
        if not as_of_date:
            as_of_date = timezone.now().date()
        
        settlement_amount = self.outstanding_principal + self.outstanding_interest
        
        # Add early repayment fee if applicable
        if self.loan_product.allow_early_repayment and self.loan_product.early_repayment_fee > 0:
            fee = (settlement_amount * self.loan_product.early_repayment_fee) / 100
            settlement_amount += fee
        
        # Add any outstanding penalties and fees
        settlement_amount += self.outstanding_penalties + self.outstanding_fees
        
        return settlement_amount
    
    def is_eligible_for_top_up(self):
        """Check if loan is eligible for top-up based on SACCO rules"""
        if not self.loan_product.allow_top_up:
            return False, "Top-up not allowed for this product"
        
        if self.status != 'ACTIVE':
            return False, "Loan must be active for top-up"
        
        if self.days_in_arrears > 0:
            return False, "Loan must be current (no arrears) for top-up"
        
        # Check minimum payment history
        try:
            sacco_config = get_sacco_config()
            min_payments = getattr(sacco_config, 'min_payments_for_topup', 6)
            
            payment_count = self.payments.count()
            if payment_count < min_payments:
                return False, f"Minimum {min_payments} payments required for top-up"
        except:
            pass
        
        return True, "Eligible for top-up"
    
    def get_payment_history_summary(self):
        """Get payment history summary"""
        from django.db.models import Sum, Count, Avg
        
        payments = self.payments.filter(is_reversed=False)
        return payments.aggregate(
            total_payments=Count('id'),
            total_amount=Sum('amount'),
            average_payment=Avg('amount'),
            total_principal=Sum('principal_amount'),
            total_interest=Sum('interest_amount')
        )
    
    def get_risk_assessment(self):
        """Get loan risk assessment"""
        risk_factors = []
        risk_score = 0
        
        # Days in arrears risk
        if self.days_in_arrears > 90:
            risk_factors.append("Severely overdue")
            risk_score += 40
        elif self.days_in_arrears > 30:
            risk_factors.append("Overdue payments")
            risk_score += 20
        elif self.days_in_arrears > 0:
            risk_factors.append("Minor delays")
            risk_score += 10
        
        # Outstanding amount risk
        if self.outstanding_total > self.principal_amount:
            risk_factors.append("Growing debt")
            risk_score += 15
        
        # Payment consistency
        payments = self.payments.filter(is_reversed=False)
        if payments.count() > 0:
            late_payments = payments.filter(
                payment_date__gt=models.F('loan__schedule__due_date')
            ).count()
            
            late_percentage = (late_payments / payments.count()) * 100
            if late_percentage > 50:
                risk_factors.append("Inconsistent payment history")
                risk_score += 25
        
        # Determine risk level
        if risk_score <= 20:
            risk_level = 'LOW'
        elif risk_score <= 50:
            risk_level = 'MEDIUM'
        else:
            risk_level = 'HIGH'
        
        return {
            'risk_level': risk_level,
            'risk_score': min(risk_score, 100),
            'risk_factors': risk_factors
        }
    
    def calculate_projected_completion_date(self):
        """Calculate projected completion date based on current payment pattern"""
        if self.outstanding_total <= 0:
            return self.last_payment_date
        
        # Get average monthly payment from last 3 months
        from datetime import timedelta
        three_months_ago = timezone.now().date() - timedelta(days=90)
        
        recent_payments = self.payments.filter(
            payment_date__gte=three_months_ago,
            is_reversed=False
        )
        
        if recent_payments.exists():
            avg_payment = recent_payments.aggregate(
                avg=models.Avg('amount')
            )['avg']
            
            if avg_payment and avg_payment > 0:
                months_remaining = self.outstanding_total / avg_payment
                projected_date = timezone.now().date() + timedelta(days=int(months_remaining * 30))
                return projected_date
        
        return self.expected_end_date
    
    def get_approved_by_user(self):
        """Get user who approved this loan"""
        if self.approved_by_id:
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                return User.objects.using('default').get(pk=self.approved_by_id)
            except:
                return None
        return None
    
    def get_disbursed_by_user(self):
        """Get user who disbursed this loan"""
        if self.disbursed_by_id:
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                return User.objects.using('default').get(pk=self.disbursed_by_id)
            except:
                return None
        return None
    
    @property
    def payment_progress_percentage(self):
        """Get payment progress as percentage"""
        if self.total_payable > 0:
            return (self.total_paid / self.total_payable) * 100
        return 0
    
    @property
    def is_overdue(self):
        """Check if loan has overdue payments"""
        return self.days_in_arrears > 0
    
    @property
    def is_current(self):
        """Check if loan is current (no overdue payments)"""
        return self.days_in_arrears == 0 and self.status == 'ACTIVE'
    
    @property
    def next_installment(self):
        """Get next pending installment"""
        return self.schedule.filter(status='PENDING').order_by('due_date').first()
    
    @property
    def overdue_installments(self):
        """Get all overdue installments"""
        return self.schedule.filter(status='OVERDUE').order_by('due_date')
    
    def __str__(self):
        return f"Loan #{self.loan_number} - {self.member} ({format_money(self.principal_amount)})"
    
    class Meta:
        db_table = 'loans'
        verbose_name = 'Loan'
        verbose_name_plural = 'Loans'
        ordering = ['-disbursement_date']
        indexes = [
            models.Index(fields=['status', 'disbursement_date']),
            models.Index(fields=['member', 'status']),
            models.Index(fields=['loan_product', 'status']),
            models.Index(fields=['days_in_arrears']),
            models.Index(fields=['outstanding_total']),
            models.Index(fields=['expected_end_date']),
            models.Index(fields=['last_payment_date']),
            models.Index(fields=['financial_period']),
            models.Index(fields=['loan_number']),
        ]


# =============================================================================
# ENHANCED LOAN PAYMENT WITH SACCO INTEGRATION
# =============================================================================

class LoanPayment(BaseModel):
    """Enhanced loan payments with SACCO configuration integration"""
    
    PAYMENT_METHODS = (
        ('CASH', 'Cash'),
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('CHEQUE', 'Cheque'),
        ('MOBILE_MONEY', 'Mobile Money'),
        ('INTERNAL_TRANSFER', 'Internal Transfer'),
        ('STANDING_ORDER', 'Standing Order'),
        ('AUTO_DEDUCTION', 'Auto Deduction'),
    )
    
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='payments')
    payment_number = models.CharField(max_length=20, unique=True)
    payment_date = models.DateField()
    
    # Payment amounts in SACCO's base currency
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_amount = models.DecimalField(max_digits=12, decimal_places=2)
    penalty_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    payment_method_ref = models.ForeignKey(
        PaymentMethod, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Reference to payment method configuration"
    )
    
    reference_number = models.CharField(max_length=100, null=True, blank=True)
    receipt_number = models.CharField(max_length=50, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    
    # Enhanced user tracking
    processed_by_id = models.CharField(max_length=100, null=True, blank=True)
    
    # Reversal handling
    is_reversed = models.BooleanField(default=False)
    reversed_by_id = models.CharField(max_length=100, null=True, blank=True)
    reversal_reason = models.TextField(null=True, blank=True)
    reversal_date = models.DateTimeField(null=True, blank=True)
    
    # Accounting integration
    gl_transaction_reference = models.CharField(max_length=50, null=True, blank=True)
    financial_period = models.ForeignKey(
        FinancialPeriod, 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True
    )
    
    # Tax handling
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_rate_applied = models.ForeignKey(
        TaxRate, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    
    def save(self, *args, **kwargs):
        """Enhanced save with SACCO configuration"""
        if not self.payment_number:
            # Use utility function for payment number generation
            from .utils import generate_payment_number
            self.payment_number = generate_payment_number()
        
        # Set financial period
        if not self.financial_period:
            try:
                self.financial_period = FinancialPeriod.get_period_for_date(
                    self.payment_date,
                    period_type='MONTH'
                )
            except:
                pass
        
        # Calculate tax if applicable
        if not self.tax_amount and not self.is_reversed:
            self.calculate_tax()
        
        super().save(*args, **kwargs)
        
        # Update loan balances after payment (controlled here vs signals)
        if not self.is_reversed:
            self.update_loan_balances()
    
    def calculate_tax(self):
        """Calculate applicable tax on payment using SACCO tax configuration"""
        try:
            # Check if there's a tax rate for interest payments
            interest_tax = TaxRate.get_tax_for_type('INTEREST', self.payment_date)
            if interest_tax and self.interest_amount > 0:
                self.tax_amount = interest_tax.calculate_tax(self.interest_amount, 'interest')
                self.tax_rate_applied = interest_tax
        except:
            pass
    
    def update_loan_balances(self):
        """Update loan balances after this payment"""
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
        loan.last_payment_amount = self.amount
        loan.last_payment_date = self.payment_date
        
        # Reset arrears if payment brings loan current
        if (loan.outstanding_principal + loan.outstanding_interest + 
            loan.outstanding_penalties + loan.outstanding_fees) <= 0:
            loan.days_in_arrears = 0
        
        loan.save()
    
    def get_formatted_amount(self):
        """Get formatted payment amount"""
        return format_money(self.amount)
    
    def get_payment_breakdown(self):
        """Get formatted breakdown of payment"""
        return {
            'total': format_money(self.amount),
            'principal': format_money(self.principal_amount),
            'interest': format_money(self.interest_amount),
            'penalties': format_money(self.penalty_amount),
            'fees': format_money(self.fee_amount),
            'tax': format_money(self.tax_amount),
        }
    
    def can_be_reversed(self, user=None):
        """Check if payment can be reversed based on SACCO rules"""
        if self.is_reversed:
            return False, "Payment is already reversed"
        
        try:
            sacco_config = get_sacco_config()
            
            # Check time limit for reversals
            reversal_limit_days = getattr(sacco_config, 'payment_reversal_limit_days', 30)
            days_since_payment = (timezone.now().date() - self.payment_date).days
            
            if days_since_payment > reversal_limit_days:
                return False, f"Reversal time limit ({reversal_limit_days} days) exceeded"
            
            # Check if financial period is closed
            if self.financial_period and self.financial_period.is_closed:
                return False, "Cannot reverse payment in closed financial period"
            
            # Check user permissions
            if user:
                reversal_limit = getattr(user, 'payment_reversal_limit', Decimal('0.00'))
                if self.amount > reversal_limit:
                    return False, f"Payment amount exceeds your reversal limit of {format_money(reversal_limit)}"
        
        except:
            pass
        
        return True, "Payment can be reversed"
    
    def reverse_payment(self, user, reason):
        """Reverse this payment"""
        can_reverse, message = self.can_be_reversed(user)
        if not can_reverse:
            return False, message
        
        # Mark as reversed
        self.is_reversed = True
        self.reversed_by_id = str(user.pk) if user else None
        self.reversal_reason = reason
        self.reversal_date = timezone.now()
        
        # Reverse loan balance updates
        loan = self.loan
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
        self.save()
        
        return True, "Payment reversed successfully"
    
    def get_processed_by_user(self):
        """Get user who processed this payment"""
        if self.processed_by_id:
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                return User.objects.using('default').get(pk=self.processed_by_id)
            except:
                return None
        return None
    
    def __str__(self):
        return f"Payment #{self.payment_number} for {self.loan} - {format_money(self.amount)}"
    
    class Meta:
        ordering = ['-payment_date']
        db_table = 'loan_payments'
        verbose_name = 'Loan Payment'
        verbose_name_plural = 'Loan Payments'
        indexes = [
            models.Index(fields=['loan', 'payment_date']),
            models.Index(fields=['payment_method', 'payment_date']),
            models.Index(fields=['is_reversed']),
            models.Index(fields=['financial_period']),
            models.Index(fields=['processed_by_id']),
            models.Index(fields=['payment_number']),
        ]


# =============================================================================
# LOAN GUARANTOR MODEL
# =============================================================================

class LoanGuarantor(BaseModel):
    """Enhanced guarantors for loan applications with SACCO integration"""
    
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
        ('RELEASED', 'Released'),
    )
    
    loan_application = models.ForeignKey(
        LoanApplication, 
        on_delete=models.CASCADE, 
        related_name='guarantors'
    )
    guarantor = models.ForeignKey(
        Member, 
        on_delete=models.CASCADE, 
        related_name='guarantor_for'
    )
    
    # Guarantee amount in SACCO's base currency
    guarantee_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    relationship = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    notes = models.TextField(null=True, blank=True)
    request_date = models.DateTimeField(auto_now_add=True)
    response_date = models.DateTimeField(null=True, blank=True)
    release_date = models.DateField(null=True, blank=True)
    release_reason = models.TextField(null=True, blank=True)
    
    # Enhanced notification settings using SACCO config
    notification_sent = models.BooleanField(default=False)
    reminder_count = models.PositiveIntegerField(default=0)
    last_reminder_date = models.DateTimeField(null=True, blank=True)
    
    def clean(self):
        """Enhanced validation using SACCO configuration"""
        super().clean()
        errors = {}
        
        try:
            sacco_config = get_sacco_config()
            
            # Validate guarantor is not the applicant
            if self.guarantor == self.loan_application.member:
                errors['guarantor'] = 'Guarantor cannot be the loan applicant'
            
            # Check if guarantor is eligible based on SACCO rules
            if not self.is_guarantor_eligible():
                errors['guarantor'] = 'Selected member is not eligible to be a guarantor'
            
            # Validate guarantee amount
            min_guarantee = getattr(sacco_config, 'minimum_guarantee_percentage', 10)
            min_amount = (self.loan_application.amount_requested * min_guarantee) / 100
            
            if self.guarantee_amount < min_amount:
                errors['guarantee_amount'] = f'Minimum guarantee amount is {format_money(min_amount)}'
            
        except Exception as e:
            # Don't fail validation if SACCO config is unavailable
            pass
        
        if errors:
            raise ValidationError(errors)
    
    def is_guarantor_eligible(self):
        """Check if member can be a guarantor based on SACCO rules"""
        try:
            sacco_config = get_sacco_config()
            
            # Check if guarantor is an active member
            if not self.guarantor.is_active:
                return False
            
            # Check membership duration
            min_membership_days = getattr(sacco_config, 'guarantor_min_membership_days', 365)
            membership_days = (timezone.now().date() - self.guarantor.membership_date).days
            if membership_days < min_membership_days:
                return False
            
            # Check guarantor's savings balance
            min_savings = getattr(sacco_config, 'guarantor_min_savings', 0)
            if min_savings > 0:
                guarantor_savings = getattr(self.guarantor, 'total_savings', 0)
                if guarantor_savings < min_savings:
                    return False
            
            # Check guarantor's share balance
            min_shares = getattr(sacco_config, 'guarantor_min_shares', 0)
            if min_shares > 0:
                guarantor_shares = getattr(self.guarantor, 'total_shares', 0)
                if guarantor_shares < min_shares:
                    return False
            
            # Check guarantor's current guarantees limit
            max_guarantees = getattr(sacco_config, 'max_active_guarantees_per_member', 5)
            current_guarantees = LoanGuarantor.objects.filter(
                guarantor=self.guarantor,
                status='APPROVED',
                loan_application__status__in=['APPROVED', 'DISBURSED']
            ).count()
            
            if current_guarantees >= max_guarantees:
                return False
            
            return True
            
        except Exception:
            # Default to True if config check fails
            return True
    
    def send_notification(self, notification_type='REQUEST'):
        """Send notification to guarantor using SACCO communication settings"""
        try:
            sacco_config = get_sacco_config()
            
            if not (sacco_config.enable_sms_notifications or sacco_config.enable_email_notifications):
                return False, "Notifications are disabled"
            
            # Prepare message content
            messages = {
                'REQUEST': f"You have been requested to guarantee a loan of {format_money(self.loan_application.amount_requested)} for {self.loan_application.member.get_full_name()}. Please respond in the SACCO portal.",
                'REMINDER': f"Reminder: Please respond to the loan guarantee request for {self.loan_application.member.get_full_name()} - Amount: {format_money(self.loan_application.amount_requested)}",
                'APPROVED': f"Thank you for approving the loan guarantee for {self.loan_application.member.get_full_name()}. The loan has been processed.",
                'REJECTED': f"Your guarantee for {self.loan_application.member.get_full_name()}'s loan has been noted. The application will be reviewed.",
                'RELEASED': f"Your guarantee obligation for {self.loan_application.member.get_full_name()}'s loan has been released. Thank you for your support."
            }
            
            message = messages.get(notification_type, messages['REQUEST'])
            
            # Update notification tracking
            if notification_type in ['REQUEST', 'REMINDER']:
                self.notification_sent = True
                if notification_type == 'REMINDER':
                    self.reminder_count += 1
                    self.last_reminder_date = timezone.now()
                self.save()
            
            return True, "Notification sent successfully"
            
        except Exception as e:
            return False, f"Failed to send notification: {str(e)}"
    
    def get_formatted_guarantee_amount(self):
        """Get formatted guarantee amount"""
        return format_money(self.guarantee_amount)
    
    def get_guarantee_percentage(self):
        """Get guarantee amount as percentage of loan amount"""
        if self.loan_application.amount_requested > 0:
            return (self.guarantee_amount / self.loan_application.amount_requested) * 100
        return 0
    
    def can_withdraw_guarantee(self):
        """Check if guarantor can withdraw their guarantee"""
        if self.status != 'APPROVED':
            return True, "Can withdraw - guarantee not approved"
        
        loan = getattr(self.loan_application, 'approved_loan', None)
        if not loan:
            return True, "Can withdraw - loan not disbursed"
        
        if loan.status in ['PAID', 'WRITTEN_OFF']:
            return True, "Can withdraw - loan completed"
        
        try:
            sacco_config = get_sacco_config()
            min_payment_count = getattr(sacco_config, 'guarantor_release_min_payments', 12)
            
            payment_count = loan.payments.filter(is_reversed=False).count()
            if payment_count >= min_payment_count:
                return True, f"Can withdraw - minimum {min_payment_count} payments made"
        except:
            pass
        
        return False, "Cannot withdraw - loan still active with insufficient payment history"
    
    def approve_guarantee(self, user=None):
        """Approve this guarantee"""
        if self.status != 'PENDING':
            return False, "Guarantee is not in pending status"
        
        self.status = 'APPROVED'
        self.response_date = timezone.now()
        if user:
            self.updated_by_id = str(user.pk)
        
        self.save()
        
        # Send confirmation notification
        self.send_notification('APPROVED')
        
        return True, "Guarantee approved successfully"
    
    def reject_guarantee(self, reason=None, user=None):
        """Reject this guarantee"""
        if self.status != 'PENDING':
            return False, "Guarantee is not in pending status"
        
        self.status = 'REJECTED'
        self.response_date = timezone.now()
        if reason:
            self.notes = f"Rejection reason: {reason}"
        if user:
            self.updated_by_id = str(user.pk)
        
        self.save()
        
        # Send notification
        self.send_notification('REJECTED')
        
        return True, "Guarantee rejected successfully"
    
    def __str__(self):
        return f"{self.guarantor} for {self.loan_application} - {self.get_status_display()}"
    
    class Meta:
        unique_together = ('loan_application', 'guarantor')
        db_table = 'loan_guarantors'
        verbose_name = 'Loan Guarantor'
        verbose_name_plural = 'Loan Guarantors'
        indexes = [
            models.Index(fields=['status', 'request_date']),
            models.Index(fields=['guarantor', 'status']),
        ]


# =============================================================================
# LOAN COLLATERAL MODEL
# =============================================================================

class LoanCollateral(BaseModel):
    """Enhanced collateral for loan applications with SACCO integration"""
    
    COLLATERAL_TYPES = (
        ('REAL_ESTATE', 'Real Estate'),
        ('VEHICLE', 'Vehicle'),
        ('EQUIPMENT', 'Equipment'),
        ('SHARES', 'Shares'),
        ('FIXED_DEPOSIT', 'Fixed Deposit'),
        ('LIVESTOCK', 'Livestock'),
        ('INVENTORY', 'Inventory'),
        ('JEWELRY', 'Jewelry'),
        ('ELECTRONICS', 'Electronics'),
        ('OTHER', 'Other'),
    )
    
    CONDITION_CHOICES = (
        ('EXCELLENT', 'Excellent'),
        ('GOOD', 'Good'),
        ('FAIR', 'Fair'),
        ('POOR', 'Poor'),
    )
    
    loan_application = models.ForeignKey(
        LoanApplication, 
        on_delete=models.CASCADE, 
        related_name='collaterals'
    )
    collateral_type = models.CharField(max_length=15, choices=COLLATERAL_TYPES)
    description = models.TextField()
    
    # Value in SACCO's base currency
    estimated_value = models.DecimalField(max_digits=12, decimal_places=2)
    appraised_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    forced_sale_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    valuation_date = models.DateField()
    location = models.TextField(null=True, blank=True)
    condition = models.CharField(max_length=10, choices=CONDITION_CHOICES, default='GOOD')
    
    # Document management
    ownership_document = models.FileField(upload_to='collateral_documents/', null=True, blank=True)
    photo = models.ImageField(upload_to='collateral_photos/', null=True, blank=True)
    valuation_report = models.FileField(upload_to='collateral_valuations/', null=True, blank=True)
    
    # Identification details
    registration_number = models.CharField(max_length=100, null=True, blank=True)
    serial_number = models.CharField(max_length=100, null=True, blank=True)
    make_model = models.CharField(max_length=100, null=True, blank=True)
    year_of_manufacture = models.PositiveIntegerField(null=True, blank=True)
    
    # Valuation details
    valuer_name = models.CharField(max_length=100, null=True, blank=True)
    valuer_contact = models.CharField(max_length=100, null=True, blank=True)
    valuer_license = models.CharField(max_length=50, null=True, blank=True)
    
    # Verification status
    is_verified = models.BooleanField(default=False)
    verified_by_id = models.CharField(max_length=100, null=True, blank=True)
    verification_date = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(null=True, blank=True)

    # Insurance details
    is_insured = models.BooleanField(default=False)
    insurance_company = models.CharField(max_length=100, null=True, blank=True)
    insurance_policy_number = models.CharField(max_length=50, null=True, blank=True)
    insurance_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    insurance_expiry = models.DateField(null=True, blank=True)
    
    def clean(self):
        """Enhanced validation using SACCO configuration"""
        super().clean()
        errors = {}
        
        try:
            sacco_config = get_sacco_config()
            
            # Validate collateral value against loan amount
            loan_amount = self.loan_application.amount_requested
            min_collateral_ratio = getattr(sacco_config, 'minimum_collateral_ratio', 120)  # 120% of loan
            
            min_required_value = (loan_amount * min_collateral_ratio) / 100
            collateral_value = self.appraised_value or self.estimated_value
            
            if collateral_value < min_required_value:
                errors['appraised_value'] = f'Collateral value must be at least {format_money(min_required_value)} ({min_collateral_ratio}% of loan amount)'
            
            # Check if collateral type is accepted
            accepted_types = getattr(sacco_config, 'accepted_collateral_types', [])
            if accepted_types and self.collateral_type not in accepted_types:
                errors['collateral_type'] = f'This collateral type is not accepted by the SACCO'
            
            # Validate valuation date
            max_valuation_age_days = getattr(sacco_config, 'max_collateral_valuation_age_days', 365)
            valuation_age = (timezone.now().date() - self.valuation_date).days
            
            if valuation_age > max_valuation_age_days:
                errors['valuation_date'] = f'Valuation is too old. Maximum age: {max_valuation_age_days} days'
            
        except Exception:
            pass
        
        # Standard validations
        if self.appraised_value and self.estimated_value:
            if self.appraised_value > self.estimated_value * 2:
                errors['appraised_value'] = 'Appraised value seems unreasonably high compared to estimated value'
        
        if self.year_of_manufacture:
            current_year = timezone.now().year
            if self.year_of_manufacture > current_year:
                errors['year_of_manufacture'] = 'Year of manufacture cannot be in the future'
        
        if errors:
            raise ValidationError(errors)
    
    def calculate_loan_to_value_ratio(self):
        """Calculate loan-to-value ratio"""
        collateral_value = self.appraised_value or self.estimated_value
        if collateral_value > 0:
            return (self.loan_application.amount_requested / collateral_value) * 100
        return 0
    
    def get_collateral_coverage(self):
        """Get collateral coverage percentage"""
        return 100 / self.calculate_loan_to_value_ratio() if self.calculate_loan_to_value_ratio() > 0 else 0
    
    def is_valuation_current(self):
        """Check if valuation is still current based on SACCO rules"""
        try:
            sacco_config = get_sacco_config()
            max_age_days = getattr(sacco_config, 'max_collateral_valuation_age_days', 365)
            
            age_days = (timezone.now().date() - self.valuation_date).days
            return age_days <= max_age_days
        except:
            # Default to 1 year if config not available
            age_days = (timezone.now().date() - self.valuation_date).days
            return age_days <= 365
    
    def verify_collateral(self, user, notes=None):
        """Verify this collateral"""
        if self.is_verified:
            return False, "Collateral is already verified"
        
        self.is_verified = True
        self.verified_by_id = str(user.pk) if user else None
        self.verification_date = timezone.now()
        if notes:
            self.verification_notes = notes
        
        self.save()
        return True, "Collateral verified successfully"
    
    def get_formatted_values(self):
        """Get formatted collateral values"""
        return {
            'estimated_value': format_money(self.estimated_value),
            'appraised_value': format_money(self.appraised_value) if self.appraised_value else 'Not appraised',
            'forced_sale_value': format_money(self.forced_sale_value) if self.forced_sale_value else 'Not determined',
            'insurance_value': format_money(self.insurance_value) if self.insurance_value else 'Not insured',
        }
    
    def __str__(self):
        return f"{self.get_collateral_type_display()} for {self.loan_application} - {format_money(self.estimated_value)}"
    
    class Meta:
        db_table = 'loan_collaterals'
        verbose_name = 'Loan Collateral'
        verbose_name_plural = 'Loan Collaterals'
        ordering = ['-valuation_date']
        indexes = [
            models.Index(fields=['collateral_type', 'is_verified']),
            models.Index(fields=['valuation_date']),
            models.Index(fields=['is_insured', 'insurance_expiry']),
        ]


# =============================================================================
# LOAN SCHEDULE MODEL
# =============================================================================

class LoanSchedule(BaseModel):
    """Enhanced repayment schedule with SACCO integration"""
    
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('WAIVED', 'Waived'),
    )
    
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='schedule')
    installment_number = models.PositiveIntegerField()
    due_date = models.DateField()
    
    # Scheduled amounts in SACCO's base currency
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_amount = models.DecimalField(max_digits=12, decimal_places=2)
    fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    penalty_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Paid amounts
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_principal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_interest = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid_penalty = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Balance and status
    balance = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    paid_date = models.DateField(null=True, blank=True)
    days_late = models.IntegerField(default=0)
    
    # Financial period tracking
    financial_period = models.ForeignKey(
        FinancialPeriod, 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True,
        help_text="Financial period when this installment is due"
    )
    
    # Waiver tracking
    is_waived = models.BooleanField(default=False)
    waived_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    waived_by_id = models.CharField(max_length=100, null=True, blank=True)
    waiver_reason = models.TextField(null=True, blank=True)
    waiver_date = models.DateTimeField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        """Enhanced save with SACCO configuration and business logic"""
        # Calculate total amount
        self.total_amount = (
            self.principal_amount + 
            self.interest_amount + 
            self.fee_amount + 
            self.penalty_amount
        )
        
        # Calculate balance
        self.balance = self.total_amount - self.paid_amount - self.waived_amount
        
        # Set financial period if not set
        if not self.financial_period:
            try:
                self.financial_period = FinancialPeriod.get_period_for_date(
                    self.due_date,
                    period_type='MONTH'
                )
            except:
                pass
        
        # Update status based on payment and SACCO rules
        self.update_status()
        
        super().save(*args, **kwargs)
    
    def update_status(self):
        """Update status based on payment and SACCO configuration"""
        try:
            sacco_config = get_sacco_config()
            grace_period_days = getattr(sacco_config, 'payment_grace_period_days', 5)
            
            # Check if fully paid or waived
            if self.balance <= 0:
                if self.is_waived or self.waived_amount > 0:
                    self.status = 'WAIVED'
                else:
                    self.status = 'PAID'
                    if not self.paid_date:
                        self.paid_date = timezone.now().date()
                return
            
            # Check if partially paid
            if self.paid_amount > 0:
                self.status = 'PARTIALLY_PAID'
            
            # Check if overdue (including grace period)
            today = timezone.now().date()
            if self.due_date < today:
                days_overdue = (today - self.due_date).days
                
                # Apply grace period before marking as overdue
                if days_overdue > grace_period_days:
                    self.status = 'OVERDUE'
                    self.days_late = days_overdue
                elif self.paid_amount == 0:
                    self.status = 'PENDING'
            else:
                self.status = 'PENDING'
                self.days_late = 0
                
        except Exception:
            # Fallback logic if SACCO config is unavailable
            if self.balance <= 0:
                self.status = 'PAID' if not self.is_waived else 'WAIVED'
            elif self.paid_amount > 0:
                self.status = 'PARTIALLY_PAID'
            elif self.due_date < timezone.now().date():
                self.status = 'OVERDUE'
                self.days_late = (timezone.now().date() - self.due_date).days
            else:
                self.status = 'PENDING'
    
    def calculate_penalty(self, as_of_date=None):
        """Calculate penalty for this installment using SACCO configuration"""
        if not as_of_date:
            as_of_date = timezone.now().date()
        
        if self.due_date >= as_of_date or self.balance <= 0:
            return Decimal('0.00')
        
        try:
            # Use loan product penalty settings
            penalty_grace_period = self.loan.loan_product.penalty_grace_period
            penalty_rate = self.loan.loan_product.penalty_rate / 100
            
            days_overdue = (as_of_date - self.due_date).days
            if days_overdue <= penalty_grace_period:
                return Decimal('0.00')
            
            effective_days = days_overdue - penalty_grace_period
            penalty_base = self.balance
            
            # Calculate penalty based on frequency
            if self.loan.loan_product.penalty_frequency == 'DAILY':
                penalty = (penalty_base * penalty_rate * effective_days) / 365
            elif self.loan.loan_product.penalty_frequency == 'WEEKLY':
                penalty = (penalty_base * penalty_rate * (effective_days / 7)) / 52
            elif self.loan.loan_product.penalty_frequency == 'MONTHLY':
                penalty = (penalty_base * penalty_rate * (effective_days / 30)) / 12
            else:  # Annual
                penalty = penalty_base * penalty_rate * (effective_days / 365)
            
            return max(penalty, Decimal('0.00'))
            
        except Exception:
            return Decimal('0.00')
    
    def apply_payment(self, payment_amount, payment_date=None, allocation_method='AUTO'):
        """Apply payment to this installment with SACCO-defined allocation logic"""
        if payment_amount <= 0:
            return False, "Payment amount must be positive"
        
        if not payment_date:
            payment_date = timezone.now().date()
        
        available_amount = payment_amount
        allocation = {
            'penalty': Decimal('0.00'),
            'fees': Decimal('0.00'),
            'interest': Decimal('0.00'),
            'principal': Decimal('0.00'),
        }
        
        try:
            sacco_config = get_sacco_config()
            
            # Get payment allocation order from SACCO configuration
            allocation_order = getattr(sacco_config, 'payment_allocation_order', 
                                     ['penalty', 'fees', 'interest', 'principal'])
            
            for component in allocation_order:
                if available_amount <= 0:
                    break
                
                if component == 'penalty':
                    outstanding = self.penalty_amount - self.paid_penalty
                elif component == 'fees':
                    outstanding = self.fee_amount - self.paid_fees
                elif component == 'interest':
                    outstanding = self.interest_amount - self.paid_interest
                elif component == 'principal':
                    outstanding = self.principal_amount - self.paid_principal
                else:
                    continue
                
                if outstanding > 0:
                    payment_to_component = min(available_amount, outstanding)
                    allocation[component] = payment_to_component
                    available_amount -= payment_to_component
            
        except Exception:
            # Fallback allocation logic
            outstanding_penalty = self.penalty_amount - self.paid_penalty
            if outstanding_penalty > 0 and available_amount > 0:
                penalty_payment = min(available_amount, outstanding_penalty)
                allocation['penalty'] = penalty_payment
                available_amount -= penalty_payment
            
            outstanding_fees = self.fee_amount - self.paid_fees
            if outstanding_fees > 0 and available_amount > 0:
                fees_payment = min(available_amount, outstanding_fees)
                allocation['fees'] = fees_payment
                available_amount -= fees_payment
            
            outstanding_interest = self.interest_amount - self.paid_interest
            if outstanding_interest > 0 and available_amount > 0:
                interest_payment = min(available_amount, outstanding_interest)
                allocation['interest'] = interest_payment
                available_amount -= interest_payment
            
            outstanding_principal = self.principal_amount - self.paid_principal
            if outstanding_principal > 0 and available_amount > 0:
                principal_payment = min(available_amount, outstanding_principal)
                allocation['principal'] = principal_payment
                available_amount -= principal_payment
        
        # Apply the allocation
        self.paid_penalty += allocation['penalty']
        self.paid_fees += allocation['fees']
        self.paid_interest += allocation['interest']
        self.paid_principal += allocation['principal']
        
        total_applied = sum(allocation.values())
        self.paid_amount += total_applied
        
        if self.paid_amount >= self.total_amount:
            self.paid_date = payment_date
        
        self.save()
        
        return True, {
            'total_applied': total_applied,
            'remaining_amount': payment_amount - total_applied,
            'allocation': allocation,
            'new_balance': self.balance
        }
    
    def get_formatted_amounts(self):
        """Get all amounts formatted using SACCO configuration"""
        return {
            'total_amount': format_money(self.total_amount),
            'principal_amount': format_money(self.principal_amount),
            'interest_amount': format_money(self.interest_amount),
            'fee_amount': format_money(self.fee_amount),
            'penalty_amount': format_money(self.penalty_amount),
            'paid_amount': format_money(self.paid_amount),
            'balance': format_money(self.balance),
            'waived_amount': format_money(self.waived_amount),
        }
    
    def __str__(self):
        return f"Installment #{self.installment_number} for {self.loan} - Due: {self.due_date}"
    
    class Meta:
        unique_together = ('loan', 'installment_number')
        ordering = ['loan', 'installment_number']
        db_table = 'loan_schedules'
        verbose_name = 'Loan Schedule'
        verbose_name_plural = 'Loan Schedules'
        indexes = [
            models.Index(fields=['due_date', 'status']),
            models.Index(fields=['status', 'days_late']),
            models.Index(fields=['financial_period']),
        ]


# =============================================================================
# LOAN PENALTY MODEL
# =============================================================================

class LoanPenalty(BaseModel):
    """Enhanced penalties with SACCO configuration integration"""
    
    PENALTY_TYPE_CHOICES = [
        ('LATE_PAYMENT', 'Late Payment'),
        ('EARLY_REPAYMENT', 'Early Repayment'),
        ('PROCESSING_DELAY', 'Processing Delay'),
        ('DOCUMENTATION', 'Documentation'),
        ('GUARANTEE_DEFAULT', 'Guarantor Default'),
        ('OTHER', 'Other'),
    ]
    
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='penalties')
    schedule = models.ForeignKey(
        LoanSchedule, 
        on_delete=models.CASCADE, 
        related_name='penalties', 
        null=True, 
        blank=True
    )
    
    penalty_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    penalty_type = models.CharField(
        max_length=20, 
        choices=PENALTY_TYPE_CHOICES,
        default='LATE_PAYMENT'
    )
    description = models.TextField(null=True, blank=True)
    
    # Payment tracking
    is_paid = models.BooleanField(default=False)
    paid_date = models.DateField(null=True, blank=True)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Waiver tracking
    is_waived = models.BooleanField(default=False)
    waived_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    waived_by_id = models.CharField(max_length=100, null=True, blank=True)
    waiver_reason = models.TextField(null=True, blank=True)
    waiver_date = models.DateTimeField(null=True, blank=True)
    
    # Auto-calculation fields
    is_system_generated = models.BooleanField(default=True)
    calculation_method = models.TextField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        """Enhanced save with SACCO business logic"""
        # Calculate balance
        self.balance = self.amount - self.paid_amount - self.waived_amount
        
        # Set paid status
        if self.balance <= 0:
            self.is_paid = True
            if not self.paid_date and self.paid_amount > 0:
                self.paid_date = timezone.now().date()
        else:
            self.is_paid = False
        
        super().save(*args, **kwargs)
    
    @classmethod
    def calculate_late_payment_penalty(cls, loan_schedule, as_of_date=None):
        """Calculate late payment penalty for a schedule using SACCO configuration"""
        if not as_of_date:
            as_of_date = timezone.now().date()
        
        # Check if penalty already exists for this date
        existing_penalty = cls.objects.filter(
            schedule=loan_schedule,
            penalty_date=as_of_date,
            penalty_type='LATE_PAYMENT'
        ).first()
        
        if existing_penalty:
            return existing_penalty
        
        penalty_amount = loan_schedule.calculate_penalty(as_of_date)
        if penalty_amount <= 0:
            return None
        
        # Create penalty record
        penalty = cls.objects.create(
            loan=loan_schedule.loan,
            schedule=loan_schedule,
            penalty_date=as_of_date,
            amount=penalty_amount,
            penalty_type='LATE_PAYMENT',
            description=f"Late payment penalty for installment #{loan_schedule.installment_number}",
            is_system_generated=True,
            calculation_method=f"Rate: {loan_schedule.loan.loan_product.penalty_rate}%, Days overdue: {loan_schedule.days_late}"
        )
        
        return penalty
    
    def waive_penalty(self, waiver_amount, reason, user=None):
        """Waive penalty (partial or full)"""
        if waiver_amount <= 0:
            return False, "Waiver amount must be positive"
        
        if waiver_amount > self.balance:
            return False, "Waiver amount cannot exceed penalty balance"
        
        self.waived_amount += waiver_amount
        self.is_waived = True
        self.waiver_reason = reason
        self.waiver_date = timezone.now()
        if user:
            self.waived_by_id = str(user.pk)
        
        self.save()
        return True, f"Penalty waived: {format_money(waiver_amount)}"
    
    def get_formatted_amounts(self):
        """Get formatted amounts"""
        return {
            'amount': format_money(self.amount),
            'paid_amount': format_money(self.paid_amount),
            'waived_amount': format_money(self.waived_amount),
            'balance': format_money(self.balance),
        }
    
    def __str__(self):
        return f"{self.get_penalty_type_display()} penalty of {format_money(self.amount)} for {self.loan}"
    
    class Meta:
        verbose_name_plural = "Loan Penalties"
        ordering = ['-penalty_date']
        db_table = 'loan_penalties'
        indexes = [
            models.Index(fields=['penalty_type', 'is_paid']),
            models.Index(fields=['penalty_date']),
            models.Index(fields=['is_system_generated']),
        ]


# =============================================================================
# LOAN DOCUMENT MODEL
# =============================================================================

class LoanDocument(BaseModel):
    """Enhanced documents with SACCO configuration integration"""
    
    DOCUMENT_TYPES = (
        ('APPLICATION_FORM', 'Application Form'),
        ('APPROVAL_LETTER', 'Approval Letter'),
        ('CONTRACT', 'Loan Contract'),
        ('GUARANTOR_FORM', 'Guarantor Form'),
        ('ID_DOCUMENT', 'Identification Document'),
        ('PASSPORT_PHOTO', 'Passport Photo'),
        ('PAYSLIP', 'Payslip'),
        ('BANK_STATEMENT', 'Bank Statement'),
        ('BUSINESS_LICENSE', 'Business License'),
        ('TAX_CERTIFICATE', 'Tax Certificate'),
        ('COLLATERAL_DOC', 'Collateral Document'),
        ('VALUATION_REPORT', 'Valuation Report'),
        ('INSURANCE_POLICY', 'Insurance Policy'),
        ('CREDIT_REPORT', 'Credit Report'),
        ('DISBURSEMENT_RECEIPT', 'Disbursement Receipt'),
        ('MEETING_MINUTES', 'Committee Meeting Minutes'),
        ('REPAYMENT_SCHEDULE', 'Repayment Schedule'),
        ('AMENDMENT_FORM', 'Loan Amendment Form'),
        ('SETTLEMENT_LETTER', 'Settlement Letter'),
        ('DEFAULT_NOTICE', 'Default Notice'),
        ('LEGAL_DOCUMENT', 'Legal Document'),
        ('OTHER', 'Other Document'),
    )
    
    DOCUMENT_STATUS = (
        ('PENDING', 'Pending Review'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired'),
        ('ARCHIVED', 'Archived'),
    )
    
    loan = models.ForeignKey(
        Loan, 
        on_delete=models.CASCADE, 
        related_name='documents', 
        null=True, 
        blank=True
    )
    application = models.ForeignKey(
        LoanApplication, 
        on_delete=models.CASCADE, 
        related_name='documents', 
        null=True, 
        blank=True
    )
    
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    document = models.FileField(upload_to='loan_documents/')
    title = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    
    # Document properties
    file_size = models.PositiveIntegerField(null=True, blank=True, help_text="File size in bytes")
    file_extension = models.CharField(max_length=10, null=True, blank=True)
    file_hash = models.CharField(max_length=64, null=True, blank=True, help_text="SHA-256 hash for integrity")
    
    # Document requirements and verification
    is_required = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=DOCUMENT_STATUS, default='PENDING')
    
    verified_by_id = models.CharField(max_length=100, null=True, blank=True)
    verification_date = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(null=True, blank=True)
    
    # Document validity
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    # Upload tracking
    uploaded_by_id = models.CharField(max_length=100, null=True, blank=True)
    upload_source = models.CharField(
        max_length=20,
        choices=[
            ('PORTAL', 'Member Portal'),
            ('ADMIN', 'Admin Interface'),
            ('MOBILE', 'Mobile App'),
            ('EMAIL', 'Email Submission'),
            ('SCAN', 'Document Scanner'),
            ('API', 'API Upload'),
        ],
        default='ADMIN'
    )
    
    # Version control
    version_number = models.PositiveIntegerField(default=1)
    replaces_document = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='replaced_by'
    )
    
    def clean(self):
        """Enhanced validation using SACCO and system configuration"""
        super().clean()
        errors = {}
        
        try:
            system_config = get_system_config()
            
            # Validate file size
            if self.document and hasattr(self.document.file, 'size'):
                max_size_bytes = system_config.get_max_file_size_bytes()
                if self.document.file.size > max_size_bytes:
                    errors['document'] = f'File size exceeds maximum allowed size of {system_config.max_file_upload_size_mb}MB'
            
            # Validate file type
            if self.document:
                filename = self.document.name
                if not system_config.is_file_type_allowed(filename):
                    allowed_types = ', '.join(system_config.get_allowed_file_extensions())
                    errors['document'] = f'File type not allowed. Allowed types: {allowed_types}'
        
        except Exception:
            pass
        
        # Validate that either loan or application is specified
        if not self.loan and not self.application:
            errors['__all__'] = 'Document must be associated with either a loan or loan application'
        
        if self.loan and self.application:
            errors['__all__'] = 'Document cannot be associated with both loan and application'
        
        # Validate expiry date
        if self.issue_date and self.expiry_date:
            if self.expiry_date <= self.issue_date:
                errors['expiry_date'] = 'Expiry date must be after issue date'
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Enhanced save with file processing and SACCO configuration"""
        if self.document:
            # Extract file information
            self.file_size = getattr(self.document.file, 'size', None)
            self.file_extension = os.path.splitext(self.document.name)[1].lower().lstrip('.')
            
            # Calculate file hash for integrity checking
            if hasattr(self.document.file, 'read'):
                import hashlib
                self.document.file.seek(0)
                file_content = self.document.file.read()
                self.file_hash = hashlib.sha256(file_content).hexdigest()
                self.document.file.seek(0)
        
        # Check for document expiry
        if self.expiry_date and self.expiry_date < timezone.now().date():
            self.status = 'EXPIRED'
        
        super().save(*args, **kwargs)
    
    def verify_document(self, user, notes=None):
        """Verify this document"""
        if self.is_verified:
            return False, "Document is already verified"
        
        if self.status == 'EXPIRED':
            return False, "Cannot verify expired document"
        
        self.is_verified = True
        self.status = 'VERIFIED'
        self.verified_by_id = str(user.pk) if user else None
        self.verification_date = timezone.now()
        if notes:
            self.verification_notes = notes
        
        self.save()
        return True, "Document verified successfully"
    
    def is_expired(self):
        """Check if document is expired"""
        if self.expiry_date:
            return self.expiry_date < timezone.now().date()
        return False
    
    def __str__(self):
        entity = self.loan or self.application
        return f"{self.get_document_type_display()} for {entity}"
    
    class Meta:
        db_table = 'loan_documents'
        verbose_name = 'Loan Document'
        verbose_name_plural = 'Loan Documents'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['document_type', 'status']),
            models.Index(fields=['is_required', 'is_verified']),
            models.Index(fields=['expiry_date']),
            models.Index(fields=['version_number']),
        ]


# =============================================================================
# LOAN WRITE-OFF MODEL
# =============================================================================

class LoanWriteOff(BaseModel):
    """Enhanced loan write-offs with SACCO configuration"""
    
    WRITE_OFF_REASONS = [
        ('DEATH', 'Borrower Death'),
        ('DISABILITY', 'Permanent Disability'),
        ('BUSINESS_CLOSURE', 'Business Closure'),
        ('UNEMPLOYMENT', 'Long-term Unemployment'),
        ('ECONOMIC_HARDSHIP', 'Economic Hardship'),
        ('LEGAL_ISSUES', 'Legal/Court Issues'),
        ('FRAUD', 'Fraud/Misrepresentation'),
        ('UNCOLLECTABLE', 'Deemed Uncollectable'),
        ('POLICY_DECISION', 'SACCO Policy Decision'),
        ('OTHER', 'Other Reason'),
    ]
    
    loan = models.OneToOneField(Loan, on_delete=models.CASCADE, related_name='write_off')
    write_off_date = models.DateField()
    
    # Write-off amounts in SACCO's base currency
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_amount = models.DecimalField(max_digits=12, decimal_places=2)
    penalties_amount = models.DecimalField(max_digits=10, decimal_places=2)
    fees_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Recovery potential
    estimated_recovery_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        help_text="Estimated amount that might still be recovered"
    )
    recovery_method = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Planned method for recovery attempts"
    )
    
    # Approval and reasoning
    write_off_reason = models.CharField(max_length=20, choices=WRITE_OFF_REASONS)
    detailed_reason = models.TextField()
    supporting_documents = models.TextField(null=True, blank=True)
    
    # Approval workflow
    recommended_by_id = models.CharField(max_length=100, null=True, blank=True)
    approved_by_id = models.CharField(max_length=100, null=True, blank=True)
    committee_approval_date = models.DateField(null=True, blank=True)
    committee_minutes_reference = models.CharField(max_length=100, null=True, blank=True)
    
    # Financial period and accounting
    financial_period = models.ForeignKey(
        FinancialPeriod,
        on_delete=models.PROTECT,
        help_text="Financial period when write-off was processed"
    )
    gl_transaction_reference = models.CharField(max_length=50, null=True, blank=True)
    
    # Tax implications
    tax_benefit_claimed = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_year = models.PositiveIntegerField(null=True, blank=True)
    
    # Recovery tracking
    total_recovered_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    last_recovery_date = models.DateField(null=True, blank=True)
    recovery_status = models.CharField(
        max_length=20,
        choices=[
            ('ACTIVE', 'Active Recovery'),
            ('SUSPENDED', 'Recovery Suspended'),
            ('CLOSED', 'Recovery Closed'),
            ('PARTIAL', 'Partial Recovery Achieved'),
        ],
        default='ACTIVE'
    )
    
    notes = models.TextField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        """Enhanced save with SACCO configuration and business logic"""
        # Calculate total amount
        self.total_amount = (
            self.principal_amount + 
            self.interest_amount + 
            self.penalties_amount + 
            self.fees_amount
        )
        
        # Set financial period if not provided
        if not self.financial_period_id:
            try:
                self.financial_period = FinancialPeriod.get_period_for_date(
                    self.write_off_date,
                    period_type='MONTH'
                )
            except:
                pass
        
        # Set tax year
        if not self.tax_year:
            self.tax_year = self.write_off_date.year
        
        super().save(*args, **kwargs)
        
        # Update loan status after write-off
        self.loan.status = 'WRITTEN_OFF'
        self.loan.save()
    
    def calculate_recovery_percentage(self):
        """Calculate percentage of write-off amount recovered"""
        if self.total_amount > 0:
            return (self.total_recovered_amount / self.total_amount) * 100
        return 0
    
    def get_net_loss(self):
        """Get net loss after recoveries"""
        return self.total_amount - self.total_recovered_amount
    
    def get_formatted_amounts(self):
        """Get formatted amounts"""
        return {
            'total_amount': format_money(self.total_amount),
            'principal_amount': format_money(self.principal_amount),
            'interest_amount': format_money(self.interest_amount),
            'penalties_amount': format_money(self.penalties_amount),
            'fees_amount': format_money(self.fees_amount),
            'total_recovered': format_money(self.total_recovered_amount),
            'net_loss': format_money(self.get_net_loss()),
            'estimated_recovery': format_money(self.estimated_recovery_amount),
        }
    
    def __str__(self):
        return f"Write-off for {self.loan} on {self.write_off_date} - {format_money(self.total_amount)}"
    
    class Meta:
        db_table = 'loan_write_offs'
        verbose_name = 'Loan Write-off'
        verbose_name_plural = 'Loan Write-offs'
        ordering = ['-write_off_date']
        indexes = [
            models.Index(fields=['write_off_date']),
            models.Index(fields=['write_off_reason']),
            models.Index(fields=['financial_period']),
            models.Index(fields=['recovery_status']),
        ]


# =============================================================================
# LOAN RECOVERY MODEL
# =============================================================================

class LoanRecovery(BaseModel):
    """Enhanced recoveries on written-off loans with SACCO integration"""
    
    RECOVERY_METHOD_CHOICES = [
        ('VOLUNTARY', 'Voluntary Payment'),
        ('SALARY_DEDUCTION', 'Salary Deduction'),
        ('ASSET_SALE', 'Asset/Collateral Sale'),
        ('GUARANTOR_PAYMENT', 'Guarantor Payment'),
        ('DEBT_COLLECTOR', 'Debt Collection Agency'),
        ('LEGAL_ACTION', 'Legal/Court Action'),
        ('SETTLEMENT', 'Negotiated Settlement'),
        ('INSURANCE_CLAIM', 'Insurance Claim'),
        ('OTHER', 'Other Method'),
    ]
    
    write_off = models.ForeignKey(LoanWriteOff, on_delete=models.CASCADE, related_name='recoveries')
    recovery_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Recovery breakdown (amounts recovered from each component)
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    interest_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    penalties_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fees_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    recovery_method = models.CharField(max_length=20, choices=RECOVERY_METHOD_CHOICES)
    recovery_agent = models.CharField(
        max_length=100, 
        null=True, 
        blank=True,
        help_text="Name of recovery agent, lawyer, or collection agency"
    )
    
    # Recovery costs and net recovery
    recovery_costs = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Costs incurred in recovery process"
    )
    net_recovery_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text="Recovery amount minus recovery costs"
    )
    
    # Payment details
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('CASH', 'Cash'),
            ('BANK_TRANSFER', 'Bank Transfer'),
            ('CHEQUE', 'Cheque'),
            ('MOBILE_MONEY', 'Mobile Money'),
            ('ASSET_PROCEEDS', 'Asset Sale Proceeds'),
            ('COURT_ORDER', 'Court-Ordered Payment'),
            ('INSURANCE', 'Insurance Payout'),
            ('OTHER', 'Other'),
        ]
    )
    
    receipt_number = models.CharField(max_length=50, null=True, blank=True)
    reference_number = models.CharField(max_length=100, null=True, blank=True)
    
    # Personnel tracking
    received_by_id = models.CharField(max_length=100, null=True, blank=True)
    processed_by_id = models.CharField(max_length=100, null=True, blank=True)
    
    # Financial period and accounting
    financial_period = models.ForeignKey(
        FinancialPeriod,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    gl_transaction_reference = models.CharField(max_length=50, null=True, blank=True)
    
    # Additional details
    notes = models.TextField(null=True, blank=True)
    recovery_agreement = models.FileField(
        upload_to='recovery_documents/', 
        null=True, 
        blank=True,
        help_text="Recovery agreement or settlement document"
    )
    
    def save(self, *args, **kwargs):
        """Enhanced save with SACCO configuration and business logic"""
        # Calculate net recovery amount
        self.net_recovery_amount = self.amount - self.recovery_costs
        
        # Set financial period if not provided
        if not self.financial_period_id:
            try:
                self.financial_period = FinancialPeriod.get_period_for_date(
                    self.recovery_date,
                    period_type='MONTH'
                )
            except:
                pass
        
        super().save(*args, **kwargs)
        
        # Update write-off recovery totals
        self.update_writeoff_recovery_totals()
    
    def update_writeoff_recovery_totals(self):
        """Update total recovered amount in the related write-off"""
        from django.db.models import Sum
        
        total_recovered = self.write_off.recoveries.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        self.write_off.total_recovered_amount = total_recovered
        self.write_off.last_recovery_date = self.recovery_date
        
        # Update recovery status
        recovery_percentage = self.write_off.calculate_recovery_percentage()
        if recovery_percentage >= 100:
            self.write_off.recovery_status = 'CLOSED'
        elif recovery_percentage > 0:
            self.write_off.recovery_status = 'PARTIAL'
        
        self.write_off.save()
    
    def get_formatted_amounts(self):
        """Get formatted amounts"""
        return {
            'amount': format_money(self.amount),
            'principal_amount': format_money(self.principal_amount),
            'interest_amount': format_money(self.interest_amount),
            'penalties_amount': format_money(self.penalties_amount),
            'fees_amount': format_money(self.fees_amount),
            'recovery_costs': format_money(self.recovery_costs),
            'net_recovery_amount': format_money(self.net_recovery_amount),
        }
    
    def __str__(self):
        return f"Recovery of {format_money(self.amount)} for {self.write_off.loan} on {self.recovery_date}"
    
    class Meta:
        verbose_name_plural = "Loan Recoveries"
        db_table = 'loan_recoveries'
        ordering = ['-recovery_date']
        indexes = [
            models.Index(fields=['recovery_date']),
            models.Index(fields=['recovery_method']),
            models.Index(fields=['financial_period']),
        ]


# =============================================================================
# LOAN DEFAULTER MODEL
# =============================================================================

class LoanDefaulter(BaseModel):
    """Enhanced tracking of loan defaulters with SACCO integration"""
    
    ACTION_TYPE_CHOICES = [
        ('NONE', 'No Action Taken'),
        ('PHONE_CALL', 'Phone Call'),
        ('SMS_REMINDER', 'SMS Reminder'),
        ('EMAIL_NOTICE', 'Email Notice'),
        ('WRITTEN_NOTICE', 'Written Notice'),
        ('HOME_VISIT', 'Home/Business Visit'),
        ('GUARANTOR_CONTACT', 'Guarantor Contact'),
        ('COMMITTEE_REVIEW', 'Committee Review'),
        ('LEGAL_NOTICE', 'Legal Notice'),
        ('COURT_ACTION', 'Court Action'),
        ('DEBT_COLLECTOR', 'Debt Collection Agency'),
        ('ASSET_ATTACHMENT', 'Asset Attachment'),
        ('SALARY_ATTACHMENT', 'Salary Attachment'),
        ('CRB_LISTING', 'Credit Bureau Listing'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE_DEFAULT', 'Active Default'),
        ('IN_COLLECTION', 'In Collection'),
        ('LEGAL_PROCEEDINGS', 'Legal Proceedings'),
        ('PAYMENT_PLAN', 'On Payment Plan'),
        ('RESTRUCTURED', 'Loan Restructured'),
        ('PARTIALLY_RECOVERED', 'Partially Recovered'),
        ('WRITTEN_OFF', 'Written Off'),
        ('FULLY_RECOVERED', 'Fully Recovered'),
        ('DECEASED', 'Borrower Deceased'),
        ('CLOSED', 'Case Closed'),
    ]
    
    loan = models.OneToOneField(Loan, on_delete=models.CASCADE, related_name='defaulter_record')
    default_date = models.DateField()
    days_in_arrears = models.PositiveIntegerField()
    amount_in_arrears = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Collection activities
    collection_action = models.CharField(max_length=20, choices=ACTION_TYPE_CHOICES, default='NONE')
    last_action_date = models.DateField(null=True, blank=True)
    action_by_id = models.CharField(max_length=100, null=True, blank=True)
    next_action_date = models.DateField(null=True, blank=True)
    
    # Credit bureau reporting
    is_reported_to_crb = models.BooleanField(default=False)
    crb_report_date = models.DateField(null=True, blank=True)
    crb_reference = models.CharField(max_length=100, null=True, blank=True)
    
    # Status and progress
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='ACTIVE_DEFAULT')
    collection_priority = models.CharField(
        max_length=10,
        choices=[
            ('LOW', 'Low Priority'),
            ('MEDIUM', 'Medium Priority'),
            ('HIGH', 'High Priority'),
            ('URGENT', 'Urgent'),
        ],
        default='MEDIUM'
    )
    
    # Recovery tracking
    total_recovered_since_default = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    last_payment_date = models.DateField(null=True, blank=True)
    
    # Collection costs
    collection_costs_incurred = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    legal_costs_incurred = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Resolution
    resolution_date = models.DateField(null=True, blank=True)
    resolution_method = models.CharField(max_length=100, null=True, blank=True)
    
    notes = models.TextField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        """Enhanced save with SACCO configuration and business logic"""
        # Update collection priority based on amount and days in arrears
        try:
            sacco_config = get_sacco_config()
            
            # Priority thresholds from SACCO configuration
            high_priority_days = getattr(sacco_config, 'high_priority_arrears_days', 120)
            urgent_priority_days = getattr(sacco_config, 'urgent_priority_arrears_days', 180)
            high_priority_amount = getattr(sacco_config, 'high_priority_arrears_amount', Decimal('500000'))
            
            if self.days_in_arrears >= urgent_priority_days or self.amount_in_arrears >= high_priority_amount * 2:
                self.collection_priority = 'URGENT'
            elif self.days_in_arrears >= high_priority_days or self.amount_in_arrears >= high_priority_amount:
                self.collection_priority = 'HIGH'
            elif self.days_in_arrears >= 60:
                self.collection_priority = 'MEDIUM'
            else:
                self.collection_priority = 'LOW'
                
        except Exception:
            pass
        
        super().save(*args, **kwargs)
    
    def update_collection_status(self, new_action, user=None, notes=None):
        """Update collection action and status"""
        self.collection_action = new_action
        self.last_action_date = timezone.now().date()
        if user:
            self.action_by_id = str(user.pk)
        
        if notes:
            if self.notes:
                self.notes += f"\n\n{timezone.now().date()}: {notes}"
            else:
                self.notes = f"{timezone.now().date()}: {notes}"
        
        # Auto-set next action date based on current action
        action_intervals = {
            'PHONE_CALL': 3,
            'SMS_REMINDER': 7,
            'EMAIL_NOTICE': 7,
            'WRITTEN_NOTICE': 14,
            'HOME_VISIT': 14,
            'GUARANTOR_CONTACT': 14,
            'LEGAL_NOTICE': 30,
            'COURT_ACTION': 60,
        }
        
        interval_days = action_intervals.get(new_action, 7)
        self.next_action_date = timezone.now().date() + timezone.timedelta(days=interval_days)
        
        self.save()
        return True, f"Collection status updated to {self.get_collection_action_display()}"
    
    def get_formatted_amounts(self):
        """Get formatted amounts"""
        return {
            'amount_in_arrears': format_money(self.amount_in_arrears),
            'total_recovered': format_money(self.total_recovered_since_default),
            'collection_costs': format_money(self.collection_costs_incurred),
            'legal_costs': format_money(self.legal_costs_incurred),
            'net_recovery': format_money(self.total_recovered_since_default - self.collection_costs_incurred - self.legal_costs_incurred),
        }
    
    def __str__(self):
        return f"Default on {self.loan} - {self.days_in_arrears} days in arrears ({format_money(self.amount_in_arrears)})"
    
    class Meta:
        db_table = 'loan_defaulters'
        verbose_name = 'Loan Defaulter'
        verbose_name_plural = 'Loan Defaulters'
        ordering = ['-default_date']
        indexes = [
            models.Index(fields=['status', 'collection_priority']),
            models.Index(fields=['days_in_arrears']),
            models.Index(fields=['next_action_date']),
            models.Index(fields=['is_reported_to_crb']),
        ]


# =============================================================================
# LOAN REMINDER MODEL
# =============================================================================

class LoanReminder(BaseModel):
    """Enhanced payment reminders with SACCO communication integration"""
    
    REMINDER_TYPES = (
        ('UPCOMING', 'Upcoming Payment'),
        ('DUE_TODAY', 'Payment Due Today'),
        ('OVERDUE', 'Overdue Payment'),
        ('PARTIAL', 'Partial Payment'),
        ('GUARANTEE_REQUEST', 'Guarantee Request'),
        ('GUARANTEE_REMINDER', 'Guarantee Reminder'),
        ('DOCUMENT_REQUEST', 'Document Request'),
        ('MEETING_NOTICE', 'Meeting Notice'),
        ('OTHER', 'Other'),
    )
    
    REMINDER_STATUS = (
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
        ('ACKNOWLEDGED', 'Acknowledged'),
    )
    
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='reminders')
    schedule = models.ForeignKey(
        LoanSchedule, 
        on_delete=models.CASCADE, 
        related_name='reminders', 
        null=True, 
        blank=True
    )
    
    reminder_type = models.CharField(max_length=20, choices=REMINDER_TYPES)
    reminder_date = models.DateField()
    send_date = models.DateTimeField()
    status = models.CharField(max_length=15, choices=REMINDER_STATUS, default='PENDING')
    
    # Reminder content
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField()
    days_to_due = models.IntegerField()
    message = models.TextField()
    custom_message = models.TextField(null=True, blank=True)
    
    # Communication channels using SACCO settings
    channel = models.CharField(
        max_length=20, 
        choices=[
            ('SMS', 'SMS'), 
            ('EMAIL', 'Email'), 
            ('WHATSAPP', 'WhatsApp'),
            ('CALL', 'Phone Call'),
            ('LETTER', 'Physical Letter'),
            ('PORTAL', 'Member Portal'),
            ('MULTIPLE', 'Multiple Channels')
        ],
        default='SMS'
    )
    
    # Delivery tracking
    sms_sent = models.BooleanField(default=False)
    email_sent = models.BooleanField(default=False)
    whatsapp_sent = models.BooleanField(default=False)
    portal_notification_sent = models.BooleanField(default=False)
    
    sent_date = models.DateTimeField(null=True, blank=True)
    acknowledged_date = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    
    # Template and personalization
    template_used = models.CharField(max_length=100, null=True, blank=True)
    personalization_data = models.JSONField(default=dict, blank=True)
    
    # Follow-up settings
    requires_follow_up = models.BooleanField(default=False)
    follow_up_date = models.DateTimeField(null=True, blank=True)
    follow_up_completed = models.BooleanField(default=False)
    
    def save(self, *args, **kwargs):
        """Enhanced save with SACCO-based message generation"""
        if not self.message and not self.custom_message:
            self.generate_message()
        
        super().save(*args, **kwargs)
    
    def generate_message(self):
        """Generate reminder message using SACCO configuration and templates"""
        try:
            sacco_config = get_sacco_config()
            member_name = self.loan.member.get_full_name()
            loan_number = self.loan.loan_number
            formatted_amount = format_money(self.amount_due)
            
            # Get SACCO name for personalization
            sacco_name = getattr(sacco_config, 'organization_name', 'Your SACCO')
            
            # Template messages based on reminder type
            templates = {
                'UPCOMING': f"Dear {member_name}, your loan payment of {formatted_amount} for loan #{loan_number} is due on {self.due_date.strftime('%d/%m/%Y')}. Please ensure timely payment. - {sacco_name}",
                
                'DUE_TODAY': f"Dear {member_name}, your loan payment of {formatted_amount} for loan #{loan_number} is due TODAY. Please make payment to avoid penalties. - {sacco_name}",
                
                'OVERDUE': f"Dear {member_name}, your loan payment of {formatted_amount} for loan #{loan_number} was due on {self.due_date.strftime('%d/%m/%Y')} and is now {abs(self.days_to_due)} days overdue. Please settle immediately to avoid further penalties. - {sacco_name}",
                
                'PARTIAL': f"Dear {member_name}, we received partial payment for loan #{loan_number}. Outstanding balance: {formatted_amount}. Please complete payment by {self.due_date.strftime('%d/%m/%Y')}. - {sacco_name}",
            }
            
            # Use custom template if available, otherwise use default
            self.message = templates.get(self.reminder_type, 
                f"Dear {member_name}, this is a reminder regarding your loan #{loan_number}. Please contact {sacco_name} for details.")
            
            # Store template reference
            self.template_used = f"default_{self.reminder_type.lower()}"
            
            # Store personalization data for future reference
            self.personalization_data = {
                'member_name': member_name,
                'loan_number': loan_number,
                'amount_due': str(self.amount_due),
                'due_date': self.due_date.isoformat(),
                'days_to_due': self.days_to_due,
                'sacco_name': sacco_name,
            }
            
        except Exception as e:
            # Fallback message if template generation fails
            self.message = f"Reminder for loan #{self.loan.loan_number}. Amount: {format_money(self.amount_due)}. Due: {self.due_date}"
            self.error_message = f"Template generation error: {str(e)}"
    
    def send_reminder(self):
        """Send reminder using SACCO communication settings"""
        try:
            sacco_config = get_sacco_config()
            member = self.loan.member
            
            success_channels = []
            failed_channels = []
            
            # Determine which channels to use
            channels_to_use = []
            if self.channel == 'MULTIPLE':
                if sacco_config.enable_sms_notifications:
                    channels_to_use.append('SMS')
                if sacco_config.enable_email_notifications:
                    channels_to_use.append('EMAIL')
            else:
                channels_to_use = [self.channel]
            
            # Send via configured channels
            if 'SMS' in channels_to_use and sacco_config.enable_sms_notifications:
                self.sms_sent = True
                success_channels.append('SMS')
            
            if 'EMAIL' in channels_to_use and sacco_config.enable_email_notifications:
                self.email_sent = True
                success_channels.append('EMAIL')
            
            # Send portal notification
            self.portal_notification_sent = True
            success_channels.append('PORTAL')
            
            # Update status based on results
            if success_channels:
                self.status = 'SENT'
                self.sent_date = timezone.now()
                
                # Set follow-up if required for overdue reminders
                if self.reminder_type in ['OVERDUE', 'PARTIAL'] and not self.follow_up_completed:
                    self.requires_follow_up = True
                    follow_up_days = getattr(sacco_config, 'reminder_follow_up_days', 7)
                    self.follow_up_date = timezone.now() + timezone.timedelta(days=follow_up_days)
            
            self.save()
            
            return True, {
                'success_channels': success_channels,
                'failed_channels': failed_channels,
                'status': self.status
            }
            
        except Exception as e:
            self.status = 'FAILED'
            self.error_message = str(e)
            self.save()
            return False, str(e)
    
    def get_formatted_amount_due(self):
        """Get formatted amount due"""
        return format_money(self.amount_due)
    
    def __str__(self):
        return f"{self.get_reminder_type_display()} reminder for {self.loan}"
    
    class Meta:
        db_table = 'loan_reminders'
        verbose_name = 'Loan Reminder'
        verbose_name_plural = 'Loan Reminders'
        ordering = ['-reminder_date']
        indexes = [
            models.Index(fields=['reminder_type', 'status']),
            models.Index(fields=['send_date', 'status']),
            models.Index(fields=['requires_follow_up', 'follow_up_date']),
        ]


# =============================================================================
# SUPPORTING MODELS (Previously referenced in utils but defined here)
# =============================================================================

class LoanRestructure(BaseModel):
    """Loan restructuring records"""
    
    STATUS_CHOICES = [
        ('INITIATED', 'Initiated'),
        ('APPROVED', 'Approved'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    original_loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='restructures')
    new_loan = models.OneToOneField(Loan, on_delete=models.SET_NULL, null=True, blank=True, related_name='restructured_from')
    
    restructure_date = models.DateField()
    restructure_reason = models.TextField()
    
    # Original loan details
    original_term = models.PositiveIntegerField()
    original_rate = models.DecimalField(max_digits=5, decimal_places=2)
    original_balance = models.DecimalField(max_digits=12, decimal_places=2)
    
    # New loan details
    new_term = models.PositiveIntegerField()

    new_rate = models.DecimalField(max_digits=5, decimal_places=2)
    additional_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='INITIATED')
    
    # Approval tracking
    requested_by_id = models.CharField(max_length=100, null=True, blank=True)
    approved_by_id = models.CharField(max_length=100, null=True, blank=True)
    
    def __str__(self):
        return f"Restructure: {self.original_loan} → {self.new_loan}"
    
    class Meta:
        db_table = 'loan_restructures'
        verbose_name = 'Loan Restructure'
        verbose_name_plural = 'Loan Restructures'
        ordering = ['-restructure_date']
        indexes = [
            models.Index(fields=['status', 'restructure_date']),
            models.Index(fields=['original_loan']),
        ]


class LoanTopUp(BaseModel):
    """Loan top-up records"""
    
    STATUS_CHOICES = [
        ('REQUESTED', 'Requested'),
        ('APPROVED', 'Approved'),
        ('DISBURSED', 'Disbursed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    original_loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='topups')
    new_loan = models.OneToOneField(Loan, on_delete=models.SET_NULL, null=True, blank=True, related_name='topup_from')
    
    top_up_date = models.DateField()
    original_balance = models.DecimalField(max_digits=12, decimal_places=2)
    top_up_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='REQUESTED')
    
    # Processing tracking
    requested_by_id = models.CharField(max_length=100, null=True, blank=True)
    processed_by_id = models.CharField(max_length=100, null=True, blank=True)
    
    def get_total_new_amount(self):
        """Get total amount of new loan"""
        return self.original_balance + self.top_up_amount
    
    def get_formatted_amounts(self):
        """Get formatted amounts"""
        return {
            'original_balance': format_money(self.original_balance),
            'top_up_amount': format_money(self.top_up_amount),
            'total_new_amount': format_money(self.get_total_new_amount()),
        }
    
    def __str__(self):
        return f"Top-up: {self.original_loan} + {format_money(self.top_up_amount)}"
    
    class Meta:
        db_table = 'loan_topups'
        verbose_name = 'Loan Top-up'
        verbose_name_plural = 'Loan Top-ups'
        ordering = ['-top_up_date']
        indexes = [
            models.Index(fields=['status', 'top_up_date']),
            models.Index(fields=['original_loan']),
        ]


class LoanIncentive(BaseModel):
    """Loan incentives and rewards"""
    
    INCENTIVE_TYPES = [
        ('EARLY_PAYMENT', 'Early Payment Incentive'),
        ('COMPLETION_REWARD', 'Loan Completion Reward'),
        ('LOYALTY_BONUS', 'Loyalty Bonus'),
        ('REFERRAL_REWARD', 'Referral Reward'),
        ('OTHER', 'Other Incentive'),
    ]
    
    APPLICATION_METHODS = [
        ('INTEREST_REDUCTION', 'Interest Reduction'),
        ('ACCOUNT_CREDIT', 'Account Credit'),
        ('PAYMENT_REDUCTION', 'Payment Reduction'),
        ('CASH_REWARD', 'Cash Reward'),
    ]
    
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='incentives')
    incentive_type = models.CharField(max_length=20, choices=INCENTIVE_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    
    applied_date = models.DateField()
    applied_by_id = models.CharField(max_length=100, null=True, blank=True)
    is_system_generated = models.BooleanField(default=False)
    
    # Application method
    application_method = models.CharField(
        max_length=20,
        choices=APPLICATION_METHODS,
        default='INTEREST_REDUCTION'
    )
    
    def get_formatted_amount(self):
        """Get formatted incentive amount"""
        return format_money(self.amount)
    
    def __str__(self):
        return f"{self.get_incentive_type_display()} - {format_money(self.amount)} for {self.loan}"
    
    class Meta:
        db_table = 'loan_incentives'
        verbose_name = 'Loan Incentive'
        verbose_name_plural = 'Loan Incentives'
        ordering = ['-applied_date']
        indexes = [
            models.Index(fields=['incentive_type', 'applied_date']),
            models.Index(fields=['is_system_generated']),
        ]


class MemberLoanDiscount(BaseModel):
    """Member loan discounts for future applications"""
    
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='loan_discounts')
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2)
    reason = models.TextField()
    
    valid_from = models.DateField()
    valid_until = models.DateField()
    
    is_used = models.BooleanField(default=False)
    used_date = models.DateField(null=True, blank=True)
    used_for_application = models.ForeignKey(
        LoanApplication, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='discount_used'
    )
    
    created_from_loan = models.ForeignKey(
        Loan, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='discounts_generated'
    )
    
    def is_valid(self):
        """Check if discount is still valid"""
        today = timezone.now().date()
        return (not self.is_used and 
                self.valid_from <= today <= self.valid_until)
    
    def days_until_expiry(self):
        """Get days until discount expires"""
        today = timezone.now().date()
        if self.valid_until > today:
            return (self.valid_until - today).days
        return 0
    
    def use_discount(self, application):
        """Mark discount as used"""
        if not self.is_valid():
            return False, "Discount is not valid or already used"
        
        self.is_used = True
        self.used_date = timezone.now().date()
        self.used_for_application = application
        self.save()
        
        return True, "Discount applied successfully"
    
    def __str__(self):
        return f"{self.discount_rate}% discount for {self.member} (Valid until {self.valid_until})"
    
    class Meta:
        db_table = 'member_loan_discounts'
        verbose_name = 'Member Loan Discount'
        verbose_name_plural = 'Member Loan Discounts'
        ordering = ['-valid_until']
        indexes = [
            models.Index(fields=['member', 'is_used']),
            models.Index(fields=['valid_from', 'valid_until']),
        ]


class MemberLoanLimitHistory(BaseModel):
    """History of member loan limit changes"""
    
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='loan_limit_history')
    old_limit = models.DecimalField(max_digits=12, decimal_places=2)
    new_limit = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField()
    
    changed_date = models.DateField()
    changed_by_id = models.CharField(max_length=100, null=True, blank=True)
    
    def get_change_amount(self):
        """Get the change amount (positive for increase, negative for decrease)"""
        return self.new_limit - self.old_limit
    
    def get_change_percentage(self):
        """Get the percentage change"""
        if self.old_limit > 0:
            return ((self.new_limit - self.old_limit) / self.old_limit) * 100
        return 0
    
    def get_formatted_amounts(self):
        """Get formatted amounts"""
        return {
            'old_limit': format_money(self.old_limit),
            'new_limit': format_money(self.new_limit),
            'change_amount': format_money(abs(self.get_change_amount())),
            'change_type': 'Increase' if self.get_change_amount() >= 0 else 'Decrease'
        }
    
    def __str__(self):
        change = self.get_change_amount()
        direction = "increased" if change >= 0 else "decreased"
        return f"Limit {direction} for {self.member}: {format_money(self.old_limit)} → {format_money(self.new_limit)}"
    
    class Meta:
        db_table = 'member_loan_limit_history'
        verbose_name = 'Member Loan Limit History'
        verbose_name_plural = 'Member Loan Limit History'
        ordering = ['-changed_date']
        indexes = [
            models.Index(fields=['member', 'changed_date']),
            models.Index(fields=['changed_date']),
        ]