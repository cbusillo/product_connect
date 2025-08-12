"""Base test classes with proper isolation and utilities."""

from contextlib import contextmanager
from typing import Iterator, Any

from odoo.models import BaseModel
from odoo.api import Environment
from ..common_imports import TransactionCase, HttpCase, MagicMock, patch, DEFAULT_TEST_CONTEXT


class _ShopifyMockMixin:
    """Shared mixin for Shopify mock functionality."""

    def _setup_shopify_mocks(self) -> None:
        self.shopify_service_patcher = patch("odoo.addons.product_connect.services.shopify.sync.base.ShopifyService")
        self.mock_shopify_service_class = self.shopify_service_patcher.start()

        self.mock_client = MagicMock()
        self.mock_service_instance = MagicMock()
        self.mock_service_instance.client = self.mock_client
        self.mock_service_instance.first_location_gid = "gid://shopify/Location/12345"
        self.mock_service_instance.get_first_location_gid.return_value = "gid://shopify/Location/12345"

        self.mock_shopify_service_class.return_value = self.mock_service_instance

    def _teardown_shopify_mocks(self) -> None:
        if hasattr(self, "shopify_service_patcher") and self.shopify_service_patcher:
            self.shopify_service_patcher.stop()


class UnitTestCase(_ShopifyMockMixin, TransactionCase):
    """Base class for unit tests with mocking support."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # Use admin user with minimal context
        cls.env = cls.env(user=cls.env.ref("base.user_admin"))
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                **DEFAULT_TEST_CONTEXT,
            )
        )

    def tearDown(self) -> None:
        """Clean up mocks after each test."""
        self._teardown_shopify_mocks()
        super().tearDown()
    
    def mock_service(self, service_path: str) -> MagicMock:
        """Helper to mock external services."""
        patcher = patch(service_path)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    @contextmanager
    def mock_shopify_client(self) -> Iterator[MagicMock]:
        """Context manager for mocking Shopify GraphQL client."""
        with patch("addons.product_connect.services.shopify.client.GraphQLClient") as mock_client:
            instance = MagicMock()
            mock_client.return_value = instance
            yield instance

    def assertRecordValues(self, record: BaseModel, expected_values: dict) -> None:
        """Assert multiple field values on a record."""
        for field, expected in expected_values.items():
            actual = record[field]
            # Handle special cases
            if hasattr(actual, "id"):
                actual = actual.id
            elif hasattr(actual, "ids"):
                actual = actual.ids

            self.assertEqual(actual, expected, f"Field '{field}' mismatch: expected {expected}, got {actual}")


def _get_or_create_geo_data(env: Environment) -> tuple[Any, Any, Any]:
    """Utility to create geographic test data without duplication."""
    usa_country = env["res.country"].search([("code", "=", "US")], limit=1)
    if not usa_country:
        usa_country = env["res.country"].create({"name": "United States", "code": "US", "phone_code": 1})

    ny_state = env["res.country.state"].search([("code", "=", "NY"), ("country_id", "=", usa_country.id)], limit=1)
    if not ny_state:
        ny_state = env["res.country.state"].create({"name": "New York", "code": "NY", "country_id": usa_country.id})

    shopify_category = env["res.partner.category"].search([("name", "=", "Shopify")], limit=1)
    if not shopify_category:
        shopify_category = env["res.partner.category"].create({"name": "Shopify"})

    return usa_country, ny_state, shopify_category


class _BaseDataMixin:
    """Shared mixin for base test data creation."""

    def _setup_base_data(self) -> None:
        self.usa_country, self.ny_state, self.shopify_category = _get_or_create_geo_data(self.env)

    @classmethod
    def _setup_class_base_data(cls) -> None:
        cls.usa_country, cls.ny_state, cls.shopify_category = _get_or_create_geo_data(cls.env)


class IntegrationTestCase(_ShopifyMockMixin, _BaseDataMixin, TransactionCase):
    """Base class for integration tests with test data."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.env = cls.env(user=cls.env.ref("base.user_admin"))
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                **DEFAULT_TEST_CONTEXT,
                skip_shopify_sync=False,  # Allow sync in integration tests
            )
        )
        cls._setup_test_data()

    @classmethod
    def _setup_test_data(cls) -> None:
        cls.test_company = cls.env.ref("base.main_company")

        cls.test_warehouse = cls.env["stock.warehouse"].search([("company_id", "=", cls.test_company.id)], limit=1)

        cls.test_pricelist = cls.env["product.pricelist"].search([("currency_id.name", "=", "USD")], limit=1)
        if not cls.test_pricelist:
            cls.test_pricelist = cls.env["product.pricelist"].create(
                {
                    "name": "Test Pricelist",
                    "currency_id": cls.env.ref("base.USD").id,
                }
            )

        cls._setup_class_base_data()

    def create_shopify_credentials(self) -> None:
        """Shopify credentials are stored in ir.config_parameter, not as a model."""
        # Store Shopify configuration in system parameters as used by the actual code
        config_param = self.env["ir.config_parameter"].sudo()
        config_param.set_param("shopify.shop_url_key", "test-store.myshopify.com")
        config_param.set_param("shopify.webhook_key", "test_webhook_key")
        config_param.set_param("shopify.test_store", "1")

    @staticmethod
    def mock_shopify_response(data: dict | None = None, errors: list | None = None) -> dict:
        response = {"data": data or {}}
        if errors:
            response["errors"] = errors
        return response

    def tearDown(self) -> None:
        self._teardown_shopify_mocks()
        super().tearDown()


class TourTestCase(HttpCase):
    """Base class for tour tests with browser support."""

    def setUp(self) -> None:
        super().setUp()
        self.browser_size = "1920x1080"
        self.tour_timeout = 120

    def start_tour(self, url: str, tour_name: str, login: str = "admin", timeout: int | None = None) -> None:
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

    def register_tour(self, tour_definition: dict) -> None:
        """Register a custom tour for testing."""
        # Tour registration would be done in JS files
        # This is a placeholder for documentation
        pass

    def take_screenshot(self, name: str = "screenshot") -> None:
        """Take a screenshot during tour execution."""
        # This would integrate with the browser automation
        pass
