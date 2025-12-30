# core/management/commands/sacco_init_config.py

"""
Configuration presets for SACCO initialization.

Provides default configurations for different SACCO types including:
- Financial settings (currencies, fiscal year, periods)
- SACCO-specific configurations (loans, savings, shares, dividends)
- Payment methods (cash, bank transfer, mobile money)
- Tax rates by country

SACCO TYPES:
- SAVINGS_CREDIT: General savings and credit cooperative
- AGRICULTURAL: Agricultural/farmers SACCO
- TRANSPORT: Transport workers (boda boda, taxi)
- TEACHERS: Teachers SACCO
- HEALTH_WORKERS: Health workers SACCO
- MARKET_VENDORS: Market vendors/traders
- WOMEN_GROUP: Women empowerment groups
- YOUTH_GROUP: Youth development groups
- COMMUNITY_BASED: Community-based SACCO
- WORKPLACE_BASED: Workplace/employee SACCO
"""

from decimal import Decimal
from datetime import date
from django.apps import apps


class SaccoInitConfig:
    """Configuration generator for SACCO initialization"""
    
    # SACCO Type Configurations
    SACCO_TYPES = {
        'SAVINGS_CREDIT': {
            'name': 'Savings & Credit Cooperative',
            'description': 'General purpose SACCO for savings and credit',
            
            # Financial settings
            'default_currency': None,  # Auto-detect from country
            'fiscal_year_type': 'CALENDAR',
            'period_system': 'MONTHLY',
            
            # Loan settings
            'loan_default_term_days': 365,
            'loan_interest_rate': Decimal('12.00'),
            'loan_min_amount': Decimal('50000.00'),
            'loan_max_amount': Decimal('10000000.00'),
            'loan_processing_fee_rate': Decimal('2.00'),
            
            # Savings settings
            'savings_min_balance': Decimal('10000.00'),
            'savings_interest_rate': Decimal('5.00'),
            
            # Share settings
            'share_value_per_share': Decimal('5000.00'),
            'share_min_shares_required': 2,
            
            # Features
            'has_loans': True,
            'has_savings': True,
            'has_shares': True,
            'has_dividends': True,
            'has_groups': True,
            'has_projects': False,
        },
        
        'AGRICULTURAL': {
            'name': 'Agricultural SACCO',
            'description': 'SACCO for farmers and agricultural workers',
            
            'default_currency': None,
            'fiscal_year_type': 'CALENDAR',
            'period_system': 'MONTHLY',
            
            'loan_default_term_days': 180,  # Seasonal
            'loan_interest_rate': Decimal('10.00'),
            'loan_min_amount': Decimal('20000.00'),
            'loan_max_amount': Decimal('5000000.00'),
            'loan_processing_fee_rate': Decimal('1.50'),
            
            'savings_min_balance': Decimal('5000.00'),
            'savings_interest_rate': Decimal('4.00'),
            
            'share_value_per_share': Decimal('3000.00'),
            'share_min_shares_required': 2,
            
            'has_loans': True,
            'has_savings': True,
            'has_shares': True,
            'has_dividends': True,
            'has_groups': True,
            'has_projects': True,
        },
        
        'TRANSPORT': {
            'name': 'Transport Workers SACCO',
            'description': 'SACCO for boda boda, taxi, and transport workers',
            
            'default_currency': None,
            'fiscal_year_type': 'CALENDAR',
            'period_system': 'MONTHLY',
            
            'loan_default_term_days': 365,
            'loan_interest_rate': Decimal('15.00'),
            'loan_min_amount': Decimal('100000.00'),
            'loan_max_amount': Decimal('15000000.00'),
            'loan_processing_fee_rate': Decimal('2.50'),
            
            'savings_min_balance': Decimal('20000.00'),
            'savings_interest_rate': Decimal('5.00'),
            
            'share_value_per_share': Decimal('10000.00'),
            'share_min_shares_required': 1,
            
            'has_loans': True,
            'has_savings': True,
            'has_shares': True,
            'has_dividends': True,
            'has_groups': True,
            'has_projects': False,
        },
        
        'TEACHERS': {
            'name': 'Teachers SACCO',
            'description': 'SACCO for teachers and education workers',
            
            'default_currency': None,
            'fiscal_year_type': 'CALENDAR',
            'period_system': 'MONTHLY',
            
            'loan_default_term_days': 365,
            'loan_interest_rate': Decimal('10.00'),
            'loan_min_amount': Decimal('100000.00'),
            'loan_max_amount': Decimal('20000000.00'),
            'loan_processing_fee_rate': Decimal('2.00'),
            
            'savings_min_balance': Decimal('15000.00'),
            'savings_interest_rate': Decimal('5.00'),
            
            'share_value_per_share': Decimal('5000.00'),
            'share_min_shares_required': 3,
            
            'has_loans': True,
            'has_savings': True,
            'has_shares': True,
            'has_dividends': True,
            'has_groups': False,
            'has_projects': True,
        },
        
        'HEALTH_WORKERS': {
            'name': 'Health Workers SACCO',
            'description': 'SACCO for medical and health workers',
            
            'default_currency': None,
            'fiscal_year_type': 'CALENDAR',
            'period_system': 'MONTHLY',
            
            'loan_default_term_days': 365,
            'loan_interest_rate': Decimal('11.00'),
            'loan_min_amount': Decimal('100000.00'),
            'loan_max_amount': Decimal('25000000.00'),
            'loan_processing_fee_rate': Decimal('2.00'),
            
            'savings_min_balance': Decimal('15000.00'),
            'savings_interest_rate': Decimal('5.50'),
            
            'share_value_per_share': Decimal('10000.00'),
            'share_min_shares_required': 2,
            
            'has_loans': True,
            'has_savings': True,
            'has_shares': True,
            'has_dividends': True,
            'has_groups': False,
            'has_projects': False,
        },
        
        'MARKET_VENDORS': {
            'name': 'Market Vendors SACCO',
            'description': 'SACCO for market vendors and traders',
            
            'default_currency': None,
            'fiscal_year_type': 'CALENDAR',
            'period_system': 'MONTHLY',
            
            'loan_default_term_days': 180,
            'loan_interest_rate': Decimal('15.00'),
            'loan_min_amount': Decimal('20000.00'),
            'loan_max_amount': Decimal('5000000.00'),
            'loan_processing_fee_rate': Decimal('2.00'),
            
            'savings_min_balance': Decimal('5000.00'),
            'savings_interest_rate': Decimal('4.00'),
            
            'share_value_per_share': Decimal('2000.00'),
            'share_min_shares_required': 3,
            
            'has_loans': True,
            'has_savings': True,
            'has_shares': True,
            'has_dividends': True,
            'has_groups': True,
            'has_projects': False,
        },
        
        'WOMEN_GROUP': {
            'name': 'Women Group SACCO',
            'description': 'Women empowerment and development SACCO',
            
            'default_currency': None,
            'fiscal_year_type': 'CALENDAR',
            'period_system': 'MONTHLY',
            
            'loan_default_term_days': 365,
            'loan_interest_rate': Decimal('10.00'),
            'loan_min_amount': Decimal('50000.00'),
            'loan_max_amount': Decimal('5000000.00'),
            'loan_processing_fee_rate': Decimal('1.50'),
            
            'savings_min_balance': Decimal('5000.00'),
            'savings_interest_rate': Decimal('5.00'),
            
            'share_value_per_share': Decimal('3000.00'),
            'share_min_shares_required': 2,
            
            'has_loans': True,
            'has_savings': True,
            'has_shares': True,
            'has_dividends': True,
            'has_groups': True,
            'has_projects': True,
        },
        
        'YOUTH_GROUP': {
            'name': 'Youth Group SACCO',
            'description': 'Youth development and entrepreneurship SACCO',
            
            'default_currency': None,
            'fiscal_year_type': 'CALENDAR',
            'period_system': 'MONTHLY',
            
            'loan_default_term_days': 365,
            'loan_interest_rate': Decimal('10.00'),
            'loan_min_amount': Decimal('30000.00'),
            'loan_max_amount': Decimal('3000000.00'),
            'loan_processing_fee_rate': Decimal('1.50'),
            
            'savings_min_balance': Decimal('3000.00'),
            'savings_interest_rate': Decimal('5.00'),
            
            'share_value_per_share': Decimal('1000.00'),
            'share_min_shares_required': 5,
            
            'has_loans': True,
            'has_savings': True,
            'has_shares': True,
            'has_dividends': True,
            'has_groups': True,
            'has_projects': True,
        },
        
        'COMMUNITY_BASED': {
            'name': 'Community-Based SACCO',
            'description': 'Community development cooperative',
            
            'default_currency': None,
            'fiscal_year_type': 'CALENDAR',
            'period_system': 'MONTHLY',
            
            'loan_default_term_days': 365,
            'loan_interest_rate': Decimal('12.00'),
            'loan_min_amount': Decimal('50000.00'),
            'loan_max_amount': Decimal('8000000.00'),
            'loan_processing_fee_rate': Decimal('2.00'),
            
            'savings_min_balance': Decimal('10000.00'),
            'savings_interest_rate': Decimal('5.00'),
            
            'share_value_per_share': Decimal('5000.00'),
            'share_min_shares_required': 2,
            
            'has_loans': True,
            'has_savings': True,
            'has_shares': True,
            'has_dividends': True,
            'has_groups': True,
            'has_projects': True,
        },
        
        'WORKPLACE_BASED': {
            'name': 'Workplace/Employee SACCO',
            'description': 'Workplace or employee-based SACCO',
            
            'default_currency': None,
            'fiscal_year_type': 'CALENDAR',
            'period_system': 'MONTHLY',
            
            'loan_default_term_days': 365,
            'loan_interest_rate': Decimal('10.00'),
            'loan_min_amount': Decimal('100000.00'),
            'loan_max_amount': Decimal('20000000.00'),
            'loan_processing_fee_rate': Decimal('2.00'),
            
            'savings_min_balance': Decimal('20000.00'),
            'savings_interest_rate': Decimal('6.00'),
            
            'share_value_per_share': Decimal('10000.00'),
            'share_min_shares_required': 2,
            
            'has_loans': True,
            'has_savings': True,
            'has_shares': True,
            'has_dividends': True,
            'has_groups': False,
            'has_projects': False,
        },
    }
    
    # Currency mapping by country code
    CURRENCY_MAP = {
        'UG': 'UGX',  # Uganda
        'KE': 'KES',  # Kenya
        'TZ': 'TZS',  # Tanzania
        'RW': 'RWF',  # Rwanda
    }
    
    @classmethod
    def get_sacco_type_config(cls, sacco_type):
        """Get configuration for a specific SACCO type"""
        return cls.SACCO_TYPES.get(sacco_type, cls.SACCO_TYPES['SAVINGS_CREDIT']).copy()
    
    @classmethod
    def get_sacco_config_from_instance(cls, sacco_instance):
        """
        Get configuration from a SACCO instance with country-specific overrides.
        
        Args:
            sacco_instance: Sacco model instance (can be None for defaults)
            
        Returns:
            dict: Configuration dictionary
        """
        # Default to SAVINGS_CREDIT if no instance
        sacco_type = 'SAVINGS_CREDIT'
        country = 'UG'  # Default to Uganda
        
        if sacco_instance:
            sacco_type = sacco_instance.sacco_type or 'SAVINGS_CREDIT'
            country = sacco_instance.country or 'UG'
        
        config = cls.get_sacco_type_config(sacco_type)
        
        # Override currency based on country
        config['default_currency'] = cls.CURRENCY_MAP.get(country, 'UGX')
        
        return config
    
    @classmethod
    def create_sacco_configuration(cls, sacco_instance):
        """
        Create SaccoConfiguration model instance.
        Uses current database context from managers.set_current_db().
        """
        SaccoConfiguration = apps.get_model('core', 'SaccoConfiguration')
        config = cls.get_sacco_config_from_instance(sacco_instance)
        
        # Create using the manager (which respects current DB context)
        sacco_config = SaccoConfiguration.objects.create(
            # Period system configuration
            period_system=config.get('period_system', 'monthly').lower(),  # lowercase for choices
            periods_per_year=12,
            period_naming_convention='monthly',
            custom_period_names={},
            
            # Fiscal year configuration
            fiscal_year_type=config.get('fiscal_year_type', 'CALENDAR').lower(),  # lowercase for choices
            fiscal_year_start_month=1,
            fiscal_year_start_day=1,
            
            # Dividend settings
            dividend_calculation_method='SHARE_BASED',
            dividend_distribution_frequency='ANNUAL',
            
            # Communication settings
            enable_automatic_reminders=True,
            enable_sms=True,
            enable_email_notifications=True,
        )
        
        return sacco_config
    
    @classmethod
    def create_financial_settings(cls, sacco_instance):
        """
        Create FinancialSettings model instance.
        Uses current database context from managers.set_current_db().
        """
        FinancialSettings = apps.get_model('core', 'FinancialSettings')
        config = cls.get_sacco_config_from_instance(sacco_instance)
        
        # Create using the manager (which respects current DB context)
        financial_settings = FinancialSettings.objects.create(
            # Currency settings
            sacco_currency=config.get('default_currency', 'UGX'),
            currency_position='BEFORE',
            decimal_places=2,
            use_thousand_separator=True,
            
            # Loan settings
            default_loan_term_days=config.get('loan_default_term_days', 365),
            default_interest_rate=config.get('loan_interest_rate', Decimal('12.00')),
            late_payment_penalty_rate=Decimal('2.00'),
            grace_period_days=7,
            minimum_loan_amount=config.get('loan_min_amount', Decimal('50000.00')),
            maximum_loan_amount=config.get('loan_max_amount', Decimal('10000000.00')),
            
            # Savings settings
            minimum_savings_balance=config.get('savings_min_balance', Decimal('10000.00')),
            savings_interest_rate=config.get('savings_interest_rate', Decimal('5.00')),
            
            # Share settings
            share_value=config.get('share_value_per_share', Decimal('5000.00')),
            minimum_shares=config.get('share_min_shares_required', 1),
            
            # Workflow settings
            loan_approval_required=True,
            withdrawal_approval_required=False,
            withdrawal_approval_limit=Decimal('500000.00'),
            
            # Communication settings
            send_transaction_notifications=True,
            send_loan_reminders=True,
            send_dividend_notifications=True,
        )
        
        return financial_settings
    
    @classmethod
    def get_payment_methods(cls, sacco_instance):
        """
        Get payment methods configuration.
        
        Args:
            sacco_instance: Sacco model instance (can be None)
            
        Returns:
            list: List of payment method configurations
        """
        country = 'UG'  # Default
        if sacco_instance:
            country = sacco_instance.country or 'UG'
        
        methods = [
            {
                'code': 'CASH',
                'name': 'Cash',
                'method_type': 'CASH',
                'is_active': True,
                'is_default': True,
                'requires_approval': False,
                'has_transaction_fee': False,
                'display_order': 1,
            },
            {
                'code': 'BANK_TRANSFER',
                'name': 'Bank Transfer',
                'method_type': 'BANK_TRANSFER',
                'is_active': True,
                'is_default': False,
                'requires_approval': False,
                'has_transaction_fee': False,
                'display_order': 2,
            },
        ]
        
        # Add mobile money based on country
        if country in ['UG', 'KE', 'TZ', 'RW']:
            methods.extend([
                {
                    'code': 'MTN_MM',
                    'name': 'MTN Mobile Money',
                    'method_type': 'MOBILE_MONEY',
                    'mobile_money_provider': 'MTN',
                    'is_active': True,
                    'is_default': False,
                    'requires_approval': False,
                    'has_transaction_fee': True,
                    'transaction_fee_type': 'PERCENTAGE',
                    'transaction_fee_amount': Decimal('1.50'),
                    'fee_bearer': 'MEMBER',
                    'color_code': '#FFCB05',
                    'display_order': 3,
                },
                {
                    'code': 'AIRTEL_MM',
                    'name': 'Airtel Money',
                    'method_type': 'MOBILE_MONEY',
                    'mobile_money_provider': 'AIRTEL',
                    'is_active': True,
                    'is_default': False,
                    'requires_approval': False,
                    'has_transaction_fee': True,
                    'transaction_fee_type': 'PERCENTAGE',
                    'transaction_fee_amount': Decimal('1.50'),
                    'fee_bearer': 'MEMBER',
                    'color_code': '#ED1C24',
                    'display_order': 4,
                },
            ])
        
        if country in ['KE', 'TZ']:
            provider = 'Safaricom' if country == 'KE' else 'Vodacom'
            methods.append({
                'code': 'MPESA',
                'name': f'M-Pesa ({provider})',
                'method_type': 'MOBILE_MONEY',
                'mobile_money_provider': 'OTHER',
                'is_active': True,
                'is_default': False,
                'requires_approval': False,
                'has_transaction_fee': True,
                'transaction_fee_type': 'PERCENTAGE',
                'transaction_fee_amount': Decimal('1.00'),
                'fee_bearer': 'MEMBER',
                'color_code': '#00A651',
                'display_order': 5,
            })
        
        return methods
    
    @classmethod
    def get_tax_rates(cls, sacco_instance, country=None):
        """
        Get tax rates by country.
        
        Args:
            sacco_instance: Sacco model instance (can be None)
            country: Country code override
            
        Returns:
            list: List of tax rate configurations
        """
        if not country and sacco_instance:
            country = sacco_instance.country or 'UG'
        elif not country:
            country = 'UG'
        
        # Tax rates by country
        tax_config = {
            'UG': [  # Uganda
                {
                    'name': 'Withholding Tax on Interest',
                    'tax_type': 'WHT_INTEREST',
                    'rate': Decimal('15.00'),
                    'effective_from': date(2020, 1, 1),
                    'is_active': True,
                    'applies_to_members': True,
                    'applies_to_sacco': False,
                },
                {
                    'name': 'Withholding Tax on Dividends',
                    'tax_type': 'WHT_DIVIDEND',
                    'rate': Decimal('15.00'),
                    'effective_from': date(2020, 1, 1),
                    'is_active': True,
                    'applies_to_members': True,
                    'applies_to_sacco': False,
                },
            ],
            'KE': [  # Kenya
                {
                    'name': 'Withholding Tax on Interest',
                    'tax_type': 'WHT_INTEREST',
                    'rate': Decimal('15.00'),
                    'effective_from': date(2020, 1, 1),
                    'is_active': True,
                    'applies_to_members': True,
                    'applies_to_sacco': False,
                },
                {
                    'name': 'Withholding Tax on Dividends',
                    'tax_type': 'WHT_DIVIDEND',
                    'rate': Decimal('5.00'),
                    'effective_from': date(2020, 1, 1),
                    'is_active': True,
                    'applies_to_members': True,
                    'applies_to_sacco': False,
                },
            ],
            'TZ': [  # Tanzania
                {
                    'name': 'Withholding Tax on Interest',
                    'tax_type': 'WHT_INTEREST',
                    'rate': Decimal('10.00'),
                    'effective_from': date(2020, 1, 1),
                    'is_active': True,
                    'applies_to_members': True,
                    'applies_to_sacco': False,
                },
                {
                    'name': 'Withholding Tax on Dividends',
                    'tax_type': 'WHT_DIVIDEND',
                    'rate': Decimal('5.00'),
                    'effective_from': date(2020, 1, 1),
                    'is_active': True,
                    'applies_to_members': True,
                    'applies_to_sacco': False,
                },
            ],
            'RW': [  # Rwanda
                {
                    'name': 'Withholding Tax on Interest',
                    'tax_type': 'WHT_INTEREST',
                    'rate': Decimal('15.00'),
                    'effective_from': date(2020, 1, 1),
                    'is_active': True,
                    'applies_to_members': True,
                    'applies_to_sacco': False,
                },
                {
                    'name': 'Withholding Tax on Dividends',
                    'tax_type': 'WHT_DIVIDEND',
                    'rate': Decimal('15.00'),
                    'effective_from': date(2020, 1, 1),
                    'is_active': True,
                    'applies_to_members': True,
                    'applies_to_sacco': False,
                },
            ],
        }
        
        return tax_config.get(country, tax_config['UG'])


class SaccoPresets:
    """Helper class for getting preset configurations"""
    
    @classmethod
    def get_preset_config(cls, sacco_instance):
        """
        Get complete preset configuration for a SACCO.
        
        Returns:
            dict: Complete configuration including:
                - sacco_type_config
                - payment_methods
                - tax_rates
        """
        country = None
        if sacco_instance:
            country = sacco_instance.country
        
        return {
            'sacco_type_config': SaccoInitConfig.get_sacco_config_from_instance(sacco_instance),
            'payment_methods': SaccoInitConfig.get_payment_methods(sacco_instance),
            'tax_rates': SaccoInitConfig.get_tax_rates(sacco_instance, country),
        }