from odoo import api, SUPERUSER_ID
from odoo.sql_db import Cursor
from odoo.upgrade import util


def _safe_rename(cr: Cursor, model: str, old: str, new: str) -> None:
    table = model.replace(".", "_")
    cr.execute(f'ALTER TABLE {table} RENAME COLUMN "{old}" TO {new}')


def migrate(cr: Cursor, version: str) -> None:
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    if not env:
        return

    env["ir.config_parameter"].sudo().search([("key", "=", "shopify.last_import_time")]).unlink()
    env["ir.config_parameter"].sudo().search([("key", "=", "shopify.shop_url")]).unlink()
    env["ir.config_parameter"].sudo().search([("key", "=", "shopify.api_version")]).unlink()

    _safe_rename(cr, "product.image", "index", "initial_index")
    _safe_rename(cr, "motor.image", "index", "initial_index")

    util.remove_field(cr, "product.product", "shopify_last_exported")

    util.remove_model(cr, "notification.history")
