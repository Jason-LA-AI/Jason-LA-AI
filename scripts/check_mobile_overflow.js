"use strict";

const widths = [375, 390, 412, 430];
const paths = [
  "/",
  "/services",
  "/ont-airport-transportation",
  "/student-airport-pickup",
  "/private-car-service",
  "/stories",
  "/vehicle",
  "/quote",
  "/contact",
];
const baseUrl = process.argv[2] || "http://127.0.0.1:8765";
const debuggingPort = process.argv[3] || "9223";

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

async function waitForLoad(socket) {
  return new Promise((resolve) => {
    const timeout = setTimeout(resolve, 5000);
    const listener = (event) => {
      const message = JSON.parse(event.data);
      if (message.method !== "Page.loadEventFired") return;
      clearTimeout(timeout);
      socket.removeEventListener("message", listener);
      resolve();
    };
    socket.addEventListener("message", listener);
  });
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

  const results = [];
  for (const width of widths) {
    await command(socket, "Emulation.setDeviceMetricsOverride", {
      width,
      height: 900,
      deviceScaleFactor: 1,
      mobile: false,
    });
    for (const path of paths) {
      const loaded = waitForLoad(socket);
      await command(socket, "Page.navigate", { url: `${baseUrl}${path}` });
      await loaded;
      const measurement = await command(socket, "Runtime.evaluate", {
        expression: `(() => ({
          innerWidth: window.innerWidth,
          scrollWidth: document.documentElement.scrollWidth,
          bodyScrollWidth: document.body.scrollWidth,
          overflowingElements: [...document.querySelectorAll("body *")]
            .filter((element) => {
              const rect = element.getBoundingClientRect();
              return rect.right > window.innerWidth + 0.5 || rect.left < -0.5;
            })
            .slice(0, 8)
            .map((element) => ({ tag: element.tagName, className: String(element.className || ""), text: (element.textContent || "").trim().slice(0, 50), rect: element.getBoundingClientRect().toJSON() })),
          clippedElements: [...document.querySelectorAll("body *")]
            .filter((element) => element.scrollWidth > element.clientWidth + 1)
            .slice(0, 8)
            .map((element) => ({ tag: element.tagName, className: String(element.className || ""), text: (element.textContent || "").trim().slice(0, 50), clientWidth: element.clientWidth, scrollWidth: element.scrollWidth }))
        }))()`,
        returnByValue: true,
      });
      const value = measurement.result.value;
      results.push({ width, path, ...value, overflow: value.scrollWidth > value.innerWidth });
    }
  }
  socket.close();
  console.log(JSON.stringify(results, null, 2));
  if (results.some((result) => result.overflow)) process.exitCode = 1;
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 2;
});
