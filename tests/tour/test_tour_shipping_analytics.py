from odoo.tests import tagged
from ..fixtures.base import TourTestCase


@tagged("post_install", "-at_install", "tour_test")
class TestShippingAnalyticsTour(TourTestCase):
    """Tour test runner for shipping analytics UI tests"""

    def test_shipping_analytics_tour(self) -> None:
        """Run the shipping analytics tour"""
        self.start_tour("/odoo", "shipping_analytics_tour", login="admin")
