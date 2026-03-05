const crypto = require("crypto");
require("dotenv").config();

const topic = process.argv[2] || "products/create";
const instanceId = process.env.ODOO_INSTANCE_ID || "1";
const odooBaseUrl = (process.env.ODOO_BASE_URL || "http://127.0.0.1:8069").replace(/\/$/, "");
const webhookSecret = process.env.SHOPIFY_WEBHOOK_SECRET || "";
const targetUrl = `${odooBaseUrl}/shopify/webhook/${instanceId}`;

function getPayloadByTopic(selectedTopic) {
  if (selectedTopic === "products/create" || selectedTopic === "products/update") {
    return {
      id: 990001001,
      title: "Kartik Test Product",
      body_html: "Demo product from local webhook sender",
      status: "active",
      variants: [
        {
          id: 99000100111,
          product_id: 990001001,
          sku: "KARTIK-PROD-001",
          price: "199.00",
          inventory_item_id: 99000100199
        }
      ]
    };
  }

  if (selectedTopic === "carts/create" || selectedTopic === "carts/update" || selectedTopic === "checkouts/create" || selectedTopic === "checkouts/update") {
    return {
      id: 880001001,
      token: "cart-token-880001001",
      checkout_token: "checkout-token-880001001",
      email: "kartik.k@elsner.com",
      line_items: [
        {
          id: 1,
          product_id: 990001001,
          variant_id: 99000100111,
          title: "Kartik Test Product",
          sku: "KARTIK-PROD-001",
          quantity: 2,
          price: "199.00"
        }
      ]
    };
  }

  if (selectedTopic === "orders/create" || selectedTopic === "orders/updated") {
    return {
      id: 770001001,
      name: "#KT1001",
      email: "kartik.k@elsner.com",
      financial_status: "paid",
      fulfillment_status: null,
      checkout_token: "checkout-token-880001001",
      cart_token: "cart-token-880001001",
      customer: {
        first_name: "Kartik",
        last_name: "K",
        email: "kartik.k@elsner.com",
        phone: "9876543210"
      },
      billing_address: {
        first_name: "Kartik",
        last_name: "K",
        phone: "9876543210",
        address1: "Test Street",
        city: "Ahmedabad",
        zip: "380015"
      },
      line_items: [
        {
          id: 1,
          product_id: 990001001,
          variant_id: 99000100111,
          name: "Kartik Test Product",
          title: "Kartik Test Product",
          sku: "KARTIK-PROD-001",
          quantity: 2,
          price: "199.00"
        }
      ],
      shipping_lines: [
        {
          price: "20.00"
        }
      ]
    };
  }

  return { id: 1 };
}

async function sendWebhook() {
  if (!webhookSecret) {
    throw new Error("SHOPIFY_WEBHOOK_SECRET is required in .env");
  }
  const payload = getPayloadByTopic(topic);
  const body = Buffer.from(JSON.stringify(payload), "utf-8");
  const hmac = crypto.createHmac("sha256", webhookSecret).update(body).digest("base64");

  const response = await fetch(targetUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Shopify-Topic": topic,
      "X-Shopify-Hmac-Sha256": hmac
    },
    body
  });

  const text = await response.text();
  console.log(JSON.stringify({ topic, targetUrl, status: response.status, body: text }, null, 2));
}

sendWebhook().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
