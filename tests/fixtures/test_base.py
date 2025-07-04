"""Base test classes for product_connect module tests."""

import secrets
from odoo.tests import TransactionCase, HttpCase, tagged


@tagged("post_install", "-at_install")
class ProductConnectTransactionCase(TransactionCase):
    """Base class for transaction-based tests with common setup."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # Disable mail tracking for better performance
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Common test data setup
        cls._setup_test_data()

    @classmethod
    def _setup_test_data(cls) -> None:
        """Override this method to set up test-specific data."""
        # Skip Shopify sync during tests
        cls.env = cls.env(context=dict(cls.env.context, skip_shopify_sync=True))
        
        # Create test tags for data isolation
        cls._create_test_tags()
        
        # Create default test products with valid SKUs
        cls._create_default_test_products()
    
    @classmethod
    def _create_test_tags(cls) -> None:
        """Create test tags for data isolation."""
        # Create product tag for test products
        cls.test_product_tag = cls.env["product.tag"].create({
            "name": "Test Suite Data",
            "sequence": 999,
            "color": 10,  # Red color for visibility
        })
        
        # Create CRM tag for test sales orders
        cls.test_order_tag = cls.env["crm.tag"].create({
            "name": "Test Suite Data",
            "color": 10,  # Red color for visibility
        })
    
    @classmethod
    def _get_default_product_vals(cls) -> dict:
        """Get default values for test products."""
        return {
            "type": "consu",
            "list_price": 100.0,
            "sale_ok": True,
            "purchase_ok": True,
            "is_storable": True,
            "website_description": "Test product description",
            "product_tag_ids": [(4, cls.test_product_tag.id)],
        }
    
    @classmethod
    def _get_default_order_vals(cls) -> dict:
        """Get default values for test sales orders."""
        return {
            "partner_id": cls.test_partner.id,
            "tag_ids": [(4, cls.test_order_tag.id)],
        }
    
    @classmethod
    def _get_default_partner_vals(cls) -> dict:
        """Get default values for test partners."""
        return {
            "email": "test@example.com",
            "is_company": False,
        }
    
    @classmethod
    def _create_default_test_products(cls) -> None:
        """Create default test products that can be used across tests."""
        # First create test partner that products might need
        cls.test_partner = cls.env["res.partner"].create({
            **cls._get_default_partner_vals(),
            "name": "Test Customer",
        })
        
        # Additional test partners
        cls.test_partners = []
        for i in range(3):
            partner = cls.env["res.partner"].create({
                **cls._get_default_partner_vals(),
                "name": f"Test Customer {i+1}",
                "email": f"test{i+1}@example.com",
            })
            cls.test_partners.append(partner)
        
        # Standard consumable product with valid SKU
        cls.test_product = cls.env["product.product"].create({
            **cls._get_default_product_vals(),
            "name": "Test Product",
            "default_code": "10000001",  # Valid 8-digit SKU
        })
        
        # Service product (no SKU validation)
        cls.test_service = cls.env["product.product"].create({
            **cls._get_default_product_vals(),
            "name": "Test Service",
            "default_code": "SERVICE-001",  # Services can have any SKU
            "type": "service",
            "list_price": 50.0,
        })
        
        # Ready-to-sell product for Shopify sync tests
        cls.test_product_ready = cls.env["product.product"].create({
            **cls._get_default_product_vals(),
            "name": "Test Product Ready",
            "default_code": "20000001",  # Valid 8-digit SKU
            "list_price": 200.0,
            "is_ready_for_sale": True,
            "is_published": True,
        })
        
        # Create a pool of generic test products for various test scenarios
        cls.test_products = []
        for i in range(10):
            sku_number = 30000001 + i
            product = cls.env["product.product"].create({
                **cls._get_default_product_vals(),
                "name": f"Test Product {i + 1}",
                "default_code": str(sku_number),  # Valid 8-digit SKUs: 30000001-30000010
                "list_price": 50.0 + (i * 10),  # Varying prices
            })
            cls.test_products.append(product)
        
        # Create test products with different states for specific scenarios
        cls.test_product_not_for_sale = cls.env["product.product"].create({
            **cls._get_default_product_vals(),
            "name": "Test Product Not For Sale",
            "default_code": "40000001",
            "list_price": 150.0,
            "sale_ok": False,  # Not available for sale
        })
        
        cls.test_product_unpublished = cls.env["product.product"].create({
            **cls._get_default_product_vals(),
            "name": "Test Product Unpublished",
            "default_code": "40000002",
            "list_price": 175.0,
            "is_published": False,  # Not published
            "is_ready_for_sale": True,
        })
        
        cls.test_product_motor = cls.env["product.product"].create({
            **cls._get_default_product_vals(),
            "name": "Test Motor Product",
            "default_code": "50000001",
            "list_price": 500.0,
            "source": "motor",  # Motor-sourced product
        })


@tagged("post_install", "-at_install")
class ProductConnectHttpCase(HttpCase):
    """Base class for HTTP/browser tests with secure test user creation."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # Disable mail tracking for better performance
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create secure test user for authentication
        cls._create_test_user()

        # Set up any common test data
        cls._setup_test_data()

    @classmethod
    def _create_test_user(cls, name: str = "Test User", login_prefix: str = "test_user") -> "odoo.model.res_users":
        """Create a test user with secure password and basic permissions."""
        # Generate unique login to avoid conflicts when tests run in parallel
        unique_suffix = secrets.token_hex(4)
        login = f"{login_prefix}_{unique_suffix}"

        # Generate cryptographically secure password
        secure_password = secrets.token_urlsafe(32)

        cls.test_user = cls.env["res.users"].create(
            {
                "name": name,
                "login": login,
                "password": secure_password,
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("base.group_system").id,  # Required for module access in tests
                        ],
                    )
                ],
            }
        )

        # Store password for authentication
        cls.test_user_password = secure_password

        return cls.test_user

    @classmethod
    def _setup_test_data(cls) -> None:
        """Override this method to set up test-specific data."""
        pass

    def authenticate_test_user(self) -> None:
        """Helper method to authenticate with the test user."""
        self.authenticate(self.test_user.login, self.test_user_password)


@tagged("post_install", "-at_install")
class ProductConnectIntegrationCase(ProductConnectHttpCase):
    """Base class for integration tests (JS/tours) with common motor test data."""

    @classmethod
    def _setup_test_data(cls) -> None:
        """Set up common test data for integration tests."""
        super()._setup_test_data()

        # Ensure we have at least one motor for tests
        if not cls.env["motor"].search([]):
            cls.test_motor = cls.env["motor"].create(
                {
                    "manufacturer": "TestMaker",
                    "stroke": "Four",
                    "configuration": "V8",
                    "horsepower": 250,
                    "location": "A1",
                    "serial_number": f"SN_{secrets.token_hex(4)}",
                    "year": 2024,
                    "model": "SuperV8",
                }
            )
        else:
            cls.test_motor = cls.env["motor"].search([], limit=1)
