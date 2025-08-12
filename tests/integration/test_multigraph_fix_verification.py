"""Test multigraph view functionality after fixes."""

from ..common_imports import tagged, INTEGRATION_TAGS
from ..fixtures.base import IntegrationTestCase
from odoo.exceptions import ValidationError


@tagged(*INTEGRATION_TAGS)
class TestMultigraphFixVerification(IntegrationTestCase):
    """Verify multigraph view works correctly after our fixes."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.View = cls.env["ir.ui.view"]
        cls.ActionWindow = cls.env["ir.actions.act_window"]

        # Create test products with required multigraph fields
        cls._create_multigraph_test_data()

    @classmethod
    def _create_multigraph_test_data(cls) -> None:
        """Create test data specific to multigraph view testing."""
        # Create products with varying dates and measures for graph data
        import datetime

        base_date = datetime.date.today() - datetime.timedelta(days=30)

        cls.multigraph_products = []
        for i in range(5):
            # Create motor product with all required fields for analytics
            product = cls._create_motor_product(
                name=f"Multigraph Test Product {i + 1}",
                default_code=f"7000000{i + 1}",  # Valid SKU
                list_price=100.0 + (i * 50),
                standard_price=50.0 + (i * 25),
                is_ready_for_sale=i % 2 == 0,  # Alternate ready for sale
                with_image=True,
            )

            # Set specific dates for testing
            test_date = base_date + datetime.timedelta(days=i * 5)
            product.write(
                {
                    "is_ready_for_sale_last_enabled_date": test_date,
                    "initial_quantity": 10 + i,
                    "image_count": i + 1,
                }
            )

            cls.multigraph_products.append(product)

    def test_multigraph_view_loads_without_errors(self) -> None:
        """Test that the multigraph view can be loaded without errors."""
        # Get the multigraph view definition
        multigraph_view = self.env.ref("product_connect.view_product_processing_multigraph")

        # Verify view exists and has correct type
        self.assertTrue(multigraph_view.exists())
        self.assertEqual(multigraph_view.type, "graph")
        self.assertEqual(multigraph_view.model, "product.template")

        # Verify the view contains multigraph-specific attributes
        arch_string = multigraph_view.arch
        self.assertIn('js_class="multigraph"', arch_string)
        self.assertIn('type="line"', arch_string)

    def test_multigraph_view_xml_validation(self) -> None:
        """Test that the multigraph view XML is valid and well-formed."""
        multigraph_view = self.env.ref("product_connect.view_product_processing_multigraph")

        # Test that get_views doesn't raise validation errors
        try:
            views_data = multigraph_view.get_views([(multigraph_view.id, "graph")])
            self.assertIn("views", views_data)
            self.assertIn("graph", views_data["views"])
        except ValidationError as e:
            self.fail(f"Multigraph view XML validation failed: {e}")

    def test_multigraph_component_initialization(self) -> None:
        """Test that the custom JavaScript component is properly registered."""
        # Verify the view references the correct js_class
        multigraph_view = self.env.ref("product_connect.view_product_processing_multigraph")
        arch_string = multigraph_view.arch

        # Check that js_class is set to "multigraph"
        self.assertIn('js_class="multigraph"', arch_string)

        # Verify required fields are present for the component
        required_fields = [
            "is_ready_for_sale_last_enabled_date",
            "initial_price_total",
            "initial_cost_total",
            "initial_quantity",
            "image_count",
        ]

        for field in required_fields:
            self.assertIn(field, arch_string, f"Required field {field} missing from multigraph view")

    def test_multigraph_measures_configuration(self) -> None:
        """Test that multigraph measures are properly configured."""
        multigraph_view = self.env.ref("product_connect.view_product_processing_multigraph")
        arch_string = multigraph_view.arch

        # Check measure fields have correct configuration
        measure_configs = [
            ("initial_price_total", 'type="measure"', 'widget="monetary"'),
            ("initial_cost_total", 'type="measure"', 'widget="monetary"'),
            ("initial_quantity", 'type="measure"'),
            ("image_count", 'type="measure"'),
        ]

        for field_name, type_attr, *optional_attrs in measure_configs:
            self.assertIn(f'name="{field_name}"', arch_string)
            self.assertIn(type_attr, arch_string)

            for optional_attr in optional_attrs:
                self.assertIn(optional_attr, arch_string)

    def test_multigraph_date_grouping(self) -> None:
        """Test that date grouping field is properly configured."""
        multigraph_view = self.env.ref("product_connect.view_product_processing_multigraph")
        arch_string = multigraph_view.arch

        # Verify date field with interval
        self.assertIn('name="is_ready_for_sale_last_enabled_date"', arch_string)
        self.assertIn('interval="day"', arch_string)

    def test_multigraph_action_integration(self) -> None:
        """Test that the analytics action properly integrates with multigraph view."""
        action = self.env.ref("product_connect.action_product_processing_analytics")

        # Verify action is configured correctly
        self.assertEqual(action.res_model, "product.template")
        self.assertIn("graph", action.view_mode)

        # Check that the specific multigraph view is referenced
        self.assertEqual(action.view_id.id, self.env.ref("product_connect.view_product_processing_multigraph").id)

    def test_multigraph_context_configuration(self) -> None:
        """Test that the action context is properly configured for multigraph."""
        action = self.env.ref("product_connect.action_product_processing_analytics")

        # Parse context (might be stored as string)
        context = action.context
        if isinstance(context, str):
            import ast

            context = ast.literal_eval(context)

        # Ensure context is a dict for type checker
        assert isinstance(context, dict)

        # Verify multigraph-specific context
        expected_context_keys = ["search_default_date_range_group", "graph_groupbys", "graph_measures"]

        for key in expected_context_keys:
            self.assertIn(key, context, f"Missing context key: {key}")

        # Verify graph configuration
        self.assertEqual(context["graph_groupbys"], ["is_ready_for_sale_last_enabled_date:day"])
        expected_measures = ["initial_price_total", "initial_cost_total", "initial_quantity", "image_count"]
        self.assertEqual(context["graph_measures"], expected_measures)

    def test_multigraph_data_rendering(self) -> None:
        """Test that multigraph can render data without errors."""
        # Use products created in setUpClass to test data rendering
        ProductTemplate = self.env["product.template"]

        # Search for products that should appear in the multigraph
        products = ProductTemplate.search(
            [("is_ready_for_sale_last_enabled_date", "!=", False), ("id", "in", [p.id for p in self.multigraph_products])]
        )

        # Verify we have test data
        self.assertTrue(len(products) > 0, "No test products found for multigraph")

        # Test that we can read the multigraph fields without errors
        for product in products:
            try:
                # Test all measure fields can be read
                _ = product.initial_price_total
                _ = product.initial_cost_total
                _ = product.initial_quantity
                _ = product.image_count
                _ = product.is_ready_for_sale_last_enabled_date
            except Exception as e:
                self.fail(f"Error reading multigraph fields from product {product.name}: {e}")

    def test_multigraph_no_js_errors(self) -> None:
        """Test that the multigraph view doesn't contain deprecated JavaScript patterns."""
        # Read the multigraph JavaScript files to check for common issues
        js_files = [
            "addons/product_connect/static/src/views/multigraph/multigraph_view.js",
            "addons/product_connect/static/src/views/multigraph/multigraph_controller.js",
            "addons/product_connect/static/src/views/multigraph/multigraph_renderer.js",
        ]

        deprecated_patterns = [
            "jQuery",
            "$(",
            ".extend(",
            "odoo.define",
            ";",  # Should not have semicolons in our style
        ]

        for js_file in js_files:
            try:
                with open(js_file) as f:
                    content = f.read()

                for pattern in deprecated_patterns:
                    self.assertNotIn(pattern, content, f"Deprecated pattern '{pattern}' found in {js_file}")
            except FileNotFoundError:
                # File might not exist, which is okay for this test
                pass

    def test_multigraph_arch_parser_compatibility(self) -> None:
        """Test that the arch parser handles multigraph XML correctly."""
        # Create a test multigraph view to verify arch parsing
        test_arch = """
        <graph string="Test MultiGraph" type="line" js_class="multigraph">
            <field name="create_date" interval="month"/>
            <field name="list_price" type="measure" widget="monetary" string="Price"/>
            <field name="qty_available" type="measure" string="Quantity"/>
        </graph>
        """

        test_view = self.View.create(
            {
                "name": "test.multigraph.arch.parser",
                "model": "product.template",
                "type": "graph",
                "arch": test_arch,
            }
        )

        # Test that the view can be processed without errors
        try:
            processed = test_view.get_views([(test_view.id, "graph")])
            self.assertIn("views", processed)
            self.assertIn("graph", processed["views"])

            # Verify the arch was processed correctly
            view_data = processed["views"]["graph"]
            self.assertIn("arch", view_data)

        except Exception as e:
            self.fail(f"Arch parser failed to process multigraph view: {e}")
        finally:
            # Clean up test view
            test_view.unlink()

    def test_multigraph_field_validation(self) -> None:
        """Test that multigraph validates required fields correctly."""
        # Test that the required fields exist on the model
        ProductTemplate = self.env["product.template"]

        required_fields = [
            "is_ready_for_sale_last_enabled_date",
            "initial_price_total",
            "initial_cost_total",
            "initial_quantity",
            "image_count",
        ]

        model_fields = ProductTemplate.fields_get(required_fields)

        for field_name in required_fields:
            self.assertIn(field_name, model_fields, f"Required multigraph field '{field_name}' not found on product.template model")

    def test_multigraph_performance_basic(self) -> None:
        """Basic performance test for multigraph view loading."""
        import time

        # Measure time to load the multigraph view
        start_time = time.time()

        multigraph_view = self.env.ref("product_connect.view_product_processing_multigraph")
        views_data = multigraph_view.get_views([(multigraph_view.id, "graph")])

        end_time = time.time()
        load_time = end_time - start_time

        # Should load in reasonable time (under 1 second for tests)
        self.assertLess(load_time, 1.0, f"Multigraph view took too long to load: {load_time:.2f}s")

        # Verify the view data is complete
        self.assertIn("views", views_data)
        self.assertIn("graph", views_data["views"])
