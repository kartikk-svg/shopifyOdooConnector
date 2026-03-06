from odoo import _, api, fields, models
from odoo.exceptions import UserError


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
    has_posted_invoice = fields.Boolean(
        compute="_compute_has_posted_invoice",
        help="True if the linked order has at least one posted customer invoice.",
    )

    @api.depends("odoo_order_id", "odoo_order_id.invoice_ids", "odoo_order_id.invoice_ids.state")
    def _compute_has_posted_invoice(self):
        for m in self:
            if m.odoo_order_id:
                m.has_posted_invoice = bool(
                    m.odoo_order_id.invoice_ids.filtered(
                        lambda inv: inv.move_type == "out_invoice" and inv.state == "posted"
                    )
                )
            else:
                m.has_posted_invoice = False

    _shopify_order_unique = models.Constraint(
        "UNIQUE(instance_id, shopify_order_id)",
        "Shopify order must be unique per Shopify instance.",
    )

    def action_print_order(self):
        """Open the sale order PDF report for the linked Odoo order."""
        self.ensure_one()
        if not self.odoo_order_id:
            raise UserError(_("No linked Odoo order."))
        report = self.env.ref("sale.action_report_saleorder", raise_if_not_found=False)
        if not report:
            raise UserError(_("Order report not found."))
        return report.report_action(self.odoo_order_id)

    def action_download_invoice(self):
        """Download the customer invoice PDF for the linked order using Odoo's download endpoint."""
        self.ensure_one()
        if not self.odoo_order_id:
            raise UserError(_("No linked Odoo order."))
        invoices = self.odoo_order_id.invoice_ids.filtered(
            lambda m: m.move_type == "out_invoice" and m.state == "posted"
        )
        if not invoices:
            raise UserError(
                _("No posted invoice found for this order. Create and confirm an invoice from the linked Odoo order first.")
            )
        return invoices.action_invoice_download_pdf(target="download")
