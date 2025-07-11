from odoo.tests import tagged
from .fixtures.test_base import ProductConnectHttpCase


@tagged("post_install", "-at_install", "product_connect_tour")
class TestMotorWorkflowTour(ProductConnectHttpCase):
    """Tour test runner for motor workflow UI tests"""

    def test_motor_workflow_to_enabled_product_tour(self) -> None:
        """Run the motor workflow tour"""
        self.start_tour("/odoo", "motor_workflow_to_enabled_product_tour", login=self.test_user.login)