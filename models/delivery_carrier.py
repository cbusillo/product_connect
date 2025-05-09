from odoo import models


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    _sql_constraints = [
        ("name_company_unique", "unique(name, company_id)", "Carrier name must be unique per company"),
    ]
