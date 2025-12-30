# accounts/urls.py
from django.urls import path
from . import views, ajax_views

app_name = 'accounts'

urlpatterns = [
    # =============================================================================
    # AUTHENTICATION URLS
    # =============================================================================
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    
    # =============================================================================
    # PROFILE & SETTINGS URLS
    # =============================================================================
    path('settings/', views.user_account_settings, name='user_account_settings'),
    path('change-password/', views.change_password, name='change_password'),
    path('save-theme-preference/', views.save_theme_preference, name='save_theme_preference'),
    path('ajax/update-profile-picture/', ajax_views.update_profile_picture, name='update_profile_picture'),
    
    # =============================================================================
    # USER MANAGEMENT URLS (Admin)
    # =============================================================================
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    path('users/<int:user_id>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:user_id>/toggle-active/', views.user_toggle_active, name='user_toggle_active'),
    path('users/<int:user_id>/unlock/', views.user_unlock_account, name='user_unlock_account'),
    
    # =============================================================================
    # SACCO MANAGEMENT URLS
    # =============================================================================
    path('saccos/', views.sacco_list, name='sacco_list'),
    path('saccos/create/', views.sacco_create, name='sacco_create'),
    path('saccos/<int:sacco_id>/', views.sacco_detail, name='sacco_detail'),
    path('saccos/<int:sacco_id>/edit/', views.sacco_edit, name='sacco_edit'),
    
    # =============================================================================
    # MEMBER ACCOUNT URLS
    # =============================================================================
    path('member-accounts/', views.member_account_list, name='member_account_list'),
]
