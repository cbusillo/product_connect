from odoo.tests import HttpCase, tagged
import secrets


@tagged("post_install", "-at_install", "product_connect_tour")
class TestMotorWorkflowTour(HttpCase):
    """Tour test runner for motor workflow UI tests"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.env = cls.env(context=dict(cls.env.context, skip_shopify_sync=True))

        # Create test user
        secure_password = secrets.token_urlsafe(32)
        cls.test_user = cls.env["res.users"].create(
            {
                "name": "Motor Workflow Tour User",
                "login": "motor_tour_user",
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

        # Create test data for tour
        cls._setup_tour_data()

    @classmethod
    def _setup_tour_data(cls) -> None:
        """Set up data needed for the tour"""
        # Create manufacturers
        for name in ["Mercury", "Yamaha", "Honda"]:
            if not cls.env["product.manufacturer"].search([("name", "=", name)]):
                cls.env["product.manufacturer"].create({"name": name})

        # Create motor product templates if needed
        if not cls.env["motor.product.template"].search([]):
            cls.env["motor.product.template"].create(
                {
                    "name": "Standard Motor Product",
                    "initial_quantity": 1.0,
                    "manufacturers": [(6, 0, cls.env["product.manufacturer"].search([]).ids)],
                }
            )

    def test_motor_workflow_to_enabled_product_tour(self) -> None:
        """
        Run the motor workflow tour that tests:
        - Creating a new motor with all required fields
        - Generating motor products
        - Enabling products for sale
        - Enabling products for purchase
        - Verifying the complete workflow
        """
        self.start_tour("/odoo", "motor_workflow_to_enabled_product_tour", login=self.test_user.login, timeout=120)
