import base64
import hashlib
import hmac
import json
import logging
import traceback

from odoo import fields, http
from odoo.http import Response, request

_logger = logging.getLogger(__name__)


class ShopifyWebhookController(http.Controller):
    @http.route("/shopify/webhook/<int:instance_id>", type="http", auth="public", methods=["POST"], csrf=False)
    def shopify_webhook(self, instance_id, **kwargs):
        instance = request.env["shopify.instance"].sudo().browse(instance_id)
        if not instance.exists() or not instance.active:
            return Response("Instance not found", status=404)

        raw_body = request.httprequest.get_data(cache=False, as_text=False)
        topic = request.httprequest.headers.get("X-Shopify-Topic", "")
        received_hmac = request.httprequest.headers.get("X-Shopify-Hmac-Sha256", "")

        if not self._is_valid_hmac(instance.webhook_secret, raw_body, received_hmac):
            _logger.warning("Invalid Shopify webhook signature for instance %s", instance.id)
            return Response("Unauthorized", status=401)

        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {}
        headers = {
            "X-Shopify-Topic": topic,
            "X-Shopify-Hmac-Sha256": received_hmac,
            "X-Shopify-Webhook-Id": request.httprequest.headers.get("X-Shopify-Webhook-Id", ""),
        }
        event = request.env["shopify.webhook.event"].sudo().create_from_webhook(
            instance=instance,
            topic=topic,
            payload=payload,
            headers=headers,
        )

        try:
            instance.process_webhook(topic, payload)
            event.write({"status": "processed", "processed_at": fields.Datetime.now()})
        except Exception:
            _logger.exception("Failed processing Shopify webhook topic %s for instance %s", topic, instance.id)
            event.write(
                {
                    "status": "failed",
                    "processed_at": fields.Datetime.now(),
                    "error_message": traceback.format_exc(),
                }
            )
            return Response("Webhook processing error", status=500)

        return Response("OK", status=200)

    @staticmethod
    def _is_valid_hmac(secret, payload, received_hmac):
        if not secret or not received_hmac:
            return False
        digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
        expected_hmac = base64.b64encode(digest).decode("utf-8")
        return hmac.compare_digest(expected_hmac, received_hmac)
