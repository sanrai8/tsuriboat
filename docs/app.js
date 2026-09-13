// 若狭釣果まとめ v0.3.0
// data/catches.json を読み、エリア・魚種で絞り込んで日別に表示する。

const AREA_GROUPS = [
  { key: "all", label: "すべて", match: () => true },
  { key: "tsuruga", label: "敦賀", match: a => a.startsWith("敦賀") },
  { key: "obama", label: "小浜", match: a => a.startsWith("小浜") },
  { key: "kyoto", label: "京都", match: a => a.startsWith("京都") },
];

const SPECIES_GROUPS = [
  { key: "all", label: "全魚種", match: () => true },
  { key: "kensaki", label: "ケンサキイカ", match: s => s === "ケンサキイカ" },
  { key: "aori", label: "アオリイカ", match: s => s === "アオリイカ" },
  { key: "surume", label: "スルメイカ", match: s => s === "スルメイカ" },
  { key: "fish", label: "魚", match: s => !/イカ$/.test(s) },
];

const state = { area: "all", species: "all", data: null };

// ---------- helpers ----------
const $ = sel => document.querySelector(sel);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};
const DOW = ["日", "月", "火", "水", "木", "金", "土"];

// 端末のタイムゾーンに依存しないよう、日付文字列を直接分解する
function fmtDate(iso) {
  if (!iso) return { md: "日付不明", dow: "" };
  const [y, m, d] = iso.split("-").map(Number);
  return { md: `${m}/${d}`, dow: DOW[new Date(Date.UTC(y, m - 1, d)).getUTCDay()] };
}
function daysAgo(iso) {
  if (!iso) return 999;
  const [y, m, d] = iso.split("-").map(Number);
  const todayJst = new Date(Date.now() + 9 * 3600000);
  const t0 = Date.UTC(todayJst.getUTCFullYear(), todayJst.getUTCMonth(), todayJst.getUTCDate());
  return Math.floor((t0 - Date.UTC(y, m - 1, d)) / 86400000);
}
function countText(sp) {
  if (sp.min != null && sp.max != null && sp.min !== sp.max) return `${sp.min}〜${sp.max}`;
  if (sp.max != null) return `${sp.max}`;
  if (sp.min != null) return `${sp.min}`;
  if (sp.total != null) return `船中${sp.total}`;
  return null;
}
function unit(name) { return /イカ$|イカ$/.test(name) ? "杯" : "匹"; }

// ---------- filtering ----------
function speciesMatch(c) {
  const g = SPECIES_GROUPS.find(g => g.key === state.species);
  if (g.key === "all") return true;
  return (c.species || []).some(s => g.match(s.name));
}
function filtered() {
  const ag = AREA_GROUPS.find(g => g.key === state.area);
  return state.data.catches.filter(c => ag.match(c.area || "") && speciesMatch(c));
}

// ---------- render ----------
function renderChips(containerId, groups, key) {
  const box = $(containerId);
  box.innerHTML = "";
  groups.forEach(g => {
    const b = el("button", "chip", g.label);
    b.setAttribute("aria-pressed", String(state[key] === g.key));
    b.addEventListener("click", () => { state[key] = g.key; render(); });
    box.appendChild(b);
  });
}

function primarySpecies(c) {
  // フィルタ中の魚種を優先、なければ最大値をもつ魚種
  const g = SPECIES_GROUPS.find(g => g.key === state.species);
  const all = (c.species || []).filter(s => s && s.name);
  if (g.key !== "all") {
    // フィルタ中は他魚種で埋めず、その魚種を数値なしでも表示する
    return all.filter(s => g.match(s.name)).sort((a, b) => (b.max ?? b.total ?? -1) - (a.max ?? a.total ?? -1))[0] || null;
  }
  return all.filter(s => countText(s)).sort((a, b) => (b.max ?? b.total ?? 0) - (a.max ?? a.total ?? 0))[0] || null;
}

