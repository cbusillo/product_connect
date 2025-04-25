import logging
from datetime import datetime, UTC
from enum import StrEnum, auto
from typing import TypeVar, cast

from dateutil.parser import parse
from odoo import models
from odoo.exceptions import UserError
from pydantic import BaseModel

T = TypeVar("T")

_logger = logging.getLogger(__name__)

DEFAULT_DATETIME = datetime(2000, 1, 1)
SHOPIFY_PAGE_SIZE = 250
IMAGE_ORDER_KEY = lambda image: (image.sequence or 0, image.create_date or DEFAULT_DATETIME)


# noinspection PyEnum
class SyncMode(StrEnum):
    @staticmethod
    def _generate_next_value_(name: str, start: int, count: int, last_values: list[str]) -> str:
        return name.lower()

    IMPORT_THEN_EXPORT = auto()
    IMPORT_CHANGED = auto()
    EXPORT_CHANGED = auto()
    IMPORT_ALL = auto()
    EXPORT_ALL = auto()
    IMPORT_SINCE_DATE = auto()
    EXPORT_SINCE_DATE = auto()
    IMPORT_ONE = auto()
    EXPORT_BATCH = auto()
    RESET_SHOPIFY = auto()

    @property
    def display_name(self) -> str:
        return self.value.replace("_", " ").title()

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return cast(list[tuple[str, str]], [(m.value, m.display_name) for m in cls])


class OdooDataError(UserError):
    def __init__(self, message: str, odoo_record: models.Model | None = None) -> None:
        super().__init__(message)
        self.odoo_record = odoo_record

    @property
    def sku(self) -> str:
        if self.odoo_record:
            return getattr(self.odoo_record, "default_code", "")
        return ""

    @property
    def odoo_product_id(self) -> str:
        if self.odoo_record:
            return getattr(self.odoo_record, "id", "")
        return ""

    @property
    def name(self) -> str:
        if self.odoo_record:
            return getattr(self.odoo_record, "name", "")
        return ""

    def __str__(self) -> str:
        text = super().__str__()
        if self.name:
            text += f" [Odoo Name {self.name}]"
        if self.odoo_product_id:
            text += f" [Odoo ID {self.odoo_product_id}]"
        if self.sku:
            text += f" [Odoo SKU {self.sku}]"
        return text


class OdooMissingSkuError(OdooDataError):
    pass


class ShopifySyncRunFailed(Exception):
    pass


class ShopifyApiError(OdooDataError):
    def __init__(
        self,
        message: str,
        *,
        shopify_record: BaseModel | None = None,
        shopify_input: BaseModel | None = None,
        odoo_record: models.Model | None = None,
    ) -> None:
        super().__init__(message, odoo_record=odoo_record)
        self.shopify_record = shopify_record
        self.shopify_input = shopify_input

    def __str__(self) -> str:
        text = super().__str__()
        if self.__cause__:
            text += f"\nShopify error: {self.__cause__}"

        if not self.shopify_record:
            return text

        if self.name and self.name not in text:
            text += f" [{self.name}]"
        if self.shopify_product_id:
            text += f" [Shopify ID {self.shopify_product_id}]"
        if self.sku and self.sku not in text:
            text += f" [Shopify SKU {self.sku}]"
        return text

    @property
    def sku(self) -> str:
        try:
            return self.shopify_record.variants.nodes[0].sku or ""
        except (AttributeError, IndexError, TypeError):
            pass
        return ""

    @property
    def shopify_product_id(self) -> str:
        if self.shopify_record:
            return getattr(self.shopify_record, "id", "")
        return ""

    @property
    def name(self) -> str:
        if self.shopify_record:
            return getattr(self.shopify_record, "title", "")
        return super().name


class ShopifyDataError(ShopifyApiError):
    pass


class ShopifyMissingSkuFieldError(ShopifyDataError):
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
