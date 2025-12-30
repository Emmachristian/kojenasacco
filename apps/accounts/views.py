# accounts/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib.auth.models import User
import json
import logging

from .models import UserProfile, Sacco, MemberAccount
from .forms import (
    LoginForm, 
    UserRegistrationForm, 
    UserProfileForm,
    CustomPasswordChangeForm,
    SaccoForm,
    MemberAccountForm,
    UserSearchForm
)

logger = logging.getLogger(__name__)


# =============================================================================
# AUTHENTICATION VIEWS
# =============================================================================

@never_cache
def login_view(request):
    """Handle user login"""
    
    # Redirect if already authenticated
    if request.user.is_authenticated:
        return redirect('core:home')
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        
        if form.is_valid():
            email = form.cleaned_data.get('username')  # username field contains email
            password = form.cleaned_data.get('password')
            remember_me = form.cleaned_data.get('remember_me', False)
            
            # Authenticate user
            user = authenticate(request, username=email, password=password)
            
            if user is not None:
                if user.is_active:
                    # Check if account is locked (via profile)
                    try:
                        profile = user.profile
                        if profile.account_locked_until and profile.account_locked_until > timezone.now():
                            messages.error(
                                request, 
                                "Your account has been locked due to multiple failed login attempts. "
                                "Please try again later or contact support."
                            )
                            return render(request, 'accounts/login.html', {'form': form})
                    except UserProfile.DoesNotExist:
                        pass  # No profile, skip lock check
                    
                    # Login user
                    login(request, user)
                    
                    # Record successful login (update last_activity in profile)
                    try:
                        profile = user.profile
                        profile.failed_login_attempts = 0
                        profile.account_locked_until = None
                        profile.last_activity = timezone.now()
                        profile.save(update_fields=['failed_login_attempts', 'account_locked_until', 'last_activity'])
                    except UserProfile.DoesNotExist:
                        pass
                    
                    # Handle remember me
                    if not remember_me:
                        request.session.set_expiry(0)  # Session expires on browser close
                    else:
                        request.session.set_expiry(1209600)  # 2 weeks
                    
                    # Handle next parameter
                    next_url = request.GET.get('next') or request.POST.get('next')
                    if next_url:
                        return redirect(next_url)
                    
                    messages.success(request, f"Welcome back, {user.get_full_name()}!")
                    logger.info(f"User {user.email} logged in successfully")
                    return redirect('core:home')
                else:
                    messages.error(request, "Your account has been disabled. Please contact support.")
                    logger.warning(f"Inactive account login attempt: {email}")
            else:
                # Record failed login attempt
                try:
                    user_obj = User.objects.get(email=email)
                    profile = user_obj.profile
                    profile.failed_login_attempts += 1
                    
                    # Lock account after 5 failed attempts (configurable)
                    if profile.failed_login_attempts >= 5:
                        profile.account_locked_until = timezone.now() + timezone.timedelta(minutes=30)
                        profile.save(update_fields=['failed_login_attempts', 'account_locked_until'])
                        messages.error(
                            request,
                            "Too many failed login attempts. Your account has been locked for 30 minutes."
                        )
                    else:
                        profile.save(update_fields=['failed_login_attempts'])
                        messages.error(request, "Invalid email or password. Please try again.")
                except User.DoesNotExist:
                    messages.error(request, "Invalid email or password. Please try again.")
                
                logger.warning(f"Failed login attempt for: {email}")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """Handle user logout"""
    user_email = request.user.email if request.user.is_authenticated else 'Unknown'
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    logger.info(f"User {user_email} logged out")
    return redirect('accounts:login')


def register_view(request):
    """Handle user registration"""
    
    if request.user.is_authenticated:
        return redirect('core:home')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        
        if form.is_valid():
            user = form.save()
            messages.success(
                request, 
                f"Account created successfully for {user.email}! You can now log in."
            )
            logger.info(f"New user registered: {user.email}")
            return redirect('accounts:login')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = UserRegistrationForm()
    
    return render(request, 'accounts/register.html', {'form': form})


# =============================================================================
# PROFILE & SETTINGS VIEWS
# =============================================================================

@login_required
def user_account_settings(request):
    """View for user to edit their account settings and profile"""
    
    try:
        user_profile = request.user.profile
    except UserProfile.DoesNotExist:
        # Create profile if it doesn't exist
        user_profile = UserProfile.objects.create(
            user=request.user,
            role='CUSTOMER_SERVICE'  # Default role
        )
        logger.info(f"Created profile for user: {request.user.email}")
    
    if request.method == 'POST':
        form = UserProfileForm(
            request.POST, 
            request.FILES, 
            instance=user_profile,
            user=request.user
        )
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            logger.info(f"Profile updated for user: {request.user.email}")
            return redirect('accounts:user_account_settings')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserProfileForm(instance=user_profile, user=request.user)
    
    context = {
        'form': form,
        'user_profile': user_profile,
    }
    
    return render(request, 'accounts/user_account_settings.html', context)


