# Shopify Odoo Connector

A custom Odoo 19 module that synchronizes products, carts, orders, inventory, and fulfillment between Shopify and Odoo.

**Version:** 19.0.2.0.0
**Author:** Elsner
**License:** LGPL-3

---

## Features

- **Product Sync** — Import products from Shopify (or local storefront API) into Odoo and export Odoo products back to Shopify.
- **Cart / Checkout Sync** — Capture Shopify carts and checkouts as draft quotations in Odoo via webhooks.
- **Order Sync** — Import Shopify orders into Odoo sale orders with automatic customer and partner creation.
- **Inventory Export** — Push Odoo on-hand stock quantities to Shopify inventory levels.
- **Fulfillment Export** — Automatically notify Shopify when a delivery order is validated in Odoo, including tracking info.
- **Webhook Receiver** — HMAC-validated webhook endpoint that processes real-time events from Shopify.
- **Webhook Event Log** — Full audit trail of every webhook received, with payload inspection and error tracking.
- **Scheduled Cron Job** — Runs every 5 minutes to auto-import products/carts/orders and auto-export products/inventory.
- **Multi-instance Support** — Connect multiple Shopify stores to a single Odoo database.
- **Local Storefront Fallback** — Development mode that talks to a local storefront API when the Shopify Admin API is unavailable.

---

## Tech Stack

- Python 3.10
- Odoo 19 (Community or Enterprise)
- PostgreSQL 14+
- Shopify Admin REST API (version `2025-10`)

---

## Prerequisites

Before starting, make sure you have the following installed on your Ubuntu system:

### 1. System Packages

```bash path=null start=null
sudo apt update && sudo apt upgrade -y

sudo apt install -y \
    python3.10 python3.10-venv python3.10-dev \
    build-essential libxml2-dev libxslt1-dev \
    libldap2-dev libsasl2-dev libjpeg-dev \
    libpq-dev libffi-dev zlib1g-dev \
    node-less npm git wget curl
```

### 2. wkhtmltopdf (for PDF reports)

```bash path=null start=null
sudo apt install -y wkhtmltopdf
```

### 3. PostgreSQL

```bash path=null start=null
sudo apt install -y postgresql postgresql-client

# Start the service
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

---

## Local Setup — Step by Step

### Step 1 — Create a PostgreSQL User

Create a database user that matches the `odoo.conf` configuration:

```bash path=null start=null
sudo -u postgres createuser --createdb --pwprompt Root
# Enter the password when prompted (e.g. Root@123)
```

### Step 2 — Clone / Download the Project

If you haven't already, place the project at the expected path:

```bash path=null start=null
sudo mkdir -p /var/www/html/shopifyConnector
# Copy or clone the project into:
# /var/www/html/shopifyConnector/ShopifyOdooConnector
```

The final directory structure should look like:

```
ShopifyOdooConnector/
├── custom/
│   └── addons/
│       └── shopify_odoo_connector/   # The custom module
│           ├── controllers/
│           ├── data/
│           ├── models/
│           ├── security/
│           ├── views/
│           ├── __init__.py
│           └── __manifest__.py
├── data/                              # Odoo data directory
├── data_user/
├── log/                               # Log directory
├── odoo/                              # Odoo source code
├── venv/                              # Python virtual environment
└── odoo.conf                          # Odoo configuration file
```

### Step 3 — Set Up the Python Virtual Environment

```bash path=null start=null
cd /var/www/html/shopifyConnector/ShopifyOdooConnector

# Create venv (skip if already exists)
python3.10 -m venv venv

# Activate
source venv/bin/activate

# Install Odoo dependencies
pip install --upgrade pip
pip install -r odoo/requirements.txt

# Install the module's external dependency
pip install requests
```

### Step 4 — Create Required Directories

```bash path=null start=null
mkdir -p /var/www/html/shopifyConnector/ShopifyOdooConnector/data
mkdir -p /var/www/html/shopifyConnector/ShopifyOdooConnector/log
```

### Step 5 — Review the Configuration File

The configuration lives in `odoo.conf`:

```ini path=/var/www/html/shopifyConnector/ShopifyOdooConnector/odoo.conf start=1
[options]
admin_passwd = Root@***
db_host = 127.0.0.1
db_port = 5432
db_user = Root
db_password = Root@***
db_name = ShopifyOdooConnector
addons_path = /var/www/html/shopifyConnector/ShopifyOdooConnector/odoo/odoo/addons,/var/www/html/shopifyConnector/ShopifyOdooConnector/odoo/addons,/var/www/html/shopifyConnector/ShopifyOdooConnector/custom/addons
data_dir = /var/www/html/shopifyConnector/ShopifyOdooConnector/data
logfile = /var/www/html/shopifyConnector/ShopifyOdooConnector/log/odoo.log
http_port = 8069
http_interface = 0.0.0.0
```

Update `db_user`, `db_password`, and `admin_passwd` as needed for your environment.

### Step 6 — Create the Database

```bash path=null start=null
# Make sure PostgreSQL is running, then create the database:
createdb -U Root -h 127.0.0.1 -p 5432 ShopifyOdooConnector
```

### Step 7 — Initialize Odoo and Install Base Modules

```bash path=null start=null
source /var/www/html/shopifyConnector/ShopifyOdooConnector/venv/bin/activate

