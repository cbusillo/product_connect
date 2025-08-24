from ..common_imports import tagged, TOUR_TAGS
from ..fixtures.base import TourTestCase


@tagged(*TOUR_TAGS, "product_connect")
class TestBasicTour(TourTestCase):
    def test_basic_tour(self) -> None:
        """Test basic tour functionality with improved error handling."""
        import logging
        _logger = logging.getLogger(__name__)
        
        _logger.info("Starting TestBasicTour.test_basic_tour")
        
        # Use reduced timeout for faster failure detection
        timeout = 60  # 1 minute should be sufficient for basic tour
        try:
            _logger.info(f"Starting tour 'test_basic_tour' with timeout {timeout}s")
            self.start_tour("/web", "test_basic_tour", timeout=timeout)
            _logger.info("Tour completed successfully")
        except Exception as e:
            _logger.error(f"Tour failed: {e}")
            self.fail(f"Basic tour failed after {timeout}s: {e}")
