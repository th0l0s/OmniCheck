/* state.js — shared runtime state. No side effects on import. */

export const STATE = {
  sources: [],
  data: {},
  status: null,
  ui: { app: "OmniCheck Cockpit", poll_interval_s: 15, readonly: true },
  route: "overview",
  routeParam: null,
  next: 15,
  refreshMs: 15000,
  detail: {},        // id -> {logic, config, events, tools}
  tools: [],         // available diagnostic tool descriptors
  toolOut: {},       // "id:idx" -> last tool run result
};

/* The three L0 essentials promoted to header control-lights ("spie"). */
export const SPIE = ["bgp", "cloud_status", "rootmon"];

/* ── Timeline: last 20 status checks per source (localStorage) ── */
const _TL_KEY = "omni_tl_v1";

export function tlGet() {
  try { return JSON.parse(localStorage.getItem(_TL_KEY) || "{}"); }
  catch { return {}; }
}

export function tlPush(id, status) {
  const tl = tlGet();
  const arr = tl[id] || [];
  arr.push(status);
  if (arr.length > 20) arr.splice(0, arr.length - 20);
  tl[id] = arr;
  try { localStorage.setItem(_TL_KEY, JSON.stringify(tl)); } catch {}
}
