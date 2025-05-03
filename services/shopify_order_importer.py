import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Literal

from odoo.api import Environment

from .shopify_service import ShopifyService
from .shopify_client import (
    AddressFields,
    GetOrdersOrdersNodes,
    OrderFieldsCustomer,
)
from ..utils.shopify_helpers import (
    DEFAULT_DATETIME,
    SHOPIFY_PAGE_SIZE,
    OdooDataError,
    ShopifyDataError,
    parse_shopify_datetime_to_utc,
    format_datetime_for_shopify,
    parse_shopify_id_from_gid,
    write_if_changed,
    parse_shopify_sku_field_to_sku_and_bin,
)

_logger = logging.getLogger(__name__)


class OrderImporter:
    def __init__(self, env: Environment, sync_record: "odoo.model.shopify_sync") -> None:
        self.env = env
        self.shopify_service = ShopifyService(env, sync_record)
        self.sync_record = sync_record
        self._last_heartbeat = time.monotonic()

    def get_last_import_time(self) -> datetime:
        if last_import_time_str := self.env["ir.config_parameter"].get_param("shopify.last_order_import_time"):
            _logger.debug(f"Last order import time from config: {last_import_time_str}")
            return parse_shopify_datetime_to_utc(last_import_time_str)
        _logger.debug(f"Last order import time not found in config, using default: {DEFAULT_DATETIME}")
        return DEFAULT_DATETIME

    def import_orders_since_last_import(self) -> int:
        last_import_time = self.get_last_import_time() - timedelta(seconds=2)
        _logger.info(f"Importing orders since last import time: {last_import_time}")
        filter_query = f'updated_at:>"{format_datetime_for_shopify(last_import_time)}"'
        _logger.debug(f"Filter query for orders: {filter_query}")
        self.import_orders_from_query(query=filter_query)
        return self.sync_record.total_count

    def import_orders_from_query(self, query: str | None = None) -> bool:
        client = self.shopify_service.client
        cursor: Optional[str] = None
        has_next_page = True
        while has_next_page:
            orders_page = client.get_orders(query=query, cursor=cursor, limit=SHOPIFY_PAGE_SIZE)
            orders = orders_page.nodes
            if not orders:
                _logger.debug("No more orders to import.")
                break
            self.sync_record.write({"total_count": self.sync_record.total_count + len(orders)})
            self.import_orders(orders)
            cursor = orders_page.page_info.end_cursor
            has_next_page = orders_page.page_info.has_next_page
        _logger.debug(f"Finished importing order query: {self.sync_record.completed_str}")
        return True

    def import_order_by_id(self, shopify_order_id: int | str) -> bool:
        _logger.info(f"Importing order by ID: {shopify_order_id}")
        filter_query = f'id:"{shopify_order_id}"'
        if self.import_orders_from_query(query=filter_query):
            _logger.info(f"Successfully imported order with ID: {shopify_order_id}")
            return True
        _logger.warning(f"Failed to import order with ID: {shopify_order_id}")
        return False

    def import_orders(self, orders: list[GetOrdersOrdersNodes]) -> None:
        for order_index, order in enumerate(orders, start=1):
            _logger.debug(
                f"Importing order index {order_index}.  Imported {self.sync_record.completed_str} on this page of {len(orders)}: {order.id} {order.name}"
            )
            try:
                if self.import_order(order):
                    self.sync_record.updated_count += 1
            except (OdooDataError, ShopifyDataError):
                raise
            except Exception as error:
                exception = ShopifyDataError("Unexpected error in import_order", shopify_record=order)
                _logger.error(exception)
                raise exception from error
            if order_index % (SHOPIFY_PAGE_SIZE // 2) == 0 or order_index == len(orders):
                self.sync_record.last_import_start_time = order.updated_at
                _logger.debug(f"Committing after {order_index} orders")
                self.env.cr.commit()
            if time.monotonic() - self._last_heartbeat > 30:
                self.sync_record.write({})
                self._last_heartbeat = time.monotonic()
                self.env.cr.commit()

    def _get_or_create_partner(self, customer: OrderFieldsCustomer) -> "odoo.model.res_partner":
        if not customer:
            raise ShopifyDataError("Missing customer information")
        email = customer.default_email_address.email_address if customer.default_email_address else ""
        partner = self.env["res.partner"].search(
            [
                "|",
                ("shopify_customer_id", "=", parse_shopify_id_from_gid(customer.id)),
                ("email", "=", email),
            ],
            limit=1,
        )
        partner_values: "odoo.values.res_partner" = {
            "shopify_customer_id": parse_shopify_id_from_gid(customer.id),
            "name": f"{customer.first_name or ''} {customer.last_name or ''}".strip() or email,
            "email": email,
        }
        if partner:
            write_if_changed(partner, partner_values)
        else:
            partner = self.env["res.partner"].create(partner_values)
        return partner

    def _get_or_create_address(
        self, mailing_address: AddressFields, partner: "odoo.model.res_partner", address_type: Literal["delivery", "invoice"]
    ) -> "odoo.model.res_partner":
        if not mailing_address:
            return partner

        country = (
            self.env["res.country"].search([("code", "=", mailing_address.country_code_v_2.value)], limit=1)
            if mailing_address.country_code_v_2
            else False
        )
        state = (
            self.env["res.country.state"].search(
                (
                    [("code", "=", mailing_address.province_code), ("country_id", "=", country.id)]
                    if country
                    else [("code", "=", mailing_address.province_code)]
                ),
                limit=1,
            )
            if mailing_address.province_code
            else False
        )

        shopify_address_id = parse_shopify_id_from_gid(mailing_address.id)
        address = self.env["res.partner"].search([("shopify_address_id", "=", shopify_address_id)], limit=1)
        address_values: "odoo.values.res_partner" = {
            "shopify_address_id": shopify_address_id,
            "parent_id": partner.id,
            "type": address_type,
            "name": mailing_address.name or partner.name,
            "street": mailing_address.address_1,
            "street2": mailing_address.address_2,
            "city": mailing_address.city,
            "zip": mailing_address.zip,
            "state_id": state.id if state else False,
            "country_id": country.id if country else False,
            "phone": mailing_address.phone,
        }
        if address:
            write_if_changed(address, address_values)
        else:
            address = self.env["res.partner"].create(address_values)
        return address

    def import_order(self, shopify_order: GetOrdersOrdersNodes) -> bool:
        partner = self._get_or_create_partner(shopify_order.customer)
        shipping_partner = self._get_or_create_address(shopify_order.shipping_address, partner, "delivery")
        billing_partner = self._get_or_create_address(shopify_order.billing_address, partner, "invoice")

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
                _logger.warning("Missing SKU for Shopify line %s in order %s", shopify_line.id, shopify_order.name)
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
                _logger.warning("No matching product for SKU %s in order %s", sku, shopify_order.name)
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
