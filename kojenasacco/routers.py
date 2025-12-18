# routers.py
import logging
import sys
from django.conf import settings
from django.db import connections

logger = logging.getLogger(__name__)


def get_current_db():
    """Import and call get_current_db from managers"""
    try:
        from .managers import get_current_db as _get_current_db
        return _get_current_db()
    except ImportError:
        logger.warning("Could not import get_current_db from managers")
        return None


class SaccoRouter:
    """Router to handle multi-database setup for SACCO system"""

    # Apps that should always use the default database
    default_apps = {
        'admin',
        'auth',
        'contenttypes',
        'sessions',
        'accounts',
    }
    
    # Apps that should use SACCO-specific databases
    sacco_apps = {
        'core',
        'members',           # SACCO members
        'loans',             # Loan management
        'savings',           # Savings accounts
        'shares',            # Share capital
        'dividends',         # Dividend management
        'transactions',      # Financial transactions
        'finance',           # Financial operations
        'hr',                # Human resources
        'messaging',         # Internal messaging
        'reports',           # Reporting
        'utils',             # Utilities
    }
    
    # Models that must always use default database
    always_default_models = {
        'accounts.user',
        'accounts.customuser',
        'accounts.usertype',
        'auth.user',
        'auth.group',
        'auth.permission',
        'core.company',      # Company/SACCO registry
        'core.sacco',        # SACCO registry (if separate)
    }

    def __init__(self):
        self._error_logged = False
        self._sacco_dbs = set()
        self._update_sacco_dbs()

    def _update_sacco_dbs(self):
        """Cache all SACCO databases from settings"""
        try:
            self._sacco_dbs = {
                db_name for db_name in settings.DATABASES.keys()
                if db_name != 'default' and db_name.startswith('sacco_')
            }
            logger.debug(f"SACCO databases: {self._sacco_dbs}")
        except Exception as e:
            logger.error(f"Error updating SACCO databases: {e}")
            self._sacco_dbs = set()

    def _should_use_default_db(self, model):
        """Check if a model should always use the default database"""
        label = f"{model._meta.app_label}.{model._meta.model_name}".lower()
        return label in self.always_default_models

    def _is_system_command(self):
        """Check if current command is a system management command"""
        cmds = ['makemigrations', 'migrate', 'showmigrations', 'sqlmigrate']
        return any(cmd in sys.argv for cmd in cmds)

    def db_for_read(self, model, **hints):
        """Determine which database to use for reads"""
        app_label = model._meta.app_label
        
        # Check if model should always use default
        if self._should_use_default_db(model) or app_label in self.default_apps:
            return 'default'
        
        # Check if model belongs to SACCO apps
        if app_label in self.sacco_apps:
            db = get_current_db()
            
            # Use current database if valid
            if db and db in connections and db != 'default':
                return db
            
            # Fallback to first SACCO database
            if self._sacco_dbs:
                fallback_db = sorted(self._sacco_dbs)[0]
                logger.debug(f"No current DB set, using fallback: {fallback_db}")
                return fallback_db
            
            # No valid SACCO database available
            logger.warning(f"No SACCO database available for {model._meta.label}")
            return None
        
        # Default to 'default' database for unknown apps
        return 'default'

    def db_for_write(self, model, **hints):
        """Determine which database to use for writes"""
        return self.db_for_read(model, **hints)

    def allow_relation(self, obj1, obj2, **hints):
        """Determine if a relationship between two objects should be allowed"""
        app1 = obj1._meta.app_label
        app2 = obj2._meta.app_label
        
        # Allow relations within default apps
        if (app1 in self.default_apps or self._should_use_default_db(obj1.__class__)) and \
           (app2 in self.default_apps or self._should_use_default_db(obj2.__class__)):
            return True
        
        # Allow relations within SACCO apps
        if app1 in self.sacco_apps and app2 in self.sacco_apps:
            return True
        
        # Allow cross-database relations between default and SACCO apps
        # (e.g., Member -> User, Loan -> User)
        if (app1 in self.default_apps and app2 in self.sacco_apps) or \
           (app2 in self.default_apps and app1 in self.sacco_apps):
            return True
        
        # Deny all other relations
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Control which apps/models can be migrated to which databases"""
        
        # Check for always-default models
        if model_name:
            label = f"{app_label}.{model_name}".lower()
            if label in self.always_default_models:
                return db == 'default'
        
        # Default apps should only migrate to default database
        if app_label in self.default_apps:
            return db == 'default'
        
        # SACCO apps should migrate to SACCO databases
        if app_label in self.sacco_apps:
            # NEVER migrate SACCO apps to default database
            if db == 'default':
                return False
            
            # Only allow migration to valid SACCO databases
            return db in self._sacco_dbs
        
        # Unknown apps default to 'default' database
        return db == 'default'
    
    def get_sacco_databases(self):
        """
        Public method to get list of SACCO databases.
        
        Returns:
            set: Set of SACCO database names
        """
        return self._sacco_dbs.copy()