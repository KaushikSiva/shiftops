import "./style.css";
import { FacilityTwin } from "./twin";
import {
  createIcons,
  Zap,
  ChevronsUpDown,
  ScanLine,
  ClipboardList,
  ListFilter,
  Layers,
  ShieldCheck,
  CircleHelp,
  Plus,
  Database,
  Workflow,
  Maximize,
  Focus,
  Bot,
  Pause,
  Route,
  ArrowRight,
  Check,
  ScanEye,
  CircleCheck,
  Play,
  Download,
  ArrowUpRight,
  Monitor,
  Server,
  X,
  FlaskConical,
  Droplets,
  Wind,
  Thermometer,
} from "lucide";
const icons = {
  Zap,
  ChevronsUpDown,
  ScanLine,
  ClipboardList,
  ListFilter,
  Layers,
  ShieldCheck,
  CircleHelp,
  Plus,
  Database,
  Workflow,
  Maximize,
  Focus,
  Bot,
  Pause,
  Route,
  ArrowRight,
  Check,
  ScanEye,
  CircleCheck,
  Play,
  Download,
  ArrowUpRight,
  Monitor,
  Server,
  X,
  FlaskConical,
  Droplets,
  Wind,
  Thermometer,
};

const el = document.querySelector<HTMLDivElement>("#app")!;
const icon = (name: string) => `<i data-lucide="${name}"></i>`;
const esc = (s: any) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ]!,
  );
