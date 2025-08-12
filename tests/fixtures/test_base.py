"""Base test classes for product_connect module tests."""

import secrets

from ..common_imports import TransactionCase, HttpCase, tagged, STANDARD_TAGS, UNIT_TAGS, TOUR_TAGS


@tagged(*STANDARD_TAGS)
class ProductConnectTransactionCase(TransactionCase):
    """Base class for transaction-based tests with common setup."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        # Run as admin user to ensure permissions for test setup
        # This MUST be done before any data creation
        cls.env = cls.env(user=cls.env.ref("base.user_admin"))

        # Disable mail tracking for better performance
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Common test data setup
        cls._setup_test_data()

    def setUp(self) -> None:
        """Override to ensure each test method runs with admin privileges."""
        super().setUp()
        # Ensure each test method uses admin environment
        self.env = self.env(user=self.env.ref("base.user_admin"))
        # Add context for testing
        self.env = self.env(context=dict(self.env.context, skip_shopify_sync=True, tracking_disable=True))

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
        cls.test_product_tag = cls.env["product.tag"].create(
            {
                "name": "Test Suite Data",
                "sequence": 999,
                "color": 10,  # Red color for visibility
            }
        )

        # Create CRM tag for test sales orders
        cls.test_order_tag = cls.env["crm.tag"].create(
            {
                "name": "Test Suite Data",
                "color": 10,  # Red color for visibility
            }
        )

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
    def _create_multigraph_test_products(cls) -> None:
        """Create test products specifically for multigraph view testing."""
        from datetime import date

        cls.test_products = cls.env["product.template"].create(
            [
                {
                    "name": f"Test Product {i}",
                    "default_code": f"{10000 + i}",  # Valid SKU
                    "list_price": 100 * i,
                    "standard_price": 60 * i,
                    "type": "consu",
                    "is_ready_for_sale": True,  # Required for multigraph
                    "is_ready_for_sale_last_enabled_date": date(2025, 1, i),  # Required for multigraph
                    "initial_quantity": 10 * i,
                    "initial_price_total": 1000 * i,
                    "initial_cost_total": 600 * i,
                }
                for i in range(1, 5)
            ]
        )

    @classmethod
    def _create_motor_dependencies(cls) -> dict:
        """Create and return motor dependencies (manufacturer, stroke, config)."""
        # Check if dependencies already exist to avoid duplicates
        manufacturer = cls.env["product.manufacturer"].search([("name", "=", "Test Manufacturer")], limit=1)
        if not manufacturer:
            manufacturer = cls.env["product.manufacturer"].create({"name": "Test Manufacturer", "is_motor_manufacturer": True})

        stroke = cls.env["motor.stroke"].search([("code", "=", "4")], limit=1)
        if not stroke:
            stroke = cls.env["motor.stroke"].sudo().create({"name": "4 Stroke", "code": "4"})

        config = cls.env["motor.configuration"].search([("code", "=", "V6")], limit=1)
        if not config:
            config = cls.env["motor.configuration"].sudo().create({"name": "V6", "code": "V6"})

        return {
            "manufacturer": manufacturer,
            "stroke": stroke,
            "config": config,
        }

    @classmethod
    def _create_motor(cls, **kwargs: int | float | str | bool) -> "odoo.model.motor":
        """Create a motor with standard test values.

        Args:
            **kwargs: Additional values to override defaults

        Returns:
            Created motor record
        """
        deps = cls._create_motor_dependencies()

        motor_vals = {
            "manufacturer": deps["manufacturer"].id,
            "stroke": deps["stroke"].id,
            "configuration": deps["config"].id,
            "horsepower": 100.0,
            "year": "2024",
            "model": "TEST",
            "cost": 1000.0,
            "location": f"A{secrets.token_hex(2)}",  # Random location to avoid conflicts
            "serial_number": f"SN{secrets.token_hex(4)}",  # Random serial to avoid conflicts
        }
        motor_vals.update(kwargs)

        return cls.env["motor"].create(motor_vals)

    @classmethod
    def _create_motor_product(cls, **kwargs: dict | int | float | str | bool) -> "odoo.model.product_template":
        """Create a complete motor product with all dependencies.

        Args:
            **kwargs: Additional values to override defaults. Can include:
                - motor_vals: dict of motor-specific values
                - template_vals: dict of motor product template values
                - product_vals: dict of product template values
                - with_image: bool to add a test image (default: False)

        Returns:
            Created product.template record
        """
        # Extract specific kwarg dicts
        motor_vals = kwargs.pop("motor_vals", {})
        template_vals = kwargs.pop("template_vals", {})
        with_image = kwargs.pop("with_image", False)

        # Create motor if not provided
        motor = kwargs.pop("motor", None)
        if not motor:
            motor = cls._create_motor(**motor_vals)

        # Create motor product template if not provided
        motor_product_template = kwargs.pop("motor_product_template", None)
        if not motor_product_template:
            deps = cls._create_motor_dependencies()
            default_template_vals = {
                "name": "Test Motor Part",
                "strokes": [(4, deps["stroke"].id)],
                "configurations": [(4, deps["config"].id)],
                "manufacturers": [(4, deps["manufacturer"].id)],
            }
            default_template_vals.update(template_vals)
            motor_product_template = cls.env["motor.product.template"].create(default_template_vals)

        # Create motor product
        product_vals = {
            "name": "Test Motor Product",
            "default_code": str(60000000 + secrets.randbelow(999999)),  # Random valid SKU
            "type": "consu",
            "source": "motor",
            "motor": motor.id,
            "motor_product_template": motor_product_template.id,
        }
        product_vals.update(kwargs)

        product = cls.env["product.template"].create(product_vals)

        # Add image if requested
        if with_image:
            # noinspection SpellCheckingInspection
            cls.env["product.image"].create(
                {
                    "product_tmpl_id": product.id,
                    "image_1920": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
                    "name": "test_image",
                }
            )

        return product

    @classmethod
    def _create_default_test_products(cls) -> None:
        """Create default test products that can be used across tests."""
        # First create test partner that products might need
        cls.test_partner = cls.env["res.partner"].create(
            {
                **cls._get_default_partner_vals(),
                "name": "Test Customer",
            }
        )

        # Additional test partners
        cls.test_partners = []
        for i in range(3):
            partner = cls.env["res.partner"].create(
                {
                    **cls._get_default_partner_vals(),
                    "name": f"Test Customer {i + 1}",
                    "email": f"test{i + 1}@example.com",
                }
            )
            cls.test_partners.append(partner)

        # Standard consumable product with valid SKU
        cls.test_product = cls.env["product.product"].create(
            {
                **cls._get_default_product_vals(),
                "name": "Test Product",
                "default_code": "10000001",  # Valid 8-digit SKU
            }
        )

        # Service product (no SKU validation)
        cls.test_service = cls.env["product.product"].create(
            {
                **cls._get_default_product_vals(),
                "name": "Test Service",
                "default_code": "SERVICE-001",  # Services can have any SKU
                "type": "service",
                "list_price": 50.0,
            }
        )

        # Ready-to-sell product for Shopify sync tests
        cls.test_product_ready = cls.env["product.product"].create(
            {
                **cls._get_default_product_vals(),
                "name": "Test Product Ready",
                "default_code": "20000001",  # Valid 8-digit SKU
                "list_price": 200.0,
                "is_ready_for_sale": True,
                "is_published": True,
            }
        )

        # Create a pool of generic test products for various test scenarios
        cls.test_products = []
        for i in range(10):
            sku_number = 30000001 + i
            product = cls.env["product.product"].create(
                {
                    **cls._get_default_product_vals(),
                    "name": f"Test Product {i + 1}",
                    "default_code": str(sku_number),  # Valid 8-digit SKUs: 30000001-30000010
                    "list_price": 50.0 + (i * 10),  # Varying prices
                }
            )
            cls.test_products.append(product)

        # Create test products with different states for specific scenarios
        cls.test_product_not_for_sale = cls.env["product.product"].create(
            {
                **cls._get_default_product_vals(),
                "name": "Test Product Not For Sale",
                "default_code": "40000001",
                "list_price": 150.0,
                "sale_ok": False,  # Not available for sale
            }
        )

        cls.test_product_unpublished = cls.env["product.product"].create(
            {
                **cls._get_default_product_vals(),
                "name": "Test Product Unpublished",
                "default_code": "40000002",
                "list_price": 175.0,
                "is_published": False,  # Not published
                "is_ready_for_sale": True,
            }
        )

        cls.test_product_motor = cls.env["product.product"].create(
            {
                **cls._get_default_product_vals(),
                "name": "Test Motor Product",
                "default_code": "50000001",
                "list_price": 500.0,
                "source": "motor",  # Motor-sourced product
            }
        )


@tagged(*STANDARD_TAGS)
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
                            cls.env.ref("base.group_partner_manager").id,  # Required for partner creation in tests
                            cls.env.ref("base.group_erp_manager").id,  # Required for full app access in tests
                        ],
                    )
                ],
            }
        )

        # Store password for authentication
        cls.test_user_password = secure_password

        # Also ensure admin user has a known password for browser tests fallback
        admin_user = cls.env.ref("base.user_admin")
        admin_user.write({"password": "admin"})

        return cls.test_user

    @classmethod
    def _setup_test_data(cls) -> None:
        """Override this method to set up test-specific data."""
        pass

    def authenticate_test_user(self) -> None:
        """Helper method to authenticate with the test user."""
        self.authenticate(self.test_user.login, self.test_user_password)


@tagged(*STANDARD_TAGS)
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


# ============================================================================
# NEW BASE CLASSES FOR TEST MIGRATION - SESSION 2
# ============================================================================


@tagged(*UNIT_TAGS)
class ProductConnectUnitCase(TransactionCase):
    """Base class for fast unit tests with best isolation.

    In Odoo 18, TransactionCase provides savepoint-per-test-method isolation.
    Each test method gets its own savepoint and automatic rollback.
    Use this for tests that:
    - Test business logic in isolation
    - Don't need production data
    - Can create their own minimal test data
    - Should run very fast (<1 second per test)

    Examples: field validations, computed fields, constraints, simple methods
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        # Run as admin user to ensure permissions for test setup
        cls.env = cls.env(user=cls.env.ref("base.user_admin"))

        # Disable mail tracking and Shopify sync for better performance
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                skip_shopify_sync=True,
                no_reset_password=True,
                mail_create_nosubscribe=True,
                mail_create_nolog=True,
            )
        )

        # Create minimal test data for unit tests
        cls._setup_minimal_test_data()

    @classmethod
    def _setup_minimal_test_data(cls) -> None:
        """Create only the essential test data needed for unit tests."""
        # Create a minimal test product with unique SKU to avoid conflicts
        import secrets

        unique_sku = f"1{secrets.randbelow(999):03d}"  # Generates SKU like 1001, 1123, etc.
        cls.test_product = cls.env["product.template"].create(
            {
                "name": "Unit Test Product",
                "default_code": unique_sku,  # Unique 4-digit SKU
                "type": "consu",
                "list_price": 100.0,
            }
        )

        # Create a minimal test partner
        cls.test_partner = cls.env["res.partner"].create(
            {
                "name": "Unit Test Partner",
                "email": "unit@test.com",
            }
        )

        # Create a service product (no SKU validation)
        cls.test_service = cls.env["product.template"].create(
            {
                "name": "Unit Test Service",
                "type": "service",
                "list_price": 50.0,
            }
        )

    def setUp(self) -> None:
        """Ensure each test method gets a clean savepoint."""
        super().setUp()
        # Each test method automatically gets its own savepoint in TransactionCase


