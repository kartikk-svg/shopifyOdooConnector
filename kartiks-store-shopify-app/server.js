const crypto = require("crypto");
const express = require("express");
const fs = require("fs");
const path = require("path");
require("dotenv").config();

const app = express();
const port = Number(process.env.PORT || 3010);
const appName = process.env.SHOPIFY_APP_NAME || "Kartik's store";
const webhookSecret = process.env.SHOPIFY_WEBHOOK_SECRET || "";
const odooWebhookUrl = process.env.ODOO_WEBHOOK_URL || "";
const publicDir = path.join(__dirname, "public");
const dataDir = path.join(__dirname, "data");
const productsFile = path.join(dataDir, "products.json");

const supportedTopics = [
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
];

const defaultProducts = [
  {
    id: "kartik-prod-001",
    title: "Kartik Smart Fitness Band",
    description: "Track steps, calories, heart-rate and sleep with week-long battery backup.",
    category: "Wearables",
    sku: "KARTIK-PROD-001",
    price: 199.0,
    compare_at_price: 249.0,
    image: "https://picsum.photos/seed/kartik-fit-band/720/540",
    featured: true,
    shopify_product_id: "990001001",
    shopify_variant_id: "99000100111",
    shopify_inventory_item_id: "99000100199",
  },
  {
    id: "kartik-prod-002",
    title: "Kartik Noise-Canceling Earbuds",
    description: "Premium in-ear audio with ANC and low-latency game mode.",
    category: "Audio",
    sku: "KARTIK-PROD-002",
    price: 149.0,
    compare_at_price: 189.0,
    image: "https://picsum.photos/seed/kartik-earbuds/720/540",
    featured: true,
    shopify_product_id: "990001002",
    shopify_variant_id: "99000100211",
    shopify_inventory_item_id: "99000100299",
  },
  {
    id: "kartik-prod-003",
    title: "Kartik Magnetic Wireless Charger",
    description: "Fast wireless charging dock compatible with phones and earbuds.",
    category: "Accessories",
    sku: "KARTIK-PROD-003",
    price: 89.0,
    compare_at_price: 109.0,
    image: "https://picsum.photos/seed/kartik-charger/720/540",
    featured: false,
    shopify_product_id: "990001003",
    shopify_variant_id: "99000100311",
    shopify_inventory_item_id: "99000100399",
  },
  {
    id: "kartik-prod-004",
    title: "Kartik Laptop Sleeve Pro 14”",
    description: "Water-resistant sleeve with soft microfiber interior and accessory pocket.",
    category: "Accessories",
    sku: "KARTIK-PROD-004",
    price: 59.0,
    compare_at_price: 79.0,
    image: "https://picsum.photos/seed/kartik-sleeve/720/540",
    featured: false,
    shopify_product_id: "990001004",
    shopify_variant_id: "99000100411",
    shopify_inventory_item_id: "99000100499",
  },
  {
    id: "kartik-prod-005",
    title: "Kartik Ergonomic Mechanical Keyboard",
    description: "Hot-swappable switches, RGB backlight and ergonomic typing angle.",
    category: "Peripherals",
    sku: "KARTIK-PROD-005",
    price: 229.0,
    compare_at_price: 269.0,
    image: "https://picsum.photos/seed/kartik-keyboard/720/540",
    featured: true,
    shopify_product_id: "990001005",
    shopify_variant_id: "99000100511",
    shopify_inventory_item_id: "99000100599",
  },
  {
    id: "kartik-prod-006",
    title: "Kartik 4K Streaming Webcam",
    description: "Ultra-clear 4K webcam with auto framing and low-light enhancement.",
    category: "Peripherals",
    sku: "KARTIK-PROD-006",
    price: 179.0,
    compare_at_price: 219.0,
    image: "https://picsum.photos/seed/kartik-webcam/720/540",
    featured: false,
    shopify_product_id: "990001006",
    shopify_variant_id: "99000100611",
    shopify_inventory_item_id: "99000100699",
  },
  {
    id: "kartik-prod-007",
    title: "Kartik Portable SSD 1TB",
    description: "High-speed USB-C portable SSD with rugged design for travel.",
    category: "Storage",
    sku: "KARTIK-PROD-007",
    price: 159.0,
    compare_at_price: 199.0,
    image: "https://picsum.photos/seed/kartik-ssd/720/540",
    featured: true,
    shopify_product_id: "990001007",
    shopify_variant_id: "99000100711",
    shopify_inventory_item_id: "99000100799",
  },
  {
    id: "kartik-prod-008",
    title: "Kartik Smart Desk Lamp",
    description: "Adjustable smart lamp with touch controls and scene-based presets.",
    category: "Home",
    sku: "KARTIK-PROD-008",
    price: 99.0,
    compare_at_price: 129.0,
    image: "https://picsum.photos/seed/kartik-lamp/720/540",
    featured: false,
    shopify_product_id: "990001008",
    shopify_variant_id: "99000100811",
    shopify_inventory_item_id: "99000100899",
  },
];

