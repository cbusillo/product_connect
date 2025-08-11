"""Proof of concept test using the new infrastructure."""

from odoo.tests import tagged
from ..fixtures import UnitTestCase, ProductFactory


@tagged("unit_test", "post_install", "-at_install")
class TestProductFactory(UnitTestCase):
    """Test the ProductFactory and new test infrastructure."""
    
    def test_create_single_product(self):
        """Test creating a single product with factory."""
        product = ProductFactory.create(self.env, name="Test Motor")
        
        self.assertTrue(product)
        self.assertEqual(product.name, "Test Motor")
        self.assertEqual(product.type, "consu")
        self.assertEqual(product.list_price, 100.0)
        self.assertTrue(product.default_code)
        self.assertTrue(len(product.default_code) == 8)  # OPW SKU pattern
    
    def test_create_batch_products(self):
        """Test creating multiple products."""
        products = ProductFactory.create_batch(self.env, count=3)
        
        self.assertEqual(len(products), 3)
        
        # Ensure all SKUs are unique
        skus = [p.default_code for p in products]
        self.assertEqual(len(skus), len(set(skus)))
    
    def test_create_product_with_variants(self):
        """Test creating product with color variants."""
        product = ProductFactory.create_with_variants(
            self.env, 
            variant_count=4,
            name="Multi-variant Product"
        )
        
        self.assertEqual(product.name, "Multi-variant Product")
        self.assertEqual(len(product.product_variant_ids), 4)
        
        # Check that each variant has a different attribute value
        colors = product.product_variant_ids.mapped("product_template_attribute_value_ids.name")
        self.assertEqual(len(colors), 4)
        self.assertIn("Red", colors)
        self.assertIn("Blue", colors)
    
    def test_mock_service(self):
        """Test mocking external services."""
        mock_shopify = self.mock_service("addons.product_connect.services.shopify.sync.ShopifySync")
        mock_shopify.return_value.sync_product.return_value = {"success": True}
        
        # This would normally trigger a sync
        from ...services.shopify.sync import ShopifySync
        sync = ShopifySync()
        result = sync.sync_product(123)
        
        self.assertEqual(result, {"success": True})
        mock_shopify.return_value.sync_product.assert_called_once_with(123)
    
    def test_assert_record_values(self):
        """Test the assertRecordValues helper."""
        product = ProductFactory.create(
            self.env,
            name="Test Product",
            list_price=250.0,
            standard_price=150.0
        )
        
        self.assertRecordValues(product, {
            "name": "Test Product",
            "list_price": 250.0,
            "standard_price": 150.0,
            "type": "consu",
        })