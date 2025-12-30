# core/views.py

"""
View functions for the core app.
Provides views for SACCO configuration, financial settings, fiscal years, periods, 
payment methods, tax rates, and units of measure with print preview functionality.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Count, Sum, Avg, Prefetch, F, Case, When
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, date, timedelta
from decimal import Decimal
import logging

from .forms import (
    SaccoConfigurationForm,
    FinancialSettingsForm,
    FiscalYearForm,
    FiscalYearFilterForm,
    FiscalPeriodForm,
    FiscalPeriodFilterForm,
    PaymentMethodForm,
    PaymentMethodFilterForm,
    TaxRateForm,
    TaxRateFilterForm,
    UnitOfMeasureForm,
    UnitOfMeasureFilterForm,
)
from .models import (
    SaccoConfiguration,
    FinancialSettings,
    FiscalYear,
    FiscalPeriod,
    PaymentMethod,
    TaxRate,
    UnitOfMeasure,
)
from .stats import (
    get_fiscal_year_statistics,
    get_fiscal_year_detail_stats,
    get_period_statistics,
    get_period_detail_stats,
    get_payment_method_statistics,
    get_payment_method_detail_stats,
    get_tax_rate_statistics,
    get_tax_rate_detail_stats,
    get_unit_of_measure_statistics,
    get_sacco_configuration_stats,
    get_financial_settings_stats,
    get_comprehensive_core_statistics,
)
from core.utils import paginate_queryset, parse_filters

logger = logging.getLogger(__name__)


# =============================================================================
# DASHBOARD
# =============================================================================

@login_required
def core_dashboard(request):
    """Core Settings Dashboard with comprehensive statistics"""
    try:
        # Get comprehensive statistics
        stats = get_comprehensive_core_statistics()
        
        # Get current fiscal year and period
        current_fy = FiscalYear.get_active_fiscal_year()
        current_period = FiscalPeriod.get_active_period()
        
        # Get today's date
        today = timezone.now().date()
        
        # Upcoming period transitions
        upcoming_periods = FiscalPeriod.objects.filter(
            start_date__gt=today,
            start_date__lte=today + timedelta(days=30),
            status='DRAFT'
        ).select_related('fiscal_year').order_by('start_date')[:5]
        
        # Recently closed periods
        recently_closed = FiscalPeriod.objects.filter(
            is_closed=True
        ).select_related('fiscal_year').order_by('-closed_at')[:5]
        
        # Active payment methods
        active_payment_methods = PaymentMethod.objects.filter(
            is_active=True
        ).order_by('display_order', 'name')[:10]
        
        # Periods expiring soon
        expiring_periods = FiscalPeriod.objects.filter(
            end_date__gt=today,
            end_date__lte=today + timedelta(days=14),
            status='ACTIVE'
        ).select_related('fiscal_year').order_by('end_date')[:5]
        
        # Recent fiscal years
        recent_fiscal_years = FiscalYear.objects.all().order_by('-start_date')[:5]
        
        # Configuration status
        financial_settings = FinancialSettings.get_instance()
        sacco_config = SaccoConfiguration.get_instance()
        
        context = {
            'stats': stats,
            'current_fy': current_fy,
            'current_period': current_period,
            'upcoming_periods': upcoming_periods,
            'recently_closed': recently_closed,
            'active_payment_methods': active_payment_methods,
            'expiring_periods': expiring_periods,
            'recent_fiscal_years': recent_fiscal_years,
            'financial_settings': financial_settings,
            'sacco_config': sacco_config,
        }
        
        return render(request, 'home.html', context)
        
    except Exception as e:
        logger.error(f"Error loading core dashboard: {e}")
        messages.error(request, "Error loading dashboard data")
        return render(request, 'home.html', {})


# =============================================================================
# SACCO CONFIGURATION VIEWS
# =============================================================================

@login_required
def sacco_configuration_view(request):
    """View and edit SACCO configuration"""
    config = SaccoConfiguration.get_instance()
    
    if request.method == "POST":
        form = SaccoConfigurationForm(request.POST, instance=config)
        if form.is_valid():
            config = form.save()
            # Clear cache after update
            SaccoConfiguration.clear_cache()
            messages.success(request, "SACCO configuration updated successfully")
            return redirect("core:sacco_configuration")
    else:
        form = SaccoConfigurationForm(instance=config)
    
    # Get configuration stats
    config_stats = get_sacco_configuration_stats()
    
    context = {
        'form': form,
        'config': config,
        'config_stats': config_stats,
        'title': 'SACCO Configuration',
    }
    return render(request, 'sacco_configuration.html', context)


# =============================================================================
# FINANCIAL SETTINGS VIEWS
# =============================================================================

@login_required
def financial_settings_view(request):
    """View and edit financial settings"""
    settings = FinancialSettings.get_instance()
    
    if request.method == "POST":
        form = FinancialSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            settings = form.save()
            messages.success(request, "Financial settings updated successfully")
            return redirect("core:financial_settings")
    else:
        form = FinancialSettingsForm(instance=settings)
    
    # Get financial settings stats
    settings_stats = get_financial_settings_stats()
    
    context = {
        'form': form,
        'settings': settings,
        'settings_stats': settings_stats,
        'title': 'Financial Settings',
    }
    return render(request, 'financial_settings.html', context)


# =============================================================================
# FISCAL YEAR VIEWS
# =============================================================================

@login_required
def fiscal_year_list(request):
    """List all fiscal years with filtering and statistics"""
    
    # Build queryset
    fiscal_years = FiscalYear.objects.all().prefetch_related('periods').order_by('-start_date')
    
    # Apply filters
    filter_form = FiscalYearFilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('status'):
            fiscal_years = fiscal_years.filter(status=filter_form.cleaned_data['status'])
        
        if filter_form.cleaned_data.get('is_active') is not None:
            fiscal_years = fiscal_years.filter(is_active=filter_form.cleaned_data['is_active'])
        
        if filter_form.cleaned_data.get('is_closed') is not None:
            fiscal_years = fiscal_years.filter(is_closed=filter_form.cleaned_data['is_closed'])
        
        if filter_form.cleaned_data.get('is_locked') is not None:
            fiscal_years = fiscal_years.filter(is_locked=filter_form.cleaned_data['is_locked'])
        
        if filter_form.cleaned_data.get('date_from'):
            fiscal_years = fiscal_years.filter(start_date__gte=filter_form.cleaned_data['date_from'])
        
        if filter_form.cleaned_data.get('date_to'):
            fiscal_years = fiscal_years.filter(start_date__lte=filter_form.cleaned_data['date_to'])
    
    # Paginate
    fiscal_years_page, paginator = paginate_queryset(request, fiscal_years, per_page=20)
    
    # Get statistics
    fy_stats = get_fiscal_year_statistics()
    
    context = {
        'fiscal_years': fiscal_years_page,
        'filter_form': filter_form,
        'fy_stats': fy_stats,
        'title': 'Fiscal Years',
    }
    
    return render(request, 'fiscal_years/list.html', context)


@login_required
def fiscal_year_create(request):
    """Create a new fiscal year"""
    if request.method == "POST":
        form = FiscalYearForm(request.POST)
        if form.is_valid():
            fiscal_year = form.save()
            messages.success(request, f"Fiscal year '{fiscal_year.name}' was created successfully")
            return redirect("core:fiscal_year_detail", pk=fiscal_year.pk)
    else:
        form = FiscalYearForm()
    
    context = {
        'form': form,
        'title': 'Create Fiscal Year',
    }
    return render(request, 'fiscal_years/form.html', context)


@login_required
def fiscal_year_detail(request, pk):
    """View fiscal year details"""
    fiscal_year = get_object_or_404(
        FiscalYear.objects.prefetch_related('periods'),
        pk=pk
    )
    
    # Get detailed stats
    detail_stats = get_fiscal_year_detail_stats(pk)
    
    # Get periods for this fiscal year
    periods = fiscal_year.periods.all().order_by('period_number')
    
    context = {
        'fiscal_year': fiscal_year,
        'detail_stats': detail_stats,
        'periods': periods,
        'title': f'Fiscal Year: {fiscal_year.name}',
    }
    
    return render(request, 'fiscal_years/detail.html', context)


@login_required
def fiscal_year_edit(request, pk):
    """Edit existing fiscal year"""
    fiscal_year = get_object_or_404(FiscalYear, pk=pk)
    
    # Prevent editing locked fiscal years
    if fiscal_year.is_locked:
        messages.error(request, "Cannot edit a locked fiscal year")
        return redirect("core:fiscal_year_detail", pk=pk)
    
    if request.method == "POST":
        form = FiscalYearForm(request.POST, instance=fiscal_year)
        if form.is_valid():
            fiscal_year = form.save()
            messages.success(request, f"Fiscal year '{fiscal_year.name}' was updated successfully")
            return redirect("core:fiscal_year_detail", pk=fiscal_year.pk)
    else:
        form = FiscalYearForm(instance=fiscal_year)
    
    context = {
        'form': form,
        'fiscal_year': fiscal_year,
        'title': f'Edit Fiscal Year: {fiscal_year.name}',
    }
    return render(request, 'fiscal_years/form.html', context)


@login_required
def fiscal_year_delete(request, pk):
    """Delete a fiscal year"""
    fiscal_year = get_object_or_404(FiscalYear, pk=pk)
    
    # Prevent deleting closed or locked fiscal years
    if fiscal_year.is_closed or fiscal_year.is_locked:
        messages.error(request, "Cannot delete a closed or locked fiscal year")
        return redirect("core:fiscal_year_list")
    
    # Check if it can be deleted
    if not fiscal_year.can_be_deleted():
        messages.error(request, "Cannot delete fiscal year - it contains periods or transactions")
        return redirect("core:fiscal_year_list")
    
    if request.method == "POST":
        fiscal_year_name = fiscal_year.name
        fiscal_year.delete()
        messages.success(request, f"Fiscal year '{fiscal_year_name}' was deleted successfully")
        return redirect("core:fiscal_year_list")
    
    return redirect("core:fiscal_year_list")


@login_required
def fiscal_year_print_view(request):
    """Generate printable fiscal year list with selected fields"""
    
    # Get selected fields from the modal
    selected_fields = request.GET.getlist('fields')
    if not selected_fields:
        # Default fields if none selected
        selected_fields = ['name', 'code', 'start_date', 'end_date', 'status', 'is_active', 'period_count']
    
    # Get additional options
    include_stats = request.GET.get('include_stats') == 'true'
    landscape = request.GET.get('landscape') == 'true'
    
    # Get filter parameters from URL
    status = request.GET.get('status', '')
    is_active = request.GET.get('is_active', '')
    is_closed = request.GET.get('is_closed', '')
    is_locked = request.GET.get('is_locked', '')
    
    # Build queryset
    fiscal_years = FiscalYear.objects.prefetch_related('periods').order_by('-start_date')
    
    # Apply filters (same as fiscal_year_list)
    if status:
        fiscal_years = fiscal_years.filter(status=status)
    
    if is_active:
        fiscal_years = fiscal_years.filter(is_active=(is_active == 'true'))
    
    if is_closed:
        fiscal_years = fiscal_years.filter(is_closed=(is_closed == 'true'))
    
    if is_locked:
        fiscal_years = fiscal_years.filter(is_locked=(is_locked == 'true'))
    
    # Calculate stats only if requested
    stats = None
    if include_stats:
        stats = get_fiscal_year_statistics()
    
    # Field display names mapping
    field_names = {
        'name': 'Fiscal Year Name',
        'code': 'Code',
        'start_date': 'Start Date',
        'end_date': 'End Date',
        'status': 'Status',
        'is_active': 'Active',
        'is_closed': 'Closed',
        'is_locked': 'Locked',
        'period_count': 'Periods',
        'duration_days': 'Duration (Days)',
        'description': 'Description',
    }
    
    # Create ordered list of field display names for template
    selected_field_names = [field_names.get(field, field.replace('_', ' ').title()) for field in selected_fields]
    
    context = {
        'fiscal_years': fiscal_years,
        'stats': stats,
        'now': timezone.now(),
        'selected_fields': selected_fields,
        'selected_field_names': selected_field_names,
        'field_names': field_names,
        'landscape': landscape,
    }
    
    return render(request, 'fiscal_years/print.html', context)


# =============================================================================
# FISCAL PERIOD VIEWS
# =============================================================================

@login_required
def period_list(request):
    """List all fiscal periods with filtering and statistics"""
    
    # Build queryset
    periods = FiscalPeriod.objects.all().select_related('fiscal_year').order_by('-fiscal_year__start_date', 'period_number')
    
    # Apply filters
    filter_form = FiscalPeriodFilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('fiscal_year'):
            periods = periods.filter(fiscal_year=filter_form.cleaned_data['fiscal_year'])
        
        if filter_form.cleaned_data.get('status'):
            periods = periods.filter(status=filter_form.cleaned_data['status'])
        
        if filter_form.cleaned_data.get('is_active') is not None:
            periods = periods.filter(is_active=filter_form.cleaned_data['is_active'])
        
        if filter_form.cleaned_data.get('is_closed') is not None:
            periods = periods.filter(is_closed=filter_form.cleaned_data['is_closed'])
        
        if filter_form.cleaned_data.get('is_locked') is not None:
            periods = periods.filter(is_locked=filter_form.cleaned_data['is_locked'])
        
        if filter_form.cleaned_data.get('min_period_number'):
            periods = periods.filter(period_number__gte=filter_form.cleaned_data['min_period_number'])
        
        if filter_form.cleaned_data.get('max_period_number'):
            periods = periods.filter(period_number__lte=filter_form.cleaned_data['max_period_number'])
        
        if filter_form.cleaned_data.get('date_from'):
            periods = periods.filter(start_date__gte=filter_form.cleaned_data['date_from'])
        
        if filter_form.cleaned_data.get('date_to'):
            periods = periods.filter(start_date__lte=filter_form.cleaned_data['date_to'])
    
    # Paginate
    periods_page, paginator = paginate_queryset(request, periods, per_page=20)
    
    # Get statistics
    period_stats = get_period_statistics()
    
    context = {
        'periods': periods_page,
        'filter_form': filter_form,
        'period_stats': period_stats,
        'title': 'Fiscal Periods',
    }
    
    return render(request, 'core/periods/list.html', context)


@login_required
def period_create(request, fiscal_year_pk=None):
    """Create a new fiscal period"""
    fiscal_year = None
    if fiscal_year_pk:
        fiscal_year = get_object_or_404(FiscalYear, pk=fiscal_year_pk)
        
        if fiscal_year.is_locked:
            messages.error(request, "Cannot add periods to a locked fiscal year")
            return redirect("core:fiscal_year_detail", pk=fiscal_year_pk)
    
    if request.method == "POST":
        form = FiscalPeriodForm(request.POST)
        if form.is_valid():
            period = form.save()
            messages.success(request, f"Period '{period.name}' was created successfully")
            return redirect("core:period_detail", pk=period.pk)
    else:
        initial = {}
        if fiscal_year:
            initial['fiscal_year'] = fiscal_year
        form = FiscalPeriodForm(initial=initial)
    
    context = {
        'form': form,
        'fiscal_year': fiscal_year,
        'title': 'Create Fiscal Period',
    }
    return render(request, 'core/periods/form.html', context)


@login_required
def period_detail(request, pk):
    """View period details"""
    period = get_object_or_404(
        FiscalPeriod.objects.select_related('fiscal_year'),
        pk=pk
    )
    
    # Get detailed stats
    detail_stats = get_period_detail_stats(pk)
    
    context = {
        'period': period,
        'detail_stats': detail_stats,
        'title': f'Period: {period.name}',
    }
    
    return render(request, 'core/periods/detail.html', context)


@login_required
def period_edit(request, pk):
    """Edit existing fiscal period"""
    period = get_object_or_404(FiscalPeriod, pk=pk)
    
    # Prevent editing locked periods
    if period.is_locked:
        messages.error(request, "Cannot edit a locked period")
        return redirect("core:period_detail", pk=pk)
    
    if request.method == "POST":
        form = FiscalPeriodForm(request.POST, instance=period)
        if form.is_valid():
            period = form.save()
            messages.success(request, f"Period '{period.name}' was updated successfully")
            return redirect("core:period_detail", pk=period.pk)
    else:
        form = FiscalPeriodForm(instance=period)
    
    context = {
        'form': form,
        'period': period,
        'title': f'Edit Period: {period.name}',
    }
    return render(request, 'core/periods/form.html', context)


@login_required
def period_delete(request, pk):
    """Delete a period"""
    period = get_object_or_404(FiscalPeriod, pk=pk)
    
    # Prevent deleting closed or locked periods
    if period.is_closed or period.is_locked:
        messages.error(request, "Cannot delete a closed or locked period")
        return redirect("core:period_list")
    
    # Check if it can be deleted
    if not period.can_be_deleted():
        messages.error(request, "Cannot delete period - it contains transactions")
        return redirect("core:period_list")
    
    if request.method == "POST":
        period_name = period.name
        period.delete()
        messages.success(request, f"Period '{period_name}' was deleted successfully")
        return redirect("core:period_list")
    
    return redirect("core:period_list")


@login_required
def period_print_view(request):
    """Generate printable period list with selected fields"""
    
    # Get selected fields from the modal
    selected_fields = request.GET.getlist('fields')
    if not selected_fields:
        # Default fields if none selected
        selected_fields = ['fiscal_year', 'name', 'period_number', 'start_date', 'end_date', 'status', 'is_active']
    
    # Get additional options
    include_stats = request.GET.get('include_stats') == 'true'
    landscape = request.GET.get('landscape') == 'true'
    
    # Get filter parameters from URL
    fiscal_year_id = request.GET.get('fiscal_year', '')
    status = request.GET.get('status', '')
    is_active = request.GET.get('is_active', '')
    is_closed = request.GET.get('is_closed', '')
    
    # Build queryset
    periods = FiscalPeriod.objects.select_related('fiscal_year').order_by('-fiscal_year__start_date', 'period_number')
    
    # Apply filters
    if fiscal_year_id:
        periods = periods.filter(fiscal_year_id=fiscal_year_id)
    
    if status:
        periods = periods.filter(status=status)
    
    if is_active:
        periods = periods.filter(is_active=(is_active == 'true'))
    
    if is_closed:
        periods = periods.filter(is_closed=(is_closed == 'true'))
    
    # Calculate stats only if requested
    stats = None
    if include_stats:
        stats = get_period_statistics()
    
    # Field display names mapping
    field_names = {
        'fiscal_year': 'Fiscal Year',
        'name': 'Period Name',
        'period_number': 'Period Number',
        'start_date': 'Start Date',
        'end_date': 'End Date',
        'status': 'Status',
        'is_active': 'Active',
        'is_closed': 'Closed',
        'is_locked': 'Locked',
        'duration_days': 'Duration (Days)',
        'description': 'Description',
    }
    
    # Create ordered list of field display names for template
    selected_field_names = [field_names.get(field, field.replace('_', ' ').title()) for field in selected_fields]
    
    context = {
        'periods': periods,
        'stats': stats,
        'now': timezone.now(),
        'selected_fields': selected_fields,
        'selected_field_names': selected_field_names,
        'field_names': field_names,
        'landscape': landscape,
    }
    
    return render(request, 'core/periods/print.html', context)

@login_required
@require_http_methods(["GET", "POST"])
def fiscal_year_modal(request, pk=None):
    """Handle fiscal year modal - HTMX version"""
    fiscal_year_id = pk or request.GET.get('id')
    fiscal_year = None
    
    if fiscal_year_id:
        fiscal_year = get_object_or_404(FiscalYear, pk=fiscal_year_id)
        if fiscal_year.is_locked and request.method == 'POST':
            return HttpResponse('<div class="alert alert-danger">Cannot edit locked fiscal year</div>', status=403)
    
    if request.method == "POST":
        form = FiscalYearForm(request.POST, instance=fiscal_year)
        if form.is_valid():
            fy = form.save()
            messages.success(request, f"Fiscal year '{fy.name}' {'updated' if fiscal_year_id else 'created'} successfully")
            # Return empty response - HTMX will trigger page reload
            return HttpResponse(status=204)
        else:
            # Return form with errors
            context = {'form': form, 'fiscal_year': fiscal_year}
            return render(request, 'fiscal_years/modals/_fiscal_year_modal.html', context)
    
    # GET request - return form HTML
    form = FiscalYearForm(instance=fiscal_year)
    context = {'form': form, 'fiscal_year': fiscal_year}
    return render(request, 'fiscal_years/modals/_fiscal_year_modal.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def period_modal(request, pk=None):
    """Handle period modal - HTMX version"""
    period_id = pk or request.GET.get('id')
    fiscal_year_id = request.GET.get('fiscal_year_id')
    period = None
    
    if period_id:
        period = get_object_or_404(FiscalPeriod, pk=period_id)
        fiscal_year_id = period.fiscal_year.id
    
    if request.method == 'POST':
        form = FiscalPeriodForm(request.POST, instance=period)
        if form.is_valid():
            period = form.save(commit=False)
            if not period_id:
                period.created_by = request.user
            period.updated_by = request.user
            period.save()
            
            messages.success(request, f'Period "{period.name}" {"updated" if period_id else "created"} successfully!')
            # Return empty response - HTMX will trigger page reload
            return HttpResponse(status=204)
        else:
            # Return form with errors
            context = {
                'form': form,
                'period': period,
                'fiscal_year_id': fiscal_year_id,
            }
            return render(request, 'fiscal_years/modals/_fiscal_period_modal.html', context)
    else:
        # GET request - show form
        initial_data = {}
        if fiscal_year_id:
            initial_data['fiscal_year'] = fiscal_year_id
        
        form = FiscalPeriodForm(instance=period, initial=initial_data)
        context = {
            'form': form,
            'period': period,
            'fiscal_year_id': fiscal_year_id,
        }
        return render(request, 'fiscal_years/modals/_fiscal_period_modal.html', context)
    
# =============================================================================
# PAYMENT METHOD VIEWS
# =============================================================================

@login_required
def payment_method_list(request):
    """List all payment methods with filtering and statistics"""
    
    # Build queryset
    payment_methods = PaymentMethod.objects.all().order_by('display_order', 'name')
    
    # Apply filters
    filter_form = PaymentMethodFilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('method_type'):
            payment_methods = payment_methods.filter(method_type=filter_form.cleaned_data['method_type'])
        
        if filter_form.cleaned_data.get('mobile_money_provider'):
            payment_methods = payment_methods.filter(mobile_money_provider=filter_form.cleaned_data['mobile_money_provider'])
        
        if filter_form.cleaned_data.get('is_active') is not None:
            payment_methods = payment_methods.filter(is_active=filter_form.cleaned_data['is_active'])
        
        if filter_form.cleaned_data.get('is_default') is not None:
            payment_methods = payment_methods.filter(is_default=filter_form.cleaned_data['is_default'])
        
        if filter_form.cleaned_data.get('requires_approval') is not None:
            payment_methods = payment_methods.filter(requires_approval=filter_form.cleaned_data['requires_approval'])
        
        if filter_form.cleaned_data.get('has_transaction_fee') is not None:
            payment_methods = payment_methods.filter(has_transaction_fee=filter_form.cleaned_data['has_transaction_fee'])
    
    # Paginate
    payment_methods_page, paginator = paginate_queryset(request, payment_methods, per_page=20)
    
    # Get statistics
    pm_stats = get_payment_method_statistics()
    
    context = {
        'payment_methods': payment_methods_page,
        'filter_form': filter_form,
        'pm_stats': pm_stats,
        'title': 'Payment Methods',
    }
    
    return render(request, 'core/payment_methods/list.html', context)


@login_required
def payment_method_create(request):
    """Create a new payment method"""
    if request.method == "POST":
        form = PaymentMethodForm(request.POST)
        if form.is_valid():
            payment_method = form.save()
            messages.success(request, f"Payment method '{payment_method.name}' was created successfully")
            return redirect("core:payment_method_detail", pk=payment_method.pk)
    else:
        form = PaymentMethodForm()
    
    context = {
        'form': form,
        'title': 'Create Payment Method',
    }
    return render(request, 'core/payment_methods/form.html', context)


@login_required
def payment_method_detail(request, pk):
    """View payment method details"""
    payment_method = get_object_or_404(PaymentMethod, pk=pk)
    
    # Get detailed stats
    detail_stats = get_payment_method_detail_stats(pk)
    
    context = {
        'payment_method': payment_method,
        'detail_stats': detail_stats,
        'title': f'Payment Method: {payment_method.name}',
    }
    
    return render(request, 'core/payment_methods/detail.html', context)


@login_required
def payment_method_edit(request, pk):
    """Edit existing payment method"""
    payment_method = get_object_or_404(PaymentMethod, pk=pk)
    
    if request.method == "POST":
        form = PaymentMethodForm(request.POST, instance=payment_method)
        if form.is_valid():
            payment_method = form.save()
            messages.success(request, f"Payment method '{payment_method.name}' was updated successfully")
            return redirect("core:payment_method_detail", pk=payment_method.pk)
    else:
        form = PaymentMethodForm(instance=payment_method)
    
    context = {
        'form': form,
        'payment_method': payment_method,
        'title': f'Edit Payment Method: {payment_method.name}',
    }
    return render(request, 'core/payment_methods/form.html', context)


@login_required
def payment_method_delete(request, pk):
    """Delete a payment method"""
    payment_method = get_object_or_404(PaymentMethod, pk=pk)
    
    if request.method == "POST":
        payment_method_name = payment_method.name
        payment_method.delete()
        messages.success(request, f"Payment method '{payment_method_name}' was deleted successfully")
        return redirect("core:payment_method_list")
    
    return redirect("core:payment_method_list")


@login_required
def payment_method_print_view(request):
    """Generate printable payment method list with selected fields"""
    
    # Get selected fields from the modal
    selected_fields = request.GET.getlist('fields')
    if not selected_fields:
        # Default fields if none selected
        selected_fields = ['name', 'code', 'method_type', 'is_active', 'requires_approval', 'has_transaction_fee']
    
    # Get additional options
    include_stats = request.GET.get('include_stats') == 'true'
    landscape = request.GET.get('landscape') == 'true'
    
    # Get filter parameters from URL
    method_type = request.GET.get('method_type', '')
    is_active = request.GET.get('is_active', '')
    has_transaction_fee = request.GET.get('has_transaction_fee', '')
    
    # Build queryset
    payment_methods = PaymentMethod.objects.all().order_by('display_order', 'name')
    
    # Apply filters
    if method_type:
        payment_methods = payment_methods.filter(method_type=method_type)
    
    if is_active:
        payment_methods = payment_methods.filter(is_active=(is_active == 'true'))
    
    if has_transaction_fee:
        payment_methods = payment_methods.filter(has_transaction_fee=(has_transaction_fee == 'true'))
    
    # Calculate stats only if requested
    stats = None
    if include_stats:
        stats = get_payment_method_statistics()
    
    # Field display names mapping
    field_names = {
        'name': 'Payment Method',
        'code': 'Code',
        'method_type': 'Type',
        'mobile_money_provider': 'Provider',
        'bank_name': 'Bank',
        'is_active': 'Active',
        'is_default': 'Default',
        'requires_approval': 'Requires Approval',
        'has_transaction_fee': 'Has Fee',
        'transaction_fee_type': 'Fee Type',
        'processing_time': 'Processing Time',
        'minimum_amount': 'Min Amount',
        'maximum_amount': 'Max Amount',
    }
    
    # Create ordered list of field display names for template
    selected_field_names = [field_names.get(field, field.replace('_', ' ').title()) for field in selected_fields]
    
    context = {
        'payment_methods': payment_methods,
        'stats': stats,
        'now': timezone.now(),
        'selected_fields': selected_fields,
        'selected_field_names': selected_field_names,
        'field_names': field_names,
        'landscape': landscape,
    }
    
    return render(request, 'core/payment_methods/print.html', context)


# =============================================================================
# TAX RATE VIEWS
# =============================================================================

@login_required
def tax_rate_list(request):
    """List all tax rates with filtering and statistics"""
    
    # Build queryset
    tax_rates = TaxRate.objects.all().order_by('tax_type', '-effective_from')
    
    # Apply filters
    filter_form = TaxRateFilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('tax_type'):
            tax_rates = tax_rates.filter(tax_type=filter_form.cleaned_data['tax_type'])
        
        if filter_form.cleaned_data.get('is_active') is not None:
            tax_rates = tax_rates.filter(is_active=filter_form.cleaned_data['is_active'])
        
        if filter_form.cleaned_data.get('applies_to_members') is not None:
            tax_rates = tax_rates.filter(applies_to_members=filter_form.cleaned_data['applies_to_members'])
        
        if filter_form.cleaned_data.get('applies_to_sacco') is not None:
            tax_rates = tax_rates.filter(applies_to_sacco=filter_form.cleaned_data['applies_to_sacco'])
        
        if filter_form.cleaned_data.get('min_rate'):
            tax_rates = tax_rates.filter(rate__gte=filter_form.cleaned_data['min_rate'])
        
        if filter_form.cleaned_data.get('max_rate'):
            tax_rates = tax_rates.filter(rate__lte=filter_form.cleaned_data['max_rate'])
        
        if filter_form.cleaned_data.get('date_from'):
            tax_rates = tax_rates.filter(effective_from__gte=filter_form.cleaned_data['date_from'])
        
        if filter_form.cleaned_data.get('date_to'):
            tax_rates = tax_rates.filter(
                Q(effective_to__isnull=True) | Q(effective_to__lte=filter_form.cleaned_data['date_to'])
            )
    
    # Paginate
    tax_rates_page, paginator = paginate_queryset(request, tax_rates, per_page=20)
    
    # Get statistics
    tax_stats = get_tax_rate_statistics()
    
    context = {
        'tax_rates': tax_rates_page,
        'filter_form': filter_form,
        'tax_stats': tax_stats,
        'title': 'Tax Rates',
    }
    
    return render(request, 'core/tax_rates/list.html', context)


@login_required
def tax_rate_create(request):
    """Create a new tax rate"""
    if request.method == "POST":
        form = TaxRateForm(request.POST)
        if form.is_valid():
            tax_rate = form.save()
            messages.success(request, f"Tax rate '{tax_rate.name}' was created successfully")
            return redirect("core:tax_rate_detail", pk=tax_rate.pk)
    else:
        form = TaxRateForm()
    
    context = {
        'form': form,
        'title': 'Create Tax Rate',
    }
    return render(request, 'core/tax_rates/form.html', context)


@login_required
def tax_rate_detail(request, pk):
    """View tax rate details"""
    tax_rate = get_object_or_404(TaxRate, pk=pk)
    
    # Get detailed stats
    detail_stats = get_tax_rate_detail_stats(pk)
    
    context = {
        'tax_rate': tax_rate,
        'detail_stats': detail_stats,
        'title': f'Tax Rate: {tax_rate.name}',
    }
    
    return render(request, 'core/tax_rates/detail.html', context)


@login_required
def tax_rate_edit(request, pk):
    """Edit existing tax rate"""
    tax_rate = get_object_or_404(TaxRate, pk=pk)
    
    if request.method == "POST":
        form = TaxRateForm(request.POST, instance=tax_rate)
        if form.is_valid():
            tax_rate = form.save()
            messages.success(request, f"Tax rate '{tax_rate.name}' was updated successfully")
            return redirect("core:tax_rate_detail", pk=tax_rate.pk)
    else:
        form = TaxRateForm(instance=tax_rate)
    
    context = {
        'form': form,
        'tax_rate': tax_rate,
        'title': f'Edit Tax Rate: {tax_rate.name}',
    }
    return render(request, 'core/tax_rates/form.html', context)


@login_required
def tax_rate_delete(request, pk):
    """Delete a tax rate"""
    tax_rate = get_object_or_404(TaxRate, pk=pk)
    
    if request.method == "POST":
        tax_rate_name = tax_rate.name
        tax_rate.delete()
        messages.success(request, f"Tax rate '{tax_rate_name}' was deleted successfully")
        return redirect("core:tax_rate_list")
    
    return redirect("core:tax_rate_list")


@login_required
def tax_rate_print_view(request):
    """Generate printable tax rate list with selected fields"""
    
    # Get selected fields from the modal
    selected_fields = request.GET.getlist('fields')
    if not selected_fields:
        # Default fields if none selected
        selected_fields = ['name', 'tax_type', 'rate', 'effective_from', 'effective_to', 'is_active']
    
    # Get additional options
    include_stats = request.GET.get('include_stats') == 'true'
    landscape = request.GET.get('landscape') == 'true'
    
    # Get filter parameters from URL
    tax_type = request.GET.get('tax_type', '')
    is_active = request.GET.get('is_active', '')
    
    # Build queryset
    tax_rates = TaxRate.objects.all().order_by('tax_type', '-effective_from')
    
    # Apply filters
    if tax_type:
        tax_rates = tax_rates.filter(tax_type=tax_type)
    
    if is_active:
        tax_rates = tax_rates.filter(is_active=(is_active == 'true'))
    
    # Calculate stats only if requested
    stats = None
    if include_stats:
        stats = get_tax_rate_statistics()
    
    # Field display names mapping
    field_names = {
        'name': 'Tax Rate Name',
        'tax_type': 'Type',
        'rate': 'Rate (%)',
        'effective_from': 'Effective From',
        'effective_to': 'Effective To',
        'is_active': 'Active',
        'applies_to_members': 'Applies to Members',
        'applies_to_sacco': 'Applies to SACCO',
        'description': 'Description',
        'legal_reference': 'Legal Reference',
    }
    
    # Create ordered list of field display names for template
    selected_field_names = [field_names.get(field, field.replace('_', ' ').title()) for field in selected_fields]
    
    context = {
        'tax_rates': tax_rates,
        'stats': stats,
        'now': timezone.now(),
        'selected_fields': selected_fields,
        'selected_field_names': selected_field_names,
        'field_names': field_names,
        'landscape': landscape,
    }
    
    return render(request, 'core/tax_rates/print.html', context)


# =============================================================================
# UNIT OF MEASURE VIEWS
# =============================================================================

@login_required
def unit_of_measure_list(request):
    """List all units of measure with filtering and statistics"""
    
    # Build queryset
    units = UnitOfMeasure.objects.all().select_related('base_unit').order_by('uom_type', 'name')
    
    # Apply filters
    filter_form = UnitOfMeasureFilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('uom_type'):
            units = units.filter(uom_type=filter_form.cleaned_data['uom_type'])
        
        if filter_form.cleaned_data.get('base_unit'):
            units = units.filter(base_unit=filter_form.cleaned_data['base_unit'])
        
        if filter_form.cleaned_data.get('is_active') is not None:
            units = units.filter(is_active=filter_form.cleaned_data['is_active'])
        
        if filter_form.cleaned_data.get('has_base_unit') is not None:
            if filter_form.cleaned_data['has_base_unit']:
                units = units.filter(base_unit__isnull=False)
            else:
                units = units.filter(base_unit__isnull=True)
    
    # Paginate
    units_page, paginator = paginate_queryset(request, units, per_page=20)
    
    # Get statistics
    uom_stats = get_unit_of_measure_statistics()
    
    context = {
        'units': units_page,
        'filter_form': filter_form,
        'uom_stats': uom_stats,
        'title': 'Units of Measure',
    }
    
    return render(request, 'core/units_of_measure/list.html', context)


@login_required
def unit_of_measure_create(request):
    """Create a new unit of measure"""
    if request.method == "POST":
        form = UnitOfMeasureForm(request.POST)
        if form.is_valid():
            unit = form.save()
            messages.success(request, f"Unit of measure '{unit.name}' was created successfully")
            return redirect("core:unit_of_measure_detail", pk=unit.pk)
    else:
        form = UnitOfMeasureForm()
    
    context = {
        'form': form,
        'title': 'Create Unit of Measure',
    }
    return render(request, 'core/units_of_measure/form.html', context)


@login_required
def unit_of_measure_detail(request, pk):
    """View unit of measure details"""
    unit = get_object_or_404(UnitOfMeasure.objects.select_related('base_unit'), pk=pk)
    
    # Get related units (if this is a base unit)
    related_units = UnitOfMeasure.objects.filter(base_unit=unit).order_by('name')
    
    context = {
        'unit': unit,
        'related_units': related_units,
        'title': f'Unit of Measure: {unit.name}',
    }
    
    return render(request, 'core/units_of_measure/detail.html', context)


@login_required
def unit_of_measure_edit(request, pk):
    """Edit existing unit of measure"""
    unit = get_object_or_404(UnitOfMeasure, pk=pk)
    
    if request.method == "POST":
        form = UnitOfMeasureForm(request.POST, instance=unit)
        if form.is_valid():
            unit = form.save()
            messages.success(request, f"Unit of measure '{unit.name}' was updated successfully")
            return redirect("core:unit_of_measure_detail", pk=unit.pk)
    else:
        form = UnitOfMeasureForm(instance=unit)
    
    context = {
        'form': form,
        'unit': unit,
        'title': f'Edit Unit of Measure: {unit.name}',
    }
    return render(request, 'core/units_of_measure/form.html', context)


@login_required
def unit_of_measure_delete(request, pk):
    """Delete a unit of measure"""
    unit = get_object_or_404(UnitOfMeasure, pk=pk)
    
    if request.method == "POST":
        unit_name = unit.name
        unit.delete()
        messages.success(request, f"Unit of measure '{unit_name}' was deleted successfully")
        return redirect("core:unit_of_measure_list")
    
    return redirect("core:unit_of_measure_list")


@login_required
def unit_of_measure_print_view(request):
    """Generate printable unit of measure list with selected fields"""
    
    # Get selected fields from the modal
    selected_fields = request.GET.getlist('fields')
    if not selected_fields:
        # Default fields if none selected
        selected_fields = ['name', 'abbreviation', 'uom_type', 'base_unit', 'conversion_factor', 'is_active']
    
    # Get additional options
    include_stats = request.GET.get('include_stats') == 'true'
    landscape = request.GET.get('landscape') == 'true'
    
    # Get filter parameters from URL
    uom_type = request.GET.get('uom_type', '')
    is_active = request.GET.get('is_active', '')
    
    # Build queryset
    units = UnitOfMeasure.objects.select_related('base_unit').order_by('uom_type', 'name')
    
    # Apply filters
    if uom_type:
        units = units.filter(uom_type=uom_type)
    
    if is_active:
        units = units.filter(is_active=(is_active == 'true'))
    
    # Calculate stats only if requested
    stats = None
    if include_stats:
        stats = get_unit_of_measure_statistics()
    
    # Field display names mapping
    field_names = {
        'name': 'Name',
        'abbreviation': 'Abbreviation',
        'symbol': 'Symbol',
        'uom_type': 'Type',
        'base_unit': 'Base Unit',
        'conversion_factor': 'Conversion Factor',
        'is_active': 'Active',
        'description': 'Description',
    }
    
    # Create ordered list of field display names for template
    selected_field_names = [field_names.get(field, field.replace('_', ' ').title()) for field in selected_fields]
    
    context = {
        'units': units,
        'stats': stats,
        'now': timezone.now(),
        'selected_fields': selected_fields,
        'selected_field_names': selected_field_names,
        'field_names': field_names,
        'landscape': landscape,
    }
    
    return render(request, 'core/units_of_measure/print.html', context)