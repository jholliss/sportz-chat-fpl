const DATA = {};
const MANAGER_COLORS = {};
const CHARTS = {};

async function fetchJSON(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  return res.json();
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function sortedManagerIds() {
  return Object.keys(DATA.managers).sort((a, b) =>
    DATA.managers[a].name.localeCompare(DATA.managers[b].name)
  );
}

function assignManagerColors() {
  sortedManagerIds().forEach((id, i) => {
    MANAGER_COLORS[id] = cssVar(`--m${(i % 9) + 1}`);
  });
}

function colorFor(managerId) {
  return MANAGER_COLORS[managerId] || cssVar("--text-muted");
}

function fmtNum(n) {
  if (n === null || n === undefined) return "–";
  return Number(n).toLocaleString();
}

function fmtSigned(n) {
  if (n === null || n === undefined) return "–";
  const sign = n > 0 ? "+" : "";
  return `${sign}${Number(n).toLocaleString()}`;
}

function fmtPct(p) {
  if (p === null || p === undefined) return "–";
  return (p * 100).toFixed(2) + "%";
}

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  Object.entries(props).forEach(([k, v]) => {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else node.setAttribute(k, v);
  });
  children.forEach((c) => node.appendChild(c));
  return node;
}

/* ---------- generic mobile-friendly rank list ---------- */
function renderRankList(containerId, items, opts) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";
  if (!items || items.length === 0) {
    container.appendChild(
      el("li", { class: "empty-state", text: opts.emptyMessage || "No data yet" })
    );
    return;
  }
  items.forEach((item, i) => {
    const li = el("li");
    const main = el("div", { class: "rank-main" });
    if (opts.numbered) main.appendChild(el("span", { class: "rank-num", text: String(i + 1) }));
    const nameWrap = el("div");
    nameWrap.appendChild(el("div", { class: "rank-name", text: opts.name(item) }));
    if (opts.sub) {
      const subText = opts.sub(item);
      if (subText) nameWrap.appendChild(el("div", { class: "rank-sub", text: subText }));
    }
    main.appendChild(nameWrap);
    li.appendChild(main);
    li.appendChild(el("span", { class: "rank-value", text: opts.value(item) }));
    container.appendChild(li);
  });
}

function emptyChartMessage(canvasId, message) {
  const wrap = document.getElementById(canvasId).closest(".chart-wrap");
  wrap.outerHTML = `<p class="empty-state">${message}</p>`;
}

/* ---------- chart helpers ---------- */
function chartDefaults() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "nearest", intersect: false },
    plugins: {
      legend: { labels: { color: cssVar("--text-secondary"), usePointStyle: true, boxWidth: 8, font: { size: 11 } } },
      tooltip: { mode: "index", intersect: false },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: cssVar("--text-muted"), font: { size: 10 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
      y: { grid: { color: cssVar("--gridline") }, ticks: { color: cssVar("--text-muted"), font: { size: 10 } } },
    },
  };
}

function makeLineChart(canvasId, labels, datasets, opts = {}) {
  const ctx = document.getElementById(canvasId);
  if (CHARTS[canvasId]) CHARTS[canvasId].destroy();
  const defaults = chartDefaults();
  CHARTS[canvasId] = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      ...defaults,
      scales: { ...defaults.scales, y: { ...defaults.scales.y, reverse: !!opts.reverseY } },
      plugins: { ...defaults.plugins, legend: { ...defaults.plugins.legend, display: datasets.length > 1 && datasets.length <= 3 } },
    },
  });
}

function makeStackedBarChart(canvasId, labels, datasets) {
  const ctx = document.getElementById(canvasId);
  if (CHARTS[canvasId]) CHARTS[canvasId].destroy();
  const defaults = chartDefaults();
  CHARTS[canvasId] = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets },
    options: {
      ...defaults,
      scales: {
        x: { ...defaults.scales.x, stacked: true },
        y: { ...defaults.scales.y, stacked: true },
      },
    },
  });
}

function resizeAllCharts() {
  Object.values(CHARTS).forEach((chart) => chart.resize());
}

