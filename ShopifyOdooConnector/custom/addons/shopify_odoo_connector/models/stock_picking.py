import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    shopify_fulfillment_exported = fields.Boolean(copy=False, readonly=True)
    shopify_fulfillment_id = fields.Char(copy=False, readonly=True)

    def button_validate(self):
        result = super().button_validate()
        for picking in self.filtered(
            lambda p: p.state == "done"
            and p.sale_id
            and p.sale_id.shopify_instance_id
            and p.sale_id.shopify_order_id
            and not p.shopify_fulfillment_exported
        ):
            try:
                picking.sale_id.shopify_instance_id._export_fulfillment_for_picking(picking)
            except Exception:
                _logger.exception("Failed exporting Shopify fulfillment for picking %s", picking.id)
                picking.message_post(body=_("Failed to push fulfillment update to Shopify."))
        return result
