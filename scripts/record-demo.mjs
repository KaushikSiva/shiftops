import { chromium } from "../web/node_modules/playwright/index.mjs";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";
import assert from "node:assert/strict";

const base = process.env.SHIFTOPS_URL || "http://127.0.0.1:8197";
const dir = path.resolve("artifacts/live-demo");
mkdirSync(dir, { recursive: true });
const fallback = path.join(
  homedir(),
  "Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell",
);
const browser = await chromium.launch({
  executablePath:
    process.env.PLAYWRIGHT_EXECUTABLE_PATH ||
    (existsSync(fallback) ? fallback : undefined),
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  recordVideo: { dir, size: { width: 1440, height: 1000 } },
});
const page = await context.newPage();
const started = Date.now();
const scenes = [];
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const scene = (title, narration) => {
  scenes.push({ at: (Date.now() - started) / 1000, title, narration });
  console.log(title);
};
const hold = (seconds) => page.waitForTimeout(seconds * 1000);
const state = () =>
  page.evaluate(() => fetch("/api/state").then((r) => r.json()));
const top = () => page.evaluate(() => window.scrollTo(0, 0));
async function dispatch(scenario) {
  await page.locator("#new-mission").click();
  await page.locator(`input[name="scenario"][value="${scenario}"]`).check();
}
async function moving() {
  await page.waitForFunction(
    () => document.querySelector("#robot-state")?.textContent === "En route",
    {},
    { timeout: 60000 },
  );
}
try {
  await page.goto(base);
  await page.locator("#connection.online").waitFor({ timeout: 30000 });
  await hold(5);
  const health = await page.evaluate(() =>
    fetch("/api/health").then((r) => r.json()),
  );
  assert.equal(
    health.deployment,
    "vultr",
    "This recording is for the deployed Vultr app",
  );
  scene(
    "Live on Vultr · ShiftOps facility operations",
    "ShiftOps turns an equipment alert into accountable maintenance work. This is the live application on a Vultr CPU virtual machine.",
  );
  await hold(10);
  await dispatch("overheat");
  scene(
    "Dispatch an air-handler inspection",
    "Start with an overheating air handler and a blocked aisle.",
  );
  await page
    .locator("#note")
    .fill(
      "Bearing alarm on the evening shift. Inspect before the maintenance handoff.",
    );
  await hold(6);
  await page
    .getByRole("button", { name: "Dispatch inspection", exact: true })
    .click();
  await moving();
  scene(
    "Live MuJoCo physics · existing learned G1 gait",
    "The backend plans a route and drives our existing G1 gait in real CPU physics.",
  );
  await hold(5);
  await page.locator("#stop").click();
  await page.locator("#resume").waitFor();
  scene(
    "Pause retains the robot and controller checkpoint",
    "Pause saves the robot and controller checkpoint.",
  );
  await hold(5);
  await page.locator("#resume").click();
  scene(
    "Resume from durable state",
    "Resuming continues from that saved state. Every recorded pose lives on the Vultr virtual machine.",
  );
  await hold(8);
  await page.locator('[data-decision="approve"]').waitFor({ timeout: 120000 });
  const inspected = (await state()).missions[0];
  assert.equal(inspected.contacts, 0);
  scene(
    "Review evidence and the proposed parts reservation",
    "At the inspection point, simulated equipment readings trigger an inventory check and a proposed maintenance handoff.",
  );
  await top();
  await hold(9);
  await page.screenshot({
    path: path.join(dir, "approval.png"),
    fullPage: true,
  });
  await page.locator('[data-decision="approve"]').click();
  await page.locator(".completion").waitFor();
  await page.locator('[data-tab="orders"]').click();
  await page.locator(".order").waitFor();
  await top();
  scene(
    "Approval commits the handoff · repair remains pending",
    "Only your approval creates a work order and reserves a part. The repair remains pending.",
  );
  await hold(9);
  await page.locator('[data-tab="activity"]').click();
  await page.locator(".activity details").first().locator("summary").click();
  await top();
  scene(
    "Durable decisions and downloadable evidence",
    "Every decision has a durable audit record, with downloadable evidence.",
  );
  await hold(7);
  await page.locator('[data-tab="operations"]').click();
  await page
    .locator("#replay")
    .evaluate((e) => e.scrollIntoView({ block: "center" }));
  await page.locator("#replay").click();
  await page.locator("#replay-strip").waitFor();
  await top();
  scene(
    "Replay actual recorded robot poses",
    "Replay shows the actual robot poses recorded during the inspection.",
  );
  await hold(8);
  await page.locator("#close-replay").click();
  await dispatch("stockout");
  scene(
    "An exception: the replacement filter is out of stock",
    "The same workflow handles exceptions. A filter replacement needs a part that is out of stock.",
  );
  await hold(6);
  await page
    .getByRole("button", { name: "Dispatch inspection", exact: true })
    .click();
  await moving();
  await page.locator('[data-decision="approve"]').waitFor({ timeout: 120000 });
  scene(
    "Stockout becomes a purchase request",
    "With no stock, the proposal becomes a purchase request.",
  );
  await top();
  await hold(7);
  await page.locator('[data-decision="approve"]').click();
  await page.locator(".completion").waitFor();
  await page.locator('[data-tab="orders"]').click();
  await page
    .locator(".order")
    .filter({ hasText: "Purchase request pending" })
    .waitFor();
  await top();
  scene(
    "Purchasing review queued · no external order sent",
    "Approval queues purchasing review. No external order is sent.",
  );
  await hold(7);
  const final = await state();
  assert.equal(final.orders.length, 2);
  assert.equal(final.inventory["BRG-6204"], 3);
  assert.equal(final.inventory["FLT-H13"], 0);
  await page.locator('[data-tab="about"]').click();
  await top();
  scene(
    "Vultr runs the app, workflow, physics and records",
    "Vultr runs the web app, API, workflow, CPU simulation, and SQLite system of record. Existing robot assets are clearly disclosed.",
  );
  await hold(12);
  assert.deepEqual(errors, []);
  writeFileSync(
    path.join(dir, "timeline.json"),
    JSON.stringify(
      {
        base,
        recorded_at: new Date().toISOString(),
        scenes,
        end: (Date.now() - started) / 1000,
        missions: final.missions.map((m) => m.id),
        orders: final.orders.map((o) => o.id),
        status: "passed",
        errors,
      },
      null,
      2,
    ),
  );
} finally {
  const video = page.video();
  await context.close();
  if (video) await video.saveAs(path.join(dir, "public-demo.webm"));
  await browser.close();
}
