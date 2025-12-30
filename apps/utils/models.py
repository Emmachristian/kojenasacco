# utils/models.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from kojenasacco.managers import get_current_db, SaccoManager, DefaultDatabaseManager
from datetime import date
import uuid
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import logging
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

# =============================================================================
# BASE MODEL - SACCO-SPECIFIC DATA
# =============================================================================

class BaseModel(models.Model):
    """
    Enhanced base model with comprehensive audit trail capabilities
    and automatic multi-database routing for SACCO data.
    
    Features:
    - Automatic user tracking (who created/updated)
    - Real IP address tracking (where operations came from)
    - Change reason tracking (why changes were made)
    - Automatic database routing for multi-tenant SACCO setup
    - Comprehensive audit trail methods
    - Thread-local context integration
    - SACCO timezone support for timestamps
    """
    
    # Core identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Timestamp fields
    created_at = models.DateTimeField("Created At", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("Updated At", auto_now=True, db_index=True)
    
    # User tracking - CharField to avoid cross-database FK constraints
    created_by_id = models.CharField(
        "Created By ID", 
        max_length=50, 
        null=True, 
        blank=True, 
        db_index=True,
        help_text="ID of user who created this record"
    )
    updated_by_id = models.CharField(
        "Updated By ID", 
        max_length=50, 
        null=True, 
        blank=True, 
        db_index=True,
        help_text="ID of user who last updated this record"
    )
    
    # Enhanced IP tracking - captures real member IP
    created_from_ip = models.GenericIPAddressField("Created From IP", null=True, blank=True)
    updated_from_ip = models.GenericIPAddressField("Updated From IP", null=True, blank=True)
    
    # Change reason tracking
    change_reason = models.CharField("Change Reason", max_length=255, blank=True, null=True)
    
    # Use SaccoManager for automatic database routing
    objects = SaccoManager()
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
            models.Index(fields=['created_by_id']),
            models.Index(fields=['updated_by_id']),
        ]

    def save(self, *args, **kwargs):
        """
        Override save to:
        1. Populate audit trail fields (created_by, updated_by, IPs)
        2. Automatically route to correct database
        3. Track field changes
        4. Create audit log entry
        """
        from utils.context import get_request_context
        
        # Determine if this is a new object
        is_new = self._state.adding
        
        # =========================================================================
        # STEP 1: POPULATE AUDIT FIELDS FROM REQUEST CONTEXT
        # =========================================================================
        context = get_request_context()
        
        if context:
            user = context.get('user')
            ip_address = context.get('ip_address')
            
            # Set created_by and created_from_ip for new objects
            if is_new:
                if user and not self.created_by_id:
                    self.created_by_id = str(user.id)
                if ip_address and not self.created_from_ip:
                    self.created_from_ip = ip_address
            
            # Always update updated_by and updated_from_ip
            if user:
                self.updated_by_id = str(user.id)
            if ip_address:
                self.updated_from_ip = ip_address
        else:
            # Log when no context is available (e.g., management commands, shell)
            if is_new:
                logger.debug(
                    f"No request context available when creating {self.__class__.__name__}. "
                    f"Audit fields will not be populated."
                )
        
        # =========================================================================
        # STEP 2: TRACK CHANGES FOR EXISTING OBJECTS
        # =========================================================================
        changes = {}
        if not is_new and self.pk:
            try:
                # Get old instance from database
                current_db = get_current_db()
                if current_db:
                    old_instance = self.__class__.objects.using(current_db).get(pk=self.pk)
                else:
                    old_instance = self.__class__.objects.get(pk=self.pk)
                
                # Compare fields to detect changes
                for field in self._meta.fields:
                    field_name = field.name
                    
                    # Skip auto-generated fields and audit fields
                    if field_name in ['id', 'created_at', 'updated_at', 'created_by_id', 
                                     'updated_by_id', 'created_from_ip', 'updated_from_ip']:
                        continue
                    
                    old_value = getattr(old_instance, field_name)
                    new_value = getattr(self, field_name)
                    
                    # Record change if values differ
                    if old_value != new_value:
                        changes[field_name] = {
                            'old': str(old_value) if old_value is not None else None,
                            'new': str(new_value) if new_value is not None else None
                        }
            except self.__class__.DoesNotExist:
                logger.debug(f"Old instance not found for {self.__class__.__name__} {self.pk}")
                pass  # Object doesn't exist yet, treat as new
            except Exception as e:
                logger.error(f"Error tracking changes for {self.__class__.__name__}: {e}")
        
        # =========================================================================
        # STEP 3: AUTOMATIC DATABASE ROUTING
        # =========================================================================
        current_db = get_current_db()
        
        # Only set 'using' if not already specified and we have a database context
        if current_db and 'using' not in kwargs:
            kwargs['using'] = current_db
            logger.debug(f"Saving {self.__class__.__name__} to {current_db}")
        
        # =========================================================================
        # STEP 4: SAVE THE OBJECT
        # =========================================================================
        result = super().save(*args, **kwargs)
        
        # =========================================================================
        # STEP 5: CREATE AUDIT LOG ENTRY
        # =========================================================================
        # Only create audit log for SACCO databases (not default)
        # ALSO skip if this IS an AuditLog to prevent infinite recursion
        if current_db and current_db != 'default' and self.__class__.__name__ != 'AuditLog':
            self._create_audit_log(
                action='CREATE' if is_new else 'UPDATE',
                changes=changes if not is_new else {}
            )
        
        return result
    
    def delete(self, *args, **kwargs):
        """Override delete to automatically route to correct database and log deletion"""
        current_db = get_current_db()
        
        if current_db and 'using' not in kwargs:
            kwargs['using'] = current_db
            logger.debug(f"Deleting {self.__class__.__name__} from {current_db}")
        
        # Create audit log before deletion (only for SACCO databases)
        # ALSO skip if this IS an AuditLog to prevent infinite recursion
        if current_db and current_db != 'default' and self.__class__.__name__ != 'AuditLog':
            self._create_audit_log(action='DELETE', changes={})
        
        return super().delete(*args, **kwargs)
    
    def refresh_from_db(self, *args, **kwargs):
        """Override refresh to automatically route to correct database"""
        current_db = get_current_db()
        
        if current_db and 'using' not in kwargs:
            kwargs['using'] = current_db
        
        return super().refresh_from_db(*args, **kwargs)
    
    # -------------------------------------------------------------------------
    # AUDIT TRAIL HELPER METHODS
    # -------------------------------------------------------------------------
    
    def get_created_by(self):
        """Get the user who created this record"""
        if not self.created_by_id:
            return None
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            return User.objects.using('default').get(id=self.created_by_id)
        except Exception as e:
            logger.error(f"Error fetching created_by user: {e}")
            return None
    
    def get_updated_by(self):
        """Get the user who last updated this record"""
        if not self.updated_by_id:
            return None
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            return User.objects.using('default').get(id=self.updated_by_id)
        except Exception as e:
            logger.error(f"Error fetching updated_by user: {e}")
            return None
    
    def get_audit_trail(self):
        """Get comprehensive audit information for this record"""
        return {
            'id': str(self.id),
            'created_at': self.created_at,
            'created_by_id': self.created_by_id,
            'created_from_ip': self.created_from_ip,
            'updated_at': self.updated_at,
            'updated_by_id': self.updated_by_id,
            'updated_from_ip': self.updated_from_ip,
            'last_change_reason': self.change_reason,
        }
    
    @property
    def created_by_name(self):
        """Get the name of the user who created this record"""
        user = self.get_created_by()
        if user:
            return user.get_full_name() or user.username
        return "System"
    
    @property
    def updated_by_name(self):
        """Get the name of the user who last updated this record"""
        user = self.get_updated_by()
        if user:
            return user.get_full_name() or user.username
        return "System"
    
    def _create_audit_log(self, action, changes):
        """Create an audit log entry for this change"""
        try:
            from utils.context import get_request_context
            
            # Get request context (user, IP, etc.)
            context = get_request_context()
            
            # Get current database to ensure audit log goes to same DB
            current_db = get_current_db()
            
            # Prepare user information
            user_id = None
            user_email = ""
            user_name = ""
            
            if context and context.get('user'):
                user = context['user']
                user_id = str(user.id) if hasattr(user, 'id') else str(user.pk)
                user_email = getattr(user, 'email', '')
                user_name = getattr(user, 'get_full_name', lambda: str(user))()
            
            # Create audit log entry
            audit_log = AuditLog(
                content_type=f"{self._meta.app_label}.{self._meta.model_name}",
                object_id=str(self.pk),
                object_repr=str(self)[:200],
                action=action,
                changes=changes,
                user_id=user_id,
                user_email=user_email,
                user_name=user_name,
                ip_address=context.get('ip_address') if context else None,
                user_agent=context.get('user_agent', '')[:255] if context else '',
                change_reason=self.change_reason or '',
                session_key=context.get('session_key', '') if context else '',
                request_path=context.get('request_path', '') if context else '',
            )
            
            # Save to the same database as the model
            if current_db:
                audit_log.save(using=current_db)
            else:
                audit_log.save()
            
            logger.debug(f"Created audit log for {action} on {self._meta.label} {self.pk}")
            
        except Exception as e:
            # Don't fail the save/delete if audit logging fails
            logger.error(f"Failed to create audit log: {e}", exc_info=True)
    
    def get_history(self, limit=10):
        """
        Get audit history for this object.
        
        Args:
            limit: Maximum number of history entries to return
            
        Returns:
            QuerySet of AuditLog entries
        """
        try:
            current_db = get_current_db()
            
            queryset = AuditLog.objects.filter(
                content_type=f"{self._meta.app_label}.{self._meta.model_name}",
                object_id=str(self.pk)
            )
            
            # Use correct database if available
            if current_db:
                queryset = queryset.using(current_db)
            
            return queryset.order_by('-timestamp')[:limit]
        except Exception as e:
            logger.error(f"Error fetching history: {e}")
            return []
    
    def set_change_reason(self, reason):
        """
        Set the reason for the next change to this object.
        
        Usage:
            member = Member.objects.get(id=some_id)
            member.name = "New Name"
            member.set_change_reason("Updated name per member request")
            member.save()
        
        Args:
            reason: String explaining why the change was made
        """
        self.change_reason = reason


