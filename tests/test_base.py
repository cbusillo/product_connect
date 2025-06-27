"""Base test classes for product_connect module tests."""

import secrets
from odoo.tests import TransactionCase, HttpCase


class ProductConnectTransactionCase(TransactionCase):
    """Base class for transaction-based tests with common setup."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Disable mail tracking for better performance
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
        # Common test data setup
        cls._setup_test_data()
    
    @classmethod
    def _setup_test_data(cls):
        """Override this method to set up test-specific data."""
        pass


class ProductConnectHttpCase(HttpCase):
    """Base class for HTTP/browser tests with secure test user creation."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Disable mail tracking for better performance
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
        # Create secure test user for authentication
        cls._create_test_user()
        
        # Set up any common test data
        cls._setup_test_data()
    
    @classmethod
    def _create_test_user(cls, name="Test User", login_prefix="test_user"):
        """Create a test user with secure password and basic permissions."""
        # Generate unique login to avoid conflicts when tests run in parallel
        unique_suffix = secrets.token_hex(4)
        login = f"{login_prefix}_{unique_suffix}"
        
        # Generate cryptographically secure password
        secure_password = secrets.token_urlsafe(32)
        
        cls.test_user = cls.env["res.users"].create({
            "name": name,
            "login": login,
            "password": secure_password,
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("base.group_system").id,  # Required for module access in tests
            ])],
        })
        
        # Store password for authentication
        cls.test_user_password = secure_password
        
        return cls.test_user
    
    @classmethod
    def _setup_test_data(cls):
        """Override this method to set up test-specific data."""
        pass
    
    def authenticate_test_user(self):
        """Helper method to authenticate with the test user."""
        self.authenticate(self.test_user.login, self.test_user_password)


class ProductConnectIntegrationCase(ProductConnectHttpCase):
    """Base class for integration tests (JS/tours) with common motor test data."""
    
    @classmethod
    def _setup_test_data(cls):
        """Set up common test data for integration tests."""
        super()._setup_test_data()
        
        # Ensure we have at least one motor for tests
        if not cls.env["motor"].search([]):
            cls.test_motor = cls.env["motor"].create({
                "manufacturer": "TestMaker",
                "stroke": "Four",  
                "configuration": "V8",
                "horsepower": 250,
                "location": "A1",
                "serial_number": f"SN_{secrets.token_hex(4)}",
                "year": 2024,
                "model": "SuperV8",
            })
        else:
            cls.test_motor = cls.env["motor"].search([], limit=1)