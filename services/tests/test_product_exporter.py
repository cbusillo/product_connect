from unittest.mock import MagicMock

from odoo.tests import TransactionCase

from ..shopify.sync.exporters.product_exporter import ProductExporter
from ..shopify import service as _service_module


class DummySync:
    def __init__(self) -> None:
        self.id = 1
        self.hard_throttle_count = 0
        self.total_count = 0
        self.updated_count = 0


class DummyPublication:
    def __init__(self, gid: str) -> None:
        self.id = gid


class TestProductExporter(TransactionCase):
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
        gid = "gid://shopify/Publication/" + str(next(iter(_service_module.PUBLICATION_CHANNELS.values())))
        publication = DummyPublication(gid)
        self.assertTrue(ProductExporter.is_published_on_channel(publication))
        publication.id = "gid://shopify/Publication/999"
        self.assertFalse(ProductExporter.is_published_on_channel(publication))

    def test_is_published_on_all_channels(self) -> None:
        values = list(_service_module.PUBLICATION_CHANNELS.values())
        channels = [DummyPublication(f"gid://shopify/Publication/{v}") for v in values]
        self.assertTrue(self.exporter.is_published_on_all_channels(channels))
        channels.append(DummyPublication("gid://shopify/Publication/999"))
        self.assertFalse(self.exporter.is_published_on_all_channels(channels))

    def test_publish_product(self) -> None:
        self.env["ir.config_parameter"].sudo().set_param("shopify.test_store", "")
        self.exporter.service._client = MagicMock()
        self.exporter._publish_product("gid")
        self.exporter.service.client.update_publications.assert_called_once()
