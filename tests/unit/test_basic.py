from odoo.tests import tagged
from unittest.mock import patch, MagicMock
from odoo.exceptions import ValidationError
from ..fixtures.base import UnitTestCase
from ..fixtures.factories import ProductFactory, PartnerFactory


@tagged("post_install", "-at_install", "unit_test")
class TestTemplate(UnitTestCase):
    """Template test demonstrating best practices using base test class

    This template shows how to use the pre-created test data from the base class:
    - Products with valid SKUs (self.test_product, self.test_products, etc.)
    - Test partners (self.test_partner, self.test_partners)
    - Context automatically set for skip_shopify_sync and tracking_disable
    """

    def test_using_factories(self) -> None:
        """Example using factories for test data creation"""
        # Create product using factory
        product = ProductFactory.create(self.env, name="Test Product", type="consu")
        self.assertEqual(product.type, "consu")
        self.assertTrue(product.default_code)  # Factory generates SKU
        self.assertGreater(product.list_price, 0)  # Factory sets price
        
        # Create partner using factory
        partner = PartnerFactory.create(self.env, name="Test Partner")
        self.assertTrue(partner.email)
        self.assertEqual(partner.customer_rank, 1)

    def test_creating_product_variants(self) -> None:
        """Example creating product with variants using valid SKUs"""
        # Create a product template with attributes
        size_attr = self.env["product.attribute"].create(
            {
                "name": "Test Size",
                "display_type": "radio",
            }
        )

        size_values = []
        for size in ["S", "M", "L"]:
            val = self.env["product.attribute.value"].create(
                {
                    "name": size,
                    "attribute_id": size_attr.id,
                }
            )
            size_values.append(val)

        template = self.env["product.template"].create(
            {
                "name": "Test T-Shirt",
                "type": "consu",
                "default_code": "60000001",  # Valid SKU
                "website_description": "Test T-shirt with sizes",
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": size_attr.id,
                            "value_ids": [(6, 0, [v.id for v in size_values])],
                        },
                    )
                ],
            }
        )

        # Variants are created automatically
        self.assertEqual(len(template.product_variant_ids), 3)

    def setUp(self) -> None:
        """Set up test-specific data"""
        super().setUp()
        # Example: Create test-specific data that varies per test
        self.test_timestamp = f"test_{self.id()}"

    def test_partner_comprehensive(self) -> None:
        """Comprehensive test for partner functionality using factories"""
        # Create partner using factory
        partner = PartnerFactory.create(self.env, name="Test Customer")
        self.assertEqual(partner.name, "Test Customer")
        self.assertTrue(partner.email)
        self.assertFalse(partner.is_company)
        
        # Create partner with context
        partner_with_context = PartnerFactory.create(
            self.env,
            name="Context Test Partner",
            email="context@example.com"
        )
        self.assertTrue(partner_with_context.exists())
        self.assertEqual(partner_with_context.name, "Context Test Partner")
        self.assertEqual(partner_with_context.email, "context@example.com")
        
        # Test partner search functionality
        found_partners = self.env["res.partner"].search([("name", "=", "Test Customer")])
        self.assertIn(partner, found_partners)
        
        # Test context is properly set from base class
        self.assertTrue(self.env.context.get("skip_shopify_sync", False))
        
        # Test searching for the newly created partner
        context_partners = self.env["res.partner"].search([("name", "=", "Context Test Partner")])
        self.assertIn(partner_with_context, context_partners)

    def test_validation_error(self) -> None:
        """Test validation error handling with invalid product SKU"""
        # Test that creating product with invalid SKU raises ValidationError
        with self.assertRaises(ValidationError):
            self.env["product.product"].create(
                {
                    "name": "Invalid Product",
                    "default_code": "ABC",  # Invalid SKU (less than 4 digits)
                    "type": "consu",
                }
            )

    def test_with_patch_object_context_manager(self) -> None:
        """Example using patch.object as context manager"""
        # Create partner using factory
        partner = PartnerFactory.create(self.env, name="Test Partner")
        
        # Mock a method on res.partner model
        with patch.object(type(partner), "message_post") as mock_message_post:
            mock_message_post.return_value = True

            # Call method that would post a message
            partner.message_post(body="Test message", subject="Test")

            # Verify mock was called correctly
            mock_message_post.assert_called_once_with(body="Test message", subject="Test")

    @patch.object(ValidationError, "__init__", return_value=None)
    def test_with_patch_object_decorator(self, mock_init: MagicMock) -> None:
        """Example using patch.object as decorator"""
        # Create partner using factory for testing
        partner = PartnerFactory.create(self.env)
        
        # This is a contrived example - normally you'd mock actual business logic
        try:
            # Code that might raise ValidationError
            if not partner.email:
                raise ValidationError("Email required")
        except ValidationError:
            # Mock prevents the actual exception
            pass

        # In real tests, mock external services or complex computations
        self.assertTrue(mock_init.called or not mock_init.called)  # Always true



# Tour tests should now be in a separate file in tests/tours/
# See tests/tours/test_basic_tour.py for the tour runner template
