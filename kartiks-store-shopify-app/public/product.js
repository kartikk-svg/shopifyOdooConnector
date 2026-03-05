document.addEventListener("DOMContentLoaded", async () => {
  const container = document.getElementById("product-detail");
  if (!container) return;

  const productId = Storefront.queryParam("id");
  if (!productId) {
    container.innerHTML = `<div class="error-box">Product ID is missing.</div>`;
    return;
  }

  try {
    const product = await Storefront.getProduct(productId);
    container.innerHTML = `
      <div class="split">
        <div class="card">
          <img src="${product.image}" alt="${product.title}" style="width:100%;max-height:460px;object-fit:cover;border-radius:10px;" />
        </div>
        <div class="card">
          <span class="badge">${product.category}</span>
          <h1 style="margin:10px 0 8px;font-size:30px;">${product.title}</h1>
          <p class="section-muted">${product.description}</p>
          <div class="price-wrap" style="margin:14px 0;">
            <span class="price" style="font-size:22px;">${Storefront.money(product.price)}</span>
            <span class="compare-price">${Storefront.money(product.compare_at_price)}</span>
          </div>
          <label for="qty">Quantity</label>
          <input id="qty" type="number" min="1" step="1" value="1" style="max-width:120px;" />
          <div class="actions">
            <button id="add-to-cart-btn" type="button">Add to Cart</button>
            <a class="btn btn-outline" href="/products">Back to Products</a>
          </div>
          <p class="helper">SKU: ${product.sku}</p>
        </div>
      </div>
    `;

    const qtyInput = document.getElementById("qty");
    const addButton = document.getElementById("add-to-cart-btn");
    addButton?.addEventListener("click", () => {
      const qty = Number(qtyInput?.value || 1);
      Storefront.addToCart(product.id, qty > 0 ? qty : 1);
      addButton.textContent = "Added";
      setTimeout(() => {
        addButton.textContent = "Add to Cart";
      }, 900);
    });
  } catch (error) {
    container.innerHTML = `<div class="error-box">${error.message}</div>`;
  }
});
