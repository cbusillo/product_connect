from odoo import fields, models, api


class IrUiView(models.Model):
    _inherit = "ir.ui.view"

    type = fields.Selection(
        selection_add=[("multigraph", "Multigraph")],
        ondelete={"multigraph": "cascade"},
    )

    @api.model
    def _get_view_info(self) -> "odoo.values.ir_ui_view":
        view_info = super()._get_view_info()
        view_info["multigraph"] = {
            "icon": "fa fa-bar-chart",
            "multi_record": True,
            "display_name": "Multigraph",
        }
        return view_info
