import logging
import re

from odoo.api import Environment
from odoo.addons.phone_validation.tools.phone_validation import phone_format

from ...gql import (
    Client,
    AddressFields,
    CustomerFields,
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
AddressType = Literal["delivery", "invoice"]


class CustomerImporter(ShopifyBaseImporter[CustomerFields]):
    def __init__(self, env: Environment, sync_record: "odoo.model.shopify_sync") -> None:
        super().__init__(env, sync_record)

    def _fetch_page(self, client: Client, query: str | None, cursor: str | None) -> ShopifyPage[CustomerFields]:
        return client.get_customers(query=query, cursor=cursor, limit=self.page_size)

    def _import_one(self, shopify_customer: CustomerFields) -> bool:
        return self.import_customer(shopify_customer)

    def _get_or_create_category(self, name: str) -> "odoo.model.res_partner_category":
        category = self.env["res.partner.category"].search([("name", "=", name)], limit=1)
        if not category:
            category = self.env["res.partner.category"].create({"name": name})
        return category

    def _get_tax_exempt_fiscal_position(self) -> "odoo.model.account_fiscal_position":
        fiscal_position = self.env["account.fiscal.position"].search([("name", "ilike", "tax exempt")], limit=1)
        if not fiscal_position:
            fiscal_position = self.env["account.fiscal.position"].create({"name": "Tax Exempt", "auto_apply": False})
        return fiscal_position

    def import_customers_since_last_import(self) -> int:
        return self.run_since_last_import("customer")

    def _format_phone_number(self, phone: str) -> str:
        if not phone or not phone.strip():
            return ""
        country = self.env.company.country_id or self.env["res.country"].search([("code", "=", "US")], limit=1)
        if not country:
            return phone.strip()
        phone_code = int(country.phone_code or 0)
        formatted = phone_format(phone, country.code, phone_code, force_format="E164", raise_exception=False)
        return formatted or phone.strip()

    def import_customer(self, shopify_customer: CustomerFields) -> bool:
        shopify_customer_id = parse_shopify_id_from_gid(shopify_customer.id)
        tags = [t.strip().lower() for t in shopify_customer.tags]
        is_ebay = "ebay" in tags

        if shopify_customer.default_email_address and shopify_customer.default_email_address.email_address:
            shopify_email = normalize_email(shopify_customer.default_email_address.email_address)
        else:
            shopify_email = ""

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
            formatted_phone = self._format_phone_number(shopify_phone)
            if formatted_phone:
                partner = self.env["res.partner"].search(
                    ["|", ("phone", "=", formatted_phone), ("mobile", "=", formatted_phone)],
                    limit=1,
                )

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

        tax_exempt_flag = bool(shopify_customer.tax_exempt) if shopify_customer.tax_exempt is not None else False
        fiscal_position = self._get_tax_exempt_fiscal_position() if tax_exempt_flag else False

        opt_in_states = {"SUBSCRIBED", "PENDING"}
        email_state = shopify_customer.default_email_address.marketing_state if shopify_customer.default_email_address else None
        sms_state = shopify_customer.default_phone_number.marketing_state if shopify_customer.default_phone_number else None
        email_blacklisted_flag = email_state not in opt_in_states if email_state else False
        sms_blacklisted_flag = sms_state not in opt_in_states if sms_state else False

        partner_vals: "odoo.values.res_partner" = {
            "shopify_customer_id": shopify_customer_id,
            "name": name,
            "ebay_username": ebay_username or False,
            "is_blacklisted": email_blacklisted_flag,
            "phone_blacklisted": sms_blacklisted_flag,
            "mobile_blacklisted": sms_blacklisted_flag,
            "property_account_position_id": fiscal_position.id if fiscal_position else False,
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
        addresses_to_process: list[tuple[AddressFields, AddressRole]] = []
        if shopify_customer.default_address:
            addresses_to_process.append((shopify_customer.default_address, "billing"))
        if shopify_customer.addresses_v_2 and shopify_customer.addresses_v_2.nodes:
            for addr in shopify_customer.addresses_v_2.nodes:
                addresses_to_process.append((addr, "shipping"))
        processed_ids: set[str] = set()
        for address, role in addresses_to_process:
            address_id = address.id
            if address_id in processed_ids:
                continue
            processed_ids.add(address_id)
            addresses_changed |= self.process_address(address, partner, role=role)
        if addresses_changed:
            changed = True

        if (
            not tax_exempt_flag
            and partner.property_account_position_id
            and "tax exempt" in partner.property_account_position_id.name.casefold()
        ):
            partner.property_account_position_id = False

        if not sms_blacklisted_flag and (partner.phone_blacklisted or partner.mobile_blacklisted):
            partner.phone_blacklisted = False
            partner.mobile_blacklisted = False

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

        formatted_phone = self._format_phone_number(address.phone) if address.phone else ""
        # Add back phone_mismatch calculation here
        phone_mismatch = bool(formatted_phone) and normalize_phone(formatted_phone) not in {
            normalize_phone(partner.phone),
            normalize_phone(partner.mobile),
        }
        existing_address = self.env["res.partner"].search([("shopify_address_id", "=", shopify_address_id)], limit=1)

        partner_has_address = any(
            (
                partner.street,
                partner.street2,
                partner.city,
                partner.zip,
                partner.state_id,
                partner.country_id,
            )
        )
        is_different_address = partner_has_address and any(
            (
                normalize_str(address.address_1) != normalize_str(partner.street),
                normalize_str(address.address_2) != normalize_str(partner.street2),
                normalize_str(address.city) != normalize_str(partner.city),
                normalize_str(address.zip) != normalize_str(partner.zip),
                country and country.id != partner.country_id.id,
                state and state.id != partner.state_id.id,
                phone_mismatch,
                normalize_str(address.company) != normalize_str(partner.company_name),
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
                and normalize_phone(formatted_phone) in {normalize_phone(a.phone), normalize_phone(a.mobile)}
                and normalize_str(a.company_name) == normalize_str(address.company)
            )
            for possible_duplicate in possible_duplicates:
                if possible_duplicate.shopify_address_id and possible_duplicate.shopify_address_id != shopify_address_id:
                    continue
                if not possible_duplicate.shopify_address_id:
                    write_if_changed(possible_duplicate, {"shopify_address_id": shopify_address_id})
                existing_address = possible_duplicate
                break

        # New address_type logic and early return for main address update
        if not is_different_address:
            main_address_vals: "odoo.values.res_partner" = {
                "shopify_address_id": shopify_address_id,
                "street": (address.address_1 or "").strip(),
                "street2": (address.address_2 or "").strip(),
                "city": (address.city or "").strip(),
                "zip": (address.zip or "").strip(),
                "state_id": state.id if state else False,
                "country_id": country.id if country else False,
            }
            if formatted_phone:
                main_address_vals["phone"] = formatted_phone
            changed = write_if_changed(partner, main_address_vals)
            return changed

        address_type: AddressType = "invoice" if role == "billing" else "delivery"

        address_vals: "odoo.values.res_partner" = {
            "shopify_address_id": shopify_address_id,
            "parent_id": partner.id,
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

        if formatted_phone:
            address_vals["phone"] = formatted_phone

        if existing_address:
            if existing_address.type != address_type:
                existing_address.copy(
                    default={
                        "type": address_type,
                        "shopify_address_id": f"{shopify_address_id}:{address_type}",
                    }
                )
                return True
            changed = write_if_changed(existing_address, address_vals)
            return changed
        elif is_different_address:
            shopify_category = self._get_or_create_category("Shopify")
            address_vals["category_id"] = [(6, 0, list(set(partner.category_id.ids + [shopify_category.id])))]
            self.env["res.partner"].create(address_vals)
            return True
        return False