@login_required
def change_password(request):
    """Handle password change"""
    
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        
        if form.is_valid():
            user = form.save()
            
            # Update password_changed_at in profile
            try:
                profile = user.profile
                profile.password_changed_at = timezone.now()
                profile.save(update_fields=['password_changed_at'])
            except UserProfile.DoesNotExist:
                pass
            
            # Update session to prevent logout
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            logger.info(f"Password changed for user: {request.user.email}")
            return redirect('accounts:user_account_settings')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomPasswordChangeForm(request.user)
    
    return render(request, 'accounts/change_password.html', {'form': form})


@login_required
@require_POST
def save_theme_preference(request):
    """Save user theme preferences via AJAX"""
    
    try:
        data = json.loads(request.body)
        setting = data.get('setting')
        value = data.get('value')
        
        if not setting:
            return JsonResponse({'success': False, 'error': 'Setting required'})
        
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Profile not found'})
        
        # Boolean settings
        if setting in ['fixed_header', 'fixed_sidebar', 'fixed_footer']:
            bool_value = value.lower() == 'true' if isinstance(value, str) else bool(value)
            setattr(profile, setting, bool_value)
        
        # String settings
        elif setting in ['theme_color', 'header_class', 'sidebar_class', 'page_tabs_style']:
            setattr(profile, setting, value or '')
        
        else:
            return JsonResponse({'success': False, 'error': f'Unknown setting: {setting}'})
        
        profile.save()
        logger.info(f"Theme preference updated for {request.user.email}: {setting}={value}")
        
        return JsonResponse({
            'success': True,
            'message': f'{setting} updated',
            'setting': setting,
            'value': value
        })
        
    except Exception as e:
        logger.error(f"Error saving theme preference: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# =============================================================================
# USER MANAGEMENT VIEWS (Admin)
# =============================================================================

def is_admin(user):
    """Check if user is admin via profile"""
    if not user.is_authenticated:
        return False
    
    # Superuser is always admin
    if user.is_superuser or user.is_staff:
        return True
    
    # Check profile
    try:
        return user.profile.is_admin_user()
    except UserProfile.DoesNotExist:
        return False


@login_required
@user_passes_test(is_admin)
def user_list(request):
    """List all users with search and filter"""
    
    form = UserSearchForm(request.GET)
    users = User.objects.select_related('profile', 'profile__sacco').all()
    
    # Apply filters
    if form.is_valid():
        search = form.cleaned_data.get('search')
        if search:
            users = users.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(username__icontains=search) |
                Q(profile__employee_id__icontains=search)
            )
        
        role = form.cleaned_data.get('role')
        if role:
            users = users.filter(profile__role=role)
        
        sacco = form.cleaned_data.get('sacco')
        if sacco:
            users = users.filter(profile__sacco=sacco)
        
        is_active = form.cleaned_data.get('is_active')
        if is_active:
            users = users.filter(is_active=(is_active == 'true'))
        
        employment_type = form.cleaned_data.get('employment_type')
        if employment_type:
            users = users.filter(profile__employment_type=employment_type)
    
    # Pagination
    paginator = Paginator(users, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'form': form,
        'page_obj': page_obj,
        'users': page_obj,
        'total_users': users.count(),
    }
    
    return render(request, 'accounts/user_management/user_list.html', context)


@login_required
@user_passes_test(is_admin)
def user_detail(request, user_id):
    """View user details"""
    
    user = get_object_or_404(User.objects.select_related('profile', 'profile__sacco'), pk=user_id)
    member_accounts = user.member_accounts.select_related('sacco').all()
    
    context = {
        'user_obj': user,
        'member_accounts': member_accounts,
    }
    
    return render(request, 'accounts/user_management/user_detail.html', context)


@login_required
@user_passes_test(is_admin)
def user_create(request):
    """Create new user"""
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        
        if form.is_valid():
            user = form.save()
            messages.success(request, f'User {user.email} created successfully!')
            logger.info(f"User {user.email} created by admin {request.user.email}")
            return redirect('accounts:user_detail', user_id=user.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'accounts/user_management/user_form.html', {
        'form': form,
        'action': 'Create'
    })


