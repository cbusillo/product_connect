from odoo.tests import tagged
from ..fixtures.base import TourTestCase


@tagged("post_install", "-at_install", "tour_test")
class TestBasicTour(TourTestCase):
    """Basic tour test runner to verify Odoo UI loads correctly"""

    def test_basic_tour(self) -> None:
        """Run the basic tour that verifies Odoo UI loads correctly"""
        self.start_tour("/odoo", "test_basic_tour", login="admin")
