import json

from odoo import api, fields, models


class ShopifyWebhookEvent(models.Model):
    _name = "shopify.webhook.event"
    _description = "Shopify Webhook Event"
    _order = "received_at desc, id desc"

    instance_id = fields.Many2one("shopify.instance", required=True, ondelete="cascade", index=True)
    topic = fields.Char(required=True, index=True)
    event_type = fields.Selection(
        selection=[
            ("product", "Product"),
            ("cart", "Cart/Checkout"),
            ("order", "Order"),
            ("other", "Other"),
        ],
        compute="_compute_event_type",
        store=True,
        index=True,
    )
    status = fields.Selection(
        selection=[
            ("received", "Received"),
            ("processed", "Processed"),
            ("failed", "Failed"),
        ],
        default="received",
        required=True,
        index=True,
    )
    webhook_id = fields.Char(index=True, help="Value from X-Shopify-Webhook-Id header when available.")
    shopify_hmac = fields.Char(help="HMAC from X-Shopify-Hmac-Sha256 header.")
    payload_json = fields.Text(required=True)
    payload_pretty = fields.Text(compute="_compute_payload_pretty")
    headers_json = fields.Text()
    error_message = fields.Text()

    received_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    processed_at = fields.Datetime(index=True)

    shopify_order_id = fields.Char(index=True)
    order_name = fields.Char(index=True)
    customer_email = fields.Char(index=True)
    product_title = fields.Char(index=True)
    line_items_count = fields.Integer()
    variants_count = fields.Integer()

    @api.depends("topic")
    def _compute_event_type(self):
        for rec in self:
            topic = rec.topic or ""
            if topic.startswith("products/"):
                rec.event_type = "product"
            elif topic.startswith("carts/") or topic.startswith("checkouts/"):
                rec.event_type = "cart"
            elif topic.startswith("orders/"):
                rec.event_type = "order"
            else:
                rec.event_type = "other"

    @api.depends("payload_json")
    def _compute_payload_pretty(self):
        for rec in self:
            pretty = rec.payload_json or "{}"
            try:
                parsed = json.loads(pretty)
                pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
            except Exception:
                pass
            rec.payload_pretty = pretty

    def _payload_dict(self):
        self.ensure_one()
        try:
            return json.loads(self.payload_json or "{}")
        except Exception:
            return {}

    @api.model
    def create_from_webhook(self, instance, topic, payload, headers=None):
        payload = payload or {}
        headers = headers or {}
        vals = {
            "instance_id": instance.id,
            "topic": topic or "",
            "status": "received",
            "webhook_id": headers.get("X-Shopify-Webhook-Id", ""),
            "shopify_hmac": headers.get("X-Shopify-Hmac-Sha256", ""),
            "payload_json": json.dumps(payload, ensure_ascii=False),
            "headers_json": json.dumps(headers, ensure_ascii=False),
            "shopify_order_id": str(payload.get("id") or "") if (topic or "").startswith("orders/") else "",
            "order_name": payload.get("name") or "",
            "customer_email": payload.get("email")
            or (payload.get("customer") or {}).get("email")
            or "",
            "product_title": payload.get("title") or "",
            "line_items_count": len(payload.get("line_items") or []),
            "variants_count": len(payload.get("variants") or []),
        }
        return self.create(vals)