# =============================================================================
# DEFAULT DATABASE MODEL - SYSTEM-WIDE DATA
# =============================================================================

class DefaultDatabaseModel(models.Model):
    """
    Base model for entities that ALWAYS use the default database.
    
    Use this for:
    - User accounts
    - SACCO registry
    - System-wide configuration
    - Any cross-tenant data
    
    This model includes basic audit fields but forces all operations
    to the default database regardless of thread-local context.
    """
    
    # Core identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Timestamp fields
    created_at = models.DateTimeField("Created At", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("Updated At", auto_now=True, db_index=True)
    
    # Use DefaultDatabaseManager for automatic database routing
    objects = DefaultDatabaseManager()
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]
    
    def save(self, *args, **kwargs):
        """Force save to default database"""
        kwargs['using'] = 'default'
        return super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Force delete from default database"""
        kwargs['using'] = 'default'
        return super().delete(*args, **kwargs)
    
    def refresh_from_db(self, *args, **kwargs):
        """Force refresh from default database"""
        kwargs['using'] = 'default'
        return super().refresh_from_db(*args, **kwargs)


# =============================================================================
# AUDIT LOG MODELS
# =============================================================================

class AuditLog(models.Model):
    """
    Comprehensive audit trail for all model changes.
    
    Tracks:
    - What changed (model, object_id, field changes)
    - Who made the change (user)
    - When it happened (timestamp in SACCO timezone)
    - Where it came from (IP address)
    - Why it was changed (reason)
    
    This model is stored in the SAME database as the model being tracked,
    so each SACCO database has its own audit trail.
    """
    
    ACTION_CHOICES = (
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'),
        ('DELETE', 'Deleted'),
    )
    
    # What was changed
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_type = models.CharField("Model Type", max_length=100, db_index=True)
    object_id = models.CharField("Object ID", max_length=100, db_index=True)
    object_repr = models.CharField("Object Representation", max_length=200)
    action = models.CharField("Action", max_length=10, choices=ACTION_CHOICES, db_index=True)
    
    # Field-level changes (JSON format)
    changes = models.JSONField(
        "Changes",
        help_text="Dictionary of field changes: {'field_name': {'old': 'value', 'new': 'value'}}",
        default=dict,
        blank=True
    )
    
    # Who made the change - CharField to avoid cross-database FK
    user_id = models.CharField(
        "User ID", 
        max_length=50, 
        db_index=True, 
        null=True, 
        blank=True,
        help_text="ID of user who performed this action"
    )
    user_email = models.EmailField("User Email", max_length=255, blank=True)
    user_name = models.CharField("User Name", max_length=255, blank=True)
    
    # When it happened - Uses SACCO timezone via auto_now_add
    timestamp = models.DateTimeField("Timestamp", auto_now_add=True, db_index=True)
    
    # Where it came from
    ip_address = models.GenericIPAddressField("IP Address", null=True, blank=True)
    user_agent = models.TextField("User Agent", blank=True)
    
    # Why it changed
    change_reason = models.CharField("Change Reason", max_length=255, blank=True)
    
    # Additional context
    session_key = models.CharField("Session Key", max_length=100, blank=True)
    request_path = models.CharField("Request Path", max_length=255, blank=True)
    
    # Use SaccoManager for automatic database routing
    objects = SaccoManager()
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['user_id', 'timestamp']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['action']),
        ]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
    
    def __str__(self):
        return f"{self.action} {self.content_type} {self.object_id} at {self.timestamp}"
    
    def save(self, *args, **kwargs):
        """Route to current database"""
        current_db = get_current_db()
        if current_db and 'using' not in kwargs:
            kwargs['using'] = current_db
        return super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Route to current database"""
        current_db = get_current_db()
        if current_db and 'using' not in kwargs:
            kwargs['using'] = current_db
        return super().delete(*args, **kwargs)
    
    def get_user(self):
        """Get the user who made this change"""
        if not self.user_id:
            return None
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            return User.objects.using('default').get(id=self.user_id)
        except Exception as e:
            logger.error(f"Error fetching audit log user: {e}")
            return None
    
    def get_changes_display(self):
        """Get a human-readable display of changes"""
        if not self.changes:
            return "No field changes recorded"
        
        lines = []
        for field, change in self.changes.items():
            old_val = change.get('old', 'N/A')
            new_val = change.get('new', 'N/A')
            lines.append(f"{field}: '{old_val}' → '{new_val}'")
        
        return "\n".join(lines)


