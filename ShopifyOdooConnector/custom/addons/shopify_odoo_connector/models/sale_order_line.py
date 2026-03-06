from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    product_image = fields.Image(related="product_id.image_128", readonly=True)
