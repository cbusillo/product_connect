import logging
import re

from odoo.api import Environment
from odoo.addons.phone_validation.tools.phone_validation import phone_format

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
    normalize_str,
    normalize_phone,
    normalize_email,
)
from typing import Literal

_logger = logging.getLogger(__name__)


AddressRole = Literal["shipping", "billing"]
AddressType = Literal["contact", "delivery", "invoice"]


class CustomerImporter(ShopifyBaseImporter[GetCustomersCustomersNodes]):
    def __init__(self, env: Environment, sync_record: "odoo.model.shopify_sync") -> None:
        super().__init__(env, sync_record)

    def _fetch_page(self, client: Client, query: str | None, cursor: str | None) -> ShopifyPage[GetCustomersCustomersNodes]:
        return client.get_customers(query=query, cursor=cursor, limit=self.page_size)

    def _import_one(self, shopify_customer: GetCustomersCustomersNodes) -> bool:
        return self.import_customer(shopify_customer)

    def _get_or_create_category(self, name: str) -> "odoo.model.res_partner_category":
        category = self.env["res.partner.category"].search([("name", "=", name)], limit=1)
        if not category:
            category = self.env["res.partner.category"].create({"name": name})
        return category

    def import_customers_since_last_import(self) -> int:
        return self.run_since_last_import("customer")

    def _format_phone_number(self, phone: str) -> str:
        country = self.env.company.country_id or self.env["res.country"].search([("code", "=", "US")], limit=1)
        if not country:
            return phone.strip()
        phone_code = int(country.phone_code or 0)
        return phone_format(phone, country.code, phone_code, force_format="E164", raise_exception=False)

    def import_customer(self, shopify_customer: OrderFieldsCustomer | GetCustomersCustomersNodes) -> bool:
        shopify_customer_id = parse_shopify_id_from_gid(shopify_customer.id)
        tags = [t.strip().lower() for t in shopify_customer.tags]
        is_ebay = "ebay" in tags

        if shopify_customer.default_email_address and shopify_customer.default_email_address.email_address:
            shopify_email = normalize_email(shopify_customer.default_email_address.email_address)
        else:
            raw_email_fallback = vars(shopify_customer).get("email", "")
            shopify_email = normalize_email(raw_email_fallback)

        if shopify_customer.default_phone_number and shopify_customer.default_phone_number.phone_number:
            shopify_phone = shopify_customer.default_phone_number.phone_number
        elif shopify_customer.default_address and shopify_customer.default_address.phone:
            shopify_phone = shopify_customer.default_address.phone
        else:
            shopify_phone = None
        shopify_phone = shopify_phone.strip() if shopify_phone else ""

        partner = self.env["res.partner"].search([("shopify_customer_id", "=", shopify_customer_id)], limit=1)
        if not partner and shopify_email:
            partner = self.env["res.partner"].search([("email", "ilike", shopify_email)], limit=1)
        if not partner and shopify_phone:
            digits = normalize_phone(shopify_phone)
            wildcard_pattern = "%" + "%".join(digits) + "%"
            partner = self.env["res.partner"].search([("phone", "=ilike", wildcard_pattern)], limit=1)

        email = shopify_email or (partner.email if partner else "")
        phone = self._format_phone_number(shopify_phone) or partner.phone

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
        else:
            shopify_category = self._get_or_create_category("Shopify")
            if shopify_category not in partner.category_id:
                partner.write({"category_id": [(4, shopify_category.id)]})
                changed = True

        addresses_changed = False
        processed_ids: set[str] = set()
        addresses: list[AddressFields] = []
        if shopify_customer.default_address:
            addresses.append(shopify_customer.default_address)
        if shopify_customer.addresses_v_2 and shopify_customer.addresses_v_2.nodes:
            addresses.extend(shopify_customer.addresses_v_2.nodes)
        for address in addresses:
            address_id = address.id
            if address_id in processed_ids:
                continue
            processed_ids.add(address_id)
            addresses_changed |= self.process_address(address, partner, role="shipping")
        if addresses_changed:
            changed = True
        return changed

    def process_address(self, address: AddressFields, partner: "odoo.model.res_partner", role: AddressRole) -> bool:
        shopify_address_id = parse_shopify_id_from_gid(address.id)

        country = (
            self.env["res.country"].search([("code", "=", address.country_code_v_2.value)], limit=1)
            if address.country_code_v_2
            else False
        )

        state = False
        if country and (address.province_code or address.province):
            domain: list[tuple] = [("country_id", "=", country.id)]
            if address.province_code and address.province:
                domain = [
                    "|",
                    ("code", "=", address.province_code.strip()),
                    ("name", "ilike", address.province.strip()),
                ] + domain
            elif address.province_code:
                domain.append(("code", "=", address.province_code.strip()))
            else:
                domain.append(("name", "ilike", address.province.strip()))
            state = self.env["res.country.state"].search(domain, limit=1)

        existing_address = self.env["res.partner"].search([("shopify_address_id", "=", shopify_address_id)], limit=1)

        is_different_address = any(
            (
                normalize_str(address.address_1) != normalize_str(partner.street),
                normalize_str(address.address_2) != normalize_str(partner.street2),
                normalize_str(address.city) != normalize_str(partner.city),
                normalize_str(address.zip) != normalize_str(partner.zip),
                country and country.id != partner.country_id.id,
                state and state.id != partner.state_id.id,
                normalize_phone(address.phone) != normalize_phone(partner.phone),
            )
        )

        if not existing_address and is_different_address:
            possible_duplicates = partner.child_ids.filtered(
                lambda a: normalize_str(a.street) == normalize_str(address.address_1)
                and normalize_str(a.street2) == normalize_str(address.address_2)
                and normalize_str(a.city) == normalize_str(address.city)
                and normalize_str(a.zip) == normalize_str(address.zip)
                and (not country or a.country_id.id == country.id)
                and (not state or a.state_id.id == state.id)
                and normalize_phone(a.phone) == normalize_phone(address.phone)
            )
            for possible_duplicate in possible_duplicates:
                if possible_duplicate.shopify_address_id and possible_duplicate.shopify_address_id != shopify_address_id:
                    continue
                if not possible_duplicate.shopify_address_id:
                    write_if_changed(possible_duplicate, {"shopify_address_id": shopify_address_id})
                existing_address = possible_duplicate
                break

        if role == "billing":
            address_type: AddressType = "invoice" if is_different_address else "contact"
        else:
            address_type = "delivery" if is_different_address else "contact"

        address_vals: "odoo.values.res_partner" = {
            "shopify_address_id": shopify_address_id,
            "parent_id": partner.id if address_type in ("delivery", "invoice") else False,
            "type": address_type,
            "name": "" if (address.name or "").strip() == (partner.name or "").strip() else (address.name or ""),
            "street": (address.address_1 or "").strip(),
            "street2": (address.address_2 or "").strip(),
            "city": (address.city or "").strip(),
            "zip": (address.zip or "").strip(),
            "state_id": state.id if state else False,
            "country_id": country.id if country else False,
        }
        if address.company:
            address_vals["company_name"] = address.company.strip()

        if address.phone:
            address_vals["phone"] = self._format_phone_number(address.phone)

        if existing_address:
            changed = write_if_changed(existing_address, address_vals)
            return changed
        elif is_different_address:
            shopify_category = self._get_or_create_category("Shopify")
            address_vals["category_id"] = [(6, 0, list(set(partner.category_id.ids + [shopify_category.id])))]
            self.env["res.partner"].create(address_vals)
            return True
        else:
            main_address_vals: "odoo.values.res_partner" = {
                "street": (address.address_1 or "").strip(),
                "street2": (address.address_2 or "").strip(),
                "city": (address.city or "").strip(),
                "zip": (address.zip or "").strip(),
                "state_id": state.id if state else False,
                "country_id": country.id if country else False,
            }
            if address.phone:
                main_address_vals["phone"] = self._format_phone_number(address.phone)
            changed = write_if_changed(partner, main_address_vals)
            return changed