@tagged("post_install", "-at_install", "validation_test")
class ProductConnectValidationCase(TransactionCase):
    """Base class for validation tests that need production data.

    Transaction per test class for integration scenarios.
    Use this for tests that:
    - Validate behavior with real production data complexity
    - Test import/export idempotency
    - Verify data migrations
    - Test performance with real volumes
    - Validate integrations with actual data patterns

    Examples: bulk operations, import validation, data integrity checks
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        # Run as admin user to ensure permissions
        cls.env = cls.env(user=cls.env.ref("base.user_admin"))

        # Keep tracking enabled for validation tests (might be important)
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                skip_shopify_sync=True,  # Still skip external sync
            )
        )

        # Validation tests use production data, so minimal setup
        cls._setup_validation_context()

    @classmethod
    def _setup_validation_context(cls) -> None:
        """Set up context for validation tests."""
        # Validation tests typically work with existing production data
        # So we don't create test data, but we might need to set up context

        # Store counts of production data for validation
        cls.product_count = cls.env["product.template"].search_count([])
        cls.partner_count = cls.env["res.partner"].search_count([])
        cls.order_count = cls.env["sale.order"].search_count([])

        # You can add more context setup here as needed
        pass


@tagged(*TOUR_TAGS)
class ProductConnectTourCase(HttpCase):
    """Base class for browser UI tests.

    Provides HTTP stack and browser automation.
    Use this for tests that:
    - Test user workflows through the UI
    - Validate form interactions
    - Test JavaScript components
    - Verify end-to-end scenarios

    Examples: form tours, workflow tours, UI component tests
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        # Disable mail tracking for better performance
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                skip_shopify_sync=True,
            )
        )

        # Create test user for browser tests
        cls._create_tour_test_user()

        # Set up minimal data for tours
        cls._setup_tour_test_data()

    @classmethod
    def _create_tour_test_user(cls) -> None:
        """Create a test user specifically for tour tests."""
        # Generate unique login to avoid conflicts
        unique_suffix = secrets.token_hex(4)
        login = f"tour_user_{unique_suffix}"

        # Generate secure password
        password = secrets.token_urlsafe(16)

        cls.tour_user = cls.env["res.users"].create(
            {
                "name": "Tour Test User",
                "login": login,
                "password": password,
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("base.group_system").id,
                        ],
                    )
                ],
            }
        )

        cls.tour_user_password = password

        # Ensure admin has known password for fallback
        admin = cls.env.ref("base.user_admin")
        admin.write({"password": "admin"})

    @classmethod
    def _setup_tour_test_data(cls) -> None:
        """Set up minimal test data for tour tests."""
        # Create a test product for UI interaction
        cls.test_product = cls.env["product.template"].create(
            {
                "name": "Tour Test Product",
                "default_code": "12345678",  # Valid 8-digit SKU
                "type": "consu",
                "list_price": 100.0,
                "is_ready_for_sale": True,
            }
        )

        # Create a test partner for forms
        cls.test_partner = cls.env["res.partner"].create(
            {
                "name": "Tour Test Customer",
                "email": "tour@test.com",
            }
        )

    def start_tour(self, url_path: str, tour_name: str, login: str | None = None, **kwargs: object) -> None:
        """Helper to start a tour with proper authentication."""
        if login:
            # Use specific login
            self.authenticate(login, self.tour_user_password)
        else:
            # Use default tour user
            self.authenticate(self.tour_user.login, self.tour_user_password)

        # Call parent start_tour
        super().start_tour(url_path, tour_name, login=False, **kwargs)