@login_required
@user_passes_test(is_admin)
def user_edit(request, user_id):
    """Edit existing user"""
    
    user = get_object_or_404(User, pk=user_id)
    
    # Ensure profile exists
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user, role='CUSTOMER_SERVICE')
    
    if request.method == 'POST':
        form = UserProfileForm(
            request.POST,
            request.FILES,
            instance=profile,
            user=user
        )
        
        if form.is_valid():
            form.save()
            messages.success(request, f'User {user.email} updated successfully!')
            logger.info(f"User {user.email} updated by admin {request.user.email}")
            return redirect('accounts:user_detail', user_id=user.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserProfileForm(instance=profile, user=user)
    
    return render(request, 'accounts/user_management/user_form.html', {
        'form': form,
        'user_obj': user,
        'action': 'Edit'
    })


@login_required
@user_passes_test(is_admin)
@require_POST
def user_toggle_active(request, user_id):
    """Toggle user active status"""
    
    user = get_object_or_404(User, pk=user_id)
    
    # Prevent disabling self
    if user == request.user:
        return JsonResponse({
            'success': False,
            'error': 'You cannot deactivate your own account'
        })
    
    user.is_active = not user.is_active
    user.save()
    
    action = 'activated' if user.is_active else 'deactivated'
    messages.success(request, f'User {user.email} {action} successfully!')
    logger.info(f"User {user.email} {action} by admin {request.user.email}")
    
    return JsonResponse({
        'success': True,
        'is_active': user.is_active,
        'message': f'User {action}'
    })


@login_required
@user_passes_test(is_admin)
@require_POST
def user_unlock_account(request, user_id):
    """Unlock a locked user account"""
    
    user = get_object_or_404(User, pk=user_id)
    
    try:
        profile = user.profile
        profile.failed_login_attempts = 0
        profile.account_locked_until = None
        profile.save(update_fields=['failed_login_attempts', 'account_locked_until'])
        
        messages.success(request, f'Account {user.email} unlocked successfully!')
        logger.info(f"Account {user.email} unlocked by admin {request.user.email}")
        
        return JsonResponse({
            'success': True,
            'message': 'Account unlocked'
        })
    except UserProfile.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'User profile not found'
        }, status=404)


# =============================================================================
# SACCO MANAGEMENT VIEWS
# =============================================================================

@login_required
@user_passes_test(is_admin)
def sacco_list(request):
    """List all SACCOs"""
    
    saccos = Sacco.objects.annotate(
        staff_count=Count('staff_profiles', distinct=True),
        member_count=Count('member_accounts', distinct=True)
    ).all()
    
    # Search
    search = request.GET.get('search')
    if search:
        saccos = saccos.filter(
            Q(full_name__icontains=search) |
            Q(short_name__icontains=search) |
            Q(abbreviation__icontains=search)
        )
    
    paginator = Paginator(saccos, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'saccos': page_obj,
    }
    
    return render(request, 'accounts/user_management/sacco_list.html', context)


@login_required
@user_passes_test(is_admin)
def sacco_detail(request, sacco_id):
    """View SACCO details"""
    
    sacco = get_object_or_404(
        Sacco.objects.annotate(
            staff_count=Count('staff_profiles', distinct=True),
            member_count=Count('member_accounts', distinct=True)
        ),
        pk=sacco_id
    )
    
    staff_profiles = sacco.staff_profiles.select_related('user').all()[:10]
    member_accounts = sacco.member_accounts.select_related('user').all()[:10]
    
    context = {
        'sacco': sacco,
        'staff_profiles': staff_profiles,
        'member_accounts': member_accounts,
    }
    
    return render(request, 'accounts/user_management/sacco_detail.html', context)


@login_required
@user_passes_test(is_admin)
def sacco_create(request):
    """Create new SACCO"""
    
    if request.method == 'POST':
        form = SaccoForm(request.POST, request.FILES)
        
        if form.is_valid():
            sacco = form.save()
            messages.success(request, f'SACCO {sacco.full_name} created successfully!')
            logger.info(f"SACCO {sacco.full_name} created by admin {request.user.email}")
            return redirect('accounts:sacco_detail', sacco_id=sacco.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SaccoForm()
    
    return render(request, 'accounts/user_management/sacco_form.html', {
        'form': form,
        'action': 'Create'
    })


@login_required
@user_passes_test(is_admin)
def sacco_edit(request, sacco_id):
    """Edit existing SACCO"""
    
    sacco = get_object_or_404(Sacco, pk=sacco_id)
    
    if request.method == 'POST':
        form = SaccoForm(request.POST, request.FILES, instance=sacco)
        
        if form.is_valid():
            sacco = form.save()
            messages.success(request, f'SACCO {sacco.full_name} updated successfully!')
            logger.info(f"SACCO {sacco.full_name} updated by admin {request.user.email}")
            return redirect('accounts:sacco_detail', sacco_id=sacco.pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SaccoForm(instance=sacco)
    
    return render(request, 'accounts/user_management/sacco_form.html', {
        'form': form,
        'sacco': sacco,
        'action': 'Edit'
    })


# =============================================================================
# MEMBER ACCOUNT VIEWS
# =============================================================================

@login_required
def member_account_list(request):
    """List member accounts for current user or all (if admin)"""
    
    try:
        is_user_admin = request.user.profile.is_admin_user()
    except UserProfile.DoesNotExist:
        is_user_admin = request.user.is_superuser or request.user.is_staff
    
    if is_user_admin:
        member_accounts = MemberAccount.objects.select_related('user', 'sacco').all()
    else:
        member_accounts = request.user.member_accounts.select_related('sacco').all()
    
    context = {
        'member_accounts': member_accounts,
    }
    
    return render(request, 'accounts/user_management/member_account_list.html', context)