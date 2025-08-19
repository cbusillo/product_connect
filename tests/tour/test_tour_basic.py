from ..common_imports import tagged, TOUR_TAGS
from ..fixtures.base import TourTestCase


@tagged(*TOUR_TAGS, "product_connect")
class TestBasicTour(TourTestCase):
    def test_basic_tour(self) -> None:
        self.start_tour("/odoo", "test_basic_tour")