function ensureProductStorage() {
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }
  if (!fs.existsSync(productsFile)) {
    fs.writeFileSync(productsFile, JSON.stringify(defaultProducts, null, 2), "utf-8");
  }
}

function loadProducts() {
  ensureProductStorage();
  try {
    const rows = JSON.parse(fs.readFileSync(productsFile, "utf-8"));
    if (Array.isArray(rows)) {
      return rows;
    }
  } catch (_error) {
    // fallback below
  }
  fs.writeFileSync(productsFile, JSON.stringify(defaultProducts, null, 2), "utf-8");
  return [...defaultProducts];
}

function saveProducts(rows) {
  ensureProductStorage();
  fs.writeFileSync(productsFile, JSON.stringify(rows, null, 2), "utf-8");
}

let storefrontProducts = loadProducts();

app.use("/shopify/webhook", express.raw({ type: "*/*", limit: "2mb" }));
app.use(express.json({ limit: "2mb" }));
app.use("/assets", express.static(publicDir));

function getAppConfig() {
  return {
    app_name: appName,
    status: "running",
    webhook_forward_target: odooWebhookUrl || "not-configured",
    has_webhook_secret: Boolean(webhookSecret),
    supported_topics: supportedTopics,
  };
}

function refreshProducts() {
  storefrontProducts = loadProducts();
  return storefrontProducts;
}

function servePage(res, fileName) {
  const filePath = path.join(publicDir, fileName);
  if (fs.existsSync(filePath)) {
    return res.sendFile(filePath);
  }
  return res.status(404).send("Page not found");
}

function verifyShopifyHmac(secret, bodyBuffer, receivedHmac) {
  if (!secret || !receivedHmac) return false;
  const digest = crypto.createHmac("sha256", secret).update(bodyBuffer).digest("base64");
  if (digest.length !== receivedHmac.length) {
    return false;
  }
  return crypto.timingSafeEqual(Buffer.from(digest), Buffer.from(receivedHmac));
}

function signPayload(secret, bodyBuffer) {
  return crypto.createHmac("sha256", secret).update(bodyBuffer).digest("base64");
}

async function forwardToOdoo(topic, bodyBuffer, hmacHeader) {
  if (!odooWebhookUrl) {
    throw new Error("ODOO_WEBHOOK_URL is not configured");
  }
  const response = await fetch(odooWebhookUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Shopify-Topic": topic || "",
      "X-Shopify-Hmac-Sha256": hmacHeader || "",
    },
    body: bodyBuffer,
  });
  const text = await response.text();
  return { status: response.status, body: text };
}

function findProductById(productId) {
  return storefrontProducts.find((product) => product.id === productId);
}

function toIntString(value, fallback) {
  const parsed = Number.parseInt(String(value || "").trim(), 10);
  if (Number.isFinite(parsed) && parsed > 0) {
    return String(parsed);
  }
  return String(fallback);
}

