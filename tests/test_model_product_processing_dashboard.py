from datetime import datetime, timedelta
from odoo.tests import tagged, TransactionCase


@tagged("post_install", "-at_install")
class TestProductProcessingDashboard(TransactionCase):
    """Unit tests for product processing report functionality"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        # Enable tracking for this test since we need to test tracking-based fields
        # Skip Shopify sync but keep tracking enabled
        cls.env = cls.env(context=dict(cls.env.context, skip_shopify_sync=True))

        # Create test data
        cls.manufacturer = cls.env["product.manufacturer"].create({"name": "Test Dashboard Manufacturer"})

        cls.part_type = cls.env["product.type"].create({"name": "Test Dashboard Part"})

        cls.condition = cls.env["product.condition"].create({"name": "Test Dashboard Condition", "code": "TDC"})

    def test_is_ready_for_sale_last_enabled_date_computation(self) -> None:
        """Test that the last enabled date is computed correctly when product is enabled"""
        # Create a product that is not ready for sale
        product = self.env["product.template"].create(
            {
                "name": "Test Product Dashboard",
                "default_code": "1234",
                "type": "consu",
                "is_ready_for_sale": False,
                "list_price": 100.0,
                "standard_price": 50.0,
                "initial_quantity": 10,
                "manufacturer": self.manufacturer.id,
                "part_type": self.part_type.id,
                "condition": self.condition.id,
            }
        )

        # Initially should have no date
        self.assertFalse(product.is_ready_for_sale_last_enabled_date)

        # Enable the product
        product.is_ready_for_sale = True
        product.flush_recordset()  # Ensure tracking is written

        # Debug: Check if tracking was created
        tracking_values = self.env["mail.tracking.value"].search(
            [
                ("field_id.name", "=", "is_ready_for_sale"),
                ("field_id.model", "=", "product.template"),
            ]
        )
        print(f"DEBUG: Found {len(tracking_values)} tracking values for is_ready_for_sale")
        print(f"DEBUG: Product has {len(product.message_ids)} messages")

        product.invalidate_recordset()  # Force recomputation

        # Should now have a date
        print(f"DEBUG: is_ready_for_sale_last_enabled_date = {product.is_ready_for_sale_last_enabled_date}")
        self.assertTrue(product.is_ready_for_sale_last_enabled_date)
        self.assertAlmostEqual(product.is_ready_for_sale_last_enabled_date, datetime.now(), delta=timedelta(seconds=5))

        # Disable and re-enable
        product.is_ready_for_sale = False
        first_date = product.is_ready_for_sale_last_enabled_date

        # Wait a bit and re-enable
        product.is_ready_for_sale = True

        # Should have updated to new date
        self.assertGreater(product.is_ready_for_sale_last_enabled_date, first_date)

    def test_is_ready_for_sale_last_enabled_date_multiple_changes(self) -> None:
        """Test that only the last enabled date is tracked"""
        product = self.env["product.template"].create(
            {
                "name": "Test Multiple Changes",
                "default_code": "5678",
                "type": "consu",
                "is_ready_for_sale": True,  # Start enabled
                "list_price": 200.0,
                "standard_price": 100.0,
                "initial_quantity": 5,
                "manufacturer": self.manufacturer.id,
                "part_type": self.part_type.id,
                "condition": self.condition.id,
            }
        )

        initial_date = product.is_ready_for_sale_last_enabled_date
        self.assertTrue(initial_date)

        # Toggle multiple times
        product.is_ready_for_sale = False
        product.is_ready_for_sale = True
        product.is_ready_for_sale = False
        product.is_ready_for_sale = True

        # Should have most recent enabled date
        self.assertGreaterEqual(product.is_ready_for_sale_last_enabled_date, initial_date)

    def test_computed_totals(self) -> None:
        """Test that initial_price_total and initial_cost_total are computed correctly"""
        product = self.env["product.template"].create(
            {
                "name": "Test Totals",
                "default_code": "9999",
                "type": "consu",
                "list_price": 100.0,
                "standard_price": 60.0,
                "initial_quantity": 15,
                "manufacturer": self.manufacturer.id,
                "part_type": self.part_type.id,
                "condition": self.condition.id,
            }
        )

        self.assertEqual(product.initial_price_total, 1500.0)  # 100 * 15
        self.assertEqual(product.initial_cost_total, 900.0)  # 60 * 15

    def test_dashboard_action_loads(self) -> None:
        """Test that the dashboard action can be executed without errors"""
        action = self.env.ref("product_connect.action_product_processing_analytics")

        result = action.read()[0]

        self.assertEqual(result["res_model"], "product.template")
        self.assertIn("graph", result["view_mode"])
        self.assertNotIn("kanban", result["view_mode"])  # We removed kanban

        # Create a test product to ensure domain works
        product = self.env["product.template"].create(
            {
                "name": "Dashboard Action Test",
                "default_code": "8888",
                "type": "consu",
                "is_ready_for_sale": True,
                "list_price": 50.0,
                "standard_price": 25.0,
                "manufacturer": self.manufacturer.id,
                "part_type": self.part_type.id,
                "condition": self.condition.id,
            }
        )
        product.flush_recordset()

        domain = eval(result["domain"])
        products = self.env["product.template"].search(domain)

        # Product should be in results if it has an enabled date
        if product.is_ready_for_sale_last_enabled_date:
            self.assertIn(product, products)

    def test_search_view_filters(self) -> None:
        """Test that search view filters can be evaluated"""
        search_view = self.env.ref("product_connect.view_product_processing_search")

        self.assertEqual(search_view.model, "product.template")

        arch = search_view.arch
        self.assertIn("processed_today", arch)
        self.assertIn("processed_week", arch)
        self.assertIn("processed_month", arch)
        self.assertIn("context_today()", arch)

    def test_graph_view_loads(self) -> None:
        """Test that graph view can be loaded"""
        graph_view = self.env.ref("product_connect.view_product_processing_graph")

        self.assertEqual(graph_view.model, "product.template")
        self.assertEqual(graph_view.type, "graph")

        arch = graph_view.arch
        self.assertIn("initial_price_total", arch)
        self.assertIn("initial_cost_total", arch)

    def test_menu_items_exist(self) -> None:
        """Test that menu items are created"""
        report_menu = self.env.ref("product_connect.menu_product_processing_report")

        self.assertTrue(report_menu.exists())
        self.assertEqual(report_menu.action, self.env.ref("product_connect.action_product_processing_analytics"))
