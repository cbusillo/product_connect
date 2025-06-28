import logging
from unittest.mock import MagicMock, patch
from odoo.tests import tagged

from ..shopify.gql import OrderFields
from ..shopify.sync.importers.order_importer import OrderImporter
from ..shopify.sync.importers.customer_importer import CustomerImporter
from ..shopify.helpers import ShopifyDataError
from .test_base import ShopifyTestBase
from .fixtures.shopify_responses import (
    create_shopify_order_response,
    create_shopify_customer_response,
    create_shopify_shipping_line_response,
    create_shopify_order_line_item_response,
)

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestOrderShippingImport(ShopifyTestBase):
    def setUp(self) -> None:
        super().setUp()
        self._setup_shopify_mocks()
        self._setup_delivery_carriers()

        # Ensure we have a company and proper context
        self.company = self.env.company
        self.env = self.env(context=dict(self.env.context, skip_shopify_sync=True))

        self.sync_record = self.env["shopify.sync"].create(
            {
                "mode": "import_changed_orders",
            }
        )
        self.importer = OrderImporter(self.env, self.sync_record)

        # Create customer with ID matching the fixture default
        self.customer_partner = self.env["res.partner"].create(
            {
                "name": "Test Customer",
                "email": "test@example.com",
                "shopify_customer_id": "123456789",  # This matches the default in create_shopify_customer_response
            }
        )

        self.product = self.env["product.product"].create(
            {
                "name": "Test Product",
                "default_code": "TEST001",
                "type": "consu",
                "list_price": 100.0,
            }
        )

    def _setup_delivery_carriers(self) -> None:
        """Create delivery carriers and service mappings for tests"""
        # First, clean up any existing test data to avoid conflicts
        self.env["delivery.carrier.service.map"].search([("platform", "=", "shopify")]).unlink()

        # Find or create delivery carriers
        def get_or_create_carrier(name: str, product_vals: dict) -> tuple:
            """Get existing carrier or create new one with product"""
            carrier = self.env["delivery.carrier"].search([("name", "=", name)], limit=1)
            if carrier:
                return carrier, carrier.product_id

            product = self.env["product.product"].create(product_vals)
            carrier = self.env["delivery.carrier"].create(
                {
                    "name": name,
                    "delivery_type": "fixed",
                    "product_id": product.id,
                    "fixed_price": 0.0,
                }
            )
            return carrier, product

        # Get or create delivery carriers
        carrier_standard, _ = get_or_create_carrier(
            "Standard Shipping",
            {
                "name": "Standard Shipping",
                "type": "service",
                "sale_ok": False,
                "purchase_ok": False,
                "list_price": 0.0,
            },
        )

        carrier_ups, _ = get_or_create_carrier(
            "UPS Ground",
            {
                "name": "UPS Ground",
                "type": "service",
                "sale_ok": False,
                "purchase_ok": False,
                "list_price": 0.0,
            },
        )

        carrier_usps, _ = get_or_create_carrier(
            "USPS Priority Mail",
            {
                "name": "USPS Priority Mail",
                "type": "service",
                "sale_ok": False,
                "purchase_ok": False,
                "list_price": 0.0,
            },
        )

        carrier_free, _ = get_or_create_carrier(
            "Free Shipping",
            {
                "name": "Free Shipping",
                "type": "service",
                "sale_ok": False,
                "purchase_ok": False,
                "list_price": 0.0,
            },
        )

        carrier_ebay_gsp, _ = get_or_create_carrier(
            "Standard Shipping (eBay GSP)",
            {
                "name": "Standard Shipping (eBay GSP)",
                "type": "service",
                "sale_ok": False,
                "purchase_ok": False,
                "list_price": 0.0,
            },
        )

        carrier_insurance, _ = get_or_create_carrier(
            "Shipping Insurance",
            {
                "name": "Shipping Insurance",
                "type": "service",
                "sale_ok": False,
                "purchase_ok": False,
                "list_price": 0.0,
            },
        )

        # Create service mappings - need to normalize the names
        service_map_model = self.env["delivery.carrier.service.map"]

        def create_service_map(carrier: "odoo.model.delivery_carrier", service_name: str) -> None:
            """Create service mapping if it doesn't exist"""
            normalized_name = service_map_model.normalize_service_name(service_name)
            existing = service_map_model.search(
                [("platform", "=", "shopify"), ("platform_service_normalized_name", "=", normalized_name)], limit=1
            )
            if not existing:
                service_map_model.create(
                    {
                        "carrier": carrier.id,
                        "platform": "shopify",
                        "platform_service_normalized_name": normalized_name,
                    }
                )

        # Standard shipping variations
        create_service_map(carrier_standard, "Standard Shipping")
        create_service_map(carrier_standard, "Via standard shipping")

        # UPS
        create_service_map(carrier_ups, "UPS Ground")
        create_service_map(carrier_ups, "UPs Ground")

        # USPS
        create_service_map(carrier_usps, "USPS Priority Mail®")

        # Free shipping
        create_service_map(carrier_free, "Free Shipping")
        create_service_map(carrier_free, "Free Shipping!")

        # eBay GSP
        create_service_map(carrier_ebay_gsp, "Standard Shipping (eBay GSP)")

        # Shipping Insurance
        create_service_map(carrier_insurance, "Shipping Insurance")

    @patch.object(CustomerImporter, "import_customer")
    def test_import_order_with_standard_shipping(self, mock_import_customer: MagicMock) -> None:
        mock_import_customer.return_value = True

        order_data = create_shopify_order_response(
            customer=create_shopify_customer_response(),
            line_items=[create_shopify_order_line_item_response(sku=self.product.default_code, unit_price="100.00")],
            shipping_lines=[create_shopify_shipping_line_response(price="9.99")],
        )

        shopify_order = OrderFields(**order_data)
        result = self.importer._import_one(shopify_order)

        self.assertTrue(result)

        order = self.env["sale.order"].search([("shopify_order_id", "=", "123456789")])
        self.assertTrue(order)

        self.assertEqual(order.source_platform, "shopify")
        self.assertEqual(order.shipping_charge, 9.99)

        delivery_lines = order.order_line.filtered("is_delivery")
        self.assertEqual(len(delivery_lines), 1)
        self.assertEqual(delivery_lines[0].price_unit, 9.99)

        carrier = self.env["delivery.carrier"].search([("name", "=", "Standard Shipping")])
        self.assertEqual(order.carrier_id.id, carrier.id)

    @patch.object(CustomerImporter, "import_customer")
    def test_import_order_with_multiple_shipping_lines(self, mock_import_customer: MagicMock) -> None:
        mock_import_customer.return_value = True

        order_data = create_shopify_order_response(
            customer=create_shopify_customer_response(),
            line_items=[create_shopify_order_line_item_response(sku=self.product.default_code)],
            shipping_lines=[
                create_shopify_shipping_line_response(title="UPS Ground", price="15.00"),
                create_shopify_shipping_line_response(title="Shipping Insurance", price="5.00"),
            ],
        )

        shopify_order = OrderFields(**order_data)
        result = self.importer._import_one(shopify_order)

        self.assertTrue(result)

        order = self.env["sale.order"].search([("shopify_order_id", "=", "123456789")])
        self.assertEqual(order.shipping_charge, 20.00)

        delivery_lines = order.order_line.filtered("is_delivery")
        self.assertGreaterEqual(len(delivery_lines), 1)

        total_delivery = sum(line.price_unit for line in delivery_lines)
        self.assertEqual(total_delivery, 20.00)

    @patch.object(CustomerImporter, "import_customer")
    def test_import_order_with_shipping_variation(self, mock_import_customer: MagicMock) -> None:
        mock_import_customer.return_value = True

        variations_to_test = [
            ("Via standard shipping", "Standard Shipping"),
            ("USPS Priority Mail®", "USPS Priority Mail"),
            ("UPs Ground", "UPS Ground"),
            ("Free Shipping!", "Free Shipping"),
            ("Standard Shipping (eBay GSP)", "Standard Shipping (eBay GSP)"),
        ]

        for shipping_title, expected_carrier_name in variations_to_test:
            order_data = create_shopify_order_response(
                gid=f"gid://shopify/Order/{shipping_title.replace(' ', '')}",
                name=f"#TEST-{shipping_title[:5]}",
                customer=create_shopify_customer_response(),
                line_items=[create_shopify_order_line_item_response(sku=self.product.default_code)],
                shipping_lines=[
                    create_shopify_shipping_line_response(
                        title=shipping_title,
                    )
                ],
            )

            shopify_order = OrderFields(**order_data)
            result = self.importer._import_one(shopify_order)

            self.assertTrue(result, f"Failed to import order with shipping: {shipping_title}")

            order = self.env["sale.order"].search([("shopify_order_id", "=", shipping_title.replace(" ", ""))])
            self.assertTrue(order, f"Order not found for shipping: {shipping_title}")

            carrier = order.carrier_id
            self.assertTrue(carrier, f"No carrier set for shipping: {shipping_title}")
            self.assertEqual(carrier.name, expected_carrier_name, f"Wrong carrier for {shipping_title}: got {carrier.name}")

    @patch.object(CustomerImporter, "import_customer")
    def test_import_order_with_unknown_shipping_method(self, mock_import_customer: MagicMock) -> None:
        mock_import_customer.return_value = True

        order_data = create_shopify_order_response(
            customer=create_shopify_customer_response(),
            line_items=[create_shopify_order_line_item_response(sku=self.product.default_code)],
            shipping_lines=[create_shopify_shipping_line_response(title="Super Express Overnight Delivery", price="50.00")],
        )

        shopify_order = OrderFields(**order_data)

        # Manually catch the exception to avoid savepoint issues
        try:
            self.importer._import_one(shopify_order)
            self.fail("Expected ShopifyDataError to be raised")
        except ShopifyDataError as e:
            self.assertIn("Unknown delivery service", str(e))
            self.assertIn("Super Express Overnight Delivery", str(e))

    @patch.object(CustomerImporter, "import_customer")
    def test_import_order_with_free_shipping(self, mock_import_customer: MagicMock) -> None:
        mock_import_customer.return_value = True

        order_data = create_shopify_order_response(
            customer=create_shopify_customer_response(),
            line_items=[create_shopify_order_line_item_response(sku=self.product.default_code)],
            shipping_lines=[create_shopify_shipping_line_response(title="Free Shipping", price="0.00")],
        )

        shopify_order = OrderFields(**order_data)
        result = self.importer._import_one(shopify_order)

        self.assertTrue(result)

        order = self.env["sale.order"].search([("shopify_order_id", "=", "123456789")])
        self.assertEqual(order.shipping_charge, 0.00)

        free_carrier = self.env["delivery.carrier"].search([("name", "=", "Free Shipping")])
        self.assertTrue(order.carrier_id, "Order should have a carrier set")
        self.assertEqual(order.carrier_id.id, free_carrier.id)

    def _create_and_import_order(self, shipping_price: str = "15.00") -> "odoo.model.sale_order":
        """Helper method to create and import an order with shipping."""
        order_data = create_shopify_order_response(
            customer=create_shopify_customer_response(),
            line_items=[create_shopify_order_line_item_response(sku=self.product.default_code)],
            shipping_lines=[create_shopify_shipping_line_response(title="UPS Ground", price=shipping_price)],
        )

        shopify_order = OrderFields(**order_data)
        self.importer._import_one(shopify_order)

        order = self.env["sale.order"].search([("shopify_order_id", "=", "123456789")])
        return order

    @patch.object(CustomerImporter, "import_customer")
    def test_shipping_charge_updates_on_reimport(self, mock_import_customer: MagicMock) -> None:
        mock_import_customer.return_value = True

        order = self._create_and_import_order()
        self.assertEqual(order.shipping_charge, 15.00)

        updated_data = create_shopify_order_response(
            customer=create_shopify_customer_response(),
            line_items=[create_shopify_order_line_item_response(sku=self.product.default_code)],
            shipping_lines=[create_shopify_shipping_line_response(title="UPS Ground", price="20.00")],
        )

        updated_order = OrderFields(**updated_data)
        result = self.importer._import_one(updated_order)

        self.assertTrue(result)

        order.invalidate_recordset()
        self.assertEqual(order.shipping_charge, 20.00)

        delivery_lines = order.order_line.filtered("is_delivery")
        self.assertEqual(len(delivery_lines), 1)
        self.assertEqual(delivery_lines[0].price_unit, 20.00)

    @patch.object(CustomerImporter, "import_customer")
    def test_imported_orders_are_completed_without_stock_moves(self, mock_import_customer: MagicMock) -> None:
        mock_import_customer.return_value = True

        order = self._create_and_import_order()
        self.assertEqual(order.state, "sale", "Imported orders should be in sale state")
        self.assertTrue(order.locked, "Imported orders should be locked")
        self.assertEqual(order.invoice_status, "invoiced", "Imported orders should be marked as invoiced")

        pickings = self.env["stock.picking"].search([("sale_id", "=", order.id)])
        self.assertEqual(len(pickings), 0, "No delivery orders should be created for imported orders")

    @patch.object(CustomerImporter, "import_customer")
    def test_import_ebay_order_from_shopify(self, mock_import_customer: MagicMock) -> None:
        mock_import_customer.return_value = True

        ebay_note_attributes = """eBay Sales Record Number: 21478
eBay Order Id: 14-13240-64196
eBay Earliest Delivery Date: 2025-06-27T07:00:00.000Z
eBay Latest Delivery Date: 2025-06-30T07:00:00.000Z
eBay Handle By Date: 2025-06-27T03:59:59.000Z
eBay Account: outboardpartswarehouseva"""

        custom_attributes = [{"key": "Note Attributes", "value": ebay_note_attributes}]

        order_data = create_shopify_order_response(
            customer=create_shopify_customer_response(),
            line_items=[create_shopify_order_line_item_response(sku=self.product.default_code)],
            shipping_lines=[create_shopify_shipping_line_response(title="UPS Ground", price="15.00")],
            custom_attributes=custom_attributes,
            payment_gateway_names=["ebay"],
        )

        shopify_order = OrderFields(**order_data)
        self.importer._import_one(shopify_order)

        order = self.env["sale.order"].search([("shopify_order_id", "=", "123456789")])
        self.assertEqual(order.source_platform, "ebay", "Order should be marked as eBay")
        self.assertTrue(order.commitment_date, "eBay order should have commitment date")
        self.assertIn("eBay Sales Record: 21478", order.shopify_note)
        self.assertIn("eBay Order ID: 14-13240-64196", order.shopify_note)
        self.assertIn("Payment: ebay", order.shopify_note)
