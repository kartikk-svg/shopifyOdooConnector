document.addEventListener("DOMContentLoaded", () => {
  const orderNameEl = document.getElementById("order-name");
  const totalEl = document.getElementById("order-total");
  if (!orderNameEl || !totalEl) return;
  const orderName = Storefront.queryParam("order_name") || "N/A";
  const total = Storefront.queryParam("total") || "0.00";
  orderNameEl.textContent = orderName;
  totalEl.textContent = Storefront.money(total);
  Storefront.updateCartCountUI();
});
