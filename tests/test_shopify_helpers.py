from typing import Any, cast
from datetime import datetime, UTC
from dataclasses import dataclass
from typing import Callable

import pytest

from pydantic import BaseModel
from odoo.exceptions import UserError

from ..services.shopify import helpers


@pytest.mark.parametrize(
    "input_string, function_to_test, expected_string",
    [
        (" TeSt  ", helpers.normalize_str, "test"),
        ("+1 (800) 555-1234", helpers.normalize_phone, "18005551234"),
        (" Example@Email.Com ", helpers.normalize_email, "example@email.com"),
    ],
)
def test_normalize_values(input_string: str, function_to_test: Callable[[str], str], expected_string: str) -> None:
    assert function_to_test(input_string) == expected_string


@dataclass
class MockImageForOrdering:
    sequence: int | None = None
    create_date: datetime | None = None


def test_image_order_key() -> None:
    datetime_value = datetime(2024, 1, 1)
    image = MockImageForOrdering(sequence=2, create_date=datetime_value)
    assert helpers.image_order_key(image) == (2, datetime_value)


def test_last_import_config_key() -> None:
    assert helpers.last_import_config_key("product") == "shopify.last_product_import_time"


def test_sync_mode_properties() -> None:
    mode = helpers.SyncMode.IMPORT_ALL_PRODUCTS
    assert mode.display_name == "Import All Products"
    assert mode.resource_type == "product"
    choices = helpers.SyncMode.choices()
    assert (mode.value, mode.display_name) in choices


@dataclass
class MockOdooRecordSimple:
    name: str = "prod"
    id: int = 42
    default_code: str = "SKU"


def test_odoo_data_error_str() -> None:
    error = helpers.OdooDataError("msg", MockOdooRecordSimple())
    assert str(error) == "msg [Odoo Name prod] [Odoo ID 42] [Odoo SKU SKU]"


@pytest.mark.parametrize("attr", ["sku", "name"])
def test_odoo_data_error_no_odoo_record(attr: str) -> None:
    error = helpers.OdooDataError("msg")
    assert getattr(error, attr) == ""


class FakeVariant(BaseModel):
    sku: str | None = None


class FakeVariants(BaseModel):
    nodes: list[FakeVariant]


class FakeShopifyProduct(BaseModel):
    id: str
    title: str
    variants: FakeVariants


def test_shopify_api_error_str() -> None:
    product = FakeShopifyProduct(
        id="gid/123",
        title="name",
        variants=FakeVariants(nodes=[FakeVariant(sku="S1")]),
    )
    error = helpers.ShopifyApiError("err", shopify_record=product)
    assert str(error) == "err [Odoo Name name] [Shopify ID gid/123] [Shopify SKU S1]"


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


def test_shopify_api_error_with_cause_and_record() -> None:
    product = FakeShopifyProduct(
        id="gid/456",
        title="name2",
        variants=FakeVariants(nodes=[FakeVariant(sku="S2")]),
    )
    with pytest.raises(helpers.ShopifyApiError) as error_info:
        try:
            raise ValueError("root cause")
        except ValueError as exc:
            raise helpers.ShopifyApiError("err", shopify_record=product) from exc
    # noinspection PyUnreachableCode
    error = error_info.value
    msg = str(error)
    assert "err" in msg
    assert "Shopify error: root cause" in msg
    assert "[Shopify ID gid/456]" in msg
    assert "[Shopify SKU S2]" in msg


def test_shopify_api_error_no_shopify_record() -> None:
    error = helpers.ShopifyApiError("err no record")
    assert str(error) == "err no record"
    assert error.sku == ""
    assert error.shopify_product_id == ""


@pytest.mark.parametrize("bad_value", ["", "   "])
def test_parse_shopify_sku_field_to_sku_and_bin_errors(bad_value: str) -> None:
    with pytest.raises(helpers.ShopifyMissingSkuFieldError):
        helpers.parse_shopify_sku_field_to_sku_and_bin(bad_value)


def test_format_sku_bin_for_shopify_missing_sku() -> None:
    with pytest.raises(helpers.OdooMissingSkuError):
        helpers.format_sku_bin_for_shopify("", "Bin")


def test_parse_shopify_datetime_to_utc_tz_aware() -> None:
    aware_datetime = datetime(2024, 1, 1, 12, tzinfo=UTC)
    result = helpers.parse_shopify_datetime_to_utc(aware_datetime)
    assert result == datetime(2024, 1, 1, 12)


