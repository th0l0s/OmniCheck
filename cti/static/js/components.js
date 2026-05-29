/* components.js — pure HTML builders. Input → HTML string. No DOM mutation. */
import { STATE, META } from './state.js';

/* ── escape helpers ─────────────────────────────────────────── */
export function esc(s) {
  return String(s == null ? "" : s)
    .replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

/* builds a safe single-quoted JS string literal for use inside onclick="…" */
export function jsq(s) {
  return esc("'" + String(s == null ? "" : s).replace(/\\/g, "\\\\").replace(/'/g, "\\'") + "'");
}

export function badge(v) {
  const c = String(v).toLowerCase().replace(/[^a-z0-9_]/g, "_");
  return `<span class="badge b-${c}">${esc(v)}</span>`;
}

export function fmtAge(s) {
  if (s == null) return "—";
  if (s < 60) return Math.round(s) + "s";
  if (s < 3600) return Math.round(s / 60) + "m";
  return Math.round(s / 3600) + "h";
}

export function img(path, cls) {
  if (!path || !String(path).startsWith("/icons")) return "";
  return `<img class="${cls}" src="${esc(path)}" onerror="this.style.display='none'" alt="">`;
}

export function val(id, k) {
  const d = STATE.data[id];
  return d && d.data ? d.data[k] : undefined;
}

/* ── status classifiers ─────────────────────────────────────── */
export function dotCls(s) {
  if (!s.enabled) return "st-off";
  if (s.ok) return "st-ok";
  return s.error ? "st-err" : "st-warn";
}

export function statusClass(v) {
  const s = String(v || "").toLowerCase();
  return (s === "critical" || s === "error" || s === "diverged") ? "st-err"
    : s === "warning" ? "st-warn"
    : s === "ok" ? "st-ok"
    : "st-off";
}

function riskClass(v) {
  const r = String(v || "").toLowerCase();
  return (r === "critical" || r === "high") ? "st-err"
    : r === "medium" ? "st-warn"
    : (r === "low" || r === "clean") ? "st-ok"
    : "st-off";
}

export function catOf(s) {
  const cat = (s.schema && s.schema.category) || (META[s.id] || {}).cat || "OTHER";
  return String(cat).toUpperCase();
}

export function srcIcon(s) {
  return (s.schema && s.schema.icon) || "";
}

/* ── panel status (drives border color + nav dot) ───────────── */
export function panelStatus(s, data) {
  if (!s.enabled) return "off";
  if (!s.ok) return s.last_error ? "err" : "warn";
  if (!data) return "warn";
  const ar = data.at_risk, fail = data.fail;
  if (typeof ar === "number" && ar > 0) return ar > 2 ? "crit" : "warn";
  if (typeof fail === "number" && fail > 0) return fail > 3 ? "crit" : "warn";
  return "ok";
}

function isPanelCollapsed(id) {
  return localStorage.getItem("pcol_" + id) === "1";
}

/* ── table builder ──────────────────────────────────────────── */
export function tableHtml(t, data, full, filterKey, filterVal) {
  let rows = data[t.rows_key] || [];
  if (filterKey && filterVal) rows = rows.filter(r => r[filterKey] === filterVal);
  const PREV = 4;
  const show = full ? rows : rows.slice(0, PREV);
  let h = `<table><thead><tr>${t.columns.map(c => `<th>${esc(c.label)}</th>`).join("")}</tr></thead><tbody>`;
  if (!show.length) {
    h += `<tr><td colspan="${t.columns.length}" class="empty">no rows</td></tr>`;
  }
  for (const r of show) {
    h += "<tr>" + t.columns.map(c => {
      let v = r[c.key]; if (v == null) v = "";
      const ic = c.icon_key && r[c.icon_key] ? img(r[c.icon_key], "prov-icon") : "";
      let cell;
      if (c.badge) {
        cell = ic + badge(v);
      } else {
        let txt = (c.link_key && r[c.link_key])
          ? `<a href="${esc(r[c.link_key])}" target="_blank" rel="noopener">${esc(v)}</a>`
          : esc(v);
        cell = ic ? `<span style="display:inline-flex;align-items:center;gap:6px">${ic}${txt}</span>` : txt;
      }
      const cls = c.mono ? " class=\"c-mono\"" : c.numeric ? " class=\"c-dim\"" : "";
      return `<td${cls}>${cell}</td>`;
    }).join("") + "</tr>";
  }
  h += `</tbody></table>`;
  if (!full && rows.length > PREV) {
    h += `<div class="more-row">+${rows.length - PREV} more — open panel →</div>`;
  }
  return h;
}

/* ── domain filter chips ────────────────────────────────────── */
function domainFilterChips(sid, allRows, filterKey) {
  const active = (STATE.domainFilters[sid] || {}).val;
  const vals = [...new Set(allRows.map(r => r[filterKey]).filter(Boolean))].sort();
  if (vals.length <= 1) return "";
  return `<div class="filter-row"><span class="filter-label">Domain</span>`
    + `<span role="button" tabindex="0" class="chip${!active ? " active" : ""}" onclick="setDomFilter(${jsq(sid)},null)">All</span>`
    + vals.map(v =>
        `<span role="button" tabindex="0" class="chip${active === v ? " active" : ""}" onclick="setDomFilter(${jsq(sid)},${jsq(v)})">${esc(v)}</span>`
      ).join("")
    + `</div>`;
}

/* ── feeds widget (news_feed + acn merged view) ─────────────── */
function feedsWidget(sid, data, full) {
  const rows = (data && data.rows) || [];
  const ff = STATE.feedFilters[sid] || {};
  let filtered = rows;
  if (ff.type) filtered = filtered.filter(r => r.type === ff.type);
  if (ff.cat) filtered = filtered.filter(r => r.category === ff.cat);

  const types = [...new Set(rows.map(r => r.type).filter(Boolean))].sort();
  const cats = [...new Set(rows.map(r => r.category).filter(Boolean))].sort();
  let chips = "";

  if (full) {
    if (types.length > 1) {
      chips += `<div class="filter-row"><span class="filter-label">Type</span>`
        + `<span role="button" tabindex="0" class="chip${!ff.type ? " active" : ""}" onclick="setFeedFilter(${jsq(sid)},'type',null)">All</span>`
        + types.map(t => `<span role="button" tabindex="0" class="chip${ff.type === t ? " active" : ""}" onclick="setFeedFilter(${jsq(sid)},'type',${jsq(t)})">${esc(t)}</span>`).join("")
        + `</div>`;
    }
    if (cats.length > 1) {
      chips += `<div class="filter-row"><span class="filter-label">Category</span>`
        + `<span role="button" tabindex="0" class="chip${!ff.cat ? " active" : ""}" onclick="setFeedFilter(${jsq(sid)},'cat',null)">All</span>`
        + cats.map(c => `<span role="button" tabindex="0" class="chip${ff.cat === c ? " active" : ""}" onclick="setFeedFilter(${jsq(sid)},'cat',${jsq(c)})">${esc(c.replace(/_/g, " "))}</span>`).join("")
        + `</div>`;
    }
  } else if (cats.length > 1) {
    chips += `<div class="filter-row" style="padding:4px var(--s3)"><span class="filter-label">Cat</span>`
      + `<span role="button" tabindex="0" class="chip${!ff.cat ? " active" : ""}" onclick="event.stopPropagation();setFeedFilter(${jsq(sid)},'cat',null)">All</span>`
      + cats.map(c => `<span role="button" tabindex="0" class="chip${ff.cat === c ? " active" : ""}" onclick="event.stopPropagation();setFeedFilter(${jsq(sid)},'cat',${jsq(c)})">${esc(c.replace(/_/g, " "))}</span>`).join("")
      + `</div>`;
  }

  const PREV = 4;
  const show = full ? filtered : filtered.slice(0, PREV);
  if (!show.length) return chips + `<div class="fi-empty">no items match filters</div>`;

  let h = chips;
  for (const item of show) {
    const typeClr = item.type === "misp" ? "var(--magenta)"
      : item.type === "advisory" ? "var(--amber)"
      : "var(--cyan)";
    const catIcon = item.category_icon ? img(item.category_icon, "kpi-icon") : "";
    const titleEl = item.link
      ? `<a href="${esc(item.link)}" target="_blank" rel="noopener">${esc(item.title)}</a>`
      : esc(item.title);
    const extra = item.extra
      ? `<span style="font-size:9px;color:var(--magenta);margin-left:6px">${esc(item.extra)}</span>`
      : "";
    const tlBadge = item.threat_level ? badge(item.threat_level) : "";
    h += `<div class="fi">
      <div class="fi-title">${titleEl}${extra}</div>
      <div class="fi-meta">
        <span style="font-size:9px;font-family:var(--mono);font-weight:700;color:${typeClr}">${esc(item.type)}</span>
        ${catIcon}<span class="fi-src">${esc(item.source)}</span>
        ${tlBadge}<span class="fi-time">${esc(item.published || "")}</span>
      </div>
    </div>`;
  }
  if (!full && filtered.length > PREV) h += `<div class="more-row">+${filtered.length - PREV} more — open →</div>`;
  return h;
}

/* ── intel widget (assets cross-source view) ────────────────── */
function intelWidget(data, full) {
  const rows = (data && data.rows) || [];
  const show = full ? rows : rows.slice(0, 5);

  function engCell(risk, ports, vulns) {
    if (!risk || risk === "—") return `<span class="muted">—</span>`;
    return `<div class="eng-cell">${badge(risk)}<span class="eng-meta">${ports !== "—" ? ports + "p" : ""} ${vulns !== "—" ? vulns + "v" : ""}</span></div>`;
  }

  let h = "";
  if (show.length) {
    h += `<table><thead><tr><th>Asset</th><th>DNS</th><th>Country / Org</th><th>Shodan</th><th>Netlas</th><th>Max</th></tr></thead><tbody>`;
    for (const r of show) {
      const risk = String(r.max_risk || "").toLowerCase();
      const dc = riskClass(risk);
      const rowCls = risk === "critical" ? "r-crit" : risk === "high" ? "r-high" : "";
      const dnsVal = (r.dns && r.dns !== "—" && r.dns !== "self (ip)") ? r.dns : "—";
      const typeClr = r.type === "ip" ? "var(--cyan)" : "var(--blue)";
      const geo = [r.country, r.org].filter(v => v && v !== "—").join(" · ");
      const fsTitle = r.first_seen ? "Monitoring since: " + r.first_seen : "";
      h += `<tr class="${rowCls}" title="${esc(fsTitle)}">
        <td><span class="dot dot-sm ${dc}"></span><span class="c-mono">${esc(r.asset)}</span><span class="asset-type" style="color:${typeClr}">${esc(r.type || "")}</span></td>
        <td class="c-dim">${esc(dnsVal)}</td>
        <td class="c-dim c-trunc geo-cell" title="${esc(geo)}">${esc(geo || "—")}</td>
        <td>${engCell(r.shodan_risk, r.shodan_ports, r.shodan_vulns)}</td>
        <td>${engCell(r.netlas_risk, r.netlas_ports, r.netlas_vulns)}</td>
        <td>${r.max_risk && r.max_risk !== "—" ? badge(r.max_risk) : `<span class="muted">—</span>`}</td>
      </tr>`;
    }
    h += `</tbody></table>`;
    if (!full && rows.length > 8) h += `<div class="more-row">+${rows.length - 8} more — open →</div>`;
  } else if (!full) {
    h = `<div class="intel-empty"><strong>no targets yet</strong>add IPs/domains via assets.yaml</div>`;
  }

  if (full) {
    const targets = rows.map(r => r.asset);
    h += `<div class="sect-title">Manage Targets</div><div style="padding:8px 16px 14px">`;
    if (STATE.ui.readonly) {
      h += `<div class="locked-note"><span class="lock-icon">🔒</span>
        <div class="lock-body">Target management requires <code>CTI_API_KEY</code> on the server.
        Manage targets via <code>assets.yaml</code> or the API directly.</div></div>`;
    } else {
      if (targets.length) {
        h += `<div style="margin-bottom:10px">`;
        for (const t of targets) {
          h += `<div style="display:flex;align-items:center;gap:6px;padding:3px 0;font-family:var(--mono);font-size:11px;border-bottom:1px solid var(--border)">
            <span style="color:var(--text);flex:1">${esc(t)}</span>
            <button onclick="rmTarget(${jsq(t)})" style="background:none;border:none;color:var(--dim-text);cursor:pointer;font-size:14px;padding:0 4px" title="remove" aria-label="remove ${esc(t)}">×</button>
          </div>`;
        }
        h += `</div>`;
      } else {
        h += `<div style="margin-bottom:10px;font-family:var(--mono);font-size:11px;color:var(--dim-text)">no targets configured yet</div>`;
      }
      h += `<div style="display:flex;gap:6px">
        <input id="tgt-new" type="text" placeholder="IP or domain to monitor…"
          style="flex:1;background:var(--surface);border:1px solid var(--border);color:var(--text);font-family:var(--mono);font-size:11px;padding:5px 9px;border-radius:3px;outline:none"
          onkeydown="if(event.key==='Enter')addTarget()">
        <button class="mast-btn" onclick="addTarget()">+ Add</button>
      </div>`;
    }
    h += `</div>`;
  }
  return h;
}

/* ── provider bar widget (cloud_status) ─────────────────────── */
function providerBar(data) {
  const rows = (data && data.rows) || [];
  if (!rows.length) return `<div class="intel-empty"><strong>no provider data yet</strong></div>`;
  let h = `<div class="intel-target-list">`;
  for (const r of rows) {
    const dc = statusClass(r.status);
    const icon = r.icon ? img(r.icon, "prov-icon") : "";
    const name = r.page
      ? `<a href="${esc(r.page)}" target="_blank" rel="noopener" style="color:inherit;text-decoration:none">${esc(r.provider)}</a>`
      : esc(r.provider);
    const inc = r.incidents
      ? ` <span class="intel-target-alert">${r.incidents} incident${r.incidents > 1 ? "s" : ""}</span>`
      : "";
    const detail = r.detail
      ? `<span class="intel-target-detail">${esc(String(r.detail).slice(0, 80))}</span>`
      : "";
    h += `<div class="intel-target">
      <span class="dot ${dc}" style="width:7px;height:7px"></span>
      ${icon}
      <span class="intel-target-addr">${name}:</span>
      <span class="intel-target-type">${esc(r.region || "")}</span>
      <div class="intel-target-meta">${badge(r.status || "—")}${inc}${detail}</div>
    </div>`;
  }
  h += `</div>`;
  return h;
}

/* ── threat score (drives KPI strip + masthead badge) ─────── */
export function threatScore() {
  const atRisk  = val("assets", "at_risk") || 0;
  const rFail   = val("rootmon", "fail")   || 0;
  const bgpCrit = (val("bgp", "critical")  || []).length;
  const cloudDeg = val("cloud_status", "degraded") || 0;
  const score = atRisk + rFail + bgpCrit;
  const [lvl, word] = score === 0 ? ["ok", "NOMINAL"]
    : score <= 3 ? ["warn", "ELEVATED"]
    : ["crit", "CRITICAL"];
  return { score, lvl, word, atRisk, rFail, bgpCrit, cloudDeg };
}

/* ── KPI strip (overview panorama) ─────────────────────────── */
export function kpiStrip() {
  const t = threatScore();
  const online = STATE.sources.filter(s => s.ok).length;
  const total  = STATE.sources.length;
  const has    = id => STATE.sources.some(s => s.id === id);
  const sev    = (n, w = 1, c = 4) => n >= c ? "crit" : n >= w ? "warn" : "ok";

  const critCount = STATE.sources.filter(s => {
    const d = (STATE.data[s.id] || {}).data;
    return panelStatus(s, d) === "crit";
  }).length;

  const warnCount = STATE.sources.filter(s => {
    const d = (STATE.data[s.id] || {}).data;
    return panelStatus(s, d) === "warn";
  }).length;

  const staleCount = STATE.sources.filter(s => {
    const age = (STATE.data[s.id] || {}).age_s;
    return s.enabled && age != null && age > s.interval * 2;
  }).length;

  const runtimeErrors = STATE.status ? (STATE.status.runtime_errors || []).length : 0;

  const tiles = [
    ["__overview", sev(total - online, 1, 3), `${online}/${total}`, "sources online"],
    ["__threat",   t.lvl,                     t.word,              "global status"],
    ["__crit",     sev(critCount, 1, 1),       critCount,           "critical findings"],
    ["__warn",     sev(warnCount, 1, 5),       warnCount,           "warnings"],
    ["__stale",    sev(staleCount, 1, 3),      staleCount,          "stale sources"],
    ["__errors",   sev(runtimeErrors, 1, 3),   runtimeErrors,       "runtime errors"],
  ];

  if (has("assets"))       tiles.push(["assets",       sev(t.atRisk, 1, 3),  t.atRisk,  "assets at risk"]);
  if (has("rootmon"))      tiles.push(["rootmon",      sev(t.rFail, 1, 4),   t.rFail,   "root DNS failing"]);
  if (has("bgp"))          tiles.push(["bgp",          sev(t.bgpCrit, 1, 1), t.bgpCrit, "BGP critical"]);
  if (has("cloud_status")) tiles.push(["cloud_status", sev(t.cloudDeg, 1, 3),t.cloudDeg,"cloud degraded"]);

  const cells = tiles.map(([id, lvl, v, label]) => {
    const onclick = id === "__threat" ? "goToProblem()"
      : id.startsWith("__") ? "showOverview()"
      : `go(${jsq(id)})`;
    return `<a class="kpi k-${lvl}" href="#" onclick="${onclick};return false">
      <div class="kpi-v">${esc(v)}</div><div class="kpi-l">${esc(label)}</div></a>`;
  }).join("");

  return `<div class="kpi-strip">${cells}</div>`;
}

/* ── panel builder ──────────────────────────────────────────── */
export function panelHtml(s, full) {
  const sc      = s.schema || {};
  const m       = META[s.id] || { cat: "OTHER", link: "" };
  const payload = STATE.data[s.id] || {};
  const data    = payload.data;
  const ext     = !full && m.link
    ? `<a href="${esc(m.link)}" target="_blank" rel="noopener" onclick="event.stopPropagation()" title="console">↗</a>`
    : "";
  const collapsed = !full && isPanelCollapsed(s.id);
  const colBtn  = !full
    ? `<button class="pcol-btn" onclick="togglePanel(${jsq(s.id)});event.stopPropagation()" title="${collapsed ? "expand" : "collapse"}">${collapsed ? "▶" : "▼"}</button>`
    : "";

  const hdr = `<div class="panel-hdr">
    <div class="panel-hdr-l">
      <span class="dot ${dotCls(s)}"></span>
      ${img(srcIcon(s), "panel-icon")}
      <span class="panel-title">${esc(sc.title || s.name)}</span>
      <span class="panel-pill">${esc(catOf(s))}</span>
    </div>
    <div class="panel-hdr-r">
      ${full ? `every ${esc(s.interval)}s · age ${fmtAge(payload.age_s)}` : fmtAge(payload.age_s)}
      ${ext}${colBtn}
    </div>
  </div>`;

  const st = panelStatus(s, data);
  if (collapsed) return { hdr, body: "", cls: `s-${st} collapsed` };

  let body = "";

  if (!s.enabled) {
    const reqs = s.requires || [];
    if (reqs.length && s.error && s.error.includes("missing config")) {
      body = `<div class="locked-note"><span class="lock-icon">🔒</span>
        <div class="lock-body">Requires credentials — set in <code>config.yaml</code> under <code>sources.${esc(s.id)}</code>:<br>
        ${reqs.map(k => `<span class="lock-key">${esc(k)}</span>`).join(" ")}</div></div>`;
    } else {
      body = `<div class="panel-body"><div class="offline-note">OFF — ${esc(s.error || "disabled")}. Configure in config.yaml to enable.</div></div>`;
    }
  } else if (!data) {
    body = `<div class="panel-body"><div class="errline">${esc(payload.error || s.error || "no data yet")}</div></div>`;
  } else {
    const keys = sc.summary_keys || [];
    const kvWrap = keys.length
      ? `<div class="panel-body pov-kv"><div class="kv-grid">${keys.map(k => {
          const v = data[k]; const vs = v == null ? "—" : v;
          return `<div class="kv-item"><div class="kv-v">${esc(vs)}</div><div class="kv-k">${esc(k.replace(/_/g, " "))}</div></div>`;
        }).join("")}</div></div>`
      : "";

    const domFilter    = full && sc.domain_filter;
    const activeFilter = domFilter ? (STATE.domainFilters[s.id] || {}).val || null : null;
    let filterBar = "";
    let sect = "";

    if (sc.widget === "intel") {
      sect = intelWidget(data, full);
    } else if (sc.widget === "providerbar") {
      sect = providerBar(data);
    } else if (sc.widget === "feeds") {
      sect = feedsWidget(s.id, data, full);
    } else if (sc.sections) {
      if (domFilter) {
        const allVals = new Set();
        for (const se of sc.sections) {
          const fk = se.table && se.table.filter_key;
          if (fk) (data[se.table.rows_key] || []).forEach(r => { if (r[fk]) allVals.add(r[fk]); });
        }
        const vals = [...allVals].sort();
        if (vals.length > 1) {
          filterBar = `<div class="filter-row"><span class="filter-label">Filter</span>`
            + `<span role="button" tabindex="0" class="chip${!activeFilter ? " active" : ""}" onclick="setDomFilter(${jsq(s.id)},null)">All</span>`
            + vals.map(v => `<span role="button" tabindex="0" class="chip${activeFilter === v ? " active" : ""}" onclick="setDomFilter(${jsq(s.id)},${jsq(v)})">${esc(v)}</span>`).join("")
            + `</div>`;
        }
      }
      for (const se of sc.sections) {
        const fk = se.table && se.table.filter_key;
        sect += `<div class="sect-title">${esc(se.title)}</div>`
          + tableHtml(se.table, data, full, fk && activeFilter ? fk : null, activeFilter);
      }
    } else if (sc.table) {
      if (domFilter) {
        const fk = sc.table.filter_key;
        if (fk) filterBar = domainFilterChips(s.id, data[sc.table.rows_key] || [], fk);
      }
      const fk = sc.table.filter_key;
      sect = tableHtml(sc.table, data, full, fk && activeFilter ? fk : null, activeFilter);
    }

    const noWrap = sc.widget === "intel" || sc.widget === "providerbar" || sc.widget === "feeds";
    if (noWrap) {
      body = kvWrap + (filterBar || "") + sect;
    } else if (filterBar) {
      body = kvWrap + filterBar + `<div class="panel-body" style="padding-top:0">${sect}</div>`;
    } else {
      body = kvWrap + `<div class="panel-body">${sect}</div>`;
    }

    if (full) {
      const rawId = "raw_" + s.id.replace(/[^a-z0-9]/g, "_");
      body += `<div class="sect-title" style="cursor:pointer;user-select:none"
          onclick="var el=document.getElementById(${jsq(rawId)});el.style.display=el.style.display==='none'?'block':'none'"
        >// raw JSON ▾</div>
        <div id="${rawId}" style="display:none;padding:0 12px 12px">
          <pre class="raw">${esc(JSON.stringify(data, null, 2))}</pre>
        </div>`;
    }
  }

  const wideWidgets = new Set(["intel", "feeds", "providerbar"]);
  const spanCls = wideWidgets.has(sc.widget) ? " w2" : "";

  return { hdr, body, cls: `s-${st}${spanCls}` };
}

/* ── runtime status page ────────────────────────────────────── */
export function aboutHtml() {
  const st = STATE.status;
  if (!st) return `<div class="empty">status unavailable</div>`;

  const up = st.uptime_s || 0;
  const uptimeStr = up < 3600
    ? Math.round(up / 60) + " min"
    : `${Math.floor(up / 3600)}h ${Math.round((up % 3600) / 60)}m`;

  const info = [
    ["app",      STATE.ui.app || st.app || "OmniCheck Cockpit"],
    ["version",  st.version],
    ["uptime",   uptimeStr],
    ["python",   st.python],
    ["platform", (st.platform || "").split("-").slice(0, 3).join("-")],
    ["bind",     `${st.host}:${st.port}`],
    ["debug",    String(st.debug)],
    ["sources",  `${st.sources_ok}/${st.sources_total} ok`],
  ];

  let h = `<div class="panel">
    <div class="panel-hdr">
      <div class="panel-hdr-l">
        ${img("/icons/security/icons8-cyber-security-1-50.png", "panel-icon")}
        <span class="panel-title">Runtime Status — ${esc(STATE.ui.app || "OmniCheck Cockpit")}</span>
      </div>
      <div class="panel-hdr-r">${esc(st.now)}</div>
    </div>
    <div class="panel-body">
      <div class="kv-grid">
        ${info.map(([k, v]) =>
          `<div class="kv-item"><div class="kv-v" style="font-size:14px">${esc(v)}</div><div class="kv-k">${esc(k)}</div></div>`
        ).join("")}
      </div>`;

  const ci = st.config_issues || [];
  const re = st.runtime_errors || [];

  h += `</div><div class="sect-title">Config Issues (${ci.length})</div>`;
  h += ci.length
    ? `<div class="panel-body">${ci.map(x => `<div class="errline">⚠ <b>${esc(x.source)}</b> — ${esc(x.detail)}</div>`).join("")}</div>`
    : `<div class="panel-body"><div class="offline-note">none — all enabled sources configured</div></div>`;

  h += `<div class="sect-title">Runtime Errors (${re.length})</div>`;
  h += re.length
    ? `<div class="panel-body">${re.map(x => `<div class="errline">✖ <b>${esc(x.source)}</b> — ${esc(x.detail)}</div>`).join("")}</div>`
    : `<div class="panel-body"><div class="offline-note">none — all active sources fetching ok</div></div>`;

  h += `<div class="sect-title">Sources (${st.sources.length})</div>
    <table><thead><tr>
      <th>Source</th><th>State</th><th>Interval</th><th>Last Fetch</th><th>Requires</th><th>Detail</th>
    </tr></thead><tbody>`;
  for (const s of st.sources) {
    const stt = !s.enabled ? "off" : s.ok ? "ok" : "error";
    h += `<tr>
      <td>${esc(s.name)}</td>
      <td>${badge(stt)}</td>
      <td class="c-dim">${esc(s.interval)}s</td>
      <td class="c-dim c-mono">${esc(s.last_fetch || "—")}</td>
      <td class="c-dim">${esc((s.requires || []).join(", ") || "—")}</td>
      <td class="c-dim">${esc(s.error || "")}</td>
    </tr>`;
  }
  h += `</tbody></table></div>`;
  return h;
}
