from unittest.mock import MagicMock

from odoo.tests import tagged
from odoo import fields
from datetime import timedelta

from ..shopify.sync.exporters.product_exporter import ProductExporter
from ..shopify import helpers as _helpers_module
from ..shopify.gql import (
    ProductSetProductSetProductResourcePublicationsV2NodesPublication,
    ProductSetProductSetProductResourcePublicationsV2Nodes,
)
from .test_base import ShopifyTestBase


class DummySync:
    def __init__(self) -> None:
        self.id = 1
        self.hard_throttle_count = 0
        self.total_count = 0
        self.updated_count = 0


class DummyPublication(ProductSetProductSetProductResourcePublicationsV2NodesPublication):
    def __init__(self, gid: str) -> None:
        super().__init__(id=gid, publication=type("P", (), {"id": gid})())


class DummyPublicationNode(ProductSetProductSetProductResourcePublicationsV2Nodes):
    def __init__(self, gid: str) -> None:
        publication = DummyPublication(gid)
        super().__init__(publication=publication)


@tagged("post_install", "-at_install")
class TestProductExporter(ShopifyTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.exporter = ProductExporter(self.env, DummySync())

    def test_metafield_from_id_value_key(self) -> None:
        result = ProductExporter.metafield_from_id_value_key("5", "k", "v", "text")
        self.assertEqual(result.namespace, "custom")
        self.assertEqual(result.key, "k")
        self.assertEqual(result.value, "v")
        self.assertEqual(result.type, "text")
        self.assertEqual(str(result.id), "gid://shopify/Metafield/5")

    def test_is_published_on_channel(self) -> None:
        gid = "gid://shopify/Publication/" + str(next(iter(_helpers_module.PUBLICATION_CHANNELS.values())))
        publication = DummyPublication(gid)
        self.assertTrue(ProductExporter.is_published_on_channel(publication))
        publication.id = "gid://shopify/Publication/999"
        self.assertFalse(ProductExporter.is_published_on_channel(publication))

    def test_is_published_on_all_channels(self) -> None:
        values = list(_helpers_module.PUBLICATION_CHANNELS.values())
        channels = [DummyPublicationNode(f"gid://shopify/Publication/{v}") for v in values]
        self.assertTrue(self.exporter.is_published_on_all_channels(channels))
        channels.append(DummyPublicationNode("gid://shopify/Publication/999"))
        self.assertFalse(self.exporter.is_published_on_all_channels(channels))

    def test_publish_product(self) -> None:
        self.env["ir.config_parameter"].sudo().set_param("shopify.test_store", "")
        self.exporter.service._client = MagicMock()
        self.exporter._publish_product("gid")
        self.exporter.service.client.update_publications.assert_called_once()

    def test_publish_product_skipped_on_test_store(self) -> None:
        self.env["ir.config_parameter"].sudo().set_param("shopify.test_store", "1")
        self.exporter.service._client = MagicMock()
        self.exporter._publish_product("gid")
        self.exporter.service.client.update_publications.assert_not_called()

    def test_find_products_to_export(self) -> None:
        tmpl1 = (
            self.env["product.template"]
            .with_context(skip_shopify_sync=True)
            .create({"name": "P1", "type": "consu", "website_description": "d"})
        )
        prod1 = tmpl1.product_variant_id
        prod1.shopify_next_export = True

        tmpl2 = (
            self.env["product.template"]
            .with_context(skip_shopify_sync=True)
            .create({"name": "P2", "type": "consu", "sale_ok": False, "website_description": "d"})
        )
        prod2 = tmpl2.product_variant_id

        tmpl3 = (
            self.env["product.template"]
            .with_context(skip_shopify_sync=True)
            .create({"name": "P3", "type": "consu", "website_description": "d"})
        )
        prod3 = tmpl3.product_variant_id
        prod3.shopify_last_exported_at = fields.Datetime.now() + timedelta(days=1)

        result = self.exporter._find_products_to_export()
        self.assertIn(prod1, result)
        self.assertNotIn(prod2, result)
        self.assertNotIn(prod3, result)
