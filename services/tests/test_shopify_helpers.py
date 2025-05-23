from datetime import datetime, UTC
from typing import Any, Callable, List, Tuple, cast
from unittest.mock import patch

from pydantic import BaseModel

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from ..shopify import helpers


@tagged("post_install", "-at_install")
class TestShopifyHelpers(TransactionCase):
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
        self.assertEqual(str(err), "x")

    def test_odoo_data_error_name_only(self) -> None:
        class Rec:
            name = "n"
            id = None
            default_code = None

        err = helpers.OdooDataError("msg", Rec())
        self.assertEqual(str(err), "msg [Odoo Name n]")

    def test_odoo_data_error_name_only(self) -> None:
        class Rec:
            name = "n"
            id = None
            default_code = None

        err = helpers.OdooDataError("msg", Rec())
        self.assertEqual(str(err), "msg [Odoo Name n]")

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

    def test_parse_datetime_and_gid_and_sku_errors(self) -> None:
        naive_dt = datetime(2024, 5, 20, 12, 34, 56)
        self.assertEqual(helpers.parse_shopify_datetime_to_utc(naive_dt), naive_dt)
        self.assertEqual(helpers.parse_shopify_id_from_gid("5"), "5")
        self.assertEqual(helpers.format_shopify_gid_from_id("product", 5), "gid://shopify/product/5")
        with self.assertRaises(helpers.ShopifyMissingSkuFieldError):
            helpers.parse_shopify_sku_field_to_sku_and_bin(" ")
        with self.assertRaises(helpers.OdooMissingSkuError):
            helpers.format_sku_bin_for_shopify("", "bin")

    def test_write_if_changed_multi_record_and_api_error_cause(self) -> None:
        class Base:
            pass

        helpers.models.BaseModel = Base  # type: ignore

        class Multi(Base):
            def __len__(self) -> int:
                return 2

            id = 1

        class Rec:
            def __init__(self) -> None:
                self.field = Multi()
                self._fields = {"field": object()}

            def __getitem__(self, name: str) -> Any:
                return getattr(self, name)

        with self.assertRaises(UserError):
            helpers.write_if_changed(cast(Any, Rec()), {"field": Multi()})

        class Var(BaseModel):
            sku: str | None = None

        class Vars(BaseModel):
            nodes: list[Var]

        class Prod(BaseModel):
            id: str
            title: str
            variants: Vars

        prod = Prod(id="gid/1", title="n", variants=Vars(nodes=[Var()]))
        err = helpers.ShopifyApiError("msg", shopify_record=prod)
        err.__cause__ = ValueError("boom")
        self.assertIn("Shopify error: boom", str(err))

    def test_parse_shopify_id_from_gid(self) -> None:
        self.assertEqual(helpers.parse_shopify_id_from_gid("gid://shopify/product/123"), "123")

    def test_parse_shopify_id_from_gid_int(self) -> None:
        self.assertEqual(helpers.parse_shopify_id_from_gid(5), "5")

    def test_parse_datetime_and_format_with_naive(self) -> None:
        dt_str = "2024-05-20T07:34:56-05:00"
        parsed = helpers.parse_shopify_datetime_to_utc(dt_str)
        self.assertEqual(parsed, datetime(2024, 5, 20, 12, 34, 56))
        naive = datetime(2024, 5, 20, 12, 34, 56)
        self.assertEqual(helpers.format_datetime_for_shopify(naive), "2024-05-20T12:34:56Z")

    def test_image_order_key_defaults(self) -> None:
        class MockImage:
            def __init__(self) -> None:
                self.sequence = None
                self.create_date = None

        self.assertEqual(helpers.image_order_key(MockImage()), (0, helpers.DEFAULT_DATETIME))

    def test_normalise_none(self) -> None:
        funcs: list[Callable[[str | None], str]] = [helpers.normalize_str, helpers.normalize_phone, helpers.normalize_email]
        for func in funcs:
            with self.subTest(func=func.__name__):
                self.assertEqual(func(None), "")

    def test_parse_shopify_sku_field_simple(self) -> None:
        self.assertEqual(helpers.parse_shopify_sku_field_to_sku_and_bin("SKU1 Bin"), ("SKU1", "Bin"))

    def test_determine_latest_modification_none(self) -> None:
        class Tmpl:
            write_date = None

        class Prod:
            write_date = None
            product_tmpl_id = Tmpl()
            shopify_last_exported_at = None

        self.assertEqual(helpers.determine_latest_odoo_product_modification_time(Prod()), helpers.DEFAULT_DATETIME)

    def test_write_if_changed_single_record_and_callable_digits(self) -> None:
        class Base:
            def __len__(self) -> int:
                return 1

            def __init__(self, rec_id: int) -> None:
                self.id = rec_id

        helpers.models.BaseModel = Base  # type: ignore

        class FloatField:
            def __init__(self) -> None:
                self.count = 0

            def digits(self, _env: object) -> tuple[int, int]:
                self.count += 1
                return 16, 2

        class Rec:
            def __init__(self) -> None:
                self.m2o = Base(1)
                self.price = 1.0
                self.env = object()
                self._fields = {"m2o": object(), "price": FloatField()}
                self._written: list[dict[str, object]] = []

            def __getitem__(self, name: str) -> object:
                return getattr(self, name)

            def with_context(self, **_kw: object) -> "Rec":
                return self

            def write(self, vals: dict[str, object]) -> None:
                self._written.append(vals)
                for k, v in vals.items():
                    setattr(self, k, v)

        rec = Rec()
        new_vals = {"m2o": Base(1), "price": 1.0}
        changed = helpers.write_if_changed(cast(Any, rec), new_vals)
        self.assertFalse(changed)
        self.assertEqual(rec._written, [])
        self.assertEqual(rec._fields["price"].count, 1)

    def test_write_if_changed_many2one_changed(self) -> None:
        class Base:
            def __len__(self) -> int:
                return 1

            def __init__(self, rec_id: int) -> None:
                self.id = rec_id

        helpers.models.BaseModel = Base  # type: ignore

        class Rec:
            def __init__(self) -> None:
                self.m2o = Base(1)
                self._fields = {"m2o": object()}
                self.env = object()
                self._written: list[dict[str, Base]] = []

            def __getitem__(self, name: str) -> Base:
                return getattr(self, name)

            def with_context(self, **_kw: object) -> "Rec":
                return self

            def write(self, vals: dict[str, Base]) -> None:
                self._written.append(vals)
                for k, v in vals.items():
                    setattr(self, k, v)

        rec = Rec()
        new = Base(2)
        changed = helpers.write_if_changed(cast(Any, rec), {"m2o": new})
        self.assertTrue(changed)
        self.assertEqual(rec.m2o.id, 2)
        self.assertEqual(rec._written, [{"m2o": new}])

    def test_shopify_api_error_sku_missing(self) -> None:
        class Prod(BaseModel):
            id: str

        prod = Prod(id="gid/1")
        err = helpers.ShopifyApiError("msg", shopify_record=prod)
        self.assertEqual(err.sku, "")

    def test_shopify_api_error_name_missing_then_present(self) -> None:
        class Prod(BaseModel):
            id: str = "gid/1"
            title: str = "foo"
            variants: list = []

        err = helpers.ShopifyApiError("msg", shopify_record=Prod())
        with patch.object(helpers.OdooDataError, "__str__", lambda _exc: "err"):
            txt = str(err)
            self.assertIn("[foo]", txt)

    def test_shopify_product_id_no_record(self) -> None:
        err = helpers.ShopifyApiError("msg")
        self.assertEqual(err.shopify_product_id, "")

    def test_shopify_api_error_no_shopify_id(self) -> None:
        class Prod(BaseModel):
            id: str | None = None
            title: str = "n"
            variants: list = []

        err = helpers.ShopifyApiError("msg", shopify_record=Prod())
        with patch.object(helpers.OdooDataError, "__str__", lambda _exc: "msg"):
            txt = str(err)
            self.assertNotIn("Shopify ID", txt)

    def test_parse_sku_no_value_error(self) -> None:
        with self.assertRaises(helpers.ShopifyMissingSkuFieldError):
            helpers.parse_shopify_sku_field_to_sku_and_bin(" - Bin")