const time = (t: number) =>
  new Date(t * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
let replayFrames: any[] = [],
  replayIndex = 0,
  replayPlaying = false;
let alternateKey = "",
  renderKey = "";
let data: any = { missions: [], orders: [], inventory: {} },
  facility: any,
  selected = "",
  tab = "operations",
  twin: FacilityTwin,
  pending = false,
  stream: EventSource;
const statusNames: Record<string, string> = {
  planning: "Planning route",
  navigating: "En route",
  inspecting: "Inspecting",
  awaiting_approval: "Needs approval",
  paused: "Paused",
  complete: "Handoff complete",
  rejected: "Rejected",
  canceled: "Canceled",
  escalated: "Needs intervention",
};

el.innerHTML = `<aside class="sidebar"><a class="brand" href="/" aria-label="ShiftOps home"><span class="brandmark">${icon("zap")}</span>ShiftOps<span class="brand-dot">®</span></a><div class="workspace"><span class="facility-mark">HW</span><div>Harbor Works<small>Facility operations</small></div>${icon("chevrons-up-down")}</div><p class="nav-label">WORKSPACE</p><nav><button class="nav-button active" data-tab="operations">${icon("scan-line")}Operations<span class="nav-dot"></span></button><button class="nav-button" data-tab="orders">${icon("clipboard-list")}Work orders<span id="order-count">0</span></button><button class="nav-button" data-tab="activity">${icon("list-filter")}Activity log</button><button class="nav-button" data-tab="about">${icon("layers")}System overview</button></nav><div class="sidebar-bottom"><div class="mode-label"><span></span>SIMULATION WORKSPACE</div><p>Live robot physics.<br>Isolated demo operations.</p><div class="operator"><span>KS</span><div>Operations lead<small>Demo operator</small></div>${icon("shield-check")}</div></div></aside>
<main><header class="topbar"><div><span class="breadcrumb">Harbor Works</span><span class="slash">/</span><span id="page-title">Operations</span></div><div class="topbar-right"><span id="connection" class="connection">Connecting</span><button class="icon-button" id="help" aria-label="System overview">${icon("circle-help")}</button></div></header>
<div class="page-heading"><div><p class="eyebrow">FACILITY CONTROL</p><h1 id="heading">Facility operations</h1><p id="subheading">Manage inspections, approvals and maintenance handoffs.</p></div><button class="primary" id="new-mission">${icon("plus")}New inspection</button></div>
<div id="error" role="alert" hidden></div>
<section id="operations"><div class="metrics"><div><span>Robot availability</span><strong id="robot-stat">1 <small>/ 1 G1</small></strong></div><div><span>Active inspections</span><strong id="active-stat">0</strong></div><div><span>Awaiting approval</span><strong id="approval-stat">0</strong></div><div><span>Work orders created</span><strong id="completed-stat">0</strong></div><div class="metric-note">${icon("database")}Persistent operations<br><b id="deployment">Connecting to backend</b></div></div>
<div class="operations-grid"><section class="twin-panel"><div class="panel-heading"><div><h2>Facility twin</h2><span>Ground floor · 130 m²</span></div><span class="live-tag"><span></span>LIVE PHYSICS</span></div><div class="canvas-wrap"><div id="twin"></div><div class="twin-corner"><span class="map-tag">HARBOR WORKS / FLOOR 01</span><span class="map-sub">MuJoCo · CPU simulation</span></div><div class="map-controls"><button id="reset-view" class="icon-button" aria-label="Reset camera">${icon("maximize")}</button><button id="focus-robot" class="icon-button" aria-label="Focus robot">${icon("focus")}</button></div><div class="twin-footer"><span><i class="legend-robot"></i>G1-01</span><span><i class="legend-route"></i>Planned route</span><span><i class="legend-hazard"></i>Exclusion zone</span></div></div><div id="replay-strip" hidden><button id="play-replay" class="text-button">Play</button><input id="replay-slider" type="range" min="0" max="1" value="0" aria-label="Replay time"><span id="replay-time">0.0 s</span><button id="close-replay" class="text-button">Exit replay</button></div><div class="robot-strip"><span class="robot-avatar">${icon("bot")}</span><div><strong>G1-01 <span id="robot-state">Ready</span></strong><p id="robot-detail">Unitree G1 · Awaiting inspection assignment</p></div><button id="stop" class="secondary" disabled>${icon("pause")}Pause run</button></div></section>
<aside class="inspector"><div class="panel-heading"><div><h2>Mission control</h2><span id="mission-sub">No active inspection</span></div>${icon("workflow")}</div><div id="mission-body"></div></aside></div>
<section class="recent"><div class="section-title"><h2>Inspection queue</h2><span id="run-count">0 inspections</span></div><div id="queue"></div></section></section>
<section id="alternate" hidden></section>
<footer><span>ShiftOps / From observation to accountable action.</span><span>Robot motion and sensor readings are simulated.</span></footer></main>
<dialog id="intake"><form id="intake-form"><div class="dialog-heading"><div><p class="eyebrow">DISPATCH G1-01</p><h2>Start an inspection</h2></div><button type="button" class="icon-button" id="close-intake" aria-label="Close">${icon("x")}</button></div><p class="dialog-intro">Choose an operational incident. ShiftOps inspects the asset and prepares a maintenance handoff.</p><div id="scenario-options"></div><label class="checkbox-row"><input type="checkbox" name="blocked" checked><span>Loading aisle blocked<small>Plan a route around the exclusion zone.</small></span></label><label class="field-label" for="note">Operator context <span>optional</span></label><textarea id="note" name="note" maxlength="1000" placeholder="Add context for the maintenance team…"></textarea><p class="simulation-note">${icon("flask-conical")}This creates an isolated simulation. No hardware moves or purchases occur.</p><button class="primary full" type="submit">${icon("arrow-up-right")}Dispatch inspection</button></form></dialog>
<div id="toast" role="status"></div>`;

function drawIcons() {
  createIcons({ icons, attrs: { "stroke-width": 1.65 } });
}
async function api(path: string, body?: any) {
  const response = await fetch("/api" + path, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    let message;
    try {
      message = (await response.json()).detail;
    } catch {
      message = response.statusText;
    }
    throw Error(
      typeof message === "string" ? message : JSON.stringify(message),
    );
  }
  return response.json();
}
function fail(error: any) {
  const e = document.querySelector<HTMLElement>("#error")!;
  e.textContent = error.message || String(error);
  e.hidden = false;
}
function toast(message: string) {
  const e = document.querySelector<HTMLElement>("#toast")!;
  e.textContent = message;
  e.classList.add("show");
  setTimeout(() => e.classList.remove("show"), 3500);
}
function current() {
  return data.missions.find((m: any) => m.id === selected) || data.missions[0];
}
function badge(status: string) {
  return `<span class="status status-${esc(status)}">${esc(statusNames[status] || status)}</span>`;
}
function missionView(m: any) {
  if (!m)
    return `<div class="empty-mission"><span class="empty-icon">${icon("route")}</span><h3>Ready for the next task.</h3><p>Send G1 to inspect an equipment issue. Watch the route, evidence and handoff arrive here.</p><button class="secondary" data-start>Start an inspection ${icon("arrow-right")}</button><div class="workflow-preview"><span>01 Inspect</span><span>02 Review</span><span>03 Handoff</span></div></div>`;
  const stages = [
    "Incident accepted",
    "Route & dispatch",
    "Inspect equipment",
    "Approve handoff",
    "Work order",
  ];
  const active = [
    "planning",
    "navigating",
    "inspecting",
    "awaiting_approval",
    "paused",
  ].includes(m.status);
  const stage =
    m.status === "complete"
      ? 5
      : m.evidence
        ? 3
        : m.events.some((e: any) => e.kind === "arrival")
          ? 2
          : 1;
  const stageLabel =
    m.status === "paused"
      ? "Paused"
      : m.status === "awaiting_approval"
        ? "Awaiting your decision"
        : "In progress";
  const evidence = m.evidence;
  return `<div class="mission-content"><div class="mission-name"><span class="asset-id">${esc(m.scenario.asset)} / ${esc(m.id.slice(0, 6).toUpperCase())}</span>${badge(m.status)}<h3>${esc(m.scenario.name)}</h3><p>${esc(m.scenario.location)} · ${esc(m.scenario.priority)} priority</p></div><ol class="workflow">${stages.map((s, i) => `<li class="${i < stage ? "done" : i === stage && active ? "current" : ""}"><span>${i < stage ? icon("check") : String(i + 1).padStart(2, "0")}</span><div>${s}${i === stage && active ? `<small>${stageLabel}</small>` : ""}</div></li>`).join("")}</ol>
  ${evidence ? `<div class="evidence"><div class="small-heading">${icon("scan-eye")}INSPECTION EVIDENCE</div><div class="reading"><strong>${esc(evidence.value)}<small>${esc(evidence.unit)}</small></strong><span>${esc(evidence.sensor)}<small>Threshold ${esc(evidence.threshold)} ${esc(evidence.unit)}</small></span></div><p>${esc(evidence.rationale)}</p><small>Source: ${esc(evidence.source)}</small></div>` : `<div class="telemetry"><div><span>Distance walked</span><strong>${Number(m.distance).toFixed(1)} m</strong></div><div><span>Obstacle contacts</span><strong>${m.contacts}</strong></div><div><span>Simulation time</span><strong>${Math.floor(m.sim_seconds)} s</strong></div></div>`}
  ${m.status === "awaiting_approval" ? `<div class="approval"><h4>${m.proposal.action === "reserve" ? "Reserve part & create work order" : "Create purchase request"}</h4><p>${esc(m.proposal.part_name)} <b>$${m.proposal.estimated_cost}</b></p><small>${m.proposal.in_stock} in stock · ${m.proposal.action === "reserve" ? "1 will be reserved" : "No order sent to an external vendor"}</small><div class="approval-actions"><button class="primary" data-decision="approve" ${pending ? "disabled" : ""}>${icon("check")}Approve handoff</button><button class="text-button" data-decision="reject" ${pending ? "disabled" : ""}>Reject</button></div></div>` : ""}
  ${m.status === "complete" ? `<div class="completion">${icon("circle-check")}<div><strong>${esc(m.order)} created</strong><p>Handoff complete. ${m.proposal.action === "reserve" ? "Repair is pending with maintenance." : "Purchasing review is pending."}</p></div></div>` : ""}
  ${m.status === "paused" ? `<div class="notice">Simulation paused. The run and robot state are saved.<button class="secondary" id="resume">${icon("play")}Resume inspection</button></div>` : ""}
  ${m.status === "canceled" || m.status === "rejected" ? `<div class="notice terminal-notice">${m.status === "canceled" ? "Inspection canceled." : "Handoff rejected."} Evidence is retained. No stock was reserved or work order created.</div>` : ""}
  ${m.error ? `<div class="notice error-notice">${esc(m.error)}</div>` : ""}
  ${active ? `<button class="text-button cancel-button" id="cancel" ${pending ? "disabled" : ""}>${icon("x")}Cancel inspection</button>` : ""}
  <button class="text-button replay-button" id="replay" ${m.sim_seconds ? "" : "disabled"}>${icon("play")}Replay recorded motion</button><a class="evidence-link" href="/api/missions/${m.id}/evidence" download>${icon("download")}Export evidence bundle</a></div>`;
}

function render() {
  const m = current();
  if (!replayFrames.length) {
    twin?.update(m);
    document.querySelector(".live-tag")!.innerHTML =
      "<span></span>" +
      (m?.status === "navigating" ? "LIVE PHYSICS" : "SIMULATION");
  }
  const key = JSON.stringify([
    data.missions,
    data.orders,
    selected,
    tab,
    pending,
  ]);
  if (key === renderKey) return;
  renderKey = key;
  const counts = {
    active: data.missions.filter((x: any) =>
      ["planning", "navigating", "inspecting", "paused"].includes(x.status),
    ).length,
    approval: data.missions.filter((x: any) => x.status === "awaiting_approval")
      .length,
  };
  document.querySelector("#active-stat")!.textContent = String(counts.active);
  document.querySelector("#approval-stat")!.textContent = String(
    counts.approval,
  );
  document.querySelector("#completed-stat")!.textContent = String(
    data.orders.length,
  );
  document.querySelector("#order-count")!.textContent = String(
    data.orders.length,
  );
  document.querySelector("#robot-state")!.textContent = m
    ? statusNames[m.status]
    : "Ready";
  document.querySelector("#robot-detail")!.textContent = m
    ? `${m.scenario.asset} · ${Number(m.distance).toFixed(1)} m walked · ${m.contacts} obstacle contacts`
    : "Unitree G1 · Awaiting inspection assignment";
  const stop = document.querySelector<HTMLButtonElement>("#stop")!;
  stop.disabled =
    !m || !["planning", "navigating", "inspecting"].includes(m.status);
  document.querySelector("#mission-sub")!.textContent = m
    ? `Inspection ${m.id.slice(0, 6).toUpperCase()}`
    : "No active inspection";
  const body = document.querySelector("#mission-body")!;
  // Do not steal focus from approval buttons on each telemetry update.
  const html = missionView(m);
  if ((body as HTMLElement).dataset.renderKey !== html) {
    body.innerHTML = html;
    (body as HTMLElement).dataset.renderKey = html;
  }
  document.querySelector("#run-count")!.textContent =
    `${data.missions.length} inspections`;
  document.querySelector("#queue")!.innerHTML = data.missions.length
    ? `<div class="table-scroll"><table><thead><tr><th>Incident / asset</th><th>Priority</th><th>Status</th><th>Created</th><th></th></tr></thead><tbody>${data.missions.map((x: any) => `<tr class="${m?.id === x.id ? "selected-row" : ""}" data-mission="${x.id}" tabindex="0"><td><strong>${esc(x.scenario.name)}</strong><small>${esc(x.scenario.asset)} · ${esc(x.scenario.location)}</small></td><td><span class="priority">${esc(x.scenario.priority)}</span></td><td>${badge(x.status)}</td><td class="mono">${time(x.created)}</td><td>${icon("arrow-up-right")}</td></tr>`).join("")}</tbody></table></div>`
    : `<div class="empty-queue"><span>No inspections yet. Start with an air-handler alert or a pump pressure issue.</span><button class="text-button" data-start>Create inspection ${icon("arrow-right")}</button></div>`;
  if (tab !== "operations") renderAlternate();
  drawIcons();
}

function renderAlternate() {
  const alternate = document.querySelector("#alternate")!;
  const key = JSON.stringify([
    tab,
    data.orders,
    data.missions.map((m: any) => [m.id, m.events]),
  ]);
  if (key === alternateKey) return;
  alternateKey = key;
  if (tab === "orders")
    alternate.innerHTML = `<div class="section-title"><h2>Maintenance handoffs</h2><span>${data.orders.length} work orders</span></div>${data.orders.length ? data.orders.map((o: any) => `<article class="order"><div class="order-top"><span class="asset-id">${esc(o.id)} / ${esc(o.asset)}</span><span class="status">${esc(o.status)}</span></div><h2>${esc(o.title)}</h2><p>${esc(o.evidence.rationale)}</p><div class="order-details"><span><small>PART</small>${esc(o.proposal.part_name)}</span><span><small>ESTIMATED COST</small>$${o.proposal.estimated_cost}</span><span><small>ASSIGNED TO</small>Facilities maintenance</span><span><small>APPROVED</small>${time(o.approved_at)}</span></div><a href="/api/missions/${o.mission}/evidence" download class="evidence-link">${icon("download")}Download evidence and approval record</a></article>`).join("") : '<div class="large-empty">Approved inspections become work orders here. No work order is created before operator approval.</div>'}`;
  if (tab === "activity") {
    const events = data.missions
      .flatMap((m: any) =>
        m.events.map((e: any) => ({ ...e, asset: m.scenario.asset })),
      )
      .sort((a: any, b: any) => b.id - a.id);
    alternate.innerHTML = `<div class="section-title"><h2>Durable activity log</h2><span>${events.length} events</span></div><div class="activity">${events.length ? events.map((e: any) => `<article><time>${time(e.created)}</time><span class="activity-dot"></span><div><strong>${esc(e.title)}</strong><small>${esc(e.asset)} · ${esc(e.kind)}</small><details><summary>View recorded evidence</summary><pre>${esc(JSON.stringify(e.detail, null, 2))}</pre></details></div></article>`).join("") : '<div class="large-empty">Each decision and state change will be recorded here.</div>'}</div>`;
  }
  if (tab === "about")
    alternate.innerHTML = `<div class="about"><p class="eyebrow">OBSERVE → DECIDE → ACT → VERIFY</p><h2>One control plane.<br>A complete operational record.</h2><p>ShiftOps coordinates a simulated facility inspection with a real physics engine and a durable enterprise workflow. The backend owns every route, observation, approval and inventory update.</p><div class="architecture"><div>${icon("monitor")}Browser workspace<small>3D twin, evidence, approvals</small></div><span>↕</span><div>${icon("server")}VM backend<small>FastAPI · REST + event stream</small></div><span>↕</span><div>${icon("database")}SQLite + MuJoCo<small>Durable state · CPU robot physics</small></div></div><h3>What is real in this demo</h3><ul><li>G1 joint motion is computed by MuJoCo with the existing Unitree locomotion policy.</li><li>Routes avoid exclusion zones; a contact or stability fault stops the run.</li><li>Work orders, approval records and parts reservations persist in the backend database.</li><li>Every browser receives an isolated demonstration workspace.</li></ul><h3>What is simulated</h3><p>The facility, equipment sensor readings, maintenance team and inventory. No physical robot is connected, no external purchase is sent, and creating a work order does not mean equipment is repaired.</p><h3>Built on your robotics work</h3><p>The G1 model and CPU gait controller are reused from G1 Street Wise. The operations application, persistent workflow, approval ledger and facility scene are new.</p><p class="simulation-note">Rules determine inspection and maintenance decisions. No language-model reasoning is claimed.</p></div>`;
}
function switchTab(next: string) {
  tab = next;
  document
    .querySelectorAll<HTMLButtonElement>("[data-tab]")
    .forEach((b) => b.classList.toggle("active", b.dataset.tab === next));
  document.querySelector<HTMLElement>("#operations")!.hidden =
    next !== "operations";
  document.querySelector<HTMLElement>("#alternate")!.hidden =
    next === "operations";
  const title = {
    operations: "Operations",
    orders: "Work orders",
    activity: "Activity log",
    about: "System overview",
  }[next]!;
  document.querySelector("#page-title")!.textContent = title;
  document.querySelector("#heading")!.textContent =
    next === "operations" ? "Facility operations" : title;
  document.querySelector("#subheading")!.textContent = {
    operations: "Manage inspections, approvals and maintenance handoffs.",
    orders: "Approved maintenance work, backed by inspection evidence.",
    activity: "Every action, decision and handoff in chronological order.",
    about:
      "A transparent view of what runs, where state lives and what is simulated.",
  }[next]!;
  render();
}
function exitReplay() {
  replayFrames = [];
  replayPlaying = false;
  document.querySelector<HTMLElement>("#replay-strip")!.hidden = true;
  document.querySelector(".live-tag")!.innerHTML = "<span></span>SIMULATION";
  twin?.update(current());
}
document.querySelector("#replay-slider")!.addEventListener("input", (e) => {
  replayIndex = Number((e.target as HTMLInputElement).value);
  replayPlaying = false;
  document.querySelector("#play-replay")!.textContent = "Play";
});
setInterval(() => {
  if (!replayFrames.length) return;
  const frame = replayFrames[replayIndex];
  twin?.update({ ...current(), pose: frame.qpos });
  document.querySelector("#replay-time")!.textContent =
    frame.time.toFixed(1) + " s";
  document.querySelector<HTMLInputElement>("#replay-slider")!.value =
    String(replayIndex);
  if (replayPlaying) {
    replayIndex = (replayIndex + 1) % replayFrames.length;
  }
}, 100);
function openIntake() {
  document.querySelector<HTMLDialogElement>("#intake")!.showModal();
}
document.addEventListener("click", async (event) => {
  const target = event.target as HTMLElement;
  const button = target.closest<HTMLElement>("button,a,tr[data-mission]");
  if (!button) return;
  if (button.dataset.tab) switchTab(button.dataset.tab);
  if (button.id === "new-mission" || button.hasAttribute("data-start"))
    openIntake();
  if (button.id === "close-intake")
    document.querySelector<HTMLDialogElement>("#intake")!.close();
  if (button.id === "help") switchTab("about");
  if (button.id === "reset-view") twin.resetCamera();
  if (button.id === "focus-robot") twin.focusRobot();
  if (button.dataset.mission) {
    exitReplay();
    selected = button.dataset.mission;
    render();
  }
  if (button.id === "close-replay") exitReplay();
  if (button.id === "play-replay") {
    replayPlaying = !replayPlaying;
    button.textContent = replayPlaying ? "Pause" : "Play";
  }
  if (button.id === "replay") {
    try {
      const recording = await api(`/missions/${current().id}/replay`);
      replayFrames = recording.frames;
      replayIndex = 0;
      replayPlaying = true;
      document.querySelector<HTMLElement>("#replay-strip")!.hidden = false;
      document.querySelector<HTMLInputElement>("#replay-slider")!.max = String(
        Math.max(0, replayFrames.length - 1),
      );
      document.querySelector("#play-replay")!.textContent = "Pause";
      document.querySelector(".live-tag")!.textContent = "RECORDED REPLAY";
    } catch (e) {
      fail(e);
    }
    return;
  }
  if (pending) return;
  const m = current();
  if (!m) return;
  try {
    if (
      button.id === "stop" ||
      button.id === "resume" ||
      button.id === "cancel" ||
      button.dataset.decision
    ) {
      pending = true;
      (button as HTMLButtonElement).disabled = true;
      await api(
        `/missions/${m.id}/${button.dataset.decision ? "decision" : button.id}`,
        button.dataset.decision ? { action: button.dataset.decision } : {},
      );
      data = await api("/state");
      toast(
        button.dataset.decision === "approve"
          ? "Work order committed. Evidence and approval saved."
          : button.id === "stop"
            ? "Simulation paused. State saved."
            : button.id === "cancel"
              ? "Inspection canceled. Evidence retained."
              : "Operation recorded.",
      );
    }
  } catch (e) {
    fail(e);
  } finally {
    pending = false;
    render();
  }
});
document.addEventListener("keydown", (e) => {
  const row = (e.target as HTMLElement).closest<HTMLElement>(
    "tr[data-mission]",
  );
  if (row && (e.key === "Enter" || e.key === " ")) {
    e.preventDefault();
    selected = row.dataset.mission!;
    render();
  }
});
document
  .querySelector("#intake-form")!
  .addEventListener("submit", async (event) => {
    event.preventDefault();
    if (pending) return;
    pending = true;
    const form = event.target as HTMLFormElement;
    const values = new FormData(form);
    const submit = form.querySelector<HTMLButtonElement>(
      "button[type=submit]",
    )!;
    submit.disabled = true;
    try {
      const m = await api("/missions", {
        scenario: values.get("scenario"),
        blocked: values.get("blocked") === "on",
        note: values.get("note"),
        request_key: crypto.randomUUID(),
      });
      selected = m.id;
      data = await api("/state");
      document.querySelector<HTMLDialogElement>("#intake")!.close();
      switchTab("operations");
      document.querySelector<HTMLElement>("#error")!.hidden = true;
    } catch (e) {
      fail(e);
      document.querySelector<HTMLDialogElement>("#intake")!.close();
    } finally {
      pending = false;
      submit.disabled = false;
      render();
    }
  });

async function boot() {
  try {
    await api("/session", {});
    const [f, state, health] = await Promise.all([
      api("/facility"),
      api("/state"),
      api("/health"),
    ]);
    facility = f;
    data = state;
    document.querySelector("#deployment")!.textContent =
      health.deployment === "vultr"
        ? "Vultr VM · SQLite"
        : "Local backend · SQLite";
    document.querySelector("#scenario-options")!.innerHTML = Object.entries(
      f.scenarios,
    )
      .map(
        ([key, s]: [string, any], i) =>
          `<label class="scenario-option"><input type="radio" name="scenario" value="${key}" ${i === 0 ? "checked" : ""}><span>${icon(i === 1 ? "droplets" : i === 2 ? "wind" : "thermometer")}<strong>${esc(s.name)}<small>${esc(s.asset)} · ${esc(s.location)}</small></strong><span class="priority">${esc(s.priority)}</span></span></label>`,
      )
      .join("");
    try {
      twin = new FacilityTwin(document.querySelector("#twin")!, facility);
    } catch (e) {
      fail(
        Error(
          "3D rendering is unavailable in this browser. Mission controls and evidence remain available.",
        ),
      );
    }
    document
      .querySelector("#twin")!
      .addEventListener("twin-error", (e) =>
        fail(Error((e as CustomEvent).detail)),
      );
    render();
    stream = new EventSource("/api/events");
    stream.onmessage = (event) => {
      data = JSON.parse(event.data);
      document.querySelector("#connection")!.textContent = "Connected";
      document.querySelector("#connection")!.classList.add("online");
      render();
    };
    stream.onerror = () => {
      document.querySelector("#connection")!.textContent = "Reconnecting";
      document.querySelector("#connection")!.classList.remove("online");
    };
  } catch (e) {
    fail(e);
    document.querySelector("#connection")!.textContent = "Disconnected";
  }
}
drawIcons();
void boot();
