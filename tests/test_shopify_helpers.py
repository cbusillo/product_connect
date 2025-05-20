from datetime import datetime, UTC
from typing import Any, Callable, List, Tuple, cast

from pydantic import BaseModel

from odoo.exceptions import UserError
from odoo.tests import TransactionCase
from ..services.shopify import helpers


class TestShopifyHelpers(TransactionCase):
    test_tags = {"-at_install", "-post_install"}
    def test_normalise_values(self) -> None:
        cases: List[Tuple[str, Callable[[str], str], str]] = [
            (" TeSt  ", helpers.normalize_str, "test"),
            ("+1 (800) 555-1234", helpers.normalize_phone, "18005551234"),
            (" Example@Email.Com ", helpers.normalize_email, "example@email.com"),
        ]
        for raw, func, expected in cases:
            with self.subTest(raw=raw, func=func.__name__):
                self.assertEqual(func(raw), expected)

    def test_image_order_key(self) -> None:
        class MockImage:
            def __init__(self, sequence: int | None, create_date: datetime | None) -> None:
                self.sequence = sequence
                self.create_date = create_date

        dt = datetime(2024, 1, 1)
        self.assertEqual(helpers.image_order_key(MockImage(2, dt)), (2, dt))

    def test_last_import_config_key(self) -> None:
        self.assertEqual(helpers.last_import_config_key("product"), "shopify.last_product_import_time")

    def test_sync_mode_properties(self) -> None:
        mode = helpers.SyncMode.IMPORT_ALL_PRODUCTS
        self.assertEqual(mode.display_name, "Import All Products")
        self.assertEqual(mode.resource_type, "product")
        self.assertIn((mode.value, mode.display_name), helpers.SyncMode.choices())

    def test_odoo_data_error_str(self) -> None:
        class MockRec:
            name = "prod"
            id = 42
            default_code = "SKU"

        err = helpers.OdooDataError("msg", MockRec())
        self.assertEqual(str(err), "msg [Odoo Name prod] [Odoo ID 42] [Odoo SKU SKU]")

    def test_odoo_data_error_no_record(self) -> None:
        err = helpers.OdooDataError("x")
        self.assertEqual(err.sku, "")
        self.assertEqual(err.name, "")

    def test_shopify_api_error_str(self) -> None:
        class Var(BaseModel):
            sku: str | None = None

        class Vars(BaseModel):
            nodes: list[Var]

        class Prod(BaseModel):
            id: str
            title: str
            variants: Vars

        prod = Prod(id="gid/123", title="name", variants=Vars(nodes=[Var(sku="S1")]))
        msg = str(helpers.ShopifyApiError("err", shopify_record=prod))
        self.assertIn("[Shopify ID gid/123]", msg)
        self.assertIn("[Shopify SKU S1]", msg)

    def test_shopify_api_error_only_odoo_record(self) -> None:
        class MockOdoo:
            def __init__(self) -> None:
                self.default_code = "D1"
                self.id = 99
                self.name = "dummy"

        txt = str(helpers.ShopifyApiError("msg", odoo_record=MockOdoo()))
        self.assertIn("[Odoo Name dummy]", txt)
        self.assertNotIn("Shopify ID", txt)

    def test_parse_shopify_datetime_to_utc(self) -> None:
        self.assertEqual(
            helpers.parse_shopify_datetime_to_utc("2024-05-20T12:34:56Z"),
            datetime(2024, 5, 20, 12, 34, 56),
        )

    def test_format_datetime_for_shopify(self) -> None:
        dt = datetime(2024, 5, 20, 12, 34, 56, tzinfo=UTC)
        self.assertEqual(helpers.format_datetime_for_shopify(dt), "2024-05-20T12:34:56Z")

    def test_parse_format_sku_bin(self) -> None:
        self.assertEqual(helpers.parse_shopify_sku_field_to_sku_and_bin("SKU1 - Bin"), ("SKU1", "Bin"))
        self.assertEqual(helpers.format_sku_bin_for_shopify("SKU1", "Bin"), "SKU1 - Bin")
        self.assertEqual(helpers.parse_shopify_sku_field_to_sku_and_bin("SKU1"), ("SKU1", ""))

    def test_parse_sku_bin_errors(self) -> None:
        for bad in ["", "   "]:
            with self.subTest(bad=bad):
                with self.assertRaises(helpers.ShopifyMissingSkuFieldError):
                    helpers.parse_shopify_sku_field_to_sku_and_bin(bad)

    def test_format_sku_bin_missing_sku(self) -> None:
        with self.assertRaises(helpers.OdooMissingSkuError):
            helpers.format_sku_bin_for_shopify("", "Bin")

    def test_write_if_changed_branches(self) -> None:
        class MockRec:
            def __init__(self) -> None:
                self._fields = {"name": object()}
                self.name = "old"
                self._written: list[dict[str, str]] = []

            def __getitem__(self, item: str) -> Any:
                return getattr(self, item)

            def with_context(self, **_kw: Any) -> "MockRec":
                return self

            def write(self, vals: dict[str, str]) -> None:
                self._written.append(vals)
                for k, v in vals.items():
                    setattr(self, k, v)

        rec = MockRec()
        self.assertFalse(helpers.write_if_changed(cast(Any, rec), {"name": "old"}))
        self.assertTrue(helpers.write_if_changed(cast(Any, rec), {"name": "new"}))
        self.assertEqual(rec._written, [{"name": "new"}])

    def test_write_if_changed_float(self) -> None:
        class FloatField:
            def __init__(self, digits: tuple[int, int] = (16, 2)) -> None:
                self.digits = digits

        class FloatRec:
            def __init__(self, price: float) -> None:
                self.price = price
                self._fields = {"price": FloatField()}
                self.env = object()
                self._written: list[dict[str, float]] = []

            def __getitem__(self, item: str) -> Any:
                return getattr(self, item)

            def with_context(self, **_kw: Any) -> "FloatRec":
                return self

            def write(self, vals: dict[str, float]) -> None:
                self._written.append(vals)
                for k, v in vals.items():
                    setattr(self, k, v)

        rec = FloatRec(1.23)
        self.assertFalse(helpers.write_if_changed(cast(Any, rec), {"price": 1.23}))
        self.assertTrue(helpers.write_if_changed(cast(Any, rec), {"price": 1.25}))
        with self.assertRaises(UserError):
            helpers.write_if_changed(cast(Any, rec), {"price": ["bad"]})

    def test_determine_latest_odoo_product_modification_time(self) -> None:
        class Tmpl:
            def __init__(self, write_date: datetime) -> None:
                self.write_date = write_date

        class Prod:
            def __init__(self, w1: datetime, w2: datetime, w3: datetime) -> None:
                self.write_date = w1
                self.product_tmpl_id = Tmpl(w2)
                self.shopify_last_exported_at = w3

        t1, t2, t3 = datetime(2024, 1, 1), datetime(2024, 1, 2), datetime(2024, 1, 3)
        self.assertEqual(helpers.determine_latest_odoo_product_modification_time(Prod(t1, t2, t3)), t3)
