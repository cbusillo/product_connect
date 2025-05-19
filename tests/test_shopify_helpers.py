from datetime import datetime, UTC
from dataclasses import dataclass
from pydantic import BaseModel

from ..services.shopify import helpers


def test_normalize_str() -> None:
    assert helpers.normalize_str(" TeSt  ") == "test"


def test_normalize_phone() -> None:
    assert helpers.normalize_phone("+1 (800) 555-1234") == "18005551234"


def test_normalize_email() -> None:
    assert helpers.normalize_email(" Example@Email.Com ") == "example@email.com"


@dataclass
class FakeImage:
    sequence: int | None = None
    create_date: datetime | None = None


def test_image_order_key() -> None:
    dt = datetime(2024, 1, 1)
    image = FakeImage(sequence=2, create_date=dt)
    assert helpers.image_order_key(image) == (2, dt)


def test_last_import_config_key() -> None:
    assert helpers.last_import_config_key("product") == "shopify.last_product_import_time"


def test_sync_mode_properties() -> None:
    mode = helpers.SyncMode.IMPORT_ALL_PRODUCTS
    assert mode.display_name == "Import All Products"
    assert mode.resource_type == "product"
    choices = helpers.SyncMode.choices()
    assert (mode.value, mode.display_name) in choices


@dataclass
class FakeRecord:
    name: str = "prod"
    id: int = 42
    default_code: str = "SKU"


def test_odoo_data_error_str() -> None:
    exc = helpers.OdooDataError("msg", FakeRecord())
    assert str(exc) == "msg [Odoo Name prod] [Odoo ID 42] [Odoo SKU SKU]"


class FakeVariant(BaseModel):
    sku: str | None = None


class FakeShopifyProduct(BaseModel):
    id: str
    title: str
    variants: list[FakeVariant]


def test_shopify_api_error_str() -> None:
    product = FakeShopifyProduct(id="gid/123", title="name", variants=[FakeVariant(sku="S1")])
    exc = helpers.ShopifyApiError("err", shopify_record=product)
    assert str(exc) == "err [Odoo Name name] [Shopify ID gid/123]"


def test_parse_shopify_datetime_to_utc() -> None:
    value = "2024-05-20T12:34:56Z"
    dt = helpers.parse_shopify_datetime_to_utc(value)
    assert dt == datetime(2024, 5, 20, 12, 34, 56)


def test_format_datetime_for_shopify() -> None:
    dt = datetime(2024, 5, 20, 12, 34, 56, tzinfo=UTC)
    assert helpers.format_datetime_for_shopify(dt) == "2024-05-20T12:34:56Z"


def test_parse_shopify_id_from_gid() -> None:
    assert helpers.parse_shopify_id_from_gid("gid://shopify/Product/123") == "123"


def test_format_shopify_gid_from_id() -> None:
    assert helpers.format_shopify_gid_from_id("Product", 123) == "gid://shopify/Product/123"


def test_parse_shopify_sku_field_to_sku_and_bin() -> None:
    assert helpers.parse_shopify_sku_field_to_sku_and_bin("SKU1 - Bin") == ("SKU1", "Bin")


def test_format_sku_bin_for_shopify() -> None:
    assert helpers.format_sku_bin_for_shopify("SKU1", "Bin") == "SKU1 - Bin"
