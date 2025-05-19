from datetime import datetime, timedelta, UTC

from unittest import TestCase
from ..services.shopify.helpers import (
    parse_shopify_datetime_to_utc,
    format_datetime_for_shopify,
    parse_shopify_id_from_gid,
    format_shopify_gid_from_id,
    parse_shopify_sku_field_to_sku_and_bin,
    format_sku_bin_for_shopify,
    normalize_str,
    normalize_phone,
    normalize_email,
    ShopifyMissingSkuFieldError,
    image_order_key,
)


class DummyImage:
    def __init__(self, sequence: int | None, create_date: datetime | None) -> None:
        self.sequence = sequence
        self.create_date = create_date


class TestShopifyHelpers(TestCase):
    def test_parse_and_format_datetime_round_trip(self) -> None:
        original = datetime(2025, 5, 17, 12, 45, 30, tzinfo=UTC)
        formatted = format_datetime_for_shopify(original)
        parsed = parse_shopify_datetime_to_utc(formatted)
        self.assertEqual(parsed, original.replace(tzinfo=None))

    def test_parse_shopify_id_from_gid(self) -> None:
        gid = "gid://shopify/Product/123456789"
        self.assertEqual(parse_shopify_id_from_gid(gid), "123456789")

    def test_format_shopify_gid_from_id(self) -> None:
        self.assertEqual(format_shopify_gid_from_id("Order", 987), "gid://shopify/Order/987")

    def test_parse_sku_and_bin(self) -> None:
        sku, bin_location = parse_shopify_sku_field_to_sku_and_bin("ABC123 - BIN2")
        self.assertEqual(sku, "ABC123")
        self.assertEqual(bin_location, "BIN2")

    def test_parse_sku_without_bin(self) -> None:
        sku, bin_location = parse_shopify_sku_field_to_sku_and_bin("XYZ789")
        self.assertEqual(sku, "XYZ789")
        self.assertEqual(bin_location, "")

    def test_parse_sku_raises_on_empty(self) -> None:
        with self.assertRaises(ShopifyMissingSkuFieldError):
            parse_shopify_sku_field_to_sku_and_bin("")

    def test_format_sku_bin_for_shopify(self) -> None:
        self.assertEqual(format_sku_bin_for_shopify("PART1", "SHELF5"), "PART1 - SHELF5")

    def test_normalize_str_email_phone(self) -> None:
        self.assertEqual(normalize_str("  Hello "), "hello")
        self.assertEqual(normalize_email("  TEST@Example.Com "), "test@example.com")
        self.assertEqual(normalize_phone("(555) 123-4567"), "5551234567")

    def test_image_order_key_sorting(self) -> None:
        now = datetime.now()
        older = now - timedelta(days=1)
        image_a = DummyImage(sequence=1, create_date=now)
        image_b = DummyImage(sequence=1, create_date=older)
        image_c = DummyImage(sequence=0, create_date=now)
        ordered = sorted([image_a, image_b, image_c], key=image_order_key)
        self.assertEqual(ordered, [image_c, image_b, image_a])
