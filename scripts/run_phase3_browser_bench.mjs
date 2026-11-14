import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const WEB_DIR = path.join(ROOT, "web");
const OUT_DIR = path.join(ROOT, "renders", "phase3");
fs.mkdirSync(OUT_DIR, { recursive: true });

const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PORT = 4173;
const CDP_PORT = 9229;

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function waitForServer(url, timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      // retry
    }
    await sleep(250);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

class CdpClient {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.id = 1;
    this.pending = new Map();
    this.ready = new Promise((resolve, reject) => {
      this.ws.addEventListener("open", resolve);
      this.ws.addEventListener("error", reject);
    });
    this.ws.addEventListener("message", (ev) => {
      const msg = JSON.parse(ev.data.toString());
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) reject(new Error(msg.error.message));
        else resolve(msg.result);
      }
    });
  }

  async send(method, params = {}) {
    await this.ready;
    const id = this.id++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async eval(expression) {
    const res = await this.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (res.exceptionDetails) {
      throw new Error(`Eval error: ${JSON.stringify(res.exceptionDetails)}`);
    }
    return res.result?.value;
  }

  async screenshot(filePath) {
    const { data } = await this.send("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(filePath, Buffer.from(data, "base64"));
  }

  close() {
    this.ws.close();
  }
}

async function main() {
  const preview = spawn("npx", ["vite", "preview", "--port", String(PORT), "--host", "127.0.0.1"], {
    cwd: WEB_DIR,
    shell: true,
    stdio: "ignore",
  });

  const userDataDir = path.join(ROOT, ".tmp_chrome_profile");
  fs.mkdirSync(userDataDir, { recursive: true });

  const chrome = spawn(
    CHROME_PATH,
    [
      "--headless=new",
      `--remote-debugging-port=${CDP_PORT}`,
      `--user-data-dir=${userDataDir}`,
      "--window-size=1280,800",
      "--enable-webgl",
      "--enable-unsafe-webgpu",
      "--ignore-gpu-blocklist",
      "--use-gl=angle",
      "--use-angle=d3d11",
      "about:blank",
    ],
    { stdio: "ignore" }
  );

  try {
    await waitForServer(`http://127.0.0.1:${PORT}/`);
    await waitForServer(`http://127.0.0.1:${CDP_PORT}/json/list`);

    const targets = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`)).json();
    const pageTarget = targets.find((t) => t.type === "page");
    if (!pageTarget) throw new Error("No Chrome page target found");

    const cdp = new CdpClient(pageTarget.webSocketDebuggerUrl);
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");

    // 1. P3.1 Fur Benchmark
    await cdp.send("Page.navigate", { url: `http://127.0.0.1:${PORT}/?view=fur-benchmark` });
    await sleep(2500);
    await cdp.screenshot(path.join(OUT_DIR, "p3_1_fur_shells_fins.png"));

    // Click "Run Automated Benchmark"
    await cdp.eval(`document.querySelector('button.btn-primary').click()`);
    const benchStart = Date.now();
    let benchResults = null;
    while (Date.now() - benchStart < 20000) {
      benchResults = await cdp.eval(`window.__FUR_BENCHMARK_RESULTS__ || null`);
      if (benchResults) break;
      await sleep(500);
    }
    const furHud = await cdp.eval(`document.querySelector('[data-testid="fur-perf-hud"]')?.innerText || ''`);

    // 2. P3.2 Rig Studio
    await cdp.send("Page.navigate", { url: `http://127.0.0.1:${PORT}/?view=rig-studio` });
    await sleep(3000);
    await cdp.screenshot(path.join(OUT_DIR, "p3_2_rig_studio.png"));
    const rigHud = await cdp.eval(`document.querySelector('[data-testid="rig-perf-hud"]')?.innerText || ''`);
    const rigError = await cdp.eval(`document.querySelector('[data-testid="rig-asset-error"]')?.innerText || null`);

    // 3. P3.3 Habitat Day (High Preset)
    await cdp.send("Page.navigate", { url: `http://127.0.0.1:${PORT}/?view=habitat&preset=high&hour=14` });
    await sleep(3500);
    await cdp.screenshot(path.join(OUT_DIR, "p3_3_habitat_high_day.png"));
    const habitatHighDayHud = await cdp.eval(`document.querySelector('[data-testid="habitat-perf-hud"]')?.innerText || ''`);

    // 4. P3.3 Habitat Night (High Preset)
    await cdp.send("Page.navigate", { url: `http://127.0.0.1:${PORT}/?view=habitat&preset=high&hour=23` });
    await sleep(3500);
    await cdp.screenshot(path.join(OUT_DIR, "p3_3_habitat_high_night.png"));
    const habitatHighNightHud = await cdp.eval(`document.querySelector('[data-testid="habitat-perf-hud"]')?.innerText || ''`);

    // 5. P3.3 Habitat Mobile Low Preset
    await cdp.send("Page.navigate", { url: `http://127.0.0.1:${PORT}/?view=habitat&preset=low&hour=14` });
    await sleep(3000);
    await cdp.screenshot(path.join(OUT_DIR, "p3_3_habitat_low_day.png"));
    const habitatLowHud = await cdp.eval(`document.querySelector('[data-testid="habitat-perf-hud"]')?.innerText || ''`);

    console.log(
      JSON.stringify(
        {
          benchResults,
          furHud,
          rigHud,
          rigError,
          habitatHighDayHud,
          habitatHighNightHud,
          habitatLowHud,
        },
        null,
        2
      )
    );

    cdp.close();
  } finally {
    chrome.kill();
    preview.kill();
    await sleep(300);
    try {
      fs.rmSync(userDataDir, { recursive: true, force: true });
    } catch {
      // ignore locked temp file on Windows
    }
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

