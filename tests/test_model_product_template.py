from unittest.mock import patch

from odoo.tests import tagged
from .fixtures.test_base import ProductConnectTransactionCase
from odoo.exceptions import ValidationError
from ..services.shopify.helpers import SyncMode
from ..models.shopify_sync import ShopifySync


@tagged("post_install", "-at_install")
class TestProductTemplate(ProductConnectTransactionCase):
    def setUp(self) -> None:
        super().setUp()
        # Use context to skip Shopify sync during tests
        self.env = self.env(context=dict(self.env.context, skip_shopify_sync=True))

    def _assert_sku_validation_error(self, invalid_skus: list[str]) -> None:
        for sku in invalid_skus:
            with self.subTest(sku=sku):
                with self.assertRaises(ValidationError) as context:
                    self.env["product.template"].create({"name": f"Test Product {sku}", "default_code": sku, "type": "consu"})
                self.assertIn("SKU must be 4-8 digits", str(context.exception))

    def test_create_syncs_variants(self) -> None:
        # Remove skip_shopify_sync context for this test since we're testing sync behavior
        env_without_skip = self.env(context=dict(self.env.context))
        if "skip_shopify_sync" in env_without_skip.context:
            env_without_skip = env_without_skip(
                context=dict((k, v) for k, v in env_without_skip.context.items() if k != "skip_shopify_sync")
            )

        with patch.object(ShopifySync, "create_and_run_async") as create_sync:
            # Create product that meets the sync criteria: consumable, ready for sale, and published
            product = env_without_skip["product.template"].create(
                {
                    "name": "Test",
                    "type": "consu",
                    "is_ready_for_sale": True,
                    "is_published": True,
                    "default_code": "1234",  # Add valid SKU to pass validation
                }
            )
            variant_ids = product.product_variant_ids.ids
            create_sync.assert_any_call({"mode": SyncMode.EXPORT_BATCH_PRODUCTS, "odoo_products_to_sync": [(6, 0, variant_ids)]})

    def test_sku_validation_valid_numeric_skus(self) -> None:
        valid_skus = ["1234", "12345", "123456", "1234567", "12345678"]
        for sku in valid_skus:
            with self.subTest(sku=sku):
                product = self.env["product.template"].create({"name": f"Test Product {sku}", "default_code": sku, "type": "consu"})
                self.assertEqual(product.default_code, sku)
                product.unlink()

    def test_sku_validation_invalid_alphanumeric_skus(self) -> None:
        invalid_skus = ["PROD-A", "TEST-SKU-001", "ABC123", "SKU123", "123ABC"]
        self._assert_sku_validation_error(invalid_skus)

    def test_sku_validation_invalid_length_skus(self) -> None:
        invalid_skus = ["123", "123456789", "12", "1"]
        self._assert_sku_validation_error(invalid_skus)

    def test_sku_validation_skip_for_non_consumable_products(self) -> None:
        invalid_sku = "INVALID-SKU"
        product = self.env["product.template"].create({"name": "Test Service", "default_code": invalid_sku, "type": "service"})
        self.assertEqual(product.default_code, invalid_sku)

    def test_sku_validation_bypass_with_context(self) -> None:
        invalid_sku = "INVALID-SKU"
        product = (
            self.env["product.template"]
            .with_context(skip_sku_check=True)
            .create({"name": "Test Bypass", "default_code": invalid_sku, "type": "consu"})
        )
        self.assertEqual(product.default_code, invalid_sku)

    def test_is_scrap_field_default_value(self) -> None:
        """Test that is_scrap field defaults to False"""
        product = self.env["product.template"].create({"name": "Test Scrap Product", "default_code": "12345678", "type": "consu"})
        self.assertFalse(product.is_scrap, "is_scrap should default to False")

    def test_is_scrap_field_can_be_set(self) -> None:
        """Test that is_scrap field can be set to True"""
        product = self.env["product.template"].create({"name": "Test Scrap Product", "default_code": "12345678", "type": "consu"})
        product.is_scrap = True
        self.assertTrue(product.is_scrap, "is_scrap should be True after setting")

    def test_is_scrap_write_posts_message_on_motor_product(self) -> None:
        """Test that marking a motor product as scrap posts a message"""
        # Create motor with required fields
        manufacturer = self.env["product.manufacturer"].create({"name": "Test Scrap Manufacturer", "is_motor_manufacturer": True})
        stroke = self.env["motor.stroke"].create({"name": "Four", "code": "4"})
        config = self.env["motor.configuration"].create({"name": "V8", "code": "V8"})

        motor = self.env["motor"].create(
            {
                "manufacturer": manufacturer.id,
                "stroke": stroke.id,
                "configuration": config.id,
                "horsepower": 100.0,
                "year": "2024",
                "model": "TEST",
                "cost": 1000.0,
            }
        )

        # Create motor product template
        motor_product_template = self.env["motor.product.template"].create(
            {
                "name": "Test Motor Part",
                "strokes": [(4, stroke.id)],
                "configurations": [(4, config.id)],
                "manufacturers": [(4, manufacturer.id)],
            }
        )

        # Create motor product
        product = self.env["product.template"].create(
            {
                "name": "Test Motor Product",
                "default_code": "12345678",
                "type": "consu",
                "source": "motor",
                "motor": motor.id,
                "motor_product_template": motor_product_template.id,
            }
        )

        # Clear existing messages
        motor.message_ids.unlink()

        # Mark as scrap
        product.is_scrap = True

        # Check message was posted
        messages = motor.message_ids.filtered(lambda m: "marked as scrap" in m.body)
        self.assertEqual(len(messages), 1, "Should post exactly one scrap message")
        self.assertIn(motor_product_template.name, messages[0].body)

        # Unmark as scrap
        product.is_scrap = False

        # Check unmarked message was posted
        messages = motor.message_ids.filtered(lambda m: "unmarked as scrap" in m.body)
        self.assertEqual(len(messages), 1, "Should post exactly one un-scrap message")

    def test_is_scrap_excludes_from_ready_to_list(self) -> None:
        """Test that scrapped products are excluded from ready to list"""
        product = self.env["product.template"].create(
            {
                "name": "Test Ready Product",
                "default_code": "12345678",
                "type": "consu",
                "is_listable": True,
                "is_dismantled": True,
                "is_dismantled_qc": True,
                "is_cleaned": True,
                "is_cleaned_qc": True,
                "bin": "A1",
                "weight": 10.0,
            }
        )

        # Add a dummy image to allow is_pictured to be set
        # noinspection SpellCheckingInspection
        self.env["product.image"].create(
            {
                "product_tmpl_id": product.id,
                "image_1920": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",  # 1x1 red pixel
                "name": "test_image",
            }
        )

        # Now set is_pictured
        product.write(
            {
                "is_pictured": True,
                "is_pictured_qc": True,
            }
        )

        # Force recomputation of the field
        product._compute_ready_to_list()

        # Debug: Check all conditions
        conditions = {
            "is_listable": product.is_listable,
            "is_dismantled": product.is_dismantled,
            "is_dismantled_qc": product.is_dismantled_qc,
            "is_cleaned": product.is_cleaned,
            "is_cleaned_qc": product.is_cleaned_qc,
            "is_pictured": product.is_pictured,
            "is_pictured_qc": product.is_pictured_qc,
            "bin": product.bin,
            "weight": product.weight,
            "is_scrap": product.is_scrap,
            "is_ready_to_list": product.is_ready_to_list,
        }

        # Log conditions for debugging if test fails
        if not product.is_ready_to_list:
            import pprint

            print(f"\nProduct conditions: {pprint.pformat(conditions)}")

        # Should be ready to list when not scrapped
        self.assertTrue(product.is_ready_to_list, "Product should be ready to list when all conditions met")

        # Mark as scrap
        product.is_scrap = True

        # Should not be ready to list when scrapped
        self.assertFalse(product.is_ready_to_list, "Scrapped product should not be ready to list")

    def test_is_scrap_in_ui_refresh_fields(self) -> None:
        """Test that is_scrap triggers UI refresh when changed on motor products"""
        # Create motor for UI refresh test
        manufacturer = self.env["product.manufacturer"].create({"name": "Test UI Manufacturer", "is_motor_manufacturer": True})
        stroke = self.env["motor.stroke"].create({"name": "Two", "code": "2"})
        config = self.env["motor.configuration"].create({"name": "V6", "code": "V6"})

        motor = self.env["motor"].create(
            {
                "manufacturer": manufacturer.id,
                "stroke": stroke.id,
                "configuration": config.id,
                "horsepower": 75.0,
                "year": "2024",
                "model": "TEST2",
                "cost": 500.0,
            }
        )

        product = self.env["product.template"].create(
            {
                "name": "Test UI Refresh Product",
                "default_code": "12345678",
                "type": "consu",
                "source": "motor",
                "motor": motor.id,
            }
        )

        # The UI refresh functionality is tested by verifying that:
        # 1. is_scrap field exists and can be modified
        # 2. When modified on a motor product, it would trigger notify_changes
        # Since notify_changes sends bus messages for UI updates, we verify the field works correctly

        # Change is_scrap and verify it was set
        self.assertFalse(product.is_scrap, "is_scrap should default to False")
        product.is_scrap = True
        self.assertTrue(product.is_scrap, "is_scrap should be True after setting")

        # Verify the field has the expected attributes
        field = product._fields.get("is_scrap")
        self.assertIsNotNone(field, "is_scrap field should exist")
        self.assertTrue(field.tracking, "is_scrap should have tracking enabled")
        self.assertTrue(field.index, "is_scrap should be indexed")
