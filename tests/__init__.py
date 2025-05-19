import os
import odoo
from odoo.tools import config as odoo_config
from odoo.modules.module import initialize_sys_path

addons_path = os.environ.get("ODOO_ADDONS_PATH")
current_path = odoo_config.get("addons_path")
database_name = os.environ.get("ODOO_DATABASE")

if database_name and not odoo_config.get("db_name"):
    odoo_config["db_name"] = database_name

if addons_path and addons_path != current_path:
    odoo_config["addons_path"] = addons_path
    initialize_sys_path()

import odoo.tests
