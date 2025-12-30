# dividends/services.py

"""
Dividends Business Logic Services

Contains complex business logic that shouldn't be in views or models:
- Dividend period management
- Dividend calculation workflows
- Disbursement processing
- Payment processing
- Member preference management
- Bulk operations

WHY SERVICES.PY?
1. Separation of Concerns: Complex business logic separate from views
2. Reusability: Can be called from views, management commands, celery tasks
3. Testing: Easier to test business logic in isolation
4. Transaction Management: Handle complex multi-step operations
5. Clear API: Well-defined functions for each business operation
"""

from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, Count
from decimal import Decimal
import logging

from .models import (
    DividendPeriod,
    MemberDividend,
    DividendRate,
    DividendDisbursement,
    DividendPayment,
    DividendPreference,
)

from .utils import (
    calculate_flat_rate_dividend,
    calculate_weighted_average_dividend,
    calculate_tiered_dividend,
    calculate_pro_rata_dividend,
    calculate_withholding_tax,
    calculate_net_dividend,
    calculate_total_shares_value,
    can_calculate_dividends,
    can_approve_dividend_period,
    can_disburse_dividends,
    get_eligible_members,
    validate_total_dividend_allocation,
)

logger = logging.getLogger(__name__)


# =============================================================================
# DIVIDEND PERIOD SERVICES
# =============================================================================

class DividendPeriodService:
    """Handle dividend period lifecycle and management"""
    
    @staticmethod
    @transaction.atomic
    def create_period(name, financial_period, start_date, end_date, record_date,
                     total_dividend_amount, dividend_rate, calculation_method='FLAT_RATE',
                     withholding_tax_rate=Decimal('15'), **kwargs):
        """
        Create a new dividend period.
        
        Args:
            name (str): Period name
            financial_period: FiscalPeriod instance
            start_date (date): Period start date
            end_date (date): Period end date
            record_date (date): Record date for eligibility
            total_dividend_amount (Decimal): Total dividend pool
            dividend_rate (Decimal): Dividend rate percentage
            calculation_method (str): Calculation method
            withholding_tax_rate (Decimal): Tax rate percentage
            **kwargs: Additional period fields
        
        Returns:
            tuple: (success: bool, period_or_error_message)
        """
        try:
            # Create period
            period = DividendPeriod.objects.create(
                name=name,
                financial_period=financial_period,
                start_date=start_date,
                end_date=end_date,
                record_date=record_date,
                total_dividend_amount=total_dividend_amount,
                dividend_rate=dividend_rate,
                calculation_method=calculation_method,
                withholding_tax_rate=withholding_tax_rate,
                apply_withholding_tax=kwargs.get('apply_withholding_tax', True),
                default_disbursement_method=kwargs.get('default_disbursement_method', 'SAVINGS_ACCOUNT'),
                status='DRAFT',
                **{k: v for k, v in kwargs.items() if k not in [
                    'apply_withholding_tax', 'default_disbursement_method'
                ]}
            )
            
            logger.info(
                f"Created dividend period: {period.name} | "
                f"Amount: {total_dividend_amount} | "
                f"Rate: {dividend_rate}%"
            )
            
            return True, period
            
        except Exception as e:
            logger.error(f"Error creating dividend period: {e}", exc_info=True)
            return False, f"Error creating period: {str(e)}"
    
    @staticmethod
    @transaction.atomic
    def open_period(period, opened_by=None):
        """
        Open dividend period for calculation.
        
        Args:
            period: DividendPeriod instance
            opened_by: User who opened the period
        
        Returns:
            tuple: (success: bool, message: str)
        """
        if period.status != 'DRAFT':
            return False, f"Cannot open period with status: {period.get_status_display()}"
        
        try:
            period.status = 'OPEN'
            period.save(update_fields=['status', 'updated_at'])
            
            logger.info(
                f"Dividend period opened: {period.name} | "
                f"By: {opened_by if opened_by else 'system'}"
            )
            
            return True, f"Period {period.name} opened successfully"
            
        except Exception as e:
            logger.error(f"Error opening period: {e}", exc_info=True)
            return False, f"Error opening period: {str(e)}"
    
    @staticmethod
    @transaction.atomic
    def close_period(period, closed_by=None):
        """
        Close dividend period.
        
        Args:
            period: DividendPeriod instance
            closed_by: User who closed the period
        
        Returns:
            tuple: (success: bool, message: str)
        """
        if period.status not in ['DRAFT', 'OPEN']:
            return False, f"Cannot close period with status: {period.get_status_display()}"
        
        try:
            period.status = 'CANCELLED'
            period.save(update_fields=['status', 'updated_at'])
            
            logger.info(
                f"Dividend period closed: {period.name} | "
                f"By: {closed_by if closed_by else 'system'}"
            )
            
            return True, f"Period {period.name} closed successfully"
            
        except Exception as e:
            logger.error(f"Error closing period: {e}", exc_info=True)
            return False, f"Error closing period: {str(e)}"
    
    @staticmethod
    @transaction.atomic
    def approve_period(period, approved_by=None):
        """
        Approve calculated dividend period.
        
        Args:
            period: DividendPeriod instance
            approved_by: User who approved the period
        
        Returns:
            tuple: (success: bool, message: str)
        """
        # Check if can be approved
        can_approve, message = can_approve_dividend_period(period)
        if not can_approve:
            return False, message
        
        try:
            # Use model method
            success, message = period.approve()
            
            if success:
                # Update approved_by
                period.approved_by_id = str(approved_by.id) if approved_by else None
                period.save(update_fields=['approved_by_id'])
                
                logger.info(
                    f"Dividend period approved: {period.name} | "
                    f"By: {approved_by if approved_by else 'system'}"
                )
            
            return success, message
            
        except Exception as e:
            logger.error(f"Error approving period: {e}", exc_info=True)
            return False, f"Error approving period: {str(e)}"


