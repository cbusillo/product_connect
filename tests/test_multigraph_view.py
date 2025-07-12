from lxml import etree
from .fixtures.test_base import ProductConnectTransactionCase


class TestMultigraphView(ProductConnectTransactionCase):
    def setUp(self) -> None:
        super().setUp()
        self.View = self.env["ir.ui.view"]

    def test_multigraph_view_type_registered(self) -> None:
        """Test that multigraph view type is properly registered"""
        view_info = self.View._get_view_info()
        self.assertIn("multigraph", view_info)
        self.assertEqual(view_info["multigraph"]["icon"], "fa fa-line-chart")
        self.assertTrue(view_info["multigraph"]["multi_record"])

    def test_postprocess_multigraph_view(self) -> None:
        """Test multigraph view postprocessing"""
        arch_string = """
            <multigraph>
                <field name="list_price" type="measure"/>
                <field name="standard_price" type="measure" widget="monetary"/>
                <field name="qty_available" type="measure" axis="y1"/>
            </multigraph>
        """
        arch = etree.fromstring(arch_string)

        processed = self.View._postprocess_multigraph_view(arch, "product.template")

        list_price_field = processed.xpath('.//field[@name="list_price"]')[0]
        self.assertEqual(list_price_field.get("axis"), "y")
        self.assertIn(list_price_field.get("string"), ["Price", "Sales Price", "Sale Price"])

        standard_price_field = processed.xpath('.//field[@name="standard_price"]')[0]
        self.assertEqual(standard_price_field.get("widget"), "monetary")
        self.assertIn("currency_field", standard_price_field.get("options", ""))

        qty_field = processed.xpath('.//field[@name="qty_available"]')[0]
        self.assertEqual(qty_field.get("axis"), "y1")

    def test_create_multigraph_view(self) -> None:
        """Test creating an actual multigraph view"""
        view = self.View.create(
            {
                "name": "test.multigraph.view",
                "model": "product.template",
                "arch": """
                <multigraph string="Test MultiGraph">
                    <field name="create_date" interval="month"/>
                    <field name="list_price" type="measure" axis="y" widget="monetary"/>
                    <field name="qty_available" type="measure" axis="y1"/>
                </multigraph>
            """,
            }
        )

        self.assertTrue(view)
        self.assertEqual(view.type, "multigraph")

        processed_arch = view.get_views([(view.id, "multigraph")])
        self.assertIn("views", processed_arch)
        self.assertIn("multigraph", processed_arch["views"])

    def test_multigraph_action_window(self) -> None:
        """Test action window with multigraph view mode"""
        action = self.env["ir.actions.act_window"].create(
            {
                "name": "Test MultiGraph Action",
                "res_model": "product.template",
                "view_mode": "multigraph,tree,form",
            }
        )

        self.assertIn("multigraph", action.view_mode)

        view = self.View.create(
            {
                "name": "test.action.multigraph",
                "model": "product.template",
                "arch": """
                <multigraph>
                    <field name="list_price" type="measure"/>
                </multigraph>
            """,
            }
        )

        action.view_id = view
        self.assertEqual(action.view_id.type, "multigraph")

    def test_product_processing_analytics_action(self) -> None:
        """Test the product processing analytics action with multigraph view"""
        action = self.env.ref("product_connect.action_product_processing_analytics")

        self.assertEqual(action.res_model, "product.template")
        self.assertIn("multigraph", action.view_mode)
        self.assertTrue(action.view_mode.startswith("multigraph"))

        # Check default context includes our new filters
        context = action.context
        if isinstance(context, str):
            # Context might be stored as string, evaluate it safely
            import ast

            context = ast.literal_eval(context)

        # Ensure context is a dictionary
        self.assertIsInstance(context, dict)
        self.assertIn("search_default_last_7_days", context)
        self.assertIn("graph_groupbys", context)
        self.assertEqual(context["graph_groupbys"], ["is_ready_for_sale_last_enabled_date:day"])

        # Ready for sale filter should not be in context since domain handles it
        self.assertNotIn("search_default_ready_for_sale", context)

    def test_enhanced_search_filters(self) -> None:
        """Test new date filters work correctly"""
        search_view = self.env.ref("product_connect.view_product_processing_search")

        # Test that the search view contains our new filters
        arch_string = search_view.arch
        self.assertIn("last_365_days", arch_string)
        self.assertIn("MTD (Month to Date)", arch_string)
        self.assertIn("YTD (Year to Date)", arch_string)
        # Group-by options are now in traditional group by section
        self.assertIn("groupby_processed_date", arch_string)
        self.assertIn("is_ready_for_sale_last_enabled_date:month", arch_string)

    def test_multigraph_view_definition(self) -> None:
        """Test the product processing multigraph view is properly defined"""
        view = self.env.ref("product_connect.view_product_processing_multigraph")

        self.assertEqual(view.model, "product.template")
        self.assertEqual(view.type, "multigraph")

        # Check that the view has the required fields
        arch_string = view.arch
        self.assertIn("initial_price_total", arch_string)
        self.assertIn("initial_cost_total", arch_string)
        self.assertIn("initial_quantity", arch_string)
        self.assertIn("is_ready_for_sale_last_enabled_date", arch_string)

        # Check multi-axis configuration
        self.assertIn('axis="y"', arch_string)  # Revenue/Cost on left axis
        self.assertIn('axis="y1"', arch_string)  # Units on right axis
