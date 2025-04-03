import base64
import json
import logging
import math
from pathlib import Path

import requests
import shopify
import time
from datetime import datetime
from dateutil.parser import parse
from odoo import fields, models, api
from odoo.exceptions import UserError
from requests.exceptions import RequestException
from typing import Any, Optional
from urllib.error import HTTPError
from zoneinfo import ZoneInfo

MAX_RETRIES = 5
MIN_SHOPIFY_REMAINING_API_POINTS = 500
MIN_RETRY_DELAY = 5
MAX_RETRY_DELAY = 60
_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)  # TODO: Remove this line in production

UTC = ZoneInfo("UTC")


class IncompleteDataError(UserError):
    pass


def parse_to_utc(date_str: str) -> datetime:
    return parse(date_str).astimezone(UTC)


def current_utc_time() -> datetime:
    return datetime.now(UTC)


def apply_rate_limit_patch_to_shopify_execute() -> None:
    original_execute = shopify.GraphQL.execute  # store original method

    class ThrottledError(Exception):
        pass

    def parse_and_raise_error(error_data: dict[str, Any]) -> None:
        error_code = error_data.get("extensions", {}).get("code")
        error_message = error_data.get("message", "Unknown error")
        if error_code == "THROTTLED":
            _logger.debug("Throttled by Shopify: %s", error_message)
            raise ThrottledError("Throttled by Shopify")
        else:
            _logger.error("Error from Shopify: %s", error_message)
            raise Exception("Error from Shopify")

    def delay_if_near_rate_limit(response_json: dict[str, Any]) -> None:
        throttle_status = response_json.get("extensions", {}).get("cost", {}).get("throttleStatus", {})
        currently_available = throttle_status.get("currentlyAvailable")
        restore_rate = throttle_status.get("restoreRate")
        if (
            currently_available is not None
            and restore_rate is not None
            and currently_available < MIN_SHOPIFY_REMAINING_API_POINTS
        ):
            sleep_time = (MIN_SHOPIFY_REMAINING_API_POINTS - currently_available) / restore_rate
            _logger.debug(
                "Shopify API limit reached. Sleeping for %s seconds. Currently available: %s, Restore rate: %s",
                sleep_time,
                currently_available,
                restore_rate,
            )

            time.sleep(sleep_time)

    def handle_and_retry_on_error(error: HTTPError, attempt: int) -> None:
        if isinstance(error, ThrottledError):
            retry_after = min(2**attempt, MAX_RETRY_DELAY)
        elif isinstance(error, HTTPError):
            retry_after = max(float(error.headers.get("Retry-After", 4)), min(attempt * 2, MAX_RETRY_DELAY))
        else:
            raise RuntimeError(f"Unexpected error: {error}")
        _logger.debug("Exceeded Shopify API limit. Retrying in %s seconds", retry_after)
        time.sleep(retry_after)

    def rate_limited_execute(self: Any, *args: Any, **kwargs: Any) -> str:
        for attempt in range(MAX_RETRIES):
            try:
                response = original_execute(self, *args, **kwargs)
                response_json = json.loads(response)
                if "errors" in response_json:
                    for error in response_json.get("errors", []):
                        parse_and_raise_error(error)
                delay_if_near_rate_limit(response_json)
                return response
            except HTTPError as error:
                handle_and_retry_on_error(error, attempt)
        raise RuntimeError(f"Failed after {MAX_RETRIES} attempts")

    shopify.GraphQL.execute = rate_limited_execute


apply_rate_limit_patch_to_shopify_execute()


