from ..common_imports import tagged, TOUR_TAGS
from ..fixtures.base import TourTestCase


@tagged(*TOUR_TAGS)
class TestShippingAnalyticsTour(TourTestCase):
    """Tour test runner for shipping analytics UI tests"""

    def test_shipping_analytics_tour(self) -> None:
        """Run the shipping analytics tour"""
        self.start_tour("/odoo", "shipping_analytics_tour")
