from ..common_imports import tagged, TOUR_TAGS
from ..fixtures.base import TourTestCase


@tagged(*TOUR_TAGS, "product_connect")
class TestShippingAnalyticsTour(TourTestCase):
    def test_shipping_analytics_tour(self) -> None:
        self.start_tour("/web", "shipping_analytics_tour")
