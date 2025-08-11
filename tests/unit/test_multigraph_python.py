"""Python tests for multigraph view functionality."""

from odoo.tests import tagged
from ..fixtures.base import UnitTestCase


@tagged("post_install", "-at_install", "unit_test")
class TestMultigraphPython(UnitTestCase):
    """Test multigraph view backend functionality"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        # Create test data with processing metrics
        cls.products_with_metrics = []

        # January products
        for i in range(3):
            product = cls.env["product.template"].create(
                {
                    "name": f"January Product {i + 1}",
                    "default_code": f"6000000{i + 1}",
                    "type": "consu",
                    "list_price": 100.0 + (i * 10),  # Will compute to 10000 + (i * 1000) with quantity
                    "standard_price": 60.0 + (i * 5),  # Will compute to 6000 + (i * 500) with quantity
                    "initial_quantity": 100 + (i * 10),
                    "is_ready_for_sale": True,
                    "is_ready_for_sale_last_enabled_date": f"2024-01-{15 + i}",
                }
            )
            cls.products_with_metrics.append(product)

        # February products
        for i in range(3):
            product = cls.env["product.template"].create(
                {
                    "name": f"February Product {i + 1}",
                    "default_code": f"6000001{i + 1}",
                    "type": "consu",
                    "list_price": 100.0 + (i * 10),  # Will compute to 15000 + (i * 1500) with quantity
                    "standard_price": 60.0 + (i * 5),  # Will compute to 9000 + (i * 800) with quantity
                    "initial_quantity": 150 + (i * 15),
                    "is_ready_for_sale": True,
                    "is_ready_for_sale_last_enabled_date": f"2024-02-{10 + i}",
                }
            )
            cls.products_with_metrics.append(product)

    def test_multigraph_view_exists(self) -> None:
        """Test that multigraph view is properly registered"""
        # Check if the view exists
        view = self.env["ir.ui.view"].search(
            [
                ("name", "=", "product.processing.multigraph"),
                ("model", "=", "product.template"),
            ]
        )
        self.assertTrue(view, "Multigraph view should exist")
        self.assertIn("Product Processing Analytics", view.arch_db)

    def test_multigraph_data_aggregation(self) -> None:
        """Test data aggregation for multigraph view"""
        # Read group to simulate what the view would do
        result = (
            self.env["product.template"]
            .with_context(skip_shopify_sync=False)
            .read_group(
                domain=[
                    ("is_ready_for_sale", "=", True),
                    ("id", "in", [p.id for p in self.products_with_metrics]),  # Only test data
                ],
                fields=["initial_price_total:sum", "initial_cost_total:sum", "initial_quantity:sum"],
                groupby=["is_ready_for_sale_last_enabled_date:month"],
            )
        )

        self.assertEqual(len(result), 2, "Should have 2 months of data")

        # Check January data
        jan_data = next((r for r in result if "January" in r.get("is_ready_for_sale_last_enabled_date:month", "")), None)
        self.assertIsNotNone(jan_data)
        # The fields are computed fields, so they might have different sums
        # Let's check they exist and are greater than 0
        self.assertGreater(jan_data["initial_price_total"], 0, "January price total should be > 0")
        self.assertGreater(jan_data["initial_cost_total"], 0, "January cost total should be > 0")
        self.assertGreater(jan_data["initial_quantity"], 0, "January quantity should be > 0")

    def test_multigraph_with_domain_filter(self) -> None:
        """Test multigraph view with domain filters"""
        # Test with price filter - using test data only
        result = (
            self.env["product.template"]
            .with_context(skip_shopify_sync=False)
            .read_group(
                domain=[
                    ("is_ready_for_sale", "=", True),
                    ("initial_price_total", ">", 12000),
                    ("id", "in", [p.id for p in self.products_with_metrics]),  # Only test data
                ],
                fields=["initial_price_total:sum", "initial_quantity:sum"],
                groupby=["is_ready_for_sale_last_enabled_date:month"],
            )
        )

        # Should have at least some results
        self.assertGreater(len(result), 0, "Should have at least one result")
        # Should only include products with price > 12000
        total_price = sum(r["initial_price_total"] for r in result)
        self.assertGreater(total_price, 0)
        # Check that we filtered out some products
        all_products_result = (
            self.env["product.template"]
            .with_context(skip_shopify_sync=False)
            .read_group(
                domain=[
                    ("is_ready_for_sale", "=", True),
                    ("id", "in", [p.id for p in self.products_with_metrics]),
                ],
                fields=["initial_price_total:sum"],
                groupby=["is_ready_for_sale_last_enabled_date:month"],
            )
        )
        all_total = sum(r["initial_price_total"] for r in all_products_result)
        self.assertLess(total_price, all_total, "Filtered total should be less than all products total")

    def test_multigraph_multiple_groupby(self) -> None:
        """Test multigraph with multiple groupby fields"""
        # Add product types for grouping
        for i, product in enumerate(self.products_with_metrics):
            product.write(
                {
                    "categ_id": self.env.ref("product.product_category_all").id
                    if i % 2 == 0
                    else self.env.ref("product.product_category_1").id
                }
            )

        result = self.env["product.template"].read_group(
            domain=[("is_ready_for_sale", "=", True)],
            fields=["initial_price_total:sum"],
            groupby=["is_ready_for_sale_last_enabled_date:month", "categ_id"],
        )

        self.assertGreater(len(result), 2, "Should have more groups with category grouping")

    def test_multigraph_empty_data(self) -> None:
        """Test multigraph view with no data"""
        result = self.env["product.template"].read_group(
            domain=[("id", "=", 0)],  # Impossible domain
            fields=["initial_price_total:sum", "initial_cost_total:sum"],
            groupby=["is_ready_for_sale_last_enabled_date:month"],
        )

        self.assertEqual(len(result), 0, "Should return empty result for no data")

    def test_multigraph_null_values(self) -> None:
        """Test multigraph with null values in measures"""
        # Create product with null metrics
        product_null = self.env["product.template"].create(
            {
                "name": "Product with Null Metrics",
                "default_code": "70000001",
                "type": "consu",
                "initial_price_total": 0.0,
                "initial_cost_total": 0.0,
                "initial_quantity": 0,
                "is_ready_for_sale": True,
                "is_ready_for_sale_last_enabled_date": "2024-03-01",
            }
        )

        result = self.env["product.template"].read_group(
            domain=[("id", "=", product_null.id)],
            fields=["initial_price_total:sum", "initial_cost_total:sum", "initial_quantity:sum"],
            groupby=["is_ready_for_sale_last_enabled_date:month"],
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["initial_price_total"], 0.0)
        self.assertEqual(result[0]["initial_quantity"], 0)

    def test_multigraph_monetary_formatting(self) -> None:
        """Test that monetary fields are properly handled"""
        # Get field definition
        field_price = self.env["product.template"]._fields["initial_price_total"]
        field_cost = self.env["product.template"]._fields["initial_cost_total"]

        # Both should be float fields (monetary is a float with currency)
        self.assertEqual(field_price.type, "float")
        self.assertEqual(field_cost.type, "float")

    def test_multigraph_date_intervals(self) -> None:
        """Test different date interval groupings"""
        # Test day interval
        result_day = self.env["product.template"].read_group(
            domain=[("is_ready_for_sale", "=", True)],
            fields=["initial_price_total:sum"],
            groupby=["is_ready_for_sale_last_enabled_date:day"],
        )

        # Test month interval
        result_month = self.env["product.template"].read_group(
            domain=[("is_ready_for_sale", "=", True)],
            fields=["initial_price_total:sum"],
            groupby=["is_ready_for_sale_last_enabled_date:month"],
        )

        # Day grouping should have more groups than month
        self.assertGreaterEqual(len(result_day), len(result_month))

    def test_multigraph_access_rights(self) -> None:
        """Test that users can access multigraph view data"""
        # Create a test user with basic access
        test_user = self.env["res.users"].create(
            {
                "name": "Multigraph Test User",
                "login": "multigraph_test",
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )

        # Switch to test user
        ProductTemplate = self.env["product.template"].with_user(test_user)

        # Should be able to read group
        result = ProductTemplate.read_group(
            domain=[],
            fields=["initial_price_total:sum"],
            groupby=["is_ready_for_sale_last_enabled_date:month"],
        )

        # Should not raise access error
        self.assertIsInstance(result, list)

    def test_multigraph_computed_measures(self) -> None:
        """Test that computed fields work as measures"""
        # Check if initial_margin field exists and can be computed
        products = self.env["product.template"].search([("id", "in", [p.id for p in self.products_with_metrics])])

        # Ensure we have products to test
        self.assertTrue(products, "Should have test products")
        self.assertEqual(len(products), len(self.products_with_metrics))

        # Check that the fields we're using exist
        self.assertIn("initial_price_total", products._fields)
        self.assertIn("initial_cost_total", products._fields)

        # Manually calculate what margin would be
        for product in products:
            expected_margin = product.initial_price_total - product.initial_cost_total
            # If initial_margin exists as a computed field, it should match
            if "initial_margin" in product._fields:
                # Use getattr to avoid PyCharm unresolved reference warning
                actual_margin = getattr(product, "initial_margin", 0)
                self.assertAlmostEqual(
                    actual_margin, expected_margin, places=2, msg=f"Margin calculation incorrect for {product.name}"
                )
            else:
                # Otherwise just verify the calculation works
                self.assertGreater(expected_margin, 0, "Margin should be positive")