function nextNumericProductId() {
  const maxId = storefrontProducts.reduce((max, product) => {
    const current = Number.parseInt(String(product.shopify_product_id || "0"), 10);
    return Number.isFinite(current) && current > max ? current : max;
  }, 990001000);
  return String(maxId + 1);
}

function normalizeSlug(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
}

function ensureUniqueProductId(baseId) {
  const exists = (id) => storefrontProducts.some((row) => row.id === id);
  if (!exists(baseId)) return baseId;
  let i = 2;
  while (exists(`${baseId}-${i}`)) i += 1;
  return `${baseId}-${i}`;
}

function normalizeProductInput(rawInput = {}, options = {}) {
  const partial = Boolean(options.partial);
  const input = rawInput || {};
  const title = String(input.title || "").trim();
  const description = String(input.description || "").trim();
  const category = String(input.category || "").trim();
  const sku = String(input.sku || "").trim();
  const image = String(input.image || "").trim();
  const featured = typeof input.featured === "boolean" ? input.featured : undefined;
  const price = input.price !== undefined ? Number(input.price) : undefined;
  const compareAtPrice = input.compare_at_price !== undefined ? Number(input.compare_at_price) : undefined;
  const errors = [];

  if (!partial || input.title !== undefined) {
    if (!title) errors.push("title is required");
  }
  if (!partial || input.sku !== undefined) {
    if (!sku) errors.push("sku is required");
  }
  if (!partial || input.price !== undefined) {
    if (!Number.isFinite(price) || price <= 0) errors.push("price must be a number greater than 0");
  }
  if (input.compare_at_price !== undefined) {
    if (!Number.isFinite(compareAtPrice) || compareAtPrice < 0) {
      errors.push("compare_at_price must be a non-negative number");
    }
  }

  return {
    values: {
      title,
      description,
      category,
      sku,
      image,
      featured,
      price,
      compare_at_price: compareAtPrice,
    },
    errors,
  };
}

function buildProductPayload(product) {
  return {
    id: Number(product.shopify_product_id),
    title: product.title,
    body_html: product.description || "",
    status: "active",
    variants: [
      {
        id: Number(product.shopify_variant_id),
        product_id: Number(product.shopify_product_id),
        sku: product.sku || "",
        price: Number(product.price || 0).toFixed(2),
        inventory_item_id: Number(product.shopify_inventory_item_id),
      },
    ],
  };
}

async function forwardProductEvent(topic, product) {
  if (!odooWebhookUrl || !webhookSecret) {
    return { skipped: true, reason: "webhook config missing" };
  }
  const payload = buildProductPayload(product);
  const bodyBuffer = Buffer.from(JSON.stringify(payload), "utf-8");
  const hmac = signPayload(webhookSecret, bodyBuffer);
  const result = await forwardToOdoo(topic, bodyBuffer, hmac);
  return { skipped: false, topic, payload, odoo_status: result.status, odoo_response: result.body };
}

function normalizeCartItems(rawItems) {
  if (!Array.isArray(rawItems)) {
    return [];
  }
  const merged = new Map();
  for (const row of rawItems) {
    const productId = String(row?.product_id || row?.id || "").trim();
    const quantity = Number(row?.quantity || 0);
    if (!productId || !Number.isFinite(quantity) || quantity <= 0) {
      continue;
    }
    if (!findProductById(productId)) {
      continue;
    }
    merged.set(productId, (merged.get(productId) || 0) + quantity);
  }
  return Array.from(merged.entries()).map(([product_id, quantity]) => ({ product_id, quantity }));
}

function normalizeCartToken(rawToken) {
  const cleaned = String(rawToken || "").trim();
  if (cleaned) {
    return cleaned.slice(0, 96);
  }
  return `cart-${Date.now()}-${Math.floor(Math.random() * 1000000)}`;
}

function numericIdFromToken(token) {
  const digits = String(token || "").replace(/\D/g, "");
  if (digits) {
    const lastDigits = digits.slice(-12);
    const parsed = Number.parseInt(lastDigits, 10);
    if (Number.isFinite(parsed) && parsed > 0) {
      return parsed;
    }
  }
  return Date.now();
}

