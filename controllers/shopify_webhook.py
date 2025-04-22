import hmac, hashlib, base64, json
from odoo import http
from odoo.http import Response
from werkzeug.exceptions import Unauthorized, BadRequest


class ShopifyWebhook(http.Controller):
    PRODUCT_TOPICS = ("products/",)
    INVENTORY_TOPICS = ("inventory_items/", "inventory_levels/", "inventory/")
    EXPORT_MODES = ["export_changed", "export_all", "export_since"]
    IMPORT_MODES = ["import_changed", "import_then_export"]
    STATE_DOMAIN = ("state", "in", ["queued", "running"])

    @http.route("/shopify/webhook", type="json", auth="public", csrf=False)
    def webhook(self) -> Response:
        secret = http.request.env["ir.config_parameter"].sudo().get_param("shopify.webhook_key") or ""
        digest = hmac.new(
            secret.encode(),
            http.request.httprequest.data,
            hashlib.sha256,
        ).digest()
        hmac_header = http.request.httprequest.headers.get("X-Shopify-Hmac-Sha256")
        if not hmac.compare_digest(base64.b64encode(digest).decode(), hmac_header or ""):
            raise Unauthorized()
        topic = http.request.httprequest.headers.get("X-Shopify-Topic")
        payload = json.loads(http.request.httprequest.data)
        if any(topic.startswith(prefix) for prefix in self.INVENTORY_TOPICS + self.PRODUCT_TOPICS):
            product_id = payload.get("id") or payload.get("product_id")
            if not product_id:
                raise BadRequest()

            if http.request.env["shopify.sync"].sudo().search([("mode", "in", self.EXPORT_MODES), self.STATE_DOMAIN]):
                if not http.request.env["shopify.sync"].sudo().search([("mode", "in", self.IMPORT_MODES), self.STATE_DOMAIN]):
                    http.request.env["shopify.sync"].sudo().create(
                        {
                            "mode": "import_changed",
                        }
                    )
                return http.Response(json.dumps({"status": "ok"}), content_type="application/json")

            http.request.env["shopify.sync"].create_and_run_async(
                {
                    "mode": "import_one",
                    "shopify_product_id_to_sync": str(payload["id"]),
                }
            )

        return http.Response(json.dumps({"status": "ok"}), content_type="application/json")
