import logging
from base64 import b64encode
from datetime import datetime, timedelta
from typing import Optional

from httpx import HTTPError
from odoo.api import Environment
from pydantic import AnyUrl

from odoo.addons.product_connect.utils.shopify_helpers import format_datetime_for_shopify
from .shopify_client import (
    MediaStatus,
    GetProductsProductsNodes,
    GetProductsProductsNodesMediaNodesMediaImage,
)
from .shopify_service import ShopifyService
from ..utils.shopify_helpers import (
    DEFAULT_DATETIME,
    IMAGE_ORDER_KEY,
    SHOPIFY_PAGE_SIZE,
    OdooDataError,
    ShopifyDataError,
    ShopifyMissingSkuFieldError,
    determine_latest_odoo_product_modification_time,
    format_shopify_gid_from_id,
    parse_shopify_id_from_gid,
    parse_shopify_sku_field_to_sku_and_bin,
)

_logger = logging.getLogger(__name__)


class ProductImporter:

    def __init__(self, env: Environment) -> None:
        self.env = env
        self.shopify_service = ShopifyService(env)
        self.page_size = SHOPIFY_PAGE_SIZE

    def get_last_import_time(self) -> datetime:
        newest_imported_product = self.env["product.product"].read_group(
            [("shopify_last_imported_at", "!=", False)],
            ["shopify_last_imported_at:max"],
            [],
        )

        if not newest_imported_product:
            _logger.debug("No products imported yet.")
            return DEFAULT_DATETIME

        return newest_imported_product[0]["shopify_last_imported_at"]

    def import_products_since_last_import(self) -> tuple[int, int]:
        last_import_time = self.get_last_import_time() - timedelta(seconds=1)
        _logger.info(f"Importing products since last import time: {last_import_time}")

        filter_query = f'updated_at:>"{format_datetime_for_shopify(last_import_time)}"'
        _logger.debug(f"Filter query for products: {filter_query}")
        updated_count, total_count = self.import_products_from_query(query=filter_query)

        return updated_count, total_count

    def import_products_from_query(self, query: str | None = None) -> tuple[int, int]:
        updated_count = 0
        total_count = 0

        client = self.shopify_service.client
        cursor = None
        has_next_page = True

        while has_next_page:
            products_page = client.get_products(query=query, cursor=cursor, limit=self.page_size)
            products = products_page.nodes
            if not products:
                _logger.debug("No more products to import.")
                break
            try:
                page_updated_count = self.import_products(products)
            except (ShopifyDataError, OdooDataError, AttributeError) as error:
                _logger.error(f"Error importing products: {error}")
                self.env["notification.manager.mixin"].notify_channel(
                    f"Imported {updated_count} product(s) with error", str(error), "shopify_sync"
                )
                raise error

            updated_count += page_updated_count
            total_count += len(products)

            cursor = products_page.page_info.end_cursor
            has_next_page = products_page.page_info.has_next_page

        _logger.debug(f"Finished importing product query: {updated_count} imported, {total_count} total")
        return updated_count, total_count

    def import_product_by_id(self, shopify_product_id: str) -> bool:
        _logger.info(f"Importing product by ID: {shopify_product_id}")

        product_gid = format_shopify_gid_from_id("Product", shopify_product_id)

        filter_query = f'id:"{product_gid}"'
        updated_count, _total_count = self.import_products_from_query(query=filter_query)

        if not updated_count:
            _logger.warning(f"Failed to import product with ID: {shopify_product_id}")
            return False

        _logger.info(f"Successfully imported product with ID: {shopify_product_id}")
        return True

    def import_products(self, products: list[GetProductsProductsNodes]) -> int:
        updated_count = 0
        for product_index, product in enumerate(products):
            _logger.debug(
                f"Importing product index {product_index}.  Imported {updated_count} of {len(products)} on this page: {product.id} {product.title}"
            )

            product_index += 1
            if self.import_product(product):
                updated_count += 1

        self.env.cr.commit()
        return updated_count

    def import_product(self, shopify_product: GetProductsProductsNodes) -> bool:
        if not shopify_product.variants or not shopify_product.variants.nodes:
            raise ShopifyDataError(f"No variants found for product {shopify_product.id} {shopify_product.title}")

        variant = shopify_product.variants.nodes[0]

        try:
            shopify_sku, _bin_location = parse_shopify_sku_field_to_sku_and_bin(variant.sku)
        except ShopifyMissingSkuFieldError:
            _logger.warning(f"Missing SKU for product {shopify_product.id} {shopify_product.title}")
            return False

        odoo_product = self.env["product.product"].search(
            [
                "|",
                ("shopify_product_id", "=", parse_shopify_id_from_gid(shopify_product.id)),
                ("default_code", "=", shopify_sku),
                ("active", "in", [True, False]),
            ],
            limit=1,
        )
        try:
            if odoo_product:
                latest_write_date = determine_latest_odoo_product_modification_time(odoo_product)
                images = shopify_product.media.nodes
                has_unready_media = any(image.status in (MediaStatus.FAILED, MediaStatus.PROCESSING) for image in images)
                if has_unready_media:
                    _logger.debug(f"Product {odoo_product.id} has media not yet ready. Flagging for re‑import.")
                    odoo_product.shopify_next_export = True
                    odoo_product.shopify_next_export_images = True

                if shopify_product.updated_at > latest_write_date:
                    _logger.debug(f"Updating existing product {odoo_product.id} from Shopify")
                    odoo_product = self.save_odoo_product(odoo_product, shopify_product)
                    return True
                _logger.debug(f"Product {odoo_product.id} is up to date with Shopify")
                odoo_product.shopify_last_imported_at = shopify_product.updated_at
                return False
            else:
                _logger.debug(f"Creating new product {shopify_product.id} from Shopify")
                odoo_product = self.save_odoo_product(None, shopify_product)
                return True

        except ValueError as error:
            raise OdooDataError(f"Failed to update odoo product from shopify with id {shopify_product.id}\n{error}", odoo_product)

    def _images_are_in_sync(
        self, odoo_product: "odoo.model.product_product", shopify_images: list[GetProductsProductsNodesMediaNodesMediaImage]
    ) -> bool:
        return self._ordered_odoo_media_ids(odoo_product) == self._ordered_shopify_media_ids(shopify_images)

    def get_or_create_manufacturer(self, manufacturer_name: str) -> "odoo.model.product_manufacturer":
        manufacturer = self.env["product.manufacturer"].search([("name", "=", manufacturer_name)], limit=1)
        if not manufacturer:
            manufacturer = self.env["product.manufacturer"].create({"name": manufacturer_name})
        return manufacturer

    def get_or_create_part_type(self, part_type_name: str, ebay_category_id: str) -> "odoo.model.product_type":
        if not ebay_category_id or not ebay_category_id.isdigit() or ebay_category_id == "0":
            raise ShopifyDataError(f"Invalid ebay_category_id {ebay_category_id}")

        if not part_type_name:
            raise ShopifyDataError(f"Invalid part_type_name {part_type_name}")
        part_type = self.env["product.type"].search(
            [
                ("name", "=", part_type_name),
                ("ebay_category_id", "=", ebay_category_id),
            ],
            limit=1,
        )
        if not part_type:
            part_type = self.env["product.type"].create({"name": part_type_name, "ebay_category_id": ebay_category_id})

        return part_type

    def import_images_from_shopify(
        self, odoo_product: "odoo.model.product_product", shopify_product: GetProductsProductsNodes
    ) -> None:
        shopify_images = [image for image in shopify_product.media.nodes if image.status == MediaStatus.READY]
        if not shopify_images:
            _logger.debug(f"No images to import for product {shopify_product.id} {shopify_product.title}")
            return

        if self._images_are_in_sync(odoo_product, shopify_images):
            _logger.debug("Images already in sync for product %s", odoo_product.id)
            return

        existing_by_mid = {image.shopify_media_id: image for image in odoo_product.images if image.shopify_media_id}
        ordered_images = []

        for shopify_image in shopify_images:
            media_id = parse_shopify_id_from_gid(shopify_image.id)
            image = existing_by_mid.get(media_id)
            if image:
                if shopify_image.alt and image.name != shopify_image.alt:
                    image.name = shopify_image.alt
            else:
                preview_url = shopify_image.preview.image.url
                if not preview_url:
                    raise ShopifyDataError(f"No image URL for product {shopify_product.id} {shopify_product.title}")
                image = self.env["product.image"].create(
                    {
                        "name": shopify_image.alt or shopify_product.title,
                        "image_1920": self.fetch_image_data(preview_url),
                        "shopify_media_id": media_id,
                    }
                )
            ordered_images.append(image)

        odoo_product.images = [(6, 0, [image.id for image in ordered_images])]

        for sequence, image in enumerate(ordered_images):
            image.sequence = sequence

    def fetch_image_data(self, image_url: AnyUrl) -> bytes:
        client = self.shopify_service.client.http_client
        response = client.get(str(image_url))
        response.raise_for_status()
        try:
            return b64encode(response.content)
        except HTTPError as error:
            raise ShopifyDataError(f"Failed to fetch image data from {image_url}: {error}")

    @staticmethod
    def _ordered_odoo_media_ids(product: "odoo.model.product_product") -> list[str]:
        ordered_images = sorted(product.images, key=IMAGE_ORDER_KEY)
        return [image.shopify_media_id for image in ordered_images if image.shopify_media_id]

    @staticmethod
    def _ordered_shopify_media_ids(shopify_images: list[GetProductsProductsNodesMediaNodesMediaImage]) -> list[str]:
        return [parse_shopify_id_from_gid(image.id) for image in shopify_images]

    def _sync_images_bidirectional(
        self, odoo_product: "odoo.model.product_product", shopify_product: GetProductsProductsNodes
    ) -> None:
        self.import_images_from_shopify(odoo_product, shopify_product)

    def save_odoo_product(
        self, odoo_product: Optional["odoo.model.product_product"], shopify_product: GetProductsProductsNodes
    ) -> "odoo.model.product_product":
        variant = shopify_product.variants.nodes[0]
        sku, bin_location = parse_shopify_sku_field_to_sku_and_bin(variant.sku or "")
        metafields = shopify_product.metafields.nodes
        metafields_by_key = {mf.key: mf for mf in metafields}

        try:
            odoo_product_input: "odoo.values.product_product" = {
                "shopify_product_id": parse_shopify_id_from_gid(shopify_product.id),
                "shopify_variant_id": parse_shopify_id_from_gid(variant.id),
                "shopify_created_at": shopify_product.created_at,
                "name": shopify_product.title,
                "default_code": sku,
                "website_description": shopify_product.description_html,
                "list_price": float(variant.price),
                "standard_price": float(variant.inventory_item.unit_cost.amount),
                "mpn": variant.barcode,
                "bin": bin_location,
                "weight": float(variant.inventory_item.measurement.weight.value),
                "type": "consu",
                "is_storable": True,
                "manufacturer": self.get_or_create_manufacturer(shopify_product.vendor).id,
                "is_published": shopify_product.status.lower() == "active",
                "is_ready_for_sale": True,
                "shopify_last_imported_at": shopify_product.updated_at,
            }

            if odoo_product:
                odoo_product_input["id"] = odoo_product.id

            condition = metafields_by_key.get("condition")
            if condition:
                if self.env["product.condition"].search([("code", "=", condition.value)], limit=1):
                    odoo_product_input["condition"] = self.env["product.condition"].search(
                        [("code", "=", condition.value)], limit=1
                    )

            ebay_category_from_shopify = metafields_by_key.get("ebay_category_id")
            if ebay_category_from_shopify:
                odoo_product_input["shopify_ebay_category_id"] = parse_shopify_id_from_gid(ebay_category_from_shopify.id)
                odoo_product_input["part_type"] = self.get_or_create_part_type(
                    shopify_product.product_type, ebay_category_from_shopify.value
                ).id

            if odoo_product:
                odoo_product.write(odoo_product_input)
            else:
                odoo_product = self.env["product.product"].create(odoo_product_input)

            self._sync_images_bidirectional(odoo_product, shopify_product)
            if shopify_product.total_inventory is not None:
                odoo_product.update_quantity(shopify_product.total_inventory)

            return odoo_product

        except (ValueError, TypeError, AttributeError) as error:
            raise OdooDataError(f"Failed to create odoo product from shopify with id {shopify_product.id}\n{error}", odoo_product)
