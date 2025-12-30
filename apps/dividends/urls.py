# dividends/urls.py

"""
URL Configuration for Dividends Module

Organized into three main sections:
1. Regular Views (views.py) - Full page loads and redirects
2. Modal Views (modal_views.py) - HTMX modal actions without page refresh
3. HTMX Views (htmx_views.py) - Dynamic search and filtering

All URLs use UUID primary keys for security
"""

from django.urls import path
from . import views, htmx_views, modal_views

app_name = 'dividends'

urlpatterns = [
    # =============================================================================
    # DASHBOARD
    # =============================================================================
    path('', views.dividends_dashboard, name='dashboard'),
    
    # =============================================================================
    # DIVIDEND PERIODS
    # =============================================================================
    
    # Regular Views
    path('periods/', views.period_list, name='period_list'),
    path('periods/create/', views.period_create, name='period_create'),
    path('periods/<uuid:pk>/', views.period_detail, name='period_detail'),
    path('periods/<uuid:pk>/edit/', views.period_edit, name='period_edit'),
    path('periods/<uuid:pk>/approve/', views.period_approve, name='period_approve'),
    
    # Modal Views
    path('periods/<uuid:pk>/modal/approve/', modal_views.period_approve_modal, name='period_approve_modal'),
    path('periods/<uuid:pk>/modal/approve/submit/', modal_views.period_approve_submit, name='period_approve_submit'),
    path('periods/<uuid:pk>/modal/cancel/', modal_views.period_cancel_modal, name='period_cancel_modal'),
    path('periods/<uuid:pk>/modal/cancel/submit/', modal_views.period_cancel_submit, name='period_cancel_submit'),
    path('periods/<uuid:pk>/modal/delete/', modal_views.period_delete_modal, name='period_delete_modal'),
    path('periods/<uuid:pk>/modal/delete/submit/', modal_views.period_delete_submit, name='period_delete_submit'),
    
    # HTMX Views
    path('periods/htmx/search/', htmx_views.dividend_period_search, name='period_search'),
    path('periods/htmx/quick-stats/', htmx_views.dividend_period_quick_stats, name='period_quick_stats'),
    path('periods/<uuid:period_id>/htmx/stats/', htmx_views.dividend_period_detail_stats, name='period_detail_stats'),
    
    # =============================================================================
    # DIVIDEND RATES
    # =============================================================================
    
    # Regular Views
    path('periods/<uuid:period_pk>/rates/create/', views.rate_create, name='rate_create'),
    path('rates/<uuid:pk>/edit/', views.rate_edit, name='rate_edit'),
    
    # Modal Views
    path('rates/<uuid:pk>/modal/activate/', modal_views.rate_activate_modal, name='rate_activate_modal'),
    path('rates/<uuid:pk>/modal/activate/submit/', modal_views.rate_activate_submit, name='rate_activate_submit'),
    path('rates/<uuid:pk>/modal/deactivate/', modal_views.rate_deactivate_modal, name='rate_deactivate_modal'),
    path('rates/<uuid:pk>/modal/deactivate/submit/', modal_views.rate_deactivate_submit, name='rate_deactivate_submit'),
    path('rates/<uuid:pk>/modal/delete/', modal_views.rate_delete_modal, name='rate_delete_modal'),
    path('rates/<uuid:pk>/modal/delete/submit/', modal_views.rate_delete_submit, name='rate_delete_submit'),
    
    # HTMX Views
    path('rates/htmx/search/', htmx_views.dividend_rate_search, name='rate_search'),
    
    # =============================================================================
    # MEMBER DIVIDENDS
    # =============================================================================
    
    # Regular Views
    path('members/', views.member_dividend_list, name='member_dividend_list'),
    path('members/<uuid:pk>/', views.member_dividend_detail, name='member_dividend_detail'),
    path('members/calculate/', views.bulk_dividend_calculation, name='bulk_calculation'),
    
    # Modal Views
    path('members/<uuid:pk>/modal/approve/', modal_views.dividend_approve_modal, name='dividend_approve_modal'),
    path('members/<uuid:pk>/modal/approve/submit/', modal_views.dividend_approve_submit, name='dividend_approve_submit'),
    path('members/<uuid:pk>/modal/cancel/', modal_views.dividend_cancel_modal, name='dividend_cancel_modal'),
    path('members/<uuid:pk>/modal/cancel/submit/', modal_views.dividend_cancel_submit, name='dividend_cancel_submit'),
    
    # HTMX Views
    path('members/htmx/search/', htmx_views.member_dividend_search, name='member_dividend_search'),
    path('members/htmx/quick-stats/', htmx_views.member_dividend_quick_stats, name='member_dividend_quick_stats'),
    
    # =============================================================================
    # DISBURSEMENTS
    # =============================================================================
    
    # Regular Views
    path('disbursements/', views.disbursement_list, name='disbursement_list'),
    path('disbursements/create/', views.disbursement_create, name='disbursement_create'),
    path('disbursements/<uuid:pk>/', views.disbursement_detail, name='disbursement_detail'),
    path('disbursements/batch/', views.batch_disbursement, name='batch_disbursement'),
    
    # Modal Views
    path('disbursements/<uuid:pk>/modal/start/', modal_views.disbursement_start_modal, name='disbursement_start_modal'),
    path('disbursements/<uuid:pk>/modal/start/submit/', modal_views.disbursement_start_submit, name='disbursement_start_submit'),
    path('disbursements/<uuid:pk>/modal/cancel/', modal_views.disbursement_cancel_modal, name='disbursement_cancel_modal'),
    path('disbursements/<uuid:pk>/modal/cancel/submit/', modal_views.disbursement_cancel_submit, name='disbursement_cancel_submit'),
    
    # HTMX Views
    path('disbursements/htmx/search/', htmx_views.dividend_disbursement_search, name='disbursement_search'),
    path('disbursements/htmx/quick-stats/', htmx_views.dividend_disbursement_quick_stats, name='disbursement_quick_stats'),
    
    # =============================================================================
    # PAYMENTS
    # =============================================================================
    
    # Regular Views
    path('payments/', views.payment_list, name='payment_list'),
    path('payments/<uuid:pk>/', views.payment_detail, name='payment_detail'),
    path('payments/<uuid:pk>/confirm/', views.payment_confirm, name='payment_confirm'),
    
    # Modal Views
    path('payments/<uuid:pk>/modal/confirm/', modal_views.payment_confirm_modal, name='payment_confirm_modal'),
    path('payments/<uuid:pk>/modal/confirm/submit/', modal_views.payment_confirm_submit, name='payment_confirm_submit'),
    path('payments/<uuid:pk>/modal/fail/', modal_views.payment_fail_modal, name='payment_fail_modal'),
    path('payments/<uuid:pk>/modal/fail/submit/', modal_views.payment_fail_submit, name='payment_fail_submit'),
    
    # HTMX Views
    path('payments/htmx/search/', htmx_views.dividend_payment_search, name='payment_search'),
    path('payments/htmx/quick-stats/', htmx_views.dividend_payment_quick_stats, name='payment_quick_stats'),
    
    # =============================================================================
    # PREFERENCES
    # =============================================================================
    
    # Regular Views
    path('preferences/', views.preference_list, name='preference_list'),
    path('preferences/create/', views.preference_create, name='preference_create'),
    path('preferences/<uuid:pk>/edit/', views.preference_edit, name='preference_edit'),
    
    # Modal Views
    path('preferences/<uuid:pk>/modal/delete/', modal_views.preference_delete_modal, name='preference_delete_modal'),
    path('preferences/<uuid:pk>/modal/delete/submit/', modal_views.preference_delete_submit, name='preference_delete_submit'),
    
    # HTMX Views
    path('preferences/htmx/search/', htmx_views.dividend_preference_search, name='preference_search'),
    
    # =============================================================================
    # REPORTS
    # =============================================================================
    
    path('reports/', views.dividend_reports, name='reports'),
]