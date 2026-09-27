import { chromium } from "../web/node_modules/playwright/index.mjs";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { fileURLToPath } from "node:url";
import path from "node:path";
import assert from "node:assert/strict";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const artifacts = path.join(root, "artifacts");
mkdirSync(artifacts, { recursive: true });
const fallback = path.join(
  homedir(),
  "Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell",
);
const executablePath =
  process.env.PLAYWRIGHT_EXECUTABLE_PATH ||
  (existsSync(fallback) ? fallback : undefined);
const base = process.env.SHIFTOPS_URL || "http://127.0.0.1:8197";
const browser = await chromium.launch({ headless: true, executablePath });
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  recordVideo: { dir: artifacts, size: { width: 1440, height: 1000 } },
  acceptDownloads: true,
});
const page = await context.newPage();
const errors = [];
const consoleErrors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (m) => {
  if (m.type() === "error") consoleErrors.push(m.text());
});
let report = { base, started: new Date().toISOString(), checks: [] };
try {
  await page.goto(base);
  await page.locator("#connection.online").waitFor({ timeout: 30000 });
  await page.waitForTimeout(2500);
  assert.equal(await page.locator("#error").isVisible(), false);
  await page.screenshot({
    path: path.join(artifacts, "desktop-ready.png"),
    fullPage: true,
  });
  await page.locator("#new-mission").click();
  await page.locator("#intake").waitFor();
  await page
    .locator("#note")
    .fill(
      "Bearing alarm during the evening shift. Check before maintenance handoff.",
    );
  await page.waitForTimeout(1500);
  await page
    .getByRole("button", { name: "Dispatch inspection", exact: true })
    .click();
  await page.waitForFunction(
    () => document.querySelector("#robot-state")?.textContent === "En route",
    {},
    { timeout: 45000 },
  );
  await page.waitForTimeout(1500);
  await page.locator("#stop").click();
  await page.locator("#resume").waitFor({ timeout: 10000 });
  const paused = await page.evaluate(() =>
    fetch("/api/state").then((r) => r.json()),
  );
  const mission = paused.missions[0];
  assert.equal(mission.status, "paused");
  await page.waitForTimeout(1200);
  const still = await page.evaluate(() =>
    fetch("/api/state").then((r) => r.json()),
  );
  assert.deepEqual(still.missions[0].pose, mission.pose);
  await page.locator("#resume").click();
  await page.locator('[data-decision="approve"]').waitFor({ timeout: 90000 });
  const inspected = await page.evaluate(() =>
    fetch("/api/state").then((r) => r.json()),
  );
  assert.equal(inspected.missions[0].contacts, 0);
  assert(inspected.missions[0].distance > 5);
  assert.equal(inspected.orders.length, 0);
  await page.screenshot({
    path: path.join(artifacts, "desktop-approval.png"),
    fullPage: true,
  });
  await page.waitForTimeout(2500);
  await page.locator('[data-decision="approve"]').click();
  await page.locator(".completion").waitFor({ timeout: 10000 });
  await page.locator('[data-tab="orders"]').click();
  await page.locator(".order").waitFor();
  await page.screenshot({
    path: path.join(artifacts, "work-order.png"),
    fullPage: true,
  });
  await page.waitForTimeout(2000);
  const downloadPromise = page.waitForEvent("download");
  await page.locator(".order .evidence-link").click();
  const download = await downloadPromise;
  await download.saveAs(path.join(artifacts, "browser-evidence.json"));
  await page.locator('[data-tab="activity"]').click();
  await page.locator(".activity details").first().locator("summary").click();
  await page.waitForTimeout(2000);
  await page.screenshot({
    path: path.join(artifacts, "activity.png"),
    fullPage: true,
  });
  await page.locator('[data-tab="operations"]').click();
  await page
    .locator("#replay")
    .evaluate((e) => e.scrollIntoView({ block: "center" }));
  await page.locator("#replay").click();
  await page.locator("#replay-strip").waitFor();
  await page.waitForTimeout(2500);
  await page.screenshot({
    path: path.join(artifacts, "replay.png"),
    fullPage: true,
  });
  assert.equal(
    await page.locator(".live-tag").textContent(),
    "RECORDED REPLAY",
  );
  await page.locator("#close-replay").click();
  await page.reload();
  await page.locator("#connection.online").waitFor();
  assert.equal(await page.locator(".completion").count(), 1);
  const completed = await page.evaluate(() =>
    fetch("/api/state").then((r) => r.json()),
  );
  assert.equal(completed.orders.length, 1);
  assert.equal(completed.inventory["BRG-6204"], 3);
  report.checks.push(
    "live CPU inspection",
    "pause freezes persisted pose",
    "resume reaches inspection",
    "approval required",
    "work order created",
    "single inventory reservation",
    "evidence download",
    "activity events",
    "recorded pose replay",
    "state survives browser reload",
  );
  await page.setViewportSize({ width: 393, height: 852 });
  await page.waitForTimeout(1500);
  await page.screenshot({
    path: path.join(artifacts, "mobile.png"),
    fullPage: true,
  });
  const widths = await page.evaluate(() => ({
    body: document.documentElement.scrollWidth,
    viewport: innerWidth,
  }));
  assert(widths.body <= widths.viewport, JSON.stringify(widths));
  await page.locator("#new-mission").click();
  await page.screenshot({
    path: path.join(artifacts, "mobile-intake.png"),
    fullPage: true,
  });
  await page.locator("#close-intake").click();
  report.checks.push(
    "mobile viewport has no horizontal overflow",
    "mobile intake dialog",
  );
  assert.deepEqual(errors, []);
  assert.deepEqual(consoleErrors, []);
  report.checks.push("no browser errors");
  report.status = "passed";
  report.mission = mission.id;
} catch (e) {
  report.status = "failed";
  report.error = String(e);
  await page.screenshot({
    path: path.join(artifacts, "browser-failure.png"),
    fullPage: true,
  });
  throw e;
} finally {
  report.errors = errors;
  report.consoleErrors = consoleErrors;
  writeFileSync(
    path.join(artifacts, "browser-report.json"),
    JSON.stringify(report, null, 2),
  );
  const video = page.video();
  await context.close();
  if (video) await video.saveAs(path.join(artifacts, "browser-demo.webm"));
  await browser.close();
  console.log(JSON.stringify(report, null, 2));
}
