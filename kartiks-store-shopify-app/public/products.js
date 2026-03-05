document.addEventListener("DOMContentLoaded", async () => {
  const grid = document.getElementById("products-grid");
  const searchInput = document.getElementById("search-products");
  if (!grid) return;

  let products = [];
  let addToCartBound = false;

  function render(rows) {
    if (!rows.length) {
      grid.innerHTML = `<div class="error-box">No products found for this search.</div>`;
      return;
    }
    grid.innerHTML = rows.map(Storefront.productCardTemplate).join("");
    if (!addToCartBound) {
      Storefront.bindAddToCartClick(grid);
      addToCartBound = true;
    }
  }

  try {
    products = await Storefront.getProducts();
    render(products);
  } catch (error) {
    grid.innerHTML = `<div class="error-box">${error.message}</div>`;
  }

  if (searchInput) {
    searchInput.addEventListener("input", () => {
      const keyword = searchInput.value.trim().toLowerCase();
      if (!keyword) {
        render(products);
        return;
      }
      const filtered = products.filter((row) => {
        return (
          row.title.toLowerCase().includes(keyword) ||
          row.category.toLowerCase().includes(keyword) ||
          row.sku.toLowerCase().includes(keyword)
        );
      });
      render(filtered);
    });
  }
});