function renderLatest(list) {
  const box = $("#boat-latest");
  box.innerHTML = "";
  const byBoat = new Map();
  list.forEach(c => { if (!byBoat.has(c.boat_key)) byBoat.set(c.boat_key, c); });
  const items = [...byBoat.values()].sort((a, b) => (b.trip_date || "").localeCompare(a.trip_date || ""));
  $("#tonight").hidden = items.length === 0;
  items.forEach(c => {
    const li = el("li");
    if (daysAgo(c.trip_date) > 7) li.classList.add("stale");
    li.appendChild(el("span", "name", c.boat_name));
    const d = fmtDate(c.trip_date);
    li.appendChild(el("span", "when", `${d.md}（${d.dow}）${c.trip_type ? " " + c.trip_type : ""}`));
    const sp = primarySpecies(c);
    const num = el("span", "num");
    if (sp) {
      const n = countText(sp);
      num.textContent = n || "—";
      const small = el("small", null, n ? `${unit(sp.name)} ${sp.name}` : `${sp.name}（数不明）`);
      num.appendChild(small);
    } else {
      num.textContent = "—";
    }
    li.appendChild(num);
    box.appendChild(li);
  });
}

function renderDays(list) {
  const box = $("#days");
  box.innerHTML = "";
  $("#empty").hidden = list.length > 0;
  const maxTop = Math.max(1, ...list.map(c => c.top_count || 0));

  const byDay = new Map();
  list.forEach(c => {
    const k = c.trip_date || "unknown";
    if (!byDay.has(k)) byDay.set(k, []);
    byDay.get(k).push(c);
  });

  [...byDay.entries()].sort((a, b) => b[0].localeCompare(a[0])).forEach(([day, items]) => {
    const li = el("li", "day");
    const h = el("h3");
    const d = fmtDate(day === "unknown" ? null : day);
    h.appendChild(el("span", null, d.md));
    if (d.dow) h.appendChild(el("span", "dow", d.dow));
    li.appendChild(h);
    const ul = el("ul");
    items.forEach(c => ul.appendChild(renderCatch(c, maxTop)));
    li.appendChild(ul);
    box.appendChild(li);
  });
}

function renderCatch(c, maxTop) {
  const a = el("a", "catch");
  a.href = c.url; a.target = "_blank"; a.rel = "noopener";
  if (c.top_count) a.style.setProperty("--bar", `${Math.round((c.top_count / maxTop) * 100)}%`);

  const row1 = el("div", "row1");
  const boat = el("span", "boat", c.boat_name);
  boat.appendChild(el("span", "area", c.area));
  row1.appendChild(boat);
  if (c.trip_type) row1.appendChild(el("span", "trip", c.trip_type));
  a.appendChild(row1);

  const sps = (c.species || []).filter(s => s && s.name);
  if (sps.length) {
    const row = el("div", "species");
    sps.forEach(s => {
      const span = el("span", "sp");
      const n = countText(s);
      if (n) {
        span.appendChild(el("b", null, n));
        span.appendChild(el("small", null, unit(s.name) + " "));
      }
      span.appendChild(document.createTextNode(s.name));
      if (s.size_note) span.appendChild(el("small", null, `（${s.size_note}）`));
      row.appendChild(span);
    });
    a.appendChild(row);
  }
  if (c.summary) a.appendChild(el("div", "summary", c.summary));
  const meta = [];
  if (c.methods && c.methods.length) meta.push(c.methods.join(" / "));
  if (c.condition) meta.push(c.condition);
  if (meta.length) a.appendChild(el("div", "methods", meta.join("　")));
  return a;
}

// ---------- 推移グラフ ----------
const PALETTE = ["#FFD166", "#7DE0A5", "#6EC1FF", "#FF8FA3", "#C89BFF", "#FFB26E", "#8EE3E0", "#E0D68A", "#B0B8FF", "#F5A3FF"];
const TREND_DAYS = 14;

function trendValue(c) {
  // フィルタ中の魚種の max（未指定なら top_count → 最大 max）
  const g = SPECIES_GROUPS.find(g => g.key === state.species);
  const list = (c.species || []).filter(s => s && s.max != null);
  if (g.key !== "all") {
    const hit = list.find(s => g.match(s.name));
    return hit ? hit.max : null;
  }
  if (c.top_count != null) return c.top_count;
  return list.length ? Math.max(...list.map(s => s.max)) : null;
}