class ShopifySync(models.AbstractModel):
    _name = "shopify.sync"
    _description = "Shopify Sync"
    _inherit = "notification.manager.mixin"

    COMMIT_AFTER = 100

    def now_in_localtime_formatted(self) -> str:
        user_timezone = ZoneInfo(self.env.user.tz or "UTC")
        current_time = datetime.now(user_timezone)
        return current_time.strftime("%Y-%m-%d %I:%M:%S %p")

    @staticmethod
    def extract_id_from_gid(gid: str) -> int:
        return int(gid.split("/")[-1])

    @staticmethod
    def convert_to_shopify_gid_static(resource_type: str, resource_id: str) -> str:
        return f"gid://shopify/{resource_type}/{resource_id}"

    @staticmethod
    def extract_sku_bin_from_shopify_product(shopify_product: dict[str, Any]) -> tuple[str, str]:
        variant_edges = shopify_product.get("variants", {}).get("edges", [])
        if not variant_edges:
            _logger.warning("No variants found for product: %s", shopify_product.get("id"))
            return "", ""
        product_variant = variant_edges[0].get("node", {})
        sku_field = product_variant.get("sku", "") or ""
        parts = [v.strip() for v in sku_field.split(" - ")]
        if not parts:
            _logger.warning("Unexpected SKU format for product: %s", shopify_product.get("id"))
            return "", ""
        sku = parts[0]
        bin_location = parts[1] if len(parts) > 1 else ""
        return sku, bin_location

    @api.model
    def initialize_shopify_session(self) -> None:
        shop_url = self.env["ir.config_parameter"].sudo().get_param("shopify.shop_url_key")
        token = self.env["ir.config_parameter"].sudo().get_param("shopify.api_token")
        api_version = self.env["ir.config_parameter"].sudo().get_param("shopify.api_version")
        shopify_session = shopify.Session(f"{shop_url}.myshopify.com", token=token, version=api_version)
        shopify.ShopifyResource.activate_session(shopify_session)

    @api.model
    def sync_with_shopify(self) -> None:
        self.initialize_shopify_session()
        try:
            self.import_from_shopify()
        except IncompleteDataError as error:
            _logger.warning("Shopify import failed.  Likely due to incomplete export.  Ignore unless recurring: %s", error)
        self.export_to_shopify()

    @api.model
    def fetch_import_timestamps(self) -> tuple[str, datetime, datetime]:
        last_import_time_str = str(self.env["ir.config_parameter"].sudo().get_param("shopify.last_import_time"))
        current_import_start_time = current_utc_time()
        last_import_time = parse_to_utc(last_import_time_str)
        return last_import_time_str, current_import_start_time, last_import_time

    @api.model
    def import_from_shopify(self) -> None:
        _logger.debug("Starting import from Shopify.")
        last_import_time_str, current_import_start_time, last_import_time = self.fetch_import_timestamps()
        graphql_query_path = Path(__file__).parent.parent / "graphql" / "shopify_product.graphql"
        graphql_document = graphql_query_path.read_text()
        graphql_client = shopify.GraphQL()
        helper = ShopifyGraphQLHelper(graphql_client, graphql_document)
        import_service = ShopifyImportService(self.env, helper)
        updated_count, total_count = import_service.import_products(last_import_time_str)
        self.env.cr.commit()
        last_import_time_commit = current_import_start_time.isoformat(timespec="seconds").replace("+00:00", "Z")
        self.env["ir.config_parameter"].sudo().set_param("shopify.last_import_time", last_import_time_commit)
        self.env.cr.commit()
        message = (
            f"Shopify imported {updated_count} out of {total_count} items successfully at {self.now_in_localtime_formatted()}"
        )
        self.notify_channel("Shopify sync", message, "shopify_sync")

    @api.model
    def export_to_shopify(self) -> None:
        _logger.debug("Starting export to Shopify...")
        odoo_products = self.env["product.product"].search(
            [
                ("sale_ok", "=", True),
                ("is_ready_for_sale", "=", True),
                ("website_description", "!=", False),
                ("website_description", "!=", ""),
            ]
        )
        odoo_products = odoo_products.filtered(
            lambda p: p.shopify_next_export is True
            or (
                p.write_date > (p.shopify_last_exported or datetime.min)
                or p.product_tmpl_id.write_date > (p.shopify_last_exported or datetime.min)
            )
        )
        total_products = len(odoo_products)
        _logger.debug(f"Found {total_products} products to export to Shopify.")
        graphql_query_path = Path(__file__).parent.parent / "graphql" / "shopify_product.graphql"
        graphql_document = graphql_query_path.read_text()
        graphql_client = shopify.GraphQL()
        helper = ShopifyGraphQLHelper(graphql_client, graphql_document)
        shopify_location_gid = self.fetch_first_store_location_id(graphql_client, graphql_document)
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        export_service = ShopifyExportService(self.env, helper, shopify_location_gid, base_url)

        done_count = 0

        for odoo_product in odoo_products:
            _logger.debug(
                f"({done_count} of {total_products}) Starting export of Odoo product ID: {odoo_product.default_code} - {odoo_product.name}"
            )

            done_count += 1

            result_dict = export_service.export_product(odoo_product)
            shopify_product = result_dict.get("data", {}).get("productUpdate", {}).get("product") or result_dict.get(
                "data", {}
            ).get("productCreate", {}).get("product")
            export_service.update_publications(shopify_product.get("id"))
            export_service.finalize_export(odoo_product, shopify_product)
            _logger.debug(
                f"({done_count} of {total_products}) Finished export of Odoo product ID: {odoo_product.default_code} - {odoo_product.name}"
            )
            if done_count % self.COMMIT_AFTER == 0:
                self.env.cr.commit()
                _logger.debug(
                    f"({int(done_count / self.COMMIT_AFTER)} of {math.ceil(total_products / self.COMMIT_AFTER)})Committed changes to the database."
                )
        message = f"Shopify exported {done_count} items successfully at {self.now_in_localtime_formatted()}"
        self.notify_channel("Shopify sync", message, "shopify_sync")

    @staticmethod
    def fetch_first_store_location_id(graphql_client: shopify.GraphQL, graphql_document: str) -> str:
        result = graphql_client.execute(query=graphql_document, operation_name="GetLocations")
        result_dict = json.loads(result)
        return result_dict["data"]["locations"]["edges"][0]["node"]["id"]


