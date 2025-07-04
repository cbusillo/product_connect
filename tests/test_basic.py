from odoo.tests import tagged
from unittest.mock import patch, MagicMock
from odoo.exceptions import ValidationError
from .fixtures.test_base import ProductConnectTransactionCase


@tagged("post_install", "-at_install", "test_basic")
class TestTemplate(ProductConnectTransactionCase):
    """Template test demonstrating best practices using base test class
    
    This template shows how to use the pre-created test data from the base class:
    - Products with valid SKUs (self.test_product, self.test_products, etc.)
    - Test partners (self.test_partner, self.test_partners)
    - Context automatically set for skip_shopify_sync and tracking_disable
    """

    def test_using_base_products(self) -> None:
        """Example using pre-created products from base class"""
        # Use the standard test product
        self.assertEqual(self.test_product.default_code, "10000001")
        self.assertEqual(self.test_product.type, "consu")
        self.assertTrue(self.test_product.website_description)
        
        # Use one of the pool products
        product = self.test_products[0]
        product.write({'shopify_next_export': True})
        self.assertEqual(product.default_code, "30000001")
        
        # Use specialized products
        self.assertFalse(self.test_product_not_for_sale.sale_ok)
        self.assertFalse(self.test_product_unpublished.is_published)
        self.assertEqual(self.test_product_motor.source, "motor")

    def test_creating_product_variants(self) -> None:
        """Example creating product with variants using valid SKUs"""
        # Create a product template with attributes
        size_attr = self.env['product.attribute'].create({
            'name': 'Test Size',
            'display_type': 'radio',
        })
        
        size_values = []
        for size in ['S', 'M', 'L']:
            val = self.env['product.attribute.value'].create({
                'name': size,
                'attribute_id': size_attr.id,
            })
            size_values.append(val)
        
        template = self.env['product.template'].create({
            'name': 'Test T-Shirt',
            'type': 'consu',
            'default_code': '60000001',  # Valid SKU
            'website_description': 'Test T-shirt with sizes',
            'attribute_line_ids': [(0, 0, {
                'attribute_id': size_attr.id,
                'value_ids': [(6, 0, [v.id for v in size_values])],
            })],
        })
        
        # Variants are created automatically
        self.assertEqual(len(template.product_variant_ids), 3)

    def setUp(self) -> None:
        """Set up test-specific data"""
        super().setUp()
        # Example: Create test-specific data that varies per test
        self.test_timestamp = f"test_{self.id()}"

    def test_partner_creation(self) -> None:
        """Test partner creation and field values"""
        # Use the pre-created test partner from base class
        self.assertEqual(self.test_partner.name, "Test Customer")
        self.assertEqual(self.test_partner.email, "test@example.com")
        self.assertTrue(self.test_partner.is_company is False)

    def test_validation_error(self) -> None:
        """Test validation error handling"""
        # Partner name is required
        with self.assertRaises(Exception):
            self.env["res.partner"].create(
                {
                    "name": False,
                    "email": "invalid@example.com",
                }
            )

    def test_context_usage(self) -> None:
        """Test using context to control behavior"""
        # Example: Skip some processing with context
        partner_with_context = (
            self.env["res.partner"]
            .with_context(skip_validation=True)
            .create(
                {
                    "name": "Context Test Partner",
                    "email": "context@example.com",
                }
            )
        )
        self.assertTrue(partner_with_context.exists())

        # Check context is available
        self.assertTrue(self.env.context.get("skip_shopify_sync", False))

    def test_partner_search(self) -> None:
        """Test partner search functionality"""
        found_partners = self.env["res.partner"].search([("name", "=", "Test Customer")])
        self.assertIn(self.test_partner, found_partners)
        self.assertGreaterEqual(len(found_partners), 1)

    def test_with_patch_object_context_manager(self) -> None:
        """Example using patch.object as context manager"""
        # Mock a method on res.partner model
        with patch.object(type(self.test_partner), "message_post") as mock_message_post:
            mock_message_post.return_value = True

            # Call method that would post a message
            self.test_partner.message_post(body="Test message", subject="Test")

            # Verify mock was called correctly
            mock_message_post.assert_called_once_with(body="Test message", subject="Test")

    @patch.object(ValidationError, "__init__", return_value=None)
    def test_with_patch_object_decorator(self, mock_init: MagicMock) -> None:
        """Example using patch.object as decorator"""
        # This is a contrived example - normally you'd mock actual business logic
        try:
            # Code that might raise ValidationError
            if not self.test_partner.email:
                raise ValidationError("Email required")
        except ValidationError:
            # Mock prevents the actual exception
            pass

        # In real tests, mock external services or complex computations
        self.assertTrue(mock_init.called or not mock_init.called)  # Always true


# Tour tests should now be in a separate file in tests/tours/
# See tests/tours/test_basic_tour.py for the tour runner template