function normalizeCustomer(rawCustomer = {}) {
  const firstName = String(rawCustomer.first_name || "").trim();
  const lastName = String(rawCustomer.last_name || "").trim();
  const email = String(rawCustomer.email || "").trim();
  const phone = String(rawCustomer.phone || "").trim();
  const address1 = String(rawCustomer.address1 || "").trim();
  const city = String(rawCustomer.city || "").trim();
  const zip = String(rawCustomer.zip || "").trim();

  if (!firstName || !email) {
    return { error: "Customer first name and email are required." };
  }

  return {
    customer: {
      first_name: firstName,
      last_name: lastName || "Customer",
      email,
      phone,
      address1,
      city,
      zip,
    },
  };
}

function buildCartPayloadFromItems(cartItems, options = {}) {
  const cartToken = normalizeCartToken(options.cart_token || "");
  const checkoutToken = normalizeCartToken(options.checkout_token || cartToken);
  const cartId = numericIdFromToken(cartToken);
  const email = String(options.email || "").trim();
  const lineItems = cartItems
    .map((cartRow, index) => {
      const product = findProductById(cartRow.product_id);
      if (!product) return null;
      return {
        id: index + 1,
        product_id: Number(product.shopify_product_id),
        variant_id: Number(product.shopify_variant_id),
        title: product.title,
        sku: product.sku,
        quantity: Number(cartRow.quantity),
        price: Number(product.price).toFixed(2),
      };
    })
    .filter(Boolean);

  return {
    id: cartId,
    token: cartToken,
    checkout_token: checkoutToken,
    email,
    line_items: lineItems,
  };
}

function buildOrderPayloadFromCheckout(customer, cartItems, options = {}) {
  const cartToken = normalizeCartToken(options.cart_token || "");
  const checkoutToken = normalizeCartToken(options.checkout_token || cartToken);
  const orderId = Date.now();
  const orderName = `#KT${String(orderId).slice(-6)}`;
  const lineItems = [];
  let subtotal = 0;

  cartItems.forEach((cartRow, index) => {
    const product = findProductById(cartRow.product_id);
    if (!product) {
      return;
    }
    const quantity = Number(cartRow.quantity);
    const unitPrice = Number(product.price);
    subtotal += unitPrice * quantity;
    lineItems.push({
      id: index + 1,
      product_id: Number(product.shopify_product_id),
      variant_id: Number(product.shopify_variant_id),
      name: product.title,
      title: product.title,
      sku: product.sku,
      quantity,
      price: unitPrice.toFixed(2),
    });
  });

  const shipping = subtotal >= 500 ? 0 : 25;
  const total = subtotal + shipping;
  const payload = {
    id: orderId,
    name: orderName,
    email: customer.email,
    financial_status: "paid",
    fulfillment_status: null,
    checkout_token: checkoutToken,
    cart_token: cartToken,
    customer: {
      first_name: customer.first_name,
      last_name: customer.last_name,
      email: customer.email,
      phone: customer.phone || "",
    },
    billing_address: {
      first_name: customer.first_name,
      last_name: customer.last_name,
      phone: customer.phone || "",
      address1: customer.address1 || "",
      city: customer.city || "",
      zip: customer.zip || "",
    },
    line_items: lineItems,
    shipping_lines: [{ price: shipping.toFixed(2) }],
    currency: "INR",
    total_price: total.toFixed(2),
  };

  return { payload, orderName, orderId, subtotal, shipping, total };
}

