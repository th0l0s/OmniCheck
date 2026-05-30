/* render.js — DOM mutation. Reads STATE, calls components, writes innerHTML. */
import { STATE, SPIE } from './state.js';
import {
  esc, jsq, fmtAge, badge, led, img,
  monitorCard, summaryCards, tableHtml, filterChips,
  intelWidget, providerBar, feedsWidget,
  sourceStatus, layerOf, kindOf, overviewOf, isConfigured,
  sourcesByLayer, globalStatus, layerLabel,
  spie, bgpBar, logicBlock, configBlock, eventsBlock, toolRunner,
  domainsWidget, bgpWidget, ateraWidget,
} from './components.js';

/* ── Top-level render ───────────────────────────────────────── */
export function render() {
  _topbar();
  _bgpBar();
  _sidebar();
  _content();
}

/* ── Topbar ─────────────────────────────────────────────────── */
function _topbar() {
  const gst = globalStatus();
  const gl = document.getElementById("global-led");
  if (gl) gl.className = `led led-lg led-${gst}`;

  const ok = STATE.sources.filter(s => s.ok).length;
  const tot = STATE.sources.length;
  const sokEl = document.getElementById("sources-ok");
  if (sokEl) sokEl.textContent = `${ok}/${tot} OK`;

  const cdEl = document.getElementById("countdown");
  if (cdEl) cdEl.textContent = `↻ ${STATE.next}s`;

  const spEl = document.getElementById("tb-spie");
  if (spEl) spEl.innerHTML = spie();

  const ipEl = document.getElementById("tb-pubip");
  if (ipEl && STATE.pubip && STATE.pubip !== "—") ipEl.textContent = STATE.pubip;
}

/* ── BGP second toolbar ─────────────────────────────────────── */
function _bgpBar() {
  const bar = document.getElementById("bgp-bar");
  if (!bar) return;
  const inner = document.getElementById("bgp-bar-inner");
  const content = bgpBar();
  if (inner) inner.innerHTML = content;
  bar.style.display = content ? "flex" : "none";
}

/* ── Sidebar ─────────────────────────────────────────────────── */
function _sidebar() {
  const nav = document.getElementById("nav-list");
  if (!nav) return;
  const r = STATE.route;
  const feedN  = sourcesByLayer(2).length;
  const checkN = STATE.sources.filter(s => layerOf(s) === 1 && isConfigured(s)).length;
  const advN   = sourcesByLayer(4).length;
  const errN   = STATE.sources.filter(s => s.enabled && !s.ok).length;

  const links = [
    { id: "overview",  label: "Essentials", glyph: "◈" },
    { id: "check",     label: `Check${checkN ? ` (${checkN})` : ""}`, glyph: "◎" },
    { id: "info",      label: `Info${feedN ? ` (${feedN})` : ""}`, glyph: "⊞" },
    { id: "advanced",  label: `Advanced${advN ? ` (${advN})` : ""}`, glyph: "◇" },
    { id: "status",    label: `Status${errN ? ` ⚑${errN}` : ""}`, glyph: "⊙" },
  ];

  const ver = STATE.status ? (STATE.status.version || "") : "";
  nav.innerHTML =
    `<div class="nav-brand">OmniCheck</div>` +
    links.map(l => {
      const act = r === l.id ? " nav-active" : "";
      return `<a class="nav-link${act}" href="#/${esc(l.id)}"
        onclick="event.preventDefault();window.navigate(${jsq(l.id)})">
        <span class="nav-glyph">${l.glyph}</span>
        <span class="nav-label">${esc(l.label)}</span>
      </a>`;
    }).join("") +
    `<div class="nav-spacer"></div>` +
    (ver ? `<div class="nav-version">v${esc(ver)}</div>` : "");
}

/* ── Content router ─────────────────────────────────────────── */
function _content() {
  const el = document.getElementById("content");
  if (!el) return;
  const { route, routeParam } = STATE;
  if      (route === "source" && routeParam) el.innerHTML = _sourcePage(routeParam);
  else if (route === "check")                el.innerHTML = _checkPage();
  else if (route === "info" || route === "feeds") el.innerHTML = _feedsPage();
  else if (route === "advanced")             el.innerHTML = _advancedPage();
  else if (route === "status")               el.innerHTML = _statusPage();
  else                                       el.innerHTML = _overviewPage();
}