/* ---------- manager-picker line chart (shared pattern) ---------- */
function setupManagerPickerChart({ pickerId, canvasId, seriesByManager, valueKey, reverseY }) {
  const picker = document.getElementById(pickerId);
  const managerIds = sortedManagerIds().filter((mid) => seriesByManager[mid]);
  picker.innerHTML = '<option value="__all__">All managers</option>';
  managerIds.forEach((mid) => picker.appendChild(el("option", { value: mid, text: DATA.managers[mid].name })));

  function draw() {
    const selected = picker.value;
    const ids = selected === "__all__" ? managerIds : [selected];
    if (!ids.length || !seriesByManager[ids[0]] || seriesByManager[ids[0]].length === 0) {
      emptyChartMessage(canvasId, "No gameweeks played yet.");
      return;
    }
    const labels = seriesByManager[ids[0]].map((p) => `GW${p.gw}`);
    const datasets = ids.map((mid) => ({
      label: DATA.managers[mid].name,
      data: seriesByManager[mid].map((p) => p[valueKey]),
      borderColor: colorFor(mid),
      backgroundColor: colorFor(mid),
      borderWidth: 2,
      pointRadius: 0,
    }));
    makeLineChart(canvasId, labels, datasets, { reverseY });
  }
  picker.addEventListener("change", draw);
  if (managerIds.length) draw();
  else emptyChartMessage(canvasId, "No gameweeks played yet.");
}

/* ---------- navigation ---------- */
function initNav() {
  const tabButtons = document.querySelectorAll("nav.bottom-tabs button");
  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabButtons.forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
      window.scrollTo({ top: 0 });
      resizeAllCharts();
    });
  });

  const pillButtons = document.querySelectorAll("nav.pill-tabs button");
  pillButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      pillButtons.forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".sub-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`sub-${btn.dataset.sub}`).classList.add("active");
      resizeAllCharts();
    });
  });
}

/* ---------- Home ---------- */
function renderHome() {
  renderRankList(
    "league-table",
    DATA.standings,
    {
      numbered: true,
      name: (r) => r.name,
      sub: (r) => r.team_name,
      value: (r) => fmtNum(r.total),
      emptyMessage: "Season hasn't started yet — check back once gameweek 1 completes.",
    }
  );

  const f = DATA.derived.form;
  renderRankList("home-in-form", f.in_form, { name: (r) => r.name, value: (r) => fmtNum(r.value) });
  renderRankList("home-in-freefall", f.in_freefall, { name: (r) => r.name, value: (r) => fmtNum(r.value) });
}

/* ---------- Season: Form ---------- */
function renderForm() {
  const f = DATA.derived.form;
  renderRankList("sound-spenders", f.sound_spenders, { name: (r) => r.name, value: (r) => fmtNum(r.value) });
  renderRankList("spend-thrifts", f.spend_thrifts, { name: (r) => r.name, value: (r) => fmtNum(r.value) });
  renderRankList("tactical-masters", f.tactical_masters, { name: (r) => r.name, value: (r) => fmtNum(r.value) });
  renderRankList("rotation-losers", f.rotation_losers, { name: (r) => r.name, value: (r) => fmtNum(r.value) });
}

/* ---------- Season: Bench ---------- */
function renderBench() {
  renderRankList("adjusted-table", DATA.derived.adjusted_table, {
    numbered: true,
    name: (r) => r.name,
    sub: (r) => `Total ${fmtNum(r.total_points)} · Jammy ${fmtSigned(r.jammy_delta)}`,
    value: (r) => fmtNum(r.total_plus_bench),
  });

  setupManagerPickerChart({
    pickerId: "bench-manager-picker",
    canvasId: "chart-bench-by-week",
    seriesByManager: DATA.derived.points_on_bench_by_week,
    valueKey: "points_on_bench",
  });
}

/* ---------- Season: Transfers ---------- */
function renderTransfers() {
  renderRankList("transfers-summary", DATA.derived.transfers_summary.summary, {
    name: (r) => r.name,
    sub: (r) => `${r.transfer_count} transfers`,
    value: (r) => fmtSigned(r.total_net_points),
  });

  const transferOpts = {
    name: (r) => r.name,
    sub: (r) => `GW${r.gw}: ${r.player_in_name} for ${r.player_out_name}`,
    value: (r) => fmtSigned(r.net_points),
    emptyMessage: "No transfer data yet.",
  };
  renderRankList("best-transfers", DATA.derived.transfers_summary.best_transfers, transferOpts);
  renderRankList("worst-transfers", DATA.derived.transfers_summary.worst_transfers, transferOpts);
}

