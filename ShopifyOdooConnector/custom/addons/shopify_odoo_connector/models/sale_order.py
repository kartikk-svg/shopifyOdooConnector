from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    shopify_instance_id = fields.Many2one("shopify.instance", copy=False, index=True)
    shopify_order_id = fields.Char(copy=False, index=True)
    shopify_order_name = fields.Char(copy=False)
    shopify_cart_id = fields.Char(copy=False, index=True)
    shopify_cart_token = fields.Char(copy=False, index=True)
    shopify_checkout_token = fields.Char(copy=False, index=True)
