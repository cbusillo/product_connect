from odoo.tests import tagged
from odoo.addons.product_connect.tests.fixtures.test_base import ProductConnectHttpCase


@tagged("post_install", "-at_install", "product_connect_tour")
class TestMultigraphTour(ProductConnectHttpCase):
    """Tour runner for multigraph view UI tests"""

    def test_multigraph_view_tour(self) -> None:
        """Test the multigraph view functionality through UI tour"""
        # The tour will test the multigraph view functionality
        self.start_tour("/odoo", "test_multigraph_view", login=self.test_user.login)