/* ---------- Season: Chips ---------- */
function renderChips() {
  const stacked = DATA.derived.chip_usage.stacked_by_manager;
  const managerIds = Object.keys(stacked).sort((a, b) => stacked[a].name.localeCompare(stacked[b].name));
  if (managerIds.length) {
    const allChipLabels = [...new Set(managerIds.flatMap((mid) => Object.keys(stacked[mid].chips)))];
    const palette = ["--m1", "--m2", "--m3", "--m4", "--m5"];
    const datasets = allChipLabels.map((chipLabel, i) => ({
      label: chipLabel,
      data: managerIds.map((mid) => stacked[mid].chips[chipLabel] || 0),
      backgroundColor: cssVar(palette[i % palette.length]),
    }));
    makeStackedBarChart(
      "chart-chip-usage",
      managerIds.map((mid) => stacked[mid].name),
      datasets
    );
  } else {
    emptyChartMessage("chart-chip-usage", "No chips played yet.");
  }

  renderRankList("top10-chips", DATA.derived.chip_usage.top_10_chips, {
    name: (r) => r.name,
    sub: (r) => r.chip_label,
    value: (r) => fmtNum(r.points),
  });
  renderRankList("tc-points", DATA.derived.chip_usage.triple_captain_points, {
    name: (r) => r.name,
    sub: (r) => `GW${r.gw}`,
    value: (r) => fmtNum(r.points),
    emptyMessage: "No Triple Captain plays yet.",
  });
}

/* ---------- Season: Captaincy ---------- */
function renderCaptaincy() {
  renderRankList("captaincy-summary", DATA.derived.captaincy.summary, {
    name: (r) => r.name,
    sub: (r) => `Picked best ${r.picked_best_captain_weeks}× · ${fmtSigned(r.gain_loss_vs_optimal)} vs optimal`,
    value: (r) => fmtNum(r.total_captain_points),
  });

  setupManagerPickerChart({
    pickerId: "captaincy-manager-picker",
    canvasId: "chart-captaincy",
    seriesByManager: DATA.derived.captaincy.series,
    valueKey: "captain_points",
  });
}

/* ---------- Season: Vs Average ---------- */
function renderAverage() {
  setupManagerPickerChart({
    pickerId: "average-manager-picker",
    canvasId: "chart-vs-average",
    seriesByManager: DATA.derived.vs_average.series,
    valueKey: "vs_average",
  });

  const summary = DATA.derived.vs_average.summary;
  const crusher = [...summary].sort((a, b) => b.weeks_beat_average - a.weeks_beat_average).slice(0, 5);
  const crushed = [...summary].sort((a, b) => b.weeks_lost_to_average - a.weeks_lost_to_average).slice(0, 5);
  renderRankList("average-crusher", crusher, {
    name: (r) => r.name,
    sub: (r) => `Best ${fmtSigned(r.best_vs_average)}`,
    value: (r) => `${r.weeks_beat_average}wks`,
  });
  renderRankList("crushingly-average", crushed, {
    name: (r) => r.name,
    sub: (r) => `Worst ${fmtSigned(r.worst_vs_average)}`,
    value: (r) => `${r.weeks_lost_to_average}wks`,
  });

  const leagueVsGlobal = DATA.derived.league_vs_global_average;
  if (leagueVsGlobal.series.length) {
    makeLineChart(
      "chart-league-vs-global",
      leagueVsGlobal.series.map((p) => `GW${p.gw}`),
      [
        {
          label: "League v Average",
          data: leagueVsGlobal.series.map((p) => p.vs_average),
          borderColor: cssVar("--diverge-pos"),
          backgroundColor: cssVar("--diverge-pos"),
          borderWidth: 2,
          pointRadius: 0,
        },
      ]
    );
  } else {
    emptyChartMessage("chart-league-vs-global", "No gameweeks played yet.");
  }
}

