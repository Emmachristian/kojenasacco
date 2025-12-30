# accounts/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse
from .models import Sacco, UserProfile, MemberAccount, UserManagementSettings


# =============================================================================
# SACCO ADMIN
# =============================================================================

@admin.register(Sacco)
class SaccoAdmin(admin.ModelAdmin):
    list_display = [
        'full_name', 
        'abbreviation', 
        'sacco_type',
        'membership_type',
        'subscription_plan',
        'subscription_status',
        'active_staff',
        'active_members',
        'established_date',
        'is_active_subscription'
    ]
    list_filter = [
        'sacco_type',
        'membership_type',
        'common_bond',
        'subscription_plan', 
        'is_active_subscription',
        'country',
        'established_date'
    ]
    search_fields = [
        'full_name', 
        'short_name', 
        'abbreviation', 
        'domain',
        'database_alias',
        'contact_phone',
        'registration_number'
    ]
    readonly_fields = [
        'created_at', 
        'updated_at',
        'active_staff_count_display',
        'active_members_count_display'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'full_name',
                'short_name',
                'abbreviation',
                'description',
            )
        }),
        ('System Configuration', {
            'fields': (
                'domain',
                'database_alias',
                'timezone',
            )
        }),
        ('SACCO Classification', {
            'fields': (
                'sacco_type',
                'membership_type',
                'common_bond',
            )
        }),
        ('Contact Information', {
            'fields': (
                'address',
                'city',
                'state_province',
                'postal_code',
                'country',
                'contact_phone',
                'alternative_contact',
            )
        }),
        ('Digital Presence', {
            'fields': (
                'website',
                'facebook_page',
                'twitter_handle',
                'instagram_handle',
            ),
            'classes': ('collapse',)
        }),
        ('Branding', {
            'fields': (
                'sacco_logo',
                'favicon',
                'brand_colors',
            ),
            'classes': ('collapse',)
        }),
        ('Administrative Details', {
            'fields': (
                'established_date',
                'registration_number',
                'license_number',
                'operating_hours',
            )
        }),
        ('Subscription', {
            'fields': (
                'subscription_plan',
                'subscription_start',
                'subscription_end',
                'is_active_subscription',
            )
        }),
        ('Statistics', {
            'fields': (
                'active_staff_count_display',
                'active_members_count_display',
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def subscription_status(self, obj):
        if obj.is_active_subscription:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Active</span>'
            )
        return format_html(
            '<span style="color: red; font-weight: bold;">✗ Inactive</span>'
        )
    subscription_status.short_description = 'Status'
    
    def active_staff(self, obj):
        count = obj.active_users_count
        return format_html(
            '<span style="font-weight: bold;">{}</span>',
            count
        )
    active_staff.short_description = 'Staff'
    
    def active_members(self, obj):
        count = MemberAccount.objects.filter(sacco=obj, is_active=True).count()
        return format_html(
            '<span style="font-weight: bold;">{}</span>',
            count
        )
    active_members.short_description = 'Members'
    
    def active_staff_count_display(self, obj):
        if obj.pk:
            count = obj.active_users_count
            return format_html(
                '<strong>{}</strong> active staff member(s)',
                count
            )
        return '-'
    active_staff_count_display.short_description = 'Active Staff'
    
    def active_members_count_display(self, obj):
        if obj.pk:
            count = MemberAccount.objects.filter(sacco=obj, is_active=True).count()
            return format_html(
                '<strong>{}</strong> active member(s)',
                count
            )
        return '-'
    active_members_count_display.short_description = 'Active Members'


# =============================================================================
# USER PROFILE INLINE
# =============================================================================

# =============================================================================
# USER PROFILE INLINE
# =============================================================================

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name = 'Profile'
    verbose_name_plural = 'Profile'
    fk_name = 'user'  # ← ADD THIS LINE
    
    fieldsets = (
        ('Role & SACCO', {
            'fields': ('sacco', 'role')
        }),
        ('Personal Information', {
            'fields': (
                'photo',
                'mobile',
                'date_of_birth',
                'gender',
            )
        }),
        ('Location', {
            'fields': (
                'address',
                'city',
                'country',
            ),
            'classes': ('collapse',)
        }),
        ('Localization', {
            'fields': (
                'language',
                'timezone',
            ),
            'classes': ('collapse',)
        }),
        ('Employment Details', {
            'fields': (
                'employee_id',
                'department',
                'position',
                'employment_type',
                'date_of_appointment',
                'qualification',
                'reports_to',
            ),
            'classes': ('collapse',)
        }),
        ('Emergency Contact', {
            'fields': (
                'emergency_contact_name',
                'emergency_contact_phone',
            ),
            'classes': ('collapse',)
        }),
        ('Theme Preferences', {
            'fields': (
                'theme_color',
                'fixed_header',
                'fixed_sidebar',
                'fixed_footer',
                'header_class',
                'sidebar_class',
                'page_tabs_style',
            ),
            'classes': ('collapse',)
        }),
        ('Security', {
            'fields': (
                'password_changed_at',
                'failed_login_attempts',
                'account_locked_until',
                'last_activity',
                'two_factor_enabled',
            ),
            'classes': ('collapse',)
        }),
    )

# =============================================================================
# MEMBER ACCOUNT INLINE
# =============================================================================

class MemberAccountInline(admin.TabularInline):
    model = MemberAccount
    extra = 0
    can_delete = True
    verbose_name = 'Member Account'
    verbose_name_plural = 'Member Accounts'
    
    fields = ['sacco', 'member_number', 'status', 'membership_date', 'is_active']
    readonly_fields = ['membership_date']


# =============================================================================
# CUSTOM USER ADMIN
# =============================================================================

class CustomUserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline, MemberAccountInline]
    
    list_display = [
        'username',
        'email',
        'full_name_display',
        'user_role',
        'sacco_display',
        'member_accounts_count',
        'is_active',
        'is_staff',
        'date_joined'
    ]
    
    list_filter = [
        'is_active',
        'is_staff',
        'is_superuser',
        'profile__role',
        'profile__sacco',
        'date_joined'
    ]
    
    search_fields = [
        'username',
        'email',
        'first_name',
        'last_name',
        'profile__employee_id',
        'profile__mobile',
        'member_accounts__member_number'
    ]
    
    ordering = ['-date_joined']
    
    fieldsets = (
        (None, {
            'fields': ('username', 'password')
        }),
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'email')
        }),
        ('Permissions', {
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
                'groups',
                'user_permissions'
            )
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined')
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username',
                'email',
                'first_name',
                'last_name',
                'password1',
                'password2',
                'is_active',
                'is_staff'
            ),
        }),
    )
    
    def full_name_display(self, obj):
        return obj.get_full_name() or '-'
    full_name_display.short_description = 'Full Name'
    
    def user_role(self, obj):
        if hasattr(obj, 'profile'):
            role = obj.profile.get_role_display()
            colors = {
                'SUPER_ADMIN': '#d32f2f',
                'SACCO_ADMIN': '#f57c00',
                'MANAGER': '#1976d2',
                'LOAN_OFFICER': '#388e3c',
                'ACCOUNTANT': '#7b1fa2',
                'CUSTOMER_SERVICE': '#00796b',
                'TELLER': '#616161',
            }
            color = colors.get(obj.profile.role, '#616161')
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                color,
                role
            )
        return '-'
    user_role.short_description = 'Role'
    
    def sacco_display(self, obj):
        if hasattr(obj, 'profile') and obj.profile.sacco:
            sacco = obj.profile.sacco
            url = reverse('admin:accounts_sacco_change', args=[sacco.id])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                sacco.abbreviation or sacco.short_name or sacco.full_name
            )
        return '-'
    sacco_display.short_description = 'SACCO'
    
    def member_accounts_count(self, obj):
        count = obj.member_accounts.count()
        if count > 0:
            return format_html(
                '<span style="font-weight: bold; color: #1976d2;">{}</span>',
                count
            )
        return '-'
    member_accounts_count.short_description = 'Member Accounts'


