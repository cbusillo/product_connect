import logging
from base64 import b64encode
from datetime import datetime
from typing import Optional

from odoo.api import Environment

from .shopify_client import GetProductsProductsEdges, GetProductsProductsEdgesNode
from .shopify_service import ShopifyService
from ..utils.shopify_helpers import (
    DEFAULT_DATETIME,
    OdooDataError,
    ShopifyDataError,
    ShopifyMissingSkuFieldError,
    current_utc_time,
    determine_latest_product_modification_time,
    format_shopify_gid_from_id,
    format_datetime_for_shopify,
    parse_shopify_id_from_gid,
    parse_shopify_sku_field_to_sku_and_bin,
    parse_shopify_datetime_to_utc,
)

_logger = logging.getLogger(__name__)


class ProductImporter:
    SHOPIFY_PAGE_SIZE = 250

    def __init__(self, env: Environment) -> None:
        self.env = env
        self.shopify_service = ShopifyService(env)
        self.page_size = self.SHOPIFY_PAGE_SIZE

    def set_last_import_time(self, current_datetime: datetime) -> None:
        formatted_datetime = format_datetime_for_shopify(current_datetime)
        self.env["ir.config_parameter"].sudo().set_param("shopify.last_import_time", formatted_datetime)
        _logger.info("Updated last sync time to %s", formatted_datetime)

    def get_last_import_time(self) -> str:
        last_sync_time = self.env["ir.config_parameter"].sudo().get_param("shopify.last_import_time")
        if not last_sync_time:
            _logger.warning("No last import time found. Returning default datetime.")
            return format_datetime_for_shopify(DEFAULT_DATETIME)
        return last_sync_time

    def import_products_since_last_import(self) -> tuple[int, int]:
        last_import_time = self.get_last_import_time()
        current_import_start_time = current_utc_time()
        if not last_import_time:
            _logger.warning("No last import time found. Importing all products.")
        _logger.info(f"Importing products since last import time: {last_import_time}")

        filter_query = f'updated_at:>"{last_import_time}"'
        _logger.debug(f"Filter query for products: {filter_query}")
        updated_count, total_count = self.import_products_from_query(query=filter_query)

        self.set_last_import_time(current_import_start_time)

        return updated_count, total_count

    def import_products_from_query(self, query: str | None = None) -> tuple[int, int]:
        updated_count = 0
        total_count = 0

        client = self.shopify_service.client
        cursor = None
        has_next_page = True

        while has_next_page:
            products_page = client.get_products(query=query, cursor=cursor, limit=self.page_size)
            product_edges = products_page.products.edges
            if not product_edges:
                _logger.debug("No more products to import.")
                break
            try:
                with self.env.cr.savepoint():
                    page_updated_count = self.import_products(product_edges)
            except (ShopifyDataError, OdooDataError, AttributeError) as error:
                _logger.error(f"Error importing products: {error}")
                self.env["notification.manager.mixin"].notify_channel(
                    f"Imported {updated_count} product(s) with error", str(error), "shopify_sync"
                )
                self.env.cr.commit()
                raise error
            updated_count += page_updated_count
            total_count += len(product_edges)

            cursor = products_page.products.page_info.end_cursor
            has_next_page = products_page.products.page_info.has_next_page

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

    def import_products(self, shopify_product_edges: list[GetProductsProductsEdges]) -> int:
        product_index = 0
        updated_count = 0
        for edge in shopify_product_edges:
            shopify_product = edge.node
            _logger.debug(
                f"Importing product index {product_index}.  Imported {updated_count} of {len(shopify_product_edges)} on this page: {shopify_product.id} {shopify_product.title}"
            )

            if self.import_product(shopify_product):
                updated_count += 1
            product_index += 1

        return updated_count

    def import_product(self, shopify_product: GetProductsProductsEdgesNode) -> bool:
        if not shopify_product.variants or not shopify_product.variants.edges:
            raise ShopifyDataError(f"No variants found for product {shopify_product.id} {shopify_product.title}")

        variant = shopify_product.variants.edges[0].node

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
                last_import_time = parse_shopify_datetime_to_utc(self.get_last_import_time())
                latest_write_date = determine_latest_product_modification_time(odoo_product, last_import_time)
                if parse_shopify_datetime_to_utc(shopify_product.updated_at) > latest_write_date:
                    _logger.debug(f"Updating existing product {odoo_product.id} from Shopify")
                    odoo_product = self.save_odoo_product(odoo_product, shopify_product)
                    return True
                _logger.debug(f"Product {odoo_product.id} is up to date with Shopify")
                return False
            else:
                _logger.debug(f"Creating new product {shopify_product.id} from Shopify")
                odoo_product = self.save_odoo_product(None, shopify_product)
                return True

        except ValueError as error:
            raise OdooDataError(f"Failed to update odoo product from shopify with id {shopify_product.id}\n{error}", odoo_product)

    def fetch_image_data(self, image_url: str) -> bytes:
        client = self.shopify_service.client.http_client
        response = client.get(image_url)
        response.raise_for_status()
        image_base64 = b64encode(response.content)
        return image_base64

    def get_or_create_manufacturer(self, manufacturer_name: str) -> "odoo.model.product_manufacturer":
        manufacturer = self.env["product.manufacturer"].search([("name", "=", manufacturer_name)], limit=1)
        if not manufacturer:
            manufacturer = self.env["product.manufacturer"].create({"name": manufacturer_name})
        return manufacturer

    def get_or_create_part_type(self, part_type_name: str, ebay_category_id: str) -> "odoo.model.product_type":
        if int(ebay_category_id) < 1 or not part_type_name:
            raise ShopifyDataError(f"Invalid ebay_category_id {ebay_category_id} or part_type_name {part_type_name}")
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
        self, odoo_product: "odoo.model.product_product", shopify_product: GetProductsProductsEdgesNode
    ) -> None:
        image_edges = shopify_product.media.edges
        if not image_edges:
            raise ShopifyDataError(f"No images found for product {shopify_product.id} {shopify_product.title}")

        if odoo_product.images:
            return None

        for image_edge in image_edges:
            image = image_edge.node
            image_url = image.preview.image.url
            if not image_url:
                raise ShopifyDataError(f"No image URL found for product {shopify_product.id} {shopify_product.title}")
            image_name = image.alt
            image_base64 = self.fetch_image_data(image_url)
            odoo_product.images += self.env["product.image"].create({"name": image_name, "image_1920": image_base64})

    def save_odoo_product(
        self, odoo_product: Optional["odoo.model.product_product"], shopify_product: GetProductsProductsEdgesNode
    ) -> "odoo.model.product_product":
        variant = shopify_product.variants.edges[0].node
        sku, bin_location = parse_shopify_sku_field_to_sku_and_bin(variant.sku or "")
        metafields_by_key = {edge.node.key: edge.node for edge in shopify_product.metafields.edges}

        try:
            odoo_product_input: "odoo.values.product_product" = {
                "shopify_product_id": parse_shopify_id_from_gid(shopify_product.id),
                "shopify_variant_id": parse_shopify_id_from_gid(variant.id),
                "shopify_created_at": parse_shopify_datetime_to_utc(shopify_product.created_at),
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
                self.import_images_from_shopify(odoo_product, shopify_product)

            if shopify_product.total_inventory is not None:
                odoo_product.update_quantity(shopify_product.total_inventory)

            return odoo_product

        except (ValueError, TypeError, AttributeError) as error:
            raise OdooDataError(f"Failed to create odoo product from shopify with id {shopify_product.id}\n{error}", odoo_product)
