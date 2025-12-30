# core/modal_views.py

"""
Modal views for core app actions using centralized utilities from core.utils

All modal responses use the standardized create_sweetalert_response() helper
from core.utils, ensuring consistency across the entire application.

Includes modals for:
- Fiscal Year actions (activate, close, lock, unlock, delete)
- Fiscal Period actions (activate, close, lock, unlock, delete)
- Payment Method actions (activate, deactivate, set default, delete)
- Tax Rate actions (activate, deactivate, delete)
- Unit of Measure actions (activate, deactivate, delete)
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.utils import timezone

# Import the centralized response helpers
from core.utils import (
    create_sweetalert_response,
    create_success_response,
    create_error_response,
    create_warning_response,
    create_info_response,
    create_redirect_response
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

import logging
logger = logging.getLogger(__name__)


# =============================================================================
# FISCAL YEAR MODALS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def fiscal_year_activate_modal(request, pk):
    """Load fiscal year activation confirmation modal"""
    fiscal_year = get_object_or_404(FiscalYear, pk=pk)
    
    # Check if already active
    if fiscal_year.is_active:
        return render(request, 'core/fiscal_years/modals/already_active.html', {
            'fiscal_year': fiscal_year,
        })
    
    # Check if closed or locked
    if fiscal_year.is_closed or fiscal_year.is_locked:
        return render(request, 'core/fiscal_years/modals/cannot_activate.html', {
            'fiscal_year': fiscal_year,
            'reason': 'closed or locked'
        })
    
    # Get currently active fiscal year
    current_active = FiscalYear.get_active_fiscal_year()
    
    return render(request, 'core/fiscal_years/modals/activate_fiscal_year.html', {
        'fiscal_year': fiscal_year,
        'current_active': current_active,
    })


@login_required
@require_http_methods(["POST"])
def fiscal_year_activate_submit(request, pk):
    """Process fiscal year activation"""
    fiscal_year = get_object_or_404(FiscalYear, pk=pk)
    
    # Check if already active
    if fiscal_year.is_active:
        return create_warning_response(
            message=f"Fiscal year '{fiscal_year.name}' is already active",
            title='Already Active'
        )
    
    # Check if closed or locked
    if fiscal_year.is_closed or fiscal_year.is_locked:
        return create_error_response(
            message=f"Cannot activate a {'locked' if fiscal_year.is_locked else 'closed'} fiscal year",
            title='Cannot Activate'
        )
    
    # Activate fiscal year (this will deactivate others)
    fiscal_year.is_active = True
    fiscal_year.save()
    
    # Return updated fiscal year card
    fiscal_year.refresh_from_db()
    
    updated_html = render_to_string(
        'core/fiscal_years/_fiscal_year_card.html',
        {'fiscal_year': fiscal_year},
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=f"Fiscal year '{fiscal_year.name}' has been activated",
        title='Fiscal Year Activated'
    )


@login_required
@require_http_methods(["GET"])
def fiscal_year_close_modal(request, pk):
    """Load fiscal year closure confirmation modal"""
    fiscal_year = get_object_or_404(FiscalYear, pk=pk)
    
    # Check if already closed
    if fiscal_year.is_closed:
        return render(request, 'core/fiscal_years/modals/already_closed.html', {
            'fiscal_year': fiscal_year,
        })
    
    # Get period statistics
    total_periods = fiscal_year.periods.count()
    open_periods = fiscal_year.periods.filter(is_closed=False).count()
    
    return render(request, 'core/fiscal_years/modals/close_fiscal_year.html', {
        'fiscal_year': fiscal_year,
        'total_periods': total_periods,
        'open_periods': open_periods,
    })


@login_required
@require_http_methods(["POST"])
def fiscal_year_close_submit(request, pk):
    """Process fiscal year closure"""
    fiscal_year = get_object_or_404(FiscalYear, pk=pk)
    
    # Check if already closed
    if fiscal_year.is_closed:
        return create_warning_response(
            message=f"Fiscal year '{fiscal_year.name}' is already closed",
            title='Already Closed'
        )
    
    # Close fiscal year (this will also close all periods)
    fiscal_year.close_fiscal_year(user=request.user)
    
    # Return updated fiscal year card
    fiscal_year.refresh_from_db()
    
    updated_html = render_to_string(
        'core/fiscal_years/_fiscal_year_card.html',
        {'fiscal_year': fiscal_year},
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=f"Fiscal year '{fiscal_year.name}' has been closed successfully",
        title='Fiscal Year Closed'
    )


@login_required
@require_http_methods(["GET"])
def fiscal_year_lock_modal(request, pk):
    """Load fiscal year lock confirmation modal"""
    fiscal_year = get_object_or_404(FiscalYear, pk=pk)
    
    # Check if already locked
    if fiscal_year.is_locked:
        return render(request, 'core/fiscal_years/modals/already_locked.html', {
            'fiscal_year': fiscal_year,
        })
    
    # Check if closed
    if not fiscal_year.is_closed:
        return render(request, 'core/fiscal_years/modals/must_close_first.html', {
            'fiscal_year': fiscal_year,
        })
    
    return render(request, 'core/fiscal_years/modals/lock_fiscal_year.html', {
        'fiscal_year': fiscal_year,
    })


@login_required
@require_http_methods(["POST"])
def fiscal_year_lock_submit(request, pk):
    """Process fiscal year locking"""
    fiscal_year = get_object_or_404(FiscalYear, pk=pk)
    
    # Check if already locked
    if fiscal_year.is_locked:
        return create_warning_response(
            message=f"Fiscal year '{fiscal_year.name}' is already locked",
            title='Already Locked'
        )
    
    # Check if closed
    if not fiscal_year.is_closed:
        return create_error_response(
            message="Fiscal year must be closed before it can be locked",
            title='Cannot Lock'
        )
    
    # Lock fiscal year
    fiscal_year.lock_fiscal_year()
    
    # Return updated fiscal year card
    fiscal_year.refresh_from_db()
    
    updated_html = render_to_string(
        'core/fiscal_years/_fiscal_year_card.html',
        {'fiscal_year': fiscal_year},
        request=request
    )
    
    return create_warning_response(
        html_content=updated_html,
        message=f"Fiscal year '{fiscal_year.name}' has been locked and cannot be edited",
        title='Fiscal Year Locked'
    )


@login_required
@require_http_methods(["GET"])
def fiscal_year_unlock_modal(request, pk):
    """Load fiscal year unlock confirmation modal"""
    fiscal_year = get_object_or_404(FiscalYear, pk=pk)
    
    # Check if locked
    if not fiscal_year.is_locked:
        return render(request, 'core/fiscal_years/modals/not_locked.html', {
            'fiscal_year': fiscal_year,
        })
    
    return render(request, 'core/fiscal_years/modals/unlock_fiscal_year.html', {
        'fiscal_year': fiscal_year,
    })


@login_required
@require_http_methods(["POST"])
def fiscal_year_unlock_submit(request, pk):
    """Process fiscal year unlocking"""
    fiscal_year = get_object_or_404(FiscalYear, pk=pk)
    
    # Check if locked
    if not fiscal_year.is_locked:
        return create_warning_response(
            message=f"Fiscal year '{fiscal_year.name}' is not locked",
            title='Not Locked'
        )
    
    # Unlock fiscal year
    fiscal_year.unlock_fiscal_year()
    
    # Return updated fiscal year card
    fiscal_year.refresh_from_db()
    
    updated_html = render_to_string(
        'core/fiscal_years/_fiscal_year_card.html',
        {'fiscal_year': fiscal_year},
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=f"Fiscal year '{fiscal_year.name}' has been unlocked",
        title='Fiscal Year Unlocked'
    )


@login_required
@require_http_methods(["GET"])
def fiscal_year_delete_modal(request, pk):
    """Load fiscal year deletion confirmation modal"""
    fiscal_year = get_object_or_404(FiscalYear, pk=pk)
    
    # Check if can be deleted
    can_delete = fiscal_year.can_be_deleted()
    has_periods = fiscal_year.periods.exists()
    is_locked = fiscal_year.is_locked
    is_closed = fiscal_year.is_closed
    
    return render(request, 'core/fiscal_years/modals/delete_fiscal_year.html', {
        'fiscal_year': fiscal_year,
        'can_delete': can_delete,
        'has_periods': has_periods,
        'is_locked': is_locked,
        'is_closed': is_closed,
        'period_count': fiscal_year.periods.count(),
    })


@login_required
@require_http_methods(["DELETE", "POST"])
def fiscal_year_delete_submit(request, pk):
    """Process fiscal year deletion"""
    fiscal_year = get_object_or_404(FiscalYear, pk=pk)
    
    # Verify can delete
    if not fiscal_year.can_be_deleted():
        return create_error_response(
            message=f"Cannot delete fiscal year '{fiscal_year.name}' because it contains periods or transactions",
            title='Cannot Delete'
        )
    
    if fiscal_year.is_locked or fiscal_year.is_closed:
        return create_error_response(
            message=f"Cannot delete a {'locked' if fiscal_year.is_locked else 'closed'} fiscal year",
            title='Cannot Delete'
        )
    
    fiscal_year_name = fiscal_year.name
    fiscal_year.delete()
    
    # Return success with redirect
    return create_redirect_response(
        redirect_url='/core/fiscal-years/',
        message=f"Fiscal year '{fiscal_year_name}' has been deleted successfully",
        title='Fiscal Year Deleted'
    )


# =============================================================================
# FISCAL PERIOD MODALS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def period_activate_modal(request, pk):
    """Load period activation confirmation modal"""
    period = get_object_or_404(FiscalPeriod, pk=pk)
    
    # Check if already active
    if period.is_active:
        return render(request, 'core/periods/modals/already_active.html', {
            'period': period,
        })
    
    # Check if closed or locked
    if period.is_closed or period.is_locked:
        return render(request, 'core/periods/modals/cannot_activate.html', {
            'period': period,
            'reason': 'closed or locked'
        })
    
    # Get currently active period
    current_active = FiscalPeriod.get_active_period()
    
    return render(request, 'core/periods/modals/activate_period.html', {
        'period': period,
        'current_active': current_active,
    })


@login_required
@require_http_methods(["POST"])
def period_activate_submit(request, pk):
    """Process period activation"""
    period = get_object_or_404(FiscalPeriod, pk=pk)
    
    # Check if already active
    if period.is_active:
        return create_warning_response(
            message=f"Period '{period.name}' is already active",
            title='Already Active'
        )
    
    # Check if closed or locked
    if period.is_closed or period.is_locked:
        return create_error_response(
            message=f"Cannot activate a {'locked' if period.is_locked else 'closed'} period",
            title='Cannot Activate'
        )
    
    # Activate period (this will deactivate others)
    period.is_active = True
    period.save()
    
    # Return updated period card
    period.refresh_from_db()
    
    updated_html = render_to_string(
        'core/periods/_period_card.html',
        {'period': period},
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=f"Period '{period.name}' has been activated",
        title='Period Activated'
    )


@login_required
@require_http_methods(["GET"])
def period_close_modal(request, pk):
    """Load period closure confirmation modal"""
    period = get_object_or_404(FiscalPeriod, pk=pk)
    
    # Check if already closed
    if period.is_closed:
        return render(request, 'core/periods/modals/already_closed.html', {
            'period': period,
        })
    
    return render(request, 'core/periods/modals/close_period.html', {
        'period': period,
    })


@login_required
@require_http_methods(["POST"])
def period_close_submit(request, pk):
    """Process period closure"""
    period = get_object_or_404(FiscalPeriod, pk=pk)
    
    # Check if already closed
    if period.is_closed:
        return create_warning_response(
            message=f"Period '{period.name}' is already closed",
            title='Already Closed'
        )
    
    # Close period
    period.close_period(user=request.user)
    
    # Return updated period card
    period.refresh_from_db()
    
    updated_html = render_to_string(
        'core/periods/_period_card.html',
        {'period': period},
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=f"Period '{period.name}' has been closed successfully",
        title='Period Closed'
    )


@login_required
@require_http_methods(["GET"])
def period_lock_modal(request, pk):
    """Load period lock confirmation modal"""
    period = get_object_or_404(FiscalPeriod, pk=pk)
    
    # Check if already locked
    if period.is_locked:
        return render(request, 'core/periods/modals/already_locked.html', {
            'period': period,
        })
    
    # Check if closed
    if not period.is_closed:
        return render(request, 'core/periods/modals/must_close_first.html', {
            'period': period,
        })
    
    return render(request, 'core/periods/modals/lock_period.html', {
        'period': period,
    })


@login_required
@require_http_methods(["POST"])
def period_lock_submit(request, pk):
    """Process period locking"""
    period = get_object_or_404(FiscalPeriod, pk=pk)
    
    # Check if already locked
    if period.is_locked:
        return create_warning_response(
            message=f"Period '{period.name}' is already locked",
            title='Already Locked'
        )
    
    # Check if closed
    if not period.is_closed:
        return create_error_response(
            message="Period must be closed before it can be locked",
            title='Cannot Lock'
        )
    
    # Lock period
    period.lock_period()
    
    # Return updated period card
    period.refresh_from_db()
    
    updated_html = render_to_string(
        'core/periods/_period_card.html',
        {'period': period},
        request=request
    )
    
    return create_warning_response(
        html_content=updated_html,
        message=f"Period '{period.name}' has been locked and cannot be edited",
        title='Period Locked'
    )


@login_required
@require_http_methods(["GET"])
def period_unlock_modal(request, pk):
    """Load period unlock confirmation modal"""
    period = get_object_or_404(FiscalPeriod, pk=pk)
    
    # Check if locked
    if not period.is_locked:
        return render(request, 'core/periods/modals/not_locked.html', {
            'period': period,
        })
    
    return render(request, 'core/periods/modals/unlock_period.html', {
        'period': period,
    })


@login_required
@require_http_methods(["POST"])
def period_unlock_submit(request, pk):
    """Process period unlocking"""
    period = get_object_or_404(FiscalPeriod, pk=pk)
    
    # Check if locked
    if not period.is_locked:
        return create_warning_response(
            message=f"Period '{period.name}' is not locked",
            title='Not Locked'
        )
    
    # Unlock period
    period.unlock_period()
    
    # Return updated period card
    period.refresh_from_db()
    
    updated_html = render_to_string(
        'core/periods/_period_card.html',
        {'period': period},
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=f"Period '{period.name}' has been unlocked",
        title='Period Unlocked'
    )


@login_required
@require_http_methods(["GET"])
def period_delete_modal(request, pk):
    """Load period deletion confirmation modal"""
    period = get_object_or_404(FiscalPeriod, pk=pk)
    
    # Check if can be deleted
    can_delete = period.can_be_deleted()
    is_locked = period.is_locked
    is_closed = period.is_closed
    
    return render(request, 'core/periods/modals/delete_period.html', {
        'period': period,
        'can_delete': can_delete,
        'is_locked': is_locked,
        'is_closed': is_closed,
    })


@login_required
@require_http_methods(["DELETE", "POST"])
def period_delete_submit(request, pk):
    """Process period deletion"""
    period = get_object_or_404(FiscalPeriod, pk=pk)
    
    # Verify can delete
    if not period.can_be_deleted():
        return create_error_response(
            message=f"Cannot delete period '{period.name}' because it contains transactions",
            title='Cannot Delete'
        )
    
    if period.is_locked or period.is_closed:
        return create_error_response(
            message=f"Cannot delete a {'locked' if period.is_locked else 'closed'} period",
            title='Cannot Delete'
        )
    
    period_name = period.name
    fiscal_year_id = period.fiscal_year.id
    period.delete()
    
    # Return success (row will be removed by HTMX)
    return create_success_response(
        html_content='',  # No content needed - HTMX removes the row
        message=f"Period '{period_name}' has been deleted successfully",
        title='Period Deleted'
    )

# =============================================================================
# PAYMENT METHOD MODALS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def payment_method_activate_modal(request, pk):
    """Load payment method activation confirmation modal"""
    payment_method = get_object_or_404(PaymentMethod, pk=pk)
    
    # Check if already active
    if payment_method.is_active:
        return render(request, 'core/payment_methods/modals/already_active.html', {
            'payment_method': payment_method,
        })
    
    return render(request, 'core/payment_methods/modals/activate_payment_method.html', {
        'payment_method': payment_method,
    })


@login_required
@require_http_methods(["POST"])
def payment_method_activate_submit(request, pk):
    """Process payment method activation"""
    payment_method = get_object_or_404(PaymentMethod, pk=pk)
    
    # Check if already active
    if payment_method.is_active:
        return create_warning_response(
            message=f"Payment method '{payment_method.name}' is already active",
            title='Already Active'
        )
    
    # Activate payment method
    payment_method.is_active = True
    payment_method.save()
    
    # Return updated payment method card
    payment_method.refresh_from_db()
    
    updated_html = render_to_string(
        'core/payment_methods/_payment_method_card.html',
        {'payment_method': payment_method},
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=f"Payment method '{payment_method.name}' has been activated",
        title='Payment Method Activated'
    )


@login_required
@require_http_methods(["GET"])
def payment_method_deactivate_modal(request, pk):
    """Load payment method deactivation confirmation modal"""
    payment_method = get_object_or_404(PaymentMethod, pk=pk)
    
    # Check if already inactive
    if not payment_method.is_active:
        return render(request, 'core/payment_methods/modals/already_inactive.html', {
            'payment_method': payment_method,
        })
    
    # Check if it's default
    is_default = payment_method.is_default
    
    return render(request, 'core/payment_methods/modals/deactivate_payment_method.html', {
        'payment_method': payment_method,
        'is_default': is_default,
    })


@login_required
@require_http_methods(["POST"])
def payment_method_deactivate_submit(request, pk):
    """Process payment method deactivation"""
    payment_method = get_object_or_404(PaymentMethod, pk=pk)
    
    # Check if already inactive
    if not payment_method.is_active:
        return create_warning_response(
            message=f"Payment method '{payment_method.name}' is already inactive",
            title='Already Inactive'
        )
    
    # Deactivate payment method
    payment_method.is_active = False
    # Also unset as default if it was
    if payment_method.is_default:
        payment_method.is_default = False
    payment_method.save()
    
    # Return updated payment method card
    payment_method.refresh_from_db()
    
    updated_html = render_to_string(
        'core/payment_methods/_payment_method_card.html',
        {'payment_method': payment_method},
        request=request
    )
    
    return create_warning_response(
        html_content=updated_html,
        message=f"Payment method '{payment_method.name}' has been deactivated",
        title='Payment Method Deactivated'
    )


@login_required
@require_http_methods(["GET"])
def payment_method_set_default_modal(request, pk):
    """Load set as default payment method modal"""
    payment_method = get_object_or_404(PaymentMethod, pk=pk)
    
    # Check if already default
    if payment_method.is_default:
        return render(request, 'core/payment_methods/modals/already_default.html', {
            'payment_method': payment_method,
        })
    
    # Check if active
    if not payment_method.is_active:
        return render(request, 'core/payment_methods/modals/must_be_active.html', {
            'payment_method': payment_method,
        })
    
    # Get current default
    current_default = PaymentMethod.get_default_method()
    
    return render(request, 'core/payment_methods/modals/set_default_payment_method.html', {
        'payment_method': payment_method,
        'current_default': current_default,
    })


@login_required
@require_http_methods(["POST"])
def payment_method_set_default_submit(request, pk):
    """Process setting payment method as default"""
    payment_method = get_object_or_404(PaymentMethod, pk=pk)
    
    # Check if already default
    if payment_method.is_default:
        return create_warning_response(
            message=f"Payment method '{payment_method.name}' is already the default",
            title='Already Default'
        )
    
    # Check if active
    if not payment_method.is_active:
        return create_error_response(
            message="Only active payment methods can be set as default",
            title='Not Active'
        )
    
    # Set as default (model will handle unsetting others)
    payment_method.is_default = True
    payment_method.save()
    
    # Return updated payment methods list
    payment_methods = PaymentMethod.objects.all().order_by('display_order', 'name')
    
    updated_html = render_to_string(
        'core/payment_methods/_payment_methods_list.html',
        {'payment_methods': payment_methods},
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=f"Payment method '{payment_method.name}' set as default",
        title='Default Payment Method Set'
    )


@login_required
@require_http_methods(["GET"])
def payment_method_delete_modal(request, pk):
    """Load payment method deletion confirmation modal"""
    payment_method = get_object_or_404(PaymentMethod, pk=pk)
    
    # Check if it's the default payment method
    is_default = payment_method.is_default
    
    # TODO: Check if it has been used in transactions
    has_transactions = False
    
    can_delete = not (is_default or has_transactions)
    
    return render(request, 'core/payment_methods/modals/delete_payment_method.html', {
        'payment_method': payment_method,
        'can_delete': can_delete,
        'is_default': is_default,
        'has_transactions': has_transactions,
    })


@login_required
@require_http_methods(["DELETE", "POST"])
def payment_method_delete_submit(request, pk):
    """Process payment method deletion"""
    payment_method = get_object_or_404(PaymentMethod, pk=pk)
    
    # Verify can delete
    if payment_method.is_default:
        return create_error_response(
            message=f"Cannot delete the default payment method. Please set another payment method as default first.",
            title='Cannot Delete'
        )
    
    payment_method_name = payment_method.name
    payment_method.delete()
    
    # Return success (row will be removed by HTMX)
    return create_success_response(
        html_content='',  # No content needed - HTMX removes the row
        message=f"Payment method '{payment_method_name}' has been deleted successfully",
        title='Payment Method Deleted'
    )


# =============================================================================
# TAX RATE MODALS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def tax_rate_activate_modal(request, pk):
    """Load tax rate activation confirmation modal"""
    tax_rate = get_object_or_404(TaxRate, pk=pk)
    
    # Check if already active
    if tax_rate.is_active:
        return render(request, 'core/tax_rates/modals/already_active.html', {
            'tax_rate': tax_rate,
        })
    
    return render(request, 'core/tax_rates/modals/activate_tax_rate.html', {
        'tax_rate': tax_rate,
    })


@login_required
@require_http_methods(["POST"])
def tax_rate_activate_submit(request, pk):
    """Process tax rate activation"""
    tax_rate = get_object_or_404(TaxRate, pk=pk)
    
    # Check if already active
    if tax_rate.is_active:
        return create_warning_response(
            message=f"Tax rate '{tax_rate.name}' is already active",
            title='Already Active'
        )
    
    # Activate tax rate
    tax_rate.is_active = True
    tax_rate.save()
    
    # Return updated tax rate card
    tax_rate.refresh_from_db()
    
    updated_html = render_to_string(
        'core/tax_rates/_tax_rate_card.html',
        {'tax_rate': tax_rate},
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=f"Tax rate '{tax_rate.name}' has been activated",
        title='Tax Rate Activated'
    )


@login_required
@require_http_methods(["GET"])
def tax_rate_deactivate_modal(request, pk):
    """Load tax rate deactivation confirmation modal"""
    tax_rate = get_object_or_404(TaxRate, pk=pk)
    
    # Check if already inactive
    if not tax_rate.is_active:
        return render(request, 'core/tax_rates/modals/already_inactive.html', {
            'tax_rate': tax_rate,
        })
    
    # Check if currently effective
    is_effective = tax_rate.is_effective()
    
    return render(request, 'core/tax_rates/modals/deactivate_tax_rate.html', {
        'tax_rate': tax_rate,
        'is_effective': is_effective,
    })


@login_required
@require_http_methods(["POST"])
def tax_rate_deactivate_submit(request, pk):
    """Process tax rate deactivation"""
    tax_rate = get_object_or_404(TaxRate, pk=pk)
    
    # Check if already inactive
    if not tax_rate.is_active:
        return create_warning_response(
            message=f"Tax rate '{tax_rate.name}' is already inactive",
            title='Already Inactive'
        )
    
    # Deactivate tax rate
    tax_rate.is_active = False
    tax_rate.save()
    
    # Return updated tax rate card
    tax_rate.refresh_from_db()
    
    updated_html = render_to_string(
        'core/tax_rates/_tax_rate_card.html',
        {'tax_rate': tax_rate},
        request=request
    )
    
    return create_warning_response(
        html_content=updated_html,
        message=f"Tax rate '{tax_rate.name}' has been deactivated",
        title='Tax Rate Deactivated'
    )


@login_required
@require_http_methods(["GET"])
def tax_rate_delete_modal(request, pk):
    """Load tax rate deletion confirmation modal"""
    tax_rate = get_object_or_404(TaxRate, pk=pk)
    
    # Check if currently effective
    is_effective = tax_rate.is_effective()
    
    # TODO: Check if it has been used in calculations
    has_calculations = False
    
    can_delete = not (is_effective or has_calculations)
    
    return render(request, 'core/tax_rates/modals/delete_tax_rate.html', {
        'tax_rate': tax_rate,
        'can_delete': can_delete,
        'is_effective': is_effective,
        'has_calculations': has_calculations,
    })


@login_required
@require_http_methods(["DELETE", "POST"])
def tax_rate_delete_submit(request, pk):
    """Process tax rate deletion"""
    tax_rate = get_object_or_404(TaxRate, pk=pk)
    
    # Verify can delete
    if tax_rate.is_effective():
        return create_error_response(
            message=f"Cannot delete tax rate '{tax_rate.name}' because it is currently effective. Please deactivate it first.",
            title='Cannot Delete'
        )
    
    tax_rate_name = tax_rate.name
    tax_rate.delete()
    
    # Return success (row will be removed by HTMX)
    return create_success_response(
        html_content='',  # No content needed - HTMX removes the row
        message=f"Tax rate '{tax_rate_name}' has been deleted successfully",
        title='Tax Rate Deleted'
    )


# =============================================================================
# UNIT OF MEASURE MODALS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def unit_activate_modal(request, pk):
    """Load unit of measure activation confirmation modal"""
    unit = get_object_or_404(UnitOfMeasure, pk=pk)
    
    # Check if already active
    if unit.is_active:
        return render(request, 'core/units_of_measure/modals/already_active.html', {
            'unit': unit,
        })
    
    return render(request, 'core/units_of_measure/modals/activate_unit.html', {
        'unit': unit,
    })


@login_required
@require_http_methods(["POST"])
def unit_activate_submit(request, pk):
    """Process unit of measure activation"""
    unit = get_object_or_404(UnitOfMeasure, pk=pk)
    
    # Check if already active
    if unit.is_active:
        return create_warning_response(
            message=f"Unit '{unit.name}' is already active",
            title='Already Active'
        )
    
    # Activate unit
    unit.is_active = True
    unit.save()
    
    # Return updated unit card
    unit.refresh_from_db()
    
    updated_html = render_to_string(
        'core/units_of_measure/_unit_card.html',
        {'unit': unit},
        request=request
    )
    
    return create_success_response(
        html_content=updated_html,
        message=f"Unit '{unit.name}' has been activated",
        title='Unit Activated'
    )


@login_required
@require_http_methods(["GET"])
def unit_deactivate_modal(request, pk):
    """Load unit of measure deactivation confirmation modal"""
    unit = get_object_or_404(UnitOfMeasure, pk=pk)
    
    # Check if already inactive
    if not unit.is_active:
        return render(request, 'core/units_of_measure/modals/already_inactive.html', {
            'unit': unit,
        })
    
    # Check if other units depend on this one
    derived_units = UnitOfMeasure.objects.filter(base_unit=unit, is_active=True)
    has_derived_units = derived_units.exists()
    
    return render(request, 'core/units_of_measure/modals/deactivate_unit.html', {
        'unit': unit,
        'has_derived_units': has_derived_units,
        'derived_units': derived_units,
    })


@login_required
@require_http_methods(["POST"])
def unit_deactivate_submit(request, pk):
    """Process unit of measure deactivation"""
    unit = get_object_or_404(UnitOfMeasure, pk=pk)
    
    # Check if already inactive
    if not unit.is_active:
        return create_warning_response(
            message=f"Unit '{unit.name}' is already inactive",
            title='Already Inactive'
        )
    
    # Deactivate unit
    unit.is_active = False
    unit.save()
    
    # Return updated unit card
    unit.refresh_from_db()
    
    updated_html = render_to_string(
        'core/units_of_measure/_unit_card.html',
        {'unit': unit},
        request=request
    )
    
    return create_warning_response(
        html_content=updated_html,
        message=f"Unit '{unit.name}' has been deactivated",
        title='Unit Deactivated'
    )


@login_required
@require_http_methods(["GET"])
def unit_delete_modal(request, pk):
    """Load unit of measure deletion confirmation modal"""
    unit = get_object_or_404(UnitOfMeasure, pk=pk)
    
    # Check if other units depend on this one
    derived_units = UnitOfMeasure.objects.filter(base_unit=unit)
    has_derived_units = derived_units.exists()
    
    # TODO: Check if it's used in products or transactions
    is_in_use = False
    
    can_delete = not (has_derived_units or is_in_use)
    
    return render(request, 'core/units_of_measure/modals/delete_unit.html', {
        'unit': unit,
        'can_delete': can_delete,
        'has_derived_units': has_derived_units,
        'derived_units': derived_units,
        'is_in_use': is_in_use,
    })


@login_required
@require_http_methods(["DELETE", "POST"])
def unit_delete_submit(request, pk):
    """Process unit of measure deletion"""
    unit = get_object_or_404(UnitOfMeasure, pk=pk)
    
    # Verify can delete
    derived_units = UnitOfMeasure.objects.filter(base_unit=unit)
    if derived_units.exists():
        return create_error_response(
            message=f"Cannot delete unit '{unit.name}' because other units are derived from it. Please delete or update the derived units first.",
            title='Cannot Delete'
        )
    
    unit_name = unit.name
    unit.delete()
    
    # Return success (row will be removed by HTMX)
    return create_success_response(
        html_content='',  # No content needed - HTMX removes the row
        message=f"Unit '{unit_name}' has been deleted successfully",
        title='Unit Deleted'
    )