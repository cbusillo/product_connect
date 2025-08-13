from ..common_imports import tagged, TOUR_TAGS
from ..fixtures.base import TourTestCase


@tagged(*TOUR_TAGS)
class TestMotorWorkflowTour(TourTestCase):
    def test_motor_workflow_to_enabled_product_tour(self) -> None:
        self.start_tour("/odoo", "motor_workflow_to_enabled_product_tour")
