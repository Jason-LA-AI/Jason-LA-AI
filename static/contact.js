(() => {
  "use strict";

  document.querySelectorAll("[data-copy-value]").forEach((button) => {
    button.addEventListener("click", async () => {
      const originalText = button.textContent;
      try {
        await navigator.clipboard.writeText(button.dataset.copyValue);
        button.textContent = `${button.dataset.copyLabel} copied`;
      } catch (_) {
        button.textContent = "Copy failed — select the ID above";
      }
      window.setTimeout(() => { button.textContent = originalText; }, 2500);
    });
  });
})();
