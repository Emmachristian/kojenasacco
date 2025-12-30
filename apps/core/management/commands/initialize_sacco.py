# core/management/commands/initialize_sacco.py

"""
Initialize SACCO-specific data after database creation.

This command creates default data for SACCO databases including:
- SaccoConfiguration and FinancialSettings
- Payment methods
- Tax rates

USAGE EXAMPLES:
===============

# Initialize all SACCO databases
python manage.py initialize_sacco --all

# Initialize specific SACCO
python manage.py initialize_sacco --sacco tumaini_sacco

# Initialize with force (recreate existing data)
python manage.py initialize_sacco --sacco tumaini_sacco --force

# Dry run (show what would be created)
python manage.py initialize_sacco --sacco tumaini_sacco --dry-run

# Initialize only specific components
python manage.py initialize_sacco --sacco tumaini_sacco --only-settings
python manage.py initialize_sacco --sacco tumaini_sacco --only-payments

# Skip specific components
python manage.py initialize_sacco --all --skip-settings --skip-taxes

# Verbose output
python manage.py initialize_sacco --sacco tumaini_sacco --verbosity 2
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.apps import apps
from kojenasacco.managers import set_current_db
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Initialize SACCO-specific default data (settings, payment methods, tax rates, etc.)'

    def add_arguments(self, parser):
        # Target selection
        parser.add_argument(
            '--sacco',
            type=str,
            help='Database alias of SACCO to initialize (e.g., tumaini_sacco)'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Initialize all SACCO databases'
        )
        
        # Execution options
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recreation of existing data (deletes and recreates)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating it'
        )
        
        # Component selection (skip options)
        parser.add_argument(
            '--skip-settings',
            action='store_true',
            help='Skip FinancialSettings and SaccoConfiguration'
        )
        parser.add_argument(
            '--skip-payments',
            action='store_true',
            help='Skip payment methods creation'
        )
        parser.add_argument(
            '--skip-taxes',
            action='store_true',
            help='Skip tax rates creation'
        )
        
        # Component selection (only options)
        parser.add_argument(
            '--only-settings',
            action='store_true',
            help='Initialize only settings'
        )
        parser.add_argument(
            '--only-payments',
            action='store_true',
            help='Initialize only payment methods'
        )
        parser.add_argument(
            '--only-taxes',
            action='store_true',
            help='Initialize only tax rates'
        )

    def handle(self, *args, **options):
        # Determine which databases to initialize
        if options['all']:
            sacco_dbs = [db for db in settings.DATABASES.keys() if db != 'default']
        elif options['sacco']:
            sacco_dbs = [options['sacco']]
            if options['sacco'] not in settings.DATABASES:
                raise CommandError(f"Database '{options['sacco']}' not found in settings")
        else:
            raise CommandError("Must specify either --sacco or --all")

        if not sacco_dbs:
            self.stdout.write(self.style.WARNING('No SACCO databases found.'))
            return

        # Header
        self.stdout.write(self.style.SUCCESS('='*80))
        self.stdout.write(self.style.SUCCESS('SACCO INITIALIZATION'))
        self.stdout.write(self.style.SUCCESS('='*80))
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('\n⚠️  DRY RUN MODE - No data will be created\n'))
        
        if options['force']:
            self.stdout.write(self.style.WARNING('⚠️  FORCE MODE - Existing data will be deleted and recreated\n'))

        success_count = 0
        error_count = 0
        errors = []

        for idx, db_name in enumerate(sacco_dbs, 1):
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"\n{'='*80}\n[{idx}/{len(sacco_dbs)}] Initializing: {db_name}\n{'='*80}"
            ))

            try:
                # Get SACCO instance from default database
                Sacco = apps.get_model('accounts', 'Sacco')
                sacco = Sacco.objects.using('default').filter(database_alias=db_name).first()
                
                if not sacco:
                    self.stdout.write(self.style.WARNING(
                        f"⚠️  No SACCO record found for database '{db_name}'. "
                        f"Using default configuration (SAVINGS_CREDIT)."
                    ))

                # Initialize
                stats = self._initialize_sacco(
                    db_name, 
                    sacco, 
                    options
                )

                success_count += 1
                self.stdout.write(self.style.SUCCESS(f"\n✓ Successfully initialized {db_name}"))
                
                # Show stats
                self._print_stats(stats)

            except Exception as e:
                error_count += 1
                errors.append((db_name, str(e)))
                self.stderr.write(self.style.ERROR(f"\n✗ Error initializing {db_name}: {str(e)}"))
                logger.exception(f"Error initializing {db_name}")

        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        self.stdout.write(self.style.SUCCESS('INITIALIZATION SUMMARY'))
        self.stdout.write(self.style.SUCCESS('='*80))
        self.stdout.write(f"\nTotal databases: {len(sacco_dbs)}")
        self.stdout.write(self.style.SUCCESS(f"Successful: {success_count}"))
        
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"Failed: {error_count}"))
            self.stdout.write(self.style.ERROR('\nErrors:'))
            for db, error in errors:
                self.stdout.write(self.style.ERROR(f"  - {db}: {error}"))
        else:
            self.stdout.write(self.style.SUCCESS("\n✓ All initializations completed successfully!"))
        
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))

        if error_count > 0:
            raise CommandError(f'Initialization failed for {error_count} database(s)')

    def _initialize_sacco(self, db_name, sacco, options):
        """Initialize a single SACCO database"""
        # IMPORT THE CONFIG MODULE HERE
        from core.management.commands.sacco_init_config import SaccoInitConfig, SaccoPresets
        
        stats = {
            'settings': 0,
            'payment_methods': 0,
            'tax_rates': 0,
        }

        # Check if this is dry run
        dry_run = options.get('dry_run', False)
        force = options.get('force', False)

        # ===================================================================
        # CRITICAL: Set database context BEFORE any model operations
        # ===================================================================
        set_current_db(db_name)

        # Get configuration using SaccoInitConfig
        config = SaccoPresets.get_preset_config(sacco)
        sacco_config = config['sacco_type_config']

        self.stdout.write(f"\n📋 SACCO Type: {sacco_config['name']}")
        self.stdout.write(f"💰 Currency: {sacco_config['default_currency']}")
        self.stdout.write(f"📅 Period System: {sacco_config['period_system']}")
        self.stdout.write(f"🏦 Has Loans: {'Yes' if sacco_config.get('has_loans') else 'No'}")
        self.stdout.write(f"💵 Has Savings: {'Yes' if sacco_config.get('has_savings') else 'No'}")
        self.stdout.write(f"📈 Has Shares: {'Yes' if sacco_config.get('has_shares') else 'No'}")
        self.stdout.write(f"💎 Has Dividends: {'Yes' if sacco_config.get('has_dividends') else 'No'}")

        # Determine what to initialize based on --only and --skip flags
        only_flags = [k for k in options.keys() if k.startswith('only_') and options[k]]
        skip_flags = [k for k in options.keys() if k.startswith('skip_') and options[k]]
        
        # If any --only flag is set, initialize only those components
        if only_flags:
            should_init = lambda component: f'only_{component}' in only_flags
        else:
            should_init = lambda component: f'skip_{component}' not in skip_flags

        # 1. Create FinancialSettings and SaccoConfiguration
        if should_init('settings'):
            self.stdout.write(self.style.HTTP_INFO("\n→ Processing settings..."))
            stats['settings'] = self._create_settings(db_name, sacco, dry_run, force)

        # 2. Create Payment Methods
        if should_init('payments'):
            self.stdout.write(self.style.HTTP_INFO("\n→ Processing payment methods..."))
            stats['payment_methods'] = self._create_payment_methods(
                db_name, config['payment_methods'], dry_run, force
            )

        # 3. Create Tax Rates
        if should_init('taxes'):
            self.stdout.write(self.style.HTTP_INFO("\n→ Processing tax rates..."))
            stats['tax_rates'] = self._create_tax_rates(
                db_name, config['tax_rates'], dry_run, force
            )

        return stats

    def _create_settings(self, db_name, sacco, dry_run, force):
        """Create FinancialSettings and SaccoConfiguration"""
        from core.management.commands.sacco_init_config import SaccoInitConfig
        
        count = 0
        
        # Get models
        FinancialSettings = apps.get_model('core', 'FinancialSettings')
        SaccoConfiguration = apps.get_model('core', 'SaccoConfiguration')
        
        # FinancialSettings
        # NOTE: .first() will use the manager which respects current DB context
        existing = FinancialSettings.objects.first()
        
        if dry_run:
            if not existing or force:
                self.stdout.write("    • Would create/update FinancialSettings")
                count += 1
            else:
                self.stdout.write("    • FinancialSettings already exists (would skip)")
        else:
            if not existing or force:
                if force and existing:
                    self.stdout.write("    • Deleting existing FinancialSettings...")
                    existing.delete()
                
                # create_financial_settings will use the current DB context
                SaccoInitConfig.create_financial_settings(sacco)
                count += 1
                self.stdout.write(self.style.SUCCESS("    ✓ FinancialSettings created"))
            else:
                self.stdout.write("    • FinancialSettings already exists (skipped)")

        # SaccoConfiguration
        existing = SaccoConfiguration.objects.first()
        
        if dry_run:
            if not existing or force:
                self.stdout.write("    • Would create/update SaccoConfiguration")
                count += 1
            else:
                self.stdout.write("    • SaccoConfiguration already exists (would skip)")
        else:
            if not existing or force:
                if force and existing:
                    self.stdout.write("    • Deleting existing SaccoConfiguration...")
                    existing.delete()
                
                # create_sacco_configuration will use the current DB context
                SaccoInitConfig.create_sacco_configuration(sacco)
                count += 1
                self.stdout.write(self.style.SUCCESS("    ✓ SaccoConfiguration created"))
            else:
                self.stdout.write("    • SaccoConfiguration already exists (skipped)")

        return count

    def _create_payment_methods(self, db_name, payment_methods, dry_run, force):
        """Create payment methods"""
        PaymentMethod = apps.get_model('core', 'PaymentMethod')
        
        if dry_run:
            self.stdout.write(f"    • Would create {len(payment_methods)} payment methods")
            return len(payment_methods)
        
        if force:
            deleted_count = PaymentMethod.objects.count()
            if deleted_count > 0:
                self.stdout.write(f"    • Deleting {deleted_count} existing payment methods...")
                PaymentMethod.objects.all().delete()
        
        count = 0
        for pm_data in payment_methods:
            # update_or_create uses the manager which respects current DB context
            pm, created = PaymentMethod.objects.update_or_create(
                code=pm_data['code'],
                defaults={k: v for k, v in pm_data.items() if k != 'code'}
            )
            if created:
                count += 1

        self.stdout.write(self.style.SUCCESS(f"    ✓ Created {count} payment methods"))
        return count

    def _create_tax_rates(self, db_name, tax_rates, dry_run, force):
        """Create tax rates"""
        TaxRate = apps.get_model('core', 'TaxRate')
        
        if dry_run:
            self.stdout.write(f"    • Would create {len(tax_rates)} tax rates")
            return len(tax_rates)
        
        if force:
            deleted_count = TaxRate.objects.count()
            if deleted_count > 0:
                self.stdout.write(f"    • Deleting {deleted_count} existing tax rates...")
                TaxRate.objects.all().delete()
        
        count = 0
        for tax_data in tax_rates:
            # Use tax_type and effective_from as unique identifier
            # update_or_create uses the manager which respects current DB context
            tax, created = TaxRate.objects.update_or_create(
                tax_type=tax_data['tax_type'],
                effective_from=tax_data['effective_from'],
                defaults={k: v for k, v in tax_data.items() if k not in ['tax_type', 'effective_from']}
            )
            if created:
                count += 1

        self.stdout.write(self.style.SUCCESS(f"    ✓ Created {count} tax rates"))
        return count

    def _print_stats(self, stats):
        """Print initialization statistics"""
        total = sum(v if isinstance(v, int) else 0 for v in stats.values())
        
        if total > 0:
            self.stdout.write(f"\n📊 Initialization Statistics:")
            self.stdout.write(f"{'='*60}")
            
            if stats['settings'] > 0:
                self.stdout.write(f"  Settings:              {stats['settings']}")
            if stats['payment_methods'] > 0:
                self.stdout.write(f"  Payment Methods:       {stats['payment_methods']}")
            if stats['tax_rates'] > 0:
                self.stdout.write(f"  Tax Rates:             {stats['tax_rates']}")
            
            self.stdout.write(f"{'='*60}")
            self.stdout.write(f"  TOTAL:                 {total}")
        else:
            self.stdout.write(f"\n📊 No new items created (all already exist)")