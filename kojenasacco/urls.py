"""
URL configuration for schoolara project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Django admin
    path('admin/', admin.site.urls),

    # Core app – homepage / dashboard
    path('', include(('core.urls', 'core'), namespace='core')),

    # Accounts app – authentication & profiles
    path('accounts/', include(('accounts.urls', 'accounts'), namespace='accounts')),

    # Members app
    path('members/', include(('members.urls', 'members'), namespace='members')),

    # Savings app
    path('savings/', include(('savings.urls', 'savings'), namespace='savings')),

    # Dividends app
    path('dividends/', include(('dividends.urls', 'dividends'), namespace='dividends')),

    # Loans app
    path('loans/', include(('loans.urls', 'loans'), namespace='loans')),

    # Projects app
    path('projects/', include(('projects.urls', 'projects'), namespace='projects')),

    # Utils app (helpers, APIs, shared tools)
    path('utils/', include(('utils.urls', 'utils'), namespace='utils')),
]

# Media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
