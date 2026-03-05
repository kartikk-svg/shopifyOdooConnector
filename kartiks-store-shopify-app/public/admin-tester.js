document.addEventListener("DOMContentLoaded", async () => {
  const appNameEl = document.getElementById("app_name");
  const statusEl = document.getElementById("status");
  const targetEl = document.getElementById("target");
  const secretEl = document.getElementById("secret");
  const topicEl = document.getElementById("topic");
  const payloadEl = document.getElementById("payload");
  const sendBtn = document.getElementById("send_btn");
  const responseEl = document.getElementById("response");

  if (!sendBtn || !responseEl) return;

  const setResponse = (data) => {
    responseEl.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
  };

  async function loadConfig() {
    try {
      const data = await Storefront.fetchJson("/api/config");
      if (appNameEl) appNameEl.textContent = data.app_name || "-";
      if (statusEl) statusEl.textContent = data.status || "-";
      if (targetEl) targetEl.textContent = data.webhook_forward_target || "-";
      if (secretEl) secretEl.textContent = data.has_webhook_secret ? "Yes" : "No";

      if (topicEl) {
        topicEl.innerHTML = "";
        (Array.isArray(data.supported_topics) ? data.supported_topics : []).forEach((topic) => {
          const option = document.createElement("option");
          option.value = topic;
          option.textContent = topic;
          topicEl.appendChild(option);
        });
      }
    } catch (error) {
      setResponse({ ok: false, error: `Failed to load config: ${error.message}` });
    }
  }

  sendBtn.addEventListener("click", async () => {
    const topic = String(topicEl?.value || "").trim();
    if (!topic) {
      setResponse({ ok: false, error: "Select a topic first." });
      return;
    }
    sendBtn.disabled = true;
    const body = { topic };
    const custom = String(payloadEl?.value || "").trim();
    if (custom) {
      try {
        body.payload = JSON.parse(custom);
      } catch (error) {
        setResponse({ ok: false, error: `Invalid JSON payload: ${error.message}` });
        sendBtn.disabled = false;
        return;
      }
    }

    setResponse("Sending...");
    try {
      const response = await Storefront.fetchJson("/api/test-webhook", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setResponse(response);
    } catch (error) {
      setResponse({ ok: false, error: error.message });
    } finally {
      sendBtn.disabled = false;
    }
  });

  await loadConfig();
});
