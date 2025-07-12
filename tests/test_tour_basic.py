from odoo.tests import tagged
from .fixtures.test_base import ProductConnectHttpCase


@tagged("post_install", "-at_install", "product_connect_tour")
class TestBasicTour(ProductConnectHttpCase):
    """Basic tour test runner to verify Odoo UI loads correctly"""

    def test_basic_tour(self) -> None:
        """Run the basic tour that verifies Odoo UI loads correctly"""
        self.start_tour("/odoo", "test_basic_tour", login=self.test_user.login)
