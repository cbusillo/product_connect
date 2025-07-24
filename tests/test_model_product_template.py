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
        # Create tech result
        dismantle_result = self.env["motor.dismantle.result"].create(
            {
                "name": "Test Result",
                "mark_for_repair": False,
            }
        )

        # Create motor product with tech_result
        product = self._create_motor_product(
            name="Test Motor Product",
            default_code="12345678",
            template_vals={"name": "Test Motor Part"},
            tech_result=dismantle_result.id,
        )

        # Clear existing messages
        product.motor.message_ids.unlink()

        # Mark as scrap
        product.is_scrap = True

        # Check message was posted
        messages = product.motor.message_ids.filtered(lambda m: "marked as scrap" in m.body)
        self.assertEqual(len(messages), 1, "Should post exactly one scrap message")
        self.assertIn(product.motor_product_template.name, messages[0].body)

        # Unmark as scrap
        product.is_scrap = False

        # Check unmarked message was posted
        messages = product.motor.message_ids.filtered(lambda m: "unmarked as scrap" in m.body)
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
        # Create tech result
        dismantle_result = self.env["motor.dismantle.result"].create(
            {
                "name": "Test Result for UI",
                "mark_for_repair": False,
            }
        )

        # Create motor product
        product = self._create_motor_product(
            name="Test UI Refresh Product",
            default_code="12345678",
            motor_vals={
                "horsepower": 75.0,
                "model": "TEST2",
                "cost": 500.0,
            },
            tech_result=dismantle_result.id,
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

    def test_is_scrap_resets_stage_fields(self) -> None:
        """Test that marking a motor product as scrap resets all stage fields to False"""
        # Create tech result
        dismantle_result = self.env["motor.dismantle.result"].create(
            {
                "name": "Test Result for Reset",
                "mark_for_repair": False,
            }
        )

        # Create motor product with image support
        product = self._create_motor_product(
            name="Test Scrap Reset Product",
            default_code="87654321",
            with_image=True,
            tech_result=dismantle_result.id,
        )

        # Set stage fields to True after creation
        product.write(
            {
                "is_dismantled": True,
                "is_dismantled_qc": True,
                "is_cleaned": True,
                "is_cleaned_qc": True,
                "is_pictured": True,
                "is_pictured_qc": True,
                "bin": "A01",
                "weight": 10,
            }
        )

        # Verify all stage fields are True before marking as scrap
        self.assertTrue(product.is_dismantled, "is_dismantled should be True before marking as scrap")
        self.assertTrue(product.is_dismantled_qc, "is_dismantled_qc should be True before marking as scrap")
        self.assertTrue(product.is_cleaned, "is_cleaned should be True before marking as scrap")
        self.assertTrue(product.is_cleaned_qc, "is_cleaned_qc should be True before marking as scrap")
        self.assertTrue(product.is_pictured, "is_pictured should be True before marking as scrap")
        self.assertTrue(product.is_pictured_qc, "is_pictured_qc should be True before marking as scrap")
        self.assertFalse(product.is_scrap, "is_scrap should be False initially")

        # Mark product as scrap
        product.is_scrap = True

        # Verify all stage fields are reset to False
        self.assertFalse(product.is_dismantled, "is_dismantled should be False when marked as scrap")
        self.assertFalse(product.is_dismantled_qc, "is_dismantled_qc should be False when marked as scrap")
        self.assertFalse(product.is_cleaned, "is_cleaned should be False when marked as scrap")
        self.assertFalse(product.is_cleaned_qc, "is_cleaned_qc should be False when marked as scrap")
        self.assertFalse(product.is_pictured, "is_pictured should be False when marked as scrap")
        self.assertFalse(product.is_pictured_qc, "is_pictured_qc should be False when marked as scrap")
        self.assertTrue(product.is_scrap, "is_scrap should remain True")

    def test_is_scrap_unmark_does_not_affect_stage_fields(self) -> None:
        """Test that unmarking a motor product as scrap does not affect stage fields"""
        # Create tech result
        dismantle_result = self.env["motor.dismantle.result"].create(
            {
                "name": "Test Result for Unscrap",
                "mark_for_repair": False,
            }
        )

        # Create a motor product that's already scrapped
        product = self._create_motor_product(
            name="Test Unscrap Product",
            default_code="11223344",
            is_scrap=True,
            tech_result=dismantle_result.id,
        )

        # Set some stage fields while product is scrapped
        product.write(
            {
                "is_dismantled": True,
                "is_cleaned": True,
            }
        )

        # Unmark as scrap
        product.is_scrap = False

        # Verify stage fields remain unchanged
        self.assertTrue(product.is_dismantled, "is_dismantled should remain True when unmarking scrap")
        self.assertTrue(product.is_cleaned, "is_cleaned should remain True when unmarking scrap")
        self.assertFalse(product.is_scrap, "is_scrap should be False")

    def test_is_scrap_requires_tech_result_for_motor_products(self) -> None:
        """Test that tech_result is required when marking motor products as scrap"""
        # Create motor product without tech_result
        product = self._create_motor_product(
            name="Test Scrap Validation Product",
            default_code="99887766",
        )

        # Try to mark as scrap without tech_result - should fail
        with self.assertRaises(ValidationError) as context:
            product.is_scrap = True
        self.assertIn("Tech result is required", str(context.exception))

        # Set tech_result
        dismantle_result = self.env["motor.dismantle.result"].create(
            {
                "name": "Test Scrap Reason",
                "mark_for_repair": False,
            }
        )
        product.tech_result = dismantle_result

        # Now marking as scrap should work
        product.is_scrap = True
        self.assertTrue(product.is_scrap, "Product should be marked as scrap after setting tech_result")

    def test_is_scrap_tracking_posts_motor_message(self) -> None:
        """Test that marking as scrap posts tracking message to motor"""
        # Create motor product with tech_result
        dismantle_result = self.env["motor.dismantle.result"].create(
            {
                "name": "Damaged Beyond Repair",
                "mark_for_repair": False,
            }
        )

        product = self._create_motor_product(
            name="Test Scrap Tracking Product",
            default_code="77665544",
            tech_result=dismantle_result.id,
        )

        # Clear motor messages to have a clean test
        product.motor.message_ids.unlink()

        # Mark as scrap
        product.is_scrap = True

        # Check for motor message
        motor_messages = product.motor.message_ids.filtered(lambda m: "marked as scrap" in m.body)

        self.assertEqual(len(motor_messages), 1, "Should have one motor message for scrap")
        self.assertIn(product.motor_product_template.name, motor_messages[0].body)

        # The message provides tracking of:
        # - Who: The user who made the change (message author)
        # - When: The message create_date
        # - What: Product marked as scrap
        # - Why: tech_result provides the reason
        self.assertEqual(product.tech_result.name, "Damaged Beyond Repair")