# =============================================================================
# DIVIDEND CALCULATION SERVICES
# =============================================================================

class DividendCalculationService:
    """Handle dividend calculation workflows"""
    
    @staticmethod
    @transaction.atomic
    def calculate_dividends(period):
        """
        Calculate dividends for all eligible members.
        
        Args:
            period: DividendPeriod instance
        
        Returns:
            dict: Calculation results
                {
                    'success': bool,
                    'message': str,
                    'total_members': int,
                    'total_calculated': Decimal,
                    'errors': list
                }
        """
        # Check if can calculate
        can_calc, message = can_calculate_dividends(period)
        if not can_calc:
            return {
                'success': False,
                'message': message,
                'total_members': 0,
                'total_calculated': Decimal('0.00'),
                'errors': []
            }
        
        try:
            # Update status
            period.status = 'CALCULATING'
            period.save(update_fields=['status'])
            
            # Get eligible members
            eligible_members = get_eligible_members(period)
            
            if not eligible_members:
                period.status = 'OPEN'
                period.save(update_fields=['status'])
                return {
                    'success': False,
                    'message': 'No eligible members found',
                    'total_members': 0,
                    'total_calculated': Decimal('0.00'),
                    'errors': []
                }
            
            # Calculate based on method
            if period.calculation_method == 'FLAT_RATE':
                result = DividendCalculationService._calculate_flat_rate(period, eligible_members)
            
            elif period.calculation_method == 'WEIGHTED_AVERAGE':
                result = DividendCalculationService._calculate_weighted_average(period, eligible_members)
            
            elif period.calculation_method == 'TIERED':
                result = DividendCalculationService._calculate_tiered(period, eligible_members)
            
            elif period.calculation_method == 'PRO_RATA':
                result = DividendCalculationService._calculate_pro_rata(period, eligible_members)
            
            else:
                result = {
                    'success': False,
                    'message': f'Unknown calculation method: {period.calculation_method}',
                    'total_members': 0,
                    'total_calculated': Decimal('0.00'),
                    'errors': []
                }
            
            # Update period status
            if result['success']:
                period.status = 'CALCULATED'
            else:
                period.status = 'OPEN'
            period.save(update_fields=['status'])
            
            logger.info(
                f"Dividend calculation completed: {period.name} | "
                f"Method: {period.calculation_method} | "
                f"Members: {result['total_members']} | "
                f"Total: {result['total_calculated']}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating dividends: {e}", exc_info=True)
            
            # Reset status
            period.status = 'OPEN'
            period.save(update_fields=['status'])
            
            return {
                'success': False,
                'message': f'Error calculating dividends: {str(e)}',
                'total_members': 0,
                'total_calculated': Decimal('0.00'),
                'errors': [str(e)]
            }
    
    @staticmethod
    def _calculate_flat_rate(period, eligible_members):
        """Calculate dividends using flat rate method"""
        total_calculated = Decimal('0.00')
        errors = []
        created_count = 0
        
        for member_info in eligible_members:
            try:
                member = member_info['member']
                shares_value = member_info['shares_value']
                shares_count = member_info['shares_count']
                
                # Calculate gross dividend
                gross_dividend = calculate_flat_rate_dividend(
                    shares_value,
                    period.dividend_rate
                )
                
                # Calculate tax
                tax_amount = Decimal('0.00')
                if period.apply_withholding_tax:
                    tax_amount = calculate_withholding_tax(
                        gross_dividend,
                        period.withholding_tax_rate
                    )
                
                # Calculate net
                net_dividend = calculate_net_dividend(gross_dividend, tax_amount)
                
                # Create or update member dividend
                member_dividend, created = MemberDividend.objects.update_or_create(
                    dividend_period=period,
                    member=member,
                    defaults={
                        'shares_count': shares_count,
                        'shares_value': shares_value,
                        'gross_dividend': gross_dividend,
                        'tax_amount': tax_amount,
                        'net_dividend': net_dividend,
                        'applied_rate': period.dividend_rate,
                        'status': 'CALCULATED'
                    }
                )
                
                if created:
                    created_count += 1
                
                total_calculated += net_dividend
                
            except Exception as e:
                error_msg = f"Error calculating dividend for {member.get_full_name()}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # Validate total allocation
        is_valid, diff, msg = validate_total_dividend_allocation(
            total_calculated,
            period.total_dividend_amount
        )
        
        if not is_valid:
            errors.append(msg)
        
        return {
            'success': len(errors) == 0 or created_count > 0,
            'message': f'Calculated dividends for {created_count} members',
            'total_members': len(eligible_members),
            'total_calculated': total_calculated,
            'errors': errors
        }
    
    @staticmethod
    def _calculate_weighted_average(period, eligible_members):
        """Calculate dividends using weighted average method"""
        # Calculate total shares value
        total_shares_value = sum(
            m['shares_value'] for m in eligible_members
        )
        
        if total_shares_value <= 0:
            return {
                'success': False,
                'message': 'Total shares value is zero',
                'total_members': 0,
                'total_calculated': Decimal('0.00'),
                'errors': ['Total shares value is zero']
            }
        
        total_calculated = Decimal('0.00')
        errors = []
        created_count = 0
        
        for member_info in eligible_members:
            try:
                member = member_info['member']
                shares_value = member_info['shares_value']
                shares_count = member_info['shares_count']
                
                # Calculate gross dividend
                gross_dividend = calculate_weighted_average_dividend(
                    shares_value,
                    total_shares_value,
                    period.total_dividend_amount
                )
                
                # Calculate yield (as applied rate)
                from .utils import calculate_dividend_yield
                applied_rate = calculate_dividend_yield(gross_dividend, shares_value)
                
                # Calculate tax
                tax_amount = Decimal('0.00')
                if period.apply_withholding_tax:
                    tax_amount = calculate_withholding_tax(
                        gross_dividend,
                        period.withholding_tax_rate
                    )
                
                # Calculate net
                net_dividend = calculate_net_dividend(gross_dividend, tax_amount)
                
                # Create or update member dividend
                member_dividend, created = MemberDividend.objects.update_or_create(
                    dividend_period=period,
                    member=member,
                    defaults={
                        'shares_count': shares_count,
                        'shares_value': shares_value,
                        'gross_dividend': gross_dividend,
                        'tax_amount': tax_amount,
                        'net_dividend': net_dividend,
                        'applied_rate': applied_rate,
                        'status': 'CALCULATED'
                    }
                )
                
                if created:
                    created_count += 1
                
                total_calculated += net_dividend
                
            except Exception as e:
                error_msg = f"Error calculating dividend for {member.get_full_name()}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        return {
            'success': len(errors) == 0 or created_count > 0,
            'message': f'Calculated dividends for {created_count} members',
            'total_members': len(eligible_members),
            'total_calculated': total_calculated,
            'errors': errors
        }
    
    @staticmethod
    def _calculate_tiered(period, eligible_members):
        """Calculate dividends using tiered rates"""
        # Get dividend rates for this period
        dividend_rates = list(period.dividend_rates.filter(is_active=True).values(
            'min_shares', 'max_shares', 'min_value', 'max_value', 'rate'
        ))
        
        if not dividend_rates:
            return {
                'success': False,
                'message': 'No active dividend rate tiers configured',
                'total_members': 0,
                'total_calculated': Decimal('0.00'),
                'errors': ['No active dividend rate tiers']
            }
        
        total_calculated = Decimal('0.00')
        errors = []
        created_count = 0
        
        for member_info in eligible_members:
            try:
                member = member_info['member']
                shares_value = member_info['shares_value']
                shares_count = member_info['shares_count']
                
                # Calculate tiered dividend
                gross_dividend, applied_rate = calculate_tiered_dividend(
                    shares_value,
                    shares_count,
                    dividend_rates
                )
                
                # Calculate tax
                tax_amount = Decimal('0.00')
                if period.apply_withholding_tax:
                    tax_amount = calculate_withholding_tax(
                        gross_dividend,
                        period.withholding_tax_rate
                    )
                
                # Calculate net
                net_dividend = calculate_net_dividend(gross_dividend, tax_amount)
                
                # Create or update member dividend
                member_dividend, created = MemberDividend.objects.update_or_create(
                    dividend_period=period,
                    member=member,
                    defaults={
                        'shares_count': shares_count,
                        'shares_value': shares_value,
                        'gross_dividend': gross_dividend,
                        'tax_amount': tax_amount,
                        'net_dividend': net_dividend,
                        'applied_rate': applied_rate,
                        'status': 'CALCULATED'
                    }
                )
                
                if created:
                    created_count += 1
                
                total_calculated += net_dividend
                
            except Exception as e:
                error_msg = f"Error calculating dividend for {member.get_full_name()}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        return {
            'success': len(errors) == 0 or created_count > 0,
            'message': f'Calculated dividends for {created_count} members',
            'total_members': len(eligible_members),
            'total_calculated': total_calculated,
            'errors': errors
        }
    
    @staticmethod
    def _calculate_pro_rata(period, eligible_members):
        """Calculate dividends using pro-rata method"""
        # Similar to weighted average but with minimum payout threshold
        return DividendCalculationService._calculate_weighted_average(period, eligible_members)
    
    @staticmethod
    @transaction.atomic
    def recalculate_dividends(period):
        """
        Recalculate dividends (delete existing and recalculate).
        
        Args:
            period: DividendPeriod instance
        
        Returns:
            dict: Calculation results
        """
        try:
            # Delete existing member dividends
            deleted_count = period.member_dividends.all().delete()[0]
            
            logger.info(f"Deleted {deleted_count} existing member dividends for period {period.name}")
            
            # Recalculate
            return DividendCalculationService.calculate_dividends(period)
            
        except Exception as e:
            logger.error(f"Error recalculating dividends: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'Error recalculating dividends: {str(e)}',
                'total_members': 0,
                'total_calculated': Decimal('0.00'),
                'errors': [str(e)]
            }


