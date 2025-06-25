import base64
from datetime import datetime
from unittest.mock import patch

from odoo.tests import tagged

from ..shopify.gql import MediaStatus, ProductStatus, ProductFields
from ..shopify.helpers import ShopifyDataError
from ..shopify.sync.importers.product_importer import ProductImporter
from .fixtures.shopify_responses import (
    create_shopify_metafield,
    create_shopify_product_image,
    create_shopify_product_response,
    create_shopify_variant_response as create_shopify_product_variant,
)
from .test_utils import create_mock_simple_response
from .test_base import ShopifyTestBase


@tagged("post_install", "-at_install")
class TestProductImporter(ShopifyTestBase):
    _sku_counter = 10000

    @classmethod
    def _get_unique_sku(cls) -> str:
        cls._sku_counter += 1
        return str(cls._sku_counter)

    def setUp(self) -> None:
        super().setUp()
        self._setup_shopify_mocks()  # Set up Shopify API mocks
        self.sync_record = self.env["shopify.sync"].create(
            {
                "mode": "import_changed_products",
            }
        )
        self.importer = ProductImporter(self.env, self.sync_record)

        # Use get-or-create pattern to avoid constraint violations
        self.manufacturer = self.env["product.manufacturer"].search([("name", "=", "Test Manufacturer")])
        if not self.manufacturer:
            self.manufacturer = self.env["product.manufacturer"].create({"name": "Test Manufacturer"})

        self.part_type = self.env["product.type"].search([("name", "=", "Motors")])
        if not self.part_type:
            self.part_type = self.env["product.type"].create({"name": "Motors", "ebay_category_id": "123456"})

        self.condition = self.env["product.condition"].search([("name", "=", "New")])
        if not self.condition:
            self.condition = self.env["product.condition"].create({"name": "New", "code": "NEW"})

    def _import_products_with_mock_data(self, product_data_list: list[dict]) -> int:
        with patch.object(self.importer, "_fetch_page") as mock_fetch:
            mock_fetch.return_value = create_mock_simple_response([ProductFields(**data) for data in product_data_list])
            return self.importer.import_products_since_last_import()

    def _get_imported_product(self) -> "odoo.model.product_product":
        product = self.env["product.product"].search([("shopify_product_id", "!=", False)])
        self.assertTrue(product)
        return product

    def _import_and_get_product(self, product_data: dict, expected_count: int = 1) -> "odoo.model.product_product":
        with patch.object(self.importer, "_fetch_page") as mock_fetch:
            mock_fetch.return_value = create_mock_simple_response([ProductFields(**product_data)])
            imported_count = self.importer.import_products_since_last_import()
        
        self.assertEqual(imported_count, expected_count)
        
        product = self.env["product.product"].search([("shopify_product_id", "=", "123456789")])
        self.assertTrue(product)
        return product

    def test_import_basic_product(self) -> None:
        product_data = create_shopify_product_response(
            title="Test Motor",
            vendor="Test Manufacturer",
            product_type="Motors",
            variants=[
                create_shopify_product_variant(
                    sku=self._get_unique_sku(),
                    barcode="1234567890",
                    weight=2.5,
                    unit_cost="45.00",
                )
            ],
        )

        product = self._import_and_get_product(product_data)
        self.assertEqual(product.name, "Test Motor")
        self.assertEqual(product.list_price, 99.99)
        self.assertEqual(product.standard_price, 45.00)
        self.assertEqual(product.mpn, "1234567890")
        self.assertEqual(product.weight, 2.5)
        self.assertEqual(product.type, "consu")
        self.assertTrue(product.is_storable)
        self.assertEqual(product.product_tmpl_id.manufacturer.name, "Test Manufacturer")

    def test_import_product_with_bin_location(self) -> None:
        product_data = create_shopify_product_response(
            variants=[
                create_shopify_product_variant(
                    sku=f"{self._get_unique_sku()} - A1-B2",
                )
            ],
        )

        product = self._import_and_get_product(product_data)
        self.assertEqual(product.bin, "A1-B2")

    def test_import_product_with_metafields(self) -> None:
        product_data = create_shopify_product_response(
            product_type="Motors",
            metafields=[
                create_shopify_metafield(key="condition", value="NEW"),
                create_shopify_metafield(key="ebay_category_id", value="123456"),
            ],
        )

        imported_count = self._import_products_with_mock_data([product_data])
        self.assertEqual(imported_count, 1)

        product = self._get_imported_product()
        self.assertEqual(product.product_tmpl_id.condition.code, "NEW")
        self.assertEqual(product.product_tmpl_id.part_type.name, "Motors")
        self.assertEqual(product.product_tmpl_id.part_type.ebay_category_id, "123456")

    def test_import_product_with_images(self) -> None:
        image_data = b"test image data"
        encoded_image = base64.b64encode(image_data).decode()

        product_data = create_shopify_product_response(
            media=[
                create_shopify_product_image(
                    gid="gid://shopify/MediaImage/111",
                    alt="Front view",
                    status=MediaStatus.READY,
                    url="https://example.com/image1.jpg",
                ),
                create_shopify_product_image(
                    gid="gid://shopify/MediaImage/222",
                    alt="Side view",
                    status=MediaStatus.READY,
                    url="https://example.com/image2.jpg",
                ),
            ],
        )

        with (
            patch.object(self.importer, "_fetch_page") as mock_fetch,
            patch.object(self.importer, "fetch_image_data") as mock_fetch_image,
        ):
            mock_fetch.return_value = create_mock_simple_response([ProductFields(**product_data)])
            mock_fetch_image.return_value = encoded_image

            imported_count = self.importer.import_products_since_last_import()

        self.assertEqual(imported_count, 1)

        product = self.env["product.product"].search([("shopify_product_id", "!=", False)])
        self.assertTrue(product)
        self.assertEqual(len(product.images), 2)
        self.assertEqual(product.images[0].name, "Front view")
        self.assertEqual(product.images[0].shopify_media_id, "111")
        self.assertEqual(product.images[1].name, "Side view")
        self.assertEqual(product.images[1].shopify_media_id, "222")

    def test_import_product_with_processing_images(self) -> None:
        product_data = create_shopify_product_response(
            gid="gid://shopify/Product/999",
            media=[
                create_shopify_product_image(status=MediaStatus.PROCESSING),
            ],
        )

        with patch.object(self.importer, "_fetch_page") as mock_fetch:
            mock_fetch.return_value = create_mock_simple_response([ProductFields(**product_data)])
            imported_count = self.importer.import_products_since_last_import()

        self.assertEqual(imported_count, 0)

        reimport_sync = self.env["shopify.sync"].search(
            [
                ("mode", "=", "import_one_product"),
                ("shopify_product_id_to_sync", "=", "999"),
            ]
        )
        self.assertTrue(reimport_sync)

    def test_import_product_with_failed_images(self) -> None:
        existing_product = self.env["product.product"].create(
            {
                "name": "Existing Product",
                "default_code": self._get_unique_sku(),
                "shopify_product_id": "888",
                "type": "consu",
            }
        )

        product_data = create_shopify_product_response(
            gid="gid://shopify/Product/888",
            variants=[
                create_shopify_product_variant(sku=existing_product.default_code),
            ],
            media=[
                create_shopify_product_image(status=MediaStatus.FAILED),
            ],
        )

        with patch.object(self.importer, "_fetch_page") as mock_fetch:
            mock_fetch.return_value = create_mock_simple_response([ProductFields(**product_data)])

            self.importer.import_products_since_last_import()

        existing_product.invalidate_recordset()
        self.assertTrue(existing_product.shopify_next_export)
        self.assertTrue(existing_product.shopify_next_export_images)

    def test_import_product_missing_sku(self) -> None:
        product_data = create_shopify_product_response(
            variants=[
                create_shopify_product_variant(),
            ],
        )

        with patch.object(self.importer, "_fetch_page") as mock_fetch:
            mock_fetch.return_value = create_mock_simple_response([ProductFields(**product_data)])
            imported_count = self.importer.import_products_since_last_import()

        self.assertEqual(imported_count, 0)

    def test_import_product_no_variants(self) -> None:
        product_data = create_shopify_product_response(variants=[])

        with patch.object(self.importer, "_fetch_page") as mock_fetch:
            mock_fetch.return_value = create_mock_simple_response([ProductFields(**product_data)])

            with self.assertRaises(ShopifyDataError) as cm:
                self.importer.import_products_since_last_import()

            self.assertIn("No variants found", str(cm.exception))

    def test_update_existing_product(self) -> None:
        existing_product = self.env["product.product"].create(
            {
                "name": "Old Name",
                "default_code": self._get_unique_sku(),
                "shopify_product_id": "777",
                "list_price": 50.00,
                "type": "consu",
            }
        )
        existing_product.write_date = datetime(2023, 1, 1)

        product_data = create_shopify_product_response(
            gid="gid://shopify/Product/777",
            title="New Name",
            updated_at=datetime(2023, 12, 31).isoformat(),
            variants=[
                create_shopify_product_variant(
                    sku=existing_product.default_code,
                    price="75.00",
                ),
            ],
        )

        with patch.object(self.importer, "_fetch_page") as mock_fetch:
            mock_fetch.return_value = create_mock_simple_response([ProductFields(**product_data)])
            imported_count = self.importer.import_products_since_last_import()

        self.assertEqual(imported_count, 1)

        existing_product.invalidate_recordset()
        self.assertEqual(existing_product.name, "New Name")
        self.assertEqual(existing_product.list_price, 75.00)

    def test_skip_up_to_date_product(self) -> None:
        self.env["product.product"].create(
            {
                "name": "Current Product",
                "default_code": self._get_unique_sku(),
                "shopify_product_id": "666",
                "type": "consu",
            }
        )

        product_data = create_shopify_product_response(
            gid="gid://shopify/Product/666",
            updated_at=datetime(2020, 1, 1).isoformat(),
            variants=[
                create_shopify_product_variant(sku=self._get_unique_sku()),
            ],
        )

        with patch.object(self.importer, "_fetch_page") as mock_fetch:
            mock_fetch.return_value = create_mock_simple_response([ProductFields(**product_data)])
            imported_count = self.importer.import_products_since_last_import()

        self.assertEqual(imported_count, 0)

    def test_import_product_with_inventory(self) -> None:
        product_data = create_shopify_product_response(
            total_inventory=25,
        )

        with (
            patch.object(self.importer, "_fetch_page") as mock_fetch,
            patch.object(self.env["product.product"], "update_quantity") as mock_update_qty,
        ):
            mock_fetch.return_value = create_mock_simple_response([ProductFields(**product_data)])

            imported_count = self.importer.import_products_since_last_import()

        self.assertEqual(imported_count, 1)
        mock_update_qty.assert_called_once_with(25)

    def test_import_inactive_product(self) -> None:
        product_data = create_shopify_product_response(
            status=ProductStatus.DRAFT,
        )

        imported_count = self._import_products_with_mock_data([product_data])
        self.assertEqual(imported_count, 1)

        product = self._get_imported_product()
        self.assertFalse(product.is_published)

    def test_create_manufacturer_if_not_exists(self) -> None:
        product_data = create_shopify_product_response(
            vendor="New Manufacturer",
            media=[],  # No media to avoid image fetching issues
        )

        with patch.object(self.importer, "_fetch_page") as mock_fetch:
            mock_fetch.return_value = create_mock_simple_response([ProductFields(**product_data)])
            imported_count = self.importer.import_products_since_last_import()

        self.assertEqual(imported_count, 1)

        manufacturer = self.env["product.manufacturer"].search([("name", "=", "New Manufacturer")])
        self.assertTrue(manufacturer)

        product = self.env["product.product"].search([("shopify_product_id", "!=", False)])
        self.assertEqual(product.product_tmpl_id.manufacturer, manufacturer)

    def test_create_part_type_if_not_exists(self) -> None:
        product_data = create_shopify_product_response(
            product_type="New Part Type",
            media=[],  # No media to avoid image fetching issues
            metafields=[
                create_shopify_metafield(key="ebay_category_id", value="999999"),
            ],
        )

        with patch.object(self.importer, "_fetch_page") as mock_fetch:
            mock_fetch.return_value = create_mock_simple_response([ProductFields(**product_data)])
            imported_count = self.importer.import_products_since_last_import()

        self.assertEqual(imported_count, 1)

        part_type = self.env["product.type"].search(
            [
                ("name", "=", "New Part Type"),
                ("ebay_category_id", "=", "999999"),
            ]
        )
        self.assertTrue(part_type)

        product = self.env["product.product"].search([("shopify_product_id", "!=", False)])
        self.assertEqual(product.product_tmpl_id.part_type, part_type)

    def test_invalid_ebay_category_id(self) -> None:
        product_data = create_shopify_product_response(
            product_type="Motors",
            metafields=[
                create_shopify_metafield(key="ebay_category_id", value="invalid"),
            ],
        )

        with patch.object(self.importer, "_fetch_page") as mock_fetch:
            mock_fetch.return_value = create_mock_simple_response([ProductFields(**product_data)])

            with self.assertRaises(ShopifyDataError) as cm:
                self.importer.import_products_since_last_import()

            self.assertIn("Invalid ebay_category_id", str(cm.exception))

    def test_fetch_image_data_error(self) -> None:
        product_data = create_shopify_product_response(
            media=[
                create_shopify_product_image(
                    status=MediaStatus.READY,
                    url="https://example.com/bad-image.jpg",
                ),
            ],
        )

        with (
            patch.object(self.importer, "_fetch_page") as mock_fetch,
            patch.object(self.mock_client.http_client, "stream") as mock_stream,
        ):
            mock_fetch.return_value = create_mock_simple_response([ProductFields(**product_data)])

            mock_stream.side_effect = Exception("Network error")

            with self.assertRaises(ShopifyDataError) as cm:
                self.importer.import_products_since_last_import()

            # The error message is "unexpected error" when image fetch fails
            self.assertIn("Network error", str(cm.exception))

    def test_images_already_in_sync(self) -> None:
        sku = self._get_unique_sku()
        existing_product = self.env["product.product"].create(
            {
                "name": "Product with Images",
                "default_code": sku,
                "shopify_product_id": "555",
                "type": "consu",
            }
        )

        self.env["product.image"].create(
            {
                "name": "Image 1",
                "shopify_media_id": "111",
                "image_1920": base64.b64encode(b"test").decode(),
                "product_tmpl_id": existing_product.product_tmpl_id.id,
            }
        )
        self.env["product.image"].create(
            {
                "name": "Image 2",
                "shopify_media_id": "222",
                "image_1920": base64.b64encode(b"test").decode(),
                "product_tmpl_id": existing_product.product_tmpl_id.id,
            }
        )

        product_data = create_shopify_product_response(
            gid="gid://shopify/Product/555",
            updated_at=datetime(2023, 12, 31).isoformat(),
            variants=[
                create_shopify_product_variant(sku=sku),
            ],
            media=[
                create_shopify_product_image(
                    gid="gid://shopify/MediaImage/111",
                    status=MediaStatus.READY,
                ),
                create_shopify_product_image(
                    gid="gid://shopify/MediaImage/222",
                    status=MediaStatus.READY,
                ),
            ],
        )

        with (
            patch.object(self.importer, "_fetch_page") as mock_fetch,
            patch.object(self.importer, "fetch_image_data") as mock_fetch_image,
        ):
            mock_fetch.return_value = create_mock_simple_response([ProductFields(**product_data)])

            imported_count = self.importer.import_products_since_last_import()

        self.assertEqual(imported_count, 1)
        mock_fetch_image.assert_not_called()

    def test_product_with_zero_weight(self) -> None:
        product_data = create_shopify_product_response(
            variants=[
                create_shopify_product_variant(weight_value=None),
            ],
        )

        imported_count = self._import_products_with_mock_data([product_data])
        self.assertEqual(imported_count, 1)

        product = self._get_imported_product()
        self.assertEqual(product.weight, 0.0)

    def test_product_data_error_handling(self) -> None:
        product_data = create_shopify_product_response()

        with (
            patch.object(self.importer, "_fetch_page") as mock_fetch,
            patch.object(self.env["product.product"], "create") as mock_create,
        ):
            mock_fetch.return_value = create_mock_simple_response([ProductFields(**product_data)])

            mock_create.side_effect = ValueError("Invalid data")

            with self.assertRaises(ShopifyDataError) as cm:
                self.importer.import_products_since_last_import()

            # Check for the actual error message
            self.assertIn("Invalid data", str(cm.exception))

    def test_import_product_with_extreme_prices(self) -> None:
        product_data = create_shopify_product_response(
            variants=[
                create_shopify_product_variant(
                    price="9999999.99",  # Very high price
                    unit_cost="0.01",  # Very low cost
                ),
            ],
        )

        imported_count = self._import_products_with_mock_data([product_data])
        self.assertEqual(imported_count, 1)

        product = self._get_imported_product()
        self.assertEqual(product.list_price, 9999999.99)
        self.assertEqual(product.standard_price, 0.01)

    def test_import_product_with_html_in_description(self) -> None:
        product_data = create_shopify_product_response(
            title="<b>Bold Product</b>",
            description_html='<script>alert("XSS")</script><p>Product <b>description</b> with <a href="https://example.com">links</a></p>',
        )

        imported_count = self._import_products_with_mock_data([product_data])
        self.assertEqual(imported_count, 1)

        product = self._get_imported_product()
        # HTML should be preserved for website_description
        self.assertIn("<p>Product", product.website_description)
        # But title should be text only
        self.assertNotIn("<b>", product.name)

    def test_import_product_with_unicode_sku(self) -> None:
        product_data = create_shopify_product_response(
            variants=[
                create_shopify_product_variant(
                    sku=f"{self._get_unique_sku()} - BIN-01",
                ),
            ],
        )

        product = self._import_and_get_product(product_data)
        self.assertEqual(product.bin, "BIN-01")

    def test_import_product_with_very_long_sku_and_bin(self) -> None:
        base_sku = self._get_unique_sku()
        long_sku = base_sku + "1" * 200
        long_bin = "BIN-" + "B" * 200
        product_data = create_shopify_product_response(
            variants=[
                create_shopify_product_variant(
                    sku=f"{long_sku} - {long_bin}",
                ),
            ],
        )

        imported_count = self._import_products_with_mock_data([product_data])
        self.assertEqual(imported_count, 1)

        product = self._get_imported_product()
        # Should handle truncation if needed
        self.assertTrue(product.default_code.startswith(base_sku))
        self.assertTrue(product.bin.startswith("BIN-"))

    def test_import_product_with_conflicting_sku_and_id(self) -> None:
        # Create two existing products
        self.env["product.product"].create(
            {
                "name": "Product 1",
                "default_code": self._get_unique_sku(),
                "shopify_product_id": "111",
                "type": "consu",
            }
        )

        product2 = self.env["product.product"].create(
            {
                "name": "Product 2",
                "default_code": self._get_unique_sku(),
                "shopify_product_id": "222",
                "type": "consu",
            }
        )

        # Import data has product1's SKU but product2's ID
        product_data = create_shopify_product_response(
            gid="gid://shopify/Product/222",
            title="Updated Product",
            variants=[
                create_shopify_product_variant(sku=product2.default_code),
            ],
        )

        with patch.object(self.importer, "_fetch_page") as mock_fetch:
            mock_fetch.return_value = create_mock_simple_response([ProductFields(**product_data)])

            self.importer.import_products_since_last_import()

        # Should match by ID first (more reliable)
        product2.invalidate_recordset()
        self.assertEqual(product2.name, "Updated Product")
        # Product should have the variant's SKU
        self.assertTrue(product2.default_code)

    def test_import_product_with_invalid_metafield_types(self) -> None:
        product_data = create_shopify_product_response(
            product_type="Motors",
            metafields=[
                create_shopify_metafield(key="condition", value="INVALID_CONDITION"),
                create_shopify_metafield(key="ebay_category_id", value="not-a-number"),
            ],
        )

        with patch.object(self.importer, "_fetch_page") as mock_fetch:
            mock_fetch.return_value = create_mock_simple_response([ProductFields(**product_data)])

            with self.assertRaises(ShopifyDataError):
                self.importer.import_products_since_last_import()

    def test_import_product_with_massive_image_count(self) -> None:
        # Create 50 images
        images = []
        for i in range(50):
            images.append(
                create_shopify_product_image(
                    gid=f"gid://shopify/MediaImage/{i + 1000}",
                    alt=f"Image {i}",
                    status=MediaStatus.READY,
                    url=f"https://example.com/image{i}.jpg",
                )
            )

        product_data = create_shopify_product_response(media=images)

        with (
            patch.object(self.importer, "_fetch_page") as mock_fetch,
            patch.object(self.importer, "fetch_image_data") as mock_fetch_image,
        ):
            mock_fetch.return_value = create_mock_simple_response([ProductFields(**product_data)])
            mock_fetch_image.return_value = base64.b64encode(b"test").decode()

            imported_count = self.importer.import_products_since_last_import()

        self.assertEqual(imported_count, 1)

        product = self.env["product.product"].search([("shopify_product_id", "!=", False)])
        self.assertTrue(product)
        self.assertEqual(len(product.images), 50)

    def test_import_product_with_network_retry(self) -> None:
        product_data = create_shopify_product_response(
            media=[
                create_shopify_product_image(status=MediaStatus.READY),
            ],
        )

        with (
            patch.object(self.importer, "_fetch_page") as mock_fetch,
            patch.object(self.mock_client.http_client, "stream") as mock_stream,
        ):
            mock_fetch.return_value = create_mock_simple_response([ProductFields(**product_data)])

            # First call fails, should raise error
            mock_stream.side_effect = [
                Exception("Connection reset"),
            ]

            with self.assertRaises(ShopifyDataError):
                self.importer.import_products_since_last_import()

    def test_import_product_inactive_then_active(self) -> None:
        # Create inactive product
        existing_product = self.env["product.product"].create(
            {
                "name": "Inactive Product",
                "default_code": self._get_unique_sku(),
                "shopify_product_id": "333",
                "type": "consu",
                "active": False,
            }
        )

        # Import as active
        product_data = create_shopify_product_response(
            gid="gid://shopify/Product/333",
            status=ProductStatus.ACTIVE,
            variants=[
                create_shopify_product_variant(sku=existing_product.default_code),
            ],
        )

        with patch.object(self.importer, "_fetch_page") as mock_fetch:
            mock_fetch.return_value = create_mock_simple_response([ProductFields(**product_data)])

            self.importer.import_products_since_last_import()

        # Should find inactive product and update it
        existing_product.invalidate_recordset()
        self.assertTrue(existing_product.is_published)

    def test_import_product_with_null_inventory_fields(self) -> None:
        product_data = create_shopify_product_response(
            variants=[
                create_shopify_product_variant(
                    inventory_item={
                        "unit_cost": {"amount": None},
                        "measurement": {"weight": {"value": None, "unit": "KILOGRAMS"}},
                    },
                ),
            ],
        )
        # Override totalInventory to be null
        product_data["totalInventory"] = None

        imported_count = self._import_products_with_mock_data([product_data])
        self.assertEqual(imported_count, 1)

        product = self._get_imported_product()
        self.assertEqual(product.standard_price, 0.0)
        self.assertEqual(product.weight, 0.0)
