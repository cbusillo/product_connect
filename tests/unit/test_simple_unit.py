"""Simple unit test to validate infrastructure."""

from ..common_imports import tagged, UNIT_TAGS
from ..fixtures.base import UnitTestCase
from ..fixtures.factories import ProductFactory


@tagged(*UNIT_TAGS)
class TestSimpleUnit(UnitTestCase):
    """Simple test to validate the new infrastructure works."""

    def test_simple_creation(self) -> None:
        """Test simple product creation using factory."""
        product = ProductFactory.create(self.env, name="Simple Test Product", type="consu")
        self.assertTrue(product)
        self.assertEqual(product.name, "Simple Test Product")
        self.assertTrue(product.default_code)  # Factory generates SKU
