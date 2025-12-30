# savings/urls.py

"""
URL Configuration for Savings Module

Organized into three main sections:
1. Regular Views (views.py) - Full page loads and redirects
2. Modal Views (modal_views.py) - HTMX modal actions without page refresh
3. HTMX Views (htmx_views.py) - Dynamic search and filtering

All URLs use UUID primary keys for security
"""

from django.urls import path
from . import views, htmx_views, modal_views

app_name = 'savings'

urlpatterns = [
    # =============================================================================
    # DASHBOARD
    # =============================================================================
    path('', views.savings_dashboard, name='dashboard'),
    
    # =============================================================================
    # SAVINGS PRODUCTS 
    # =============================================================================

    # Regular Views 
    path('products/', views.product_list, name='product_list'),
    path('products/create/', views.product_create, name='product_create'),
    path('products/<uuid:pk>/', views.product_detail, name='product_detail'),
    path('products/<uuid:pk>/edit/', views.product_edit, name='product_edit'),

    # Modal Views 
    path('products/<uuid:pk>/modal/activate/', modal_views.product_activate_modal, name='product_activate_modal'),
    path('products/<uuid:pk>/modal/activate/submit/', modal_views.product_activate_submit, name='product_activate_submit'),
    path('products/<uuid:pk>/modal/deactivate/', modal_views.product_deactivate_modal, name='product_deactivate_modal'),
    path('products/<uuid:pk>/modal/deactivate/submit/', modal_views.product_deactivate_submit, name='product_deactivate_submit'),
    path('products/<uuid:pk>/modal/delete/', modal_views.product_delete_modal, name='product_delete_modal'),
    path('products/<uuid:pk>/modal/delete/submit/', modal_views.product_delete_submit, name='product_delete_submit'),

    # HTMX Views 
    path('products/htmx/search/', htmx_views.savings_product_search, name='product_search'),
    path('products/htmx/quick-stats/', htmx_views.savings_product_quick_stats, name='product_quick_stats'),

    # =============================================================================
    # INTEREST TIERS 
    # =============================================================================

    # Regular Views 
    path('products/<uuid:product_pk>/tiers/create/', views.tier_create, name='tier_create'),
    path('tiers/<uuid:pk>/edit/', views.tier_edit, name='tier_edit'),

    # Modal Views 
    path('tiers/<uuid:pk>/modal/activate/', modal_views.tier_activate_modal, name='tier_activate_modal'),
    path('tiers/<uuid:pk>/modal/activate/submit/', modal_views.tier_activate_submit, name='tier_activate_submit'),
    path('tiers/<uuid:pk>/modal/deactivate/', modal_views.tier_deactivate_modal, name='tier_deactivate_modal'),
    path('tiers/<uuid:pk>/modal/deactivate/submit/', modal_views.tier_deactivate_submit, name='tier_deactivate_submit'),
    path('tiers/<uuid:pk>/modal/delete/', modal_views.tier_delete_modal, name='tier_delete_modal'),
    path('tiers/<uuid:pk>/modal/delete/submit/', modal_views.tier_delete_submit, name='tier_delete_submit'),

    # =============================================================================
    # SAVINGS ACCOUNTS 
    # =============================================================================

    # Regular Views 
    path('accounts/', views.account_list, name='account_list'),
    path('accounts/create/', views.account_create, name='account_create'),
    path('accounts/quick-open/', views.account_quick_open, name='account_quick_open'),
    path('accounts/<uuid:pk>/', views.account_detail, name='account_detail'),
    path('accounts/<uuid:pk>/edit/', views.account_edit, name='account_edit'),
    path('accounts/<uuid:pk>/approve/', views.account_approve, name='account_approve'),

    # Modal Views 
    path('accounts/<uuid:pk>/modal/approve/', modal_views.account_approve_modal, name='account_approve_modal'),
    path('accounts/<uuid:pk>/modal/approve/submit/', modal_views.account_approve_submit, name='account_approve_submit'),
    path('accounts/<uuid:pk>/modal/freeze/', modal_views.account_freeze_modal, name='account_freeze_modal'),
    path('accounts/<uuid:pk>/modal/freeze/submit/', modal_views.account_freeze_submit, name='account_freeze_submit'),
    path('accounts/<uuid:pk>/modal/unfreeze/', modal_views.account_unfreeze_modal, name='account_unfreeze_modal'),
    path('accounts/<uuid:pk>/modal/unfreeze/submit/', modal_views.account_unfreeze_submit, name='account_unfreeze_submit'),
    path('accounts/<uuid:pk>/modal/close/', modal_views.account_close_modal, name='account_close_modal'),
    path('accounts/<uuid:pk>/modal/close/submit/', modal_views.account_close_submit, name='account_close_submit'),

    # HTMX Views 
    path('accounts/htmx/search/', htmx_views.savings_account_search, name='account_search'),
    path('accounts/<uuid:account_id>/htmx/stats/', htmx_views.account_detail_stats, name='account_detail_stats'),
    path('accounts/htmx/quick-stats/', htmx_views.savings_account_quick_stats, name='account_quick_stats'),

    # =============================================================================
    # TRANSACTIONS 
    # =============================================================================

    # Regular Views 
    path('transactions/', views.transaction_list, name='transaction_list'),
    #path('transactions/create/', views.transaction_create, name='transaction_create'),
    path('transactions/<uuid:pk>/', views.transaction_detail, name='transaction_detail'),
    path('transactions/deposit/', views.deposit, name='deposit'),
    path('transactions/withdrawal/', views.withdrawal, name='withdrawal'),
    path('transactions/transfer/', views.transfer, name='transfer'),

    # Modal Views 
    path('transactions/<uuid:pk>/modal/reverse/', modal_views.transaction_reverse_modal, name='transaction_reverse_modal'),
    path('transactions/<uuid:pk>/modal/reverse/submit/', modal_views.transaction_reverse_submit, name='transaction_reverse_submit'),

    # HTMX Views 
    path('transactions/htmx/search/', htmx_views.savings_transaction_search, name='transaction_search'),
    path('transactions/htmx/quick-stats/', htmx_views.savings_transaction_quick_stats, name='transaction_quick_stats'),

    # =============================================================================
    # INTEREST CALCULATIONS 
    # =============================================================================

    # Regular Views 
    path('interest/', views.bulk_interest_calculation, name='bulk_interest_calculation'),
    path('interest/post/', views.bulk_interest_posting, name='bulk_interest_posting'),

    # Modal Views 
    path('interest/<uuid:pk>/modal/post/', modal_views.interest_post_modal, name='interest_post_modal'),
    path('interest/<uuid:pk>/modal/post/submit/', modal_views.interest_post_submit, name='interest_post_submit'),
    path('interest/<uuid:pk>/modal/delete/', modal_views.interest_delete_modal, name='interest_delete_modal'),
    path('interest/<uuid:pk>/modal/delete/submit/', modal_views.interest_delete_submit, name='interest_delete_submit'),

    # HTMX Views 
    path('interest/htmx/search/', htmx_views.interest_calculation_search, name='interest_search'),

    # =============================================================================
    # STANDING ORDERS 
    # =============================================================================

    # Regular Views 
    path('standing-orders/', views.standing_order_list, name='standing_order_list'),
    path('standing-orders/create/', views.standing_order_create, name='standing_order_create'),
    path('standing-orders/<uuid:pk>/', views.standing_order_detail, name='standing_order_detail'),
    path('standing-orders/<uuid:pk>/edit/', views.standing_order_edit, name='standing_order_edit'),

    # Modal Views 
    path('standing-orders/<uuid:pk>/modal/activate/', modal_views.standing_order_activate_modal, name='standing_order_activate_modal'),
    path('standing-orders/<uuid:pk>/modal/activate/submit/', modal_views.standing_order_activate_submit, name='standing_order_activate_submit'),
    path('standing-orders/<uuid:pk>/modal/pause/', modal_views.standing_order_pause_modal, name='standing_order_pause_modal'),
    path('standing-orders/<uuid:pk>/modal/pause/submit/', modal_views.standing_order_pause_submit, name='standing_order_pause_submit'),
    path('standing-orders/<uuid:pk>/modal/resume/', modal_views.standing_order_resume_modal, name='standing_order_resume_modal'),
    path('standing-orders/<uuid:pk>/modal/resume/submit/', modal_views.standing_order_resume_submit, name='standing_order_resume_submit'),
    path('standing-orders/<uuid:pk>/modal/cancel/', modal_views.standing_order_cancel_modal, name='standing_order_cancel_modal'),
    path('standing-orders/<uuid:pk>/modal/cancel/submit/', modal_views.standing_order_cancel_submit, name='standing_order_cancel_submit'),

    # HTMX Views 
    path('standing-orders/htmx/search/', htmx_views.standing_order_search, name='standing_order_search'),
    path('standing-orders/htmx/quick-stats/', htmx_views.standing_order_quick_stats, name='standing_order_quick_stats'),

    # =============================================================================
    # SAVINGS GOALS 
    # =============================================================================

    # Regular Views 
    path('goals/', views.savings_goal_list, name='goal_list'),
    path('goals/create/', views.savings_goal_create, name='goal_create'),
    path('goals/<uuid:pk>/', views.savings_goal_detail, name='goal_detail'),
    path('goals/<uuid:pk>/edit/', views.savings_goal_edit, name='goal_edit'),

    # Modal Views 
    path('goals/<uuid:pk>/modal/delete/', modal_views.goal_delete_modal, name='goal_delete_modal'),
    path('goals/<uuid:pk>/modal/delete/submit/', modal_views.goal_delete_submit, name='goal_delete_submit'),
    path('goals/<uuid:pk>/modal/mark-achieved/', modal_views.goal_mark_achieved_modal, name='goal_mark_achieved_modal'),
    path('goals/<uuid:pk>/modal/mark-achieved/submit/', modal_views.goal_mark_achieved_submit, name='goal_mark_achieved_submit'),

    # HTMX Views 
    path('goals/htmx/search/', htmx_views.savings_goal_search, name='goal_search'),
    path('goals/htmx/quick-stats/', htmx_views.savings_goal_quick_stats, name='goal_quick_stats'),

    # =============================================================================
    # REPORTS
    # =============================================================================
    
    path('reports/', views.savings_reports, name='reports'),
]