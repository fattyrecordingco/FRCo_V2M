import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import process from "node:process";
import { chromium } from "playwright";

const HOST = "127.0.0.1";
const PORT = 4173;
const URL = `http://${HOST}:${PORT}`;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForServer(url, attempts = 80) {
  for (let i = 0; i < attempts; i += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // Ignore while waiting for preview server startup.
    }
    await sleep(500);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

function intersects(a, b) {
  return !(a.x + a.width <= b.x || b.x + b.width <= a.x || a.y + a.height <= b.y || b.y + b.height <= a.y);
}

async function assertVisibleInViewport(page, selector, viewport, label) {
  const box = await page.locator(selector).boundingBox();
  if (!box) throw new Error(`${label} not found: ${selector}`);
  if (box.x < 0 || box.y < 0 || box.x + box.width > viewport.width || box.y + box.height > viewport.height) {
    throw new Error(`${label} clipped at ${viewport.width}x${viewport.height}`);
  }
}

async function runViewportChecks(page, viewport) {
  await page.setViewportSize(viewport);
  await page.goto(URL, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("[data-testid='step-prep']");

  await assertVisibleInViewport(page, "[data-testid='generate-btn']", viewport, "generate button");
  await assertVisibleInViewport(page, "[data-testid='session-select']", viewport, "session select");
  await assertVisibleInViewport(page, "[data-testid='step-input']", viewport, "step 1 panel");

  const hasActionDock = (await page.locator(".action-dock").count()) > 0;
  if (hasActionDock) throw new Error("Removed bottom action dock is still present.");

  const step2 = await page.locator("[data-testid='step-prep']").boundingBox();
  const step3 = await page.locator("[data-testid='step-preview']").boundingBox();
  if (!step2 || !step3) throw new Error("Step 2/3 cards missing.");
  if (intersects(step2, step3)) {
    throw new Error(`Step 2 and Step 3 overlap at ${viewport.width}x${viewport.height}`);
  }

  const piano = await page.locator("[data-testid='piano-picker']").boundingBox();
  if (!piano || piano.width < 100 || piano.height < 50) {
    throw new Error(`Piano picker failed to render at ${viewport.width}x${viewport.height}`);
  }
  const pianoRatio = await page.$eval("[data-testid='piano-picker']", (element) => {
    const styles = getComputedStyle(element);
    const width = Number.parseFloat(styles.width);
    const height = Number.parseFloat(styles.height);
    return width / Math.max(height, 1);
  });
  if (pianoRatio > 5.3 || pianoRatio < 3.0) {
    throw new Error(`Piano proportions regressed at ${viewport.width}x${viewport.height} (${pianoRatio.toFixed(2)})`);
  }
  if (step2 && piano.y + piano.height > step2.y + step2.height + 10) {
    const overflow = Math.round(piano.y + piano.height - (step2.y + step2.height));
    throw new Error(`Prep panel clipped piano at ${viewport.width}x${viewport.height} (overflow ${overflow}px)`);
  }

  await page.locator("[data-testid='step-prep'] select").nth(1).selectOption("custom");
  const customPiano = await page.locator("[data-testid='piano-picker']").boundingBox();
  if (!customPiano || customPiano.width < 100 || customPiano.height < 50) {
    throw new Error(`Custom piano picker failed to render at ${viewport.width}x${viewport.height}`);
  }

  const midiHeader = await page.locator("[data-testid='output-panel'] .file-section-title", { hasText: "MIDI Tracks" }).count();
  const audioHeader = await page.locator("[data-testid='output-panel'] .file-section-title", { hasText: "Audio Tracks" }).count();
  if (!midiHeader || !audioHeader) {
    throw new Error(`Output track sections missing at ${viewport.width}x${viewport.height}`);
  }

  const waveformShell = await page.locator(".waveform-shell").count()
    ? await page.locator(".waveform-shell").boundingBox()
    : await page.locator(".dropzone").boundingBox();
  const inputPanel = await page.locator("[data-testid='step-input']").boundingBox();
  if (!waveformShell || !inputPanel) throw new Error("Input panel or waveform missing.");
  if (waveformShell.x + waveformShell.width > inputPanel.x + inputPanel.width + 2) {
    throw new Error(`Waveform overflowed input panel at ${viewport.width}x${viewport.height}`);
  }

  const titleRowsHaveExtras = await page.evaluate(() =>
    Array.from(document.querySelectorAll(".step-title-row")).some((row) =>
      Array.from(row.children).some((child) => child.tagName !== "H2")
    )
  );
  if (titleRowsHaveExtras) {
    throw new Error(`Status badge content still visible in title rows at ${viewport.width}x${viewport.height}`);
  }

  const midiChart = await page.locator(".midi-mini-chart").count()
    ? await page.locator(".midi-mini-chart").boundingBox()
    : null;
  const trackGrid = await page.locator(".track-grid").count()
    ? await page.locator(".track-grid").boundingBox()
    : null;
  if (midiChart && trackGrid && intersects(midiChart, trackGrid)) {
    throw new Error(`Preview chart overlaps track controls at ${viewport.width}x${viewport.height}`);
  }

  const panelHasInternalScroll = await page.evaluate(() => {
    const panels = Array.from(document.querySelectorAll(".step-input, .step-prep, .step-preview"));
    return panels.some((panel) => panel.scrollHeight > panel.clientHeight + 2);
  });
  if (panelHasInternalScroll) {
    throw new Error(`Internal panel scroll detected at ${viewport.width}x${viewport.height}`);
  }

}

async function main() {
  if (!existsSync("dist/index.html")) {
    throw new Error("dist output missing. Run `npm run build` before `npm run layout:smoke`.");
  }

  const previewCmd = `npm run preview -- --host ${HOST} --port ${PORT} --strictPort`;
  const server =
    process.platform === "win32"
      ? spawn("cmd.exe", ["/d", "/s", "/c", previewCmd], { cwd: process.cwd(), stdio: "ignore", shell: false })
      : spawn("sh", ["-c", previewCmd], { cwd: process.cwd(), stdio: "ignore", shell: false });

  let browser;
  try {
    await waitForServer(URL);

    try {
      browser = await chromium.launch({ headless: true, channel: "msedge" });
    } catch {
      browser = await chromium.launch({ headless: true });
    }

    const page = await browser.newPage();
    await runViewportChecks(page, { width: 1024, height: 768 });
    await runViewportChecks(page, { width: 1152, height: 720 });
    await runViewportChecks(page, { width: 1280, height: 720 });
    await runViewportChecks(page, { width: 1220, height: 680 });
    await runViewportChecks(page, { width: 1366, height: 768 });
    await runViewportChecks(page, { width: 1400, height: 700 });
    await runViewportChecks(page, { width: 1600, height: 900 });
    await runViewportChecks(page, { width: 1664, height: 936 });
    await runViewportChecks(page, { width: 1820, height: 860 });
    await runViewportChecks(page, { width: 1920, height: 1080 });

    console.log("layout smoke passed");
  } finally {
    if (browser) await browser.close();
    if (!server.killed) {
      server.kill("SIGTERM");
      await sleep(300);
      if (!server.killed) server.kill("SIGKILL");
    }
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