/var/www/html/shopifyConnector/ShopifyOdooConnector/odoo/odoo-bin \
    -c /var/www/html/shopifyConnector/ShopifyOdooConnector/odoo.conf \
    -d ShopifyOdooConnector \
    -i base \
    --stop-after-init
```

This initializes the database schema and installs the `base` module.

### Step 8 — Install the Shopify Connector Module

```bash path=null start=null
/var/www/html/shopifyConnector/ShopifyOdooConnector/odoo/odoo-bin \
    -c /var/www/html/shopifyConnector/ShopifyOdooConnector/odoo.conf \
    -d ShopifyOdooConnector \
    -i shopify_odoo_connector \
    --stop-after-init
```

This installs the connector along with its dependencies (`sale_management`, `stock`, `account`, `mail`).

### Step 9 — Start the Odoo Server

```bash path=null start=null
source /var/www/html/shopifyConnector/ShopifyOdooConnector/venv/bin/activate

/var/www/html/shopifyConnector/ShopifyOdooConnector/odoo/odoo-bin \
    -c /var/www/html/shopifyConnector/ShopifyOdooConnector/odoo.conf
```

Odoo will be available at: **http://localhost:8069**

Default login credentials:
- **Email:** admin
- **Password:** admin (or the master password set in `odoo.conf`)

---

## Configuring the Shopify Connector

### Step 1 — Open the Connector

1. Log in to Odoo at `http://localhost:8069`.
2. Navigate to **Shopify Connector → Instances** from the top menu.
3. Click **New** to create a new Shopify instance.

### Step 2 — Fill in Instance Details

| Field | Description |
|---|---|
| **Name** | A friendly name for this connection |
| **Shop URL** | Your Shopify store domain, e.g. `your-store.myshopify.com` |
| **API Version** | Defaults to `2025-10` |
| **Access Token** | Shopify Admin API access token (from your Shopify custom app) |
| **Webhook Secret** | Shopify API secret key for HMAC validation |
| **Webhook Base URL** | Public URL of your Odoo instance (e.g. `https://yourdomain.com`) |
| **Company** | The Odoo company to link |
| **Warehouse** | Warehouse for inventory operations |
| **Pricelist** | Pricelist for pricing |
| **Shopify Location ID** | (Optional) Specific Shopify location for inventory sync |

### Step 3 — Test the Connection

Click the **Test Connection** button in the form header. A success message will appear in the chatter if the connection is valid.

### Step 4 — Register Webhooks

Click **Register Webhooks** to subscribe to the following Shopify events:

- `products/create`, `products/update`, `products/delete`
- `carts/create`, `carts/update`, `carts/delete`
- `checkouts/create`, `checkouts/update`, `checkouts/delete`
- `orders/create`, `orders/updated`

The webhook callback URL will be: `<webhook_base_url>/shopify/webhook/<instance_id>`

### Step 5 — Configure Automation Settings

Under the **Automation** tab, toggle the options:

- **Auto Import Products** — Sync products from Shopify on each cron run
- **Auto Import Carts** — Import cart/checkout data from webhook events
- **Auto Import Orders** — Import orders from Shopify on each cron run
- **Auto Export Products** — Push Odoo product changes to Shopify
- **Auto Export Inventory** — Push stock levels to Shopify
- **Auto Confirm Orders** — Automatically confirm orders with `paid`/`authorized` status
- **Auto Create Invoice** — Create and post invoices for confirmed orders
- **Auto Register Payment** — Register payments automatically (requires a payment journal)
- **Notify Customer on Fulfillment** — Send Shopify fulfillment notification emails

---

## Sync Operations (Manual)

From the Shopify Instance form, you can trigger these actions manually:

