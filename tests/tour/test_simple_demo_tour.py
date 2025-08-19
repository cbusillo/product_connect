"""Simple demo-based tour test to verify infrastructure works"""

import os
import logging
from odoo.tests import HttpCase, tagged

_logger = logging.getLogger(__name__)
_logger.info("IMPORTING test_simple_demo_tour.py - THIS SHOULD APPEAR IN LOGS")


from ..base_types import TOUR_TAGS

@tagged(*TOUR_TAGS)
class TestSimpleDemoTour(HttpCase):
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
        # This uses the standard Odoo HttpCase pattern
        # With production clones, we use the test password set up during DB clone
        self.browser_js(
            "/web",
            "odoo.__DEBUG__.services['web_tour.tour'].run('test_basic_tour')",
            "odoo.__DEBUG__.services['web_tour.tour'].tours['test_basic_tour'].ready",
            login=self._get_test_login(),
            timeout=60
        )