class ShopifyGraphQLHelper:
    def __init__(self, graphql_client: shopify.GraphQL, graphql_document: str):
        self.client = graphql_client
        self.document = graphql_document

    def execute_query(self, variables: dict[str, Any], operation_name: str) -> dict[str, Any]:
        result = self.client.execute(query=self.document, variables=variables, operation_name=operation_name)
        return json.loads(result)

    @staticmethod
    def check_errors(result: dict[str, Any]) -> None:
        errors = result.get("errors", [])
        errors += result.get("data", {}).get("productUpdate", {}).get("userErrors", [])
        errors += result.get("data", {}).get("productCreate", {}).get("userErrors", [])
        if errors:
            error_messages = []
            for error in errors:
                error_messages.append(
                    f"Error updating/creating product: (Message: {error.get('message')}) (Extension: {error.get('extensions')}) (Field: {error.get('field')})"
                )
            raise ValueError("Shopify GraphQL Errors: " + " | ".join(error_messages))

    def execute_and_validate(self, variables: dict[str, Any], operation_name: str) -> dict[str, Any]:
        result = self.execute_query(variables, operation_name)
        self.check_errors(result)
        return result


class ShopifyImportService:
    def __init__(self, env: Any, helper: ShopifyGraphQLHelper):
        self.env = env
        self.helper = helper
        self.max_products = 250
        self.commit_after = self.max_products
        self.default_datetime = datetime(2000, 1, 1, tzinfo=UTC)

    def fetch_product_edges(self, cursor: Optional[str], time_filter: str) -> list[dict[str, Any]]:
        variables = {"query": f"updated_at:>{time_filter}", "cursor": cursor, "limit": self.max_products}
        result = self.helper.execute_and_validate(variables, "GetProducts")
        return result.get("data", {}).get("products", {}).get("edges", [])

    @staticmethod
    def parse_product_data(product: dict[str, Any]) -> dict[str, Any]:
        try:
            variant = product.get("variants", {}).get("edges", [])[0].get("node", {})
            metafields = product.get("metafields", {}).get("edges", [])
            inventory = variant.get("inventoryItem", {})
            weight = float(inventory.get("measurement", {}).get("weight", {}).get("value", 0))
            cost = float(inventory.get("unitCost", {}).get("amount", 0))
            sku, bin_location = ShopifySync.extract_sku_bin_from_shopify_product(product)
            quantity = int(product.get("totalInventory", 0))
        except AttributeError as error:
            _logger.error("Error parsing product data: %s", error)
            if error.args[0] == "'NoneType' object has no attribute 'get'":
                raise IncompleteDataError("Incomplete data from Shopify" + str(error))
            raise error

        return {
            "id": ShopifySync.extract_id_from_gid(product.get("id")),
            "variant_id": ShopifySync.extract_id_from_gid(variant.get("id")),
            "sku": sku,
            "bin": bin_location,
            "qty_available": quantity,
            "metafields": metafields,
            "title": product.get("title") or "",
            "description_html": product.get("descriptionHtml") or "",
            "created_at": product.get("createdAt") or "",
            "price": float(variant.get("price") or 0.0),
            "cost": cost,
            "barcode": variant.get("barcode") or "",
            "weight": weight,
            "status": product.get("status") or "",
            "vendor": product.get("vendor") or "",
            "part_type": product.get("productType") or "",
        }

    def map_to_odoo_product_data(self, shopify_data: dict[str, Any], odoo_product: Optional[Any]) -> dict[str, Any]:
        metafields = shopify_data["metafields"]
        odoo_data = {
            "name": shopify_data["title"],
            "default_code": shopify_data["sku"],
            "website_description": shopify_data["description_html"],
            "shopify_product_id": shopify_data["id"],
            "shopify_variant_id": shopify_data["variant_id"],
            "shopify_created_at": parse_to_utc(shopify_data["created_at"]).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S"),
            "barcode": "",
            "list_price": shopify_data["price"],
            "standard_price": shopify_data["cost"],
            "mpn": shopify_data["barcode"],
            "bin": shopify_data["bin"],
            "weight": shopify_data["weight"],
            "type": "consu",
            "is_storable": True,
            "manufacturer": (
                self.env["product.manufacturer"].search([("name", "=", shopify_data["vendor"])], limit=1).id
                if shopify_data["vendor"]
                else None
            ),
            "is_published": shopify_data["status"].lower() == "active",
            "is_ready_for_sale": True,
        }
        shopify_condition = ""
        for mf_data in metafields:
            mf = mf_data.get("node", {})
            if mf.get("key") == "condition":
                shopify_condition = mf.get("value")
                odoo_data["shopify_condition_id"] = ShopifySync.extract_id_from_gid(mf.get("id"))
            if mf.get("key") == "ebay_category_id":
                odoo_data["shopify_ebay_category_id"] = ShopifySync.extract_id_from_gid(mf.get("id"))
                part_type = self.env["product.type"].search(
                    [("name", "=", shopify_data["part_type"]), ("ebay_category_id", "=", mf.get("value"))], limit=1
                )
                if part_type:
                    odoo_data["part_type"] = part_type.id
        if shopify_condition:
            odoo_condition = self.env["product.condition"].search([("code", "=", shopify_condition)], limit=1)
            if odoo_condition:
                odoo_data["condition"] = odoo_condition.id
            elif odoo_product:
                odoo_data["condition"] = odoo_product.condition.code
        return odoo_data

    @staticmethod
    def determine_latest_product_modification_time_static(odoo_product: Any) -> datetime:
        dt1 = odoo_product.write_date.replace(tzinfo=UTC) if odoo_product.write_date else None
        dt2 = odoo_product.product_tmpl_id.write_date.replace(tzinfo=UTC) if odoo_product.product_tmpl_id.write_date else None
        dt3 = odoo_product.shopify_last_exported.replace(tzinfo=UTC) if odoo_product.shopify_last_exported else None
        return max(filter(None, [dt1, dt2, dt3, datetime(2000, 1, 1, tzinfo=UTC)]))

    def fetch_and_store_product_image(self, index: int, shopify_image_url: str, odoo_product_template: Any) -> None:
        retries = 0
        while retries < MAX_RETRIES:
            try:
                response = requests.get(shopify_image_url, timeout=10)
                response.raise_for_status()
                image_base64 = base64.b64encode(response.content)
                self.env["product.image"].create(
                    {"product_tmpl_id": odoo_product_template.id, "name": index, "image_1920": image_base64}
                )
                return
            except RequestException as error:
                _logger.warning("Failed to fetch image from Shopify. Attempt %s/%s. Reason: %s", retries + 1, MAX_RETRIES, error)
                retries += 1
                time.sleep(MIN_RETRY_DELAY * (2**retries))
        _logger.error("Failed to fetch image from Shopify after %s attempts.", MAX_RETRY_DELAY)

    def import_products(self, last_import_time_str: str) -> tuple[int, int]:
        updated_count = 0
        total_count = 0
        cursor: Optional[str] = None
        has_more = True
        while has_more:
            edges = self.fetch_product_edges(cursor, last_import_time_str)
            for edge in edges:
                product = edge.get("node", {})
                total_count += 1
                shopify_data = self.parse_product_data(product)
                odoo_product = self.env["product.product"].search(
                    [
                        "|",
                        ("shopify_product_id", "=", ShopifySync.extract_id_from_gid(product["id"])),
                        ("default_code", "=", shopify_data["sku"]),
                        ("active", "in", [True, False]),
                    ],
                    limit=1,
                )
                shopify_updated_at = parse_to_utc(product.get("updatedAt", ""))
                _logger.debug(
                    f"({total_count}) Starting import of Shopify product ID: {shopify_data["id"]} - {shopify_data["title"]}"
                )
                if odoo_product:
                    latest_write = self.determine_latest_product_modification_time_static(odoo_product)
                    status = "unchanged"
                    if shopify_updated_at > latest_write:
                        odoo_data = self.map_to_odoo_product_data(shopify_data, odoo_product)
                        odoo_product.write(odoo_data)
                        status = "updated"
                    if status in ["created", "updated"]:
                        updated_count += 1
                else:
                    odoo_data = self.map_to_odoo_product_data(shopify_data, None)
                    odoo_product = self.env["product.product"].create(odoo_data)
                    updated_count += 1
                self.import_product_images_from_shopify(product, odoo_product)
                self.update_product_stock_in_odoo(shopify_data["qty_available"], odoo_product)
                _logger.debug(
                    f"({total_count}) Finished import of Shopify product ID: {shopify_data['id']} - {shopify_data['title']}"
                )
            if edges:
                cursor = edges[-1].get("cursor")
                has_more = bool(cursor)
            else:
                has_more = False
            if total_count % self.commit_after == 0:
                self.env.cr.commit()

        return updated_count, total_count

    def import_product_images_from_shopify(self, shopify_product: dict, odoo_product: Any) -> None:
        product_template = self.env["product.template"].browse(odoo_product.product_tmpl_id.id)
        if not product_template.image_1920:
            image_edges = shopify_product.get("media", {}).get("edges", [])
            for index, edge in enumerate(image_edges):
                image_url = edge.get("node", {}).get("preview", {}).get("image", {}).get("url") or ""
                self.fetch_and_store_product_image(index, image_url, product_template)

    @staticmethod
    def update_product_stock_in_odoo(shopify_quantity: int, odoo_product: Any) -> None:
        if shopify_quantity is not None:
            odoo_product.update_quantity(shopify_quantity)


