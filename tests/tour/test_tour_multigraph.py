from ..common_imports import tagged, TOUR_TAGS
from ..fixtures.base import TourTestCase


@tagged(*TOUR_TAGS)
class TestMultigraphTour(TourTestCase):
    """Tour runner for multigraph view UI tests"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # Create test data for the tour with all required fields
        from datetime import date

        cls.tour_products = cls.env["product.template"].create(
            [
                {
                    "name": f"Tour Product {i}",
                    "default_code": f"{30000 + i}",  # Valid SKU
                    "list_price": 200 * i,
                    "standard_price": 120 * i,
                    "type": "consu",
                    "is_ready_for_sale": True,
                    "is_ready_for_sale_last_enabled_date": date(2025, 1, i),
                    "initial_quantity": 30 * i,
                    "initial_price_total": 3000 * i,
                    "initial_cost_total": 1800 * i,
                }
                for i in range(1, 6)
            ]
        )

    def test_multigraph_view_tour(self) -> None:
        """Test the multigraph view functionality through UI tour"""
        # The tour will test the multigraph view functionality
        self.start_tour("/odoo", "test_multigraph_view", timeout=60)
