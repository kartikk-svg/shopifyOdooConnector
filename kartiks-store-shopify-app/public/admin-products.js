document.addEventListener("DOMContentLoaded", async () => {
  const listEl = document.getElementById("admin-products-list");
  const searchEl = document.getElementById("search-products-admin");
  const formEl = document.getElementById("product-form");
  const resetBtn = document.getElementById("reset-btn");
  const saveBtn = document.getElementById("save-btn");
  const statusEl = document.getElementById("admin-status");
  const idEl = document.getElementById("product_id");
  const titleEl = document.getElementById("title");
  const descriptionEl = document.getElementById("description");
  const categoryEl = document.getElementById("category");
  const skuEl = document.getElementById("sku");
  const priceEl = document.getElementById("price");
  const compareEl = document.getElementById("compare_at_price");
  const imageEl = document.getElementById("image");
  const featuredEl = document.getElementById("featured");

  if (!listEl || !formEl || !statusEl) return;

  let products = [];
  let filtered = [];
  let mode = "create";

  const setStatus = (message, isError = false) => {
    statusEl.textContent = message;
    statusEl.classList.toggle("error", Boolean(isError));
  };

  const clearForm = () => {
    mode = "create";
    formEl.reset();
    if (idEl) idEl.value = "";
    if (saveBtn) saveBtn.textContent = "Create Product";
  };

  const toPrice = (value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed.toFixed(2) : "0.00";
  };

  const applySearch = () => {
    const keyword = String(searchEl?.value || "").trim().toLowerCase();
    if (!keyword) {
      filtered = [...products];
      return;
    }
    filtered = products.filter((product) => {
      return (
        String(product.title || "").toLowerCase().includes(keyword) ||
        String(product.category || "").toLowerCase().includes(keyword) ||
        String(product.sku || "").toLowerCase().includes(keyword)
      );
    });
  };

  const rowTemplate = (product) => {
    return `
      <article class="admin-product-row">
        <img src="${product.image}" alt="${product.title}" loading="lazy" />
        <div>
          <strong>${product.title}</strong>
          <div class="helper">${product.category} • SKU ${product.sku}</div>
          <div class="helper">Price ₹${toPrice(product.price)} • Compare ₹${toPrice(product.compare_at_price)}</div>
        </div>
        <div class="admin-actions">
          <button type="button" class="btn btn-outline" data-edit-id="${product.id}">Edit</button>
          <button type="button" data-delete-id="${product.id}" style="background:#dc2626;">Delete</button>
        </div>
      </article>
    `;
  };

  const render = () => {
    applySearch();
    if (!filtered.length) {
      listEl.innerHTML = `<div class="error-box">No products found.</div>`;
      return;
    }
    listEl.innerHTML = filtered.map(rowTemplate).join("");
  };

  const loadProducts = async () => {
    products = await Storefront.getProducts();
    render();
  };

  const fillFormForEdit = (productId) => {
    const product = products.find((row) => row.id === productId);
    if (!product) {
      setStatus("Product not found for edit.", true);
      return;
    }
    mode = "update";
    if (idEl) idEl.value = product.id;
    if (titleEl) titleEl.value = product.title || "";
    if (descriptionEl) descriptionEl.value = product.description || "";
    if (categoryEl) categoryEl.value = product.category || "";
    if (skuEl) skuEl.value = product.sku || "";
    if (priceEl) priceEl.value = Number(product.price || 0);
    if (compareEl) compareEl.value = Number(product.compare_at_price || 0);
    if (imageEl) imageEl.value = product.image || "";
    if (featuredEl) featuredEl.checked = Boolean(product.featured);
    if (saveBtn) saveBtn.textContent = "Update Product";
    setStatus(`Editing product ${product.title}`);
  };

  const collectFormPayload = () => {
    return {
      title: String(titleEl?.value || "").trim(),
      description: String(descriptionEl?.value || "").trim(),
      category: String(categoryEl?.value || "").trim(),
      sku: String(skuEl?.value || "").trim(),
      price: Number(priceEl?.value || 0),
      compare_at_price: Number(compareEl?.value || 0),
      image: String(imageEl?.value || "").trim(),
      featured: Boolean(featuredEl?.checked),
    };
  };

  listEl.addEventListener("click", async (event) => {
    const editBtn = event.target.closest("[data-edit-id]");
    if (editBtn) {
      const productId = editBtn.getAttribute("data-edit-id");
      fillFormForEdit(productId);
      return;
    }

    const deleteBtn = event.target.closest("[data-delete-id]");
    if (!deleteBtn) return;
    const productId = deleteBtn.getAttribute("data-delete-id");
    const product = products.find((row) => row.id === productId);
    if (!product) {
      setStatus("Product not found for delete.", true);
      return;
    }
    const confirmed = window.confirm(`Delete product "${product.title}"?`);
    if (!confirmed) return;

    deleteBtn.disabled = true;
    try {
      const response = await Storefront.fetchJson(`/api/store/products/${encodeURIComponent(productId)}`, {
        method: "DELETE",
      });
      await loadProducts();
      clearForm();
      const webhookStatus = response?.webhook?.odoo_status ? `, webhook ${response.webhook.odoo_status}` : "";
      setStatus(`Deleted ${product.title}${webhookStatus}.`);
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      deleteBtn.disabled = false;
    }
  });

  formEl.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = collectFormPayload();
    if (!payload.title || !payload.sku || !Number.isFinite(payload.price) || payload.price <= 0) {
      setStatus("Title, SKU, and valid price are required.", true);
      return;
    }
    if (!Number.isFinite(payload.compare_at_price) || payload.compare_at_price < 0) {
      setStatus("Compare price must be 0 or greater.", true);
      return;
    }

    if (saveBtn) saveBtn.disabled = true;
    try {
      if (mode === "update" && idEl?.value) {
        const response = await Storefront.fetchJson(`/api/store/products/${encodeURIComponent(idEl.value)}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        await loadProducts();
        clearForm();
        const webhookStatus = response?.webhook?.odoo_status ? `, webhook ${response.webhook.odoo_status}` : "";
        setStatus(`Updated ${response.product?.title || "product"}${webhookStatus}.`);
      } else {
        const response = await Storefront.fetchJson("/api/store/products", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        await loadProducts();
        clearForm();
        const webhookStatus = response?.webhook?.odoo_status ? `, webhook ${response.webhook.odoo_status}` : "";
        setStatus(`Created ${response.product?.title || "product"}${webhookStatus}.`);
      }
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      if (saveBtn) saveBtn.disabled = false;
    }
  });

  resetBtn?.addEventListener("click", () => {
    clearForm();
    setStatus("Form reset.");
  });

  searchEl?.addEventListener("input", () => {
    render();
  });

  try {
    clearForm();
    await loadProducts();
    setStatus("Products loaded.");
  } catch (error) {
    setStatus(`Failed to load products: ${error.message}`, true);
  }
});
