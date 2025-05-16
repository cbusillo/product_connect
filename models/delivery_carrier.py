from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    _sql_constraints = [
        ("name_company_unique", "unique(name, company_id)", "Carrier name must be unique per company"),
    ]

    service_map_ids = fields.One2many("delivery.carrier.service.map", "carrier", string="Service Map")


class DeliveryCarrierServiceMap(models.Model):
    _name = "delivery.carrier.service.map"
    _description = "External ↔ Odoo shipping-service map"
    _sql_constraints = [
        ("uniq_platform_external_name", "unique(platform, external_name)", "Duplicate external service for this platform.")
    ]

    carrier = fields.Many2one(
        "delivery.carrier", required=True, ondelete="cascade", help="The Odoo delivery.carrier representing this service level."
    )
    platform = fields.Selection([("shopify", "Shopify"), ("ebay", "eBay"), ("manual", "Manual")], required=True, index=True)
    external_name = fields.Char(
        required=True, index=True, help="Normalised display text from Shopify, or service code from eBay."
    )
    external_id = fields.Char(help="Numeric ID when a platform sends one (e.g. eBay’s ShippingService ID).")
