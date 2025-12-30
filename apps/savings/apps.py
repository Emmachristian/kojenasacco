# savings/apps.py

from django.apps import AppConfig


class SavingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "savings"
    verbose_name = "Savings Management"
    
    def ready(self):
        """
        Import signals when the app is ready.
        This ensures all signal handlers are registered.
        """
        # Import signals to register them
        import savings.signals
        
        # Optional: Call the ready function from signals if you have one
        # savings.signals.ready()