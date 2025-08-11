"""Simple test to verify infrastructure is working."""

from odoo.tests import tagged
from ..fixtures.base import UnitTestCase
from ..fixtures.factories import ProductFactory


@tagged("unit_test", "post_install", "-at_install")
class TestInfrastructureCheck(UnitTestCase):
    """Simple test to verify the test infrastructure is working."""
    
    def test_basic_math(self):
        """Test basic arithmetic."""
        self.assertEqual(2 + 2, 4)
        self.assertTrue(True)
    
    def test_factory_works(self):
        """Test that factory creates products."""
        product = ProductFactory.create(self.env)
        self.assertTrue(product)
        self.assertTrue(product.default_code)
        self.assertEqual(product.type, "consu")
    
    def test_context_setup(self):
        """Test that context is properly set up."""
        self.assertTrue(self.env.context.get("skip_shopify_sync"))
        self.assertTrue(self.env.context.get("tracking_disable"))