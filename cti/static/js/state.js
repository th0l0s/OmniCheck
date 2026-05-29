/* state.js — shared runtime state and constants. No side effects. */

export const STATE = {
  sources: [],
  data: {},
  status: null,
  ui: { app: "OmniCheck Cockpit", poll_interval_s: 15, readonly: true },
  view: "overview",
  next: 15,
  refreshMs: 15000,
  domainFilters: {},
  feedFilters: {},
};

/* hardcoded metadata for sources not exposing a category in schema() */
export const META = {
  atera:        { cat: "API",    link: "https://app.atera.com" },
  shodan:       { cat: "API",    link: "https://account.shodan.io" },
  netlas:       { cat: "API",    link: "https://app.netlas.io" },
  bgp:          { cat: "API",    link: "https://stat.ripe.net" },
  rootmon:      { cat: "PROBE",  link: "https://root-servers.org" },
  news_feed:    { cat: "FEED",   link: "" },
  acn_misp:     { cat: "FEED",   link: "https://www.csirt.gov.it" },
  cloud_status: { cat: "STATUS", link: "" },
  correlation:  { cat: "META",   link: "" },
  opencti:      { cat: "META",   link: "" },
  assets:       { cat: "META",   link: "" },
};

export const CAT_ORDER = ["API", "FEED", "STATUS", "PROBE", "META"];

/* sources shown only in their dedicated sidebar tabs, not in overview grid */
export const GRID_HIDDEN = new Set([
  "shodan", "netlas", "correlation", "thc_rdns",
  "acn_misp", "news_feed", "cloud_status", "rootmon",
]);
