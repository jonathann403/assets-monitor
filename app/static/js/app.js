"use strict";
/* Assets Monitor dashboard.
 * All values rendered into the table come from scanned third-party sites and
 * are therefore untrusted: every cell is built with DOM APIs / textContent so
 * a malicious page <title> or header can never inject markup here. */

const POLL_MS = 2500;
const ACTIVE = new Set(["queued", "enumerating", "probing"]);

const state = {
  scans: [],
  selected: null,
  results: [],
  meta: null,
  summary: null,
  search: "",
  statusFilter: "all",
  sort: { key: "input", dir: 1 },
  pollTimer: null,
  lastStatus: {},
};

const COLUMNS = [
  { key: "input", label: "Subdomain", sortable: true },
  { key: "status_code", label: "Status", sortable: true, numeric: true },
  { key: "title", label: "Title", sortable: true },
  { key: "webserver", label: "Server", sortable: true },
  { key: "tech", label: "Technology", sortable: false },
  { key: "content_type", label: "Type", sortable: true },
  { key: "content_length", label: "Length", sortable: true, numeric: true, align: "num" },
  { key: "host", label: "IP", sortable: true },
];

/* ---------- tiny DOM helpers ---------- */
const $ = (sel) => document.querySelector(sel);

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v == null || v === false) continue;
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === "href" || k === "src") node[k] = v;
    else if (v === true) node.setAttribute(k, "");
    else node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    node.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return node;
}

function safeUrl(u) {
  return typeof u === "string" && /^https?:\/\//i.test(u) ? u : null;
}

/* ---------- API ---------- */
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  let body = null;
  try { body = await res.json(); } catch (_) { /* no body */ }
  if (!res.ok) {
    const msg = (body && body.error) || `Request failed (${res.status})`;
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }
  return body;
}

/* ---------- toasts ---------- */
function toast(title, body, kind = "") {
  const node = el("div", { class: `toast ${kind}` },
    el("div", { class: "t-title" }, title),
    body ? el("div", { class: "t-body" }, body) : null
  );
  $("#toasts").append(node);
  setTimeout(() => {
    node.style.opacity = "0";
    node.style.transition = "opacity .3s";
    setTimeout(() => node.remove(), 300);
  }, kind === "error" ? 6000 : 4000);
}

/* ---------- status helpers ---------- */
function statusBucket(code) {
  const c = parseInt(code, 10);
  if (c >= 200 && c < 300) return "2xx";
  if (c >= 300 && c < 400) return "3xx";
  if (c >= 400 && c < 500) return "4xx";
  if (c >= 500 && c < 600) return "5xx";
  return "other";
}

