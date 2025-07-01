from odoo.tests import tagged
from .fixtures.test_base import ProductConnectHttpCase


@tagged("post_install", "-at_install", "product_connect_tour")
class TestProductProcessingDashboardTour(ProductConnectHttpCase):
    """Tour test runner for product processing report UI tests"""

    def test_product_processing_dashboard_tour(self) -> None:
        """
        Run the product processing report tour that tests:
        - Report loads from Inventory > Reporting menu
        - All three views work (graph, pivot, list)
        - Filters and grouping function correctly
        - Report displays processed product analytics
        """
        self.start_tour("/odoo", "product_processing_dashboard_tour", login=self.test_user.login, timeout=120)
