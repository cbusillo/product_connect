"""Simple demo-based tour test to verify infrastructure works"""

import os
import logging
from odoo.tests import tagged

_logger = logging.getLogger(__name__)
_logger.info("IMPORTING test_simple_demo_tour.py - THIS SHOULD APPEAR IN LOGS")


from ..base_types import TOUR_TAGS
from ..fixtures.base import TourTestCase

@tagged(*TOUR_TAGS)
class TestSimpleDemoTour(TourTestCase):
    """Test using standard Odoo pattern with demo data"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _logger.info("TestSimpleDemoTour.setUpClass called - TEST IS RUNNING!")
        
        # Get test password from environment if available
        test_password = os.environ.get('ODOO_TEST_PASSWORD')
        if test_password:
            _logger.info("Using test password from environment")
            # Update the admin user's password for this test session
            cls.env['res.users'].browse(2).password = test_password
    
    def test_simple_navigation(self):
        """Test basic navigation without production data dependencies"""
        # Use the fixed start_tour method with proper completion detection
        self.start_tour("/web", "test_basic_tour", login=self._get_test_login())