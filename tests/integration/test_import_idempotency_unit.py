"""Unit tests for data idempotency at the _import_one level

These tests verify that importing the same data multiple times doesn't create
duplicates and that updates are handled correctly. They test at the individual
record level without the complexity of date filtering or sync infrastructure.
"""

from odoo.tests import tagged
from ..fixtures.base import IntegrationTestCase
from ..fixtures.shopify_responses import (
    create_shopify_order_response,
    create_shopify_customer_response,
    create_shopify_product_response,
    create_shopify_order_line_item_response,
    create_shopify_variant_response,
    create_shopify_address_response,
)
from ...services.shopify.gql import OrderFields, CustomerFields, ProductFields
from ...services.shopify.sync.importers.order_importer import OrderImporter
from ...services.shopify.sync.importers.customer_importer import CustomerImporter
from ...services.shopify.sync.importers.product_importer import ProductImporter


@tagged("post_install", "-at_install", "integration_test")
class TestImportIdempotencyUnit(IntegrationTestCase):
    """Unit tests for import idempotency at the record level"""

    def setUp(self) -> None:
        super().setUp()
        self._setup_import_idempotency_test()

    def _setup_import_idempotency_test(self):
        """Set up test data for import idempotency tests."""
        # Create test product with SKU
        self.test_product = self.env["product.product"].create({
            "name": "Test Product",
            "default_code": "TEST001",  # SKU needed for line items
            "list_price": 100.0,
            "standard_price": 50.0,
        })
        
        # Create sync record for importers
        self.sync_record = self.env["shopify.sync"].create({
            "mode": "import_changed_orders",
        })

    def test_order_import_creates_new_order(self) -> None:
        """Test that importing a new order creates it and returns True"""
        importer = OrderImporter(self.env, self.sync_record)

        order_data = create_shopify_order_response(
            gid="gid://shopify/Order/new_order_1",
            name="#NEW-001",
            customer=create_shopify_customer_response(gid="gid://shopify/Customer/cust_1", email="customer1@test.com"),
            line_items=[
                create_shopify_order_line_item_response(
                    sku=self.test_product.default_code,
                    variant_id="987654321",
                )
            ],
        )
        order = OrderFields(**order_data)

        # Import new order
        result = importer._import_one(order)

        # Should return True for new order
        self.assertTrue(result)

        # Verify order was created
        orders = self.env["sale.order"].search([("shopify_order_id", "=", "new_order_1")])
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].name, "#NEW-001")

    def test_order_import_existing_unchanged_returns_false(self) -> None:
        """Test that importing an existing unchanged order returns False"""
        importer = OrderImporter(self.env, self.sync_record)

        order_data = create_shopify_order_response(
            gid="gid://shopify/Order/existing_order_1",
            name="#EXIST-001",
            customer=create_shopify_customer_response(gid="gid://shopify/Customer/cust_2", email="customer2@test.com"),
            line_items=[
                create_shopify_order_line_item_response(
                    sku=self.test_product.default_code,
                    variant_id="987654321",
                )
            ],
        )
        order = OrderFields(**order_data)

        # First import
        result1 = importer._import_one(order)
        self.assertTrue(result1)

        # Second import of same data
        result2 = importer._import_one(order)

        # Should return False - no changes
        self.assertFalse(result2)

        # Verify still only one order
        orders = self.env["sale.order"].search([("shopify_order_id", "=", "existing_order_1")])
        self.assertEqual(len(orders), 1)

    def test_order_import_with_updates_returns_true(self) -> None:
        """Test that importing an order with updates returns True"""
        importer = OrderImporter(self.env, self.sync_record)

        # Initial order
        order_data = create_shopify_order_response(
            gid="gid://shopify/Order/update_order_1",
            name="#UPDATE-001",
            customer=create_shopify_customer_response(gid="gid://shopify/Customer/cust_3", email="customer3@test.com"),
            line_items=[
                create_shopify_order_line_item_response(
                    sku=self.test_product.default_code,
                    variant_id="987654321",
                )
            ],
        )
        order = OrderFields(**order_data)

        # First import
        result1 = importer._import_one(order)
        self.assertTrue(result1)

        # Update order data (change quantity)
        updated_order_data = create_shopify_order_response(
            gid="gid://shopify/Order/update_order_1",
            name="#UPDATE-001",
            customer=create_shopify_customer_response(gid="gid://shopify/Customer/cust_3", email="customer3@test.com"),
            line_items=[
                create_shopify_order_line_item_response(
                    sku=self.test_product.default_code,
                    variant_id="987654321",
                    quantity=2,  # Changed quantity
                )
            ],
        )
        updated_order = OrderFields(**updated_order_data)

        # Import with updates
        result2 = importer._import_one(updated_order)

        # Should return True - order was updated
        self.assertTrue(result2)

        # Verify order was updated
        orders = self.env["sale.order"].search([("shopify_order_id", "=", "update_order_1")])
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].order_line[0].product_uom_qty, 2)

    def test_customer_import_creates_new_customer(self) -> None:
        """Test that importing a new customer creates it and returns True"""
        importer = CustomerImporter(self.env, self.sync_record)

        customer_data = create_shopify_customer_response(
            gid="gid://shopify/Customer/new_customer_1",
            email="newcustomer@test.com",
            first_name="New",
            last_name="Customer",
        )
        customer = CustomerFields(**customer_data)

        # Import new customer
        result = importer.import_customer(customer)

        # Should return True for new customer
        self.assertTrue(result)

        # Verify customer was created
        customers = self.env["res.partner"].search([("shopify_customer_id", "=", "new_customer_1")])
        self.assertEqual(len(customers), 1)
        self.assertEqual(customers[0].email, "newcustomer@test.com")

    def test_customer_import_existing_unchanged_returns_false(self) -> None:
        """Test that importing an existing unchanged customer returns False"""
        importer = CustomerImporter(self.env, self.sync_record)

        customer_data = create_shopify_customer_response(
            gid="gid://shopify/Customer/existing_customer_1",
            email="existing@test.com",
            first_name="Existing",
            last_name="Customer",
        )
        customer = CustomerFields(**customer_data)

        # First import
        result1 = importer.import_customer(customer)
        self.assertTrue(result1)

        # Second import of same data
        result2 = importer.import_customer(customer)

        # Should return False - no changes
        self.assertFalse(result2)

        # Verify still only one customer
        customers = self.env["res.partner"].search([("shopify_customer_id", "=", "existing_customer_1")])
        self.assertEqual(len(customers), 1)

    def test_customer_import_with_new_address_returns_true(self) -> None:
        """Test that adding an address to a customer returns True"""
        importer = CustomerImporter(self.env, self.sync_record)

        # Initial customer without address - use overrides to ensure no address
        customer_data = create_shopify_customer_response(
            gid="gid://shopify/Customer/address_customer_1",
            email="address@test.com",
            first_name="Address",
            last_name="Customer",
            **{
                "defaultAddress": None,  # Override to ensure no default address
                "addressesV2": {"nodes": []},  # Empty addresses list
            },
        )
        customer = CustomerFields(**customer_data)

        # First import
        result1 = importer.import_customer(customer)
        self.assertTrue(result1)

        # Verify no address data initially
        customers = self.env["res.partner"].search([("shopify_customer_id", "=", "address_customer_1")])
        self.assertEqual(len(customers), 1)
        self.assertFalse(customers[0].street)  # Should have no street initially

        # Add address
        address = create_shopify_address_response(
            gid="gid://shopify/CustomerAddress/addr_1",
            address1="123 New Street",
            city="New City",
        )
        updated_customer_data = create_shopify_customer_response(
            gid="gid://shopify/Customer/address_customer_1",
            email="address@test.com",
            first_name="Address",
            last_name="Customer",
            default_address=address,
            addresses=[address],
        )
        updated_customer = CustomerFields(**updated_customer_data)

        # Import with new address
        result2 = importer.import_customer(updated_customer)

        # Should return True - address was added
        self.assertTrue(result2)

        # Verify address was added to main record
        customers = self.env["res.partner"].search([("shopify_customer_id", "=", "address_customer_1")])
        self.assertEqual(len(customers), 1)
        self.assertEqual(customers[0].street, "123 New Street")

    def test_product_import_creates_new_product(self) -> None:
        """Test that importing a new product creates it and returns True"""
        importer = ProductImporter(self.env, self.sync_record)

        product_data = create_shopify_product_response(
            gid="gid://shopify/Product/new_product_1",
            title="New Product",
            vendor="Test Manufacturer",
            product_type="Motors",
            variants=[
                create_shopify_variant_response(
                    gid="gid://shopify/ProductVariant/new_variant_1",
                    sku="NEW001",
                    price="149.99",
                )
            ],
        )
        product = ProductFields(**product_data)

        # Import new product
        result = importer._import_one(product)

        # Should return True for new product
        self.assertTrue(result)

        # Verify product was created
        products = self.env["product.product"].search([("shopify_product_id", "=", "new_product_1")])
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].name, "New Product")
        self.assertEqual(products[0].default_code, "NEW001")

    def test_product_import_existing_with_old_timestamp_returns_false(self) -> None:
        """Test that importing a product with old timestamp returns False"""
        importer = ProductImporter(self.env, self.sync_record)

        # Create product with specific timestamps
        product_data = create_shopify_product_response(
            gid="gid://shopify/Product/timestamp_product_1",
            title="Timestamp Product",
            vendor="Test Manufacturer",
            product_type="Motors",
            created_at="2023-01-01T00:00:00Z",
            updated_at="2023-01-01T00:00:00Z",
            variants=[
                create_shopify_variant_response(
                    gid="gid://shopify/ProductVariant/timestamp_variant_1",
                    sku="TIME001",
                    price="199.99",
                )
            ],
        )
        product = ProductFields(**product_data)

        # First import
        result1 = importer._import_one(product)
        self.assertTrue(result1)

        # Second import with same (old) data
        result2 = importer._import_one(product)

        # Should return False - timestamp hasn't changed
        self.assertFalse(result2)

        # Verify still only one product
        products = self.env["product.product"].search([("shopify_product_id", "=", "timestamp_product_1")])
        self.assertEqual(len(products), 1)

    def test_product_import_uses_first_variant(self) -> None:
        """Test that importing a product with multiple variants only uses the first one"""
        importer = ProductImporter(self.env, self.sync_record)

        product_data = create_shopify_product_response(
            gid="gid://shopify/Product/multi_variant_product",
            title="Multi Variant Product",
            vendor="Test Manufacturer",
            product_type="Motors",
            variants=[
                create_shopify_variant_response(
                    gid="gid://shopify/ProductVariant/variant_1",
                    sku="MULTI001",
                ),
                create_shopify_variant_response(
                    gid="gid://shopify/ProductVariant/variant_2",
                    sku="MULTI002",
                    price="149.99",
                ),
            ],
        )
        product = ProductFields(**product_data)

        # Import product with multiple variants
        result = importer._import_one(product)

        # Should return True
        self.assertTrue(result)

        # ProductImporter only processes the first variant
        variants = self.env["product.product"].search([("shopify_product_id", "=", "multi_variant_product")])
        self.assertEqual(len(variants), 1)

        # Check that it used the first variant
        self.assertEqual(variants[0].default_code, "MULTI001")
        self.assertEqual(variants[0].shopify_variant_id, "variant_1")