/* ---------- Season: Records ---------- */
function renderRecords() {
  const scoreOpts = {
    name: (r) => r.name,
    sub: (r) => `GW${r.gw} · vs avg ${fmtSigned(r.vs_average)}${r.hits ? ` · ${r.hits} hits` : ""}`,
    value: (r) => fmtNum(r.points),
    emptyMessage: "No scores yet.",
  };
  renderRankList("best-10-scores", DATA.derived.best_worst_scores.best_10, scoreOpts);
  renderRankList("worst-10-scores", DATA.derived.best_worst_scores.worst_10, scoreOpts);

  setupManagerPickerChart({
    pickerId: "overallrank-manager-picker",
    canvasId: "chart-overall-rank",
    seriesByManager: DATA.derived.overall_rank_trend,
    valueKey: "overall_rank",
    reverseY: true,
  });
}

/* ---------- All-Time ---------- */
function renderAllTime() {
  setupManagerPickerChart({
    pickerId: "progression-manager-picker",
    canvasId: "chart-league-progression",
    seriesByManager: DATA.derived.league_progression,
    valueKey: "total_points",
  });

  renderRankList("top10-all-time", DATA.derived.top10_all_time, {
    numbered: true,
    name: (r) => r.name,
    sub: (r) => `${r.year} · top ${fmtPct(r.overall_percentage)}`,
    value: (r) => fmtNum(r.points),
  });

  renderRankList("wins-podiums", DATA.derived.wins_and_podiums_alltime, {
    name: (r) => r.name,
    sub: (r) => `${r.podiums} podiums`,
    value: (r) => `${r.wins}W`,
  });

  renderRankList("weeks-top-podium", DATA.derived.weeks_at_top_and_podium, {
    name: (r) => r.name,
    sub: (r) => `${r.weeks_on_podium} on podium`,
    value: (r) => `${r.weeks_at_top} wks`,
    emptyMessage: "No gameweeks played yet.",
  });

  renderRankList("consistency", DATA.derived.consistency, {
    name: (r) => r.name,
    sub: (r) => `avg ${r.mean_points} pts`,
    value: (r) => r.consistency_stdev,
    emptyMessage: "Not enough gameweeks played yet.",
  });

  renderRankList("average-position", DATA.derived.average_position, {
    name: (r) => r.name,
    value: (r) => r.average_position,
    emptyMessage: "No gameweeks played yet.",
  });

  renderHistory();
}

function renderHistory() {
  const container = document.getElementById("history-tables");
  container.innerHTML = "";
  const names = Object.keys(DATA.historic).sort();
  if (names.length === 0) {
    container.appendChild(el("p", { class: "empty-state", text: "No historic data seeded." }));
    return;
  }
  names.forEach((name) => {
    const details = el("details", { class: "accordion-item" });
    details.appendChild(el("summary", { text: name }));
    const body = el("div", { class: "accordion-body" });
    const ul = el("ul", { class: "rank-list", id: `history-${name.replace(/\s+/g, "-")}` });
    body.appendChild(ul);
    details.appendChild(body);
    container.appendChild(details);

    renderRankList(ul.id, DATA.historic[name], {
      name: (r) => r.year,
      sub: (r) => (r.league_rank ? `League rank ${r.league_rank}` : ""),
      value: (r) => (r.points ? fmtNum(r.points) : "–"),
    });
  });
}

/* ---------- boot ---------- */
async function loadAll() {
  const [standings, managers, historic, derived] = await Promise.all([
    fetchJSON("data/standings.json"),
    fetchJSON("data/managers.json"),
    fetchJSON("data/historic.json"),
    fetchJSON("data/derived.json"),
  ]);
  DATA.standings = standings;
  DATA.managers = managers;
  DATA.historic = historic;
  DATA.derived = derived;
  assignManagerColors();
}

async function main() {
  initNav();
  try {
    await loadAll();
  } catch (err) {
    document.getElementById("header-subtitle").textContent = "Couldn't load data — " + err.message;
    return;
  }

  document.getElementById("header-subtitle").textContent = Object.keys(DATA.managers).length
    ? `${Object.keys(DATA.managers).length} managers this season`
    : "Waiting for the season to start…";
  document.getElementById("footer-note").textContent = "sportz-chat-fpl, updated hourly.";

  renderHome();
  renderForm();
  renderBench();
  renderTransfers();
  renderChips();
  renderCaptaincy();
  renderAverage();
  renderRecords();
  renderAllTime();
}

main();
