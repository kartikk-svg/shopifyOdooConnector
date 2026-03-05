import logging
import re
from datetime import timezone

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ShopifyInstance(models.Model):
    _name = "shopify.instance"
    _description = "Shopify Instance"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    shop_url = fields.Char(required=True, tracking=True, help="Store domain, for example: your-store.myshopify.com")
    api_version = fields.Char(default="2025-10", required=True)
    access_token = fields.Char(required=True)
    webhook_secret = fields.Char(help="Shopify app API secret used to validate webhook HMAC signatures.")
    webhook_base_url = fields.Char(
        default=lambda self: self.env["ir.config_parameter"].sudo().get_param("web.base.url"),
        help="Public base URL of this Odoo instance for webhook callbacks.",
    )
    webhook_url = fields.Char(compute="_compute_webhook_url")
    shopify_location_id = fields.Char(help="Shopify location ID used for inventory sync.")
    local_storefront_base_url = fields.Char(
        default="http://127.0.0.1:3010",
        help="Local storefront URL used in development mode fallback when Shopify API is unavailable.",
    )

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        required=True,
        default=lambda self: self.env["stock.warehouse"].search([("company_id", "=", self.env.company.id)], limit=1),
    )
    pricelist_id = fields.Many2one(
        "product.pricelist",
        default=lambda self: self.env["product.pricelist"].search([("company_id", "in", [False, self.env.company.id])], limit=1),
    )

    auto_import_products = fields.Boolean(default=True)
    auto_import_carts = fields.Boolean(default=True)
    auto_import_orders = fields.Boolean(default=True)
    auto_export_products = fields.Boolean(default=False)
    auto_export_inventory = fields.Boolean(default=True)
    auto_confirm_orders = fields.Boolean(default=True)
    auto_create_invoice = fields.Boolean(default=True)
    auto_register_payment = fields.Boolean(default=False)
    notify_customer_on_fulfillment = fields.Boolean(default=True)
    payment_journal_id = fields.Many2one(
        "account.journal",
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id)]",
        help="Journal used when auto-registering payments for paid Shopify orders.",
    )

    last_product_sync_at = fields.Datetime(readonly=True)
    last_cart_sync_at = fields.Datetime(readonly=True)
    last_order_sync_at = fields.Datetime(readonly=True)
    last_export_sync_at = fields.Datetime(readonly=True)
    last_inventory_sync_at = fields.Datetime(readonly=True)

    product_mapping_ids = fields.One2many("shopify.product.mapping", "instance_id")
    cart_mapping_ids = fields.One2many("shopify.cart.mapping", "instance_id")
    order_mapping_ids = fields.One2many("shopify.order.mapping", "instance_id")
    webhook_event_ids = fields.One2many("shopify.webhook.event", "instance_id")

    webhook_event_count = fields.Integer(compute="_compute_webhook_event_stats")
    webhook_product_event_count = fields.Integer(compute="_compute_webhook_event_stats")
    webhook_cart_event_count = fields.Integer(compute="_compute_webhook_event_stats")
    webhook_order_event_count = fields.Integer(compute="_compute_webhook_event_stats")
    webhook_failed_event_count = fields.Integer(compute="_compute_webhook_event_stats")
    last_webhook_received_at = fields.Datetime(compute="_compute_webhook_event_stats")

    @api.depends("webhook_event_ids", "webhook_event_ids.status", "webhook_event_ids.event_type", "webhook_event_ids.received_at")
    def _compute_webhook_event_stats(self):
        stats = {instance.id: {"all": 0, "product": 0, "cart": 0, "order": 0, "failed": 0} for instance in self}
        latest_map = {instance.id: False for instance in self}
        if self.ids:
            grouped = self.env["shopify.webhook.event"].read_group(
                [("instance_id", "in", self.ids)],
                ["instance_id", "event_type", "status"],
                ["instance_id", "event_type", "status"],
                lazy=False,
            )
            for row in grouped:
                instance_id = row.get("instance_id") and row["instance_id"][0]
                if not instance_id or instance_id not in stats:
                    continue
                count = row.get("__count", 0)
                stats[instance_id]["all"] += count
                event_type = row.get("event_type")
                status = row.get("status")
                if event_type in ("product", "cart", "order"):
                    stats[instance_id][event_type] += count
                if status == "failed":
                    stats[instance_id]["failed"] += count

            latest_rows = self.env["shopify.webhook.event"].read_group(
                [("instance_id", "in", self.ids)],
                ["instance_id", "received_at:max"],
                ["instance_id"],
                lazy=False,
            )
            for row in latest_rows:
                instance_id = row.get("instance_id") and row["instance_id"][0]
                if instance_id in latest_map:
                    latest_map[instance_id] = row.get("received_at_max") or row.get("received_at")

        for instance in self:
            instance.webhook_event_count = stats[instance.id]["all"]
            instance.webhook_product_event_count = stats[instance.id]["product"]
            instance.webhook_cart_event_count = stats[instance.id]["cart"]
            instance.webhook_order_event_count = stats[instance.id]["order"]
            instance.webhook_failed_event_count = stats[instance.id]["failed"]
            instance.last_webhook_received_at = latest_map[instance.id]

    @api.depends("webhook_base_url")
    def _compute_webhook_url(self):
        for instance in self:
            base = (instance.webhook_base_url or "").strip().rstrip("/")
            instance.webhook_url = f"{base}/shopify/webhook/{instance.id}" if base and instance.id else False

    @api.constrains("shop_url")
    def _check_shop_url(self):
        for instance in self:
            domain = instance._normalized_shop_domain()
            if not domain or "." not in domain or "/" in domain:
                raise ValidationError(_("Shop URL must be a valid Shopify domain like your-store.myshopify.com."))

    def _normalized_shop_domain(self):
        self.ensure_one()
        domain = (self.shop_url or "").strip()
        if not domain:
            return ""
        domain = re.sub(r"^https?://", "", domain, flags=re.IGNORECASE).strip("/")
        return domain

    @staticmethod
    def _to_shopify_datetime(dt_value):
        if not dt_value:
            return False
        dt = fields.Datetime.to_datetime(dt_value)
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _shopify_url(self, path):
        self.ensure_one()
        domain = self._normalized_shop_domain()
        return f"https://{domain}/admin/api/{self.api_version}/{path.lstrip('/')}"

    def _shopify_request(self, method, path, payload=None, params=None):
        self.ensure_one()
        url = self._shopify_url(path)
        headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=headers,
                json=payload,
                params=params,
                timeout=60,
            )
        except requests.RequestException as exc:
            raise UserError(_("Unable to connect to Shopify: %s") % exc) from exc

        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text}

        if not response.ok:
            raise UserError(_("Shopify API error (%s): %s") % (response.status_code, body))
        return body, response.headers

    @staticmethod
    def _extract_next_page_info(link_header):
        if not link_header:
            return False
        for part in link_header.split(","):
            if 'rel="next"' not in part:
                continue
            match = re.search(r"[?&]page_info=([^&>]+)", part)
            if match:
                return match.group(1)
        return False

    def _shopify_paginated_get(self, path, params, root_key):
        self.ensure_one()
        all_rows = []
        base_params = dict(params or {})
        page_info = False
        while True:
            current_params = dict(base_params)
            if page_info:
                current_params = {"limit": base_params.get("limit", 250), "page_info": page_info}
            data, headers = self._shopify_request("GET", path, params=current_params)
            all_rows.extend(data.get(root_key, []))
            page_info = self._extract_next_page_info(headers.get("Link"))
            if not page_info:
                break
        return all_rows

    def _has_local_storefront_config(self):
        self.ensure_one()
        return bool((self.local_storefront_base_url or "").strip())

    def _storefront_request(self, method, path, payload=None, params=None):
        self.ensure_one()
        if not self._has_local_storefront_config():
            raise UserError(_("Local storefront base URL is not configured."))
        base = self.local_storefront_base_url.strip().rstrip("/")
        url = f"{base}/{path.lstrip('/')}"
        try:
            response = requests.request(
                method=method.upper(),
                url=url,
                json=payload,
                params=params,
                timeout=60,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
        except requests.RequestException as exc:
            raise UserError(_("Unable to connect to local storefront: %s") % exc) from exc

        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text}
        if not response.ok:
            raise UserError(_("Local storefront API error (%s): %s") % (response.status_code, body))
        return body

    @staticmethod
    def _build_storefront_product_payload(product_row):
        product_row = product_row or {}
        product_id = str(product_row.get("shopify_product_id") or product_row.get("id") or "").strip()
        if not product_id:
            return {}
        variant_id = str(product_row.get("shopify_variant_id") or f"{product_id}11").strip()
        inventory_item_id = str(product_row.get("shopify_inventory_item_id") or f"{variant_id}99").strip()
        return {
            "id": int(product_id) if product_id.isdigit() else product_id,
            "title": product_row.get("title") or _("Shopify Product"),
            "body_html": product_row.get("description") or "",
            "status": "active",
            "variants": [
                {
                    "id": int(variant_id) if variant_id.isdigit() else variant_id,
                    "product_id": int(product_id) if product_id.isdigit() else product_id,
                    "sku": (product_row.get("sku") or "").strip(),
                    "price": str(product_row.get("price") or 0.0),
                    "inventory_item_id": int(inventory_item_id) if inventory_item_id.isdigit() else inventory_item_id,
                }
            ],
        }

    def _import_products_from_storefront_api(self):
        self.ensure_one()
        products = self._storefront_request("GET", "/api/store/products")
        if not isinstance(products, list):
            raise UserError(_("Unexpected local storefront product response."))
        product_payloads = []
        for row in products:
            payload = self._build_storefront_product_payload(row)
            if payload:
                product_payloads.append(payload)

        synced_variant_ids = set()
        synced_product_ids = set()
        count = 0
        for product_payload in product_payloads:
            count += self._sync_product_payload(product_payload)
            product_id = str(product_payload.get("id") or "")
            if product_id:
                synced_product_ids.add(product_id)
            for variant in product_payload.get("variants", []):
                variant_id = str(variant.get("id") or "")
                if variant_id:
                    synced_variant_ids.add(variant_id)

        stale_domain = [("instance_id", "=", self.id)]
        if synced_variant_ids:
            stale_domain.append(("shopify_variant_id", "not in", list(synced_variant_ids)))
        elif synced_product_ids:
            stale_domain.append(("shopify_product_id", "not in", list(synced_product_ids)))
        stale_mappings = self.env["shopify.product.mapping"].search(stale_domain)
        stale_count = len(stale_mappings)
        if stale_mappings:
            stale_mappings.mapped("odoo_product_id").mapped("product_tmpl_id").write({"active": False})
            stale_mappings.unlink()
        self.last_product_sync_at = fields.Datetime.now()
        self.message_post(
            body=_("Imported/updated %s products from local storefront API and removed %s stale mappings.")
            % (count, stale_count)
        )
        return count

    def _import_carts_from_webhook_events(self):
        self.ensure_one()
        events = self.env["shopify.webhook.event"].search(
            [
                ("instance_id", "=", self.id),
                ("topic", "in", ("carts/create", "carts/update", "checkouts/create", "checkouts/update")),
            ],
            order="received_at asc, id asc",
        )
        count = 0
        for event in events:
            if self._sync_cart_payload(event._payload_dict()):
                count += 1
        self.last_cart_sync_at = fields.Datetime.now()
        self.message_post(body=_("Imported/updated %s carts from webhook events.") % count)
        return count

    def _import_orders_from_webhook_events(self):
        self.ensure_one()
        events = self.env["shopify.webhook.event"].search(
            [
                ("instance_id", "=", self.id),
                ("topic", "in", ("orders/create", "orders/updated")),
            ],
            order="received_at asc, id asc",
        )
        count = 0
        for event in events:
            if self._sync_order_payload(event._payload_dict()):
                count += 1
        self.last_order_sync_at = fields.Datetime.now()
        self.message_post(body=_("Imported/updated %s orders from webhook events.") % count)
        return count

    def action_test_connection(self):
        for instance in self:
            try:
                data, _headers = instance._shopify_request("GET", "shop.json")
                shop_name = data.get("shop", {}).get("name") or instance.shop_url
                if not instance.name or instance.name == instance.shop_url:
                    instance.name = shop_name
                instance.message_post(body=_("Shopify connection successful: %s") % shop_name)
            except UserError:
                if not instance._has_local_storefront_config():
                    raise
                local_data = instance._storefront_request("GET", "/api/store/config")
                local_name = local_data.get("app_name") or instance.name or _("Local Storefront")
                instance.message_post(body=_("Local storefront connection successful: %s") % local_name)
        return True

    def action_register_webhooks(self):
        topics = [
            "products/create",
            "products/update",
            "products/delete",
            "carts/create",
            "carts/update",
            "carts/delete",
            "checkouts/create",
            "checkouts/update",
            "checkouts/delete",
            "orders/create",
            "orders/updated",
        ]
        for instance in self:
            if not instance.webhook_url:
                raise UserError(_("Webhook URL is empty. Configure webhook base URL first."))
            try:
                existing = instance._shopify_paginated_get("webhooks.json", {"limit": 250}, "webhooks")
                existing_topics = {
                    webhook.get("topic")
                    for webhook in existing
                    if webhook.get("address", "").rstrip("/") == instance.webhook_url.rstrip("/")
                }
                for topic in topics:
                    if topic in existing_topics:
                        continue
                    instance._shopify_request(
                        "POST",
                        "webhooks.json",
                        payload={"webhook": {"topic": topic, "address": instance.webhook_url, "format": "json"}},
                    )
                instance.message_post(body=_("Webhook registration completed for %s.") % instance.webhook_url)
            except UserError:
                if not instance._has_local_storefront_config():
                    raise
                instance.message_post(
                    body=_(
                        "External Shopify webhook registration skipped. Local storefront mode uses direct callback URL: %s"
                    )
                    % instance.webhook_url
                )
        return True

    def action_import_products(self):
        for instance in self:
            instance._import_products_from_shopify()
        return True

    def action_import_orders(self):
        for instance in self:
            instance._import_orders_from_shopify()
        return True
    def action_import_carts(self):
        for instance in self:
            instance._import_carts_from_shopify()
        return True

    def action_export_products(self):
        for instance in self:
            try:
                instance._export_products_to_shopify()
            except UserError:
                if not instance._has_local_storefront_config():
                    raise
                instance.last_export_sync_at = fields.Datetime.now()
                instance.message_post(body=_("Product export skipped in local storefront mode (no external Shopify Admin API)."))
        return True

    def action_export_inventory(self):
        for instance in self:
            try:
                instance._export_inventory_to_shopify()
            except UserError:
                if not instance._has_local_storefront_config():
                    raise
                instance.last_inventory_sync_at = fields.Datetime.now()
                instance.message_post(
                    body=_("Inventory export skipped in local storefront mode (no external Shopify Admin API).")
                )
        return True

    def _get_or_create_product(self, product_payload, variant_payload):
        self.ensure_one()
        sku = (variant_payload.get("sku") or "").strip()
        variant_id = str(variant_payload.get("id") or "")

        mapping = self.env["shopify.product.mapping"].search(
            [("instance_id", "=", self.id), ("shopify_variant_id", "=", variant_id)],
            limit=1,
        )
        if mapping:
            return mapping.odoo_product_id, mapping

        product = False
        if sku:
            product = self.env["product.product"].search([("default_code", "=", sku)], limit=1)

        if not product:
            title = product_payload.get("title") or _("Shopify Product")
            variant_title = variant_payload.get("title")
            name = title
            if variant_title and variant_title != "Default Title":
                name = f"{title} ({variant_title})"
            template = self.env["product.template"].create(
                {
                    "name": name,
                    "type": "consu",
                    "sale_ok": True,
                    "purchase_ok": False,
                    "list_price": float(variant_payload.get("price") or 0.0),
                }
            )
            product = template.product_variant_id
            if sku:
                product.default_code = sku

        return product, mapping

    def _sync_product_payload(self, product_payload):
        self.ensure_one()
        product_model = self.env["shopify.product.mapping"]
        product_id = str(product_payload.get("id") or "")
        synced = 0

        for variant in product_payload.get("variants", []):
            variant_id = str(variant.get("id") or "")
            if not variant_id:
                continue

            odoo_product, mapping = self._get_or_create_product(product_payload, variant)
            sku = (variant.get("sku") or "").strip()
            price = float(variant.get("price") or 0.0)

            if sku and odoo_product.default_code != sku:
                odoo_product.default_code = sku
            odoo_product.product_tmpl_id.write(
                {
                    "name": product_payload.get("title") or odoo_product.product_tmpl_id.name,
                    "list_price": price,
                    "description_sale": product_payload.get("body_html") or "",
                    "active": product_payload.get("status", "active") != "archived",
                }
            )

            vals = {
                "instance_id": self.id,
                "shopify_product_id": product_id,
                "shopify_variant_id": variant_id,
                "shopify_inventory_item_id": str(variant.get("inventory_item_id") or ""),
                "odoo_product_id": odoo_product.id,
                "sku": sku,
                "last_synced_at": fields.Datetime.now(),
            }
            if mapping:
                mapping.write(vals)
            else:
                product_model.create(vals)
            synced += 1
        return synced

    def _delete_product_payload(self, product_payload):
        self.ensure_one()
        product_payload = product_payload or {}
        product_id = str(product_payload.get("id") or "")
        variant_ids = [str(variant.get("id") or "") for variant in (product_payload.get("variants") or []) if variant.get("id")]
        if not product_id and not variant_ids:
            return 0

        domain = [("instance_id", "=", self.id)]
        if variant_ids:
            domain.append(("shopify_variant_id", "in", variant_ids))
        else:
            domain.append(("shopify_product_id", "=", product_id))

        mappings = self.env["shopify.product.mapping"].search(domain)
        if not mappings and product_id:
            mappings = self.env["shopify.product.mapping"].search(
                [("instance_id", "=", self.id), ("shopify_product_id", "=", product_id)]
            )

        products = mappings.mapped("odoo_product_id")
        if products:
            products.mapped("product_tmpl_id").write({"active": False})
        count = len(mappings)
        if mappings:
            mappings.unlink()
        self.last_product_sync_at = fields.Datetime.now()
        if count:
            self.message_post(body=_("Processed Shopify delete for %s product variants.") % count)
        return count

    def _import_products_from_shopify(self, product_payloads=None):
        self.ensure_one()
        if product_payloads is None:
            if self._has_local_storefront_config():
                try:
                    return self._import_products_from_storefront_api()
                except UserError as local_error:
                    _logger.warning(
                        "Local storefront product import failed for instance %s, falling back to Shopify API: %s",
                        self.id,
                        local_error,
                    )
            params = {"limit": 250}
            if self.last_product_sync_at:
                params["updated_at_min"] = self._to_shopify_datetime(self.last_product_sync_at)
            try:
                product_payloads = self._shopify_paginated_get("products.json", params, "products")
            except UserError:
                if not self._has_local_storefront_config():
                    raise
                return self._import_products_from_storefront_api()

        count = 0
        for product_payload in product_payloads:
            count += self._sync_product_payload(product_payload)

        self.last_product_sync_at = fields.Datetime.now()
        self.message_post(body=_("Imported/updated %s Shopify product variants.") % count)
        return count

    def _get_or_create_partner(self, order_payload):
        self.ensure_one()
        customer = order_payload.get("customer") or {}
        billing = order_payload.get("billing_address") or {}

        email = order_payload.get("email") or customer.get("email") or ""
        first_name = billing.get("first_name") or customer.get("first_name") or ""
        last_name = billing.get("last_name") or customer.get("last_name") or ""
        name = " ".join(x for x in [first_name, last_name] if x).strip() or customer.get("name") or email or _("Shopify Customer")

        partner = False
        if email:
            partner = self.env["res.partner"].search([("email", "=", email)], limit=1)
        if not partner:
            partner = self.env["res.partner"].create(
                {
                    "name": name,
                    "email": email or False,
                    "phone": billing.get("phone") or customer.get("phone") or False,
                    "street": billing.get("address1") or False,
                    "street2": billing.get("address2") or False,
                    "city": billing.get("city") or False,
                    "zip": billing.get("zip") or False,
                    "company_id": self.company_id.id,
                }
            )
        else:
            partner.write(
                {
                    "name": name,
                    "phone": billing.get("phone") or partner.phone,
                    "street": billing.get("address1") or partner.street,
                    "street2": billing.get("address2") or partner.street2,
                    "city": billing.get("city") or partner.city,
                    "zip": billing.get("zip") or partner.zip,
                }
            )
        return partner

    def _get_or_create_line_product(self, line_item):
        self.ensure_one()
        variant_id = str(line_item.get("variant_id") or "")
        mapping = False
        if variant_id:
            mapping = self.env["shopify.product.mapping"].search(
                [("instance_id", "=", self.id), ("shopify_variant_id", "=", variant_id)],
                limit=1,
            )
        if mapping:
            return mapping.odoo_product_id

        sku = (line_item.get("sku") or "").strip()
        product = False
        if sku:
            product = self.env["product.product"].search([("default_code", "=", sku)], limit=1)

        if not product:
            template = self.env["product.template"].create(
                {
                    "name": line_item.get("title") or _("Shopify Item"),
                    "type": "consu",
                    "sale_ok": True,
                    "purchase_ok": False,
                    "list_price": float(line_item.get("price") or 0.0),
                }
            )
            product = template.product_variant_id
            if sku:
                product.default_code = sku

        if variant_id:
            self.env["shopify.product.mapping"].create(
                {
                    "instance_id": self.id,
                    "shopify_product_id": str(line_item.get("product_id") or ""),
                    "shopify_variant_id": variant_id,
                    "shopify_inventory_item_id": str(line_item.get("inventory_item_id") or ""),
                    "odoo_product_id": product.id,
                    "sku": sku,
                    "last_synced_at": fields.Datetime.now(),
                }
            )
        return product

    def _get_shipping_product(self):
        product = self.env["product.product"].search([("default_code", "=", "SHOPIFY-SHIPPING")], limit=1)
        if not product:
            template = self.env["product.template"].create(
                {
                    "name": "Shopify Shipping",
                    "type": "service",
                    "sale_ok": True,
                    "purchase_ok": False,
                    "list_price": 0.0,
                }
            )
            product = template.product_variant_id
            product.default_code = "SHOPIFY-SHIPPING"
        return product

    def _get_or_create_partner_by_email(self, email, name):
        self.ensure_one()
        email = (email or "").strip()
        name = (name or "").strip() or _("Shopify Customer")
        partner = False
        if email:
            partner = self.env["res.partner"].search([("email", "=", email)], limit=1)
        if not partner:
            partner = self.env["res.partner"].create(
                {
                    "name": name,
                    "email": email or False,
                    "company_id": self.company_id.id,
                }
            )
        elif name and partner.name != name:
            partner.name = name
        return partner

    def _build_line_commands_from_line_items(self, line_items):
        self.ensure_one()
        commands = []
        for line_item in line_items or []:
            product = self._get_or_create_line_product(line_item)
            quantity = float(line_item.get("quantity") or 0.0)
            price = float(line_item.get("price") or line_item.get("final_line_price") or 0.0)
            if not quantity:
                continue
            commands.append(
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "name": line_item.get("name") or line_item.get("title") or product.display_name,
                        "product_uom_qty": quantity,
                        "price_unit": price,
                    },
                )
            )
        return commands

    def _extract_cart_identifiers(self, payload):
        self.ensure_one()
        payload = payload or {}
        cart_id = str(payload.get("id") or "")
        cart_token = str(payload.get("token") or payload.get("cart_token") or "")
        checkout_token = str(payload.get("checkout_token") or "")
        if not checkout_token and payload.get("source_name") == "web":
            checkout_token = cart_token
        return cart_id, cart_token, checkout_token

    def _find_cart_mapping(self, cart_id, cart_token, checkout_token):
        self.ensure_one()
        mapping_model = self.env["shopify.cart.mapping"]
        mapping = False
        if cart_id:
            mapping = mapping_model.search(
                [("instance_id", "=", self.id), ("shopify_cart_id", "=", cart_id)],
                limit=1,
            )
        if not mapping and cart_token:
            mapping = mapping_model.search(
                [("instance_id", "=", self.id), ("shopify_cart_token", "=", cart_token)],
                limit=1,
            )
        if not mapping and checkout_token:
            mapping = mapping_model.search(
                [("instance_id", "=", self.id), ("shopify_checkout_token", "=", checkout_token)],
                limit=1,
            )
        return mapping

    def _get_or_create_cart_partner(self, cart_payload):
        self.ensure_one()
        buyer = cart_payload.get("buyer_identity") or {}
        customer = cart_payload.get("customer") or {}
        email = cart_payload.get("email") or buyer.get("email") or customer.get("email") or ""
        first_name = cart_payload.get("first_name") or customer.get("first_name") or ""
        last_name = cart_payload.get("last_name") or customer.get("last_name") or ""
        name = " ".join(x for x in [first_name, last_name] if x).strip() or email or _("Shopify Cart Customer")
        return self._get_or_create_partner_by_email(email, name)

    def _sync_cart_payload(self, cart_payload):
        self.ensure_one()
        cart_payload = cart_payload or {}
        cart_id, cart_token, checkout_token = self._extract_cart_identifiers(cart_payload)
        if not (cart_id or cart_token or checkout_token):
            return False

        mapping = self._find_cart_mapping(cart_id, cart_token, checkout_token)
        partner = self._get_or_create_cart_partner(cart_payload)
        cart_label = cart_payload.get("name") or cart_token or cart_id or checkout_token

        quote_vals = {
            "partner_id": partner.id,
            "partner_invoice_id": partner.id,
            "partner_shipping_id": partner.id,
            "company_id": self.company_id.id,
            "warehouse_id": self.warehouse_id.id,
            "origin": _("Shopify Cart %s") % cart_label,
            "client_order_ref": _("Cart %s") % cart_label,
            "shopify_instance_id": self.id,
            "shopify_cart_id": cart_id or False,
            "shopify_cart_token": cart_token or False,
            "shopify_checkout_token": checkout_token or False,
        }
        if self.pricelist_id:
            quote_vals["pricelist_id"] = self.pricelist_id.id

        line_commands = self._build_line_commands_from_line_items(cart_payload.get("line_items", []))

        if mapping and mapping.odoo_quote_id and mapping.odoo_quote_id.state in ("draft", "sent"):
            quote = mapping.odoo_quote_id
            quote.write(quote_vals)
            quote.order_line.unlink()
            if line_commands:
                quote.write({"order_line": line_commands})
        else:
            quote_vals["order_line"] = line_commands
            quote = self.env["sale.order"].create(quote_vals)

        mapping_vals = {
            "instance_id": self.id,
            "shopify_cart_id": cart_id or False,
            "shopify_cart_token": cart_token or False,
            "shopify_checkout_token": checkout_token or False,
            "shopify_cart_name": str(cart_label),
            "customer_email": partner.email or False,
            "state": "active",
            "odoo_quote_id": quote.id,
            "last_synced_at": fields.Datetime.now(),
        }
        if mapping:
            mapping.write(mapping_vals)
        else:
            self.env["shopify.cart.mapping"].create(mapping_vals)

        self.last_cart_sync_at = fields.Datetime.now()
        return quote

    def _import_carts_from_shopify(self, cart_payloads=None):
        self.ensure_one()
        if cart_payloads is None:
            return self._import_carts_from_webhook_events()

        count = 0
        for cart_payload in cart_payloads:
            if self._sync_cart_payload(cart_payload):
                count += 1
        self.last_cart_sync_at = fields.Datetime.now()
        self.message_post(body=_("Imported/updated %s Shopify carts.") % count)
        return count

    def _cancel_cart_payload(self, cart_payload):
        self.ensure_one()
        cart_id, cart_token, checkout_token = self._extract_cart_identifiers(cart_payload or {})
        mapping = self._find_cart_mapping(cart_id, cart_token, checkout_token)
        if not mapping:
            return False
        mapping.write({"state": "cancelled", "last_synced_at": fields.Datetime.now()})
        if mapping.odoo_quote_id and mapping.odoo_quote_id.state in ("draft", "sent"):
            mapping.odoo_quote_id.action_cancel()
        self.last_cart_sync_at = fields.Datetime.now()
        return mapping

    def _mark_related_cart_as_converted(self, order_payload, sale_order):
        self.ensure_one()
        checkout_token = str(order_payload.get("checkout_token") or "")
        cart_token = str(order_payload.get("cart_token") or "")
        mapping = self._find_cart_mapping("", cart_token, checkout_token)
        if not mapping:
            return False
        old_quote = mapping.odoo_quote_id
        mapping.write({"state": "converted", "odoo_quote_id": sale_order.id, "last_synced_at": fields.Datetime.now()})
        if old_quote and old_quote.state in ("draft", "sent") and old_quote.id != sale_order.id:
            old_quote.action_cancel()
        return mapping

    def _build_order_line_commands(self, order_payload):
        self.ensure_one()
        commands = self._build_line_commands_from_line_items(order_payload.get("line_items", []))

        shipping_lines = order_payload.get("shipping_lines") or []
        shipping_total = sum(float(line.get("price") or 0.0) for line in shipping_lines)
        if shipping_total:
            shipping_product = self._get_shipping_product()
            commands.append(
                (
                    0,
                    0,
                    {
                        "product_id": shipping_product.id,
                        "name": _("Shipping"),
                        "product_uom_qty": 1.0,
                        "price_unit": shipping_total,
                    },
                )
            )
        return commands

    def _sync_order_payload(self, order_payload):
        self.ensure_one()
        shopify_order_id = str(order_payload.get("id") or "")
        if not shopify_order_id:
            return False

        mapping = self.env["shopify.order.mapping"].search(
            [("instance_id", "=", self.id), ("shopify_order_id", "=", shopify_order_id)],
            limit=1,
        )
        partner = self._get_or_create_partner(order_payload)
        order_vals = {
            "partner_id": partner.id,
            "partner_invoice_id": partner.id,
            "partner_shipping_id": partner.id,
            "company_id": self.company_id.id,
            "warehouse_id": self.warehouse_id.id,
            "origin": _("Shopify %s") % (order_payload.get("name") or shopify_order_id),
            "client_order_ref": order_payload.get("name") or shopify_order_id,
            "shopify_instance_id": self.id,
            "shopify_order_id": shopify_order_id,
            "shopify_order_name": order_payload.get("name") or "",
        }
        if self.pricelist_id:
            order_vals["pricelist_id"] = self.pricelist_id.id

        line_commands = self._build_order_line_commands(order_payload)
        cart_mapping = self._find_cart_mapping(
            "",
            str(order_payload.get("cart_token") or ""),
            str(order_payload.get("checkout_token") or ""),
        )

        if mapping and mapping.odoo_order_id:
            sale_order = mapping.odoo_order_id
            if sale_order.state in ("draft", "sent"):
                sale_order.write(order_vals)
                sale_order.order_line.unlink()
                if line_commands:
                    sale_order.write({"order_line": line_commands})
            else:
                sale_order.message_post(
                    body=_("Shopify order update received, but Odoo order is not in draft and line changes were skipped.")
                )
        elif cart_mapping and cart_mapping.odoo_quote_id and cart_mapping.odoo_quote_id.state in ("draft", "sent"):
            sale_order = cart_mapping.odoo_quote_id
            sale_order.write(order_vals)
            sale_order.order_line.unlink()
            if line_commands:
                sale_order.write({"order_line": line_commands})
        else:
            order_vals["order_line"] = line_commands
            sale_order = self.env["sale.order"].create(order_vals)

        map_vals = {
            "instance_id": self.id,
            "shopify_order_id": shopify_order_id,
            "shopify_order_name": order_payload.get("name") or "",
            "odoo_order_id": sale_order.id,
            "financial_status": order_payload.get("financial_status") or "",
            "fulfillment_status": order_payload.get("fulfillment_status") or "",
            "last_synced_at": fields.Datetime.now(),
        }
        if mapping:
            mapping.write(map_vals)
        else:
            self.env["shopify.order.mapping"].create(map_vals)

        if (
            self.auto_confirm_orders
            and sale_order.state in ("draft", "sent")
            and (order_payload.get("financial_status") or "") in ("paid", "partially_paid", "authorized")
        ):
            sale_order.action_confirm()
        self._mark_related_cart_as_converted(order_payload, sale_order)

        self._create_invoice_and_payment_for_order(sale_order, order_payload)

        return sale_order

    def _create_invoice_and_payment_for_order(self, sale_order, order_payload):
        self.ensure_one()
        if not self.auto_create_invoice or sale_order.state not in ("sale", "done"):
            return True

        invoices = sale_order.invoice_ids.filtered(lambda inv: inv.move_type == "out_invoice")
        if not invoices:
            invoices = sale_order._create_invoices()
        for invoice in invoices.filtered(lambda inv: inv.state == "draft"):
            invoice.action_post()

        financial_status = (order_payload.get("financial_status") or "").strip().lower()
        if not self.auto_register_payment or financial_status not in ("paid", "partially_paid"):
            return True

        journal = self.payment_journal_id or self.env["account.journal"].search(
            [("company_id", "=", self.company_id.id), ("type", "in", ("bank", "cash"))],
            limit=1,
        )
        if not journal:
            sale_order.message_post(body=_("No bank/cash journal found for payment registration."))
            return True

        for invoice in invoices.filtered(lambda inv: inv.state == "posted" and inv.amount_residual > 0):
            payment_wizard = self.env["account.payment.register"].with_context(
                active_model="account.move",
                active_ids=invoice.ids,
            ).create(
                {
                    "journal_id": journal.id,
                    "amount": invoice.amount_residual,
                    "payment_date": fields.Date.context_today(self),
                }
            )
            payment_wizard.action_create_payments()
        return True

    def _import_orders_from_shopify(self, order_payloads=None):
        self.ensure_one()
        if order_payloads is None:
            params = {"limit": 250, "status": "any"}
            if self.last_order_sync_at:
                params["updated_at_min"] = self._to_shopify_datetime(self.last_order_sync_at)
            try:
                order_payloads = self._shopify_paginated_get("orders.json", params, "orders")
            except UserError:
                if not self._has_local_storefront_config():
                    raise
                return self._import_orders_from_webhook_events()

        count = 0
        for order_payload in order_payloads:
            if self._sync_order_payload(order_payload):
                count += 1

        self.last_order_sync_at = fields.Datetime.now()
        self.message_post(body=_("Imported/updated %s Shopify orders.") % count)
        return count

    def _export_single_product_to_shopify(self, product):
        self.ensure_one()
        mapping = self.env["shopify.product.mapping"].search(
            [("instance_id", "=", self.id), ("odoo_product_id", "=", product.id)],
            limit=1,
        )
        price = product.lst_price or 0.0

        if mapping and mapping.shopify_variant_id:
            self._shopify_request(
                "PUT",
                f"variants/{mapping.shopify_variant_id}.json",
                payload={"variant": {"id": int(mapping.shopify_variant_id), "sku": product.default_code or "", "price": f"{price:.2f}"}},
            )
            mapping.write({"sku": product.default_code or "", "last_synced_at": fields.Datetime.now()})
            return

        payload = {
            "product": {
                "title": product.product_tmpl_id.name,
                "body_html": product.product_tmpl_id.description_sale or "",
                "status": "active" if product.active else "draft",
                "variants": [{"sku": product.default_code or "", "price": f"{price:.2f}", "inventory_management": "shopify"}],
            }
        }
        response, _headers = self._shopify_request("POST", "products.json", payload=payload)
        response_product = response.get("product", {})
        variants = response_product.get("variants", [])
        if not variants:
            return
        variant = variants[0]
        vals = {
            "instance_id": self.id,
            "shopify_product_id": str(response_product.get("id") or ""),
            "shopify_variant_id": str(variant.get("id") or ""),
            "shopify_inventory_item_id": str(variant.get("inventory_item_id") or ""),
            "odoo_product_id": product.id,
            "sku": product.default_code or "",
            "last_synced_at": fields.Datetime.now(),
        }
        if mapping:
            mapping.write(vals)
        else:
            self.env["shopify.product.mapping"].create(vals)

    def _export_products_to_shopify(self):
        self.ensure_one()
        domain = [("sale_ok", "=", True), ("active", "in", [True, False])]
        if self.last_export_sync_at:
            domain.append(("write_date", ">=", self.last_export_sync_at))
        products = self.env["product.product"].search(domain, limit=500)
        exported = 0
        for product in products:
            try:
                self._export_single_product_to_shopify(product)
                exported += 1
            except Exception:
                _logger.exception("Failed exporting product %s to Shopify instance %s", product.id, self.id)
        self.last_export_sync_at = fields.Datetime.now()
        self.message_post(body=_("Exported %s products to Shopify.") % exported)
        return exported

    def _ensure_shopify_location(self):
        self.ensure_one()
        if self.shopify_location_id:
            return int(self.shopify_location_id)
        locations_data, _headers = self._shopify_request("GET", "locations.json", params={"limit": 1})
        locations = locations_data.get("locations", [])
        if not locations:
            raise UserError(_("No Shopify location found to sync inventory."))
        self.shopify_location_id = str(locations[0]["id"])
        return int(self.shopify_location_id)

    def _get_available_qty(self, product):
        self.ensure_one()
        product_ctx = product.with_context(warehouse=self.warehouse_id.id)
        return int(round(product_ctx.qty_available))

    def _export_inventory_to_shopify(self):
        self.ensure_one()
        location_id = self._ensure_shopify_location()
        mappings = self.env["shopify.product.mapping"].search([("instance_id", "=", self.id)])
        synced = 0
        for mapping in mappings:
            if not mapping.shopify_inventory_item_id:
                continue
            qty = self._get_available_qty(mapping.odoo_product_id)
            try:
                self._shopify_request(
                    "POST",
                    "inventory_levels/set.json",
                    payload={
                        "location_id": location_id,
                        "inventory_item_id": int(mapping.shopify_inventory_item_id),
                        "available": qty,
                    },
                )
                synced += 1
            except Exception:
                _logger.exception(
                    "Failed syncing inventory for product %s on instance %s",
                    mapping.odoo_product_id.id,
                    self.id,
                )
        self.last_inventory_sync_at = fields.Datetime.now()
        self.message_post(body=_("Synced inventory for %s mapped products.") % synced)
        return synced

    def process_webhook(self, topic, payload):
        self.ensure_one()
        topic = topic or ""
        if topic in ("products/create", "products/update"):
            self._import_products_from_shopify(product_payloads=[payload])
        elif topic == "products/delete":
            self._delete_product_payload(payload)
        elif topic in ("carts/create", "carts/update", "checkouts/create", "checkouts/update"):
            self._import_carts_from_shopify(cart_payloads=[payload])
        elif topic in ("carts/delete", "checkouts/delete"):
            self._cancel_cart_payload(payload)
        elif topic in ("orders/create", "orders/updated"):
            self._import_orders_from_shopify(order_payloads=[payload])
        else:
            _logger.info("Ignoring unsupported Shopify webhook topic %s", topic)
        return True

    def _export_fulfillment_for_picking(self, picking):
        self.ensure_one()
        if picking.shopify_fulfillment_exported:
            return True
        sale_order = picking.sale_id
        if not sale_order or not sale_order.shopify_order_id:
            return True

        order_id = sale_order.shopify_order_id
        fulfillment_orders_data, _headers = self._shopify_request("GET", f"orders/{order_id}/fulfillment_orders.json")
        fulfillment_orders = fulfillment_orders_data.get("fulfillment_orders", [])
        if not fulfillment_orders:
            sale_order.message_post(body=_("No Shopify fulfillment orders available for export."))
            return True

        tracking_number = picking.carrier_tracking_ref or ""
        tracking_company = picking.carrier_id.name if picking.carrier_id else ""
        tracking_url = getattr(picking, "carrier_tracking_url", "") or ""

        line_items_by_fulfillment_order = [{"fulfillment_order_id": order_data.get("id")} for order_data in fulfillment_orders]
        payload = {
            "fulfillment": {
                "line_items_by_fulfillment_order": line_items_by_fulfillment_order,
                "notify_customer": self.notify_customer_on_fulfillment,
            }
        }
        if tracking_number or tracking_company or tracking_url:
            payload["fulfillment"]["tracking_info"] = {
                "number": tracking_number,
                "company": tracking_company,
                "url": tracking_url,
            }

        fulfillment_data, _headers = self._shopify_request("POST", "fulfillments.json", payload=payload)
        fulfillment = fulfillment_data.get("fulfillment", {})
        picking.write(
            {
                "shopify_fulfillment_exported": True,
                "shopify_fulfillment_id": str(fulfillment.get("id") or ""),
            }
        )
        sale_order.message_post(body=_("Shopify fulfillment exported from delivery %s.") % (picking.name,))
        return True

    @api.model
    def _cron_run_connector_jobs(self):
        instances = self.search([("active", "=", True)])
        for instance in instances:
            try:
                if instance.auto_import_products:
                    instance._import_products_from_shopify()
                if instance.auto_import_carts:
                    instance._import_carts_from_shopify()
                if instance.auto_import_orders:
                    instance._import_orders_from_shopify()
                if instance.auto_export_products:
                    try:
                        instance._export_products_to_shopify()
                    except UserError:
                        if not instance._has_local_storefront_config():
                            raise
                        instance.last_export_sync_at = fields.Datetime.now()
                        instance.message_post(
                            body=_("Scheduled product export skipped in local storefront mode.")
                        )
                if instance.auto_export_inventory:
                    try:
                        instance._export_inventory_to_shopify()
                    except UserError:
                        if not instance._has_local_storefront_config():
                            raise
                        instance.last_inventory_sync_at = fields.Datetime.now()
                        instance.message_post(
                            body=_("Scheduled inventory export skipped in local storefront mode.")
                        )
            except Exception:
                _logger.exception("Scheduled Shopify sync failed for instance %s", instance.id)
                instance.message_post(body=_("Scheduled sync failed; check server logs for details."))
        return True
