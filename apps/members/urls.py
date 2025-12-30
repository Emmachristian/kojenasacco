# members/urls.py

"""
URL Configuration for Members Module

Organized into three main sections:
1. Regular Views (views.py) - Full page loads and redirects
2. Modal Views (modal_views.py) - HTMX modal actions without page refresh
3. HTMX Views (htmx_views.py) - Dynamic search and filtering

All URLs use UUID primary keys for security
"""

from django.urls import path
from . import views, htmx_views, modal_views

app_name = 'members'

urlpatterns = [
    # =============================================================================
    # DASHBOARD
    # =============================================================================
    path('', views.members_dashboard, name='dashboard'),
    
    # =============================================================================
    # MEMBERS 
    # =============================================================================

    # Regular Views 
    path('members/', views.member_list, name='member_list'),
    path('members/create/', views.member_create, name='member_create'),  # Wizard view
    path('members/<uuid:pk>/', views.member_profile, name='member_profile'),
    path('members/<uuid:pk>/edit/', views.member_edit, name='member_edit'),
    path('members/<uuid:pk>/activate/', views.member_activate, name='member_activate'),
    path('members/<uuid:pk>/suspend/', views.member_suspend, name='member_suspend'),
    #path('members/<uuid:pk>/deactivate/', views.member_deactivate, name='member_deactivate'),
    path('print/', views.member_print_view, name='member_print_view'),

    # Modal Views 
    path('members/<uuid:pk>/modal/activate/', modal_views.member_activate_modal, name='member_activate_modal'),
    path('members/<uuid:pk>/modal/activate/submit/', modal_views.member_activate_submit, name='member_activate_submit'),
    path('members/<uuid:pk>/modal/suspend/', modal_views.member_suspend_modal, name='member_suspend_modal'),
    path('members/<uuid:pk>/modal/suspend/submit/', modal_views.member_suspend_submit, name='member_suspend_submit'),
    path('members/<uuid:pk>/modal/deactivate/', modal_views.member_deactivate_modal, name='member_deactivate_modal'),
    path('members/<uuid:pk>/modal/deactivate/submit/', modal_views.member_deactivate_submit, name='member_deactivate_submit'),
    path('members/<uuid:pk>/modal/delete/', modal_views.member_delete_modal, name='member_delete_modal'),
    path('members/<uuid:pk>/modal/delete/submit/', modal_views.member_delete_submit, name='member_delete_submit'),

    # HTMX Views 
    path('members/htmx/search/', htmx_views.member_search, name='member_search'),
    path('members/<uuid:member_id>/htmx/stats/', htmx_views.member_detail_stats, name='member_detail_stats'),
    path('members/htmx/quick-stats/', htmx_views.member_quick_stats, name='member_quick_stats'),
    
    # =============================================================================
    # PAYMENT METHODS 
    # =============================================================================

    # Regular Views 
    path('payment-methods/', views.payment_method_list, name='payment_method_list'),
    path('members/<uuid:member_pk>/payment-methods/create/', views.payment_method_create, name='payment_method_create'),
    #path('payment-methods/<uuid:pk>/', views.payment_method_detail, name='payment_method_detail'),
    path('payment-methods/<uuid:pk>/edit/', views.payment_method_edit, name='payment_method_edit'),

    # Modal Views 
    path('payment-methods/<uuid:pk>/modal/verify/', modal_views.payment_method_verify_modal, name='payment_method_verify_modal'),
    path('payment-methods/<uuid:pk>/modal/verify/submit/', modal_views.payment_method_verify_submit, name='payment_method_verify_submit'),
    path('payment-methods/<uuid:pk>/modal/set-primary/', modal_views.payment_method_set_primary_modal, name='payment_method_set_primary_modal'),
    path('payment-methods/<uuid:pk>/modal/set-primary/submit/', modal_views.payment_method_set_primary_submit, name='payment_method_set_primary_submit'),
    path('payment-methods/<uuid:pk>/modal/delete/', modal_views.payment_method_delete_modal, name='payment_method_delete_modal'),
    path('payment-methods/<uuid:pk>/modal/delete/submit/', modal_views.payment_method_delete_submit, name='payment_method_delete_submit'),

    # HTMX Views 
    path('payment-methods/htmx/search/', htmx_views.payment_method_search, name='payment_method_search'),
    path('payment-methods/htmx/quick-stats/', htmx_views.payment_method_quick_stats, name='payment_method_quick_stats'),

    # =============================================================================
    # NEXT OF KIN 
    # =============================================================================

    # Regular Views 
    path('next-of-kin/', views.next_of_kin_list, name='next_of_kin_list'),
    path('members/<uuid:member_pk>/next-of-kin/create/', views.next_of_kin_create, name='next_of_kin_create'),
    #path('next-of-kin/<uuid:pk>/', views.next_of_kin_detail, name='next_of_kin_detail'),
    path('next-of-kin/<uuid:pk>/edit/', views.next_of_kin_edit, name='next_of_kin_edit'),

    # Modal Views 
    path('next-of-kin/<uuid:pk>/modal/set-primary/', modal_views.next_of_kin_set_primary_modal, name='next_of_kin_set_primary_modal'),
    path('next-of-kin/<uuid:pk>/modal/set-primary/submit/', modal_views.next_of_kin_set_primary_submit, name='next_of_kin_set_primary_submit'),
    path('next-of-kin/<uuid:pk>/modal/set-emergency/', modal_views.next_of_kin_set_emergency_modal, name='next_of_kin_set_emergency_modal'),
    path('next-of-kin/<uuid:pk>/modal/set-emergency/submit/', modal_views.next_of_kin_set_emergency_submit, name='next_of_kin_set_emergency_submit'),
    path('next-of-kin/<uuid:pk>/modal/delete/', modal_views.next_of_kin_delete_modal, name='next_of_kin_delete_modal'),
    path('next-of-kin/<uuid:pk>/modal/delete/submit/', modal_views.next_of_kin_delete_submit, name='next_of_kin_delete_submit'),

    # HTMX Views 
    path('next-of-kin/htmx/search/', htmx_views.next_of_kin_search, name='next_of_kin_search'),

    # =============================================================================
    # ADDITIONAL CONTACTS 
    # =============================================================================

    # Regular Views 
    path('members/<uuid:member_pk>/additional-contacts/create/', views.additional_contact_create, name='additional_contact_create'),
    path('additional-contacts/<uuid:pk>/edit/', views.additional_contact_edit, name='additional_contact_edit'),

    # Modal Views 
    path('additional-contacts/<uuid:pk>/modal/verify/', modal_views.additional_contact_verify_modal, name='additional_contact_verify_modal'),
    path('additional-contacts/<uuid:pk>/modal/verify/submit/', modal_views.additional_contact_verify_submit, name='additional_contact_verify_submit'),
    path('additional-contacts/<uuid:pk>/modal/delete/', modal_views.additional_contact_delete_modal, name='additional_contact_delete_modal'),
    path('additional-contacts/<uuid:pk>/modal/delete/submit/', modal_views.additional_contact_delete_submit, name='additional_contact_delete_submit'),

    # HTMX Views 
    path('additional-contacts/htmx/search/', htmx_views.additional_contact_search, name='additional_contact_search'),

    # =============================================================================
    # MEMBER GROUPS 
    # =============================================================================

    # Regular Views 
    path('groups/', views.group_list, name='group_list'),
    path('groups/create/', views.group_create, name='group_create'),
    path('groups/<uuid:pk>/', views.group_detail, name='group_detail'),
    path('groups/<uuid:pk>/edit/', views.group_edit, name='group_edit'),
    path('groups/<uuid:group_pk>/add-member/', views.group_add_member, name='group_add_member'),

    # Modal Views 
    path('groups/<uuid:pk>/modal/activate/', modal_views.group_activate_modal, name='group_activate_modal'),
    path('groups/<uuid:pk>/modal/activate/submit/', modal_views.group_activate_submit, name='group_activate_submit'),
    path('groups/<uuid:pk>/modal/deactivate/', modal_views.group_deactivate_modal, name='group_deactivate_modal'),
    path('groups/<uuid:pk>/modal/deactivate/submit/', modal_views.group_deactivate_submit, name='group_deactivate_submit'),
    path('groups/<uuid:pk>/modal/delete/', modal_views.group_delete_modal, name='group_delete_modal'),
    path('groups/<uuid:pk>/modal/delete/submit/', modal_views.group_delete_submit, name='group_delete_submit'),

    # HTMX Views 
    path('groups/htmx/search/', htmx_views.member_group_search, name='group_search'),
    path('groups/<uuid:group_id>/htmx/stats/', htmx_views.member_group_detail_stats, name='group_detail_stats'),
    path('groups/htmx/quick-stats/', htmx_views.member_group_quick_stats, name='group_quick_stats'),

    # =============================================================================
    # GROUP MEMBERSHIPS 
    # =============================================================================

    # Regular Views 
    path('group-memberships/<uuid:pk>/edit/', views.group_membership_edit, name='group_membership_edit'),

    # Modal Views 
    path('group-memberships/<uuid:pk>/modal/remove/', modal_views.group_membership_remove_modal, name='group_membership_remove_modal'),
    path('group-memberships/<uuid:pk>/modal/remove/submit/', modal_views.group_membership_remove_submit, name='group_membership_remove_submit'),
    path('group-memberships/<uuid:pk>/modal/suspend/', modal_views.group_membership_suspend_modal, name='group_membership_suspend_modal'),
    path('group-memberships/<uuid:pk>/modal/suspend/submit/', modal_views.group_membership_suspend_submit, name='group_membership_suspend_submit'),
    path('group-memberships/<uuid:pk>/modal/reactivate/', modal_views.group_membership_reactivate_modal, name='group_membership_reactivate_modal'),
    path('group-memberships/<uuid:pk>/modal/reactivate/submit/', modal_views.group_membership_reactivate_submit, name='group_membership_reactivate_submit'),

    # HTMX Views 
    path('group-memberships/htmx/search/', htmx_views.group_membership_search, name='group_membership_search'),

    # =============================================================================
    # EXPORTS
    # =============================================================================

    path('members/export/excel/', views.export_members_excel, name='export_members_excel'),
    path('members/export/pdf/', views.export_members_pdf, name='export_members_pdf'),
]