class ShopifyExportService:
    ONLINE_STORE_ID = "19453116480"
    POINT_OF_SALE_ID = "42683596853"
    GOOGLE_ID = "88268636213"
    SHOP_ID = "99113467957"

    def __init__(self, env: Any, helper: ShopifyGraphQLHelper, shopify_location_gid: str, base_url: str):
        self.env = env
        self.helper = helper
        self.shopify_location_gid = shopify_location_gid
        self.base_url = base_url

    def prepare_variant_data(self, odoo_product: Any) -> dict[str, Any]:
        sku_field = f"{odoo_product.default_code} - {odoo_product.bin}" if odoo_product.bin else odoo_product.default_code
        variant = {
            "price": odoo_product.list_price,
            "barcode": odoo_product.mpn or "",
            "inventoryItem": {
                "cost": odoo_product.standard_price,
                "sku": sku_field,
                "measurement": {
                    "weight": {
                        "value": odoo_product.weight,
                        "unit": "POUNDS",
                    }
                },
            },
        }
        if odoo_product.shopify_variant_id:
            variant["id"] = ShopifySync.convert_to_shopify_gid_static("ProductVariant", odoo_product.shopify_variant_id)
        if not odoo_product.shopify_product_id:
            variant["inventoryQuantities"] = [
                {"availableQuantity": int(odoo_product.qty_available), "locationId": self.shopify_location_gid}
            ]
        return variant

    @staticmethod
    def prepare_metafields(odoo_product: Any) -> list[dict[str, Any]]:
        condition = {"value": odoo_product.condition.code or ""}
        if odoo_product.shopify_condition_id:
            condition["id"] = ShopifySync.convert_to_shopify_gid_static("Metafield", odoo_product.shopify_condition_id)
        else:
            condition.update({"key": "condition", "type": "single_line_text_field", "namespace": "custom"})
        ebay = {"value": str(odoo_product.part_type.ebay_category_id) or ""}
        if odoo_product.shopify_ebay_category_id:
            ebay["id"] = ShopifySync.convert_to_shopify_gid_static("Metafield", odoo_product.shopify_ebay_category_id)
        else:
            ebay.update({"key": "ebay_category_id", "type": "number_integer", "namespace": "custom"})
        return [condition, ebay]

    def prepare_product_data(self, odoo_product: Any) -> dict[str, Any]:
        metafields = self.prepare_metafields(odoo_product)
        product_data = {
            "title": odoo_product.name,
            "descriptionHtml": odoo_product.website_description,
            "vendor": odoo_product.manufacturer.name if odoo_product.manufacturer else None,
            "productType": odoo_product.part_type.name if odoo_product.part_type else None,
            "status": "ACTIVE" if odoo_product.qty_available > 0 else "DRAFT",
            "metafields": metafields,
        }
        if odoo_product.shopify_product_id:
            product_data["id"] = ShopifySync.convert_to_shopify_gid_static("Product", odoo_product.shopify_product_id)
        return product_data

    @staticmethod
    def prepare_images(base_url: str, odoo_product: Any) -> list[dict[str, str]]:
        media = []
        for image in sorted(odoo_product.product_tmpl_id.product_template_image_ids, key=lambda img: img.name):
            media.append(
                {
                    "mediaContentType": "IMAGE",
                    "alt": odoo_product.name,
                    "originalSource": base_url + "/web/image/product.image/" + str(image.id) + "/image_1920",
                }
            )
        return media

    def export_product(self, odoo_product: Any) -> dict[str, Any]:
        product_data = self.prepare_product_data(odoo_product)
        if odoo_product.shopify_product_id:
            result = self.helper.execute_and_validate({"input": product_data}, "UpdateProduct")
            _logger.debug("Shopify update result: %s", result)
        else:
            result = self.helper.execute_and_validate({"input": product_data}, "CreateProduct")
            _logger.debug("Shopify create result: %s", result)
            product_id = result.get("data", {}).get("productCreate", {}).get("product", {}).get("id")
            variant_data = self.prepare_variant_data(odoo_product)
            self.send_variant(product_id, variant_data)
            images = self.prepare_images(self.base_url, odoo_product)
            try:
                self.helper.execute_and_validate({"productId": product_id, "media": images}, "createProductMedia")
            except ValueError as error:
                self.helper.execute_and_validate({"input": {"id": product_id}}, "DeleteProduct")
                raise error

        return result

    def send_variant(self, product_id: str, variant_data: dict[str, Any]) -> dict[str, Any]:
        variables = {
            "productId": product_id,
            "strategy": "REMOVE_STANDALONE_VARIANT",
            "variants": [variant_data],
        }
        result = self.helper.execute_and_validate(variables, "ProductVariantsBulkCreate")
        return result

    def update_publications(self, product_id: str) -> None:
        publications = {
            "id": product_id,
            "input": [
                {"publicationId": ShopifySync.convert_to_shopify_gid_static("Publication", self.ONLINE_STORE_ID)},
                {"publicationId": ShopifySync.convert_to_shopify_gid_static("Publication", self.POINT_OF_SALE_ID)},
                {"publicationId": ShopifySync.convert_to_shopify_gid_static("Publication", self.GOOGLE_ID)},
                {"publicationId": ShopifySync.convert_to_shopify_gid_static("Publication", self.SHOP_ID)},
            ],
        }
        self.helper.execute_and_validate(publications, "UpdatePublications")

    @staticmethod
    def finalize_export(odoo_product: Any, shopify_product: dict[str, Any]) -> None:
        shopify_metafields = shopify_product.get("metafields", {}).get("edges", [])
        condition_id = ""
        ebay_id = ""
        for mf in shopify_metafields:
            key = mf.get("node", {}).get("key")
            if key == "condition":
                condition_id = str(ShopifySync.extract_id_from_gid(mf.get("node", {}).get("id")))
            elif key == "ebay_category_id":
                ebay_id = str(ShopifySync.extract_id_from_gid(mf.get("node", {}).get("id")))
        odoo_product.write(
            {
                "shopify_last_exported": fields.Datetime.now(),
                "shopify_product_id": ShopifySync.extract_id_from_gid(shopify_product.get("id")),
                "shopify_next_export": False,
                "shopify_ebay_category_id": ebay_id,
                "shopify_condition_id": condition_id,
            }
        )
