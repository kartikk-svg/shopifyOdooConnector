document.addEventListener("DOMContentLoaded", async () => {
  const summaryEl = document.getElementById("checkout-summary");
  const formEl = document.getElementById("checkout-form");
  const errorEl = document.getElementById("checkout-error");
  if (!summaryEl || !formEl) return;

  const rows = await Storefront.getDetailedCart();
  if (!rows.length) {
    summaryEl.innerHTML = `
      <div class="error-box">
        Cart is empty. <a href="/products">Go to products</a>
      </div>
    `;
    formEl.style.display = "none";
    return;
  }

  let subtotal = 0;
  rows.forEach((row) => {
    subtotal += row.line_total;
  });
  const shipping = subtotal >= 500 ? 0 : 25;
  const total = subtotal + shipping;

  summaryEl.innerHTML = `
    <div class="summary-row"><span>Subtotal</span><strong>${Storefront.money(subtotal)}</strong></div>
    <div class="summary-row"><span>Shipping</span><strong>${Storefront.money(shipping)}</strong></div>
    <div class="summary-row total"><span>Total</span><strong>${Storefront.money(total)}</strong></div>
    <p class="helper">Your order will be pushed to Odoo through the webhook pipeline.</p>
  `;

  function setError(message) {
    if (!errorEl) return;
    errorEl.style.display = "block";
    errorEl.textContent = message;
  }

  function clearError() {
    if (!errorEl) return;
    errorEl.style.display = "none";
    errorEl.textContent = "";
  }

  function validateCustomer(customer) {
    if (!customer.first_name || customer.first_name.length < 2) {
      return "First name must be at least 2 characters.";
    }
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailPattern.test(customer.email)) {
      return "Please enter a valid email address.";
    }
    const phone = customer.phone.replace(/\s+/g, "");
    if (phone && !/^[0-9]{10,15}$/.test(phone)) {
      return "Phone must be 10 to 15 digits.";
    }
    if (!customer.address1 || customer.address1.length < 4) {
      return "Please enter a valid address.";
    }
    if (!customer.city || customer.city.length < 2) {
      return "Please enter a valid city.";
    }
    if (!/^[0-9A-Za-z-]{4,10}$/.test(customer.zip || "")) {
      return "Please enter a valid ZIP code.";
    }
    return "";
  }

  formEl.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearError();
    const submitBtn = formEl.querySelector("button[type='submit']");
    if (submitBtn) submitBtn.disabled = true;

    const formData = new FormData(formEl);
    const customer = {
      first_name: String(formData.get("first_name") || "").trim(),
      last_name: String(formData.get("last_name") || "").trim(),
      email: String(formData.get("email") || "").trim(),
      phone: String(formData.get("phone") || "").trim(),
      address1: String(formData.get("address1") || "").trim(),
      city: String(formData.get("city") || "").trim(),
      zip: String(formData.get("zip") || "").trim(),
    };
    const validationError = validateCustomer(customer);
    if (validationError) {
      setError(validationError);
      if (submitBtn) submitBtn.disabled = false;
      return;
    }

    const cartToken = Storefront.getOrCreateCartToken();
    const payload = {
      customer,
      cart_token: cartToken,
      checkout_token: cartToken,
      cart: rows.map((row) => ({
        product_id: row.product.id,
        quantity: row.quantity,
      })),
    };

    try {
      await Storefront.syncCartWithOdoo({
        email: customer.email,
        cart_token: cartToken,
        checkout_token: cartToken,
      });
      const response = await Storefront.fetchJson("/api/store/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      Storefront.clearCart({ skipSync: true });
      const params = new URLSearchParams({
        order_name: response.order_name || "",
        total: response.total || "0.00",
      });
      window.location.href = `/order-success?${params.toString()}`;
    } catch (error) {
      setError(error.message);
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  });
});
