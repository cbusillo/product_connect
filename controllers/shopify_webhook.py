import hmac, hashlib, base64, json
from odoo import http


class ShopifyWebhook(http.Controller):
    @http.route("/shopify/webhook", type="json", auth="public", csrf=False)
    def webhook(self) -> str | tuple[str, int]:
        secret = http.request.env["ir.config_parameter"].sudo().get_param("shopify.webhook_secret") or ""
        digest = hmac.new(
            secret.encode(),
            http.request.httprequest.data,
            hashlib.sha256,
        ).digest()
        hmac_header = http.request.httprequest.headers.get("X-Shopify-Hmac-Sha256")
        if not hmac.compare_digest(base64.b64encode(digest).decode(), hmac_header or ""):
            return "Unauthorized", 401
        topic = http.request.httprequest.headers.get("X-Shopify-Topic")
        payload = json.loads(http.request.httprequest.data)
        if topic in ("products/create", "products/update"):
            http.request.env["shopify.sync"].sudo().create(
                {
                    "mode": "import_one",
                    "shopify_product_id_to_sync": payload["id"],
                }
            )
        return "OK"
