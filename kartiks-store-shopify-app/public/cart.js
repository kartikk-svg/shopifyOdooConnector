document.addEventListener("DOMContentLoaded", async () => {
  const listEl = document.getElementById("cart-list");
  const subtotalEl = document.getElementById("subtotal");
  const shippingEl = document.getElementById("shipping");
  const totalEl = document.getElementById("total");
  const checkoutBtn = document.getElementById("checkout-btn");
  if (!listEl) return;
  Storefront.getOrCreateCartToken();

  async function render() {
    const rows = await Storefront.getDetailedCart();
    if (!rows.length) {
      listEl.innerHTML = `
        <div class="card">
          <h3>Your cart is empty</h3>
          <p class="muted">Browse products and add items to continue.</p>
          <a class="btn" href="/products">Shop Now</a>
        </div>
      `;
      subtotalEl.textContent = Storefront.money(0);
      shippingEl.textContent = Storefront.money(0);
      totalEl.textContent = Storefront.money(0);
      if (checkoutBtn) checkoutBtn.style.display = "none";
      return;
    }

    let subtotal = 0;
    listEl.innerHTML = rows
      .map((row) => {
        subtotal += row.line_total;
        return `
          <article class="cart-item">
            <img src="${row.product.image}" alt="${row.product.title}" />
            <div>
              <h4 style="margin:0 0 4px;">${row.product.title}</h4>
              <p class="muted" style="margin:0 0 8px;">${Storefront.money(row.product.price)} x ${row.quantity}</p>
              <div style="display:flex; gap:8px; max-width:260px;">
                <input type="number" min="1" step="1" value="${row.quantity}" data-qty-id="${row.product.id}" />
                <button type="button" class="btn btn-outline" data-remove-id="${row.product.id}">Remove</button>
              </div>
            </div>
            <strong>${Storefront.money(row.line_total)}</strong>
          </article>
        `;
      })
      .join("");

    const shipping = subtotal >= 500 ? 0 : 25;
    const total = subtotal + shipping;
    subtotalEl.textContent = Storefront.money(subtotal);
    shippingEl.textContent = Storefront.money(shipping);
    totalEl.textContent = Storefront.money(total);
    if (checkoutBtn) checkoutBtn.style.display = "inline-block";
  }

  listEl.addEventListener("change", (event) => {
    const input = event.target.closest("[data-qty-id]");
    if (!input) return;
    const productId = input.getAttribute("data-qty-id");
    const parsed = Number(input.value || 1);
    const qty = Number.isFinite(parsed) ? Math.max(1, Math.min(99, Math.floor(parsed))) : 1;
    input.value = String(qty);
    Storefront.setCartQuantity(productId, qty);
    render();
  });

  listEl.addEventListener("click", (event) => {
    const button = event.target.closest("[data-remove-id]");
    if (!button) return;
    const productId = button.getAttribute("data-remove-id");
    Storefront.removeFromCart(productId);
    render();
  });

  await render();
});
