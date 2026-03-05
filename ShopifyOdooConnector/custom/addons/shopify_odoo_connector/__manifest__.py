{
    "name": "Shopify Odoo Connector",
    "version": "19.0.2.0.0",
    "category": "Sales/Sales",
    "summary": "Synchronize Shopify products, carts, orders, inventory, and fulfillment with Odoo",
    "author": "Elsner",
    "website": "https://www.elsner.com",
    "license": "LGPL-3",
    "depends": [
        "sale_management",
        "stock",
        "account",
        "mail",
    ],
    "external_dependencies": {
        "python": ["requests"],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/shopify_instance_views.xml",
        "views/shopify_menu.xml",
        "data/ir_cron_data.xml",
    ],
    "application": True,
    "installable": True,
}
