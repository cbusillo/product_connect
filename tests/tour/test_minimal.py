"""Minimal test to debug test discovery"""

import logging
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)
_logger.info("IMPORTING test_minimal.py - MINIMAL TEST")

# Use direct tagging since this doesn't inherit from a base class with tags
@tagged("post_install", "-at_install", "tour_test")
class TestMinimal(TransactionCase):
    """Minimal test without tour functionality"""
    
    def test_minimal(self):
        """Just test that we can run"""
        _logger.info("TestMinimal.test_minimal is running!")
        self.assertTrue(True, "This should always pass")