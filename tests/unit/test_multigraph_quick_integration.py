"""Quick integration tests for multigraph that don't require browser automation."""

from odoo.tests import tagged
from ..fixtures.base import UnitTestCase


@tagged("post_install", "-at_install", "unit_test")
class TestMultigraphQuickIntegration(UnitTestCase):
    """Test multigraph integration without slow browser automation"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # Create test data with all required fields for multigraph view
        # noinspection PyUnresolvedReferences - Method exists in ProductConnectHttpCase base class
        cls._create_multigraph_test_products()

    def test_multigraph_action_loads_without_error(self) -> None:
        """Test that the multigraph action loads without server errors"""
        action = self.env.ref("product_connect.action_product_processing_analytics")

        # The action should exist and have proper configuration
        self.assertTrue(action)
        self.assertEqual(action.res_model, "product.template")
        self.assertIn("multigraph", action.view_mode)

        # Test that we can get the view without errors
        view = self.env.ref("product_connect.view_product_processing_multigraph")
        self.assertEqual(view.type, "graph")
        self.assertIn('js_class="multigraph"', view.arch)

    def test_multigraph_data_query_works(self) -> None:
        """Test that the multigraph can query data without errors"""
        # Simulate what the frontend would do - query for graph data
        domain = [("is_ready_for_sale", "=", True)]

        # Test basic read_group functionality that multigraph uses
        data = self.env["product.template"].read_group(
            domain=domain,
            fields=["initial_price_total", "initial_cost_total", "initial_quantity"],
            groupby=["is_ready_for_sale_last_enabled_date:day"],
        )

        # Should get data without errors
        self.assertGreater(len(data), 0)

        # Verify the data has the expected fields
        first_group = data[0]
        self.assertIn("initial_price_total", first_group)
        self.assertIn("initial_cost_total", first_group)
        self.assertIn("initial_quantity", first_group)

    def test_multigraph_view_renders_without_server_error(self) -> None:
        """Test that the multigraph view renders without server-side errors"""
        view = self.env.ref("product_connect.view_product_processing_multigraph")

        # Get the view definition like the web client would
        view_info = self.env["product.template"].get_views([(view.id, "graph")], options={"load_filters": True})

        # Should get view info without errors
        self.assertIn("views", view_info)
        self.assertIn("graph", view_info["views"])

        graph_view = view_info["views"]["graph"]
        self.assertIn("arch", graph_view)
        self.assertIn("multigraph", graph_view["arch"])

    def test_multigraph_search_filters_work(self) -> None:
        """Test that search filters work properly with multigraph data"""
        # Test the various search filters that the action uses
        # Note: search_view reference validates it exists
        self.env.ref("product_connect.view_product_processing_search")

        # Test domain with ready for sale filter
        domain = [("is_ready_for_sale", "=", True)]
        products = self.env["product.template"].search(domain)

        # Should find our test products
        self.assertGreater(len(products), 0)
        self.assertTrue(all(p.is_ready_for_sale for p in products))

        # Test date range filter
        from datetime import date

        date_domain = [
            ("is_ready_for_sale_last_enabled_date", ">=", date(2025, 1, 1)),
            ("is_ready_for_sale_last_enabled_date", "<=", date(2025, 1, 31)),
        ]
        date_products = self.env["product.template"].search(date_domain)
        self.assertGreater(len(date_products), 0)
