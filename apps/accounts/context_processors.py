# accounts/context_processors.py

from accounts.models import Sacco
import logging

logger = logging.getLogger(__name__)


def active_sacco(request):
    """
    Adds the current active SACCO to all templates.
    """
    sacco = None
    if request.user.is_authenticated:
        # Get user's SACCO through profile
        try:
            profile = getattr(request.user, 'profile', None)
            if profile:
                sacco = profile.sacco
            
            # Log if user has no SACCO assigned
            if not sacco:
                logger.warning(f"User {request.user.email} has no SACCO assigned")
        except Exception as e:
            logger.debug(f"Error getting user SACCO: {e}")
    
    return {'active_sacco': sacco}


def user_context(request):
    """
    Provides user-specific context including profile and theme preferences.
    """
    context = {}
    
    if request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        
        # Basic user info
        context['user_first_name'] = request.user.first_name
        context['user_last_name'] = request.user.last_name
        context['user_full_name'] = request.user.get_full_name()
        context['user_email'] = request.user.email
        
        # User permissions - USE PROFILE METHODS, NOT USER METHODS
        if profile:
            context['user_type'] = profile.get_role_display()
            context['user_type_code'] = profile.role
            context['is_admin'] = profile.is_admin_user()
            context['can_approve_loans'] = profile.can_approve_loans()
            context['can_manage_finances'] = profile.can_manage_finances()
            context['can_manage_members'] = profile.can_manage_members()
            
            # Profile-specific info
            context['user_profile_pic'] = profile.photo.url if profile.photo else None
            context['user_sacco'] = profile.sacco
            context['user_department'] = profile.department
            context['user_position'] = profile.position
            context['user_employee_id'] = profile.employee_id
            
            # Theme preferences - CRITICAL FOR base.html
            context['fixed_header'] = profile.fixed_header
            context['fixed_sidebar'] = profile.fixed_sidebar
            context['fixed_footer'] = profile.fixed_footer
            context['theme_color'] = profile.theme_color
            context['header_class'] = profile.header_class
            context['sidebar_class'] = profile.sidebar_class
            context['page_tabs_style'] = profile.page_tabs_style
        else:
            # Default values if no profile
            context['user_type'] = 'User'
            context['user_type_code'] = None
            context['is_admin'] = request.user.is_staff or request.user.is_superuser
            context['can_approve_loans'] = request.user.is_staff or request.user.is_superuser
            context['can_manage_finances'] = request.user.is_staff or request.user.is_superuser
            context['can_manage_members'] = request.user.is_staff or request.user.is_superuser
            context['user_profile_pic'] = None
            context['user_sacco'] = None
            context['fixed_header'] = True
            context['fixed_sidebar'] = True
            context['fixed_footer'] = False
            context['theme_color'] = 'app-theme-white'
            context['header_class'] = ''
            context['sidebar_class'] = ''
            context['page_tabs_style'] = 'body-tabs-shadow'
    else:
        # Default values for anonymous users
        context['fixed_header'] = True
        context['fixed_sidebar'] = True
        context['fixed_footer'] = False
        context['theme_color'] = 'app-theme-white'
        context['header_class'] = ''
        context['sidebar_class'] = ''
        context['page_tabs_style'] = 'body-tabs-shadow'
    
    return context


def sacco_context(request):
    """
    Provides SACCO-specific context for branding and configuration.
    """
    context = {
        'sacco_name': None,
        'sacco_logo': None,
        'sacco_favicon': None,
        'sacco_brand_colors': {},
        'sacco_timezone': 'UTC',
        'sacco_currency': 'UGX',
    }
    
    if request.user.is_authenticated:
        try:
            profile = getattr(request.user, 'profile', None)
            sacco = profile.sacco if profile else None
            
            if sacco:
                context.update({
                    'sacco_name': sacco.full_name,
                    'sacco_short_name': sacco.short_name,
                    'sacco_abbreviation': sacco.abbreviation,
                    'sacco_logo': sacco.sacco_logo.url if sacco.sacco_logo else None,
                    'sacco_favicon': sacco.favicon.url if sacco.favicon else None,
                    'sacco_brand_colors': sacco.brand_colors or {},
                    'sacco_timezone': sacco.timezone,
                    'sacco_type': sacco.get_sacco_type_display(),
                    'sacco_address': sacco.address,
                    'sacco_contact': sacco.contact_phone,
                    'sacco_website': sacco.website,
                    'sacco_established': sacco.established_date,
                    'sacco_is_active': sacco.is_active_subscription,
                })
                
                # Get currency from financial settings
                try:
                    currency = sacco.get_currency()
                    context['sacco_currency'] = currency
                except Exception as e:
                    logger.warning(f"Could not get currency for SACCO {sacco.full_name}: {e}")
                    context['sacco_currency'] = 'UGX'
                
                # Check subscription status
                if sacco.subscription_end:
                    from datetime import date
                    context['subscription_active'] = sacco.is_active_subscription and sacco.subscription_end >= date.today()
                    context['subscription_end'] = sacco.subscription_end
                    context['subscription_plan'] = sacco.get_subscription_plan_display()
                else:
                    context['subscription_active'] = sacco.is_active_subscription
        except Exception as e:
            logger.error(f"Error loading SACCO context: {e}")
    
    return context


