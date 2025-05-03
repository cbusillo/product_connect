from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    shopify_customer_id = fields.Char(string="Shopify Customer ID", copy=False)
    shopify_address_id = fields.Char(string="Shopify Address ID", copy=False)
    ocn_token = fields.Char()
