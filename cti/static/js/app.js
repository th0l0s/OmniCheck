/* app.js — entry point. Routing, polling, event wiring. */
import { STATE, tlPush } from './state.js';
import { loadAll, loadDetail } from './api.js';
import { render } from './render.js';
import { sourceStatus } from './components.js';

/* ── Hash routing ───────────────────────────────────────────── */
function _parseHash() {
  const h = (location.hash || "#/overview").replace(/^#\/?/, "");
  const parts = h.split("/");
  return { route: parts[0] || "overview", param: parts.slice(1).join("/") || null };
}

function _afterRoute() {
  // Source pages carry a substatus payload (logic/config/log/tools) loaded lazily.
  if (STATE.route === "source" && STATE.routeParam && !STATE.detail[STATE.routeParam]) {
    loadDetail(STATE.routeParam).then(render);
  }
}

export function navigate(path) {
  const clean = String(path).replace(/^#?\/?/, "");
  const parts = clean.split("/");
  STATE.route     = parts[0] || "overview";
  STATE.routeParam= parts.slice(1).join("/") || null;
  history.pushState(null, "", "#/" + clean);
  render();
  _afterRoute();
}

window.navigate = navigate;

window.addEventListener("popstate", () => {
  const { route, param } = _parseHash();
  STATE.route      = route;
  STATE.routeParam = param;
  render();
  _afterRoute();
});

/* ── Filter state (used from source detail / feed center) ────── */
window.setFilter = function(sid, key, val) {
  if (!STATE._filters) STATE._filters = {};
  STATE._filters[`${sid}:${key}`] = val || null;
  render();
};

/* ── Force refresh ──────────────────────────────────────────── */
window.forceRefresh = async function(id) {
  const key = prompt("API Key:");
  if (!key) return;
  try {
    await fetch("/api/refresh/" + id, {
      method: "POST",
      headers: { "X-API-Key": key },
    });
    await _refresh();
  } catch (e) {
    console.error("refresh failed", e);
  }
};

/* ── L0 tool runner ─────────────────────────────────────────── */
window.runTool = async function(sid, idx, tool) {
  const argEl   = document.getElementById(`tr-arg-${sid}-${idx}`);
  const extraEl = document.getElementById(`tr-extra-${sid}-${idx}`);
  const target  = argEl ? argEl.value.trim() : "";
  const extra   = extraEl ? extraEl.value.trim() : null;
  if (!target) return;
  const key = prompt("API Key:");
  if (!key) return;
  const okey = `${sid}:${idx}`;
  STATE.toolOut[okey] = { ok: false, output: "running…" };
  render();
  try {
    const r = await fetch("/api/tool/" + encodeURIComponent(tool), {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": key },
      body: JSON.stringify({ target, extra }),
    });
    STATE.toolOut[okey] = await r.json();
  } catch (e) {
    STATE.toolOut[okey] = { ok: false, error: String(e) };
  }
  render();
};

/* ── Target management ──────────────────────────────────────── */
window.addTarget = async function() {
  const inp = document.getElementById("tgt-new");
  if (!inp || !inp.value.trim()) return;
  const key = prompt("API Key:");
  if (!key) return;
  await fetch("/api/targets", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": key },
    body: JSON.stringify({ add: [inp.value.trim()], remove: [] }),
  });
  inp.value = "";
  await _refresh();
};

window.rmTarget = async function(addr) {
  const key = prompt("API Key:");
  if (!key) return;
  await fetch("/api/targets", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": key },
    body: JSON.stringify({ add: [], remove: [addr] }),
  });
  await _refresh();
};

/* ── Main refresh loop ──────────────────────────────────────── */
async function _refresh() {
  await loadAll();
  // push current status into per-source timeline
  STATE.sources.forEach(s => tlPush(s.id, sourceStatus(s)));
  render();
  _afterRoute();
}

/* ── Countdown ──────────────────────────────────────────────── */
setInterval(() => {
  STATE.next = Math.max(0, STATE.next - 1);
  const cd = document.getElementById("countdown");
  if (cd) cd.textContent = `↻ ${STATE.next}s`;
  if (STATE.next <= 0) _refresh();
}, 1000);

/* ── Events ─────────────────────────────────────────────────── */
document.getElementById("refresh-btn")?.addEventListener("click", _refresh);

document.addEventListener("keydown", e => {
  if (e.key === "r" && !e.ctrlKey && !e.metaKey &&
      document.activeElement.tagName !== "INPUT") _refresh();
});

/* ── Boot ───────────────────────────────────────────────────── */
const _init = _parseHash();
STATE.route      = _init.route;
STATE.routeParam = _init.param;

_refresh();