- **Import Products** — Fetches products from Shopify Admin API (or local storefront)
- **Import Carts** — Processes cart webhook events into draft quotations
- **Import Orders** — Fetches orders from Shopify Admin API
- **Export Products** — Pushes Odoo products to Shopify
- **Export Inventory** — Pushes stock quantities to Shopify

---

## Scheduled Automation (Cron)

A cron job runs every **5 minutes** and executes all enabled auto-sync operations for each active Shopify instance. The cron is defined in `data/ir_cron_data.xml` and can be adjusted from **Settings → Technical → Scheduled Actions → Shopify Connector Sync**.

---

## Module Structure

```
shopify_odoo_connector/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── main.py                      # Webhook endpoint (/shopify/webhook/<id>)
├── data/
│   └── ir_cron_data.xml             # Scheduled action (every 5 min)
├── models/
│   ├── __init__.py
│   ├── shopify_instance.py          # Core model: connection, sync logic, API calls
│   ├── shopify_product_mapping.py   # Maps Shopify variants ↔ Odoo products
│   ├── shopify_cart_mapping.py      # Maps Shopify carts ↔ Odoo draft quotations
│   ├── shopify_order_mapping.py     # Maps Shopify orders ↔ Odoo sale orders
│   ├── shopify_webhook_event.py     # Webhook event audit log
│   ├── sale_order.py                # Extends sale.order with Shopify fields
│   └── stock_picking.py             # Extends stock.picking for fulfillment export
├── security/
│   └── ir.model.access.csv          # Access rights (user: read / manager: full)
└── views/
    ├── shopify_instance_views.xml   # Forms, lists, and actions
    └── shopify_menu.xml             # Top-level Shopify Connector menu
```

---

## Data Flow

```
Shopify Store
    │
    ├──[Webhook POST]──→  /shopify/webhook/<id>  ──→  Webhook Event Log
    │                                                      │
    │                                              ┌───────┴────────┐
    │                                              ▼                ▼
    │                                     Product Sync        Cart / Order Sync
    │                                              │                │
    ├──[Admin API GET]──→  Import Products ──→  product.product     │
    │                                           + mapping           │
    ├──[Admin API GET]──→  Import Orders  ──→  sale.order ──────────┘
    │                                           + mapping
    │
    ◄──[Admin API POST]──  Export Products  ◄──  product.product
    ◄──[Admin API POST]──  Export Inventory ◄──  stock.warehouse
    ◄──[Admin API POST]──  Export Fulfillment ◄── stock.picking (on validate)
```

---

## Updating the Module

After making code changes, update the module in Odoo:

```bash path=null start=null
/var/www/html/shopifyConnector/ShopifyOdooConnector/odoo/odoo-bin \
    -c /var/www/html/shopifyConnector/ShopifyOdooConnector/odoo.conf \
    -d ShopifyOdooConnector \
    -u shopify_odoo_connector \
    --stop-after-init
```

Then restart the Odoo server.

---

## Logs

Server logs are written to:

```
/var/www/html/shopifyConnector/ShopifyOdooConnector/log/odoo.log
```

Tail logs in real time:

```bash path=null start=null
tail -f /var/www/html/shopifyConnector/ShopifyOdooConnector/log/odoo.log
```

---

## Troubleshooting

- **"Unable to connect to Shopify"** — Verify `shop_url` and `access_token` in the instance form. Ensure the Shopify custom app has the required API scopes.
- **Webhook returns 401** — Check that `webhook_secret` matches your Shopify app's API secret key.
- **Products not syncing** — Confirm `auto_import_products` is enabled and the cron job is active.
- **Database connection errors** — Verify PostgreSQL is running and `db_user`/`db_password` in `odoo.conf` are correct.
- **Module not found** — Ensure `addons_path` in `odoo.conf` includes the `custom/addons` directory.

---

## Shopify App Setup (Quick Reference)

1. Go to your [Shopify Partner Dashboard](https://partners.shopify.com/) or **Shopify Admin → Settings → Apps and sales channels → Develop apps**.
2. Create a custom app.
3. Under **API credentials**, configure the following **Admin API scopes**:
   - `read_products`, `write_products`
   - `read_orders`, `write_orders`
   - `read_inventory`, `write_inventory`
   - `read_fulfillments`, `write_fulfillments`
   - `read_locations`
4. Install the app on your store.
5. Copy the **Admin API access token** and **API secret key** into the Odoo Shopify Instance form.

---

## License

This project is licensed under [LGPL-3](https://www.gnu.org/licenses/lgpl-3.0.html).