class MockOdooRecord:
    def __init__(self) -> None:
        self.default_code = "D1"
        self.id = 99
        self.name = "dummy"


def test_shopify_api_error_only_odoo_record() -> None:
    err = helpers.ShopifyApiError("msg", odoo_record=MockOdooRecord())
    txt = str(err)
    assert "[Odoo Name dummy]" in txt
    assert "[Odoo ID 99]" in txt
    assert "Shopify ID" not in txt


def test_shopify_api_error_with_cause_no_shopify_record() -> None:
    with pytest.raises(helpers.ShopifyApiError) as exc_info:
        try:
            raise ValueError("root")
        except ValueError as exc:
            raise helpers.ShopifyApiError("msg") from exc
    # noinspection PyUnreachableCode
    txt = str(exc_info.value)
    assert "Shopify error: root" in txt
    assert "Shopify ID" not in txt
    assert "Shopify SKU" not in txt


class MockOdooModelRecord:
    def __init__(self) -> None:
        self._fields = {"name": object()}
        self.name = "old"
        self._written: list[dict[str, str]] = []

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def with_context(self, **_kwargs: Any) -> "MockOdooModelRecord":
        return self

    def write(self, vals: dict[str, Any]) -> None:
        self._written.append(vals)
        for k, v in vals.items():
            setattr(self, k, v)


def test_write_if_changed_branches() -> None:
    mock_record = MockOdooModelRecord()

    assert not helpers.write_if_changed(cast(Any, mock_record), {"name": "old"})
    assert mock_record._written == []

    assert helpers.write_if_changed(cast(Any, mock_record), {"name": "new"})
    assert mock_record.name == "new"
    assert mock_record._written == [{"name": "new"}]


class _DummyTemplate:
    def __init__(self, write_date: datetime) -> None:
        self.write_date = write_date


class _DummyProduct:
    def __init__(self, write_date: datetime, tmpl_write_date: datetime, export_date: datetime) -> None:
        self.write_date = write_date
        self.product_tmpl_id = _DummyTemplate(tmpl_write_date)
        self.shopify_last_exported_at = export_date


def test_determine_latest_odoo_product_modification_time() -> None:
    t1 = datetime(2024, 1, 1)
    t2 = datetime(2024, 1, 2)
    t3 = datetime(2024, 1, 3)  #
    prod = _DummyProduct(t1, t2, t3)
    assert helpers.determine_latest_odoo_product_modification_time(prod) == t3


class MockFloatField:
    def __init__(self, digits: tuple[int, int] = (16, 2)) -> None:
        self.digits = digits


class MockFloatRecord:
    def __init__(self, initial_price: float) -> None:
        self.price = initial_price
        self._fields = {"price": MockFloatField()}
        self.env = object()
        self._written: list[dict[str, float]] = []

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def with_context(self, **_kwargs: Any) -> "MockFloatRecord":
        return self

    def write(self, vals: dict[str, float]) -> None:
        self._written.append(vals)
        for key, value in vals.items():
            setattr(self, key, value)


def test_write_if_changed_unsupported_value_error() -> None:
    record = MockOdooModelRecord()
    with pytest.raises(UserError):
        helpers.write_if_changed(cast(Any, record), {"name": ["bad", "value"]})


def test_write_if_changed_float_no_write() -> None:
    record = MockFloatRecord(1.23)
    assert not helpers.write_if_changed(cast(Any, record), {"price": 1.23})
    assert record._written == []


def test_write_if_changed_float_write() -> None:
    record = MockFloatRecord(1.23)
    assert helpers.write_if_changed(cast(Any, record), {"price": 1.25})
    assert record._written == [{"price": 1.25}]


def test_parse_shopify_datetime_to_utc_naive() -> None:
    naive_dt = datetime(2024, 1, 1, 12)
    assert helpers.parse_shopify_datetime_to_utc(naive_dt) == datetime(2024, 1, 1, 12)


def test_format_datetime_for_shopify_naive() -> None:
    naive_datetime = datetime(2024, 1, 1, 12)
    assert helpers.format_datetime_for_shopify(naive_datetime) == "2024-01-01T12:00:00Z"


def test_parse_shopify_sku_field_space_separator() -> None:
    assert helpers.parse_shopify_sku_field_to_sku_and_bin("SKU1 BinA") == ("SKU1", "BinA")


def test_parse_shopify_sku_field_no_bin() -> None:
    assert helpers.parse_shopify_sku_field_to_sku_and_bin("SKU1") == ("SKU1", "")
