from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .fixtures.test_service_base import ShopifyTestBase


class ImportIdempotencySetupMixin:
    """Mixin for common setup code in import idempotency tests.

    This mixin expects to be used with ShopifyTestBase which provides:
    - self._setup_shopify_mocks()
    - self.env
    - self.test_products
    """

    def _setup_import_idempotency_test(self: "ShopifyTestBase") -> None:
        """Common setup for import idempotency tests."""
        self._setup_shopify_mocks()

        # Create sync record
        self.sync_record = self.env["shopify.sync"].create(
            {
                "mode": "import_changed_orders",
            }
        )

        # Create test product
        self.test_product = self.test_products[0]
        self.test_product.write(
            {
                "shopify_variant_id": "987654321",
                "list_price": 99.99,
            }
        )
