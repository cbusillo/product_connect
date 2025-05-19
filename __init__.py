# noinspection PyUnresolvedReferences
import odoo
import os

from odoo.tools import config as odoo_config
from odoo.modules.module import initialize_sys_path

env_addons_path = os.environ.get("ODOO_ADDONS_PATH")
current_addons_path = odoo_config.get("addons_path")
env_db_name = os.environ.get("ODOO_DATABASE")

if env_db_name and not odoo_config.get("db_name"):
    odoo_config["db_name"] = env_db_name

if env_addons_path and env_addons_path != current_addons_path:
    odoo_config["addons_path"] = env_addons_path
    initialize_sys_path()

if __name__.startswith("odoo.addons."):
    from . import mixins, controllers, models, wizards