function renderTrend(list) {
  const box = $("#chart"), legend = $("#legend");
  box.innerHTML = ""; legend.innerHTML = "";
  const g = SPECIES_GROUPS.find(g => g.key === state.species);
  $("#trend-title").textContent = `${g.key === "all" ? "竿頭" : g.label + " 竿頭"}の推移（直近${TREND_DAYS}日）`;

  const pts = list
    .map(c => ({ c, v: trendValue(c), d: daysAgo(c.trip_date) }))
    .filter(p => p.v != null && p.d >= 0 && p.d < TREND_DAYS);
  const boats = [...new Set(pts.map(p => p.c.boat_key))];
  $("#trend").hidden = pts.length < 2;
  if (pts.length < 2) return;

  const W = 360, H = 170, L = 28, R = 8, T = 8, B = 22;
  const maxV = Math.max(10, ...pts.map(p => p.v));
  const yTick = maxV <= 20 ? 5 : maxV <= 50 ? 10 : maxV <= 100 ? 20 : 50;
  const yMax = Math.ceil(maxV / yTick) * yTick;
  const x = d => L + ((TREND_DAYS - 1 - d) / (TREND_DAYS - 1)) * (W - L - R);
  const y = v => T + (1 - v / yMax) * (H - T - B);

  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${$("#trend-title").textContent}">`;
  for (let v = 0; v <= yMax; v += yTick) {
    svg += `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/>`;
    svg += `<text class="axis" x="${L - 4}" y="${y(v) + 3}" text-anchor="end">${v}</text>`;
  }
  for (let d = 0; d < TREND_DAYS; d += (TREND_DAYS > 10 ? 2 : 1)) {
    const dt = new Date(Date.now() + 9 * 3600000 - d * 86400000);
    svg += `<text class="axis" x="${x(d)}" y="${H - 6}" text-anchor="middle">${dt.getUTCMonth() + 1}/${dt.getUTCDate()}</text>`;
  }
  boats.forEach((bk, i) => {
    const color = PALETTE[i % PALETTE.length];
    const series = pts.filter(p => p.c.boat_key === bk).sort((a, b) => b.d - a.d);
    if (series.length > 1) {
      svg += `<polyline class="series" stroke="${color}" points="${series.map(p => `${x(p.d)},${y(p.v)}`).join(" ")}"/>`;
    }
    series.forEach(p => { svg += `<circle class="pt" cx="${x(p.d)}" cy="${y(p.v)}" r="3.5" fill="${color}"><title>${p.c.boat_name} ${fmtDate(p.c.trip_date).md} ${p.v}</title></circle>`; });
    const li = el("li"); const dot = el("i"); dot.style.background = color;
    li.appendChild(dot); li.appendChild(document.createTextNode(series[0].c.boat_name));
    legend.appendChild(li);
  });
  svg += "</svg>";
  box.innerHTML = svg;
}

function renderLinkOnly() {
  const ag = AREA_GROUPS.find(g => g.key === state.area);
  const boats = (state.data.boats || []).filter(b => b.link_only && b.home && ag.match(b.area || ""));
  const box = $("#linkonly-list");
  box.innerHTML = "";
  $("#linkonly").hidden = boats.length === 0;
  boats.forEach(b => {
    const li = el("li");
    const link = el("a", null, b.name);
    link.href = b.home; link.target = "_blank"; link.rel = "noopener";
    link.appendChild(el("span", "area", b.area));
    li.appendChild(link);
    box.appendChild(li);
  });
}

function render() {
  renderChips("#area-chips", AREA_GROUPS, "area");
  renderChips("#species-chips", SPECIES_GROUPS, "species");
  const list = filtered();
  renderLatest(list);
  renderTrend(list);
  renderDays(list);
  renderLinkOnly();
}

// ---------- boot ----------
async function load() {
  try {
    const r = await fetch(`data/catches.json?t=${Date.now()}`, { cache: "no-store" });
    if (!r.ok) throw new Error(r.status);
    state.data = await r.json();
    const g = state.data.generated_at ? new Date(state.data.generated_at) : null;
    $("#updated").textContent = g
      ? "更新 " + g.toLocaleString("ja-JP", { timeZone: "Asia/Tokyo", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })
        + (state.data.sample ? "（サンプルデータ）" : "")
      : "未更新";
    render();
  } catch (e) {
    $("#updated").textContent = "データを読み込めませんでした";
    $("#empty").hidden = false;
  }
}

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}
load();
