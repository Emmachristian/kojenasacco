# utils/urls.py

from django.urls import path
from . import htmx_views

app_name = 'utils'

urlpatterns = [
    # =============================================================================
    # AUDIT LOG HTMX ENDPOINTS
    # =============================================================================
    
    # Search and filter
    path('audit-logs/search/', htmx_views.audit_log_search, name='audit_log_search'),
    path('financial-audit-logs/search/', htmx_views.financial_audit_log_search, name='financial_audit_log_search'),
    
    # Quick stats
    path('audit-logs/quick-stats/', htmx_views.audit_log_quick_stats, name='audit_log_quick_stats'),
    path('financial-audit-logs/quick-stats/', htmx_views.financial_audit_log_quick_stats, name='financial_audit_log_quick_stats'),
    
    # Detail views
    path('audit-logs/<uuid:log_id>/detail/', htmx_views.audit_log_detail, name='audit_log_detail'),
    path('financial-audit-logs/<int:log_id>/detail/', htmx_views.financial_audit_log_detail, name='financial_audit_log_detail'),
    
    # =============================================================================
    # USER ACTIVITY ENDPOINTS
    # =============================================================================
    
    path('users/<str:user_id>/activity/', htmx_views.user_activity_stats, name='user_activity_stats'),
    
    # =============================================================================
    # TIMELINE ENDPOINTS
    # =============================================================================
    
    path('audit-logs/timeline/', htmx_views.audit_timeline, name='audit_timeline'),
    path('financial-audit-logs/timeline/', htmx_views.financial_audit_timeline, name='financial_audit_timeline'),
    
    # =============================================================================
    # OBJECT HISTORY ENDPOINTS
    # =============================================================================
    
    path('object-history/', htmx_views.object_history, name='object_history'),
    
    # =============================================================================
    # COMPLIANCE REPORTING ENDPOINTS
    # =============================================================================
    
    path('compliance/report/', htmx_views.compliance_report, name='compliance_report'),
]