/* ── Essentials (L0, minus the header spie) ─────────────────── */
function _overviewPage() {
  // bgp/cloud/root live in the header now — show the rest of L0 here.
  const l0 = sourcesByLayer(0).filter(s => !SPIE.includes(s.id));
  const checkN = STATE.sources.filter(s => layerOf(s) === 1 && isConfigured(s)).length;
  const feedN  = sourcesByLayer(2).length;

  let html = `<div class="pg-hdr"><h1 class="pg-title">Essentials</h1>
    <div class="pg-sub c-dim">Public-probe internet health · the spie above watch BGP, cloud and the DNS root</div></div>`;

  // Monitored domains (dnsmon) and Italian backbone BGP states (bgp),
  // surfaced here even though their cards/spie live elsewhere.
  const dnsData = (STATE.data["dnsmon"] || {}).data;
  if (dnsData) {
    html += `<div class="sect-title">Monitored Domains</div>` + domainsWidget(dnsData);
  }
  const bgpData = (STATE.data["bgp"] || {}).data;
  if (bgpData) {
    html += `<div class="sect-title">BGP — Italian backbone</div>` + bgpWidget(bgpData);
  }

  html += `<div class="ov-shortcuts">
    <button class="sc-btn" onclick="window.navigate('check')">
      <span class="sc-glyph">◎</span>
      <div><div class="sc-name">Check</div>
      <div class="sc-sub">${checkN} configured API${checkN !== 1 ? "s" : ""} · assets</div></div>
    </button>
    <button class="sc-btn" onclick="window.navigate('info')">
      <span class="sc-glyph">⊞</span>
      <div><div class="sc-name">Info</div>
      <div class="sc-sub">${feedN} feed source${feedN !== 1 ? "s" : ""}</div></div>
    </button>
    <button class="sc-btn" onclick="window.navigate('status')">
      <span class="sc-glyph">⊙</span>
      <div><div class="sc-name">Status</div>
      <div class="sc-sub">engines &amp; config</div></div>
    </button>
  </div>`;

  // Engine cards last, at the bottom of the page.
  if (l0.length) {
    html += `<div class="sect-title">Engines</div>
      <div class="mon-grid">${l0.map(monitorCard).join("")}</div>`;
  }
  return html;
}

/* ── Check (L1): working APIs + correlated assets ───────────── */
function _checkPage() {
  const l1 = STATE.sources.filter(s => layerOf(s) === 1 && isConfigured(s));
  let html = `<div class="pg-hdr"><h1 class="pg-title">Check</h1>
    <div class="pg-sub c-dim">Configured intelligence APIs and the assets correlated from their results</div></div>`;

  if (!l1.length) {
    html += `<div class="empty-note">No API is configured yet — add credentials in <code>config.yaml</code>.</div>`;
  }

  // Atera RMM: last 5 alerts + open tickets, surfaced inline.
  const atera = STATE.sources.find(s => s.id === "atera" && isConfigured(s));
  if (atera) {
    html += `<div class="sect-title">Atera RMM — alerts &amp; tickets</div>`;
    html += ateraWidget((STATE.data["atera"] || {}).data);
  }

  // Correlated assets: the `assets` source carries the cross-engine intel view.
  const assets = STATE.sources.find(s => s.id === "assets");
  if (assets) {
    const dd = STATE.data["assets"] || {};
    html += `<div class="sect-title">Assets — correlated engine results</div>`;
    html += intelWidget(dd.data || null, STATE.ui.readonly);
  }

  // Engine cards last, at the bottom of the page.
  if (l1.length) {
    html += `<div class="sect-title">Engines</div>
      <div class="mon-grid">${l1.map(monitorCard).join("")}</div>`;
  }
  return html;
}

/* ── Advanced (L4): correlation + STIX export engines ───────── */
function _advancedPage() {
  const adv = sourcesByLayer(4);
  let html = `<div class="pg-hdr"><h1 class="pg-title">Advanced</h1>
    <div class="pg-sub c-dim">Cross-engine correlation and threat-intel export</div></div>`;

  if (!adv.length) {
    return html + `<div class="empty-note">No Advanced-layer engines registered.</div>`;
  }

  for (const s of adv) {
    const dd   = STATE.data[s.id] || {};
    const data = dd.data;
    const sch  = s.schema || {};
    if (!data) continue;
    html += `<div class="sect-title">${esc(s.name)}</div>`;
    if (sch.table) {
      const rows = data[sch.table.rows_key] || [];
      html += tableHtml(sch.table, { [sch.table.rows_key]: rows.slice(0, 25) }, null, null);
    }
  }

  // Engine cards last, at the bottom of the page.
  html += `<div class="sect-title">Engines</div>
    <div class="mon-grid">${adv.map(monitorCard).join("")}</div>`;
  return html;
}

/* ── Substatus block: tools (L0) + how-it-works + config + log ── */
function _subStatusHtml(id, layer) {
  const det = STATE.detail[id];
  if (!det) return `<div class="empty-note">Loading engine detail…</div>`;
  let h = "";
  if (layer === 0) h += toolRunner(id, det);
  h += logicBlock(det);
  h += configBlock(det);
  h += eventsBlock(det);
  return h;
}

