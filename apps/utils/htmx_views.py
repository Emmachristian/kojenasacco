# utils/htmx_views.py

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Count, Sum, Avg, Min, Max, F, Value, CharField
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.contrib.contenttypes.models import ContentType
from datetime import timedelta
from decimal import Decimal
import logging

from .models import AuditLog, FinancialAuditLog
from core.utils import parse_filters, paginate_queryset, format_money

logger = logging.getLogger(__name__)


# =============================================================================
# AUDIT LOG SEARCH
# =============================================================================

def audit_log_search(request):
    """HTMX-compatible audit log search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'action', 'content_type', 'user_id', 'object_id',
        'date_from', 'date_to', 'ip_address', 'session_key',
        'has_changes', 'has_change_reason'
    ])
    
    query = filters['q']
    action = filters['action']
    content_type = filters['content_type']
    user_id = filters['user_id']
    object_id = filters['object_id']
    date_from = filters['date_from']
    date_to = filters['date_to']
    ip_address = filters['ip_address']
    session_key = filters['session_key']
    has_changes = filters['has_changes']
    has_change_reason = filters['has_change_reason']
    
    # Build queryset
    logs = AuditLog.objects.all().order_by('-timestamp')
    
    # Apply text search
    if query:
        logs = logs.filter(
            Q(object_repr__icontains=query) |
            Q(user_name__icontains=query) |
            Q(user_email__icontains=query) |
            Q(content_type__icontains=query) |
            Q(change_reason__icontains=query)
        )
    
    # Apply filters
    if action:
        logs = logs.filter(action=action)
    
    if content_type:
        logs = logs.filter(content_type=content_type)
    
    if user_id:
        logs = logs.filter(user_id=user_id)
    
    if object_id:
        logs = logs.filter(object_id=object_id)
    
    if ip_address:
        logs = logs.filter(ip_address__icontains=ip_address)
    
    if session_key:
        logs = logs.filter(session_key=session_key)
    
    # Date filters
    if date_from:
        logs = logs.filter(timestamp__gte=date_from)
    
    if date_to:
        # Add one day to include the entire end date
        from datetime import datetime, time
        if isinstance(date_to, str):
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        end_datetime = datetime.combine(date_to, time.max)
        logs = logs.filter(timestamp__lte=end_datetime)
    
    # Boolean filters
    if has_changes is not None:
        if has_changes.lower() == 'true':
            logs = logs.exclude(changes={})
        else:
            logs = logs.filter(changes={})
    
    if has_change_reason is not None:
        if has_change_reason.lower() == 'true':
            logs = logs.exclude(Q(change_reason__isnull=True) | Q(change_reason=''))
        else:
            logs = logs.filter(Q(change_reason__isnull=True) | Q(change_reason=''))
    
    # Paginate
    logs_page, paginator = paginate_queryset(request, logs, per_page=50)
    
    # Calculate stats
    total = logs.count()
    
    # Action breakdown
    action_stats = logs.values('action').annotate(
        count=Count('id')
    ).order_by('action')
    
    stats = {
        'total': total,
        'create': logs.filter(action='CREATE').count(),
        'update': logs.filter(action='UPDATE').count(),
        'delete': logs.filter(action='DELETE').count(),
        'unique_users': logs.values('user_id').distinct().count(),
        'unique_objects': logs.values('content_type', 'object_id').distinct().count(),
        'unique_content_types': logs.values('content_type').distinct().count(),
        'with_changes': logs.exclude(changes={}).count(),
        'with_reason': logs.exclude(Q(change_reason__isnull=True) | Q(change_reason='')).count(),
        'unique_ips': logs.exclude(ip_address__isnull=True).values('ip_address').distinct().count(),
    }
    
    # Top content types
    top_content_types = logs.values('content_type').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    stats['top_content_types'] = list(top_content_types)
    
    # Recent activity (last 24 hours)
    last_24h = timezone.now() - timedelta(hours=24)
    stats['last_24h'] = logs.filter(timestamp__gte=last_24h).count()
    
    return render(request, 'utils/audit_logs/_audit_log_results.html', {
        'logs_page': logs_page,
        'stats': stats,
    })


# =============================================================================
# FINANCIAL AUDIT LOG SEARCH
# =============================================================================

def financial_audit_log_search(request):
    """HTMX-compatible financial audit log search with pagination and stats"""
    
    # Parse filters
    filters = parse_filters(request, [
        'q', 'action', 'user_id', 'member_id', 'period_id',
        'date_from', 'date_to', 'risk_level', 'ip_address',
        'min_amount', 'max_amount', 'currency', 'is_automated',
        'batch_id', 'has_compliance_flags'
    ])
    
    query = filters['q']
    action = filters['action']
    user_id = filters['user_id']
    member_id = filters['member_id']
    period_id = filters['period_id']
    date_from = filters['date_from']
    date_to = filters['date_to']
    risk_level = filters['risk_level']
    ip_address = filters['ip_address']
    min_amount = filters['min_amount']
    max_amount = filters['max_amount']
    currency = filters['currency']
    is_automated = filters['is_automated']
    batch_id = filters['batch_id']
    has_compliance_flags = filters['has_compliance_flags']
    
    # Build queryset
    logs = FinancialAuditLog.objects.select_related(
        'content_type'
    ).order_by('-timestamp')
    
    # Apply text search
    if query:
        logs = logs.filter(
            Q(user_name__icontains=query) |
            Q(member_name__icontains=query) |
            Q(member_account_number__icontains=query) |
            Q(object_description__icontains=query) |
            Q(notes__icontains=query) |
            Q(period_name__icontains=query)
        )
    
    # Apply filters
    if action:
        logs = logs.filter(action=action)
    
    if user_id:
        logs = logs.filter(user_id=user_id)
    
    if member_id:
        logs = logs.filter(member_id=member_id)
    
    if period_id:
        logs = logs.filter(period_id=period_id)
    
    if risk_level:
        logs = logs.filter(risk_level=risk_level)
    
    if ip_address:
        logs = logs.filter(ip_address__icontains=ip_address)
    
    if currency:
        logs = logs.filter(currency=currency)
    
    if batch_id:
        logs = logs.filter(batch_id=batch_id)
    
    # Date filters
    if date_from:
        logs = logs.filter(timestamp__gte=date_from)
    
    if date_to:
        from datetime import datetime, time
        if isinstance(date_to, str):
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        end_datetime = datetime.combine(date_to, time.max)
        logs = logs.filter(timestamp__lte=end_datetime)
    
    # Amount filters
    if min_amount:
        try:
            logs = logs.filter(amount_involved__gte=Decimal(min_amount))
        except (ValueError, TypeError):
            pass
    
    if max_amount:
        try:
            logs = logs.filter(amount_involved__lte=Decimal(max_amount))
        except (ValueError, TypeError):
            pass
    
    # Boolean filters
    if is_automated is not None:
        logs = logs.filter(is_automated=(is_automated.lower() == 'true'))
    
    if has_compliance_flags is not None:
        if has_compliance_flags.lower() == 'true':
            logs = logs.exclude(compliance_flags=[])
        else:
            logs = logs.filter(compliance_flags=[])
    
    # Paginate
    logs_page, paginator = paginate_queryset(request, logs, per_page=50)
    
    # Calculate stats
    total = logs.count()
    
    aggregates = logs.aggregate(
        total_amount=Sum('amount_involved'),
        avg_amount=Avg('amount_involved'),
        min_amount=Min('amount_involved'),
        max_amount=Max('amount_involved')
    )
    
    stats = {
        'total': total,
        'unique_users': logs.values('user_id').distinct().count(),
        'unique_members': logs.exclude(member_id__isnull=True).values('member_id').distinct().count(),
        'unique_periods': logs.exclude(period_id__isnull=True).values('period_id').distinct().count(),
        'total_amount': aggregates['total_amount'] or Decimal('0.00'),
        'avg_amount': aggregates['avg_amount'] or Decimal('0.00'),
        'min_amount': aggregates['min_amount'] or Decimal('0.00'),
        'max_amount': aggregates['max_amount'] or Decimal('0.00'),
        'automated': logs.filter(is_automated=True).count(),
        'manual': logs.filter(is_automated=False).count(),
        'with_compliance_flags': logs.exclude(compliance_flags=[]).count(),
    }
    
    # Format money in stats
    stats['total_amount_formatted'] = format_money(stats['total_amount'])
    stats['avg_amount_formatted'] = format_money(stats['avg_amount'])
    stats['min_amount_formatted'] = format_money(stats['min_amount'])
    stats['max_amount_formatted'] = format_money(stats['max_amount'])
    
    # Risk level breakdown
    stats['low_risk'] = logs.filter(risk_level='LOW').count()
    stats['medium_risk'] = logs.filter(risk_level='MEDIUM').count()
    stats['high_risk'] = logs.filter(risk_level='HIGH').count()
    stats['critical_risk'] = logs.filter(risk_level='CRITICAL').count()
    
    # Action breakdown
    action_stats = logs.values('action').annotate(
        count=Count('id'),
        total_amount=Sum('amount_involved')
    ).order_by('-count')[:10]
    
    stats['top_actions'] = [
        {
            'action': item['action'],
            'action_display': dict(FinancialAuditLog.FINANCIAL_ACTIONS).get(item['action'], item['action']),
            'count': item['count'],
            'total_amount': format_money(item['total_amount'] or Decimal('0.00'))
        }
        for item in action_stats
    ]
    
    # Recent high-risk activity (last 24 hours)
    last_24h = timezone.now() - timedelta(hours=24)
    stats['high_risk_24h'] = logs.filter(
        timestamp__gte=last_24h,
        risk_level__in=['HIGH', 'CRITICAL']
    ).count()
    
    # Currency breakdown
    currency_stats = logs.exclude(amount_involved__isnull=True).values('currency').annotate(
        count=Count('id'),
        total=Sum('amount_involved')
    ).order_by('-total')
    
    stats['by_currency'] = list(currency_stats)
    
    return render(request, 'utils/audit_logs/_financial_audit_log_results.html', {
        'logs_page': logs_page,
        'stats': stats,
    })


# =============================================================================
# QUICK STATS ENDPOINTS
# =============================================================================

@require_http_methods(["GET"])
def audit_log_quick_stats(request):
    """Get quick statistics for audit logs"""
    
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    last_7_days = today - timedelta(days=7)
    last_30_days = today - timedelta(days=30)
    
    stats = {
        'total_logs': AuditLog.objects.count(),
        'today': AuditLog.objects.filter(timestamp__date=today).count(),
        'yesterday': AuditLog.objects.filter(timestamp__date=yesterday).count(),
        'last_7_days': AuditLog.objects.filter(timestamp__date__gte=last_7_days).count(),
        'last_30_days': AuditLog.objects.filter(timestamp__date__gte=last_30_days).count(),
        'create': AuditLog.objects.filter(action='CREATE').count(),
        'update': AuditLog.objects.filter(action='UPDATE').count(),
        'delete': AuditLog.objects.filter(action='DELETE').count(),
        'unique_users': AuditLog.objects.values('user_id').distinct().count(),
        'unique_content_types': AuditLog.objects.values('content_type').distinct().count(),
    }
    
    # Most active users (last 7 days)
    active_users = AuditLog.objects.filter(
        timestamp__date__gte=last_7_days
    ).values('user_name', 'user_email').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    stats['most_active_users'] = list(active_users)
    
    # Most changed content types (last 7 days)
    active_types = AuditLog.objects.filter(
        timestamp__date__gte=last_7_days
    ).values('content_type').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    stats['most_active_types'] = list(active_types)
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def financial_audit_log_quick_stats(request):
    """Get quick statistics for financial audit logs"""
    
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    last_7_days = today - timedelta(days=7)
    last_30_days = today - timedelta(days=30)
    
    # Basic counts
    stats = {
        'total_logs': FinancialAuditLog.objects.count(),
        'today': FinancialAuditLog.objects.filter(timestamp__date=today).count(),
        'yesterday': FinancialAuditLog.objects.filter(timestamp__date=yesterday).count(),
        'last_7_days': FinancialAuditLog.objects.filter(timestamp__date__gte=last_7_days).count(),
        'last_30_days': FinancialAuditLog.objects.filter(timestamp__date__gte=last_30_days).count(),
    }
    
    # Risk levels
    stats['low_risk'] = FinancialAuditLog.objects.filter(risk_level='LOW').count()
    stats['medium_risk'] = FinancialAuditLog.objects.filter(risk_level='MEDIUM').count()
    stats['high_risk'] = FinancialAuditLog.objects.filter(risk_level='HIGH').count()
    stats['critical_risk'] = FinancialAuditLog.objects.filter(risk_level='CRITICAL').count()
    
    # Amount aggregates (last 30 days)
    recent_aggregates = FinancialAuditLog.objects.filter(
        timestamp__date__gte=last_30_days
    ).aggregate(
        total_amount=Sum('amount_involved'),
        avg_amount=Avg('amount_involved')
    )
    
    stats['total_amount_30d'] = str(recent_aggregates['total_amount'] or Decimal('0.00'))
    stats['total_amount_30d_formatted'] = format_money(recent_aggregates['total_amount'] or Decimal('0.00'))
    stats['avg_amount_30d'] = str(recent_aggregates['avg_amount'] or Decimal('0.00'))
    stats['avg_amount_30d_formatted'] = format_money(recent_aggregates['avg_amount'] or Decimal('0.00'))
    
    # Automation stats
    stats['automated'] = FinancialAuditLog.objects.filter(is_automated=True).count()
    stats['manual'] = FinancialAuditLog.objects.filter(is_automated=False).count()
    
    # Compliance flags
    stats['with_compliance_flags'] = FinancialAuditLog.objects.exclude(compliance_flags=[]).count()
    
    # High-risk activity (last 24 hours)
    last_24h = timezone.now() - timedelta(hours=24)
    stats['high_risk_24h'] = FinancialAuditLog.objects.filter(
        timestamp__gte=last_24h,
        risk_level__in=['HIGH', 'CRITICAL']
    ).count()
    
    # Top actions (last 7 days)
    top_actions = FinancialAuditLog.objects.filter(
        timestamp__date__gte=last_7_days
    ).values('action').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    stats['top_actions'] = [
        {
            'action': item['action'],
            'action_display': dict(FinancialAuditLog.FINANCIAL_ACTIONS).get(item['action'], item['action']),
            'count': item['count']
        }
        for item in top_actions
    ]
    
    return JsonResponse(stats)


# =============================================================================
# DETAIL STATS ENDPOINTS
# =============================================================================

@require_http_methods(["GET"])
def audit_log_detail(request, log_id):
    """Get detailed information for a specific audit log entry"""
    
    log = get_object_or_404(AuditLog, id=log_id)
    
    stats = {
        'id': str(log.id),
        'timestamp': log.timestamp.isoformat(),
        'action': log.action,
        'action_display': log.get_action_display(),
        'content_type': log.content_type,
        'object_id': log.object_id,
        'object_repr': log.object_repr,
        'user_id': log.user_id,
        'user_name': log.user_name,
        'user_email': log.user_email,
        'ip_address': log.ip_address,
        'user_agent': log.user_agent,
        'change_reason': log.change_reason,
        'session_key': log.session_key,
        'request_path': log.request_path,
        'has_changes': bool(log.changes),
        'changes': log.changes,
        'changes_display': log.get_changes_display(),
    }
    
    return JsonResponse(stats)


@require_http_methods(["GET"])
def financial_audit_log_detail(request, log_id):
    """Get detailed information for a specific financial audit log entry"""
    
    log = get_object_or_404(FinancialAuditLog, id=log_id)
    
    stats = {
        'id': log.id,
        'timestamp': log.timestamp.isoformat(),
        'action': log.action,
        'action_display': log.get_action_display(),
        'user_id': log.user_id,
        'user_name': log.user_name,
        'user_role': log.user_role,
        'ip_address': log.ip_address,
        'session_key': log.session_key,
        'risk_level': log.risk_level,
        'risk_level_display': log.get_risk_level_display(),
        'is_automated': log.is_automated,
        'batch_id': log.batch_id,
    }
    
    # Object information
    if log.content_type:
        stats['content_type'] = str(log.content_type)
        stats['object_id'] = log.object_id
        stats['object_description'] = log.object_description
    
    # Amount information
    if log.amount_involved:
        stats['amount_involved'] = str(log.amount_involved)
        stats['amount_involved_formatted'] = format_money(log.amount_involved)
        stats['currency'] = log.currency
    
    # Member information
    if log.member_id:
        stats['member_id'] = log.member_id
        stats['member_name'] = log.member_name
        stats['member_account_number'] = log.member_account_number
    
    # Period information
    if log.period_id:
        stats['period_id'] = log.period_id
        stats['period_name'] = log.period_name
    
    # Changes
    if log.old_values or log.new_values:
        stats['old_values'] = log.old_values
        stats['new_values'] = log.new_values
        stats['changes_summary'] = log.changes_summary
    
    # Compliance
    if log.compliance_flags:
        stats['compliance_flags'] = log.compliance_flags
    
    # Additional data
    if log.additional_data:
        stats['additional_data'] = log.additional_data
    
    if log.notes:
        stats['notes'] = log.notes
    
    return JsonResponse(stats)


# =============================================================================
# USER ACTIVITY ENDPOINTS
# =============================================================================

@require_http_methods(["GET"])
def user_activity_stats(request, user_id):
    """Get activity statistics for a specific user"""
    
    # Audit logs
    audit_logs = AuditLog.objects.filter(user_id=user_id)
    
    audit_stats = {
        'total_actions': audit_logs.count(),
        'create': audit_logs.filter(action='CREATE').count(),
        'update': audit_logs.filter(action='UPDATE').count(),
        'delete': audit_logs.filter(action='DELETE').count(),
        'first_action': None,
        'last_action': None,
    }
    
    first = audit_logs.order_by('timestamp').first()
    if first:
        audit_stats['first_action'] = first.timestamp.isoformat()
    
    last = audit_logs.order_by('-timestamp').first()
    if last:
        audit_stats['last_action'] = last.timestamp.isoformat()
    
    # Financial audit logs
    financial_logs = FinancialAuditLog.objects.filter(user_id=user_id)
    
    financial_aggregates = financial_logs.aggregate(
        total_amount=Sum('amount_involved'),
        avg_amount=Avg('amount_involved')
    )
    
    financial_stats = {
        'total_actions': financial_logs.count(),
        'total_amount': str(financial_aggregates['total_amount'] or Decimal('0.00')),
        'total_amount_formatted': format_money(financial_aggregates['total_amount'] or Decimal('0.00')),
        'avg_amount': str(financial_aggregates['avg_amount'] or Decimal('0.00')),
        'avg_amount_formatted': format_money(financial_aggregates['avg_amount'] or Decimal('0.00')),
        'low_risk': financial_logs.filter(risk_level='LOW').count(),
        'medium_risk': financial_logs.filter(risk_level='MEDIUM').count(),
        'high_risk': financial_logs.filter(risk_level='HIGH').count(),
        'critical_risk': financial_logs.filter(risk_level='CRITICAL').count(),
        'automated': financial_logs.filter(is_automated=True).count(),
        'manual': financial_logs.filter(is_automated=False).count(),
    }
    
    # Recent activity (last 7 days)
    last_7_days = timezone.now() - timedelta(days=7)
    recent_stats = {
        'audit_logs_7d': audit_logs.filter(timestamp__gte=last_7_days).count(),
        'financial_logs_7d': financial_logs.filter(timestamp__gte=last_7_days).count(),
    }
    
    # Most frequent actions
    top_actions = financial_logs.values('action').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    stats = {
        'user_id': user_id,
        'audit': audit_stats,
        'financial': financial_stats,
        'recent': recent_stats,
        'top_actions': [
            {
                'action': item['action'],
                'action_display': dict(FinancialAuditLog.FINANCIAL_ACTIONS).get(item['action'], item['action']),
                'count': item['count']
            }
            for item in top_actions
        ],
    }
    
    return JsonResponse(stats)


# =============================================================================
# TIMELINE ENDPOINTS
# =============================================================================

@require_http_methods(["GET"])
def audit_timeline(request):
    """Get audit log activity timeline (by day)"""
    
    # Parse date range
    filters = parse_filters(request, ['date_from', 'date_to'])
    
    date_from = filters['date_from']
    date_to = filters['date_to']
    
    # Default to last 30 days if not specified
    if not date_to:
        date_to = timezone.now().date()
    if not date_from:
        date_from = date_to - timedelta(days=30)
    
    # Get daily counts
    timeline = AuditLog.objects.filter(
        timestamp__date__gte=date_from,
        timestamp__date__lte=date_to
    ).annotate(
        date=TruncDate('timestamp')
    ).values('date').annotate(
        total=Count('id'),
        creates=Count('id', filter=Q(action='CREATE')),
        updates=Count('id', filter=Q(action='UPDATE')),
        deletes=Count('id', filter=Q(action='DELETE'))
    ).order_by('date')
    
    data = {
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
        'timeline': [
            {
                'date': item['date'].isoformat(),
                'total': item['total'],
                'creates': item['creates'],
                'updates': item['updates'],
                'deletes': item['deletes'],
            }
            for item in timeline
        ]
    }
    
    return JsonResponse(data)


@require_http_methods(["GET"])
def financial_audit_timeline(request):
    """Get financial audit log activity timeline (by day)"""
    
    # Parse filters
    filters = parse_filters(request, ['date_from', 'date_to', 'risk_level'])
    
    date_from = filters['date_from']
    date_to = filters['date_to']
    risk_level = filters['risk_level']
    
    # Default to last 30 days if not specified
    if not date_to:
        date_to = timezone.now().date()
    if not date_from:
        date_from = date_to - timedelta(days=30)
    
    # Build queryset
    queryset = FinancialAuditLog.objects.filter(
        timestamp__date__gte=date_from,
        timestamp__date__lte=date_to
    )
    
    if risk_level:
        queryset = queryset.filter(risk_level=risk_level)
    
    # Get daily counts and amounts
    timeline = queryset.annotate(
        date=TruncDate('timestamp')
    ).values('date').annotate(
        total=Count('id'),
        amount=Sum('amount_involved'),
        low_risk=Count('id', filter=Q(risk_level='LOW')),
        medium_risk=Count('id', filter=Q(risk_level='MEDIUM')),
        high_risk=Count('id', filter=Q(risk_level='HIGH')),
        critical_risk=Count('id', filter=Q(risk_level='CRITICAL')),
        automated=Count('id', filter=Q(is_automated=True))
    ).order_by('date')
    
    data = {
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
        'timeline': [
            {
                'date': item['date'].isoformat(),
                'total': item['total'],
                'amount': str(item['amount'] or Decimal('0.00')),
                'amount_formatted': format_money(item['amount'] or Decimal('0.00')),
                'low_risk': item['low_risk'],
                'medium_risk': item['medium_risk'],
                'high_risk': item['high_risk'],
                'critical_risk': item['critical_risk'],
                'automated': item['automated'],
            }
            for item in timeline
        ]
    }
    
    return JsonResponse(data)


# =============================================================================
# OBJECT HISTORY ENDPOINT
# =============================================================================

@require_http_methods(["GET"])
def object_history(request):
    """Get audit history for a specific object"""
    
    content_type = request.GET.get('content_type')
    object_id = request.GET.get('object_id')
    
    if not content_type or not object_id:
        return JsonResponse({'error': 'content_type and object_id required'}, status=400)
    
    # Get audit logs
    logs = AuditLog.objects.filter(
        content_type=content_type,
        object_id=object_id
    ).order_by('-timestamp')
    
    # Paginate
    logs_page, paginator = paginate_queryset(request, logs, per_page=20)
    
    history = [
        {
            'id': str(log.id),
            'timestamp': log.timestamp.isoformat(),
            'action': log.action,
            'action_display': log.get_action_display(),
            'user_name': log.user_name,
            'user_email': log.user_email,
            'changes': log.changes,
            'change_reason': log.change_reason,
        }
        for log in logs_page
    ]
    
    data = {
        'content_type': content_type,
        'object_id': object_id,
        'total_changes': logs.count(),
        'history': history,
        'has_next': logs_page.has_next() if hasattr(logs_page, 'has_next') else False,
        'has_previous': logs_page.has_previous() if hasattr(logs_page, 'has_previous') else False,
    }
    
    return JsonResponse(data)


# =============================================================================
# COMPLIANCE REPORTING ENDPOINTS
# =============================================================================

@require_http_methods(["GET"])
def compliance_report(request):
    """Generate compliance report from financial audit logs"""
    
    # Parse filters
    filters = parse_filters(request, ['date_from', 'date_to', 'risk_level'])
    
    date_from = filters['date_from']
    date_to = filters['date_to']
    risk_level = filters['risk_level']
    
    # Default to last 30 days
    if not date_to:
        date_to = timezone.now().date()
    if not date_from:
        date_from = date_to - timedelta(days=30)
    
    # Build queryset
    queryset = FinancialAuditLog.objects.filter(
        timestamp__date__gte=date_from,
        timestamp__date__lte=date_to
    )
    
    if risk_level:
        queryset = queryset.filter(risk_level=risk_level)
    
    # Get logs with compliance flags
    flagged_logs = queryset.exclude(compliance_flags=[])
    
    report = {
        'period': {
            'from': date_from.isoformat(),
            'to': date_to.isoformat(),
        },
        'summary': {
            'total_logs': queryset.count(),
            'flagged_logs': flagged_logs.count(),
            'high_risk': queryset.filter(risk_level='HIGH').count(),
            'critical_risk': queryset.filter(risk_level='CRITICAL').count(),
        },
        'by_action': {},
        'by_user': {},
        'flagged_entries': [],
    }
    
    # Action breakdown
    action_stats = flagged_logs.values('action').annotate(
        count=Count('id')
    ).order_by('-count')
    
    report['by_action'] = {
        item['action']: item['count']
        for item in action_stats
    }
    
    # User breakdown
    user_stats = flagged_logs.values('user_name', 'user_id').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    report['by_user'] = [
        {
            'user_name': item['user_name'],
            'user_id': item['user_id'],
            'count': item['count']
        }
        for item in user_stats
    ]
    
    # Recent flagged entries
    recent_flagged = flagged_logs.order_by('-timestamp')[:20]
    
    report['flagged_entries'] = [
        {
            'id': log.id,
            'timestamp': log.timestamp.isoformat(),
            'action': dict(FinancialAuditLog.FINANCIAL_ACTIONS).get(log.action, log.action),
            'risk_level': log.get_risk_level_display(),
            'user_name': log.user_name,
            'compliance_flags': log.compliance_flags,
            'amount': str(log.amount_involved) if log.amount_involved else None,
        }
        for log in recent_flagged
    ]
    
    return JsonResponse(report)