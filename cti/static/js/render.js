/* render.js — DOM mutation. Reads STATE, calls components, writes innerHTML. */
import { STATE, META, CAT_ORDER, GRID_HIDDEN } from './state.js';
import {
  esc, jsq, fmtAge, img, val,
  dotCls, statusClass, catOf, srcIcon, panelStatus,
  panelHtml, kpiStrip, threatScore, aboutHtml,
} from './components.js';

export function render() {
  renderThreatBadge();
  renderRootmon();
  renderCloudBar();
  renderSidebar();
  renderWorkspace();
  renderFooter();
  _updateTopbar();
}

function _updateTopbar() {
  const online = STATE.sources.filter(s => s.ok).length;
  const total  = STATE.sources.length;

  const sok = document.getElementById("sources-ok");
  if (sok) sok.textContent = `${online}/${total} ok`;

  const st = STATE.status;
  if (st) {
    const up = st.uptime_s || 0;
    const upStr = up < 3600 ? Math.round(up / 60) + "m" : Math.floor(up / 3600) + "h";
    const ul = document.getElementById("uptime-lbl");
    if (ul) { ul.textContent = "up " + upStr; ul.style.display = ""; }
  }
}

export function renderThreatBadge() {
  const el = document.getElementById("threat-badge");
  if (!el) return;
  const t = threatScore();
  el.innerHTML = `<span class="threat-badge thr-${t.lvl}">${esc(t.word)}</span>`;
}

export function renderRootmon() {
  const el = document.getElementById("rootmon-dots");
  if (!el) return;
  const rows = val("rootmon", "rows");
  if (!rows || !rows.length) { el.style.display = "none"; return; }
  el.style.display = "flex";
  let h = `<span class="rmon-lbl">DNS</span>`;
  for (const r of rows) {
    h += `<span class="rmon-dot ${statusClass(r.status)}" title="${esc(r.server + " · " + r.hostname)}"></span>`;
  }
  el.innerHTML = h;
}

export function renderCloudBar() {
  const el = document.getElementById("cloud-bar");
  if (!el) return;
  const rows = val("cloud_status", "rows");
  if (!rows || !rows.length) { el.style.display = "none"; return; }
  el.style.display = "flex";
  let h = `<span class="cbar-lbl">${img("/icons/cloud/icons8-cloud-50.png", "prov-icon")} Cloud</span>`;
  for (const r of rows) {
    const dc    = statusClass(r.status);
    const cpCls = "cp-" + dc.slice(3);
    const icon  = r.icon ? img(r.icon, "prov-icon") : "";
    const inc   = r.incidents ? `<span class="cbar-inc">${r.incidents}⚠</span>` : "";
    const tgt   = r.page
      ? `href="${esc(r.page)}" target="_blank" rel="noopener"`
      : `href="#" onclick="go('cloud_status');return false"`;
    h += `<a ${tgt} class="cbar-pill ${cpCls}" title="${esc((r.detail || r.status || "").slice(0, 80))}">
      <span class="dot ${dc}" style="width:5px;height:5px;flex-shrink:0"></span>
      ${icon}<span class="cbar-name">${esc(r.provider)}</span>${inc}
    </a>`;
  }
  el.innerHTML = h;
}

export function renderSidebar() {
  const el = document.getElementById("nav-list");
  if (!el) return;

  let h = `<a class="nav-item${STATE.view === "overview" ? " active" : ""}" href="#" onclick="showOverview();return false">
    <span class="nav-icon">▦</span>
    <span class="nav-label">Overview</span>
  </a>`;

  for (const cat of CAT_ORDER) {
    const sources = STATE.sources.filter(x => catOf(x) === cat);
    if (!sources.length) continue;
    h += `<div class="nav-group-label"><span class="nav-group-label-text">${esc(cat)}</span></div>`;
    for (const s of sources) {
      const active  = s.id === STATE.view ? " active" : "";
      const age     = fmtAge((STATE.data[s.id] || {}).age_s);
      const icon    = srcIcon(s) ? img(srcIcon(s), "nav-src-icon") : "";
      const st      = panelStatus(s, (STATE.data[s.id] || {}).data);
      const alert   = (st === "crit" || st === "err") ? `<span class="nav-alert">!</span>` : "";
      h += `<a class="nav-item${active}" href="#" onclick="go(${jsq(s.id)});return false">
        <span class="nav-dot ${dotCls(s)}"></span>
        ${icon}
        <span class="nav-label">${esc((s.schema && s.schema.title) || s.name)}</span>
        <span class="nav-age">${esc(age)}</span>
        ${alert}
      </a>`;
    }
  }

  const appName = STATE.ui.app || "OmniCheck Cockpit";
  h += `<div class="nav-bottom">
    <a class="nav-item${STATE.view === "about" ? " active" : ""}" href="#" onclick="go('about');return false">
      <span class="nav-icon" style="font-size:11px">ⓘ</span>
      <span class="nav-label">Runtime Status</span>
    </a>
  </div>`;

  el.innerHTML = h;
}

