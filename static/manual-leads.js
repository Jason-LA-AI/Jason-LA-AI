(() => {
  "use strict";

  const toggle = document.getElementById("toggleLeadForm");
  const form = document.getElementById("manualLeadForm");
  const message = document.getElementById("manualLeadMessage");
  if (!toggle || !form || !message) return;

  toggle.addEventListener("click", () => {
    const opening = form.hidden;
    form.hidden = !opening;
    toggle.setAttribute("aria-expanded", String(opening));
    toggle.textContent = opening ? "Cancel" : "Add lead";
    if (opening) form.elements.customer_name.focus();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const payload = Object.fromEntries(
      [...data.entries()].map(([key, value]) => [key, String(value).trim() || null])
    );
    if (!payload.phone && !payload.wechat && !payload.social_contact) {
      message.textContent = "Provide a phone, WeChat, or social contact.";
      message.className = "form-message error";
      return;
    }

    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    message.textContent = "Saving…";
    message.className = "form-message";
    try {
      const response = await fetch("/dashboard/leads", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error("Unable to save this lead. Check the fields and try again.");
      message.textContent = "Lead saved. Refreshing list…";
      message.className = "form-message success";
      window.location.reload();
    } catch (error) {
      message.textContent = error.message;
      message.className = "form-message error";
      button.disabled = false;
    }
  });

  document.querySelectorAll(".lead-status").forEach((select) => {
    select.dataset.savedValue = select.value;
    select.addEventListener("change", async () => {
      const indicator = select.parentElement.querySelector(".status-save");
      const previous = select.dataset.savedValue;
      select.disabled = true;
      indicator.textContent = "Saving…";
      try {
        const response = await fetch(`/dashboard/leads/${encodeURIComponent(select.dataset.leadId)}/status`, {
          method: "PATCH",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({status: select.value}),
        });
        if (!response.ok) throw new Error("Status update failed.");
        select.dataset.savedValue = select.value;
        indicator.textContent = "Saved";
      } catch (_) {
        select.value = previous;
        indicator.textContent = "Not saved";
      } finally {
        select.disabled = false;
      }
    });
  });
})();
