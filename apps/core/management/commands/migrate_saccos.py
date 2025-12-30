# management/commands/migrate_saccos.py

"""
Custom Django management command to migrate SACCO databases.

USAGE EXAMPLES:
===============

# 1. Migrate all apps to all SACCO databases
python manage.py migrate_saccos

# 2. Migrate only SACCO apps to all SACCOs
python manage.py migrate_saccos --sacco-apps-only

# 3. Migrate a specific app (loans) to all SACCOs
python manage.py migrate_saccos loans --sacco-apps-only

# 4. Migrate all apps to a specific SACCO
python manage.py migrate_saccos --only kojena_ltd

# 5. Migrate a specific app to specific SACCOs (comma-separated)
python manage.py migrate_saccos loans --only kojena_ltd,deon_ltd --sacco-apps-only

# 6. Show migration plan for an app on a specific SACCO (dry run)
python manage.py migrate_saccos loans --only kojena_ltd --plan

# 7. Fake migrations (mark as applied without running)
python manage.py migrate_saccos loans --only kojena_ltd --fake

# 8. Fake initial migrations (when tables already exist)
python manage.py migrate_saccos loans --only kojena_ltd --fake-initial

# 9. Migrate to a specific migration
python manage.py migrate_saccos loans 0003 --only kojena_ltd

# 10. Migrate all SACCO apps to all databases with verbosity
python manage.py migrate_saccos --sacco-apps-only --verbosity 2

# 11. List migrations without applying (plan mode)
python manage.py migrate_saccos --plan --sacco-apps-only
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.conf import settings
from django.db import connections
import logging

logger = logging.getLogger(__name__)

# List of apps that belong to SACCO databases
SACCO_APPS = [
    'core',
    'members',
    'savings',
    'dividends',
    'loans',
    'shares',
    'projects',
    'utils',
]

class Command(BaseCommand):
    help = 'Run migrations for all SACCO databases'

    def add_arguments(self, parser):
        parser.add_argument(
            'app_label', nargs='?', default=None,
            help='Optional app label to migrate'
        )
        parser.add_argument(
            'migration_name', nargs='?', default=None,
            help='Optional migration name to migrate to'
        )
        parser.add_argument(
            '--fake', action='store_true',
            help='Mark migrations as run without actually executing them'
        )
        parser.add_argument(
            '--plan', action='store_true',
            help='Show migration plan without executing it'
        )
        parser.add_argument(
            '--fake-initial', action='store_true',
            help='Mark initial migrations as applied if tables already exist'
        )
        parser.add_argument(
            '--sacco-apps-only', action='store_true',
            help='Only migrate apps that belong to SACCO databases'
        )
        parser.add_argument(
            '--only', type=str, default=None,
            help='Comma-separated list of SACCO database names to migrate (e.g., kojena_ltd,deon_ltd)'
        )
        parser.add_argument(
            '--skip', type=str, default=None,
            help='Comma-separated list of SACCO database names to skip'
        )
        parser.add_argument(
            '--check', action='store_true',
            help='Check if migrations are needed without applying them'
        )
        parser.add_argument(
            '--run-syncdb', action='store_true',
            help='Create tables for apps without migrations'
        )

    def handle(self, *args, **options):
        # Determine databases to migrate
        if options['only']:
            sacco_databases = [db.strip() for db in options['only'].split(',')]
            # Validate that specified databases exist
            invalid_dbs = [db for db in sacco_databases if db not in settings.DATABASES]
            if invalid_dbs:
                raise CommandError(f"Invalid database(s): {', '.join(invalid_dbs)}")
        else:
            # Get all SACCO databases (excluding 'default')
            sacco_databases = [
                db for db in settings.DATABASES.keys()
                if db != 'default'
            ]

        # Apply skip filter if provided
        if options['skip']:
            skip_dbs = [db.strip() for db in options['skip'].split(',')]
            sacco_databases = [db for db in sacco_databases if db not in skip_dbs]

        if not sacco_databases:
            self.stdout.write(self.style.WARNING('No SACCO databases found to migrate.'))
            return

        # Display header
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('SACCO DATABASE MIGRATION'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        # Determine apps to migrate
        app_label = options['app_label']
        if options['sacco_apps_only'] and app_label is None:
            # Migrate all SACCO apps
            apps_to_migrate = SACCO_APPS
            self.stdout.write(
                self.style.WARNING(f"\nMigrating SACCO apps only: {', '.join(apps_to_migrate)}")
            )
        elif app_label:
            apps_to_migrate = [app_label]
            if options['sacco_apps_only'] and app_label not in SACCO_APPS:
                self.stdout.write(
                    self.style.WARNING(
                        f"\nWarning: '{app_label}' is not in the SACCO apps list. "
                        f"SACCO apps are: {', '.join(SACCO_APPS)}"
                    )
                )
        else:
            apps_to_migrate = None  # All apps
            self.stdout.write(self.style.WARNING('\nMigrating ALL apps'))

        # Display database list
        self.stdout.write(
            self.style.WARNING(f"\nDatabases to migrate ({len(sacco_databases)}): {', '.join(sacco_databases)}\n")
        )

        # Prepare migration command options
        cmd_options = {
            'verbosity': options.get('verbosity', 1),
            'fake': options['fake'],
            'plan': options['plan'],
            'fake_initial': options['fake_initial'],
            'run_syncdb': options['run_syncdb'],
            'check': options['check'],
        }

        # Track results
        success_count = 0
        error_count = 0
        errors = []

        # Loop through each SACCO database
        for idx, db in enumerate(sacco_databases, 1):
            if db not in settings.DATABASES:
                self.stderr.write(
                    self.style.ERROR(f"\n[{idx}/{len(sacco_databases)}] Database '{db}' not found in settings")
                )
                error_count += 1
                errors.append((db, "Database not found in settings"))
                continue

            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"\n{'=' * 70}\n"
                    f"[{idx}/{len(sacco_databases)}] Migrating database: {db}\n"
                    f"{'=' * 70}"
                )
            )

            cmd_options['database'] = db

            try:
                if apps_to_migrate:
                    # Migrate specific apps
                    for app in apps_to_migrate:
                        self.stdout.write(f"  → Migrating app: {app}")
                        call_command(
                            'migrate',
                            app,
                            *([options['migration_name']] if options['migration_name'] else []),
                            **cmd_options
                        )
                else:
                    # Migrate all apps
                    call_command('migrate', **cmd_options)

                success_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Successfully migrated {db}")
                )

            except Exception as e:
                error_count += 1
                error_msg = str(e)
                errors.append((db, error_msg))
                self.stderr.write(
                    self.style.ERROR(f"✗ Error migrating {db}: {error_msg}")
                )

        # Display summary
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('MIGRATION SUMMARY'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(f"\nTotal databases: {len(sacco_databases)}")
        self.stdout.write(self.style.SUCCESS(f"Successful: {success_count}"))
        
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"Failed: {error_count}"))
            self.stdout.write(self.style.ERROR('\nErrors:'))
            for db, error in errors:
                self.stdout.write(self.style.ERROR(f"  - {db}: {error}"))
        else:
            self.stdout.write(self.style.SUCCESS("\n✓ All migrations completed successfully!"))

        self.stdout.write(self.style.SUCCESS('=' * 70 + '\n'))

        # Return appropriate exit code
        if error_count > 0:
            raise CommandError(f'Migration failed for {error_count} database(s)')