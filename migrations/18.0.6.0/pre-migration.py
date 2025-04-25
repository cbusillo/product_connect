from odoo import api, SUPERUSER_ID
from odoo.sql_db import Cursor
from odoo.upgrade import util


def migrate(cr: Cursor, version: str) -> None:
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    if not env:
        return

    env["ir.config_parameter"].sudo().search([("key", "=", "shopify.last_import_time")]).unlink()
    env["ir.config_parameter"].sudo().search([("key", "=", "shopify.shop_url")]).unlink()
    env["ir.config_parameter"].sudo().search([("key", "=", "shopify.api_version")]).unlink()
