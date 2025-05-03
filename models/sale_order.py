from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    shopify_order_id = fields.Char(string="Shopify Order ID", copy=False)