/* ── Source detail ──────────────────────────────────────────── */
function _sourcePage(id) {
  const s = STATE.sources.find(s => s.id === id);
  if (!s) return `<div class="empty-note">Unknown source: ${esc(id)}</div>`;

  const st   = sourceStatus(s);
  const sch  = s.schema || {};
  const dd   = STATE.data[id] || {};
  const data = dd.data || null;
  const kind = kindOf(s).replace(/_/g, " ");
  const layer = layerOf(s);

  let html = `<div class="pg-hdr">
    <button class="back-btn" onclick="history.back()">← back</button>
    <h1 class="pg-title">${esc(s.name)}</h1>
    <div class="pg-meta">
      ${led(st, false)}
      <span class="pill-${esc(st)}">${esc(st.toUpperCase())}</span>
      <span class="kind-chip kb-${esc(kindOf(s))}">${esc(kind)}</span>
      <span class="layer-chip">L${layer}</span>
    </div>
  </div>`;

  if (sch.description) html += `<p class="src-desc">${esc(sch.description)}</p>`;

  html += `<div class="kv-grid">
    <div class="kv-item"><div class="kv-v c-mono">${esc(s.last_fetch || "—")}</div><div class="kv-k">last fetch</div></div>
    <div class="kv-item"><div class="kv-v">${esc(fmtAge(dd.age_s ?? s.age_s))}</div><div class="kv-k">data age</div></div>
    <div class="kv-item"><div class="kv-v">${esc(fmtAge(s.interval))}</div><div class="kv-k">interval</div></div>
    <div class="kv-item"><div class="kv-v">L${layer} ${esc(kind)}</div><div class="kv-k">layer / kind</div></div>
  </div>`;

  const errTxt = dd.error || s.last_error || s.error || "";
  if (errTxt) html += `<div class="errline">⚠ ${esc(errTxt)}</div>`;

  if (!s.enabled) {
    html += `<div class="locked-note">Source disabled — configure <code>sources.${esc(id)}</code> in config.yaml</div>`;
    return html + _subStatusHtml(id, layer);
  }

  if (!data) {
    html += `<div class="empty-note">No data yet — source is fetching.</div>`;
    return html + _subStatusHtml(id, layer);
  }

  // Summary cards
  html += `<div class="sect-title">Summary</div>` + summaryCards(s, data);

  // Widget or table(s)
  if (sch.widget === "intel") {
    html += `<div class="sect-title">Assets</div>` + intelWidget(data, STATE.ui.readonly);
  } else if (sch.widget === "providerbar") {
    html += `<div class="sect-title">Providers</div>` + providerBar(data);
  } else if (sch.widget === "feeds") {
    html += `<div class="sect-title">Latest</div>` + feedsWidget(id, data, 0);
  } else if (sch.sections) {
    for (const sec of sch.sections) {
      html += `<div class="sect-title">${esc(sec.title)}</div>` + tableHtml(sec.table, data, null, null);
    }
  } else if (sch.table) {
    html += `<div class="sect-title">Data</div>` + tableHtml(sch.table, data, null, null);
  }

  // Substatus: tools (L0), how-it-works, config, last significant log
  html += _subStatusHtml(id, layer);

  // Refresh button
  if (!STATE.ui.readonly) {
    html += `<div class="src-actions">
      <button class="tb-btn" onclick="window.forceRefresh(${jsq(id)})">↻ Force Refresh</button>
    </div>`;
  }

  // Raw JSON
  html += `<details class="raw-details"><summary>Raw JSON</summary>
    <pre class="raw-pre">${esc(JSON.stringify(dd, null, 2))}</pre>
  </details>`;

  return html;
}

/* ── Feed Center ────────────────────────────────────────────── */
function _feedsPage() {
  const feeds = sourcesByLayer(2);
  let html = `<div class="pg-hdr"><h1 class="pg-title">Info</h1>
    <div class="pg-sub c-dim">Feed sources · advisories, news and threat intel streams</div></div>`;

  if (!feeds.length) {
    return html + `<div class="empty-note">No Info-layer feed sources configured.</div>`;
  }

  for (const s of feeds) {
    const dd   = STATE.data[s.id] || {};
    const data = dd.data;
    const sch  = s.schema || {};
    if (!data) continue;

    html += `<div class="sect-title">${esc(s.name)} — Latest</div>`;
    if (sch.widget === "feeds") {
      html += feedsWidget(s.id, data, 10);
    } else if (sch.table) {
      const rows = data[sch.table.rows_key] || [];
      html += tableHtml(sch.table, { [sch.table.rows_key]: rows.slice(0, 15) }, null, null);
    }
  }

  // Engine cards last, at the bottom of the page.
  html += `<div class="sect-title">Engines</div>
    <div class="mon-grid">${feeds.map(monitorCard).join("")}</div>`;
  return html;
}

