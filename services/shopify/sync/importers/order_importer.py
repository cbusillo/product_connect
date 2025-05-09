import logging
import re
import unicodedata
from decimal import Decimal

from odoo.api import Environment

from ...gql import (
    Client,
    GetOrdersOrdersNodes,
    OrderFieldsShippingAddress,
    OrderFieldsBillingAddress,
    CurrencyCode,
    OrderLineItemFields,
)
from ..base import ShopifyBaseImporter, ShopifyPage
from ...helpers import (
    ShopifyDataError,
    parse_shopify_id_from_gid,
    write_if_changed,
    parse_shopify_sku_field_to_sku_and_bin,
    PriceSet,
)

from .customer_importer import CustomerImporter, AddressRole

_logger = logging.getLogger(__name__)


class OrderImporter(ShopifyBaseImporter[GetOrdersOrdersNodes]):
    PROVIDER_PREFIXES = [
        "royal mail",
        "fedex",
        "ups",
        "usps",
        "dhl",
        "freight",
    ]

    _CARRIER_PUNCTUATION_PATTERN = re.compile(r"[^\w\s\-]")

    @classmethod
    def _normalise_carrier_name(cls, name: str) -> str:
        cleaned = cls._CARRIER_PUNCTUATION_PATTERN.sub("", name or "")
        # noinspection SpellCheckingInspection
        return unicodedata.normalize("NFKD", cleaned).strip().casefold()

    @staticmethod
    def _get_amount_for_order_currency(price_set: PriceSet, order_currency: CurrencyCode) -> Decimal:
        if not price_set:
            return Decimal("0")
        if (
            price_set.shop_money
            and price_set.shop_money.currency_code
            and price_set.shop_money.currency_code.value == order_currency
        ):
            return price_set.shop_money.amount
        if price_set.presentment_money:
            return price_set.presentment_money.amount
        return Decimal("0")

    @staticmethod
    def _get_discount_allocation_amount(line: OrderLineItemFields, order_currency: CurrencyCode) -> Decimal:
        return sum(
            (
                OrderImporter._get_amount_for_order_currency(allocation.allocated_amount_set, order_currency)
                for allocation in line.discount_allocations
                if allocation and allocation.allocated_amount_set
            ),
            Decimal("0"),
        )

    def __init__(self, env: Environment, sync_record: "odoo.model.shopify_sync") -> None:
        super().__init__(env, sync_record)

    def _fetch_page(self, client: Client, query: str | None, cursor: str | None) -> ShopifyPage[GetOrdersOrdersNodes]:
        return client.get_orders(query=query, cursor=cursor, limit=self.page_size)

    def import_orders_since_last_import(self) -> int:
        return self.run_since_last_import("order")

    def _import_one(self, shopify_order: GetOrdersOrdersNodes) -> bool:
        if not shopify_order.customer:
            _logger.warning(f"Order {shopify_order.name} has no customer; skipping order")
            return False
        CustomerImporter(self.env, self.sync_record).import_customer(shopify_order.customer)

        shopify_customer_id = parse_shopify_id_from_gid(shopify_order.customer.id)
        partner = self.env["res.partner"].search([("shopify_customer_id", "=", shopify_customer_id)], limit=1)
        if not partner:
            _logger.warning(f"Customer {shopify_customer_id} not found for order {shopify_order.name}; skipping order")
            return False

        shipping_partner = self._resolve_address(shopify_order.shipping_address, partner, role="shipping")
        billing_partner = self._resolve_address(shopify_order.billing_address, partner, role="billing")

        currency = self.env["res.currency"].search([("name", "=", shopify_order.currency_code.value)], limit=1)
        if not currency:
            raise ShopifyDataError(f"Unsupported currency {shopify_order.currency_code.value}")

        shopify_order_id = parse_shopify_id_from_gid(shopify_order.id)
        existing_order = (
            self.env["sale.order"]
            .with_context(skip_shopify_sync=True)
            .search([("shopify_order_id", "=", shopify_order_id)], limit=1)
        )

        order_values: "odoo.values.sale_order" = {
            "shopify_order_id": shopify_order_id,
            "name": shopify_order.name,
            "date_order": shopify_order.created_at,
            "partner_id": partner.id,
            "partner_invoice_id": billing_partner.id,
            "partner_shipping_id": shipping_partner.id,
            "currency_id": currency.id,
        }

        if existing_order:
            changed = write_if_changed(existing_order, order_values)
            changed |= self._sync_order_lines(existing_order, shopify_order)
            return changed
        new_order = self.env["sale.order"].with_context(skip_shopify_sync=True).create(order_values)
        self._sync_order_lines(new_order, shopify_order)
        return True

    def _sync_order_lines(self, odoo_order: "odoo.model.sale_order", shopify_order: GetOrdersOrdersNodes) -> bool:
        changed = False
        line_items = shopify_order.line_items.nodes

        existing_by_line_id: dict[str, "odoo.model.sale_order_line"] = {
            line.shopify_order_line_id: line for line in odoo_order.order_line
        }

        # bulk product pre‑fetch
        sku_list: list[str] = []
        variant_id_list: list[str] = []
        for line in line_items:
            try:
                sku, _ = parse_shopify_sku_field_to_sku_and_bin(line.sku or "")
            except ShopifyDataError:
                continue
            sku_list.append(sku)
            variant_id_list.append(parse_shopify_id_from_gid(line.variant.id))
        if sku_list or variant_id_list:
            products = self.env["product.product"].search(
                [
                    "|",
                    ("default_code", "in", sku_list),
                    ("shopify_variant_id", "in", variant_id_list),
                ]
            )
        else:
            products = self.env["product.product"].browse()
        product_by_sku: dict[str, "odoo.model.product_product"] = {p.default_code: p for p in products if p.default_code}
        product_by_variant: dict[str, "odoo.model.product_product"] = {
            p.shopify_variant_id: p for p in products if p.shopify_variant_id
        }

        for shopify_line in line_items:
            shopify_line_item_id = parse_shopify_id_from_gid(shopify_line.id)

            try:
                sku, _ = parse_shopify_sku_field_to_sku_and_bin(shopify_line.sku or "")
            except ShopifyDataError:
                _logger.warning(f"Missing SKU for Shopify line {shopify_line.id} in order {shopify_order.name}")
                continue

            product = product_by_sku.get(sku) or product_by_variant.get(parse_shopify_id_from_gid(shopify_line.variant.id))
            if not product:
                _logger.warning(f"No matching product for SKU {sku} in order {shopify_order.name}")
                continue

            price_set = shopify_line.original_unit_price_set
            discount_amount_dec = self._get_discount_allocation_amount(shopify_line, shopify_order.currency_code.value)
            if not price_set or not price_set.presentment_money:
                _logger.warning(f"Missing price for line {shopify_line.id} in order {shopify_order.name}; skipping line")
                continue
            price_unit_dec = self._get_amount_for_order_currency(price_set, shopify_order.currency_code.value)
            if discount_amount_dec and shopify_line.quantity:
                price_unit_dec -= discount_amount_dec / shopify_line.quantity
            price_unit_val = float(price_unit_dec)
            line_vals: "odoo.values.sale_order_line" = {
                "order_id": odoo_order.id,
                "product_id": product.id,
                "product_uom_qty": shopify_line.quantity,
                "price_unit": price_unit_val,
                "name": shopify_line.name,
                "shopify_order_line_id": shopify_line_item_id,
            }
            existing_line = existing_by_line_id.pop(shopify_line_item_id, None)
            if existing_line:
                changed |= write_if_changed(existing_line, line_vals)
            else:
                self.env["sale.order.line"].with_context(skip_shopify_sync=True).create(line_vals)
                changed = True

        shipping_changed = self._apply_shipping(odoo_order, shopify_order)
        discount_changed = self._apply_global_discount(odoo_order, shopify_order)
        changed |= shipping_changed or discount_changed

        for tax_line in shopify_order.tax_lines:
            if not tax_line or not tax_line.price_set:
                continue
            tax_amount_dec = self._get_amount_for_order_currency(tax_line.price_set, shopify_order.currency_code.value)
            if tax_amount_dec == 0:
                continue
            tax_product = self._get_special_product("TAX", tax_line.title or "Tax")
            tax_key = f"tax:{parse_shopify_id_from_gid(shopify_order.id)}:{tax_line.title or tax_line.rate_percentage}"
            tax_vals: "odoo.values.sale_order_line" = {
                "order_id": odoo_order.id,
                "product_id": tax_product.id,
                "product_uom_qty": 1,
                "price_unit": float(tax_amount_dec),
                "name": tax_line.title or "Tax",
                "shopify_order_line_id": tax_key,
            }
            existing_tax = existing_by_line_id.pop(tax_key, None)
            if existing_tax:
                changed |= write_if_changed(existing_tax, tax_vals)
            else:
                self.env["sale.order.line"].with_context(skip_shopify_sync=True).create(tax_vals)
                changed = True

        if existing_by_line_id:
            self.env["sale.order.line"].browse([l.id for l in existing_by_line_id.values()]).unlink()
            changed = True

        return changed

    def _apply_shipping(self, odoo_order: "odoo.model.sale_order", shopify_order: GetOrdersOrdersNodes) -> bool:
        shipping_lines = shopify_order.shipping_lines.nodes
        if not shipping_lines:
            delivery_lines = odoo_order.order_line.filtered("is_delivery")
            if delivery_lines:
                delivery_lines.unlink()
                return True
            return False

        shipping_total_dec = sum(
            self._get_amount_for_order_currency(
                (shipping_line.current_discounted_price_set or shipping_line.original_price_set),
                shopify_order.currency_code.value,
            )
            for shipping_line in shipping_lines
            if shipping_line
        )
        if shipping_total_dec == 0:
            return False

        raw_name = shipping_lines[0].title or "Shopify Shipping"
        carrier_name = raw_name.strip()
        normalised = self._normalise_carrier_name(carrier_name)
        carrier = self.env["delivery.carrier"].search([("name", "ilike", normalised)], limit=1)
        if not carrier:
            provider, _ = self._parse_provider_and_service(carrier_name)
            product_code = provider.upper()[:4] or "SHIP"
            shipping_product = self._get_special_product(product_code, carrier_name)
            carrier = self.env["delivery.carrier"].create(
                {
                    "name": carrier_name,
                    "delivery_type": "fixed",
                    "product_id": shipping_product.id,
                    "company_id": self.env.company.id,
                    "fixed_price": 0.0,
                    "margin": 0.0,
                }
            )
        if not carrier.tax_ids:
            default_sale_tax = self.env["account.tax"].search([("type_tax_use", "=", "sale")], limit=1)
            if default_sale_tax:
                fiscal_position = odoo_order.fiscal_position_id or odoo_order.partner_id.property_account_position_id
                mapped_tax = fiscal_position.map_tax(default_sale_tax) if fiscal_position else default_sale_tax
                carrier.tax_ids = [(6, 0, mapped_tax.ids)]

        odoo_order.order_line.filtered("is_delivery").unlink()
        odoo_order.set_delivery_line(carrier, float(shipping_total_dec))
        return True

    def _apply_global_discount(self, odoo_order: "odoo.model.sale_order", shopify_order: GetOrdersOrdersNodes) -> bool:
        discount_amount = self._get_amount_for_order_currency(
            shopify_order.total_discounts_set, shopify_order.currency_code.value
        )

        # locate any existing discount line by matching the discount product
        discount_product = self.env["product.product"].search([("default_code", "=", "DISC")], limit=1)
        if not discount_product:
            discount_product = self._get_special_product("DISC", "Discount")
        discount_lines = odoo_order.order_line.filtered(lambda l: l.product_id.id == discount_product.id)

        if discount_amount == 0:
            if discount_lines:
                discount_lines.unlink()
                return True
            return False

        discount_vals: "odoo.values.sale_order_line" = {
            "order_id": odoo_order.id,
            "product_id": discount_product.id,
            "product_uom_qty": 1,
            "price_unit": -float(discount_amount),
            "name": "Discount",
        }

        if discount_lines:
            return write_if_changed(discount_lines[0], discount_vals)

        self.env["sale.order.line"].with_context(skip_shopify_sync=True).create(discount_vals)
        return True

    def _parse_provider_and_service(self, title: str) -> tuple[str, str]:
        cleaned_title = re.sub(r"\s+", " ", title or "").strip()
        cleaned_title = re.sub(r"[®™]", "", cleaned_title)
        lowered_title = cleaned_title.lower()
        for prefix in self.PROVIDER_PREFIXES:
            if lowered_title.startswith(prefix):
                provider = cleaned_title[: len(prefix)].strip()
                service = cleaned_title[len(prefix) :].strip(" -")
                return provider, service
        if "free" in lowered_title:
            return "Free Shipping", cleaned_title
        if any(word in lowered_title for word in ("economy", "standard")):
            return "Generic", cleaned_title
        first, *rest = cleaned_title.split(" ", 1)
        return first, rest[0] if rest else ""

    def _get_special_product(self, default_code: str, name: str) -> "odoo.model.product_product":
        product = self.env["product.product"].search([("default_code", "=", default_code)], limit=1)
        if product:
            return product
        return self.env["product.product"].create(
            {
                "name": name,
                "default_code": default_code,
                "type": "service",
                "sale_ok": True,
                "purchase_ok": False,
                "invoice_policy": "order",
            }
        )

    def _resolve_address(
        self,
        shopify_address: OrderFieldsShippingAddress | OrderFieldsBillingAddress,
        partner: "odoo.model.res_partner",
        role: AddressRole,
    ) -> "odoo.model.res_partner":
        if not shopify_address:
            return partner

        def _find_partner() -> "odoo.model.res_partner":
            return self.env["res.partner"].search(
                [("shopify_address_id", "=", parse_shopify_id_from_gid(shopify_address.id))], limit=1
            )

        address_partner = _find_partner()
        if address_partner:
            return address_partner

        CustomerImporter(self.env, self.sync_record).process_address(shopify_address, partner, role=role)
        return _find_partner() or partner
