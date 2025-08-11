from odoo.tests import tagged
from datetime import datetime, timedelta
from ..fixtures.base import IntegrationTestCase


@tagged("post_install", "-at_install", "integration_test")
class TestShippingAnalytics(IntegrationTestCase):
    """Comprehensive test suite for shipping analytics functionality

    This test class covers:
    - Shipping analytics data calculations
    - Platform-specific analytics
    - Margin analysis and reporting
    - Integration with existing orders
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # Create comprehensive test data
        cls._create_test_data()

    @classmethod
    def _create_test_data(cls) -> None:
        """Create test data for analytics testing"""
        # Partners
        cls.partner_shopify = cls.env["res.partner"].create(
            {
                "name": "Shopify Analytics Customer",
                "email": "shopify.analytics@test.com",
            }
        )

        cls.partner_ebay = cls.env["res.partner"].create(
            {
                "name": "eBay Analytics Customer",
                "email": "ebay.analytics@test.com",
            }
        )

        cls.partner_manual = cls.env["res.partner"].create(
            {
                "name": "Manual Analytics Customer",
                "email": "manual.analytics@test.com",
            }
        )

        # Use the base class test product
        cls.product = cls.test_product
        cls.product.list_price = 200.0  # Update price for this test

        # Delivery products for different carriers
        delivery_products = {}
        for carrier_name in ["UPS", "USPS", "FedEx"]:
            delivery_products[carrier_name] = cls.env["product.product"].create(
                {
                    "name": f"Test {carrier_name} Delivery",
                    "type": "service",
                    "list_price": 0.0,
                }
            )

        # Create carriers
        cls.carrier_ups = cls.env["delivery.carrier"].create(
            {
                "name": "Test UPS",
                "delivery_type": "fixed",
                "fixed_price": 15.0,
                "product_id": delivery_products["UPS"].id,
            }
        )

        cls.carrier_usps = cls.env["delivery.carrier"].create(
            {
                "name": "Test USPS",
                "delivery_type": "fixed",
                "fixed_price": 10.0,
                "product_id": delivery_products["USPS"].id,
            }
        )

        cls.carrier_fedex = cls.env["delivery.carrier"].create(
            {
                "name": "Test FedEx",
                "delivery_type": "fixed",
                "fixed_price": 20.0,
                "product_id": delivery_products["FedEx"].id,
            }
        )

        # Create orders with various shipping scenarios
        cls._create_test_orders()

    @classmethod
    def _create_test_orders(cls) -> None:
        """Create test orders with different shipping scenarios"""
        # Get default order values from base class
        default_order_vals = cls._get_default_order_vals()

        # Shopify orders with positive margins
        for i in range(3):
            order = cls.env["sale.order"].create(
                {
                    **default_order_vals,
                    "partner_id": cls.partner_shopify.id,
                    "source_platform": "shopify",
                    "shopify_order_id": f"SHOP-ANALYTICS-{i}",
                    "carrier_id": cls.carrier_ups.id,
                    "shipping_charge": 25.0,
                    "shipping_paid": 20.0 - i,  # Varying margins
                    "date_order": datetime.now() - timedelta(days=i),
                }
            )
            cls._add_order_line(order)
            order.action_confirm()

        # eBay orders with mixed margins
        for i in range(3):
            order = cls.env["sale.order"].create(
                {
                    **default_order_vals,
                    "partner_id": cls.partner_ebay.id,
                    "source_platform": "ebay",
                    "ebay_order_id": f"EBAY-ANALYTICS-{i}",
                    "carrier_id": cls.carrier_usps.id,
                    "shipping_charge": 15.0,
                    "shipping_paid": 20.0 - (i * 10),  # Some negative margins
                    "date_order": datetime.now() - timedelta(days=i + 3),
                }
            )
            cls._add_order_line(order)
            order.action_confirm()

        # Manual orders
        order = cls.env["sale.order"].create(
            {
                **default_order_vals,
                "partner_id": cls.partner_manual.id,
                "source_platform": "manual",
                "carrier_id": cls.carrier_fedex.id,
                "shipping_charge": 30.0,
                "shipping_paid": 25.0,
                "date_order": datetime.now() - timedelta(days=7),
            }
        )
        cls._add_order_line(order)

    @classmethod
    def _add_order_line(cls, order: "odoo.model.sale_order") -> None:
        """Add a product line to an order"""
        cls.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": cls.product.id,
                "product_uom_qty": 2,
                "price_unit": 200.0,
            }
        )

    # ========== Analytics Calculation Tests ==========

    def test_shipping_margin_analytics(self) -> None:
        """Test shipping margin calculations across orders"""
        # Get all test orders using tag
        orders = self.env["sale.order"].search([("tag_ids", "in", [self.test_order_tag.id])])

        # Verify margins are calculated correctly
        for order in orders:
            expected_margin = order.shipping_charge - order.shipping_paid
            self.assertEqual(order.shipping_margin, expected_margin, f"Order {order.name} margin calculation incorrect")

    def test_platform_analytics_grouping(self) -> None:
        """Test analytics grouped by platform"""
        # Group by platform
        platform_data = {}

        for platform in ["shopify", "ebay", "manual"]:
            orders = self.env["sale.order"].search(
                [
                    ("source_platform", "=", platform),
                    ("tag_ids", "in", [self.test_order_tag.id]),
                ]
            )

            platform_data[platform] = {
                "count": len(orders),
                "total_charge": sum(orders.mapped("shipping_charge")),
                "total_paid": sum(orders.mapped("shipping_paid")),
                "total_margin": sum(orders.mapped("shipping_margin")),
            }

        # Verify Shopify data (3 orders)
        self.assertEqual(platform_data["shopify"]["count"], 3)
        self.assertEqual(platform_data["shopify"]["total_charge"], 75.0)  # 25 * 3
        self.assertEqual(platform_data["shopify"]["total_paid"], 57.0)  # 20 + 19 + 18
        self.assertEqual(platform_data["shopify"]["total_margin"], 18.0)  # 5 + 6 + 7

        # Verify eBay data (3 orders)
        self.assertEqual(platform_data["ebay"]["count"], 3)
        self.assertEqual(platform_data["ebay"]["total_charge"], 45.0)  # 15 * 3
        self.assertEqual(platform_data["ebay"]["total_paid"], 30.0)  # 20 + 10 + 0
        self.assertEqual(platform_data["ebay"]["total_margin"], 15.0)  # -5 + 5 + 15

        # Verify manual data (1 order)
        self.assertEqual(platform_data["manual"]["count"], 1)
        self.assertEqual(platform_data["manual"]["total_charge"], 30.0)
        self.assertEqual(platform_data["manual"]["total_paid"], 25.0)
        self.assertEqual(platform_data["manual"]["total_margin"], 5.0)

    def test_carrier_analytics(self) -> None:
        """Test analytics grouped by carrier"""
        # Get orders by carrier
        ups_orders = self.env["sale.order"].search(
            [("carrier_id", "=", self.carrier_ups.id), ("tag_ids", "in", [self.test_order_tag.id])]
        )

        usps_orders = self.env["sale.order"].search(
            [("carrier_id", "=", self.carrier_usps.id), ("tag_ids", "in", [self.test_order_tag.id])]
        )

        fedex_orders = self.env["sale.order"].search(
            [("carrier_id", "=", self.carrier_fedex.id), ("tag_ids", "in", [self.test_order_tag.id])]
        )

        # Verify carrier distribution
        self.assertEqual(len(ups_orders), 3)
        self.assertEqual(len(usps_orders), 3)
        self.assertEqual(len(fedex_orders), 1)

        # Verify average margins by carrier
        ups_avg_margin = sum(ups_orders.mapped("shipping_margin")) / len(ups_orders)
        self.assertEqual(ups_avg_margin, 6.0)  # (5 + 6 + 7) / 3

        usps_avg_margin = sum(usps_orders.mapped("shipping_margin")) / len(usps_orders)
        self.assertEqual(usps_avg_margin, 5.0)  # (-5 + 5 + 15) / 3

    def test_negative_margin_detection(self) -> None:
        """Test detection of orders with negative shipping margins"""
        # Find orders with negative margins
        negative_margin_orders = self.env["sale.order"].search(
            [
                ("shipping_margin", "<", 0),
                ("tag_ids", "in", [self.test_order_tag.id]),
            ]
        )

        # Should have 1 eBay order with negative margin
        self.assertEqual(len(negative_margin_orders), 1)
        self.assertEqual(negative_margin_orders.source_platform, "ebay")
        self.assertEqual(negative_margin_orders.shipping_margin, -5.0)

    def test_date_range_analytics(self) -> None:
        """Test analytics filtered by date ranges"""
        # Get only the orders created in setUpClass
        all_test_orders = self.env["sale.order"].search(
            [
                ("tag_ids", "in", [self.test_order_tag.id]),
                ("carrier_id", "!=", False),
            ]
        )

        # Group orders by platform to verify we have test data
        by_platform = {}
        for order in all_test_orders:
            platform = order.source_platform or "none"
            if platform not in by_platform:
                by_platform[platform] = []
            by_platform[platform].append(order)

        # Basic verification that we have orders from multiple platforms
        self.assertIn("shopify", by_platform, "Should have Shopify orders")
        self.assertIn("ebay", by_platform, "Should have eBay orders")
        self.assertGreaterEqual(len(all_test_orders), 6, "Should have at least 6 test orders")

        # Test that we can filter by date ranges
        now = datetime.now()
        three_days_ago = now - timedelta(days=3)

        recent_orders = all_test_orders.filtered(lambda o: o.date_order and o.date_order >= three_days_ago)
        older_orders = all_test_orders.filtered(lambda o: o.date_order and o.date_order < three_days_ago)

        # Basic sanity checks
        self.assertGreater(len(recent_orders), 0, "Should have some recent orders")
        self.assertGreater(len(older_orders), 0, "Should have some older orders")

        # Verify date filtering works correctly
        for order in recent_orders:
            self.assertGreaterEqual(order.date_order, three_days_ago, "Recent orders should be within last 3 days")

        for order in older_orders:
            self.assertLess(order.date_order, three_days_ago, "Older orders should be more than 3 days old")

    def test_shipping_efficiency_metrics(self) -> None:
        """Test shipping efficiency calculations"""
        all_orders = self.env["sale.order"].search([("tag_ids", "in", [self.test_order_tag.id])])

        # Calculate efficiency metrics
        total_charge = sum(all_orders.mapped("shipping_charge"))
        total_paid = sum(all_orders.mapped("shipping_paid"))
        total_margin = sum(all_orders.mapped("shipping_margin"))

        # Overall efficiency (margin as % of charge)
        efficiency = (total_margin / total_charge) * 100 if total_charge else 0

        self.assertEqual(total_charge, 150.0)  # 75 + 45 + 30
        self.assertEqual(total_paid, 112.0)  # 57 + 30 + 25
        self.assertEqual(total_margin, 38.0)  # 18 + 15 + 5
        self.assertAlmostEqual(efficiency, 25.33, places=2)

    def test_analytics_with_no_shipping_data(self) -> None:
        """Test analytics behavior with orders lacking shipping data"""
        # Create order without shipping data
        no_shipping_order = self.env["sale.order"].create(
            {
                **self._get_default_order_vals(),
                "partner_id": self.partner_manual.id,
                "source_platform": "manual",
            }
        )

        self._add_order_line(no_shipping_order)

        # Verify default values
        self.assertEqual(no_shipping_order.shipping_charge, 0.0)
        self.assertEqual(no_shipping_order.shipping_paid, 0.0)
        self.assertEqual(no_shipping_order.shipping_margin, 0.0)

        # Verify it doesn't break analytics calculations
        all_margins = (
            self.env["sale.order"]
            .search([("tag_ids", "in", [self.test_order_tag.id]), ("partner_id", "=", self.partner_manual.id)])
            .mapped("shipping_margin")
        )

        self.assertIn(0.0, all_margins)
        self.assertEqual(len(all_margins), 2)  # Original + new order
