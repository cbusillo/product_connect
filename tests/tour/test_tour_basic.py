from ..common_imports import tagged, TOUR_TAGS
from ..fixtures.base import TourTestCase


@tagged(*TOUR_TAGS)
class TestBasicTour(TourTestCase):
    """Basic tour test runner to verify Odoo UI loads correctly"""

    def test_basic_tour(self) -> None:
        """Run the basic tour that verifies Odoo UI loads correctly"""
        self.start_tour("/odoo", "test_basic_tour")