def theme_colors(request):
    """
    Provides comprehensive theme color configuration for templates.
    This includes color schemes, text color mappings, and theme options.
    """
    
    # Define color schemes with their properties
    COLOR_SCHEMES = {
        # Basic Bootstrap colors
        'primary': {'label': 'Primary Blue', 'text': 'light'},
        'secondary': {'label': 'Secondary Gray', 'text': 'light'},
        'success': {'label': 'Success Green', 'text': 'light'},
        'info': {'label': 'Info Cyan', 'text': 'light'},
        'warning': {'label': 'Warning Yellow', 'text': 'dark'},
        'danger': {'label': 'Danger Red', 'text': 'light'},
        'light': {'label': 'Light', 'text': 'dark'},
        'dark': {'label': 'Dark', 'text': 'light'},
        'focus': {'label': 'Focus Purple', 'text': 'light'},
        'alternate': {'label': 'Alternate', 'text': 'light'},
        
        # Gradient/Premium colors
        'vicious-stance': {'label': 'Vicious Stance', 'text': 'light'},
        'midnight-bloom': {'label': 'Midnight Bloom', 'text': 'light'},
        'night-sky': {'label': 'Night Sky', 'text': 'light'},
        'slick-carbon': {'label': 'Slick Carbon', 'text': 'light'},
        'asteroid': {'label': 'Asteroid', 'text': 'light'},
        'royal': {'label': 'Royal', 'text': 'light'},
        'warm-flame': {'label': 'Warm Flame', 'text': 'dark'},
        'night-fade': {'label': 'Night Fade', 'text': 'dark'},
        'sunny-morning': {'label': 'Sunny Morning', 'text': 'dark'},
        'tempting-azure': {'label': 'Tempting Azure', 'text': 'dark'},
        'amy-crisp': {'label': 'Amy Crisp', 'text': 'dark'},
        'heavy-rain': {'label': 'Heavy Rain', 'text': 'dark'},
        'mean-fruit': {'label': 'Mean Fruit', 'text': 'dark'},
        'malibu-beach': {'label': 'Malibu Beach', 'text': 'light'},
        'deep-blue': {'label': 'Deep Blue', 'text': 'dark'},
        'ripe-malin': {'label': 'Ripe Malin', 'text': 'light'},
        'arielle-smile': {'label': 'Arielle Smile', 'text': 'light'},
        'plum-plate': {'label': 'Plum Plate', 'text': 'light'},
        'happy-fisher': {'label': 'Happy Fisher', 'text': 'dark'},
        'happy-itmeo': {'label': 'Happy Itmeo', 'text': 'light'},
        'mixed-hopes': {'label': 'Mixed Hopes', 'text': 'light'},
        'strong-bliss': {'label': 'Strong Bliss', 'text': 'light'},
        'grow-early': {'label': 'Grow Early', 'text': 'light'},
        'love-kiss': {'label': 'Love Kiss', 'text': 'light'},
        'premium-dark': {'label': 'Premium Dark', 'text': 'light'},
        'happy-green': {'label': 'Happy Green', 'text': 'light'},
    }
    
    # Separate basic and gradient colors for template organization
    basic_color_keys = [
        'primary', 'secondary', 'success', 'info', 
        'warning', 'danger', 'light', 'dark', 'focus', 'alternate'
    ]
    
    gradient_color_keys = [k for k in COLOR_SCHEMES.keys() if k not in basic_color_keys]
    
    # Build color lists with full information
    basic_colors = [
        {
            'key': key,
            'label': COLOR_SCHEMES[key]['label'],
            'text_class': COLOR_SCHEMES[key]['text'],
            'bg_class': f'bg-{key}',
            'full_class': f"bg-{key} header-text-{COLOR_SCHEMES[key]['text']}"
        }
        for key in basic_color_keys
    ]
    
    gradient_colors = [
        {
            'key': key,
            'label': COLOR_SCHEMES[key]['label'],
            'text_class': COLOR_SCHEMES[key]['text'],
            'bg_class': f'bg-{key}',
            'full_class': f"bg-{key} header-text-{COLOR_SCHEMES[key]['text']}"
        }
        for key in gradient_color_keys
    ]
    
    # Get current user's theme preferences
    current_theme = 'app-theme-white'
    current_page_tabs = 'body-tabs-shadow'
    
    if request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        if profile:
            current_theme = profile.theme_color
            current_page_tabs = profile.page_tabs_style
    
    # Theme options
    theme_options = [
        {
            'value': 'app-theme-white',
            'label': 'White Theme',
            'class': 'light',
            'active': current_theme == 'app-theme-white'
        },
        {
            'value': 'app-theme-gray',
            'label': 'Gray Theme',
            'class': 'light',
            'active': current_theme == 'app-theme-gray'
        },
        {
            'value': 'app-theme-dark',
            'label': 'Dark Theme',
            'class': 'dark',
            'active': current_theme == 'app-theme-dark'
        },
    ]
    
    # Tab style options
    tab_style_options = [
        {
            'value': 'body-tabs-shadow',
            'label': 'Shadow',
            'active': current_page_tabs == 'body-tabs-shadow'
        },
        {
            'value': 'body-tabs-line',
            'label': 'Line',
            'active': current_page_tabs == 'body-tabs-line'
        },
    ]
    
    # Helper function to get text class for a color
    def get_text_class(color_key):
        return COLOR_SCHEMES.get(color_key, {}).get('text', 'light')
    
    return {
        'color_schemes': COLOR_SCHEMES,
        'basic_colors': basic_colors,
        'gradient_colors': gradient_colors,
        'all_colors': basic_colors + gradient_colors,
        'theme_options': theme_options,
        'tab_style_options': tab_style_options,
        'get_text_class': get_text_class,
        'current_theme': current_theme,
        'current_page_tabs': current_page_tabs,
    }