function buildSamplePayload(topic) {
  const firstProduct = storefrontProducts[0];
  if (!firstProduct) {
    return { id: 1 };
  }
  if (topic === "products/create" || topic === "products/update" || topic === "products/delete") {
    return buildProductPayload(firstProduct);
  }

  if (
    topic === "carts/create" ||
    topic === "carts/update" ||
    topic === "checkouts/create" ||
    topic === "checkouts/update"
  ) {
    return {
      id: 880001001,
      token: "cart-token-880001001",
      checkout_token: "checkout-token-880001001",
      email: "kartik.k@elsner.com",
      line_items: [
        {
          id: 1,
          product_id: Number(firstProduct.shopify_product_id),
          variant_id: Number(firstProduct.shopify_variant_id),
          title: firstProduct.title,
          sku: firstProduct.sku,
          quantity: 2,
          price: Number(firstProduct.price).toFixed(2),
        },
      ],
    };
  }

  if (topic === "orders/create" || topic === "orders/updated") {
    const { payload } = buildOrderPayloadFromCheckout(
      {
        first_name: "Kartik",
        last_name: "K",
        email: "kartik.k@elsner.com",
        phone: "9876543210",
        address1: "Test Street",
        city: "Ahmedabad",
        zip: "380015",
      },
      [
        { product_id: firstProduct.id, quantity: 1 },
      ]
    );
    return payload;
  }

  return { id: 1 };
}

app.get("/", (_req, res) => servePage(res, "index.html"));
app.get("/products", (_req, res) => servePage(res, "products.html"));
app.get("/product", (_req, res) => servePage(res, "product.html"));
app.get("/cart", (_req, res) => servePage(res, "cart.html"));
app.get("/checkout", (_req, res) => servePage(res, "checkout.html"));
app.get("/order-success", (_req, res) => servePage(res, "order-success.html"));
app.get("/admin/tester", (_req, res) => servePage(res, "admin-tester.html"));
app.get("/admin/products", (_req, res) => servePage(res, "admin-products.html"));

app.get("/api/config", (_req, res) => {
  return res.json(getAppConfig());
});

app.get("/api/store/config", (_req, res) => {
  refreshProducts();
  return res.json({
    app_name: appName,
    currency_symbol: "₹",
    free_shipping_threshold: 500,
    shipping_fee: 25,
    product_count: storefrontProducts.length,
  });
});

app.get("/api/store/products", (req, res) => {
  refreshProducts();
  const featuredOnly = String(req.query.featured || "").toLowerCase();
  const rows = featuredOnly === "1" || featuredOnly === "true"
    ? storefrontProducts.filter((row) => row.featured)
    : storefrontProducts;
  return res.json(rows);
});

app.get("/api/store/products/:id", (req, res) => {
  refreshProducts();
  const product = findProductById(req.params.id);
  if (!product) {
    return res.status(404).json({ ok: false, error: "Product not found" });
  }
  return res.json(product);
});

app.post("/api/store/products", async (req, res) => {
  refreshProducts();
  const { values, errors } = normalizeProductInput(req.body || {}, { partial: false });
  if (errors.length) {
    return res.status(400).json({ ok: false, error: errors.join(", ") });
  }

  const productSlug = normalizeSlug(values.title || "product") || "product";
  const candidateId = String(req.body?.id || `${productSlug}-${Date.now()}`).trim();
  const id = ensureUniqueProductId(candidateId);
  const productId = nextNumericProductId();
  const variantId = `${productId}11`;
  const inventoryItemId = `${productId}99`;
  const newProduct = {
    id,
    title: values.title,
    description: values.description || "",
    category: values.category || "General",
    sku: values.sku,
    price: Number(values.price),
    compare_at_price:
      Number.isFinite(values.compare_at_price) && values.compare_at_price >= 0
        ? Number(values.compare_at_price)
        : Number(values.price),
    image: values.image || `https://picsum.photos/seed/${encodeURIComponent(id)}/720/540`,
    featured: values.featured === true,
    shopify_product_id: toIntString(req.body?.shopify_product_id, productId),
    shopify_variant_id: toIntString(req.body?.shopify_variant_id, variantId),
    shopify_inventory_item_id: toIntString(req.body?.shopify_inventory_item_id, inventoryItemId),
  };

  storefrontProducts.push(newProduct);
  saveProducts(storefrontProducts);

  let webhook = null;
  try {
    webhook = await forwardProductEvent("products/create", newProduct);
  } catch (error) {
    webhook = { skipped: false, error: error.message };
  }

  return res.status(201).json({ ok: true, product: newProduct, webhook });
});

