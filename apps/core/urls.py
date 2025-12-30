# core/urls.py

"""
URL Configuration for Core Module

Organized into three main sections:
1. Regular Views (views.py) - Full page loads and redirects
2. Modal Views (modal_views.py) - HTMX modal actions without page refresh
3. HTMX Views (htmx_views.py) - Dynamic search and filtering

All URLs use UUID primary keys for security
"""

from django.urls import path
from . import views, htmx_views, modal_views

app_name = 'core'

urlpatterns = [
    # =============================================================================
    # DASHBOARD
    # =============================================================================
    path('', views.core_dashboard, name='home'),
    
    # =============================================================================
    # SACCO CONFIGURATION
    # =============================================================================
    
    # Regular Views
    path('configuration/', views.sacco_configuration_view, name='sacco_configuration'),
    
    # HTMX Views
    path('configuration/htmx/stats/', htmx_views.sacco_configuration_stats, name='sacco_configuration_stats'),
    
    # =============================================================================
    # FINANCIAL SETTINGS
    # =============================================================================
    
    # Regular Views
    path('financial-settings/', views.financial_settings_view, name='financial_settings'),
    
    # HTMX Views
    path('financial-settings/htmx/stats/', htmx_views.financial_settings_stats, name='financial_settings_stats'),
    
    # =============================================================================
    # FISCAL YEARS
    # =============================================================================
    
    # Regular Views
    path('fiscal-years/', views.fiscal_year_list, name='fiscal_year_list'),
    path('fiscal-years/create/', views.fiscal_year_create, name='fiscal_year_create'),
    path('fiscal-years/<uuid:pk>/', views.fiscal_year_detail, name='fiscal_year_detail'),
    path('fiscal-years/<uuid:pk>/edit/', views.fiscal_year_edit, name='fiscal_year_edit'),
    path('fiscal-years/<uuid:pk>/delete/', views.fiscal_year_delete, name='fiscal_year_delete'),
    path('fiscal-years/print/', views.fiscal_year_print_view, name='fiscal_year_print_view'),
    
    # Modal Views
    path('fiscal-years/<uuid:pk>/modal/activate/', modal_views.fiscal_year_activate_modal, name='fiscal_year_activate_modal'),
    path('fiscal-years/<uuid:pk>/modal/activate/submit/', modal_views.fiscal_year_activate_submit, name='fiscal_year_activate_submit'),
    path('fiscal-years/<uuid:pk>/modal/close/', modal_views.fiscal_year_close_modal, name='fiscal_year_close_modal'),
    path('fiscal-years/<uuid:pk>/modal/close/submit/', modal_views.fiscal_year_close_submit, name='fiscal_year_close_submit'),
    path('fiscal-years/<uuid:pk>/modal/lock/', modal_views.fiscal_year_lock_modal, name='fiscal_year_lock_modal'),
    path('fiscal-years/<uuid:pk>/modal/lock/submit/', modal_views.fiscal_year_lock_submit, name='fiscal_year_lock_submit'),
    path('fiscal-years/<uuid:pk>/modal/unlock/', modal_views.fiscal_year_unlock_modal, name='fiscal_year_unlock_modal'),
    path('fiscal-years/<uuid:pk>/modal/unlock/submit/', modal_views.fiscal_year_unlock_submit, name='fiscal_year_unlock_submit'),
    path('fiscal-years/<uuid:pk>/modal/delete/', modal_views.fiscal_year_delete_modal, name='fiscal_year_delete_modal'),
    path('fiscal-years/<uuid:pk>/modal/delete/submit/', modal_views.fiscal_year_delete_submit, name='fiscal_year_delete_submit'),
    
    # HTMX Views
    path('fiscal-years/htmx/search/', htmx_views.fiscal_year_search, name='fiscal_year_search'),
    path('fiscal-years/htmx/quick-stats/', htmx_views.fiscal_year_quick_stats, name='fiscal_year_quick_stats'),
    path('fiscal-years/<uuid:year_id>/htmx/stats/', htmx_views.fiscal_year_detail_stats, name='fiscal_year_detail_stats'),
    path('fiscal-years/fiscal_year_modal/', views.fiscal_year_modal, name='fiscal_year_modal'),
    path('fiscal-years/period_modal/', views.period_modal, name='period_modal'),
    
    # =============================================================================
    # FISCAL PERIODS
    # =============================================================================
    
    # Regular Views
    path('periods/', views.period_list, name='period_list'),
    path('periods/create/', views.period_create, name='period_create'),
    path('fiscal-years/<uuid:fiscal_year_pk>/periods/create/', views.period_create, name='period_create_for_year'),
    path('periods/<uuid:pk>/', views.period_detail, name='period_detail'),
    path('periods/<uuid:pk>/edit/', views.period_edit, name='period_edit'),
    path('periods/<uuid:pk>/delete/', views.period_delete, name='period_delete'),
    path('periods/print/', views.period_print_view, name='period_print_view'),
    
    # Modal Views
    path('periods/<uuid:pk>/modal/activate/', modal_views.period_activate_modal, name='period_activate_modal'),
    path('periods/<uuid:pk>/modal/activate/submit/', modal_views.period_activate_submit, name='period_activate_submit'),
    path('periods/<uuid:pk>/modal/close/', modal_views.period_close_modal, name='period_close_modal'),
    path('periods/<uuid:pk>/modal/close/submit/', modal_views.period_close_submit, name='period_close_submit'),
    path('periods/<uuid:pk>/modal/lock/', modal_views.period_lock_modal, name='period_lock_modal'),
    path('periods/<uuid:pk>/modal/lock/submit/', modal_views.period_lock_submit, name='period_lock_submit'),
    path('periods/<uuid:pk>/modal/unlock/', modal_views.period_unlock_modal, name='period_unlock_modal'),
    path('periods/<uuid:pk>/modal/unlock/submit/', modal_views.period_unlock_submit, name='period_unlock_submit'),
    path('periods/<uuid:pk>/modal/delete/', modal_views.period_delete_modal, name='period_delete_modal'),
    path('periods/<uuid:pk>/modal/delete/submit/', modal_views.period_delete_submit, name='period_delete_submit'),
    
    # HTMX Views
    path('periods/htmx/search/', htmx_views.fiscal_period_search, name='period_search'),
    path('periods/htmx/quick-stats/', htmx_views.fiscal_period_quick_stats, name='period_quick_stats'),
    path('periods/<uuid:period_id>/htmx/stats/', htmx_views.fiscal_period_detail_stats, name='period_detail_stats'),
    
    # =============================================================================
    # PAYMENT METHODS
    # =============================================================================
    
    # Regular Views
    path('payment-methods/', views.payment_method_list, name='payment_method_list'),
    path('payment-methods/create/', views.payment_method_create, name='payment_method_create'),
    path('payment-methods/<uuid:pk>/', views.payment_method_detail, name='payment_method_detail'),
    path('payment-methods/<uuid:pk>/edit/', views.payment_method_edit, name='payment_method_edit'),
    path('payment-methods/<uuid:pk>/delete/', views.payment_method_delete, name='payment_method_delete'),
    path('payment-methods/print/', views.payment_method_print_view, name='payment_method_print_view'),
    
    # Modal Views
    path('payment-methods/<uuid:pk>/modal/activate/', modal_views.payment_method_activate_modal, name='payment_method_activate_modal'),
    path('payment-methods/<uuid:pk>/modal/activate/submit/', modal_views.payment_method_activate_submit, name='payment_method_activate_submit'),
    path('payment-methods/<uuid:pk>/modal/deactivate/', modal_views.payment_method_deactivate_modal, name='payment_method_deactivate_modal'),
    path('payment-methods/<uuid:pk>/modal/deactivate/submit/', modal_views.payment_method_deactivate_submit, name='payment_method_deactivate_submit'),
    path('payment-methods/<uuid:pk>/modal/set-default/', modal_views.payment_method_set_default_modal, name='payment_method_set_default_modal'),
    path('payment-methods/<uuid:pk>/modal/set-default/submit/', modal_views.payment_method_set_default_submit, name='payment_method_set_default_submit'),
    path('payment-methods/<uuid:pk>/modal/delete/', modal_views.payment_method_delete_modal, name='payment_method_delete_modal'),
    path('payment-methods/<uuid:pk>/modal/delete/submit/', modal_views.payment_method_delete_submit, name='payment_method_delete_submit'),
    
    # HTMX Views
    path('payment-methods/htmx/search/', htmx_views.payment_method_search, name='payment_method_search'),
    path('payment-methods/htmx/quick-stats/', htmx_views.payment_method_quick_stats, name='payment_method_quick_stats'),
    path('payment-methods/<uuid:method_id>/htmx/stats/', htmx_views.payment_method_detail_stats, name='payment_method_detail_stats'),
    
    # =============================================================================
    # TAX RATES
    # =============================================================================
    
    # Regular Views
    path('tax-rates/', views.tax_rate_list, name='tax_rate_list'),
    path('tax-rates/create/', views.tax_rate_create, name='tax_rate_create'),
    path('tax-rates/<uuid:pk>/', views.tax_rate_detail, name='tax_rate_detail'),
    path('tax-rates/<uuid:pk>/edit/', views.tax_rate_edit, name='tax_rate_edit'),
    path('tax-rates/<uuid:pk>/delete/', views.tax_rate_delete, name='tax_rate_delete'),
    path('tax-rates/print/', views.tax_rate_print_view, name='tax_rate_print_view'),
    
    # Modal Views
    path('tax-rates/<uuid:pk>/modal/activate/', modal_views.tax_rate_activate_modal, name='tax_rate_activate_modal'),
    path('tax-rates/<uuid:pk>/modal/activate/submit/', modal_views.tax_rate_activate_submit, name='tax_rate_activate_submit'),
    path('tax-rates/<uuid:pk>/modal/deactivate/', modal_views.tax_rate_deactivate_modal, name='tax_rate_deactivate_modal'),
    path('tax-rates/<uuid:pk>/modal/deactivate/submit/', modal_views.tax_rate_deactivate_submit, name='tax_rate_deactivate_submit'),
    path('tax-rates/<uuid:pk>/modal/delete/', modal_views.tax_rate_delete_modal, name='tax_rate_delete_modal'),
    path('tax-rates/<uuid:pk>/modal/delete/submit/', modal_views.tax_rate_delete_submit, name='tax_rate_delete_submit'),
    
    # HTMX Views
    path('tax-rates/htmx/search/', htmx_views.tax_rate_search, name='tax_rate_search'),
    path('tax-rates/htmx/quick-stats/', htmx_views.tax_rate_quick_stats, name='tax_rate_quick_stats'),
    path('tax-rates/<uuid:rate_id>/htmx/stats/', htmx_views.tax_rate_detail_stats, name='tax_rate_detail_stats'),
    
    # =============================================================================
    # UNITS OF MEASURE
    # =============================================================================
    
    # Regular Views
    path('units-of-measure/', views.unit_of_measure_list, name='unit_of_measure_list'),
    path('units-of-measure/create/', views.unit_of_measure_create, name='unit_of_measure_create'),
    path('units-of-measure/<uuid:pk>/', views.unit_of_measure_detail, name='unit_of_measure_detail'),
    path('units-of-measure/<uuid:pk>/edit/', views.unit_of_measure_edit, name='unit_of_measure_edit'),
    path('units-of-measure/<uuid:pk>/delete/', views.unit_of_measure_delete, name='unit_of_measure_delete'),
    path('units-of-measure/print/', views.unit_of_measure_print_view, name='unit_of_measure_print_view'),
    
    # Modal Views
    path('units-of-measure/<uuid:pk>/modal/activate/', modal_views.unit_activate_modal, name='unit_activate_modal'),
    path('units-of-measure/<uuid:pk>/modal/activate/submit/', modal_views.unit_activate_submit, name='unit_activate_submit'),
    path('units-of-measure/<uuid:pk>/modal/deactivate/', modal_views.unit_deactivate_modal, name='unit_deactivate_modal'),
    path('units-of-measure/<uuid:pk>/modal/deactivate/submit/', modal_views.unit_deactivate_submit, name='unit_deactivate_submit'),
    path('units-of-measure/<uuid:pk>/modal/delete/', modal_views.unit_delete_modal, name='unit_delete_modal'),
    path('units-of-measure/<uuid:pk>/modal/delete/submit/', modal_views.unit_delete_submit, name='unit_delete_submit'),
    
    # HTMX Views
    path('units-of-measure/htmx/search/', htmx_views.unit_of_measure_search, name='unit_of_measure_search'),
    path('units-of-measure/htmx/quick-stats/', htmx_views.unit_of_measure_quick_stats, name='unit_of_measure_quick_stats'),
    path('units-of-measure/<uuid:unit_id>/htmx/stats/', htmx_views.unit_of_measure_detail_stats, name='unit_of_measure_detail_stats'),
]