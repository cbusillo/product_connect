import logging

from odoo.api import Environment

from ...gql import Client, GetOrdersOrdersNodes, OrderFieldsShippingAddress, OrderFieldsBillingAddress
from ..base import ShopifyBaseImporter, ShopifyPage
from ...helpers import (
    ShopifyDataError,
    parse_shopify_id_from_gid,
    write_if_changed,
    parse_shopify_sku_field_to_sku_and_bin,
)

from .customer_importer import CustomerImporter

_logger = logging.getLogger(__name__)


class OrderImporter(ShopifyBaseImporter[GetOrdersOrdersNodes]):
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

        shipping_partner = self._resolve_address(shopify_order.shipping_address, partner)
        billing_partner = self._resolve_address(shopify_order.billing_address, partner)

        # Odoo 18 keeps ISO code in the `name` column (iso_code field no longer exists)
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
            line.shopify_order_line_id: line for line in odoo_order.order_line if getattr(line, "shopify_order_line_id", False)
        }

        for shopify_line in line_items:
            shopify_line_item_id = parse_shopify_id_from_gid(shopify_line.id)

            try:
                sku, _ = parse_shopify_sku_field_to_sku_and_bin(shopify_line.sku or "")
            except ShopifyDataError:
                _logger.warning(f"Missing SKU for Shopify line {shopify_line.id} in order {shopify_order.name}")
                continue

            product = self.env["product.product"].search(
                [
                    "|",
                    ("default_code", "=", sku),
                    ("shopify_variant_id", "=", parse_shopify_id_from_gid(shopify_line.variant.id)),
                ],
                limit=1,
            )
            if not product:
                _logger.warning(f"No matching product for SKU {sku} in order {shopify_order.name}")
                continue

            line_vals: "odoo.values.sale_order_line" = {
                "order_id": odoo_order.id,
                "product_id": product.id,
                "product_uom_qty": shopify_line.quantity,
                "price_unit": float(shopify_line.original_unit_price_set.presentment_money.amount),
                "name": shopify_line.name,
                "shopify_order_line_id": shopify_line_item_id,
            }
            existing_line = existing_by_line_id.pop(shopify_line_item_id, None)
            if existing_line:
                changed = write_if_changed(existing_line, line_vals)
            else:
                self.env["sale.order.line"].with_context(skip_shopify_sync=True).create(line_vals)
                changed = True

        for removed_line in existing_by_line_id.values():
            removed_line.unlink()
            changed = True

        return changed

    # ------------------------------------------------------------------ #
    # helpers                                                            #
    # ------------------------------------------------------------------ #
    def _resolve_address(
        self,
        shopify_address: OrderFieldsShippingAddress | OrderFieldsBillingAddress,
        partner: "odoo.model.res_partner",
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

        # create via CustomerImporter, then re‑search
        CustomerImporter(self.env, self.sync_record).process_address(shopify_address, partner)
        return _find_partner() or partner