app.put("/api/store/products/:id", async (req, res) => {
  refreshProducts();
  const product = findProductById(req.params.id);
  if (!product) {
    return res.status(404).json({ ok: false, error: "Product not found" });
  }
  const { values, errors } = normalizeProductInput(req.body || {}, { partial: true });
  if (errors.length) {
    return res.status(400).json({ ok: false, error: errors.join(", ") });
  }

  if (req.body?.title !== undefined) product.title = values.title;
  if (req.body?.description !== undefined) product.description = values.description;
  if (req.body?.category !== undefined) product.category = values.category || "General";
  if (req.body?.sku !== undefined) product.sku = values.sku;
  if (req.body?.price !== undefined) product.price = Number(values.price);
  if (req.body?.compare_at_price !== undefined) product.compare_at_price = Number(values.compare_at_price);
  if (req.body?.image !== undefined) product.image = values.image;
  if (req.body?.featured !== undefined) product.featured = values.featured === true;

  saveProducts(storefrontProducts);

  let webhook = null;
  try {
    webhook = await forwardProductEvent("products/update", product);
  } catch (error) {
    webhook = { skipped: false, error: error.message };
  }

  return res.json({ ok: true, product, webhook });
});

app.delete("/api/store/products/:id", async (req, res) => {
  refreshProducts();
  const index = storefrontProducts.findIndex((row) => row.id === req.params.id);
  if (index === -1) {
    return res.status(404).json({ ok: false, error: "Product not found" });
  }
  const product = storefrontProducts[index];
  storefrontProducts.splice(index, 1);
  saveProducts(storefrontProducts);

  let webhook = null;
  try {
    webhook = await forwardProductEvent("products/delete", product);
  } catch (error) {
    webhook = { skipped: false, error: error.message };
  }

  return res.json({ ok: true, deleted_product: product, webhook });
});

app.post("/api/store/checkout", async (req, res) => {
  refreshProducts();
  if (!webhookSecret) {
    return res.status(400).json({ ok: false, error: "SHOPIFY_WEBHOOK_SECRET is not configured" });
  }
  if (!odooWebhookUrl) {
    return res.status(400).json({ ok: false, error: "ODOO_WEBHOOK_URL is not configured" });
  }

  const cartItems = normalizeCartItems(req.body?.cart);
  if (!cartItems.length) {
    return res.status(400).json({ ok: false, error: "Cart is empty or invalid" });
  }

  const normalizedCustomer = normalizeCustomer(req.body?.customer || {});
  if (normalizedCustomer.error) {
    return res.status(400).json({ ok: false, error: normalizedCustomer.error });
  }
  const cartToken = normalizeCartToken(req.body?.cart_token || "");
  const checkoutToken = normalizeCartToken(req.body?.checkout_token || cartToken);

  const { payload, orderName, orderId, subtotal, shipping, total } = buildOrderPayloadFromCheckout(
    normalizedCustomer.customer,
    cartItems,
    {
      cart_token: cartToken,
      checkout_token: checkoutToken,
    }
  );
  const bodyBuffer = Buffer.from(JSON.stringify(payload), "utf-8");
  const hmac = signPayload(webhookSecret, bodyBuffer);

  try {
    const forwardResult = await forwardToOdoo("orders/create", bodyBuffer, hmac);
    if (forwardResult.status >= 400) {
      return res.status(502).json({
        ok: false,
        error: "Odoo webhook rejected checkout payload",
        odoo_status: forwardResult.status,
        odoo_response: forwardResult.body,
      });
    }
    return res.json({
      ok: true,
      order_id: orderId,
      order_name: orderName,
      cart_token: cartToken,
      checkout_token: checkoutToken,
      subtotal: subtotal.toFixed(2),
      shipping: shipping.toFixed(2),
      total: total.toFixed(2),
      odoo_status: forwardResult.status,
      odoo_response: forwardResult.body,
    });
  } catch (error) {
    return res.status(500).json({ ok: false, error: error.message });
  }
});