# =============================================================================
# DIVIDEND DISBURSEMENT SERVICES
# =============================================================================

class DividendDisbursementService:
    """Handle dividend disbursement workflows"""
    
    @staticmethod
    @transaction.atomic
    def create_disbursement_batch(period, disbursement_date, disbursement_method,
                                  description=None):
        """
        Create a new disbursement batch.
        
        Args:
            period: DividendPeriod instance
            disbursement_date (date): Disbursement date
            disbursement_method (str): Disbursement method
            description (str, optional): Batch description
        
        Returns:
            tuple: (success: bool, disbursement_or_error_message)
        """
        # Check if can disburse
        can_disb, message = can_disburse_dividends(period)
        if not can_disb:
            return False, message
        
        try:
            # Get approved member dividends
            approved_dividends = period.member_dividends.filter(status='APPROVED')
            
            if not approved_dividends.exists():
                return False, "No approved member dividends found"
            
            # Calculate totals
            totals = approved_dividends.aggregate(
                total_members=Count('id'),
                total_amount=Sum('net_dividend')
            )
            
            # Create disbursement (batch number auto-generated by signal)
            disbursement = DividendDisbursement.objects.create(
                dividend_period=period,
                disbursement_date=disbursement_date,
                disbursement_method=disbursement_method,
                description=description,
                total_members=totals['total_members'],
                total_amount=totals['total_amount'],
                status='PENDING'
            )
            
            logger.info(
                f"Created disbursement batch: {disbursement.batch_number} | "
                f"Period: {period.name} | "
                f"Members: {totals['total_members']} | "
                f"Amount: {totals['total_amount']}"
            )
            
            return True, disbursement
            
        except Exception as e:
            logger.error(f"Error creating disbursement batch: {e}", exc_info=True)
            return False, f"Error creating disbursement: {str(e)}"
    
    @staticmethod
    @transaction.atomic
    def process_disbursement(disbursement):
        """
        Process dividend disbursement batch.
        
        Creates individual payment records for each member.
        
        Args:
            disbursement: DividendDisbursement instance
        
        Returns:
            dict: Processing results
        """
        if disbursement.status != 'PENDING':
            return {
                'success': False,
                'message': f'Cannot process disbursement with status: {disbursement.get_status_display()}',
                'processed': 0,
                'errors': []
            }
        
        try:
            # Start processing
            success, message = disbursement.start_processing()
            if not success:
                return {
                    'success': False,
                    'message': message,
                    'processed': 0,
                    'errors': []
                }
            
            # Get approved member dividends
            member_dividends = disbursement.dividend_period.member_dividends.filter(
                status='APPROVED'
            )
            
            processed = 0
            errors = []
            
            for member_dividend in member_dividends:
                try:
                    # Create payment record
                    payment = DividendPayment.objects.create(
                        member_dividend=member_dividend,
                        disbursement=disbursement,
                        payment_date=timezone.now(),
                        amount=member_dividend.net_dividend,
                        status='PENDING',
                        savings_account=member_dividend.disbursement_account
                    )
                    
                    # Update member dividend status
                    member_dividend.status = 'PROCESSING'
                    member_dividend.save(update_fields=['status'])
                    
                    processed += 1
                    
                except Exception as e:
                    error_msg = f"Error creating payment for {member_dividend.member.get_full_name()}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Complete processing
            disbursement.complete_processing()
            
            logger.info(
                f"Disbursement batch processed: {disbursement.batch_number} | "
                f"Processed: {processed} | "
                f"Errors: {len(errors)}"
            )
            
            return {
                'success': processed > 0,
                'message': f'Processed {processed} payments',
                'processed': processed,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error processing disbursement: {e}", exc_info=True)
            
            # Mark as failed
            disbursement.status = 'FAILED'
            disbursement.save(update_fields=['status'])
            
            return {
                'success': False,
                'message': f'Error processing disbursement: {str(e)}',
                'processed': 0,
                'errors': [str(e)]
            }


# =============================================================================
# DIVIDEND PAYMENT SERVICES
# =============================================================================

class DividendPaymentService:
    """Handle individual dividend payments"""
    
    @staticmethod
    @transaction.atomic
    def process_payment_to_savings(payment):
        """
        Process payment to member's savings account.
        
        Args:
            payment: DividendPayment instance
        
        Returns:
            tuple: (success: bool, message: str)
        """
        if payment.status != 'PENDING':
            return False, f"Cannot process payment with status: {payment.get_status_display()}"
        
        try:
            # Get savings account
            savings_account = payment.savings_account
            
            if not savings_account:
                return payment.mark_as_failed("No savings account specified")
            
            # Create deposit transaction in savings
            from savings.services import TransactionService
            
            success, result = TransactionService.process_deposit(
                account=savings_account,
                amount=payment.amount,
                payment_method='INTERNAL_TRANSFER',
                description=f"Dividend payment from {payment.disbursement.dividend_period.name}",
                reference_number=payment.disbursement.batch_number
            )
            
            if success:
                transaction = result
                
                # Mark payment as completed
                payment.mark_as_completed(transaction_id=transaction.transaction_id)
                
                logger.info(
                    f"Dividend paid to savings: {payment.member_dividend.member.get_full_name()} | "
                    f"Amount: {payment.amount} | "
                    f"Account: {savings_account.account_number}"
                )
                
                return True, "Payment completed successfully"
            else:
                # Mark as failed
                payment.mark_as_failed(f"Deposit failed: {result}")
                return False, result
            
        except Exception as e:
            error_msg = f"Error processing payment: {str(e)}"
            logger.error(error_msg, exc_info=True)
            payment.mark_as_failed(error_msg)
            return False, error_msg
    
    @staticmethod
    @transaction.atomic
    def retry_failed_payment(payment):
        """
        Retry a failed payment.
        
        Args:
            payment: DividendPayment instance
        
        Returns:
            tuple: (success: bool, message: str)
        """
        if not payment.can_retry:
            return False, "Payment cannot be retried (max attempts reached or not failed)"
        
        try:
            # Reset status to pending
            payment.status = 'PENDING'
            payment.save(update_fields=['status'])
            
            # Process based on disbursement method
            if payment.disbursement.disbursement_method == 'SAVINGS_ACCOUNT':
                return DividendPaymentService.process_payment_to_savings(payment)
            else:
                return False, f"Unsupported disbursement method: {payment.disbursement.get_disbursement_method_display()}"
            
        except Exception as e:
            logger.error(f"Error retrying payment: {e}", exc_info=True)
            return False, f"Error retrying payment: {str(e)}"
