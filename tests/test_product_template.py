from unittest.mock import patch

from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError
from odoo.addons.product_connect.services.shopify.helpers import SyncMode
from odoo.addons.product_connect.models.shopify_sync import ShopifySync


class TestProductTemplate(TransactionCase):
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
            product = env_without_skip["product.template"].create({"name": "Test", "type": "consu"})
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
