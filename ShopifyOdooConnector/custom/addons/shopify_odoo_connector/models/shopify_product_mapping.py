from odoo import fields, models


class ShopifyProductMapping(models.Model):
    _name = "shopify.product.mapping"
    _description = "Shopify Product Variant Mapping"
    _rec_name = "shopify_variant_id"
    _order = "id desc"

    instance_id = fields.Many2one("shopify.instance", required=True, ondelete="cascade", index=True)
    shopify_product_id = fields.Char(required=True, index=True)
    shopify_variant_id = fields.Char(required=True, index=True)
    shopify_inventory_item_id = fields.Char(index=True)
    odoo_product_id = fields.Many2one("product.product", required=True, ondelete="cascade", index=True)
    sku = fields.Char(index=True)
    last_synced_at = fields.Datetime(readonly=True)

    _shopify_variant_unique = models.Constraint(
        "UNIQUE(instance_id, shopify_variant_id)",
        "Shopify variant must be unique per Shopify instance.",
    )
    _odoo_product_unique = models.Constraint(
        "UNIQUE(instance_id, odoo_product_id)",
        "Odoo product must be unique per Shopify instance.",
    )
