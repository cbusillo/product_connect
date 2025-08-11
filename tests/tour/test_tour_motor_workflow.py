from odoo.tests import tagged
from ..fixtures.base import TourTestCase


@tagged("post_install", "-at_install", "tour_test")
class TestMotorWorkflowTour(TourTestCase):
    """Tour test runner for motor workflow UI tests"""

    def test_motor_workflow_to_enabled_product_tour(self) -> None:
        """Run the motor workflow tour"""
        self.start_tour("/odoo", "motor_workflow_to_enabled_product_tour", login="admin")
