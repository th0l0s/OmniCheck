/* api.js — fetch layer. All network calls go through here. */
import { STATE } from './state.js';

export async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} → HTTP ${r.status}`);
  return r.json();
}

export async function loadAll() {
  const btn = document.getElementById("refresh-btn");
  if (btn) { btn.disabled = true; btn.classList.add("syncing"); }
  try {
    /* /api/ui first — it configures poll interval and readonly mode */
    const [uiConf, src] = await Promise.all([
      fetchJSON("/api/ui").catch(() => STATE.ui),
      fetchJSON("/api/sources"),
    ]);
    Object.assign(STATE.ui, uiConf);
    STATE.refreshMs = (STATE.ui.poll_interval_s || 15) * 1000;
    STATE.sources = src.sources || [];

    const ds = await Promise.all(
      STATE.sources.map(s => fetchJSON("/api/data/" + s.id).catch(() => ({})))
    );
    STATE.data = {};
    STATE.sources.forEach((s, i) => { STATE.data[s.id] = ds[i]; });

    STATE.status = await fetchJSON("/api/status").catch(() => null);
    STATE.next = STATE.refreshMs / 1000;

    const tl = document.getElementById("ts-lbl");
    if (tl) tl.textContent = "updated " + new Date().toLocaleTimeString();
  } finally {
    if (btn) { btn.disabled = false; btn.classList.remove("syncing"); }
  }
}
