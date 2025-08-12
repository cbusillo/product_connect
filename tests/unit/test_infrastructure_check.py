"""Simple test to verify infrastructure is working."""

from ..common_imports import tagged, UNIT_TAGS
from ..fixtures.base import UnitTestCase
from ..fixtures.factories import ProductFactory


@tagged(*UNIT_TAGS)
class TestInfrastructureCheck(UnitTestCase):
    """Simple test to verify the test infrastructure is working."""
    
    def test_basic_math(self) -> None:
        """Test basic arithmetic."""
        self.assertEqual(2 + 2, 4)
        self.assertTrue(True)
    
    def test_factory_works(self) -> None:
        """Test that factory creates products."""
        product = ProductFactory.create(self.env)
        self.assertTrue(product)
        self.assertTrue(product.default_code)
        self.assertEqual(product.type, "consu")
    
    def test_context_setup(self) -> None:
        """Test that context is properly set up."""
        self.assertTrue(self.env.context.get("skip_shopify_sync"))
        self.assertTrue(self.env.context.get("tracking_disable"))