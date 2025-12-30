# members/apps.py

from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class MembersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "members"
    verbose_name = "Member Management"
    
    def ready(self):
        """
        Import signals when the app is ready.
        This ensures all signal handlers are registered.
        """
        import members.signals
        logger.info("✓ Members app signals registered successfully")