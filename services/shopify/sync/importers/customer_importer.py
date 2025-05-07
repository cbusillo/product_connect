import logging
import re

from odoo.api import Environment

from ...gql import (
    Client,
    AddressFields,
    GetCustomersCustomersNodes,
    OrderFieldsCustomer,
)
from ..base import ShopifyBaseImporter, ShopifyPage
from ...helpers import (
    parse_shopify_id_from_gid,
    write_if_changed,
)

_logger = logging.getLogger(__name__)


class CustomerImporter(ShopifyBaseImporter[GetCustomersCustomersNodes]):
    def __init__(self, env: Environment, sync_record: "odoo.model.shopify_sync") -> None:
        super().__init__(env, sync_record)

    def _fetch_page(self, client: Client, query: str | None, cursor: str | None) -> ShopifyPage[GetCustomersCustomersNodes]:
        return client.get_customers(query=query, cursor=cursor, limit=self.page_size)

    def _import_one(self, shopify_customer: GetCustomersCustomersNodes) -> bool:
        return self.import_customer(shopify_customer)

    def import_customers_since_last_import(self) -> int:
        return self.run_since_last_import("customer")

    def _get_or_create_category(self, name: str) -> "odoo.model.res_partner_category":
        category = self.env["res.partner.category"].search([("name", "=", name)], limit=1)
        if not category:
            category = self.env["res.partner.category"].create({"name": name})
        return category

    def import_customer(self, shopify_customer: OrderFieldsCustomer | GetCustomersCustomersNodes) -> bool:
        shopify_customer_id = parse_shopify_id_from_gid(shopify_customer.id)
        tags = [t.strip().lower() for t in getattr(shopify_customer, "tags", [])]
        is_ebay = "ebay" in tags

        shopify_email = (
            shopify_customer.default_email_address.email_address
            if shopify_customer.default_email_address and shopify_customer.default_email_address.email_address
            else None
        )
        shopify_email = shopify_email.strip() if shopify_email else ""

        if shopify_customer.default_phone_number and shopify_customer.default_phone_number.phone_number:
            shopify_phone = shopify_customer.default_phone_number.phone_number
        elif shopify_customer.default_address and shopify_customer.default_address.phone:
            shopify_phone = shopify_customer.default_address.phone
        else:
            shopify_phone = None
        shopify_phone = shopify_phone.strip() if shopify_phone else ""

        # ------------------------------------------------------------------ #
        # partner resolution – first by Shopify‑ID, then by e‑mail
        # ------------------------------------------------------------------ #
        partner = self.env["res.partner"].search([("shopify_customer_id", "=", shopify_customer_id)], limit=1)
        if not partner and shopify_email:
            partner = self.env["res.partner"].search([("email", "=", shopify_email)], limit=1)
        if not partner and shopify_phone:
            partner = self.env["res.partner"].search([("phone", "=", shopify_phone)], limit=1)

        # ------------------------------------------------------------------ #
        # fallback when Shopify omits e‑mail / phone
        # ------------------------------------------------------------------ #
        email = shopify_email or (partner.email if partner else "")
        phone = shopify_phone or (partner.phone if partner else "")

        # extract eBay username only when the customer carries the “eBay” tag
        last_name_raw = (shopify_customer.last_name or "").strip()
        ebay_username = ""
        if is_ebay:
            ebay_match = re.search(r"\(([^)]+)\)$", last_name_raw)
            if ebay_match:
                ebay_username = ebay_match.group(1).strip()
                last_name_raw = re.sub(r"\s*\([^)]+\)\s*$", "", last_name_raw)
        last_name = last_name_raw

        first_name = (shopify_customer.first_name or "").strip()
        name_parts = [first_name, last_name]
        name = re.sub(r"\s{2,}", " ", " ".join(p for p in name_parts if p)).strip() or email
        partner_vals: "odoo.values.res_partner" = {
            "shopify_customer_id": shopify_customer_id,
            "name": name,
            "ebay_username": ebay_username or False,
        }
        if email:
            partner_vals["email"] = email
        if phone:
            partner_vals["phone"] = phone
        created = False

        if not partner:
            partner = self.env["res.partner"].create(partner_vals)
            created = changed = True
        else:
            changed = write_if_changed(partner, partner_vals)

        if created:
            shopify_category = self._get_or_create_category("Shopify")
            partner.write({"category_id": [(4, shopify_category.id)]})
            changed = True

        # ------------------------------------------------------------------ #
        # process addresses (default & additional)
        # ------------------------------------------------------------------ #
        addresses_changed = False
        addresses: list[AddressFields] = []
        if shopify_customer.default_address:
            addresses.append(shopify_customer.default_address)
        if shopify_customer.addresses_v_2 and shopify_customer.addresses_v_2.nodes:
            addresses.extend(shopify_customer.addresses_v_2.nodes)
        for addr in addresses:
            addresses_changed |= self.process_address(addr, partner)
        if addresses_changed:
            changed = True
        return changed

    def process_address(self, address: AddressFields, partner: "odoo.model.res_partner") -> bool:
        shopify_address_id = parse_shopify_id_from_gid(address.id)

        # normalize country / state once
        country = (
            self.env["res.country"].search([("code", "=", address.country_code_v_2.value)], limit=1)
            if address.country_code_v_2
            else False
        )
        state = (
            self.env["res.country.state"].search(
                (
                    [("code", "=", address.province_code), ("country_id", "=", country.id)]
                    if country
                    else [("code", "=", address.province_code)]
                ),
                limit=1,
            )
            if address.province_code
            else False
        )

        # see if a record already exists by Shopify‑ID
        existing_address = self.env["res.partner"].search([("shopify_address_id", "=", shopify_address_id)], limit=1)

        # do we need a separate delivery address?
        is_different_address = any(
            (
                address.address_1 != partner.street,
                address.address_2 != partner.street2,
                address.city != partner.city,
                address.zip != partner.zip,
                country and country.id != partner.country_id.id,
                state and state.id != partner.state_id.id,
            )
        )

        # second chance: identical child already linked (same data, different Shopify‑ID)
        if not existing_address and is_different_address:
            duplicate = partner.child_ids.filtered(
                lambda a: a.street == address.address_1
                and a.street2 == address.address_2
                and a.city == address.city
                and a.zip == address.zip
                and (not country or a.country_id.id == country.id)
                and (not state or a.state_id.id == state.id)
            )
            if duplicate:
                existing_address = duplicate[0]

        address_type = "delivery" if is_different_address else "contact"

        # Prepare address values
        address_values: "odoo.values.res_partner" = {
            "shopify_address_id": shopify_address_id,
            "parent_id": partner.id if address_type == "delivery" else False,
            "type": address_type,
            # keep child.name only if it differs from the parent to avoid “X, X” display names
            "name": "" if (address.name or "").strip() == (partner.name or "").strip() else (address.name or ""),
            "street": (address.address_1 or "").strip(),
            "street2": (address.address_2 or "").strip(),
            "city": (address.city or "").strip(),
            "zip": (address.zip or "").strip(),
            "state_id": state.id if state else False,
            "country_id": country.id if country else False,
        }
        if address.phone:
            address_values["phone"] = address.phone.strip()

        # Update or create the address
        if existing_address:
            changed = write_if_changed(existing_address, address_values)
            return changed
        elif is_different_address:
            shopify_category = self._get_or_create_category("Shopify")
            address_values["category_id"] = [(6, 0, list(set(partner.category_id.ids + [shopify_category.id])))]
            self.env["res.partner"].create(address_values)
            return True
        else:
            # Update the main partner with address info if not different
            main_address_values: "odoo.values.res_partner" = {
                "street": (address.address_1 or "").strip(),
                "street2": (address.address_2 or "").strip(),
                "city": (address.city or "").strip(),
                "zip": (address.zip or "").strip(),
                "state_id": state.id if state else False,
                "country_id": country.id if country else False,
            }
            if address.phone:
                main_address_values["phone"] = address.phone.strip()
            changed = write_if_changed(partner, main_address_values)
            return changed
