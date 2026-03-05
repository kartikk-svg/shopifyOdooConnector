from odoo import fields, models


class ShopifyOrderMapping(models.Model):
    _name = "shopify.order.mapping"
    _description = "Shopify Order Mapping"
    _rec_name = "shopify_order_name"
    _order = "id desc"

    instance_id = fields.Many2one("shopify.instance", required=True, ondelete="cascade", index=True)
    shopify_order_id = fields.Char(required=True, index=True)
    shopify_order_name = fields.Char(index=True)
    odoo_order_id = fields.Many2one("sale.order", required=True, ondelete="cascade", index=True)
    financial_status = fields.Char()
    fulfillment_status = fields.Char()
    last_synced_at = fields.Datetime(readonly=True)
    customer_name = fields.Char(related="odoo_order_id.partner_id.name", readonly=True)
    customer_email = fields.Char(related="odoo_order_id.partner_id.email", readonly=True)
    customer_phone = fields.Char(related="odoo_order_id.partner_id.phone", readonly=True)
    customer_address = fields.Char(related="odoo_order_id.partner_id.contact_address", readonly=True)
    order_currency_id = fields.Many2one(related="odoo_order_id.currency_id", readonly=True)
    order_total = fields.Monetary(related="odoo_order_id.amount_total", currency_field="order_currency_id", readonly=True)
    order_line_ids = fields.One2many(related="odoo_order_id.order_line", readonly=True)

    _shopify_order_unique = models.Constraint(
        "UNIQUE(instance_id, shopify_order_id)",
        "Shopify order must be unique per Shopify instance.",
    )