app.get("/health", (_req, res) => {
  res.status(200).send("ok");
});

app.post("/api/store/cart/sync", async (req, res) => {
  refreshProducts();
  if (!webhookSecret) {
    return res.status(400).json({ ok: false, error: "SHOPIFY_WEBHOOK_SECRET is not configured" });
  }
  if (!odooWebhookUrl) {
    return res.status(400).json({ ok: false, error: "ODOO_WEBHOOK_URL is not configured" });
  }

  const cartItems = normalizeCartItems(req.body?.cart || []);
  const cartToken = normalizeCartToken(req.body?.cart_token || "");
  const checkoutToken = normalizeCartToken(req.body?.checkout_token || cartToken);
  const email = String(req.body?.email || "").trim();
  const hasItems = cartItems.length > 0;
  const topic = hasItems ? "carts/update" : "carts/delete";
  const payload = hasItems
    ? buildCartPayloadFromItems(cartItems, {
      cart_token: cartToken,
      checkout_token: checkoutToken,
      email,
    })
    : {
      id: numericIdFromToken(cartToken),
      token: cartToken,
      checkout_token: checkoutToken,
      email,
      line_items: [],
    };
  const bodyBuffer = Buffer.from(JSON.stringify(payload), "utf-8");
  const hmac = signPayload(webhookSecret, bodyBuffer);

  try {
    const forwardResult = await forwardToOdoo(topic, bodyBuffer, hmac);
    return res.json({
      ok: true,
      topic,
      cart_token: cartToken,
      checkout_token: checkoutToken,
      item_count: cartItems.reduce((sum, row) => sum + Number(row.quantity || 0), 0),
      odoo_status: forwardResult.status,
      odoo_response: forwardResult.body,
    });
  } catch (error) {
    return res.status(500).json({ ok: false, error: error.message });
  }
});

app.post("/api/test-webhook", async (req, res) => {
  refreshProducts();
  const topic = String(req.body?.topic || "").trim();
  if (!topic) {
    return res.status(400).json({ ok: false, error: "topic is required" });
  }
  if (!supportedTopics.includes(topic)) {
    return res.status(400).json({ ok: false, error: `unsupported topic: ${topic}` });
  }
  if (!webhookSecret) {
    return res.status(400).json({ ok: false, error: "SHOPIFY_WEBHOOK_SECRET is not configured" });
  }

  const payload = req.body?.payload || buildSamplePayload(topic);
  const bodyBuffer = Buffer.from(JSON.stringify(payload), "utf-8");
  const hmac = signPayload(webhookSecret, bodyBuffer);

  try {
    const forwardResult = await forwardToOdoo(topic, bodyBuffer, hmac);
    return res.json({
      ok: true,
      topic,
      odoo_status: forwardResult.status,
      odoo_response: forwardResult.body,
      payload,
    });
  } catch (error) {
    return res.status(500).json({ ok: false, error: error.message });
  }
});

app.post("/shopify/webhook", async (req, res) => {
  const topic = req.header("X-Shopify-Topic") || "";
  const receivedHmac = req.header("X-Shopify-Hmac-Sha256") || "";
  const bodyBuffer = Buffer.isBuffer(req.body)
    ? req.body
    : Buffer.from(JSON.stringify(req.body || {}), "utf-8");

  if (!verifyShopifyHmac(webhookSecret, bodyBuffer, receivedHmac)) {
    return res.status(401).json({ ok: false, error: "invalid webhook signature" });
  }

  try {
    const forwardResult = await forwardToOdoo(topic, bodyBuffer, receivedHmac);
    return res.status(200).json({
      ok: true,
      app_name: appName,
      forwarded_to_odoo: true,
      odoo_status: forwardResult.status,
      odoo_response: forwardResult.body,
    });
  } catch (error) {
    return res.status(500).json({ ok: false, error: error.message });
  }
});

app.listen(port, () => {
  console.log(`[${appName}] listening on port ${port}`);
});