class FinancialAuditLog(models.Model):
    """
    Specialized audit log for SACCO financial transactions and sensitive operations.
    Uses SACCO timezone for all timestamps and CharField for currency.
    """
    
    # SACCO-specific financial action types
    FINANCIAL_ACTIONS = [
        # Member financial actions
        ('DEPOSIT_RECEIVE', 'Deposit Received'),
        ('WITHDRAWAL_PROCESS', 'Withdrawal Processed'),
        ('TRANSFER_EXECUTE', 'Transfer Executed'),
        ('BALANCE_ADJUST', 'Member Balance Adjusted'),
        
        # Loan actions
        ('LOAN_APPLICATION', 'Loan Application Submitted'),
        ('LOAN_APPROVE', 'Loan Approved'),
        ('LOAN_REJECT', 'Loan Rejected'),
        ('LOAN_DISBURSE', 'Loan Disbursed'),
        ('LOAN_PAYMENT', 'Loan Payment Received'),
        ('LOAN_RESTRUCTURE', 'Loan Restructured'),
        ('LOAN_WRITEOFF', 'Loan Written Off'),
        
        # Savings actions
        ('SAVINGS_OPEN', 'Savings Account Opened'),
        ('SAVINGS_CLOSE', 'Savings Account Closed'),
        ('SAVINGS_DEPOSIT', 'Savings Deposit'),
        ('SAVINGS_WITHDRAWAL', 'Savings Withdrawal'),
        ('INTEREST_CREDIT', 'Interest Credited'),
        
        # Share capital actions
        ('SHARE_PURCHASE', 'Shares Purchased'),
        ('SHARE_TRANSFER', 'Shares Transferred'),
        ('SHARE_WITHDRAWAL', 'Shares Withdrawn'),
        
        # Dividend actions
        ('DIVIDEND_DECLARE', 'Dividend Declared'),
        ('DIVIDEND_DISTRIBUTE', 'Dividend Distributed'),
        ('DIVIDEND_CALCULATION', 'Dividend Calculated'),
        
        # Fee and charge actions
        ('FEE_CHARGE', 'Fee Charged'),
        ('FEE_WAIVER', 'Fee Waived'),
        ('PENALTY_CHARGE', 'Penalty Charged'),
        
        # Administrative actions
        ('FINANCIAL_REPORT_GENERATE', 'Financial Report Generated'),
        ('ACCOUNT_CREATE', 'Account Created'),
        ('ACCOUNT_UPDATE', 'Account Updated'),
        ('JOURNAL_POST', 'Journal Entry Posted'),
        ('RECONCILIATION', 'Account Reconciliation'),
        
        # Security actions
        ('FINANCIAL_DATA_EXPORT', 'Financial Data Exported'),
        ('SETTINGS_CHANGE', 'Financial Settings Changed'),
        ('USER_ACCESS_FINANCIAL', 'Financial Module Accessed'),
        
        # Budget and expense actions
        ('EXPENSE_CREATE', 'Expense Created'),
        ('EXPENSE_APPROVE', 'Expense Approved'),
        ('BUDGET_CREATE', 'Budget Created'),
        ('BUDGET_APPROVE', 'Budget Approved'),
        
        # Tax actions
        ('TAX_CALCULATE', 'Tax Calculated'),
        ('TAX_WITHHOLD', 'Tax Withheld'),
        ('TAX_REMIT', 'Tax Remitted'),
        ('TAX_REPORT', 'Tax Report Generated'),
    ]
    
    # Core audit fields
    id = models.AutoField(primary_key=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    action = models.CharField(max_length=30, choices=FINANCIAL_ACTIONS, db_index=True)
    
    # User information - CharField to avoid cross-database FK
    user_id = models.CharField(
        "User ID",
        max_length=50,
        null=True, 
        blank=True, 
        db_index=True,
        help_text="ID of user who performed this action"
    )
    user_name = models.CharField(max_length=200, null=True, blank=True)
    user_role = models.CharField(max_length=100, null=True, blank=True)
    
    # Session and request context
    session_key = models.CharField(max_length=40, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    user_agent = models.TextField(null=True, blank=True)
    
    # Target object (what was changed)
    content_type = models.ForeignKey(
        ContentType, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    object_id = models.CharField(max_length=100, null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    object_description = models.CharField(max_length=500, null=True, blank=True)
    
    # Financial-specific fields
    amount_involved = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Monetary amount involved in the action"
    )
    currency = models.CharField(max_length=3, default='UGX', blank=True)
    
    # Member context (for member-related financial actions)
    member_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    member_name = models.CharField(max_length=200, null=True, blank=True)
    member_account_number = models.CharField(max_length=50, null=True, blank=True)
    
    # Period context
    period_id = models.CharField(max_length=100, null=True, blank=True)
    period_name = models.CharField(max_length=100, null=True, blank=True)
    
    # Change tracking
    old_values = models.JSONField(null=True, blank=True, help_text="Values before change")
    new_values = models.JSONField(null=True, blank=True, help_text="Values after change")
    changes_summary = models.TextField(null=True, blank=True, help_text="Human-readable summary of changes")
    
    # Risk and compliance
    risk_level = models.CharField(
        max_length=10,
        choices=[
            ('LOW', 'Low Risk'),
            ('MEDIUM', 'Medium Risk'),
            ('HIGH', 'High Risk'),
            ('CRITICAL', 'Critical Risk'),
        ],
        default='LOW',
        db_index=True
    )
    compliance_flags = models.JSONField(
        default=list, 
        blank=True,
        help_text="Compliance-related flags or concerns"
    )
    
    # Additional context
    additional_data = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Additional context-specific data"
    )
    notes = models.TextField(null=True, blank=True)
    
    # Processing information
    is_automated = models.BooleanField(
        default=False,
        help_text="Whether this action was performed automatically by the system"
    )
    batch_id = models.CharField(
        max_length=100, 
        null=True, 
        blank=True,
        help_text="For grouping related bulk operations"
    )
    
    # Use SaccoManager for automatic database routing
    objects = SaccoManager()
    
    class Meta:
        verbose_name = "Financial Audit Log"
        verbose_name_plural = "Financial Audit Logs"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp', 'action']),
            models.Index(fields=['user_id', 'timestamp']),
            models.Index(fields=['member_id', 'timestamp']),
            models.Index(fields=['risk_level', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
            models.Index(fields=['period_id', 'action']),
        ]
    
    def __str__(self):
        return f"{self.get_action_display()} at {self.timestamp}"
    
    def save(self, *args, **kwargs):
        """Route to current database"""
        current_db = get_current_db()
        if current_db and 'using' not in kwargs:
            kwargs['using'] = current_db
        return super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Route to current database"""
        current_db = get_current_db()
        if current_db and 'using' not in kwargs:
            kwargs['using'] = current_db
        return super().delete(*args, **kwargs)
    
    @classmethod
    def log_financial_action(
        cls,
        action,
        user=None,
        request=None,
        target_object=None,
        amount=None,
        member=None,
        period=None,
        old_values=None,
        new_values=None,
        risk_level='LOW',
        additional_data=None,
        notes=None,
        currency=None,
        **kwargs
    ):
        """
        Class method to log SACCO financial actions.
        
        Uses SACCO timezone for timestamps and CharField for currency.
        
        Args:
            action: Action type from FINANCIAL_ACTIONS
            user: User performing the action
            request: HTTP request object (for IP, session, etc.)
            target_object: The object being acted upon
            amount: Monetary amount involved
            member: Member related to this action
            period: Fiscal period (object or ID)
            old_values: Dict of values before change
            new_values: Dict of values after change
            risk_level: Risk level of this action
            additional_data: Dict of additional context
            notes: Text notes about this action
            currency: Currency code (string or object with .code)
            **kwargs: Additional fields (is_automated, batch_id, etc.)
            
        Returns:
            FinancialAuditLog instance or None if error
            
        Example:
            FinancialAuditLog.log_financial_action(
                action='LOAN_DISBURSE',
                user=request.user,
                request=request,
                target_object=loan,
                amount=loan.amount,
                member=loan.member,
                period=fiscal_period,
                risk_level='MEDIUM',
                notes='Loan disbursed to member account'
            )
        """
        from django.contrib.contenttypes.models import ContentType
        from core.utils import get_sacco_current_time  # ⭐ USE SACCO TIMEZONE

        try:
            # Prepare base log payload with SACCO timezone
            log_data = {
                'action': action,
                'risk_level': risk_level,
                'timestamp': get_sacco_current_time(),  # ⭐ SACCO TIMEZONE
                'notes': (notes or '')[:2000],
                'old_values': old_values,
                'new_values': new_values,
                'additional_data': (additional_data or {}),
                'is_automated': bool(kwargs.get('is_automated', False)),
                'batch_id': kwargs.get('batch_id'),
            }

            # User info - Handle with CharField
            if user:
                full_name = getattr(user, 'get_full_name', lambda: '')() or getattr(user, 'username', '') or str(user)
                role = getattr(user, 'role', '') or getattr(user, 'user_type', '') or ''
                log_data.update({
                    'user_id': str(getattr(user, 'id', None) or getattr(user, 'pk', None)),
                    'user_name': full_name[:255],
                    'user_role': role[:100],
                })

            # Request info
            if request:
                session_key = getattr(getattr(request, 'session', None), 'session_key', None)
                user_agent = getattr(request, 'META', {}).get('HTTP_USER_AGENT', '')
                xff = getattr(request, 'META', {}).get('HTTP_X_FORWARDED_FOR')
                ip = (xff.split(',')[0].strip() if xff else getattr(request, 'META', {}).get('REMOTE_ADDR', ''))
                log_data.update({
                    'session_key': session_key,
                    'ip_address': ip,
                    'user_agent': user_agent[:512],
                })

            # Target object info
            if target_object is not None:
                try:
                    ct = ContentType.objects.get_for_model(target_object, for_concrete_model=False)
                except Exception:
                    ct = None
                log_data.update({
                    'content_type': ct,
                    'object_id': str(getattr(target_object, 'pk', '')),
                    'object_description': (str(target_object)[:500] if target_object is not None else ''),
                })

            # Member info (SACCO-specific)
            if member:
                member_name = getattr(member, 'get_full_name', lambda: str(member))()
                log_data.update({
                    'member_id': str(getattr(member, 'pk', '')),
                    'member_name': member_name[:255],
                    'member_account_number': str(getattr(member, 'member_number', '') or getattr(member, 'account_number', ''))[:64],
                })

            # Period - handle as object or string/UUID
            if period:
                try:
                    if hasattr(period, 'pk'):
                        log_data.update({
                            'period_id': str(period.pk),
                            'period_name': str(period)[:255],
                        })
                    else:
                        period_str = str(period)
                        try:
                            from core.models import FiscalPeriod
                            period_obj = FiscalPeriod.objects.filter(id=period_str).first()
                        except Exception:
                            period_obj = None

                        if period_obj:
                            log_data.update({
                                'period_id': str(period_obj.pk),
                                'period_name': str(period_obj)[:255],
                            })
                        else:
                            log_data.update({
                                'period_id': period_str[:64],
                                'period_name': period_str[:255],
                            })
                except Exception as period_error:
                    logger.warning(f"Error processing period for audit log: {period_error}")
                    ps = str(period)
                    log_data.update({
                        'period_id': ps[:64],
                        'period_name': ps[:255],
                    })

            # Amount
            if amount is not None:
                try:
                    log_data['amount_involved'] = Decimal(str(amount))
                except (ValueError, InvalidOperation):
                    logger.warning(f"Invalid amount for audit log: {amount}")

            # Currency handling - CharField (no .code needed!)
            if currency:
                # Handle both string and Currency object (for backward compatibility)
                if hasattr(currency, 'code'):
                    log_data['currency'] = str(currency.code)[:3].upper()
                else:
                    log_data['currency'] = str(currency)[:3].upper()
            else:
                # Get from FinancialSettings (sacco_currency is CharField)
                try:
                    from core.models import FinancialSettings
                    settings = FinancialSettings.get_settings()
                    if settings and settings.sacco_currency:
                        # ⭐ Direct string access - no .code needed!
                        log_data['currency'] = str(settings.sacco_currency)[:3].upper()
                    else:
                        log_data['currency'] = 'UGX'
                except Exception as e:
                    logger.debug(f"Could not get currency from FinancialSettings: {e}")
                    log_data['currency'] = 'UGX'

            return cls.objects.create(**log_data)

        except Exception as e:
            logger.error(f"Error creating financial audit log: {e}", exc_info=True)
            return None