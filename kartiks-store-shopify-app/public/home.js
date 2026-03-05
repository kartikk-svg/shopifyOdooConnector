document.addEventListener("DOMContentLoaded", async () => {
  const grid = document.getElementById("featured-grid");
  if (!grid) return;
  try {
    const products = await Storefront.fetchJson("/api/store/products?featured=1");
    grid.innerHTML = products.map(Storefront.productCardTemplate).join("");
    Storefront.bindAddToCartClick(grid);
  } catch (error) {
    grid.innerHTML = `<div class="error-box">${error.message}</div>`;
  }
});
