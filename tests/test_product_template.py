from unittest.mock import patch

from odoo.tests import TransactionCase
from odoo.addons.product_connect.services.shopify.helpers import SyncMode


class TestProductTemplate(TransactionCase):
    test_tags = {"-at_install", "-post_install"}

    def test_create_syncs_variants(self) -> None:
        with patch.object(type(self.env["shopify.sync"]), "create_and_run_async") as create_sync:
            product = self.env["product.template"].create({"name": "Test", "type": "consu"})
            variant_ids = product.product_variant_ids.ids
            create_sync.assert_any_call({"mode": SyncMode.EXPORT_BATCH_PRODUCTS, "odoo_products_to_sync": [(6, 0, variant_ids)]})
