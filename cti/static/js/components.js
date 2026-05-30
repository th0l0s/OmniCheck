/* components.js — pure HTML builders. Input → HTML string. No DOM mutation. */
import { STATE, tlGet, SPIE } from './state.js';

/* ── Layer naming (L0 essentials · L1 check · L2 info) ──────── */
const _LAYER_LABEL = { 0: "Essentials", 1: "Check", 2: "Info", 4: "Advanced" };
export function layerLabel(n) { return _LAYER_LABEL[n] || `L${n}`; }

/* ── Escape helpers ─────────────────────────────────────────── */
export function esc(s) {
  return String(s == null ? "" : s)
    .replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
}

export function jsq(s) {
  return esc("'" + String(s == null ? "" : s)
    .replace(/\\/g, "\\\\").replace(/'/g, "\\'") + "'");
}

export function badge(v) {
  const c = String(v).toLowerCase().replace(/[^a-z0-9_]/g, "_");
  return `<span class="badge b-${c}">${esc(v)}</span>`;
}

export function fmtAge(s) {
  if (s == null) return "—";
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`;
  return `${Math.round(s / 3600)}h`;
}

export function img(path, cls) {
  if (!path || !String(path).startsWith("/icons")) return "";
  return `<img class="${esc(cls)}" src="${esc(path)}" onerror="this.style.display='none'" alt="">`;
}

export function val(id, k) {
  const d = STATE.data[id];
  return d && d.data ? d.data[k] : undefined;
}

/* ── Layer / kind helpers ───────────────────────────────────── */
export function layerOf(s)   { return s.layer ?? 0; }
export function kindOf(s)    { return s.kind  ?? "internet_health"; }
export function overviewOf(s){ return s.overview !== false; }

export function sourcesByLayer(layer) {
  return STATE.sources.filter(s => layerOf(s) === layer);
}

export function isConfigured(s) {
  if (!s.enabled) return false;
  const err = (s.error || s.last_error || "").toLowerCase();
  if (err.includes("missing config")) return false;
  if (s.requires && s.requires.length > 0 && !s.last_fetch && !s.ok) return false;
  return true;
}

/* ── Status semantics ───────────────────────────────────────── */
export function sourceStatus(s) {
  if (!s.enabled) return "off";
  const err = (s.error || s.last_error || "").toLowerCase();
  if (err.includes("missing config")) return "config";
  if (s.requires && s.requires.length > 0 && !s.ok && !s.last_fetch) return "config";

  const age = (STATE.data[s.id] || {}).age_s ?? s.age_s;
  if (age != null && s.interval && age > s.interval * 2.5) return "stale";
  if (!s.ok && err) return "source_error";
  if (!s.ok) return "warning";

  const d = (STATE.data[s.id] || {}).data || {};
  if ((d.at_risk > 2) || (d.fail > 3) || (d.degraded > 1)) return "critical";
  if ((d.at_risk > 0) || (d.fail > 0) || (d.degraded > 0) || (d.correlated_iocs > 0)) return "warning";
  return "ok";
}

export function globalStatus() {
  const sts = STATE.sources.map(s => sourceStatus(s));
  if (sts.includes("critical"))    return "critical";
  if (sts.includes("source_error"))return "source_error";
  if (sts.includes("warning"))     return "warning";
  if (sts.includes("stale"))       return "stale";
  return "ok";
}

const _LABELS = {
  ok:"OK", warning:"WARN", critical:"CRIT",
  source_error:"ERR", stale:"STALE", off:"OFF", config:"CONF",
};

/* ── LED indicator ──────────────────────────────────────────── */
export function led(status, large) {
  const sz = large ? " led-lg" : "";
  return `<span class="led${sz} led-${esc(status)}"></span>`;
}

/* ── Mini timeline strip (20 bars) ─────────────────────────── */
export function timelineStrip(id) {
  const hist = (tlGet()[id] || []);
  if (!hist.length) return '<div class="tl-strip tl-empty"></div>';
  return `<div class="tl-strip">${
    hist.map(st => `<span class="tl-bar tl-${esc(st)}" title="${esc(st)}"></span>`).join("")
  }</div>`;
}

/* ── Uptime Kuma–style monitor card ─────────────────────────── */
export function monitorCard(s) {
  const st   = sourceStatus(s);
  const lbl  = _LABELS[st] || st.toUpperCase();
  const age  = fmtAge((STATE.data[s.id] || {}).age_s ?? s.age_s);
  const ivl  = fmtAge(s.interval);
  const desc = esc((s.schema && s.schema.description) || "");
  const kind = esc(kindOf(s).replace(/_/g, " "));
  const nav  = jsq("source/" + s.id);

  return `<div class="mc mc-${esc(st)}" onclick="window.navigate(${nav})"
      role="button" tabindex="0" onkeydown="if(event.key==='Enter')window.navigate(${nav})">
  <div class="mc-top">
    ${led(st, false)}
    <span class="mc-name">${esc(s.name)}</span>
    <span class="mc-pill pill-${esc(st)}">${esc(lbl)}</span>
  </div>
  ${desc ? `<div class="mc-desc">${desc}</div>` : ""}
  <div class="mc-meta">
    <span class="mc-kind">${kind}</span>
    <span class="mc-age" title="data age">⏱ ${esc(age)}</span>
    <span class="mc-ivl" title="refresh every">↻ ${esc(ivl)}</span>
  </div>
  ${timelineStrip(s.id)}
  <a class="mc-link" href="#/source/${esc(s.id)}" onclick="event.stopPropagation()">engine results →</a>
</div>`;
}

/* ── Summary KV cards ───────────────────────────────────────── */
export function summaryCards(s, data) {
  const keys = (s.schema && s.schema.summary_keys) || [];
  if (!keys.length || !data) return "";
  const items = keys.map(k => {
    const v = data[k];
    return `<div class="kv-item">
      <div class="kv-v">${esc(v ?? "—")}</div>
      <div class="kv-k">${esc(k.replace(/_/g, " "))}</div>
    </div>`;
  });
  return `<div class="kv-grid">${items.join("")}</div>`;
}

/* ── Table builder ──────────────────────────────────────────── */
export function tableHtml(t, data, filterKey, filterVal) {
  if (!t || !data) return "";
  let rows = data[t.rows_key] || [];
  if (filterKey && filterVal)
    rows = rows.filter(r => String(r[filterKey] || "").toLowerCase() === String(filterVal).toLowerCase());
  if (!rows.length) return "<p class='empty-note'>No data.</p>";
  const cols = t.columns || [];
  const head = cols.map(c => `<th>${esc(c.label)}</th>`).join("");
  const body = rows.map(row => {
    const cells = cols.map(c => {
      let v = row[c.key]; if (v == null) v = "";
      let cell;
      if (c.badge) {
        cell = (c.icon_key && row[c.icon_key] ? img(row[c.icon_key], "row-icon") + " " : "") + badge(v);
      } else if (c.link_key && row[c.link_key]) {
        cell = `<a href="${esc(row[c.link_key])}" target="_blank" rel="noopener">${esc(v)}</a>`;
      } else if (c.icon_key && row[c.icon_key]) {
        cell = img(row[c.icon_key], "row-icon") + " " + esc(v);
      } else {
        cell = esc(v);
      }
      const cls = c.mono ? ' class="c-mono"' : c.numeric ? ' class="c-dim"' : "";
      return `<td${cls}>${cell}</td>`;
    });
    return `<tr>${cells.join("")}</tr>`;
  }).join("");
  return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

/* ── Filter chips ───────────────────────────────────────────── */
export function filterChips(sid, rows, key, activeVal) {
  const vals = [...new Set((rows || []).map(r => r[key]).filter(Boolean))].sort();
  if (vals.length < 2) return "";
  const all = `<button class="chip${!activeVal ? " active" : ""}" onclick="window.setFilter(${jsq(sid)},${jsq(key)},${jsq("")})">all</button>`;
  const chips = vals.map(v => {
    const act = activeVal === v ? " active" : "";
    return `<button class="chip${act}" onclick="window.setFilter(${jsq(sid)},${jsq(key)},${jsq(v)})">${esc(v)}</button>`;
  });
  return `<div class="filter-row">${all}${chips.join("")}</div>`;
}

/* ── Asset add form: one input, IP *or* domain, live type hint ── */
function _assetAddForm() {
  return `<div class="asset-add">
    <div class="asset-add-row">
      <input id="tgt-new" type="text" placeholder="IP (es. 8.8.8.8) o dominio (es. example.com)…"
        class="tgt-input" oninput="window.hintTarget(this.value)"
        onkeydown="if(event.key==='Enter')window.addTarget()">
      <span id="tgt-kind" class="asset-kind c-dim"></span>
      <button class="tb-btn" onclick="window.addTarget()">+ Add</button>
    </div>
    <div class="asset-add-row asset-ie-row">
      <button class="tb-btn asset-ie-btn" onclick="window.exportTargets()" title="Download assets as JSON">⬇ Export JSON</button>
      <button class="tb-btn asset-ie-btn" onclick="window.importTargets()" title="Upload a JSON asset list">⬆ Import JSON</button>
      <span class="c-dim" style="font-size:10px">import/export migra la lista su altre postazioni</span>
    </div>
  </div>`;
}

/* ── Intel widget (assets cross-source view) ────────────────── */
export function intelWidget(data, readonly) {
  const rows = (data && data.rows) || [];

  function _risk(risk, ports, vulns) {
    if (!risk || risk === "—") return `<span class="muted">—</span>`;
    const meta = [ports !== "—" ? ports + "p" : "", vulns !== "—" ? vulns + "v" : ""].filter(Boolean).join(" ");
    return `${badge(risk)}<span class="c-dim" style="font-size:10px;margin-left:4px">${esc(meta)}</span>`;
  }

  let h = "";
  if (!rows.length) {
    h += `<div class="empty-note">No assets yet — add an IP or domain below.</div>`;
  } else {
    h += `<table><thead><tr>
      <th>Asset</th><th>DNS</th><th>Country/Org</th><th>Shodan</th><th>Netlas</th><th>Worst</th>
      ${readonly ? "" : "<th></th>"}
    </tr></thead><tbody>`;
    for (const r of rows) {
      const risk = String(r.max_risk || "").toLowerCase();
      const rc = (risk === "critical" || risk === "high") ? "r-crit" : risk === "medium" ? "r-high" : "";
      const geo = [r.country, r.org].filter(v => v && v !== "—").join(" · ");
      h += `<tr class="${rc}">
        <td class="c-mono">${esc(r.asset)} <span class="c-dim" style="font-size:10px">${esc(r.type||"")}</span></td>
        <td class="c-dim">${esc(r.dns && r.dns !== "self (ip)" ? r.dns : "—")}</td>
        <td class="c-dim c-trunc" title="${esc(geo)}">${esc(geo||"—")}</td>
        <td>${_risk(r.shodan_risk, r.shodan_ports, r.shodan_vulns)}</td>
        <td>${_risk(r.netlas_risk, r.netlas_ports, r.netlas_vulns)}</td>
        <td>${r.max_risk && r.max_risk !== "—" ? badge(r.max_risk) : '<span class="muted">—</span>'}</td>
        ${readonly ? "" : `<td><button class="asset-rm" title="remove ${esc(r.asset)}"
          onclick="window.rmTarget(${jsq(r.asset)})">✕</button></td>`}
      </tr>`;
    }
    h += `</tbody></table>`;
  }

  // The add form is always shown when not readonly — even on an empty list.
  if (!readonly) h += _assetAddForm();
  return h;
}

/* ── Atera widget: last 5 alerts + open tickets ─────────────── */
export function ateraWidget(data) {
  if (!data) return `<div class="empty-note">No Atera data yet.</div>`;
  const alerts  = (data.alert_rows || []).slice(0, 5);
  const tickets = data.ticket_rows || [];

  let h = `<div class="kv-grid">
    <div class="kv-item"><div class="kv-v">${esc(data.tickets_open ?? 0)}</div><div class="kv-k">open tickets</div></div>
    <div class="kv-item"><div class="kv-v">${esc(data.tickets_triage ?? 0)}</div><div class="kv-k">triage</div></div>
    <div class="kv-item"><div class="kv-v">${esc(data.alerts_total ?? 0)}</div><div class="kv-k">alerts</div></div>
    <div class="kv-item"><div class="kv-v">${esc(data.servers_offline ?? 0)}</div><div class="kv-k">servers offline</div></div>
  </div>`;

  h += `<div class="sect-sub">Recent alerts (last 5)</div>`;
  if (!alerts.length) {
    h += `<div class="empty-note">No open alerts.</div>`;
  } else {
    h += `<table><thead><tr><th>Severity</th><th>Alert</th><th>Device</th><th>When</th></tr></thead><tbody>`;
    for (const a of alerts) {
      h += `<tr><td>${badge(a.severity || "—")}</td><td>${esc(a.title)}</td>
        <td class="c-dim">${esc(a.device || "")}</td><td class="c-mono c-dim">${esc(a.created || "")}</td></tr>`;
    }
    h += `</tbody></table>`;
  }

  h += `<div class="sect-sub">Open tickets</div>`;
  if (!tickets.length) {
    h += `<div class="empty-note">No open tickets.</div>`;
  } else {
    h += `<table><thead><tr><th>Ticket</th><th>Customer</th><th>Priority</th><th>Created</th></tr></thead><tbody>`;
    for (const t of tickets.slice(0, 15)) {
      h += `<tr><td>${esc(t.title)}</td><td class="c-dim">${esc(t.customer || "")}</td>
        <td>${badge(t.priority || "—")}</td><td class="c-mono c-dim">${esc(t.created || "")}</td></tr>`;
    }
    h += `</tbody></table>`;
  }
  return h;
}

/* ── Provider bar widget (cloud_status) ─────────────────────── */
export function providerBar(data) {
  const rows = (data && data.rows) || [];
  if (!rows.length) return `<div class="empty-note">No provider data yet.</div>`;
  return `<div class="pbar">${rows.map(r => {
    const st = r.status || "off";
    const link = r.page ? `href="${esc(r.page)}" target="_blank" rel="noopener"` : "";
    const icon = r.icon ? img(r.icon, "pbar-icon") : "";
    return `<div class="pbar-row">
      ${led(st, false)}
      ${icon}
      <a class="pbar-name" ${link}>${esc(r.provider)}</a>
      <span class="pbar-region c-dim">${esc(r.region||"")}</span>
      ${badge(st)}
      ${r.incidents ? `<span class="pbar-inc">${r.incidents} incident${r.incidents>1?"s":""}</span>` : ""}
      ${r.detail ? `<span class="pbar-detail c-dim c-trunc">${esc(String(r.detail).slice(0,80))}</span>` : ""}
    </div>`;
  }).join("")}</div>`;
}

/* ── BGP / IAAS bars — shared helpers ───────────────────────── */
const _SEV_RANK = { ok: 0, info: 1, source_error: 1, warning: 2, critical: 3 };

function _dedup(rows) {
  // One entry per operator name, keeping worst severity.
  const map = {};
  for (const r of rows) {
    const n = r.target;
    if (!map[n] || (_SEV_RANK[r.severity] || 0) > (_SEV_RANK[map[n].severity] || 0))
      map[n] = r;
  }
  return Object.values(map);
}

function _barChip(r, navTarget) {
  const st = (_SEV_RANK[r.severity] != null) ? r.severity : "off";
  const title = `${r.target} — ${r.severity}`;
  const inner = `${led(st, false)}<span class="bgp-name">${esc(r.target)}</span>`;
  if (navTarget) {
    return `<button class="bgp-spia bgp-spia-${esc(st)}" title="${esc(title)}"
      onclick="window.navigate(${jsq(navTarget)})">${inner}</button>`;
  }
  if (r.status_url) {
    return `<a class="bgp-spia bgp-spia-${esc(st)}" href="${esc(r.status_url)}"
      target="_blank" rel="noopener" title="${esc(title)}">${inner}</a>`;
  }
  return `<span class="bgp-spia bgp-spia-${esc(st)}" title="${esc(title)}">${inner}</span>`;
}

/* BGP-IT bar: ISP backbone operators only → click navigates to bgp-it page */
export function bgpBar() {
  const rows = ((STATE.data["bgp"] || {}).data || {}).rows || [];
  const isps = rows.filter(r => r.role === "isp" || !r.role);
  if (!isps.length) return "";
  return _dedup(isps).map(r => _barChip(r, "bgp-it")).join("");
}

/* IAAS-IT footer bar: datacenter + IXP → click goes to their status page */
export function iaasBar() {
  const rows = ((STATE.data["bgp"] || {}).data || {}).rows || [];
  const dc = rows.filter(r => r.role === "datacenter" || r.role === "ixp");
  if (!dc.length) return "";
  return _dedup(dc).map(r => _barChip(r, null)).join("");
}

/* BGP-IT full status page: grouped by operator, columns with tech detail */
export function bgpItPage() {
  const bgpData = (STATE.data["bgp"] || {}).data;
  if (!bgpData) return `<div class="empty-note">No BGP data yet.</div>`;
  const rows = (bgpData.rows || []).filter(r => r.role === "isp" || !r.role);
  if (!rows.length) return `<div class="empty-note">No BGP ISP data.</div>`;

  // Group by target name
  const groups = {};
  for (const r of rows) {
    if (!groups[r.target]) groups[r.target] = [];
    groups[r.target].push(r);
  }

  const bad = s => ["warning","critical","source_error"].includes(s);
  const problems = Object.values(groups).filter(g =>
    g.some(r => bad(r.severity))).length;

  let h = problems
    ? `<div class="errline">⚠ ${problems} operator${problems > 1 ? "s" : ""} with BGP/RPKI issues</div>`
    : `<div class="ok-note">✓ All monitored Italian backbone operators clean</div>`;

  h += `<table><thead><tr>
    <th>Operator</th><th>ASN</th><th>Severity</th><th>Risk</th>
    <th>Prefixes</th><th>Status Page</th>
  </tr></thead><tbody>`;

  const sorted = Object.entries(groups).sort(([, a], [, b]) => {
    const wa = Math.max(...a.map(r => _SEV_RANK[r.severity] || 0));
    const wb = Math.max(...b.map(r => _SEV_RANK[r.severity] || 0));
    return wb - wa;
  });

  for (const [name, asns] of sorted) {
    const worst = asns.reduce((m, r) =>
      (_SEV_RANK[r.severity] || 0) > (_SEV_RANK[m.severity] || 0) ? r : m);
    const cls = worst.severity === "critical" ? "r-crit" : bad(worst.severity) ? "r-high" : "";
    const statusLink = worst.status_url
      ? `<a href="${esc(worst.status_url)}" target="_blank" rel="noopener" class="ext-link">
           status ↗</a>`
      : `<span class="c-dim">—</span>`;
    const asnList = asns.map(r => `<span class="c-mono c-dim">${esc(r.asn)}</span>`).join(" ");
    h += `<tr class="${cls}">
      <td><strong>${esc(name)}</strong></td>
      <td>${asnList}</td>
      <td>${badge(worst.severity || "—")}</td>
      <td class="c-dim">${esc(worst.risk_score ?? "—")}</td>
      <td class="c-dim">${esc(asns.reduce((s, r) => s + (r.prefixes || 0), 0))}</td>
      <td>${statusLink}</td>
    </tr>`;
  }
  return h + `</tbody></table>`;
}

/* ── Header "spie": L0 control-lights ────────────────────────
   bgp + root render as one light each; cloud_status explodes into one
   light per configured provider (icon + per-provider status). */
function _spia(st, ico, label, title, nav) {
  // Icon-only control light: the name lives in the tooltip, not on screen.
  return `<button class="spia spia-${esc(st)}" title="${esc(title)}" aria-label="${esc(label)}"
      onclick="window.navigate(${jsq(nav)})">
    ${ico ? img(ico, "spia-icon") : ""}
    ${led(st, false)}
  </button>`;
}

export function spie() {
  let out = "";
  for (const id of SPIE) {
    const s = STATE.sources.find(x => x.id === id);
    if (!s) continue;

    if (id === "cloud_status") {
      const provs = ((STATE.data["cloud_status"] || {}).data || {}).rows || [];
      if (!provs.length) {
        out += _spia(sourceStatus(s), (s.schema && s.schema.icon) || "", "cloud", "Cloud Status", "source/cloud_status");
        continue;
      }
      for (const p of provs) {
        const st = p.status === "ok" ? "ok"
                 : p.status === "critical" || p.status === "major" ? "critical"
                 : p.status === "warning" ? "warning"
                 : p.status === "error" ? "source_error"
                 : "config";
        const det = p.incidents ? ` — ${p.incidents} incident(s)` : (p.detail ? ` — ${p.detail}` : "");
        out += _spia(st, p.icon || "", p.provider, `${p.provider} (${p.status})${det}`, "source/cloud_status");
      }
    } else {
      out += _spia(sourceStatus(s), (s.schema && s.schema.icon) || "", s.name, `${s.name} — ${sourceStatus(s)}`, "source/" + id);
    }
  }
  return out;
}

/* ── Essentials: monitored domains (dnsmon) ─────────────────── */
export function domainsWidget(data) {
  const rows = (data && data.rows) || [];
  if (!rows.length) return `<div class="empty-note">No domains under monitoring.</div>`;
  let h = `<table><thead><tr>
    <th>Domain</th><th>Status</th><th>NS OK</th><th>SOA Serial</th><th>ms</th>
  </tr></thead><tbody>`;
  for (const r of rows) {
    const st = String(r.status || "").toLowerCase();
    const cls = (st === "critical") ? "r-crit" : (st === "warning" || st === "diverged") ? "r-high" : "";
    h += `<tr class="${cls}">
      <td class="c-mono">${esc(r.domain)}</td>
      <td>${badge(r.status || "—")}</td>
      <td class="c-dim">${esc(r.ns_ok ?? "—")}</td>
      <td class="c-mono c-dim">${esc(r.serial ?? "—")}</td>
      <td class="c-mono c-dim">${esc(r.latency_ms ?? "—")}</td>
    </tr>`;
  }
  return h + `</tbody></table>`;
}

/* ── Essentials: Italian backbone BGP states (bgp) ──────────── */
export function bgpWidget(data) {
  const rows = (data && data.rows) || [];
  if (!rows.length) return `<div class="empty-note">No BGP assessments yet.</div>`;
  const bad = r => ["warning", "critical", "source_error"].includes(String(r.severity).toLowerCase());
  const problems = rows.filter(bad);
  const ranked = [...problems, ...rows.filter(r => !bad(r))];

  const lead = problems.length
    ? `<div class="errline">⚠ ${problems.length} operator${problems.length > 1 ? "s" : ""} with BGP/RPKI issues</div>`
    : `<div class="ok-note">✓ All monitored Italian operators clean (RPKI/IRR/visibility)</div>`;

  let h = lead + `<table><thead><tr>
    <th>Operator</th><th>ASN</th><th>Group</th><th>Severity</th><th>Risk</th><th>Prefixes</th>
  </tr></thead><tbody>`;
  for (const r of ranked) {
    const cls = String(r.severity).toLowerCase() === "critical" ? "r-crit"
              : bad(r) ? "r-high" : "";
    h += `<tr class="${cls}">
      <td>${esc(r.target)}</td>
      <td class="c-mono">${esc(r.asn)}</td>
      <td class="c-dim">${esc(r.group || "—")}</td>
      <td>${badge(r.severity || "—")}</td>
      <td class="c-dim">${esc(r.risk_score ?? "—")}</td>
      <td class="c-dim">${esc(r.prefixes ?? "—")}</td>
    </tr>`;
  }
  return h + `</tbody></table>`;
}

/* ── Substatus: how-it-works, redacted config, recent log ───── */
export function logicBlock(detail) {
  const txt = (detail && detail.logic) || "";
  const it  = (detail && detail.help_it) || "";
  let h = "";
  if (txt) h += `<div class="sect-title">How it works</div>
    <pre class="logic-pre">${esc(txt)}</pre>`;
  if (it) h += `<div class="sect-title">Come funziona e configurazione 🇮🇹</div>
    <pre class="logic-pre logic-it">${esc(it)}</pre>`;
  return h;
}

export function configBlock(detail) {
  const cfg = detail && detail.config;
  if (!cfg || !Object.keys(cfg).length)
    return `<div class="sect-title">Config</div>
      <div class="empty-note">No config block — running on built-in defaults.</div>`;
  return `<div class="sect-title">Config <span class="c-dim">(secrets masked)</span></div>
    <pre class="cfg-pre">${esc(JSON.stringify(cfg, null, 2))}</pre>`;
}

export function eventsBlock(detail) {
  const evs = (detail && detail.events) || [];
  if (!evs.length) return `<div class="sect-title">Last significant log</div>
    <div class="empty-note">No events recorded yet.</div>`;
  const rows = evs.map(e => {
    const when = e.ts ? new Date(e.ts * 1000).toLocaleString() : "—";
    const ev   = String(e.event || "");
    const cls  = ev.includes("fail") ? "lg-err" : ev.includes("ok") ? "lg-ok" : "";
    return `<div class="lg-row ${cls}">
      <span class="lg-ts c-mono c-dim">${esc(when)}</span>
      <span class="lg-ev">${esc(ev)}</span>
      <span class="lg-detail c-dim c-trunc">${esc(e.error || "")}</span>
    </div>`;
  }).join("");
  return `<div class="sect-title">Last significant log</div>
    <div class="lg-box">${rows}</div>`;
}

/* ── L0 tool runner (allowlisted, browser-driven diagnostics) ── */
export function toolRunner(sid, detail) {
  const decls = (detail && detail.tools) || [];
  if (!decls.length) return "";
  const avail = new Map(STATE.tools.map(t => [t.name, t]));

  const rows = decls.map((d, i) => {
    const meta = avail.get(d.tool) || { available: false, extra: null, hint: "" };
    const key  = `${sid}:${i}`;
    const out  = STATE.toolOut[key];
    const disabled = !meta.available;
    const extraInput = meta.extra
      ? `<input class="tr-extra" id="tr-extra-${esc(sid)}-${i}" value="${esc(d.extra || "")}"
           placeholder="${esc(meta.extra)}" ${disabled ? "disabled" : ""}>`
      : "";
    const note = !meta.available ? `${esc(d.tool)} not installed` : esc(meta.hint || "");
    let outHtml = "";
    if (out) {
      const cls = out.ok ? "tr-ok" : "tr-fail";
      const body = out.output || out.error || "(no output)";
      const cmd = out.cmd ? `<div class="tr-cmd c-mono c-dim">$ ${esc(out.cmd)}</div>` : "";
      outHtml = `<div class="tr-out ${cls}">${cmd}<pre>${esc(body)}</pre></div>`;
    }
    return `<div class="tr-row">
      <div class="tr-line">
        <span class="tr-tool">${esc(d.label || d.tool)}</span>
        <input class="tr-arg" id="tr-arg-${esc(sid)}-${i}" value="${esc(d.arg || "")}"
          placeholder="target" ${disabled ? "disabled" : ""}>
        ${extraInput}
        <button class="tb-btn tr-run" ${disabled ? "disabled" : ""}
          onclick="window.runTool(${jsq(sid)},${i},${jsq(d.tool)})">▶ run</button>
      </div>
      <div class="tr-note c-dim">${note}</div>
      ${outHtml}
    </div>`;
  }).join("");

  return `<div class="sect-title">Tools <span class="c-dim">(read-only diagnostics)</span></div>
    <div class="tr-box">${rows}</div>`;
}

/* ── Feed items widget ──────────────────────────────────────── */
export function feedsWidget(sid, data, limit) {
  const rows = (data && data.rows) || [];
  const show = limit ? rows.slice(0, limit) : rows;
  if (!show.length) return `<div class="empty-note">No feed items yet.</div>`;
  return show.map(item => {
    const title = item.link
      ? `<a href="${esc(item.link)}" target="_blank" rel="noopener">${esc(item.title)}</a>`
      : esc(item.title);
    return `<div class="fi">
      <div class="fi-title">${title}</div>
      <div class="fi-meta">
        ${item.category ? badge(item.category) : ""}
        <span class="fi-src c-dim">${esc(item.source||"")}</span>
        <span class="fi-time c-dim">${esc(item.published||"")}</span>
      </div>
    </div>`;
  }).join("");
}
