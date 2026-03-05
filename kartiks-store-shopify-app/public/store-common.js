(() => {
  const CART_KEY = "kartik_store_cart_v1";
  const CART_TOKEN_KEY = "kartik_store_cart_token_v1";
  const money = (amount) => `₹${Number(amount || 0).toFixed(2)}`;
  let cartSyncTimer = null;

  function readCart() {
    try {
      const raw = localStorage.getItem(CART_KEY);
      const rows = JSON.parse(raw || "[]");
      if (!Array.isArray(rows)) return [];
      return rows
        .map((row) => ({
          product_id: String(row?.product_id || "").trim(),
          quantity: Number(row?.quantity || 0),
        }))
        .filter((row) => row.product_id && Number.isFinite(row.quantity) && row.quantity > 0);
    } catch (_error) {
      return [];
    }
  }

  async function syncCartWithOdoo(options = {}) {
    const rows = readCart();
    const cartToken = options.cart_token || getOrCreateCartToken();
    const checkoutToken = options.checkout_token || cartToken;
    const payload = {
      cart_token: cartToken,
      checkout_token: checkoutToken,
      email: String(options.email || "").trim(),
      cart: rows,
    };
    return fetchJson("/api/store/cart/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  function queueCartSync(options = {}) {
    if (cartSyncTimer) {
      clearTimeout(cartSyncTimer);
    }
    cartSyncTimer = window.setTimeout(() => {
      syncCartWithOdoo(options).catch(() => {});
    }, 180);
  }

  function writeCart(rows) {
    localStorage.setItem(CART_KEY, JSON.stringify(rows));
  }

  function getOrCreateCartToken() {
    let token = String(localStorage.getItem(CART_TOKEN_KEY) || "").trim();
    if (!token) {
      token = `cart-${Date.now()}-${Math.floor(Math.random() * 1000000)}`;
      localStorage.setItem(CART_TOKEN_KEY, token);
    }
    return token;
  }

  function clearCartToken() {
    localStorage.removeItem(CART_TOKEN_KEY);
  }

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);
    const text = await response.text();
    let parsed;
    try {
      parsed = JSON.parse(text);
    } catch (_error) {
      parsed = text;
    }
    if (!response.ok) {
      const message =
        (parsed && typeof parsed === "object" && parsed.error) ||
        `Request failed with status ${response.status}`;
      throw new Error(message);
    }
    return parsed;
  }

  async function getProducts() {
    return fetchJson("/api/store/products");
  }

  async function getProduct(productId) {
    return fetchJson(`/api/store/products/${encodeURIComponent(productId)}`);
  }

  function cartCount() {
    return readCart().reduce((sum, row) => sum + row.quantity, 0);
  }

  function updateCartCountUI() {
    const count = cartCount();
    document.querySelectorAll("[data-cart-count]").forEach((el) => {
      el.textContent = String(count);
    });
  }

  function addToCart(productId, quantity = 1) {
    const qty = Number(quantity);
    if (!productId || !Number.isFinite(qty) || qty <= 0) return;
    const rows = readCart();
    const existing = rows.find((row) => row.product_id === productId);
    if (existing) {
      existing.quantity += qty;
    } else {
      rows.push({ product_id: productId, quantity: qty });
    }
    writeCart(rows);
    updateCartCountUI();
    queueCartSync();
  }

  function setCartQuantity(productId, quantity) {
    const qty = Number(quantity);
    const rows = readCart();
    const row = rows.find((item) => item.product_id === productId);
    if (!row) return;
    if (!Number.isFinite(qty) || qty <= 0) {
      const nextRows = rows.filter((item) => item.product_id !== productId);
      writeCart(nextRows);
    } else {
      row.quantity = qty;
      writeCart(rows);
    }
    updateCartCountUI();
    queueCartSync();
  }

  function removeFromCart(productId) {
    const rows = readCart().filter((row) => row.product_id !== productId);
    writeCart(rows);
    updateCartCountUI();
    queueCartSync();
  }

  function clearCart(options = {}) {
    writeCart([]);
    updateCartCountUI();
    const skipSync = Boolean(options.skipSync);
    if (!skipSync) {
      queueCartSync();
    }
    clearCartToken();
  }

  function productCardTemplate(product) {
    return `
      <article class="product-card">
        <a href="/product?id=${encodeURIComponent(product.id)}">
          <img src="${product.image}" alt="${product.title}" loading="lazy" />
        </a>
        <div class="content">
          <span class="badge">${product.category}</span>
          <h3 class="title">${product.title}</h3>
          <p class="desc">${product.description}</p>
          <div class="price-wrap">
            <span class="price">${money(product.price)}</span>
            <span class="compare-price">${money(product.compare_at_price)}</span>
          </div>
          <div class="actions">
            <a class="btn btn-outline" href="/product?id=${encodeURIComponent(product.id)}">View</a>
            <button type="button" data-add-to-cart="${product.id}">Add to Cart</button>
          </div>
        </div>
      </article>
    `;
  }

  function bindAddToCartClick(root = document) {
    root.addEventListener("click", (event) => {
      const button = event.target.closest("[data-add-to-cart]");
      if (!button) return;
      const productId = button.getAttribute("data-add-to-cart");
      addToCart(productId, 1);
      const original = button.textContent;
      button.textContent = "Added";
      setTimeout(() => {
        button.textContent = original;
      }, 800);
    });
  }

  function queryParam(name) {
    return new URLSearchParams(window.location.search).get(name);
  }

  async function getDetailedCart() {
    const [products, cartRows] = await Promise.all([getProducts(), Promise.resolve(readCart())]);
    const productMap = new Map(products.map((row) => [row.id, row]));
    return cartRows
      .map((row) => {
        const product = productMap.get(row.product_id);
        if (!product) return null;
        return {
          product,
          quantity: row.quantity,
          line_total: Number(product.price) * Number(row.quantity),
        };
      })
      .filter(Boolean);
  }

  window.Storefront = {
    money,
    fetchJson,
    getProducts,
    getProduct,
    readCart,
    writeCart,
    cartCount,
    updateCartCountUI,
    addToCart,
    setCartQuantity,
    removeFromCart,
    clearCart,
    getOrCreateCartToken,
    clearCartToken,
    syncCartWithOdoo,
    queueCartSync,
    productCardTemplate,
    bindAddToCartClick,
    queryParam,
    getDetailedCart,
  };

  document.addEventListener("DOMContentLoaded", () => {
    updateCartCountUI();
  });
})();
