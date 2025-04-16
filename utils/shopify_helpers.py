import logging
from datetime import datetime
from typing import TypeVar
from zoneinfo import ZoneInfo

from dateutil.parser import parse
from odoo import models
from odoo.exceptions import UserError
from pydantic import BaseModel

T = TypeVar("T")
UTC = ZoneInfo("UTC")

_logger = logging.getLogger(__name__)

DEFAULT_DATETIME = datetime(2000, 1, 1, tzinfo=UTC)


class ShopifyApiError(UserError):
    def __init__(self, message: str, shopify_record: BaseModel | None = None, odoo_record: models.Model | None = None) -> None:
        super().__init__(message)
        self.record = odoo_record
        self.shopify_record = shopify_record


class ShopifyDataError(ShopifyApiError):
    pass


class ShopifyMissingSkuFieldError(ShopifyDataError):
    pass


class OdooDataError(UserError):
    def __init__(self, message: str, record: models.Model | None = None) -> None:
        super().__init__(message)
        self.record = record

    def __str__(self) -> str:
        return super().__str__() + f"(Odoo record: {self.record})" if self.record else ""


class OdooMissingSkuError(OdooDataError):
    pass


def normalize_datetime(dt: datetime | None) -> datetime | None:
    if not dt:
        return None
    return dt.astimezone(UTC).replace(tzinfo=None)


def parse_shopify_datetime_to_utc(date_str: str) -> datetime:
    return parse(date_str).astimezone(UTC).replace(tzinfo=None)


def format_datetime_for_shopify(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def current_datetime_for_shopify() -> str:
    return format_datetime_for_shopify(datetime.now(UTC))


def current_utc_time() -> datetime:
    return datetime.now(UTC)


def parse_shopify_id_from_gid(gid: str) -> int:
    return int(gid.split("/")[-1])


def format_shopify_gid_from_id(resource_type: str, resource_id: int | str) -> str:
    return f"gid://shopify/{resource_type}/{resource_id}"


def parse_shopify_sku_field_to_sku_and_bin(sku_field: str) -> tuple[str, str]:
    if not sku_field.strip():
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


def determine_latest_product_modification_time(
    odoo_product: "odoo.model.product_product", last_import_time: datetime
) -> datetime:
    if last_import_time.year < 2001:
        return normalize_datetime(DEFAULT_DATETIME)
    odoo_product_template = odoo_product.product_tmpl_id
    odoo_product_write_date = normalize_datetime(odoo_product.write_date)
    odoo_product_template_write_date = normalize_datetime(odoo_product_template.write_date)
    odoo_product_shopify_last_exported = normalize_datetime(odoo_product.shopify_last_exported)

    dates = [
        odoo_product_write_date,
        odoo_product_template_write_date,
        odoo_product_shopify_last_exported,
        normalize_datetime(DEFAULT_DATETIME),
    ]
    return max(filter(None, dates))
