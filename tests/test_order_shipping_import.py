import logging
from unittest.mock import MagicMock, patch
from odoo.tests import tagged

from ..services.shopify.gql import OrderFields
from ..services.shopify.sync.importers.order_importer import OrderImporter
from ..services.shopify.helpers import ShopifyDataError
from ..services.tests.test_base import ShopifyTestBase
from ..services.tests.fixtures.shopify_responses import (
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

        self.sync_record = self.env["shopify.sync"].create(
            {
                "mode": "import_changed_orders",
            }
        )
        self.importer = OrderImporter(self.env, self.sync_record)

        self.customer_partner = self.env["res.partner"].create(
            {
                "name": "Test Customer",
                "email": "test@example.com",
                "shopify_customer_id": "123456789",
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

    @patch("odoo.addons.product_connect.services.shopify.sync.importers.customer_importer.CustomerImporter.import_customer")
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

    @patch("odoo.addons.product_connect.services.shopify.sync.importers.customer_importer.CustomerImporter.import_customer")
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

    @patch("odoo.addons.product_connect.services.shopify.sync.importers.customer_importer.CustomerImporter.import_customer")
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

    @patch("odoo.addons.product_connect.services.shopify.sync.importers.customer_importer.CustomerImporter.import_customer")
    def test_import_order_with_unknown_shipping_method(self, mock_import_customer: MagicMock) -> None:
        mock_import_customer.return_value = True

        order_data = create_shopify_order_response(
            customer=create_shopify_customer_response(),
            line_items=[create_shopify_order_line_item_response(sku=self.product.default_code)],
            shipping_lines=[create_shopify_shipping_line_response(title="Super Express Overnight Delivery", price="50.00")],
        )

        shopify_order = OrderFields(**order_data)

        with self.assertRaises(ShopifyDataError) as cm:
            self.importer._import_one(shopify_order)

        self.assertIn("Unknown delivery service", str(cm.exception))
        self.assertIn("Super Express Overnight Delivery", str(cm.exception))

    @patch("odoo.addons.product_connect.services.shopify.sync.importers.customer_importer.CustomerImporter.import_customer")
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
        self.assertEqual(order.carrier_id.id, free_carrier.id)

    @patch("odoo.addons.product_connect.services.shopify.sync.importers.customer_importer.CustomerImporter.import_customer")
    def test_shipping_charge_updates_on_reimport(self, mock_import_customer: MagicMock) -> None:
        mock_import_customer.return_value = True

        order_data = create_shopify_order_response(
            customer=create_shopify_customer_response(),
            line_items=[create_shopify_order_line_item_response(sku=self.product.default_code)],
            shipping_lines=[create_shopify_shipping_line_response(title="UPS Ground", price="15.00")],
        )

        shopify_order = OrderFields(**order_data)
        self.importer._import_one(shopify_order)

        order = self.env["sale.order"].search([("shopify_order_id", "=", "123456789")])
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

    @patch("odoo.addons.product_connect.services.shopify.sync.importers.customer_importer.CustomerImporter.import_customer")
    def test_imported_orders_are_completed_without_stock_moves(self, mock_import_customer: MagicMock) -> None:
        mock_import_customer.return_value = True

        order_data = create_shopify_order_response(
            customer=create_shopify_customer_response(),
            line_items=[create_shopify_order_line_item_response(sku=self.product.default_code)],
            shipping_lines=[create_shopify_shipping_line_response(title="UPS Ground", price="15.00")],
        )

        shopify_order = OrderFields(**order_data)
        self.importer._import_one(shopify_order)

        order = self.env["sale.order"].search([("shopify_order_id", "=", "123456789")])
        self.assertEqual(order.state, "sale", "Imported orders should be in sale state")
        self.assertTrue(order.locked, "Imported orders should be locked")
        self.assertEqual(order.invoice_status, "invoiced", "Imported orders should be marked as invoiced")

        pickings = self.env["stock.picking"].search([("sale_id", "=", order.id)])
        self.assertEqual(len(pickings), 0, "No delivery orders should be created for imported orders")

    @patch("odoo.addons.product_connect.services.shopify.sync.importers.customer_importer.CustomerImporter.import_customer")
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
            customAttributes=custom_attributes,
            paymentGatewayNames=["ebay"],
        )

        shopify_order = OrderFields(**order_data)
        self.importer._import_one(shopify_order)

        order = self.env["sale.order"].search([("shopify_order_id", "=", "123456789")])
        self.assertEqual(order.source_platform, "ebay", "Order should be marked as eBay")
        self.assertTrue(order.commitment_date, "eBay order should have commitment date")
        self.assertIn("eBay Sales Record: 21478", order.note)
        self.assertIn("eBay Order ID: 14-13240-64196", order.note)
        self.assertIn("Payment: ebay", order.note)
