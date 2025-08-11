"""Base test classes with proper isolation and utilities."""

from odoo.tests import TransactionCase, HttpCase, tagged
from unittest.mock import MagicMock, patch
from contextlib import contextmanager


class UnitTestCase(TransactionCase):
    """Base class for unit tests with mocking support."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Use admin user with minimal context
        cls.env = cls.env(user=cls.env.ref("base.user_admin"))
        cls.env = cls.env(context=dict(
            cls.env.context,
            skip_shopify_sync=True,
            tracking_disable=True,
            no_reset_password=True,
            mail_notrack=True,
            mail_create_nolog=True,
        ))
    
    def mock_service(self, service_path):
        """Helper to mock external services."""
        patcher = patch(service_path)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock
    
    @contextmanager
    def mock_shopify_client(self):
        """Context manager for mocking Shopify GraphQL client."""
        with patch("addons.product_connect.services.shopify.client.GraphQLClient") as mock_client:
            instance = MagicMock()
            mock_client.return_value = instance
            yield instance
    
    def assertRecordValues(self, record, expected_values):
        """Assert multiple field values on a record."""
        for field, expected in expected_values.items():
            actual = record[field]
            # Handle special cases
            if hasattr(actual, "id"):
                actual = actual.id
            elif hasattr(actual, "ids"):
                actual = actual.ids
            
            self.assertEqual(
                actual, expected,
                f"Field '{field}' mismatch: expected {expected}, got {actual}"
            )
    
    def _setup_shopify_mocks(self):
        """Set up minimal Shopify service mocks for unit tests."""
        self.shopify_service_patcher = patch("odoo.addons.product_connect.services.shopify.sync.base.ShopifyService")
        self.mock_shopify_service_class = self.shopify_service_patcher.start()
        
        self.mock_client = MagicMock()
        self.mock_service_instance = MagicMock()
        self.mock_service_instance.client = self.mock_client
        self.mock_service_instance.first_location_gid = "gid://shopify/Location/12345"
        self.mock_service_instance.get_first_location_gid.return_value = "gid://shopify/Location/12345"
        
        self.mock_shopify_service_class.return_value = self.mock_service_instance
    
    def tearDown(self):
        """Clean up mocks and patches."""
        if hasattr(self, "shopify_service_patcher") and self.shopify_service_patcher:
            self.shopify_service_patcher.stop()
        super().tearDown()


class IntegrationTestCase(TransactionCase):
    """Base class for integration tests with test data."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(user=cls.env.ref("base.user_admin"))
        cls.env = cls.env(context=dict(
            cls.env.context,
            skip_shopify_sync=False,  # Allow sync in integration tests
            tracking_disable=True,
            no_reset_password=True,
        ))
        cls._setup_test_data()
    
    @classmethod
    def _setup_test_data(cls):
        """Override to set up test data."""
        # Create test company
        cls.test_company = cls.env.ref("base.main_company")
        
        # Create test warehouse
        cls.test_warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.test_company.id)], limit=1
        )
        
        # Create test pricelist
        cls.test_pricelist = cls.env["product.pricelist"].search(
            [("currency_id.name", "=", "USD")], limit=1
        )
        if not cls.test_pricelist:
            cls.test_pricelist = cls.env["product.pricelist"].create({
                "name": "Test Pricelist",
                "currency_id": cls.env.ref("base.USD").id,
            })
        
        # Set up base test data that integration tests expect
        cls._setup_class_base_data()
    
    @classmethod
    def _setup_class_base_data(cls):
        """Set up base test data at class level (countries, states, categories)."""
        cls.usa_country = cls.env["res.country"].search([("code", "=", "US")], limit=1)
        if not cls.usa_country:
            cls.usa_country = cls.env["res.country"].create({"name": "United States", "code": "US", "phone_code": 1})
        
        cls.ny_state = cls.env["res.country.state"].search(
            [("code", "=", "NY"), ("country_id", "=", cls.usa_country.id)], limit=1
        )
        if not cls.ny_state:
            cls.ny_state = cls.env["res.country.state"].create(
                {"name": "New York", "code": "NY", "country_id": cls.usa_country.id}
            )
        
        cls.shopify_category = cls.env["res.partner.category"].search([("name", "=", "Shopify")], limit=1)
        if not cls.shopify_category:
            cls.shopify_category = cls.env["res.partner.category"].create({"name": "Shopify"})
    
    def create_shopify_credentials(self):
        """Create test Shopify credentials."""
        return self.env["shopify.credentials"].create({
            "name": "Test Store",
            "shop_domain": "test-store.myshopify.com",
            "access_token": "test_token_123",
            "api_version": "2024-01",
            "active": True,
        })
    
    def mock_shopify_response(self, data=None, errors=None):
        """Create a mock Shopify GraphQL response."""
        response = {"data": data or {}}
        if errors:
            response["errors"] = errors
        return response
    
    def _setup_shopify_mocks(self):
        """Set up Shopify service mocks for integration tests."""
        self.shopify_service_patcher = patch("odoo.addons.product_connect.services.shopify.sync.base.ShopifyService")
        self.mock_shopify_service_class = self.shopify_service_patcher.start()
        
        self.mock_client = MagicMock()
        self.mock_service_instance = MagicMock()
        self.mock_service_instance.client = self.mock_client
        self.mock_service_instance.first_location_gid = "gid://shopify/Location/12345"
        self.mock_service_instance.get_first_location_gid.return_value = "gid://shopify/Location/12345"
        
        self.mock_shopify_service_class.return_value = self.mock_service_instance
    
    def _setup_base_data(self):
        """Set up base test data (countries, states, categories)."""
        self.usa_country = self.env["res.country"].search([("code", "=", "US")], limit=1)
        if not self.usa_country:
            self.usa_country = self.env["res.country"].create({"name": "United States", "code": "US", "phone_code": 1})
        
        self.ny_state = self.env["res.country.state"].search(
            [("code", "=", "NY"), ("country_id", "=", self.usa_country.id)], limit=1
        )
        if not self.ny_state:
            self.ny_state = self.env["res.country.state"].create(
                {"name": "New York", "code": "NY", "country_id": self.usa_country.id}
            )
        
        self.shopify_category = self.env["res.partner.category"].search([("name", "=", "Shopify")], limit=1)
        if not self.shopify_category:
            self.shopify_category = self.env["res.partner.category"].create({"name": "Shopify"})
    
    def tearDown(self):
        """Clean up mocks and patches."""
        if hasattr(self, "shopify_service_patcher") and self.shopify_service_patcher:
            self.shopify_service_patcher.stop()
        super().tearDown()


class TourTestCase(HttpCase):
    """Base class for tour tests with browser support."""
    
    def setUp(self):
        super().setUp()
        self.browser_size = (1920, 1080)
        self.tour_timeout = 120
    
    def start_tour(self, url, tour_name, login="admin", timeout=None):
        """Start a tour test with proper setup."""
        if timeout is None:
            timeout = self.tour_timeout
        
        # Ensure user exists and has password
        if login:
            user = self.env.ref(f"base.user_{login}")
            user.password = login
        
        # Start the tour
        self.browser_js(
            url,
            f"odoo.__DEBUG__.services['web_tour.tour'].run('{tour_name}')",
            f"odoo.__DEBUG__.services['web_tour.tour'].tours['{tour_name}'].ready",
            login=login,
            timeout=timeout,
        )
    
    def register_tour(self, tour_definition):
        """Register a custom tour for testing."""
        # Tour registration would be done in JS files
        # This is a placeholder for documentation
        pass
    
    def take_screenshot(self, name="screenshot"):
        """Take a screenshot during tour execution."""
        # This would integrate with the browser automation
        pass