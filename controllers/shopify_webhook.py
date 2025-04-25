import hmac, hashlib, base64, json

from odoo import http
from odoo.http import Response
from werkzeug.exceptions import Unauthorized, BadRequest

from odoo.addons.product_connect.utils.shopify_helpers import SyncMode, ShopifyApiError


class ShopifyWebhook(http.Controller):
    PRODUCT_TOPICS = ("products/",)
    INVENTORY_TOPICS = ("inventory_items/", "inventory_levels/", "inventory/")

    STATE_DOMAIN = ("state", "in", ["queued", "running"])
    SHOPIFY_LOGIN = "shopify@outboardpartswarehouse.com"

    @http.route("/shopify/webhook", type="json", auth="public", csrf=False, methods=["POST"])
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

        shopify_user = http.request.env["res.users"].sudo().search([("login", "=", self.SHOPIFY_LOGIN)], limit=1)
        if not shopify_user:
            message = f"Shopify user not found for login: {self.SHOPIFY_LOGIN}"
            exception = ShopifyApiError(message)
            http.request.env["notification.manager.mixin"].sudo().notify_channel_on_error(
                "Shopify Webhook Error", message, error=exception
            )
            raise exception
        env = http.request.env(user=shopify_user.id)

        topic = http.request.httprequest.headers.get("X-Shopify-Topic")
        payload = json.loads(http.request.httprequest.data)
        if any(topic.startswith(prefix) for prefix in self.INVENTORY_TOPICS + self.PRODUCT_TOPICS):
            product_id = payload.get("id") or payload.get("odoo_product_id")
            if not product_id:
                raise BadRequest()

            env["shopify.sync"].create_and_run_async({"mode": SyncMode.IMPORT_CHANGED.value, "user": shopify_user.id})
            return http.Response(json.dumps({"status": "ok"}), content_type="application/json")

        return http.Response(json.dumps({"status": "ok"}), content_type="application/json")