# =============================================================================
# USER PROFILE ADMIN
# =============================================================================

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'role',
        'sacco_display',
        'employee_id',
        'department',
        'position',
        'employment_type',
        'is_active_user'
    ]
    
    list_filter = [
        'role',
        'sacco',
        'employment_type',
        'department',
        'user__is_active',
        'language'
    ]
    
    search_fields = [
        'user__username',
        'user__email',
        'user__first_name',
        'user__last_name',
        'employee_id',
        'mobile',
        'department',
        'position'
    ]
    
    readonly_fields = ['created_at', 'updated_at', 'sacco_name']
    
    fieldsets = (
        ('User & SACCO', {
            'fields': ('user', 'sacco', 'role', 'sacco_name')
        }),
        ('Personal Information', {
            'fields': (
                'photo',
                'mobile',
                'date_of_birth',
                'gender',
            )
        }),
        ('Location', {
            'fields': (
                'address',
                'city',
                'country',
            )
        }),
        ('Localization', {
            'fields': (
                'language',
                'timezone',
            )
        }),
        ('Employment Details', {
            'fields': (
                'employee_id',
                'department',
                'position',
                'employment_type',
                'date_of_appointment',
                'qualification',
                'reports_to',
            )
        }),
        ('Emergency Contact', {
            'fields': (
                'emergency_contact_name',
                'emergency_contact_phone',
            )
        }),
        ('Theme Preferences', {
            'fields': (
                'theme_color',
                'fixed_header',
                'fixed_sidebar',
                'fixed_footer',
                'header_class',
                'sidebar_class',
                'page_tabs_style',
            ),
            'classes': ('collapse',)
        }),
        ('Security', {
            'fields': (
                'password_changed_at',
                'failed_login_attempts',
                'account_locked_until',
                'last_activity',
                'two_factor_enabled',
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def sacco_display(self, obj):
        if obj.sacco:
            url = reverse('admin:accounts_sacco_change', args=[obj.sacco.id])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.sacco.abbreviation or obj.sacco.short_name or obj.sacco.full_name
            )
        return '-'
    sacco_display.short_description = 'SACCO'
    
    def is_active_user(self, obj):
        if obj.user.is_active:
            return format_html(
                '<span style="color: green;">✓ Active</span>'
            )
        return format_html(
            '<span style="color: red;">✗ Inactive</span>'
        )
    is_active_user.short_description = 'Active'


# =============================================================================
# MEMBER ACCOUNT ADMIN
# =============================================================================

@admin.register(MemberAccount)
class MemberAccountAdmin(admin.ModelAdmin):
    list_display = [
        'member_number',
        'user_display',
        'sacco_display',
        'status',
        'membership_date',
        'is_active'
    ]
    
    list_filter = [
        'status',
        'is_active',
        'sacco',
        'membership_date'
    ]
    
    search_fields = [
        'member_number',
        'user__username',
        'user__email',
        'user__first_name',
        'user__last_name',
        'sacco__full_name'
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Member Information', {
            'fields': (
                'user',
                'sacco',
                'member_number',
            )
        }),
        ('Status', {
            'fields': (
                'status',
                'membership_date',
                'is_active',
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_display(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.user.get_full_name() or obj.user.username
        )
    user_display.short_description = 'User'
    
    def sacco_display(self, obj):
        url = reverse('admin:accounts_sacco_change', args=[obj.sacco.id])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.sacco.abbreviation or obj.sacco.short_name or obj.sacco.full_name
        )
    sacco_display.short_description = 'SACCO'


# =============================================================================
# USER MANAGEMENT SETTINGS ADMIN
# =============================================================================

@admin.register(UserManagementSettings)
class UserManagementSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'min_password_length',
        'password_expiry_days',
        'max_failed_login_attempts',
        'default_session_timeout_minutes'
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Password Policy', {
            'fields': (
                'min_password_length',
                'require_uppercase',
                'require_lowercase',
                'require_numbers',
                'require_special_chars',
                'password_expiry_days',
                'password_history_count',
            )
        }),
        ('Session Management', {
            'fields': (
                'default_session_timeout_minutes',
                'max_concurrent_sessions',
                'session_warning_minutes',
            )
        }),
        ('Account Security', {
            'fields': (
                'max_failed_login_attempts',
                'account_lockout_duration_minutes',
                'enable_two_factor_default',
                'force_password_change_on_first_login',
            )
        }),
        ('User Registration', {
            'fields': (
                'allow_user_registration',
                'require_admin_approval',
            )
        }),
        ('Notifications', {
            'fields': (
                'send_welcome_emails',
                'send_password_expiry_warnings',
                'password_expiry_warning_days',
            )
        }),
        ('Audit & Logging', {
            'fields': (
                'log_login_attempts',
                'log_permission_changes',
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        # Only allow one settings instance
        return not UserManagementSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of settings
        return False


# Unregister the default User admin and register custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)