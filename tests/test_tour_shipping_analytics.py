from odoo.tests import tagged
from .fixtures.test_base import ProductConnectHttpCase
import secrets


@tagged("post_install", "-at_install", "product_connect_tour")
class TestShippingAnalyticsTour(ProductConnectHttpCase):
    """Tour test runner for shipping analytics UI tests"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.env = cls.env(context=dict(cls.env.context, skip_shopify_sync=True, tracking_disable=True))

        # Create test user with proper permissions
        secure_password = secrets.token_urlsafe(32)
        cls.test_user = cls.env["res.users"].create(
            {
                "name": "Shipping Analytics Tour User",
                "login": "shipping_tour_user",
                "password": secure_password,
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("sales_team.group_sale_salesman").id,
                            cls.env.ref("stock.group_stock_user").id,
                        ],
                    )
                ],
            }
        )
        cls.test_user_password = secure_password

    def test_shipping_analytics_tour(self) -> None:
        """
        Run the shipping analytics tour that tests:
        - Navigation to shipping analytics from Sales menu
        - Pivot view functionality
        - Graph view switching
        - Filter application
        - Views load without errors
        """
        self.start_tour("/odoo", "shipping_analytics_tour", login=self.test_user.login, timeout=120)