function relTime(iso) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (isNaN(then)) return "";
  const s = Math.round((Date.now() - then) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

/* ---------- sidebar ---------- */
function renderSidebar() {
  const list = $("#domain-list");
  list.replaceChildren();
  $("#domain-count").textContent = state.scans.length;
  $("#domain-empty").hidden = state.scans.length > 0;

  for (const scan of state.scans) {
    const running = ACTIVE.has(scan.status);
    const item = el("li", {
      class: `domain-item ${scan.status} ${scan.domain === state.selected ? "active" : ""}`,
      onclick: () => selectDomain(scan.domain),
    },
      el("span", { class: "dot" }),
      el("span", { class: "d-name", title: scan.domain }, scan.domain),
      running
        ? el("span", { class: "d-count running" }, phaseLabel(scan.status))
        : el("span", { class: "d-count" }, `${scan.hosts_live ?? 0}`)
    );
    list.append(item);
  }
}

function phaseLabel(status) {
  return { queued: "queued", enumerating: "enum…", probing: "probing…" }[status] || status;
}

function renderCapacity() {
  const cap = state.capacity || { active: 0, max: 0 };
  const node = $("#capacity");
  node.replaceChildren();
  if (cap.active > 0) {
    node.append(el("span", { class: "spinner" }), ` ${cap.active} scanning`);
  } else {
    node.append(`${state.scans.length} domain${state.scans.length === 1 ? "" : "s"} monitored`);
  }
}

/* ---------- detail ---------- */
async function selectDomain(domain) {
  state.selected = domain;
  renderSidebar();
  try {
    const data = await api(`/api/scans/${encodeURIComponent(domain)}`);
    if (state.selected !== domain) return; // user moved on
    state.results = Array.isArray(data.results) ? data.results : [];
    state.meta = data.meta;
    state.summary = data.summary;
    renderDetail();
  } catch (err) {
    toast("Could not load scan", err.message, "error");
  }
}

function renderDetail() {
  $("#detail-empty").hidden = true;
  $("#detail").hidden = false;

  const meta = state.meta || {};
  $("#detail-domain").textContent = state.selected;

  const sub = $("#detail-sub");
  sub.replaceChildren();
  sub.append(statusBadge(meta.status));
  const bits = [];
  if (meta.message) bits.push(meta.message);
  if (meta.finished_at && !ACTIVE.has(meta.status)) bits.push(relTime(meta.finished_at));
  else if (meta.started_at) bits.push(`started ${relTime(meta.started_at)}`);
  if (meta.duration_seconds != null) bits.push(`${meta.duration_seconds}s`);
  if (bits.length) sub.append(document.createTextNode("  ·  " + bits.join("  ·  ")));

  $("#export-csv").href = `/api/scans/${encodeURIComponent(state.selected)}/export.csv`;
  $("#delete-btn").disabled = ACTIVE.has(meta.status);
  $("#rescan-btn").disabled = ACTIVE.has(meta.status);

  renderStats();
  renderStatusFilters();
  renderTable();
}

function statusBadge(status) {
  const kind = ACTIVE.has(status) ? "running" : status;
  const label = ACTIVE.has(status) ? phaseLabel(status) : status;
  return el("span", { class: `status-badge ${kind}` }, el("span", { class: "dot" }), label || "unknown");
}

function stat(label, value, opts = {}) {
  return el("div", { class: "stat" },
    el("div", { class: "label" }, label),
    el("div", { class: `value ${opts.accent ? "accent" : ""}` }, value),
    opts.extra || null
  );
}

function renderStats() {
  const grid = $("#stat-grid");
  grid.replaceChildren();
  const s = state.summary || { total: 0, live: 0, status_classes: {}, technologies: [], cdn_count: 0, unique_technologies: 0 };
  const meta = state.meta || {};

  grid.append(stat("Subdomains", meta.subdomains_found ?? "—"));
  grid.append(stat("Live hosts", s.live ?? 0, { accent: true }));

  // status breakdown card with a stacked bar
  const sc = s.status_classes || {};
  const total = (sc["2xx"] || 0) + (sc["3xx"] || 0) + (sc["4xx"] || 0) + (sc["5xx"] || 0) + (sc.other || 0) || 1;
  const bar = el("div", { class: "stat-bars" });
  const breakdown = el("div", { class: "breakdown" });
  for (const cls of ["2xx", "3xx", "4xx", "5xx"]) {
    const n = sc[cls] || 0;
    if (n > 0) {
      bar.append(el("span", { class: "seg", style: `flex:${n};background:var(--c-${cls})` }));
    }
    breakdown.append(el("span", {}, el("b", { style: `color:var(--c-${cls})` }, n), ` ${cls}`));
  }
  grid.append(el("div", { class: "stat" },
    el("div", { class: "label" }, "Status codes"),
    bar,
    breakdown
  ));

  // technologies card
  const techChips = el("div", { class: "chips" });
  for (const t of (s.technologies || []).slice(0, 8)) {
    techChips.append(el("span", { class: "chip" }, t.name, " ", el("b", {}, t.count)));
  }
  if (!(s.technologies || []).length) techChips.append(el("span", { class: "chip" }, "none detected"));
  grid.append(el("div", { class: "stat" },
    el("div", { class: "label" }, `Technologies (${s.unique_technologies || 0})`),
    techChips
  ));

  grid.append(stat("Behind CDN", s.cdn_count || 0));
}

function renderStatusFilters() {
  const wrap = $("#status-filters");
  wrap.replaceChildren();
  const counts = { all: state.results.length, "2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0 };
  for (const r of state.results) {
    const b = statusBucket(r.status_code);
    if (counts[b] != null) counts[b]++;
  }
  for (const key of ["all", "2xx", "3xx", "4xx", "5xx"]) {
    if (key !== "all" && counts[key] === 0) continue;
    const label = key === "all" ? `All ${counts.all}` : `${key} ${counts[key]}`;
    wrap.append(el("span", {
      class: `filter ${state.statusFilter === key ? "active" : ""}`,
      onclick: () => { state.statusFilter = key; renderStatusFilters(); renderTable(); },
    }, label));
  }
}

/* ---------- table ---------- */
function renderTable() {
  const head = $("#results-head");
  head.replaceChildren();
  const tr = el("tr");
  for (const col of COLUMNS) {
    const sorted = state.sort.key === col.key;
    tr.append(el("th", {
      class: [col.sortable ? "sortable" : "", sorted ? (state.sort.dir === 1 ? "sort-asc" : "sort-desc") : "", col.align || ""].join(" ").trim(),
      onclick: col.sortable ? () => toggleSort(col.key) : null,
    }, col.label));
  }
  head.append(tr);

  let rows = state.results.slice();

  // status filter
  if (state.statusFilter !== "all") {
    rows = rows.filter((r) => statusBucket(r.status_code) === state.statusFilter);
  }
  // search
  const q = state.search.trim().toLowerCase();
  if (q) {
    rows = rows.filter((r) => {
      const hay = [r.input, r.title, r.webserver, r.host, r.content_type, (r.tech || []).join(" ")]
        .filter(Boolean).join(" ").toLowerCase();
      return hay.includes(q);
    });
  }
  // sort
  const { key, dir } = state.sort;
  const numeric = COLUMNS.find((c) => c.key === key)?.numeric;
  rows.sort((a, b) => {
    let va = a[key], vb = b[key];
    if (numeric) { va = parseFloat(va) || 0; vb = parseFloat(vb) || 0; return (va - vb) * dir; }
    va = (va == null ? "" : String(va)).toLowerCase();
    vb = (vb == null ? "" : String(vb)).toLowerCase();
    return va < vb ? -dir : va > vb ? dir : 0;
  });

  const body = $("#results-body");
  body.replaceChildren();
  for (const r of rows) body.append(renderRow(r));

  const empty = $("#results-empty");
  if (rows.length === 0) {
    empty.hidden = false;
    empty.textContent = state.results.length === 0
      ? (ACTIVE.has((state.meta || {}).status) ? "Scan in progress…" : "No live hosts found.")
      : "No results match your filters.";
  } else {
    empty.hidden = true;
  }
}

function toggleSort(key) {
  if (state.sort.key === key) state.sort.dir *= -1;
  else state.sort = { key, dir: 1 };
  renderTable();
}

function renderRow(r) {
  const tr = el("tr");

  // subdomain
  const url = safeUrl(r.url);
  const nameCell = el("td", { class: "host-cell" });
  nameCell.append(url ? el("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, r.input || "")
                      : el("span", { class: "mono" }, r.input || ""));
  if (r.cdn) nameCell.append(" ", el("span", { class: "cdn-tag" }, r.cdn_name || "CDN"));
  const loc = safeUrl(r.location);
  if (loc) {
    nameCell.append(el("div", { class: "muted mono", style: "font-size:.72rem;margin-top:2px" },
      "→ ", el("a", { href: loc, target: "_blank", rel: "noopener noreferrer" }, r.location)));
  }
  tr.append(nameCell);

  // status
  const bucket = statusBucket(r.status_code);
  tr.append(el("td", {}, r.status_code != null
    ? el("span", { class: `code-badge code-${bucket}` }, r.status_code)
    : el("span", { class: "muted" }, "—")));

  // title
  tr.append(el("td", { class: "title-cell" }, r.title || el("span", { class: "muted" }, "—")));
  // server
  tr.append(el("td", {}, r.webserver || el("span", { class: "muted" }, "—")));
  // tech
  const techCell = el("td", {}, el("div", { class: "tech-cell" },
    ...((r.tech || []).map((t) => el("span", { class: "tech" }, t)))));
  if (!(r.tech || []).length) techCell.firstChild.append(el("span", { class: "muted" }, "—"));
  tr.append(techCell);
  // type
  tr.append(el("td", { class: "muted mono" }, (r.content_type || "—")));
  // length
  tr.append(el("td", { class: "num muted" }, r.content_length != null ? formatBytes(r.content_length) : "—"));
  // ip
  tr.append(el("td", { class: "mono muted" }, r.host || "—"));
  return tr;
}

function formatBytes(n) {
  n = parseInt(n, 10);
  if (isNaN(n)) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

/* ---------- actions ---------- */
async function startScan(domain) {
  const btn = $("#scan-btn");
  const errBox = $("#scan-error");
  errBox.textContent = "";
  btn.disabled = true;
  try {
    const data = await api("/api/scans", { method: "POST", body: JSON.stringify({ domain }) });
    const started = data.scan.domain;
    $("#domain-input").value = "";
    toast("Scan started", started, "success");
    await loadDomains();
    selectDomain(started);
    ensurePolling();
  } catch (err) {
    errBox.textContent = err.message;
    if (err.status === 409 || err.status === 429) toast("Scan not started", err.message, "error");
  } finally {
    btn.disabled = false;
  }
}

async function deleteDomain(domain) {
  if (!confirm(`Delete all results for ${domain}? This cannot be undone.`)) return;
  try {
    await api(`/api/scans/${encodeURIComponent(domain)}`, { method: "DELETE" });
    toast("Deleted", domain, "success");
    if (state.selected === domain) {
      state.selected = null;
      $("#detail").hidden = true;
      $("#detail-empty").hidden = false;
    }
    await loadDomains();
  } catch (err) {
    toast("Could not delete", err.message, "error");
  }
}

function exportJson() {
  const blob = new Blob([JSON.stringify(state.results, null, 2)], { type: "application/json" });
  const a = el("a", { href: URL.createObjectURL(blob), download: `${state.selected}.json` });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

/* ---------- polling ---------- */
async function loadDomains() {
  try {
    const data = await api("/api/scans");
    state.scans = data.scans || [];
    state.capacity = data.capacity;

    // detect transitions active -> terminal
    for (const scan of state.scans) {
      const prev = state.lastStatus[scan.domain];
      if (prev && ACTIVE.has(prev) && !ACTIVE.has(scan.status)) {
        if (scan.status === "completed") toast("Scan complete", `${scan.domain}: ${scan.hosts_live} live hosts`, "success");
        else if (scan.status === "failed") toast("Scan failed", `${scan.domain}: ${scan.error || "error"}`, "error");
        if (state.selected === scan.domain) selectDomain(scan.domain);
      }
    }
    state.lastStatus = Object.fromEntries(state.scans.map((s) => [s.domain, s.status]));

    renderSidebar();
    renderCapacity();
    managePolling();
  } catch (err) {
    console.error(err);
  }
}

function anyActive() {
  return state.scans.some((s) => ACTIVE.has(s.status));
}

function managePolling() {
  if (anyActive()) ensurePolling();
  else stopPolling();
}

function ensurePolling() {
  if (state.pollTimer) return;
  state.pollTimer = setInterval(loadDomains, POLL_MS);
}

function stopPolling() {
  if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
}

/* ---------- theme ---------- */
function initTheme() {
  let theme = null;
  try { theme = localStorage.getItem("am-theme"); } catch (_) {}
  if (!theme) theme = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  document.documentElement.dataset.theme = theme;
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("am-theme", next); } catch (_) {}
}

/* ---------- init ---------- */
function init() {
  initTheme();
  $("#theme-toggle").addEventListener("click", toggleTheme);

  $("#scan-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const domain = $("#domain-input").value.trim();
    if (domain) startScan(domain);
  });
  $("#domain-input").addEventListener("input", () => { $("#scan-error").textContent = ""; });

  let searchT;
  $("#table-search").addEventListener("input", (e) => {
    clearTimeout(searchT);
    searchT = setTimeout(() => { state.search = e.target.value; renderTable(); }, 120);
  });

  $("#export-json").addEventListener("click", exportJson);
  $("#delete-btn").addEventListener("click", () => state.selected && deleteDomain(state.selected));
  $("#rescan-btn").addEventListener("click", () => state.selected && startScan(state.selected));

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) loadDomains();
  });

  const preselect = document.body.dataset.preselect;
  loadDomains().then(() => {
    if (preselect) selectDomain(preselect);
  });
}

document.addEventListener("DOMContentLoaded", init);
