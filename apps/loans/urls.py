# loans/urls.py

"""
URL Configuration for Loans Module

Organized into three main sections:
1. Regular Views (views.py) - Full page loads and redirects
2. Modal Views (modal_views.py) - HTMX modal actions without page refresh
3. HTMX Views (htmx_views.py) - Dynamic search and filtering

All URLs use UUID primary keys for security
"""

from django.urls import path
from . import views, htmx_views, modal_views

app_name = 'loans'

urlpatterns = [
    # =============================================================================
    # DASHBOARD
    # =============================================================================
    path('', views.loans_dashboard, name='dashboard'),
    
    # =============================================================================
    # LOAN PRODUCTS 
    # =============================================================================

    # Regular Views 
    path('products/', views.loan_product_list, name='product_list'),
    path('products/create/', views.loan_product_create, name='product_create'),
    path('products/<uuid:pk>/', views.loan_product_detail, name='product_detail'),
    path('products/<uuid:pk>/edit/', views.loan_product_edit, name='product_edit'),

    # Modal Views 
    path('products/<uuid:pk>/modal/delete/', modal_views.loan_product_delete_modal, name='product_delete_modal'),
    path('products/<uuid:pk>/modal/delete/submit/', modal_views.loan_product_delete_submit, name='product_delete_submit'),

    # HTMX Views 
    path('products/htmx/search/', htmx_views.loan_product_search, name='product_search'),
    
    # =============================================================================
    # LOAN APPLICATIONS 
    # =============================================================================

    # Regular Views 
    path('applications/', views.loan_application_list, name='application_list'),
    path('applications/create/', views.loan_application_create, name='application_create'),
    path('applications/<uuid:pk>/', views.loan_application_detail, name='application_detail'),
    path('applications/<uuid:pk>/edit/', views.loan_application_edit, name='application_edit'),
    path('applications/<uuid:pk>/submit/', views.loan_application_submit, name='application_submit'),

    # Modal Views 
    path('applications/<uuid:pk>/modal/approve/', modal_views.loan_application_approve_modal, name='application_approve_modal'),
    path('applications/<uuid:pk>/modal/approve/submit/', modal_views.loan_application_approve_submit, name='application_approve_submit'),

    # HTMX Views 
    path('applications/htmx/search/', htmx_views.loan_application_search, name='application_search'),
    
    # =============================================================================
    # LOANS 
    # =============================================================================

    # Regular Views 
    path('loans/', views.loan_list, name='loan_list'),
    path('loans/<uuid:pk>/', views.loan_detail, name='loan_detail'),
    path('applications/<uuid:pk>/disburse/', views.loan_disburse, name='loan_disburse'),

    # HTMX Views 
    path('loans/htmx/search/', htmx_views.loan_search, name='loan_search'),

    # =============================================================================
    # LOAN PAYMENTS 
    # =============================================================================

    # Regular Views 
    path('payments/', views.loan_payment_list, name='payment_list'),
    path('payments/create/', views.loan_payment_create, name='payment_create'),
    path('payments/<uuid:pk>/', views.loan_payment_detail, name='payment_detail'),

    # Modal Views 
    path('payments/<uuid:pk>/modal/reverse/', modal_views.loan_payment_reverse_modal, name='payment_reverse_modal'),
    path('payments/<uuid:pk>/modal/reverse/submit/', modal_views.loan_payment_reverse_submit, name='payment_reverse_submit'),

    # HTMX Views 
    path('payments/htmx/search/', htmx_views.loan_payment_search, name='payment_search'),

    # =============================================================================
    # LOAN GUARANTORS 
    # =============================================================================

    # Regular Views 
    path('guarantors/', views.loan_guarantor_list, name='guarantor_list'),
    path('applications/<uuid:application_pk>/guarantors/create/', views.loan_guarantor_create, name='guarantor_create'),

    # Modal Views 
    path('guarantors/<uuid:pk>/modal/approve/', modal_views.loan_guarantor_approve_modal, name='guarantor_approve_modal'),
    path('guarantors/<uuid:pk>/modal/approve/submit/', modal_views.loan_guarantor_approve_submit, name='guarantor_approve_submit'),
    path('guarantors/<uuid:pk>/modal/reject/', modal_views.loan_guarantor_reject_modal, name='guarantor_reject_modal'),
    path('guarantors/<uuid:pk>/modal/reject/submit/', modal_views.loan_guarantor_reject_submit, name='guarantor_reject_submit'),

    # HTMX Views 
    path('guarantors/htmx/search/', htmx_views.loan_guarantor_search, name='guarantor_search'),

    # =============================================================================
    # LOAN COLLATERAL 
    # =============================================================================

    # Regular Views 
    path('collaterals/', views.loan_collateral_list, name='collateral_list'),
    path('applications/<uuid:application_pk>/collaterals/create/', views.loan_collateral_create, name='collateral_create'),
    path('collaterals/<uuid:pk>/', views.loan_collateral_detail, name='collateral_detail'),

    # Modal Views 
    path('collaterals/<uuid:pk>/modal/verify/', modal_views.loan_collateral_verify_modal, name='collateral_verify_modal'),
    path('collaterals/<uuid:pk>/modal/verify/submit/', modal_views.loan_collateral_verify_submit, name='collateral_verify_submit'),

    # HTMX Views
    path('collaterals/htmx/search/', htmx_views.loan_collateral_search, name='collateral_search'),

    # =============================================================================
    # LOAN SCHEDULES 
    # =============================================================================

    # Regular Views 
    path('schedules/', views.loan_schedule_list, name='schedule_list'),
    path('loans/<uuid:loan_pk>/schedule/', views.loan_schedule_detail, name='schedule_detail'),

    # HTMX Views 
    path('schedules/htmx/search/', htmx_views.loan_schedule_search, name='schedule_search'),
    
    # =============================================================================
    # LOAN DOCUMENTS 
    # =============================================================================

    # Regular Views 
    path('applications/<uuid:application_pk>/documents/create/', views.loan_document_create, name='document_create_for_application'),
    path('loans/<uuid:loan_pk>/documents/create/', views.loan_document_create, name='document_create_for_loan'),

    # =============================================================================
    # BULK OPERATIONS
    # =============================================================================

    path('bulk/disburse/', views.bulk_loan_disbursement, name='bulk_disburse'),
    
    # =============================================================================
    # REPORTS
    # =============================================================================
    
    path('reports/', views.loan_reports, name='reports'),
]

