# loans/views.py

"""
Loan Management Views

Comprehensive view functions for:
- Loan Products and Configuration
- Loan Applications and Processing
- Loan Disbursement and Management
- Loan Payments and Collections
- Loan Guarantors and Collateral
- Loan Schedule and Tracking
- Reports and Analytics

All views include proper permissions, messaging, and error handling
Uses stats.py for comprehensive statistics and analytics
Uses SweetAlert2 for all notifications via Django messages
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg, F
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from datetime import timedelta, date
from decimal import Decimal
import logging

from .models import (
    LoanProduct,
    LoanApplication,
    Loan,
    LoanPayment,
    LoanGuarantor,
    LoanCollateral,
    LoanSchedule,
    LoanDocument
)

from .forms import (
    LoanProductForm,
    LoanApplicationForm,
    LoanApplicationQuickForm,
    LoanDisbursementForm,
    LoanPaymentForm,
    QuickLoanPaymentForm,
    LoanGuarantorForm,
    LoanCollateralForm,
    LoanDocumentForm,
    BulkLoanDisbursementForm,
    LoanReportForm,
    LoanFilterForm,
    LoanApplicationFilterForm,
    LoanCollateralFilterForm,
    LoanPaymentFilterForm,
    LoanProductFilterForm,
    LoanGuarantorFilterForm,
    LoanScheduleFilterForm
)

# Import stats functions
from . import stats as loan_stats

from members.models import Member
from core.models import PaymentMethod, FiscalPeriod
from core.utils import format_money

logger = logging.getLogger(__name__)


# =============================================================================
# DASHBOARD
# =============================================================================

@login_required
def loans_dashboard(request):
    """Main loans dashboard with overview statistics - USES stats.py"""
    
    try:
        # Use comprehensive overview from stats.py
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)
        
        overview = loan_stats.get_loan_overview(
            date_from=thirty_days_ago,
            date_to=today
        )
        
        # Get additional product stats
        product_stats = loan_stats.get_product_statistics()
        
        # Get application stats
        application_stats = loan_stats.get_application_statistics({
            'date_from': thirty_days_ago,
            'date_to': today
        })
        
        # Get loan stats
        loan_stats_data = loan_stats.get_loan_statistics()
        
        # Get payment stats
        payment_stats = loan_stats.get_payment_statistics({
            'date_from': thirty_days_ago,
            'date_to': today
        })
        
    except Exception as e:
        logger.error(f"Error getting dashboard statistics: {e}")
        overview = {}
        product_stats = {}
        application_stats = {}
        loan_stats_data = {}
        payment_stats = {}
    
    # Get recent activities (limited queries for display)
    recent_applications = LoanApplication.objects.select_related(
        'member', 'loan_product'
    ).order_by('-created_at')[:10]
    
    recent_disbursements = Loan.objects.select_related(
        'member', 'loan_product'
    ).order_by('-disbursement_date')[:10]
    
    recent_payments = LoanPayment.objects.select_related(
        'loan', 'loan__member'
    ).order_by('-payment_date')[:10]
    
    # Get pending applications
    pending_applications = LoanApplication.objects.filter(
        status__in=['SUBMITTED', 'UNDER_REVIEW']
    ).select_related('member', 'loan_product').order_by('-submission_date')[:10]
    
    # Get overdue loans
    overdue_loans = Loan.objects.filter(
        status='ACTIVE',
        days_in_arrears__gt=0
    ).select_related('member', 'loan_product').order_by('-days_in_arrears')[:10]
    
    # Get due installments
    due_installments = LoanSchedule.objects.filter(
        status='PENDING',
        due_date__lte=today + timedelta(days=7)
    ).select_related('loan', 'loan__member').order_by('due_date')[:10]
    
    context = {
        'overview': overview,
        'product_stats': product_stats,
        'application_stats': application_stats,
        'loan_stats': loan_stats_data,
        'payment_stats': payment_stats,
        'recent_applications': recent_applications,
        'recent_disbursements': recent_disbursements,
        'recent_payments': recent_payments,
        'pending_applications': pending_applications,
        'overdue_loans': overdue_loans,
        'due_installments': due_installments,
    }
    
    return render(request, 'loans/dashboard.html', context)


# =============================================================================
# LOAN PRODUCT VIEWS
# =============================================================================

@login_required
def loan_product_list(request):
    """List all loan products - HTMX loads data on page load"""
    
    # Initialize filter form
    filter_form = LoanProductFilterForm()
    
    # Get initial stats from stats.py
    try:
        initial_stats = loan_stats.get_product_statistics()
    except Exception as e:
        logger.error(f"Error getting loan product statistics: {e}")
        initial_stats = {}
    
    context = {
        'filter_form': filter_form,
        'stats': initial_stats,
    }
    
    return render(request, 'loans/products/list.html', context)


@login_required
def loan_product_create(request):
    """Create a new loan product"""
    if request.method == "POST":
        form = LoanProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            # Use SweetAlert for success notification
            messages.success(
                request,
                f"Loan product '{product.name}' was created successfully",
                extra_tags='sweetalert'
            )
            return redirect("loans:product_list")
        else:
            # Use SweetAlert for form error notification
            messages.error(
                request,
                "Please correct the errors below",
                extra_tags='sweetalert-error'
            )
    else:
        form = LoanProductForm()
    
    context = {
        'form': form,
        'title': 'Create Loan Product',
    }
    return render(request, 'loans/products/form.html', context)


@login_required
def loan_product_edit(request, pk):
    """Edit existing loan product"""
    product = get_object_or_404(LoanProduct, pk=pk)
    
    if request.method == "POST":
        form = LoanProductForm(request.POST, instance=product)
        if form.is_valid():
            product = form.save()
            messages.success(
                request,
                f"Loan product '{product.name}' was updated successfully",
                extra_tags='sweetalert'
            )
            return redirect("loans:product_detail", pk=product.pk)
        else:
            messages.error(
                request,
                "Please correct the errors below",
                extra_tags='sweetalert-error'
            )
    else:
        form = LoanProductForm(instance=product)
    
    context = {
        'form': form,
        'product': product,
        'title': 'Update Loan Product',
    }
    return render(request, 'loans/products/form.html', context)


@login_required
def loan_product_detail(request, pk):
    """View loan product details with statistics - USES stats.py"""
    product = get_object_or_404(LoanProduct, pk=pk)
    
    # Get product performance breakdown from stats.py
    try:
        performance_data = loan_stats.get_product_performance_breakdown(product_id=str(product.id))
        product_performance = performance_data['breakdown'][0] if performance_data['breakdown'] else {}
    except Exception as e:
        logger.error(f"Error getting product performance: {e}")
        product_performance = {}
    
    # Get recent applications
    recent_applications = LoanApplication.objects.filter(
        loan_product=product
    ).select_related('member').order_by('-created_at')[:10]
    
    # Get active loans
    active_loans = Loan.objects.filter(
        loan_product=product,
        status='ACTIVE'
    ).select_related('member').order_by('-disbursement_date')[:10]
    
    context = {
        'product': product,
        'performance': product_performance,
        'recent_applications': recent_applications,
        'active_loans': active_loans,
    }
    
    return render(request, 'loans/products/detail.html', context)

# =============================================================================
# LOAN APPLICATION VIEWS
# =============================================================================

@login_required
def loan_application_list(request):
    """List all loan applications - HTMX loads data on page load"""
    
    # Initialize filter form
    filter_form = LoanApplicationFilterForm()
    
    # Get initial stats from stats.py
    try:
        initial_stats = loan_stats.get_application_statistics()
    except Exception as e:
        logger.error(f"Error getting loan application statistics: {e}")
        initial_stats = {}
    
    context = {
        'filter_form': filter_form,
        'stats': initial_stats,
    }
    
    return render(request, 'loans/applications/list.html', context)


@login_required
def loan_application_create(request):
    """Create a new loan application"""
    if request.method == "POST":
        form = LoanApplicationForm(request.POST)
        if form.is_valid():
            application = form.save()
            messages.success(
                request,
                f"Loan application #{application.application_number} was created successfully",
                extra_tags='sweetalert'
            )
            return redirect("loans:application_detail", pk=application.pk)
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = LoanApplicationForm()
    
    context = {
        'form': form,
        'title': 'Create Loan Application',
    }
    return render(request, 'loans/applications/form.html', context)


@login_required
def loan_application_edit(request, pk):
    """Edit existing loan application"""
    application = get_object_or_404(LoanApplication, pk=pk)
    
    # Only draft applications can be edited
    if not application.can_be_edited:
        messages.error(
            request,
            f"Application #{application.application_number} cannot be edited - it is {application.get_status_display()}",
            extra_tags='sweetalert'
        )
        return redirect("loans:application_detail", pk=application.pk)
    
    if request.method == "POST":
        form = LoanApplicationForm(request.POST, instance=application)
        if form.is_valid():
            application = form.save()
            messages.success(
                request,
                f"Loan application #{application.application_number} was updated successfully",
                extra_tags='sweetalert'
            )
            return redirect("loans:application_detail", pk=application.pk)
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = LoanApplicationForm(instance=application)
    
    context = {
        'form': form,
        'application': application,
        'title': 'Update Loan Application',
    }
    return render(request, 'loans/applications/form.html', context)


@login_required
def loan_application_detail(request, pk):
    """View loan application details - USES stats.py for summary"""
    application = get_object_or_404(
        LoanApplication.objects.select_related(
            'member',
            'loan_product',
            'financial_period'
        ).prefetch_related(
            'guarantors',
            'collaterals',
            'documents'
        ),
        pk=pk
    )
    
    # Get application summary from stats.py
    try:
        summary = loan_stats.get_application_summary(application)
    except Exception as e:
        logger.error(f"Error getting application summary: {e}")
        summary = {}
    
    # Get related data
    guarantors = application.guarantors.select_related('guarantor').order_by('-created_at')
    collaterals = application.collaterals.order_by('-created_at')
    documents = application.documents.order_by('-created_at')
    
    context = {
        'application': application,
        'summary': summary,
        'guarantors': guarantors,
        'collaterals': collaterals,
        'documents': documents,
    }
    
    return render(request, 'loans/applications/detail.html', context)


@login_required
def loan_application_submit(request, pk):
    """Submit loan application for review"""
    application = get_object_or_404(LoanApplication, pk=pk)
    
    if request.method == "POST":
        success, message = application.submit()
        
        if success:
            messages.success(request, message, extra_tags='sweetalert')
        else:
            messages.error(request, message, extra_tags='sweetalert')
        
        return redirect("loans:application_detail", pk=application.pk)
    
    return redirect("loans:application_detail", pk=application.pk)

# =============================================================================
# LOAN VIEWS
# =============================================================================

@login_required
def loan_list(request):
    """List all loans - HTMX loads data on page load"""
    
    # Initialize filter form
    filter_form = LoanFilterForm()
    
    # Get initial stats from stats.py
    try:
        stats = loan_stats.get_loan_statistics()
    except Exception as e:
        logger.error(f"Error getting loan statistics: {e}")
        stats = {}
    
    context = {
        'filter_form': filter_form,
        'stats': stats,
    }
    
    return render(request, 'loans/loans/list.html', context)


@login_required
def loan_detail(request, pk):
    """View loan details - USES stats.py for summary"""
    loan = get_object_or_404(
        Loan.objects.select_related(
            'member',
            'loan_product',
            'application',
            'financial_period',
            'disbursement_method'
        ).prefetch_related(
            'payments',
            'schedule'
        ),
        pk=pk
    )
    
    # Get loan summary from stats.py
    try:
        summary = loan_stats.get_loan_summary(loan)
    except Exception as e:
        logger.error(f"Error getting loan summary: {e}")
        summary = {}
    
    # Get payments
    payments = loan.payments.select_related('payment_method_ref').order_by('-payment_date')[:20]
    
    # Get schedule
    schedule = loan.schedule.select_related('financial_period').order_by('installment_number')
    
    # Get documents
    documents = loan.documents.order_by('-created_at')
    
    context = {
        'loan': loan,
        'summary': summary,
        'payments': payments,
        'schedule': schedule,
        'documents': documents,
    }
    
    return render(request, 'loans/loans/detail.html', context)


@login_required
def loan_disburse(request, pk):
    """Disburse approved loan application"""
    application = get_object_or_404(LoanApplication, pk=pk)
    
    # Check if application is approved
    if not application.is_approved:
        messages.error(
            request,
            f"Application #{application.application_number} is not approved for disbursement",
            extra_tags='sweetalert'
        )
        return redirect("loans:application_detail", pk=application.pk)
    
    if request.method == "POST":
        form = LoanDisbursementForm(request.POST)
        if form.is_valid():
            try:
                # Create loan from application
                loan = Loan.objects.create(
                    member=application.member,
                    loan_product=application.loan_product,
                    application=application,
                    principal_amount=application.approved_amount or application.amount_requested,
                    interest_rate=application.approved_interest_rate or application.loan_product.interest_rate,
                    term_months=application.approved_term or application.term_months,
                    payment_frequency=application.loan_product.repayment_cycle,
                    disbursement_date=form.cleaned_data['disbursement_date'],
                    first_payment_date=form.cleaned_data['first_payment_date'],
                    expected_end_date=form.cleaned_data['disbursement_date'] + timedelta(
                        days=30 * (application.approved_term or application.term_months)
                    ),
                    disbursement_method=form.cleaned_data['disbursement_method'],
                    disbursement_reference=form.cleaned_data.get('disbursement_reference'),
                    notes=form.cleaned_data.get('notes'),
                )
                
                # Update application status
                application.status = 'DISBURSED'
                application.save()
                
                messages.success(
                    request,
                    f"Loan #{loan.loan_number} was disbursed successfully to {loan.member.get_full_name()}",
                    extra_tags='sweetalert'
                )
                return redirect("loans:loan_detail", pk=loan.pk)
                
            except Exception as e:
                logger.error(f"Error disbursing loan: {e}")
                messages.error(
                    request,
                    f"Error disbursing loan: {str(e)}",
                    extra_tags='sweetalert'
                )
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = LoanDisbursementForm()
    
    context = {
        'form': form,
        'application': application,
        'title': 'Disburse Loan',
    }
    return render(request, 'loans/loans/disburse_form.html', context)


# =============================================================================
# LOAN PAYMENT VIEWS
# =============================================================================

@login_required
def loan_payment_list(request):
    """List all loan payments - HTMX loads data on page load"""
    
    # Initialize filter form
    filter_form = LoanPaymentFilterForm()
    
    # Get initial stats from stats.py
    try:
        today = timezone.now().date()
        stats = loan_stats.get_payment_statistics({
            'date_from': today,
            'date_to': today
        })
    except Exception as e:
        logger.error(f"Error getting payment statistics: {e}")
        stats = {}
    
    context = {
        'filter_form': filter_form,
        'stats': stats,
    }
    
    return render(request, 'loans/payments/list.html', context)


@login_required
def loan_payment_create(request):
    """Create a new loan payment"""
    if request.method == "POST":
        form = LoanPaymentForm(request.POST)
        if form.is_valid():
            payment = form.save()
            messages.success(
                request,
                f"Payment #{payment.payment_number} of {payment.formatted_amount} was recorded successfully",
                extra_tags='sweetalert'
            )
            return redirect("loans:loan_detail", pk=payment.loan.pk)
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = LoanPaymentForm()
    
    context = {
        'form': form,
        'title': 'Record Loan Payment',
    }
    return render(request, 'loans/payments/form.html', context)


@login_required
def loan_payment_detail(request, pk):
    """View payment details"""
    payment = get_object_or_404(
        LoanPayment.objects.select_related(
            'loan',
            'loan__member',
            'loan__loan_product',
            'payment_method_ref',
            'financial_period'
        ),
        pk=pk
    )
    
    context = {
        'payment': payment,
    }
    
    return render(request, 'loans/payments/detail.html', context)

# =============================================================================
# LOAN GUARANTOR VIEWS
# =============================================================================

@login_required
def loan_guarantor_list(request):
    """List all loan guarantors - HTMX loads data on page load"""
    
    # Get initial stats from stats.py
    try:
        stats = loan_stats.get_guarantor_statistics()
    except Exception as e:
        logger.error(f"Error getting guarantor statistics: {e}")
        stats = {}
    
    context = {
        'stats': stats,
    }
    return render(request, 'loans/guarantors/list.html', context)


@login_required
def loan_guarantor_create(request, application_pk):
    """Add guarantor to loan application"""
    application = get_object_or_404(LoanApplication, pk=application_pk)
    
    if request.method == "POST":
        form = LoanGuarantorForm(request.POST)
        if form.is_valid():
            guarantor = form.save()
            messages.success(
                request,
                f"Guarantor {guarantor.guarantor.get_full_name()} was added successfully",
                extra_tags='sweetalert'
            )
            return redirect("loans:application_detail", pk=application.pk)
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = LoanGuarantorForm(initial={'loan_application': application})
    
    context = {
        'form': form,
        'application': application,
        'title': 'Add Guarantor',
    }
    return render(request, 'loans/guarantors/form.html', context)

# =============================================================================
# LOAN COLLATERAL VIEWS
# =============================================================================

@login_required
def loan_collateral_list(request):
    """List all loan collateral - HTMX loads data on page load"""
    
    # Get initial stats from stats.py
    try:
        stats = loan_stats.get_collateral_statistics()
    except Exception as e:
        logger.error(f"Error getting collateral statistics: {e}")
        stats = {}
    
    context = {
        'stats': stats,
    }
    return render(request, 'loans/collaterals/list.html', context)


@login_required
def loan_collateral_create(request, application_pk):
    """Add collateral to loan application"""
    application = get_object_or_404(LoanApplication, pk=application_pk)
    
    if request.method == "POST":
        form = LoanCollateralForm(request.POST, request.FILES)
        if form.is_valid():
            collateral = form.save()
            messages.success(
                request,
                f"Collateral '{collateral.get_collateral_type_display()}' was added successfully",
                extra_tags='sweetalert'
            )
            return redirect("loans:application_detail", pk=application.pk)
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = LoanCollateralForm(initial={'loan_application': application})
    
    context = {
        'form': form,
        'application': application,
        'title': 'Add Collateral',
    }
    return render(request, 'loans/collaterals/form.html', context)


@login_required
def loan_collateral_detail(request, pk):
    """View collateral details"""
    collateral = get_object_or_404(
        LoanCollateral.objects.select_related(
            'loan_application',
            'loan_application__member'
        ),
        pk=pk
    )
    
    context = {
        'collateral': collateral,
    }
    
    return render(request, 'loans/collaterals/detail.html', context)

# =============================================================================
# LOAN SCHEDULE VIEWS
# =============================================================================

@login_required
def loan_schedule_list(request):
    """List all loan schedules - HTMX loads data on page load"""
    
    # Get initial stats from stats.py
    try:
        stats = loan_stats.get_schedule_statistics()
    except Exception as e:
        logger.error(f"Error getting schedule statistics: {e}")
        stats = {}
    
    context = {
        'stats': stats,
    }
    return render(request, 'loans/schedules/list.html', context)


@login_required
def loan_schedule_detail(request, loan_pk):
    """View complete repayment schedule for a loan"""
    loan = get_object_or_404(Loan, pk=loan_pk)
    
    schedule = loan.schedule.select_related('financial_period').order_by('installment_number')
    
    # Calculate summary
    schedule_summary = schedule.aggregate(
        total_installments=Count('id'),
        total_due=Sum('total_amount'),
        total_paid=Sum('paid_amount'),
        total_balance=Sum('balance'),
        paid_count=Count('id', filter=Q(status='PAID')),
        pending_count=Count('id', filter=Q(status='PENDING')),
        overdue_count=Count('id', filter=Q(status='OVERDUE'))
    )
    
    context = {
        'loan': loan,
        'schedule': schedule,
        'summary': schedule_summary,
    }
    
    return render(request, 'loans/schedules/detail.html', context)


# =============================================================================
# LOAN DOCUMENT VIEWS
# =============================================================================

@login_required
def loan_document_create(request, application_pk=None, loan_pk=None):
    """Upload loan document"""
    
    application = None
    loan = None
    
    if application_pk:
        application = get_object_or_404(LoanApplication, pk=application_pk)
    elif loan_pk:
        loan = get_object_or_404(Loan, pk=loan_pk)
    else:
        messages.error(
            request,
            "Invalid request - no application or loan specified",
            extra_tags='sweetalert'
        )
        return redirect("loans:dashboard")
    
    if request.method == "POST":
        form = LoanDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save()
            messages.success(
                request,
                f"Document '{document.title}' was uploaded successfully",
                extra_tags='sweetalert'
            )
            
            if application:
                return redirect("loans:application_detail", pk=application.pk)
            else:
                return redirect("loans:loan_detail", pk=loan.pk)
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        initial = {}
        if application:
            initial['application'] = application
        if loan:
            initial['loan'] = loan
        
        form = LoanDocumentForm(initial=initial)
    
    context = {
        'form': form,
        'application': application,
        'loan': loan,
        'title': 'Upload Document',
    }
    return render(request, 'loans/documents/form.html', context)

# =============================================================================
# BULK OPERATIONS
# =============================================================================

@login_required
def bulk_loan_disbursement(request):
    """Bulk disburse approved loan applications"""
    
    if request.method == "POST":
        form = BulkLoanDisbursementForm(request.POST)
        if form.is_valid():
            disbursement_date = form.cleaned_data['disbursement_date']
            loan_product = form.cleaned_data.get('loan_product')
            
            # Get approved applications
            applications = LoanApplication.objects.filter(status='APPROVED')
            
            if loan_product:
                applications = applications.filter(loan_product=loan_product)
            
            if not applications.exists():
                messages.warning(
                    request,
                    "No approved applications found for disbursement",
                    extra_tags='sweetalert'
                )
                return redirect("loans:loan_list")
            
            disbursed_count = 0
            failed_count = 0
            
            for application in applications:
                try:
                    # Create loan from application
                    loan = Loan.objects.create(
                        member=application.member,
                        loan_product=application.loan_product,
                        application=application,
                        principal_amount=application.approved_amount or application.amount_requested,
                        interest_rate=application.approved_interest_rate or application.loan_product.interest_rate,
                        term_months=application.approved_term or application.term_months,
                        payment_frequency=application.loan_product.repayment_cycle,
                        disbursement_date=disbursement_date,
                        first_payment_date=disbursement_date + timedelta(days=30),
                        expected_end_date=disbursement_date + timedelta(
                            days=30 * (application.approved_term or application.term_months)
                        ),
                    )
                    
                    # Update application status
                    application.status = 'DISBURSED'
                    application.save()
                    
                    disbursed_count += 1
                
                except Exception as e:
                    logger.error(f"Error disbursing application {application.application_number}: {e}")
                    failed_count += 1
                    continue
            
            if disbursed_count > 0:
                messages.success(
                    request,
                    f"Successfully disbursed {disbursed_count} loan(s)" + 
                    (f". {failed_count} failed." if failed_count > 0 else ""),
                    extra_tags='sweetalert'
                )
            else:
                messages.error(
                    request,
                    f"Failed to disburse any loans. {failed_count} error(s) occurred.",
                    extra_tags='sweetalert'
                )
            
            return redirect("loans:loan_list")
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = BulkLoanDisbursementForm()
    
    context = {
        'form': form,
        'title': 'Bulk Loan Disbursement',
    }
    return render(request, 'loans/bulk_operations/disburse_form.html', context)


# =============================================================================
# REPORTS
# =============================================================================

@login_required
def loan_reports(request):
    """Generate loan reports - USES stats.py"""
    
    if request.method == "POST":
        form = LoanReportForm(request.POST)
        if form.is_valid():
            report_type = form.cleaned_data['report_type']
            start_date = form.cleaned_data.get('start_date')
            end_date = form.cleaned_data.get('end_date')
            loan_product = form.cleaned_data.get('loan_product')
            report_format = form.cleaned_data.get('format')
            
            # Use stats.py functions based on report type
            try:
                filters = {}
                if start_date:
                    filters['date_from'] = start_date
                if end_date:
                    filters['date_to'] = end_date
                if loan_product:
                    filters['product_id'] = str(loan_product.id)
                
                if report_type == 'PORTFOLIO_SUMMARY':
                    data = loan_stats.get_loan_overview(start_date, end_date)
                elif report_type == 'DISBURSEMENT_REPORT':
                    data = loan_stats.get_loan_statistics(filters)
                elif report_type == 'REPAYMENT_REPORT':
                    data = loan_stats.get_payment_statistics(filters)
                elif report_type == 'ARREARS_REPORT':
                    filters['is_overdue'] = True
                    data = loan_stats.get_loan_statistics(filters)
                elif report_type == 'PRODUCT_PERFORMANCE':
                    if loan_product:
                        data = loan_stats.get_product_performance_breakdown(str(loan_product.id))
                    else:
                        data = loan_stats.get_product_statistics()
                elif report_type == 'DEFAULTERS':
                    filters['status'] = 'DEFAULTED'
                    data = loan_stats.get_loan_statistics(filters)
                else:
                    data = {}
                
                # For now, just display the data
                # TODO: Implement PDF/Excel/CSV export
                context = {
                    'report_type': report_type,
                    'report_data': data,
                    'start_date': start_date,
                    'end_date': end_date,
                    'loan_product': loan_product,
                    'format': report_format,
                }
                
                return render(request, 'loans/reports/report_view.html', context)
                
            except Exception as e:
                logger.error(f"Error generating report: {e}")
                messages.error(
                    request,
                    f"Error generating report: {str(e)}",
                    extra_tags='sweetalert'
                )
                return redirect("loans:reports")
        else:
            messages.error(
                request,
                "Please correct the errors in the form",
                extra_tags='sweetalert-error'
            )
    else:
        form = LoanReportForm()
    
    context = {
        'form': form,
        'title': 'Generate Loan Reports',
    }
    return render(request, 'loans/reports/form.html', context)