/* ── Status page ────────────────────────────────────────────── */
function _statusPage() {
  const st = STATE.status;
  let html = `<div class="pg-hdr"><h1 class="pg-title">Status</h1></div>`;

  if (st) {
    const up = st.uptime_s || 0;
    const upStr = up < 3600 ? `${Math.round(up/60)}m` : `${Math.floor(up/3600)}h ${Math.round((up%3600)/60)}m`;
    const dShort = v => v ? esc(String(v).slice(0, 10)) : "—";
    html += `<div class="kv-grid">
      <div class="kv-item"><div class="kv-v c-mono">${esc(st.version||"")}</div><div class="kv-k">version</div></div>
      <div class="kv-item"><div class="kv-v">${esc(upStr)}</div><div class="kv-k">uptime</div></div>
      <div class="kv-item"><div class="kv-v c-mono">${dShort(st.installed_at)}</div><div class="kv-k">installed</div></div>
      <div class="kv-item"><div class="kv-v c-mono">${dShort(st.updated_at)}</div><div class="kv-k">last update</div></div>
      <div class="kv-item"><div class="kv-v c-mono">${esc(st.python||"")}</div><div class="kv-k">python</div></div>
      <div class="kv-item"><div class="kv-v">${esc(st.sources_ok||0)}/${esc(st.sources_total||0)}</div><div class="kv-k">sources OK</div></div>
    </div>`;

    if ((st.config_issues||[]).length) {
      html += `<div class="sect-title">Configuration Issues</div>`;
      html += (st.config_issues||[]).map(i =>
        `<div class="errline">⚠ <b>${esc(i.source)}</b>: ${esc(i.detail)}</div>`
      ).join("");
    }
    if ((st.runtime_errors||[]).length) {
      html += `<div class="sect-title">Runtime Errors</div>`;
      html += (st.runtime_errors||[]).map(i =>
        `<div class="errline">✕ <b>${esc(i.source)}</b>: ${esc(i.detail)}</div>`
      ).join("");
    }
  }

  // Source table grouped by layer
  for (const layer of [0, 1, 2, 4]) {
    const srcs = STATE.sources.filter(s => layerOf(s) === layer);
    if (!srcs.length) continue;
    html += `<div class="sect-title">L${layer} — ${esc(layerLabel(layer))}</div>
      <table><thead><tr>
        <th>Source</th><th>Kind</th><th>Status</th><th>Age</th><th>Interval</th><th>Error</th>
      </tr></thead><tbody>${srcs.map(s => {
        const st2 = sourceStatus(s);
        const cls = !s.enabled ? "row-off" : !s.ok ? "row-err" : "";
        return `<tr class="${cls}">
          <td><a href="#/source/${esc(s.id)}" onclick="window.navigate(${jsq('source/'+s.id)});event.preventDefault()">${esc(s.name)}</a></td>
          <td class="c-dim">${esc(kindOf(s).replace(/_/g," "))}</td>
          <td>${led(st2,false)} <span class="pill-${esc(st2)}">${esc(st2)}</span></td>
          <td class="c-mono c-dim">${esc(fmtAge((STATE.data[s.id]||{}).age_s ?? s.age_s))}</td>
          <td class="c-mono c-dim">${esc(fmtAge(s.interval))}</td>
          <td class="c-dim c-trunc">${esc(s.last_error||s.error||"")}</td>
        </tr>`;
      }).join("")}</tbody></table>`;
  }

  html += _creditsHtml();
  return html;
}

/* ── Credits: a tip of the hat to the hackers and the machine ── */
function _creditsHtml() {
  return `<div class="sect-title">Credits</div>
  <div class="credits">
    <p class="cr-lead">Built in the solo-hacker spirit — simplicity over completeness,
      deep understanding over surface coverage.</p>
    <p>In tribute to <strong>Salvatore Sanfilippo (antirez)</strong>, whose Redis,
      linenoise and writings are the north star of this codebase: small, sharp,
      legible tools you can hold whole in your head. With a nod to the other
      tinkerers who build great things alone — Karpathy, Thompson, Gerganov.</p>
    <p class="cr-ai c-dim">Crafted in pair-programming with an AI assistant
      (Claude), under a human hand that owns every line. The machine drafts;
      the hacker decides.</p>
    <p class="cr-foot c-dim">Icons by icons8 · public data via RIPEstat, IANA,
      crt.sh and provider status pages.</p>
  </div>`;
}
