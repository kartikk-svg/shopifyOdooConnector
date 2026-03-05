from odoo import fields, models


class ShopifyCartMapping(models.Model):
    _name = "shopify.cart.mapping"
    _description = "Shopify Cart Mapping"
    _rec_name = "shopify_cart_name"
    _order = "id desc"

    instance_id = fields.Many2one("shopify.instance", required=True, ondelete="cascade", index=True)
    shopify_cart_id = fields.Char(index=True)
    shopify_cart_token = fields.Char(index=True)
    shopify_checkout_token = fields.Char(index=True)
    shopify_cart_name = fields.Char(index=True)
    customer_email = fields.Char(index=True)
    state = fields.Selection(
        [("active", "Active"), ("converted", "Converted"), ("cancelled", "Cancelled")],
        default="active",
        required=True,
    )
    odoo_quote_id = fields.Many2one("sale.order", required=True, ondelete="cascade", index=True)
    last_synced_at = fields.Datetime(readonly=True)
    customer_name = fields.Char(related="odoo_quote_id.partner_id.name", readonly=True)
    customer_phone = fields.Char(related="odoo_quote_id.partner_id.phone", readonly=True)
    quote_state = fields.Selection(related="odoo_quote_id.state", readonly=True)
    quote_currency_id = fields.Many2one(related="odoo_quote_id.currency_id", readonly=True)
    quote_total = fields.Monetary(related="odoo_quote_id.amount_total", currency_field="quote_currency_id", readonly=True)
    quote_line_ids = fields.One2many(related="odoo_quote_id.order_line", readonly=True)

    _odoo_quote_unique = models.Constraint(
        "UNIQUE(instance_id, odoo_quote_id)",
        "Odoo quotation must be unique per Shopify instance.",
    )
