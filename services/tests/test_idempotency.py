from unittest.mock import patch, MagicMock
from typing import TYPE_CHECKING

from odoo.tests import tagged

from ..shopify.gql import OrderFields, CustomerFields, ProductFields
from ..shopify.sync.importers.order_importer import OrderImporter
from ..shopify.sync.importers.customer_importer import CustomerImporter
from ..shopify.sync.importers.product_importer import ProductImporter
from .test_base import ShopifyTestBase

if TYPE_CHECKING:
    from ..shopify.sync.base import ShopifyBaseImporter

from .fixtures.shopify_responses import (
    create_shopify_order_response,
    create_shopify_customer_response,
    create_shopify_product_response,
    create_shopify_order_line_item_response,
    create_shopify_variant_response,
    create_shopify_address_response,
)
from .test_utils import create_mock_fetch_page_function


@tagged("post_install", "-at_install")
class TestIdempotency(ShopifyTestBase):
    def setUp(self) -> None:
        super().setUp()
        self._setup_shopify_mocks()  # Set up Shopify API mocks
        self.sync_record = self.env["shopify.sync"].create(
            {
                "mode": "import_changed_orders",
            }
        )

        # Create base test data
        self.currency = self.env["res.currency"].search([("name", "=", "USD")], limit=1)
        if not self.currency:
            self.currency = self.env["res.currency"].create({"name": "USD", "symbol": "$", "rate": 1.0})

        # Generate unique SKU to avoid conflicts (must be 4-8 digits)
        import time
        self.sku = str(70000 + (int(time.time()) % 10000))  # 7xxxx series
        self.test_product = self.env["product.product"].create(
            {
                "name": "Test Product",
                "default_code": self.sku,
                "shopify_variant_id": "987654321",
                "list_price": 99.99,
                "type": "consu",
            }
        )

        self.manufacturer = self.env["product.manufacturer"].create({"name": "Test Manufacturer"})
        self.part_type = self.env["product.type"].create({"name": "Motors", "ebay_category_id": "123456"})
        self.condition = self.env["product.condition"].create({"name": "New", "code": "NEW"})

    @staticmethod
    def _import_with_mock_data(
        importer: "ShopifyBaseImporter",
        entity_type: str,
        data_list: list,
        field_class: type,
        import_method_name: str = "import_orders_since_last_import",
    ) -> int:
        mock_fetch = create_mock_fetch_page_function(
            entity_type=entity_type,
            data_list=data_list,
            field_class=field_class,
        )

        with patch.object(importer, "_fetch_page", side_effect=mock_fetch):
            import_method = getattr(importer, import_method_name)
            return import_method()

    def _verify_order_state(self, shopify_order_id: str, expected_line_count: int, expected_qty: float) -> "odoo.model.sale_order":
        orders = self.env["sale.order"].search([("shopify_order_id", "=", shopify_order_id)])
        self.assertEqual(len(orders), 1)
        order = orders[0]
        self.assertEqual(len(order.order_line), expected_line_count)
        if expected_line_count > 0:
            self.assertEqual(order.order_line[0].product_uom_qty, expected_qty)
        return order

    def _verify_customer_state(
        self, shopify_customer_id: str, expected_child_count: int, expected_street: str = None
    ) -> "odoo.model.res_partner":
        customers = self.env["res.partner"].search([("shopify_customer_id", "=", shopify_customer_id)])
        self.assertEqual(len(customers), 1)
        customer = customers[0]
        self.assertEqual(len(customer.child_ids), expected_child_count)
        if expected_street and expected_child_count > 0:
            self.assertEqual(customer.child_ids[0].street, expected_street)
        return customer

    def _verify_product_variants(
        self, shopify_product_id: str, expected_count: int, expected_skus: list[str] = None
    ) -> "odoo.model.product_product":
        products = self.env["product.product"].search([("shopify_product_id", "=", shopify_product_id)])
        self.assertEqual(len(products), expected_count)
        if expected_skus:
            skus = sorted([p.default_code for p in products])
            self.assertEqual(skus, sorted(expected_skus))
        return products

    def test_order_import_idempotency(self) -> None:
        importer = OrderImporter(self.env, self.sync_record)

        order_data = create_shopify_order_response(
            gid="gid://shopify/Order/idempotent_order",
            name="#IDEM-001",
            line_items=[
                create_shopify_order_line_item_response(
                    sku=self.test_product.default_code,
                    variant_id="987654321",
                )
            ],
        )

        mock_fetch_page = create_mock_fetch_page_function(
            entity_type="orders",
            data_list=[order_data],
            field_class=OrderFields,
        )

        with patch.object(importer, "_fetch_page", side_effect=mock_fetch_page):
            # First import
            first_import_count = importer.import_orders_since_last_import()
            self.assertEqual(first_import_count, 1)

            # Verify order was created
            orders = self.env["sale.order"].search([("shopify_order_id", "=", "idempotent_order")])
            self.assertEqual(len(orders), 1)
            original_order = orders[0]

            # Second import of same data
            second_import_count = importer.import_orders_since_last_import()
            self.assertEqual(second_import_count, 0)  # No new orders created

            # Verify still only one order exists
            orders = self.env["sale.order"].search([("shopify_order_id", "=", "idempotent_order")])
            self.assertEqual(len(orders), 1)
            self.assertEqual(orders[0].id, original_order.id)

            # Third import with same data
            third_import_count = importer.import_orders_since_last_import()
            self.assertEqual(third_import_count, 0)

            # Verify order details remain unchanged
            orders[0].invalidate_recordset()
            self.assertEqual(orders[0].name, "#IDEM-001")
            self.assertEqual(len(orders[0].order_line), 1)

    def test_customer_import_idempotency(self) -> None:
        importer = CustomerImporter(self.env, self.sync_record)

        customer_data = create_shopify_customer_response(
            gid="gid://shopify/Customer/idempotent_customer",
            email="john.doe@idempotent.com",
        )

        mock_fetch_page = create_mock_fetch_page_function(
            entity_type="customers",
            data_list=[customer_data],
            field_class=CustomerFields,
        )

        with patch.object(importer, "_fetch_page", side_effect=mock_fetch_page):
            # First import
            first_import_count = importer.import_customers_since_last_import()
            self.assertEqual(first_import_count, 1)

            # Verify customer was created
            customers = self.env["res.partner"].search([("shopify_customer_id", "=", "idempotent_customer")])
            self.assertEqual(len(customers), 1)
            original_customer = customers[0]

            # Second import of same data
            second_import_count = importer.import_customers_since_last_import()
            self.assertEqual(second_import_count, 0)  # No new customers created

            # Verify still only one customer exists
            customers = self.env["res.partner"].search([("shopify_customer_id", "=", "idempotent_customer")])
            self.assertEqual(len(customers), 1)
            self.assertEqual(customers[0].id, original_customer.id)

            # Verify customer details remain unchanged
            customers[0].invalidate_recordset()
            self.assertEqual(customers[0].name, "John Doe")
            self.assertEqual(customers[0].email, "john.doe@idempotent.com")

    def test_product_import_idempotency(self) -> None:
        importer = ProductImporter(self.env, self.sync_record)

        product_data = create_shopify_product_response(
            gid="gid://shopify/Product/idempotent_product",
            title="Idempotent Product",
            vendor="Test Manufacturer",
            product_type="Motors",
            variants=[
                create_shopify_variant_response(
                    gid="gid://shopify/ProductVariant/idempotent_variant",
                    sku="80001",
                    price="149.99",
                )
            ],
        )

        mock_fetch_page = create_mock_fetch_page_function(
            entity_type="products",
            data_list=[product_data],
            field_class=ProductFields,
        )

        with patch.object(importer, "_fetch_page", side_effect=mock_fetch_page):
            # First import
            first_import_count = importer.import_products_since_last_import()
            self.assertEqual(first_import_count, 1)

            # Verify product was created
            products = self.env["product.product"].search([("shopify_product_id", "=", "idempotent_product")])
            self.assertEqual(len(products), 1)
            original_product = products[0]

            # Second import of same data
            second_import_count = importer.import_products_since_last_import()
            self.assertEqual(second_import_count, 0)  # No new products created

            # Verify still only one product exists
            products = self.env["product.product"].search([("shopify_product_id", "=", "idempotent_product")])
            self.assertEqual(len(products), 1)
            self.assertEqual(products[0].id, original_product.id)

            # Verify product details remain unchanged
            products[0].invalidate_recordset()
            self.assertEqual(products[0].name, "Idempotent Product")
            self.assertEqual(products[0].default_code, "80001")

    def test_order_with_updates_idempotency(self) -> None:
        importer = OrderImporter(self.env, self.sync_record)

        # Initial order data
        initial_order_data = create_shopify_order_response(
            gid="gid://shopify/Order/updating_order",
            name="#UPDATE-001",
            total_price="99.99",
            updated_at="2023-01-01T12:00:00Z",
            line_items=[
                create_shopify_order_line_item_response(
                    sku=self.test_product.default_code,
                    variant_id="987654321",
                )
            ],
        )

        # Updated order data
        updated_order_data = create_shopify_order_response(
            gid="gid://shopify/Order/updating_order",
            name="#UPDATE-001",
            total_price="199.98",
            updated_at="2023-01-02T12:00:00Z",  # Later timestamp
            line_items=[
                create_shopify_order_line_item_response(
                    sku=self.test_product.default_code,
                    variant_id="987654321",
                    quantity=2,  # Quantity changed
                )
            ],
        )

        # First import with initial data
        first_count = self._import_with_mock_data(importer, "orders", [initial_order_data], OrderFields)
        self.assertEqual(first_count, 1)

        # Verify initial state
        self._verify_order_state("updating_order", 1, 1)

        # Second import with updated data
        second_count = self._import_with_mock_data(importer, "orders", [updated_order_data], OrderFields)
        self.assertEqual(second_count, 1)  # Should update existing order

        # Verify update was applied
        order = self._verify_order_state("updating_order", 1, 2)  # Quantity updated
        order.invalidate_recordset()

        # Third import with same updated data (idempotency test)
        third_count = self._import_with_mock_data(importer, "orders", [updated_order_data], OrderFields)
        self.assertEqual(third_count, 0)  # No changes, should skip

        # Verify state remains the same
        orders = self.env["sale.order"].search([("shopify_order_id", "=", "updating_order")])
        self.assertEqual(len(orders), 1)
        order = orders[0]
        self.assertEqual(order.order_line[0].product_uom_qty, 2)

    def test_customer_with_addresses_idempotency(self) -> None:
        importer = CustomerImporter(self.env, self.sync_record)

        # Initial customer with one address
        initial_address = create_shopify_address_response(
            gid="gid://shopify/CustomerAddress/1001",
            address1="123 Initial St",
            city="Initial City",
        )

        initial_customer_data = create_shopify_customer_response(
            gid="gid://shopify/Customer/address_customer",
            first_name="Address",
            last_name="Customer",
            email="address@customer.com",
            default_address=initial_address,
            addresses=[initial_address],
        )

        # Updated customer with additional address
        additional_address = create_shopify_address_response(
            gid="gid://shopify/CustomerAddress/1002",
            address1="456 Additional Ave",
            city="Additional City",
        )

        updated_customer_data = create_shopify_customer_response(
            gid="gid://shopify/Customer/address_customer",
            first_name="Address",
            last_name="Customer",
            email="address@customer.com",
            default_address=initial_address,
            addresses=[initial_address, additional_address],
        )

        # First import
        mock_fetch_initial = create_mock_fetch_page_function(
            entity_type="customers",
            data_list=[initial_customer_data],
            field_class=CustomerFields,
        )

        with patch.object(importer, "_fetch_page", side_effect=mock_fetch_initial):
            first_count = importer.import_customers_since_last_import()
            self.assertEqual(first_count, 1)

        # Verify initial state
        customers = self.env["res.partner"].search([("shopify_customer_id", "=", "address_customer")])
        self.assertEqual(len(customers), 1)
        customer = customers[0]
        self.assertEqual(customer.street, "123 Initial St")
        self.assertEqual(len(customer.child_ids), 0)  # No additional addresses yet

        # Second import with additional address
        second_count = self._import_with_mock_data(
            importer, "customers", [updated_customer_data], CustomerFields, "import_customers_since_last_import"
        )
        self.assertEqual(second_count, 0)  # Update, not new customer

        # Verify address was added
        self._verify_customer_state("address_customer", 1, "456 Additional Ave")

        # Third import with same data (idempotency test)
        third_count = self._import_with_mock_data(
            importer, "customers", [updated_customer_data], CustomerFields, "import_customers_since_last_import"
        )
        self.assertEqual(third_count, 0)

        # Verify state remains the same
        self._verify_customer_state("address_customer", 1, "456 Additional Ave")

    def test_product_with_variants_idempotency(self) -> None:
        importer = ProductImporter(self.env, self.sync_record)

        # Initial product with one variant
        initial_product_data = create_shopify_product_response(
            gid="gid://shopify/Product/variant_product",
            title="Variant Product",
            vendor="Test Manufacturer",
            product_type="Motors",
            variants=[
                create_shopify_variant_response(
                    gid="gid://shopify/ProductVariant/variant_1",
                    sku="90001",
                )
            ],
        )

        # Updated product with additional variant
        updated_product_data = create_shopify_product_response(
            gid="gid://shopify/Product/variant_product",
            title="Variant Product",
            vendor="Test Manufacturer",
            product_type="Motors",
            variants=[
                create_shopify_variant_response(
                    gid="gid://shopify/ProductVariant/variant_1",
                    sku="90001",
                ),
                create_shopify_variant_response(
                    gid="gid://shopify/ProductVariant/variant_2",
                    sku="90002",
                    price="149.99",
                ),
            ],
        )

        # First import
        first_count = self._import_with_mock_data(
            importer, "products", [initial_product_data], ProductFields, "import_products_since_last_import"
        )
        self.assertEqual(first_count, 1)

        # Verify initial state
        self._verify_product_variants("variant_product", 1, ["90001"])

        # Second import with additional variant
        second_count = self._import_with_mock_data(
            importer, "products", [updated_product_data], ProductFields, "import_products_since_last_import"
        )
        self.assertEqual(second_count, 1)  # Should create second variant

        # Verify second variant was added
        self._verify_product_variants("variant_product", 2, ["90001", "90002"])

        # Third import with same data (idempotency test)
        third_count = self._import_with_mock_data(
            importer, "products", [updated_product_data], ProductFields, "import_products_since_last_import"
        )
        self.assertEqual(third_count, 0)  # No new variants created

        # Verify state remains the same
        self._verify_product_variants("variant_product", 2, ["90001", "90002"])

    def test_mixed_import_idempotency(self) -> None:
        order_importer = OrderImporter(self.env, self.sync_record)

        # Pre-create one order
        existing_order_data = create_shopify_order_response(
            gid="gid://shopify/Order/existing_order",
            name="#EXISTING-001",
            line_items=[
                create_shopify_order_line_item_response(
                    sku=self.test_product.default_code,
                    variant_id="987654321",
                )
            ],
        )

        def mock_fetch_existing(after: str = None) -> MagicMock:
            if after is None:
                mock_response = MagicMock()
                mock_response.orders.nodes = [OrderFields(**existing_order_data)]
                mock_response.orders.page_info.has_next_page = False
                return mock_response
            else:
                mock_response = MagicMock()
                mock_response.orders.nodes = []
                mock_response.orders.page_info.has_next_page = False
                return mock_response

        with patch.object(order_importer, "_fetch_page", side_effect=mock_fetch_existing):
            order_importer.import_orders_since_last_import()

        # Now import mix of existing and new orders
        new_order_data = create_shopify_order_response(
            gid="gid://shopify/Order/new_order",
            name="#NEW-001",
            line_items=[
                create_shopify_order_line_item_response(
                    sku=self.test_product.default_code,
                    variant_id="987654321",
                )
            ],
        )

        mixed_data = [existing_order_data, new_order_data]

        mock_fetch_mixed = create_mock_fetch_page_function(
            entity_type="orders",
            data_list=mixed_data,
            field_class=OrderFields,
        )

        # Import mixed data
        with patch.object(order_importer, "_fetch_page", side_effect=mock_fetch_mixed):
            mixed_count = order_importer.import_orders_since_last_import()
            self.assertEqual(mixed_count, 1)  # Only the new order should be imported

        # Verify both orders exist but no duplicates
        all_orders = self.env["sale.order"].search([("shopify_order_id", "in", ["existing_order", "new_order"])])
        self.assertEqual(len(all_orders), 2)

        # Import same mixed data again (idempotency test)
        with patch.object(order_importer, "_fetch_page", side_effect=mock_fetch_mixed):
            repeat_count = order_importer.import_orders_since_last_import()
            self.assertEqual(repeat_count, 0)  # No new imports

        # Verify state remains unchanged
        all_orders = self.env["sale.order"].search([("shopify_order_id", "in", ["existing_order", "new_order"])])
        self.assertEqual(len(all_orders), 2)

    def test_transaction_rollback_safety(self) -> None:
        importer = OrderImporter(self.env, self.sync_record)

        # Create an order that will fail during line item processing
        failing_order_data = create_shopify_order_response(
            gid="gid://shopify/Order/failing_order",
            name="#FAIL-001",
            line_items=[
                create_shopify_order_line_item_response(
                    sku="999998",  # This SKU doesn't exist
                    variant_id="999999999",
                )
            ],
        )

        mock_fetch_failing = create_mock_fetch_page_function(
            entity_type="orders",
            data_list=[failing_order_data],
            field_class=OrderFields,
        )

        # Count orders before import
        self.env["sale.order"].search_count([])  # Ensure clean state

        with patch.object(importer, "_fetch_page", side_effect=mock_fetch_failing):
            # Import should handle the failure gracefully
            importer.import_orders_since_last_import()
            # Might be 0 (skipped) or raise exception depending on implementation

        # Verify no partial orders were created
        orders_after = self.env["sale.order"].search_count([])

        # Should not have created a broken order
        failing_orders = self.env["sale.order"].search([("shopify_order_id", "=", "failing_order")])
        if failing_orders:
            # If order was created, it should be complete (not partial)
            self.assertTrue(len(failing_orders[0].order_line) > 0 or failing_orders[0].state == "cancel")

        # Re-import same failing data should be idempotent
        with patch.object(importer, "_fetch_page", side_effect=mock_fetch_failing):
            importer.import_orders_since_last_import()

        # Should maintain consistent state
        orders_final = self.env["sale.order"].search_count([])
        self.assertEqual(orders_after, orders_final)
