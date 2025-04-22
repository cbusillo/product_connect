import logging
from datetime import datetime, UTC
from typing import TypeVar

from dateutil.parser import parse
from odoo import models
from odoo.exceptions import UserError
from pydantic import BaseModel

T = TypeVar("T")

_logger = logging.getLogger(__name__)

DEFAULT_DATETIME = datetime(2000, 1, 1)
SHOPIFY_PAGE_SIZE = 250
IMAGE_ORDER_KEY = lambda image: (image.sequence or 0, image.create_date or DEFAULT_DATETIME)


class ShopifySyncRunFailed(Exception):
    pass


class ShopifyApiError(UserError):
    def __init__(
        self,
        message: str,
        shopify_record: BaseModel | None = None,
        shopify_input: BaseModel | None = None,
        odoo_record: models.Model | None = None,
    ) -> None:
        super().__init__(message)
        self.odoo_record = odoo_record
        self.shopify_record = shopify_record
        self.shopify_input = shopify_input


class ShopifyDataError(ShopifyApiError):
    pass


class ShopifyMissingSkuFieldError(ShopifyDataError):
    pass


class OdooDataError(UserError):
    def __init__(self, message: str, odoo_record: models.Model | None = None) -> None:
        super().__init__(message)
        self.odoo_record = odoo_record

    def __str__(self) -> str:
        return super().__str__() + f"(Odoo record: {self.odoo_record})" if self.odoo_record else ""


class OdooMissingSkuError(OdooDataError):
    pass


def parse_shopify_datetime_to_utc(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = parse(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).replace(tzinfo=None)


def format_datetime_for_shopify(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_shopify_id_from_gid(gid: str) -> str:
    if isinstance(gid, int):
        return str(gid)
    return gid.split("/")[-1]


def format_shopify_gid_from_id(resource_type: str, resource_id: int | str) -> str:
    return f"gid://shopify/{resource_type}/{resource_id}"


def parse_shopify_sku_field_to_sku_and_bin(sku_field: str) -> tuple[str, str]:
    if not sku_field or not sku_field.strip():
        raise ShopifyMissingSkuFieldError("No SKU field from Shopify")

    sku_field_separator = " - " if " - " in sku_field else " "
    parts = [value.strip() for value in sku_field.split(sku_field_separator, 1)]

    sku = parts[0]
    bin_location = parts[1] if len(parts) > 1 else ""

    if not sku:
        raise ShopifyMissingSkuFieldError("No SKU from Shopify")

    return sku, bin_location


def format_sku_bin_for_shopify(sku: str, bin_location: str) -> str:
    sku = sku.strip()
    if not sku:
        raise OdooMissingSkuError("No SKU to format for Shopify")

    bin_location = bin_location.strip()
    return f"{sku} - {bin_location}"


def determine_latest_odoo_product_modification_time(product: "odoo.model.product_product") -> datetime:
    dates = [
        product.write_date,
        product.product_tmpl_id.write_date,
        product.shopify_last_exported_at,
        DEFAULT_DATETIME,
    ]
    return max(filter(None, dates))
