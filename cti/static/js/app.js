/* app.js — entry point. Lifecycle, navigation, polling, event wiring. */
import { STATE } from './state.js';
import { loadAll } from './api.js';
import { render } from './render.js';
import { panelStatus } from './components.js';

/* ── navigation ─────────────────────────────────────────────── */
function go(id) {
  if (id === "overview") { showOverview(); return; }
  STATE.view = id;
  render();
  const pc = document.querySelector(".page-content");
  if (pc) pc.scrollTop = 0;
}

function showOverview() {
  STATE.view = "overview";
  render();
}

function goToProblem() {
  for (const priority of ["crit", "err", "warn"]) {
    const s = STATE.sources.find(x =>
      x.enabled && panelStatus(x, (STATE.data[x.id] || {}).data) === priority
    );
    if (s) { go(s.id); return; }
  }
  const degraded = STATE.sources.find(x => x.enabled && !x.ok);
  if (degraded) { go(degraded.id); return; }
  go("about");
}

/* ── filter state ────────────────────────────────────────────── */
function setDomFilter(sid, v) {
  STATE.domainFilters[sid] = { val: v };
  render();
}

function setFeedFilter(sid, dim, v) {
  if (!STATE.feedFilters[sid]) STATE.feedFilters[sid] = {};
  STATE.feedFilters[sid][dim] = v;
  render();
}

/* ── panel collapse state (persisted in localStorage) ────────── */
function togglePanel(id) {
  const key = "pcol_" + id;
  localStorage.setItem(key, localStorage.getItem(key) === "1" ? "0" : "1");
  render();
}

/* ── target management (requires CTI_API_KEY on server) ────────── */
async function addTarget() {
  const inp = document.getElementById("tgt-new");
  const v   = (inp ? inp.value : "").trim();
  if (!v) return;
  const r = await fetch("/api/targets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ add: [v], remove: [] }),
  });
  if (r.ok) {
    if (inp) inp.value = "";
    await _refresh();
  } else {
    const e = await r.json().catch(() => ({}));
    alert("Error: " + (e.detail || r.status));
  }
}

async function rmTarget(addr) {
  if (!confirm("Remove " + addr + "?")) return;
  const r = await fetch("/api/targets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ add: [], remove: [addr] }),
  });
  if (r.ok) { await _refresh(); }
  else {
    const e = await r.json().catch(() => ({}));
    alert("Error: " + (e.detail || r.status));
  }
}

/* ── main refresh cycle ─────────────────────────────────────── */
async function _refresh() {
  await loadAll();
  render();
}

/* ── expose globals for inline onclick handlers ─────────────── */
window.go           = go;
window.showOverview = showOverview;
window.goToProblem  = goToProblem;
window.setDomFilter = setDomFilter;
window.setFeedFilter= setFeedFilter;
window.togglePanel  = togglePanel;
window.addTarget    = addTarget;
window.rmTarget     = rmTarget;
window.loadAll      = _refresh;

/* ── event wiring ───────────────────────────────────────────── */
document.getElementById("brand-link")?.addEventListener("click", e => {
  e.preventDefault();
  showOverview();
});

document.getElementById("refresh-btn")?.addEventListener("click", () => _refresh());

document.getElementById("threat-badge")?.addEventListener("click", () => goToProblem());

/* keyboard activation for role="button" elements (chips, etc.) */
document.addEventListener("keydown", e => {
  const t = e.target;
  if ((e.key === "Enter" || e.key === " ") &&
      t && t.getAttribute && t.getAttribute("role") === "button") {
    e.preventDefault();
    t.click();
  }
});

/* ── countdown timer ────────────────────────────────────────── */
setInterval(() => {
  STATE.next = Math.max(0, STATE.next - 1);
  const el = document.getElementById("countdown");
  if (el) el.textContent = STATE.next > 0 ? STATE.next + "s" : "…";
  if (STATE.next <= 0) _refresh();
}, 1000);

/* ── boot ───────────────────────────────────────────────────── */
_refresh();
