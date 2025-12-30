# shares/apps.py

from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class SharesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "shares"
    verbose_name = "Share Capital Management"
    
    def ready(self):
        """
        Import signals when the app is ready.
        This ensures all signal handlers are registered.
        """
        import shares.signals
        logger.info("✓ Shares app signals registered successfully")