export function renderWorkspace() {
  const ws      = document.getElementById("workspace");
  const pageHdr = document.getElementById("page-hdr");
  if (!ws) return;

  /* Runtime Status page */
  if (STATE.view === "about") {
    _showPageHdr(
      `<span class="bc-link" onclick="showOverview()">OmniCheck</span><span class="bc-sep">/</span>Runtime Status`,
      "Runtime Status",
      ""
    );
    ws.innerHTML = `<div class="detail-wrap">${aboutHtml()}</div>`;
    return;
  }

  /* Source detail page */
  if (STATE.view !== "overview") {
    const s = STATE.sources.find(x => x.id === STATE.view);
    if (!s) {
      if (pageHdr) pageHdr.style.display = "none";
      ws.innerHTML = `<div class="empty">unknown source</div>`;
      return;
    }
    const m   = META[s.id] || { cat: "OTHER", link: "" };
    const ext = m.link ? `<a class="mast-btn" href="${esc(m.link)}" target="_blank" rel="noopener">↗ Console</a>` : "";
    _showPageHdr(
      `<span class="bc-link" onclick="showOverview()">OmniCheck</span>
       <span class="bc-sep">/</span>${esc(catOf(s))}
       <span class="bc-sep">/</span><span style="color:var(--sub)">${esc((s.schema && s.schema.title) || s.name)}</span>`,
      (s.schema && s.schema.title) || s.name,
      ext
    );
    const p = panelHtml(s, true);
    ws.innerHTML = `<div class="detail-wrap"><div class="panel ${p.cls || ""}">${p.hdr}${p.body}</div></div>`;
    ws.scrollTop = 0;
    return;
  }

  /* Overview */
  if (pageHdr) pageHdr.style.display = "none";

  let html = `<div class="ws-body">` + kpiStrip();

  for (const cat of CAT_ORDER) {
    const sources = STATE.sources.filter(x => catOf(x) === cat && !GRID_HIDDEN.has(x.id));
    if (!sources.length) continue;
    html += `<div class="ws-cat-label">${esc(cat)}</div><div class="ws-grid">`;
    for (const s of sources) {
      const p = panelHtml(s, false);
      html += `<div class="panel click ${p.cls || ""}" onclick="go(${jsq(s.id)})">${p.hdr}${p.body}</div>`;
    }
    html += `</div>`;
  }

  html += `</div>`;
  ws.innerHTML = html;
}

export function renderFooter() {
  const el = document.getElementById("status-footer");
  if (!el) return;

  const online   = STATE.sources.filter(s => s.ok).length;
  const total    = STATE.sources.length;
  const degraded = STATE.sources.filter(s => s.enabled && !s.ok).map(s => (s.schema && s.schema.title) || s.name);
  const off      = STATE.sources.filter(s => !s.enabled).length;
  const crit     = [];

  const bgpCrit = val("bgp", "critical");
  if (bgpCrit && bgpCrit.length) crit.push(`${bgpCrit.length} BGP critical`);
  const cloudDeg = val("cloud_status", "degraded");
  if (cloudDeg) crit.push(`${cloudDeg} cloud degraded`);
  const rFail = val("rootmon", "fail");
  if (rFail) crit.push(`${rFail} root DNS failing`);
  const atRisk = val("assets", "at_risk");
  if (atRisk) crit.push(`${atRisk} assets at risk`);

  el.innerHTML =
    `<span class="foot-label">Status</span>`
    + `<span class="foot-item"><b>${online}/${total}</b> online</span>`
    + `<span class="foot-item">${degraded.length} degraded${degraded.length ? ": " + esc(degraded.join(", ")) : ""}</span>`
    + `<span class="foot-item">${off} off</span>`
    + (crit.length
      ? `<span class="foot-item" style="color:var(--magenta)">⚠ ${esc(crit.join(" · "))}</span>`
      : `<span class="foot-item" style="color:var(--green)">no critical signals</span>`);
}

function _showPageHdr(breadcrumbHtml, title, actionsHtml) {
  const hdr = document.getElementById("page-hdr");
  if (!hdr) return;
  hdr.style.display = "";
  document.getElementById("page-breadcrumb").innerHTML = breadcrumbHtml;
  document.getElementById("page-title").textContent = title;
  document.getElementById("page-actions").innerHTML = actionsHtml;
}
