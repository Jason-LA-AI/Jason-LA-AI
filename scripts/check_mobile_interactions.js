"use strict";

const baseUrl = process.argv[2] || "http://127.0.0.1:8765";
const debuggingPort = process.argv[3] || "9226";

async function command(socket, method, params = {}) {
  const id = ++command.nextId;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => {
    const listener = (event) => {
      const message = JSON.parse(event.data);
      if (message.id !== id) return;
      socket.removeEventListener("message", listener);
      if (message.error) reject(new Error(JSON.stringify(message.error)));
      else resolve(message.result);
    };
    socket.addEventListener("message", listener);
  });
}
command.nextId = 0;

async function evaluate(socket, expression) {
  const response = await command(socket, "Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (response.exceptionDetails) {
    throw new Error(response.exceptionDetails.exception?.description || JSON.stringify(response.exceptionDetails));
  }
  return response.result.value;
}

async function navigate(socket, url) {
  await command(socket, "Page.navigate", { url });
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (await evaluate(socket, `location.href === ${JSON.stringify(url)} && document.readyState === 'complete'`)) return;
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  throw new Error(`Timed out loading ${url}`);
}

async function main() {
  const pages = await fetch(`http://127.0.0.1:${debuggingPort}/json/list`).then((response) => response.json());
  const page = pages.find((candidate) => candidate.type === "page");
  if (!page) throw new Error("No Chrome page target is available.");
  const socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  await command(socket, "Page.enable");
  await command(socket, "Runtime.enable");
  await command(socket, "Network.enable");
  await command(socket, "Network.setCacheDisabled", { cacheDisabled: true });
  await command(socket, "Log.enable");
  const consoleErrors = [];
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.method === "Runtime.exceptionThrown") consoleErrors.push(message.params.exceptionDetails.text);
    if (message.method === "Log.entryAdded" && message.params.entry.level === "error") consoleErrors.push(message.params.entry.text);
  });

  await command(socket, "Emulation.setDeviceMetricsOverride", { width: 375, height: 900, deviceScaleFactor: 1, mobile: false });
  await navigate(socket, `${baseUrl}/`);
  const nav = await evaluate(socket, `(async () => {
    const toggle = document.querySelector('.nav-toggle');
    const menu = document.querySelector('#main-menu');
    const visible = (element) => getComputedStyle(element).display !== 'none';
    const result = { initialExpanded: toggle.getAttribute('aria-expanded'), initialOpen: menu.classList.contains('is-open') };
    toggle.click();
    result.clickExpanded = toggle.getAttribute('aria-expanded');
    result.clickOpen = menu.classList.contains('is-open');
    result.moreServices = [...document.querySelectorAll('.menu-secondary a')].map((a) => a.getAttribute('href'));
    result.targetsAtLeast44 = [...menu.querySelectorAll('a')].every((a) => a.getBoundingClientRect().height >= 44);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    result.escapeExpanded = toggle.getAttribute('aria-expanded');
    result.escapeOpen = menu.classList.contains('is-open');
    toggle.click();
    const link = menu.querySelector('a[href="/services"]');
    link.addEventListener('click', (event) => event.preventDefault(), { once: true });
    link.click();
    result.linkClickExpanded = toggle.getAttribute('aria-expanded');
    result.linkClickOpen = menu.classList.contains('is-open');
    result.toggleVisible = visible(toggle);
    return result;
  })()`);

  await command(socket, "Emulation.setDeviceMetricsOverride", { width: 1024, height: 900, deviceScaleFactor: 1, mobile: false });
  await navigate(socket, `${baseUrl}/`);
  const desktop = await evaluate(socket, `(() => ({
    innerWidth,
    toggleDisplay: getComputedStyle(document.querySelector('.nav-toggle')).display,
    menuDisplay: getComputedStyle(document.querySelector('#main-menu')).display,
    visibleLinks: [...document.querySelectorAll('#main-menu a')].filter((a) => a.getBoundingClientRect().width > 0).length
  }))()`);

  const quote = [];
  for (const width of [375, 390, 412, 430]) {
    await command(socket, "Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: false });
    await navigate(socket, `${baseUrl}/quote`);
    quote.push(await evaluate(socket, `(() => {
      const panel = document.querySelector('#estimatePanel');
      panel.hidden = false;
      document.querySelector('#estimateRange').textContent = '$000–$000';
      const error = document.querySelector('[data-error-for="estimateRequest"]');
      error.textContent = 'We could not load an estimate. Please try again.';
      document.querySelector('#estimateErrorContact').hidden = false;
      const selectors = '.choice-grid--airports button, #passengers, #luggage, .next-button, .estimate-card, [data-error-for="estimateRequest"], #estimateErrorContact, .quote-contact-cta';
      const inspected = [...document.querySelectorAll(selectors)];
      const clipped = inspected.filter((element) => {
        const rect = element.getBoundingClientRect();
        return rect.left < -0.5 || rect.right > innerWidth + 0.5 || element.scrollWidth > element.clientWidth + 1;
      }).map((element) => element.id || element.className || element.tagName);
      const text = document.body.innerText;
      return {
        width: ${width},
        innerWidth,
        scrollWidth: document.documentElement.scrollWidth,
        airportOptions: document.querySelectorAll('.choice-grid--airports button').length,
        clipped,
        fareWording: document.querySelector('.estimate-card__label')?.textContent.trim() === 'Estimated Fare Range',
        disclaimer: text.includes('This is a preliminary planning range. Jason will review the exact route, pickup time, luggage, and availability before confirming the final fare.'),
        forbiddenTerms: ['development_mock', 'development-only', 'development only'].filter((term) => text.toLowerCase().includes(term)),
        errorFallbackVisible: document.querySelector('#estimateErrorContact a')?.getBoundingClientRect().width > 0
      };
    })()`));
  }

  const contact = [];
  for (const width of [375, 390, 412, 430]) {
    await command(socket, "Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: false });
    await navigate(socket, `${baseUrl}/contact`);
    contact.push(await evaluate(socket, `(async () => {
      const copyButton = document.querySelector('[data-copy-label="WeChat ID"]');
      if (copyButton) copyButton.click();
      await new Promise((resolve) => setTimeout(resolve, 25));
      return {
      width: ${width},
      innerWidth,
      scrollWidth: document.documentElement.scrollWidth,
      qr: [...document.querySelectorAll('.contact-qr')].map((img) => ({
        alt: img.alt,
        renderedWidth: img.getBoundingClientRect().width,
        containerWidth: img.closest('.contact-channel-card').getBoundingClientRect().width,
        fits: img.getBoundingClientRect().right <= innerWidth + 0.5 && img.scrollWidth <= img.clientWidth + 1
      })),
      telLinks: document.querySelectorAll('a[href^="tel:"]').length,
      smsLinks: document.querySelectorAll('a[href^="sms:"]').length,
      wechatId: Boolean(document.querySelector('[data-copy-label="WeChat ID"]')),
      wechatCopyFeedback: copyButton ? copyButton.textContent.trim() !== 'Copy WeChat ID' : null,
      lineId: Boolean(document.querySelector('[data-copy-label="LINE ID"]')),
      lineUrl: Boolean([...document.querySelectorAll('a')].find((a) => a.textContent.trim() === 'Open LINE'))
      };
    })()`));
  }

  socket.close();
  console.log(JSON.stringify({ nav, desktop, quote, contact, consoleErrors }, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
