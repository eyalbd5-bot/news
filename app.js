/* חדשות אייל - client. Vanilla JS, no build step. Data comes from data/index/<topic>.json written by the pipeline. */
(() => {
"use strict";
const $ = (s, r = document) => r.querySelector(s);
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const ICONS = {
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
  bookmark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"><path d="M6 4h12v17l-6-4-6 4z"/></svg>',
  bookmarkOn: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 4h12v17l-6-4-6 4z"/></svg>',
  sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4m11.4-11.4 1.4-1.4"/></svg>',
  moon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"><path d="M20 15.5A8.5 8.5 0 0 1 8.5 4a8.5 8.5 0 1 0 11.5 11.5z"/></svg>',
  close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  ext: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/></svg>',
};

const state = {
  cfg: null, meta: null, data: {}, bodies: {},
  topic: null, section: "all", team: null, league: null, q: "", view: "feed",
  saved: load("saved", {}),
};
function load(k, d) { try { return JSON.parse(localStorage.getItem("news:" + k)) ?? d; } catch { return d; } }
function store(k, v) { try { localStorage.setItem("news:" + k, JSON.stringify(v)); } catch {} }

/* ---------- time ---------- */
const MIN = 60e3, H = 36e5, D = 864e5;
function ago(iso) {
  const t = Date.parse(iso), d = Date.now() - t;
  if (isNaN(t)) return "";
  if (d < MIN) return "עכשיו";
  if (d < H) { const m = Math.round(d / MIN); return m === 1 ? "לפני דקה" : `לפני ${m} דק'`; }
  if (d < D) { const h = Math.round(d / H); return h === 1 ? "לפני שעה" : h === 2 ? "לפני שעתיים" : `לפני ${h} שעות`; }
  const days = Math.round(d / D);
  if (days === 1) return "אתמול";
  if (days === 2) return "לפני יומיים";
  return `לפני ${days} ימים`;
}
const hhmm = iso => new Date(iso).toLocaleTimeString("he-IL", { hour: "2-digit", minute: "2-digit" });

/* ---------- theme ---------- */
function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  $("#btnTheme").innerHTML = t === "dark" ? ICONS.sun : ICONS.moon;
  $('meta[name="theme-color"]').content = t === "dark" ? "#0b0f17" : "#f3f5f9";
  store("theme", t);
}

/* ---------- data ---------- */
async function getJSON(u) { const r = await fetch(u, { cache: "no-cache" }); if (!r.ok) throw new Error(u + " " + r.status); return r.json(); }
async function boot() {
  $("#btnSearch").innerHTML = ICONS.search; $("#btnSaved").innerHTML = ICONS.bookmark + '<span class="badge" id="savedCount" hidden></span>';
  $("#btnCloseSearch").innerHTML = ICONS.close; $("#btnCloseReader").innerHTML = ICONS.close; $("#btnCloseStatus").innerHTML = ICONS.close;
  $("#btnReaderOpen").innerHTML = ICONS.ext;
  applyTheme(load("theme", "dark"));
  state.cfg = await getJSON("config/sources.json");
  try { state.meta = await getJSON("data/meta.json"); } catch { state.meta = null; }
  const hash = location.hash.replace("#", "").split("/");
  state.topic = state.cfg.topics.find(t => t.id === hash[0])?.id || state.cfg.topics[0].id;
  if (hash[1]) state.section = hash[1];
  await Promise.all(state.cfg.topics.map(async t => { try { state.data[t.id] = await getJSON(`data/index/${t.id}.json`); } catch { state.data[t.id] = []; } }));
  renderUpdated(); renderTabs(); render(); updateSavedBadge();
  setInterval(renderUpdated, 60e3);
  setInterval(refresh, 5 * 60e3);
}
async function refresh() {
  try {
    const meta = await getJSON("data/meta.json");
    if (meta.updated === state.meta?.updated) return;
    state.meta = meta;
    await Promise.all(state.cfg.topics.map(async t => { state.data[t.id] = await getJSON(`data/index/${t.id}.json`); }));
    renderUpdated(); renderTabs(); render();
  } catch {}
}
function renderUpdated() {
  const u = $("#updated"); if (!state.meta) { u.textContent = ""; return; }
  const d = Date.now() - Date.parse(state.meta.updated);
  u.textContent = "עודכן " + ago(state.meta.updated);
  u.classList.toggle("stale", d > 2 * H);
  $("#footInfo").textContent = `עודכן ${new Date(state.meta.updated).toLocaleString("he-IL", { dateStyle: "short", timeStyle: "short" })}`;
}

/* ---------- helpers ---------- */
const topicCfg = () => state.cfg.topics.find(t => t.id === state.topic);
const title = a => a.he?.title || a.title;
const summary = a => a.he?.summary || a.summary || "";
const isPrimary = a => !a.cluster || a.cluster === a.id;
function matches(a, q) {
  q = q.trim().toLowerCase(); if (!q) return true;
  return [a.title, a.summary, a.he?.title, a.he?.summary, a.source_name].some(s => (s || "").toLowerCase().includes(q));
}
function teamOf(a) { const t = topicCfg().teams || []; const ids = a.tags?.teams || []; return t.find(x => ids.includes(x.id)); }
function setAccent(color) { document.documentElement.style.setProperty("--accent", color); }

/* ---------- tabs / subbar ---------- */
function renderTabs() {
  const nav = $("#tabs"); nav.innerHTML = "";
  for (const t of state.cfg.topics) {
    const n = (state.data[t.id] || []).filter(a => isPrimary(a) && !a.ticker && Date.now() - Date.parse(a.published) < D).length;
    const b = el("button", "tab" + (t.id === state.topic && state.view === "feed" ? " active" : ""),
      `<span class="ic">${t.icon}</span><span>${esc(t.name)}</span><span class="cnt" title="ידיעות ב-24 שעות">${n}</span>`);
    b.style.setProperty("--tab-color", t.color);
    b.onclick = () => { state.topic = t.id; state.section = "all"; state.team = null; state.league = null; state.view = "feed"; state.q = ""; $("#q").value = ""; render(); renderTabs(); };
    nav.append(b);
  }
  setAccent(state.view === "saved" ? "#f59e0b" : topicCfg().color);
}
function chip(label, active, onclick, extra = {}) {
  const c = el("button", "chip" + (active ? " active" : "") + (extra.cls ? " " + extra.cls : ""),
    (extra.color ? `<span class="sw"></span>` : "") + esc(label));
  if (extra.color) c.style.setProperty("--c", extra.color);
  c.onclick = onclick; return c;
}
function renderSubbar() {
  const bar = $("#subbar"); bar.innerHTML = "";
  if (state.view !== "feed") return;
  const t = topicCfg();
  const row1 = el("div", "chips");
  row1.append(chip("הכל", state.section === "all", () => { state.section = "all"; render(); }));
  for (const s of t.sections) row1.append(chip(s.name, state.section === s.id, () => { state.section = s.id; render(); }));
  bar.append(row1);
  if (t.teams?.length) {
    const row2 = el("div", "chips");
    row2.append(el("span", "chips-label", "הקבוצות שלי"));
    for (const tm of t.teams) row2.append(chip(tm.name, state.team === tm.id, () => { state.team = state.team === tm.id ? null : tm.id; state.league = null; render(); }, { color: tm.color, cls: "team" }));
    bar.append(row2);
  }
  if (t.leagues?.length) {
    const row3 = el("div", "chips");
    row3.append(el("span", "chips-label", "ליגות"));
    for (const lg of t.leagues) row3.append(chip(lg.name, state.league === lg.id, () => { state.league = state.league === lg.id ? null : lg.id; state.team = null; render(); }));
    bar.append(row3);
  }
}

/* ---------- ticker ---------- */
function renderTicker() {
  const box = $("#ticker"), track = $("#tickerTrack");
  const items = (state.data[state.topic] || []).filter(a => a.ticker).slice(0, 25);
  if (state.view !== "feed" || !items.length) { box.hidden = true; return; }
  box.hidden = false; track.innerHTML = "";
  const frag = document.createDocumentFragment();
  for (let k = 0; k < 2; k++) for (const a of items) {
    const it = el("a", "tick-item", `<time>${hhmm(a.published)}</time><span>${esc(a.title)}</span><span class="sep"></span>`);
    it.href = a.url; it.target = "_blank"; it.rel = "noopener"; frag.append(it);
  }
  track.append(frag);
  track.style.setProperty("--dur", Math.max(40, items.length * 6) + "s");
}

/* ---------- feed ---------- */
function visibleArticles() {
  let arts;
  if (state.view === "saved") arts = Object.values(state.saved).sort((a, b) => (b.saved_at || "").localeCompare(a.saved_at || ""));
  else if (state.q.trim()) arts = state.cfg.topics.flatMap(t => state.data[t.id] || []).filter(a => isPrimary(a) && matches(a, state.q)).sort((a, b) => b.published.localeCompare(a.published));
  else {
    arts = (state.data[state.topic] || []).filter(a => isPrimary(a) && !a.ticker);
    if (state.section !== "all") arts = arts.filter(a => a.section === state.section);
    if (state.team) arts = arts.filter(a => a.tags?.teams?.includes(state.team));
    if (state.league) arts = arts.filter(a => a.tags?.leagues?.includes(state.league));
  }
  return arts;
}
function render() {
  renderSubbar(); renderTicker();
  const feed = $("#feed"); feed.innerHTML = "";
  const arts = visibleArticles();
  $("#qCount").textContent = state.q.trim() ? `${arts.length} תוצאות` : "";
  location.hash = state.view === "saved" ? "saved" : state.topic + (state.section !== "all" ? "/" + state.section : "");
  if (!arts.length) {
    feed.append(el("div", "empty", state.view === "saved" ? "<b>🔖</b>עדיין לא שמרת ידיעות. לחיצה על הסימנייה בכרטיס שומרת אותו כאן." :
      state.q ? "<b>🔍</b>לא נמצאו ידיעות." : "<b>📭</b>אין ידיעות להצגה כאן כרגע."));
    return;
  }
  let i = 0;
  const t = topicCfg();
  if (state.view === "feed" && !state.q && !state.team && !state.league && t.teams?.length) {
    const spot = arts.filter(a => a.tags?.teams?.length).slice(0, 10);
    if (spot.length) feed.append(renderSpotlight(spot));
  }
  const heroIdx = arts.findIndex(a => a.image);
  if (heroIdx >= 0 && state.view === "feed" && !state.q) { const a = arts.splice(heroIdx, 1)[0]; feed.append(card(a, i++, true)); }
  let lastDay = null;
  for (const a of arts) {
    if (state.view === "feed" && !state.q) {
      const day = dayLabel(a.published);
      if (day !== lastDay && lastDay !== null) feed.append(el("div", "section-title", esc(day)));
      lastDay = day;
    }
    feed.append(card(a, i++));
  }
}
function dayLabel(iso) {
  const d = new Date(iso), now = new Date();
  const same = (x, y) => x.toDateString() === y.toDateString();
  if (same(d, now)) return "היום";
  const y = new Date(now); y.setDate(y.getDate() - 1);
  if (same(d, y)) return "אתמול";
  return d.toLocaleDateString("he-IL", { weekday: "long", day: "numeric", month: "long" });
}
function renderSpotlight(items) {
  const w = el("section", "spot");
  w.append(el("div", "spot-head", `הקבוצות שלי <small>הידיעות האחרונות על מכבי חיפה, מילאן, ברצלונה ויונייטד</small>`));
  const row = el("div", "spot-row");
  for (const a of items) {
    const tm = teamOf(a);
    const m = el("article", "mini");
    m.style.setProperty("--c", tm?.color || "var(--accent)");
    m.innerHTML = (a.image ? `<img src="${esc(a.image)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : "") +
      `<div class="ov"><span class="team-badge">${esc(tm?.short || "")}</span><b>${esc(title(a))}</b><span class="when">${esc(a.source_name)} · ${ago(a.published)}</span></div>`;
    m.onclick = () => openReader(a);
    row.append(m);
  }
  w.append(row); return w;
}
function card(a, i, hero = false) {
  const c = el("article", "card" + (hero ? " hero" : ""));
  c.style.setProperty("--i", Math.min(i, 12));
  const t = state.cfg.topics.find(x => x.id === a.topic);
  const media = el("div", "media");
  if (a.image) {
    const img = el("img"); img.src = a.image; img.alt = ""; img.loading = hero ? "eager" : "lazy"; img.referrerPolicy = "no-referrer";
    img.onerror = () => { img.remove(); media.append(el("div", "ph", t.icon)); };
    media.append(img);
  } else media.append(el("div", "ph", t.icon));
  media.append(el("span", "src-chip", esc(a.source_name)));
  const others = (a.cluster_sources || []).filter(s => s !== a.source_name);
  const extraSrc = others.length ? `<span class="more" title="${esc(others.join(", "))}">+${others.length} מקורות</span>` : "";
  const pend = a.lang !== "he" && !a.he ? `<span class="pending">ממתין לתרגום</span>` : "";
  const topicPill = (state.q || state.view === "saved") ? `<span class="topic-pill" style="--tc:${t.color}">${t.icon} ${esc(t.name)}</span>` : "";
  const body = el("div", "card-body",
    `<div class="meta">${topicPill}<span>${ago(a.published)}</span>${extraSrc}${pend}</div>
     <h3>${esc(title(a))}</h3><p>${esc(summary(a))}</p>`);
  const foot = el("div", "card-foot");
  const tm = teamOf(a); if (tm) { const tg = el("span", "tag team", esc(tm.name)); tg.style.setProperty("--c", tm.color); foot.append(tg); }
  for (const lid of (a.tags?.leagues || []).slice(0, 2)) { const lg = (t.leagues || []).find(x => x.id === lid); if (lg) foot.append(el("span", "tag", esc(lg.name))); }
  if (a.official) foot.append(el("span", "tag", "הודעה רשמית"));
  const sv = el("button", "save-btn" + (state.saved[a.id] ? " on" : ""), state.saved[a.id] ? ICONS.bookmarkOn : ICONS.bookmark);
  sv.title = "שמירה"; sv.onclick = e => { e.stopPropagation(); toggleSave(a); sv.className = "save-btn" + (state.saved[a.id] ? " on" : ""); sv.innerHTML = state.saved[a.id] ? ICONS.bookmarkOn : ICONS.bookmark; if (state.view === "saved") render(); };
  foot.append(sv); body.append(foot);
  c.append(media, body);
  c.onclick = () => openReader(a);
  return c;
}

/* ---------- saved ---------- */
function toggleSave(a) {
  if (state.saved[a.id]) delete state.saved[a.id]; else state.saved[a.id] = { ...a, saved_at: new Date().toISOString() };
  store("saved", state.saved); updateSavedBadge();
}
function updateSavedBadge() { const n = Object.keys(state.saved).length; const b = $("#savedCount"); b.hidden = !n; b.textContent = n; $("#btnSaved").classList.toggle("on", state.view === "saved"); }

/* ---------- reader ---------- */
let current = null;
async function openReader(a) {
  current = a;
  const r = $("#reader"), body = $("#readerBody");
  r.hidden = false; $("#scrim").hidden = false; document.body.style.overflow = "hidden";
  $("#btnReaderOpen").href = a.url;
  const paintSave = () => { $("#btnReaderSave").innerHTML = state.saved[a.id] ? ICONS.bookmarkOn : ICONS.bookmark; $("#btnReaderSave").classList.toggle("on", !!state.saved[a.id]); };
  paintSave(); $("#btnReaderSave").onclick = () => { toggleSave(a); paintSave(); render(); };
  const t = state.cfg.topics.find(x => x.id === a.topic);
  const cluster = (state.data[a.topic] || []).filter(x => x.cluster === a.cluster && x.id !== a.id);
  body.innerHTML = (a.image ? `<div class="r-media"><img src="${esc(a.image)}" alt="" referrerpolicy="no-referrer" onerror="this.parentNode.remove()"></div>` : "") +
    `<div class="r-wrap">
      <div class="r-meta"><span class="src">${esc(a.source_name)}</span><span>·</span><span>${ago(a.published)}</span><span>·</span><span>${new Date(a.published).toLocaleString("he-IL", { dateStyle: "medium", timeStyle: "short" })}</span></div>
      <h1>${esc(title(a))}</h1>
      ${summary(a) ? `<p class="r-lead">${esc(summary(a))}</p>` : ""}
      <div id="rText"><div class="skeleton" style="width:90%"></div><div class="skeleton"></div><div class="skeleton" style="width:70%"></div></div>
    </div>`;
  body.scrollTop = 0;
  let b = null;
  if (a.has_body || (a.lang !== "he" && a.he)) {
    try { b = state.bodies[a.id] || (state.bodies[a.id] = await getJSON(`data/body/${a.id}.json`)); } catch { b = null; }
  }
  if (current !== a) return;
  const box = $("#rText"); if (!box) return;
  const paras = s => (s || "").split(/\n{2,}|\n/).map(p => p.trim()).filter(Boolean).map(p => `<p>${esc(p)}</p>`).join("");
  let html = "";
  if (a.lang !== "he") {
    if (b?.digest_he) html += `<div class="r-text">${paras(b.digest_he)}</div><div class="r-note">תקציר בעברית שנוצר אוטומטית מהכתבה המקורית. לדיוק מלא, הכתבה במקור למטה.</div>`;
    else if (a.he) html += `<div class="r-note">התקציר המלא בעברית עדיין בהכנה. הכותרת והתקציר הקצר כבר תורגמו.</div>`;
    else html += `<div class="r-note">הידיעה עדיין לא תורגמה. התרגום מגיע בעדכון הבא.</div>`;
    if (b?.text) html += `<details class="orig"><summary>הכתבה המקורית באנגלית</summary><div class="r-text ltr">${paras(b.text)}</div></details>`;
    else if (!a.he) html += `<div class="r-text ltr"><p>${esc(a.summary)}</p></div>`;
  } else {
    if (b?.text) html += `<div class="r-text">${paras(b.text)}</div>`;
    else html += `<div class="r-note">${a.no_body ? "המקור הזה מספק כותרת ותקציר בלבד." : "לא ניתן היה לשלוף את הכתבה המלאה מהאתר."} הכתבה המלאה בלינק למטה.</div>`;
  }
  html += `<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:6px"><a class="btn primary" href="${esc(a.url)}" target="_blank" rel="noopener">${ICONS.ext} לכתבה המקורית ב-${esc(a.source_name)}</a></div>`;
  if (cluster.length) html += `<div class="r-sep">אותה ידיעה במקורות נוספים</div><div class="also">` +
    cluster.map(x => `<a href="${esc(x.url)}" target="_blank" rel="noopener"><b>${esc(x.source_name)}</b><span>${esc(title(x))}</span></a>`).join("") + `</div>`;
  box.outerHTML = html;
}
function closeReader() { current = null; $("#reader").hidden = true; $("#scrim").hidden = $("#status").hidden; document.body.style.overflow = ""; }

/* ---------- status ---------- */
function openStatus() {
  const m = state.meta; const b = $("#statusBody"); b.innerHTML = "";
  if (!m) { b.textContent = "אין עדיין נתוני ריצה."; } else {
    const tr = m.translate || {};
    b.append(el("div", "st-sum", `ריצה אחרונה: ${new Date(m.updated).toLocaleString("he-IL")} · ${m.seconds} שניות<br>ידיעות חדשות: ${m.new} · כתבות מלאות שנשלפו: ${m.extracted} · קבוצות כפילות: ${m.clusters}<br>תרגום: ${tr.translated ?? 0} ידיעות ב-${tr.requests ?? 0} בקשות, ${tr.tokens ?? 0} טוקנים · ממתינות: ${tr.pending_after ?? 0}`));
    for (const t of state.cfg.topics) {
      b.append(el("div", "section-title", esc(t.name)));
      for (const s of t.sources) {
        const st = (m.sources || []).find(x => x.id === s.id) || {};
        b.append(el("div", "st-row", `<span class="ok${st.ok ? "" : " bad"}"></span><span>${esc(s.name)}${st.error ? `<span class="err">${esc(st.error)}</span>` : ""}</span><span class="n">${st.count ?? "-"}</span>`));
      }
    }
  }
  $("#status").hidden = false; $("#scrim").hidden = false;
}
function closeStatus() { $("#status").hidden = true; $("#scrim").hidden = $("#reader").hidden; }

/* ---------- events ---------- */
$("#btnTheme").onclick = () => applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
$("#btnSearch").onclick = () => { const r = $("#searchRow"); r.hidden = !r.hidden; if (!r.hidden) $("#q").focus(); else { state.q = ""; $("#q").value = ""; render(); } };
$("#btnCloseSearch").onclick = () => { $("#searchRow").hidden = true; state.q = ""; $("#q").value = ""; render(); };
let qt; $("#q").oninput = e => { clearTimeout(qt); qt = setTimeout(() => { state.q = e.target.value; state.view = "feed"; render(); }, 160); };
$("#btnSaved").onclick = () => { state.view = state.view === "saved" ? "feed" : "saved"; state.q = ""; $("#q").value = ""; renderTabs(); render(); updateSavedBadge(); };
$("#brand").onclick = e => { e.preventDefault(); state.view = "feed"; state.section = "all"; state.team = null; state.league = null; state.q = ""; $("#q").value = ""; renderTabs(); render(); updateSavedBadge(); window.scrollTo({ top: 0, behavior: "smooth" }); };
$("#btnCloseReader").onclick = closeReader; $("#btnStatus").onclick = openStatus; $("#btnCloseStatus").onclick = closeStatus;
$("#scrim").onclick = () => { closeReader(); closeStatus(); };
document.addEventListener("keydown", e => { if (e.key === "Escape") { closeReader(); closeStatus(); } });
window.addEventListener("hashchange", () => {
  const h = location.hash.replace("#", "").split("/");
  if (h[0] === "saved") { if (state.view !== "saved") { state.view = "saved"; renderTabs(); render(); updateSavedBadge(); } return; }
  const t = state.cfg?.topics.find(x => x.id === h[0]); if (!t) return;
  const sec = h[1] || "all";
  if (t.id !== state.topic || sec !== state.section || state.view !== "feed") { state.topic = t.id; state.section = sec; state.view = "feed"; state.team = null; state.league = null; renderTabs(); render(); updateSavedBadge(); }
});

boot().catch(err => { $("#feed").innerHTML = `<div class="empty"><b>⚠️</b>טעינת הנתונים נכשלה.<br><small>${esc(err.message)}</small></div>`; });
})();
