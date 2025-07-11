from odoo.tests import tagged
from .fixtures.test_base import ProductConnectHttpCase


@tagged("post_install", "-at_install", "product_connect_tour")
class TestShippingAnalyticsTour(ProductConnectHttpCase):
    """Tour test runner for shipping analytics UI tests"""

    def test_shipping_analytics_tour(self) -> None:
        """Run the shipping analytics tour"""
        self.start_tour("/odoo", "shipping_analytics_tour", login=self.test_user.login)