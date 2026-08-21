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

function assignManagerColors(managers) {
  const ids = Object.keys(managers).sort((a, b) =>
    managers[a].name.localeCompare(managers[b].name)
  );
  ids.forEach((id, i) => {
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

function emptyState(container, message = "No data yet — check back once the season is underway.") {
  container.innerHTML = "";
  container.appendChild(el("p", { class: "empty-state", text: message }));
}

/* ---------- generic table renderer ---------- */
function renderTable(container, columns, rows, opts = {}) {
  if (!rows || rows.length === 0) return emptyState(container, opts.emptyMessage);
  container.innerHTML = "";
  const table = el("table");
  const thead = el("tr");
  columns.forEach((col) => thead.appendChild(el("th", { class: col.num ? "num" : "", text: col.label })));
  table.appendChild(el("thead", {}, [thead]));
  const tbody = el("tbody");
  rows.forEach((row) => {
    const tr = el("tr");
    columns.forEach((col) => {
      const value = col.format ? col.format(row) : row[col.key];
      tr.appendChild(el("td", { class: col.num ? "num" : "", text: value }));
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  container.appendChild(table);
}

/* ---------- paired best/worst leaderboard ---------- */
function renderLeaderboard(ulId, items, opts = {}) {
  const ul = document.getElementById(ulId);
  ul.innerHTML = "";
  if (!items || items.length === 0) {
    ul.appendChild(el("li", { text: "No data yet" }));
    return;
  }
  items.forEach((item) => {
    const li = el("li");
    li.appendChild(el("span", { text: item.name }));
    li.appendChild(el("span", { class: "value", text: opts.format ? opts.format(item.value) : fmtNum(item.value) }));
    ul.appendChild(li);
  });
}

/* ---------- chart helpers ---------- */
const CHART_DEFAULTS = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: "nearest", intersect: false },
  plugins: {
    legend: {
      labels: { color: cssVar("--text-secondary"), usePointStyle: true, boxWidth: 8 },
    },
    tooltip: { mode: "index", intersect: false },
  },
  scales: {
    x: {
      grid: { color: cssVar("--gridline") },
      ticks: { color: cssVar("--text-muted") },
    },
    y: {
      grid: { color: cssVar("--gridline") },
      ticks: { color: cssVar("--text-muted") },
    },
  },
};

function makeLineChart(canvasId, labels, datasets, opts = {}) {
  const ctx = document.getElementById(canvasId);
  if (CHARTS[canvasId]) CHARTS[canvasId].destroy();
  CHARTS[canvasId] = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      ...CHART_DEFAULTS,
      scales: {
        ...CHART_DEFAULTS.scales,
        y: { ...CHART_DEFAULTS.scales.y, reverse: !!opts.reverseY },
      },
      plugins: {
        ...CHART_DEFAULTS.plugins,
        legend: { display: datasets.length > 1, labels: CHART_DEFAULTS.plugins.legend.labels },
      },
    },
  });
}

function makeStackedBarChart(canvasId, labels, datasets) {
  const ctx = document.getElementById(canvasId);
  if (CHARTS[canvasId]) CHARTS[canvasId].destroy();
  CHARTS[canvasId] = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets },
    options: {
      ...CHART_DEFAULTS,
      scales: {
        x: { ...CHART_DEFAULTS.scales.x, stacked: true },
        y: { ...CHART_DEFAULTS.scales.y, stacked: true },
      },
    },
  });
}

/* ---------- tabs ---------- */
function initTabs() {
  const buttons = document.querySelectorAll("nav.tabs button");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
      // Charts created while their tab panel was display:none get measured
      // at zero size and never redraw on their own once the panel becomes
      // visible again -- force every chart to re-measure its container now.
      Object.values(CHARTS).forEach((chart) => chart.resize());
    });
  });
}

/* ---------- render: Home ---------- */
function renderHome() {
  renderTable(
    document.getElementById("league-table"),
    [
      { label: "#", key: "rank", num: true },
      { label: "Name", key: "name" },
      { label: "Team Name", key: "team_name" },
      { label: "Points", key: "total", num: true, format: (r) => fmtNum(r.total) },
    ],
    DATA.standings,
    { emptyMessage: "Season hasn't started yet — standings will appear once gameweek 1 completes." }
  );

  const f = DATA.derived.form;
  if (!f || f.in_form.length === 0) {
    ["in-form", "in-freefall", "sound-spenders", "spend-thrifts", "tactical-masters", "rotation-losers"].forEach(
      (id) => renderLeaderboard(id, [])
    );
    return;
  }
  renderLeaderboard("in-form", f.in_form);
  renderLeaderboard("in-freefall", f.in_freefall);
  renderLeaderboard("sound-spenders", f.sound_spenders);
  renderLeaderboard("spend-thrifts", f.spend_thrifts);
  renderLeaderboard("tactical-masters", f.tactical_masters);
  renderLeaderboard("rotation-losers", f.rotation_losers);
}

/* ---------- render: Hall of Fame ---------- */
function renderHallOfFame() {
  const progression = DATA.derived.league_progression;
  const managerIds = Object.keys(progression).sort((a, b) =>
    DATA.managers[a].name.localeCompare(DATA.managers[b].name)
  );
  if (managerIds.length && progression[managerIds[0]].length) {
    const labels = progression[managerIds[0]].map((p) => `GW${p.gw}`);
    const datasets = managerIds.map((mid) => ({
      label: DATA.managers[mid].name,
      data: progression[mid].map((p) => p.total_points),
      borderColor: colorFor(mid),
      backgroundColor: colorFor(mid),
      borderWidth: 2,
      pointRadius: 0,
    }));
    makeLineChart("chart-league-progression", labels, datasets);
  } else {
    document.getElementById("chart-league-progression").closest(".card").querySelector(".chart-wrap").outerHTML =
      '<p class="empty-state">No gameweeks played yet.</p>';
  }

  renderTable(
    document.getElementById("top10-all-time"),
    [
      { label: "Name", key: "name" },
      { label: "Season", key: "year" },
      { label: "Points", key: "points", num: true, format: (r) => fmtNum(r.points) },
      { label: "%ile", key: "overall_percentage", num: true, format: (r) => (r.overall_percentage * 100).toFixed(2) + "%" },
    ],
    DATA.derived.top10_all_time
  );

  renderTable(
    document.getElementById("wins-podiums"),
    [
      { label: "Name", key: "name" },
      { label: "Wins", key: "wins", num: true },
      { label: "Podiums", key: "podiums", num: true },
    ],
    DATA.derived.wins_and_podiums_alltime
  );

  renderTable(
    document.getElementById("weeks-top-podium"),
    [
      { label: "Name", key: "name" },
      { label: "Weeks Top", key: "weeks_at_top", num: true },
      { label: "Weeks Podium", key: "weeks_on_podium", num: true },
    ],
    DATA.derived.weeks_at_top_and_podium
  );

  renderTable(
    document.getElementById("consistency"),
    [
      { label: "Name", key: "name" },
      { label: "Std. Dev.", key: "consistency_stdev", num: true },
      { label: "Mean Pts", key: "mean_points", num: true },
    ],
    DATA.derived.consistency
  );

  renderTable(
    document.getElementById("average-position"),
    [
      { label: "Name", key: "name" },
      { label: "Avg. Position", key: "average_position", num: true },
    ],
    DATA.derived.average_position
  );
}

/* ---------- render: History ---------- */
function renderHistory() {
  const container = document.getElementById("history-tables");
  container.innerHTML = "";
  const names = Object.keys(DATA.historic).sort();
  if (names.length === 0) return emptyState(container, "No historic data seeded.");

  const grid = el("div", { class: "card-grid" });
  names.forEach((name) => {
    const card = el("div", { class: "card" });
    card.appendChild(el("h3", { text: name }));
    const box = el("div");
    renderTable(
      box,
      [
        { label: "Season", key: "year" },
        { label: "Points", key: "points", num: true, format: (r) => fmtNum(r.points) },
        { label: "League Rank", key: "league_rank", num: true },
        { label: "Overall %ile", key: "overall_percentage", num: true, format: (r) => (r.overall_percentage != null ? (r.overall_percentage * 100).toFixed(2) + "%" : "–") },
      ],
      DATA.historic[name]
    );
    card.appendChild(box);
    grid.appendChild(card);
  });
  container.appendChild(grid);
}

/* ---------- render: Bench ---------- */
function renderBench() {
  renderTable(
    document.getElementById("bench-leaderboard"),
    [
      { label: "Name", key: "name" },
      { label: "POB", key: "points_on_bench", num: true },
    ],
    DATA.derived.bench_leaderboard
  );

  renderTable(
    document.getElementById("adjusted-table"),
    [
      { label: "Name", key: "name" },
      { label: "Total Pts", key: "total_points", num: true },
      { label: "Total+Bench", key: "total_plus_bench", num: true },
      { label: "Jammy Δ", key: "jammy_delta", num: true, format: (r) => fmtSigned(r.jammy_delta) },
    ],
    DATA.derived.adjusted_table
  );

  const byWeek = DATA.derived.points_on_bench_by_week;
  const managerIds = Object.keys(byWeek).sort((a, b) => DATA.managers[a].name.localeCompare(DATA.managers[b].name));
  if (managerIds.length && byWeek[managerIds[0]].length) {
    const labels = byWeek[managerIds[0]].map((p) => `GW${p.gw}`);
    const datasets = managerIds.map((mid) => ({
      label: DATA.managers[mid].name,
      data: byWeek[mid].map((p) => p.points_on_bench),
      borderColor: colorFor(mid),
      backgroundColor: colorFor(mid),
      borderWidth: 2,
      pointRadius: 0,
    }));
    makeLineChart("chart-bench-by-week", labels, datasets);
  }
}

/* ---------- render: Transfers ---------- */
function renderTransfers() {
  renderTable(
    document.getElementById("transfers-summary"),
    [
      { label: "Name", key: "name" },
      { label: "Transfers", key: "transfer_count", num: true },
      { label: "Net Points", key: "total_net_points", num: true, format: (r) => fmtSigned(r.total_net_points) },
    ],
    DATA.derived.transfers_summary.summary
  );

  const transferCols = [
    { label: "Name", key: "name" },
    { label: "GW", key: "gw", num: true },
    { label: "In", key: "player_in_name" },
    { label: "Out", key: "player_out_name" },
    { label: "Net", key: "net_points", num: true, format: (r) => fmtSigned(r.net_points) },
  ];
  renderTable(document.getElementById("best-transfers"), transferCols, DATA.derived.transfers_summary.best_transfers);
  renderTable(document.getElementById("worst-transfers"), transferCols, DATA.derived.transfers_summary.worst_transfers);
}

/* ---------- render: Chips ---------- */
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
    emptyState(document.getElementById("chart-chip-usage").closest(".card"));
  }

  renderTable(
    document.getElementById("top10-chips"),
    [
      { label: "Name", key: "name" },
      { label: "Chip", key: "chip_label" },
      { label: "Points", key: "points", num: true },
    ],
    DATA.derived.chip_usage.top_10_chips
  );

  renderTable(
    document.getElementById("tc-points"),
    [
      { label: "Name", key: "name" },
      { label: "GW", key: "gw", num: true },
      { label: "Points", key: "points", num: true },
    ],
    DATA.derived.chip_usage.triple_captain_points
  );
}

/* ---------- render: Captaincy ---------- */
function renderCaptaincy() {
  renderTable(
    document.getElementById("captaincy-summary"),
    [
      { label: "Name", key: "name" },
      { label: "Total", key: "total_captain_points", num: true },
      { label: "Picked Best", key: "picked_best_captain_weeks", num: true },
      { label: "Gain/Loss", key: "gain_loss_vs_optimal", num: true, format: (r) => fmtSigned(r.gain_loss_vs_optimal) },
    ],
    DATA.derived.captaincy.summary
  );

  const series = DATA.derived.captaincy.series;
  const managerIds = Object.keys(series).sort((a, b) => DATA.managers[a].name.localeCompare(DATA.managers[b].name));
  const picker = document.getElementById("captaincy-manager-picker");
  picker.innerHTML = '<option value="__all__">All managers</option>';
  managerIds.forEach((mid) => picker.appendChild(el("option", { value: mid, text: DATA.managers[mid].name })));

  function draw() {
    const selected = picker.value;
    const ids = selected === "__all__" ? managerIds : [selected];
    if (!ids.length || !series[ids[0]] || series[ids[0]].length === 0) return;
    const labels = series[ids[0]].map((p) => `GW${p.gw}`);
    const datasets = ids.map((mid) => ({
      label: DATA.managers[mid].name,
      data: series[mid].map((p) => p.captain_points),
      borderColor: colorFor(mid),
      backgroundColor: colorFor(mid),
      borderWidth: 2,
      pointRadius: 2,
    }));
    makeLineChart("chart-captaincy", labels, datasets);
  }
  picker.addEventListener("change", draw);
  if (managerIds.length) draw();
}

/* ---------- render: Fun Stuff ---------- */
function renderFun() {
  const vsAvg = DATA.derived.vs_average;
  const managerIds = Object.keys(vsAvg.series).sort((a, b) => DATA.managers[a].name.localeCompare(DATA.managers[b].name));
  const picker = document.getElementById("average-manager-picker");
  picker.innerHTML = '<option value="__all__">All managers</option>';
  managerIds.forEach((mid) => picker.appendChild(el("option", { value: mid, text: DATA.managers[mid].name })));

  function drawVsAvg() {
    const selected = picker.value;
    const ids = selected === "__all__" ? managerIds : [selected];
    if (!ids.length || !vsAvg.series[ids[0]] || vsAvg.series[ids[0]].length === 0) return;
    const labels = vsAvg.series[ids[0]].map((p) => `GW${p.gw}`);
    const datasets = ids.map((mid) => ({
      label: DATA.managers[mid].name,
      data: vsAvg.series[mid].map((p) => p.vs_average),
      borderColor: colorFor(mid),
      backgroundColor: colorFor(mid),
      borderWidth: 2,
      pointRadius: 0,
    }));
    makeLineChart("chart-vs-average", labels, datasets);
  }
  picker.addEventListener("change", drawVsAvg);
  if (managerIds.length) drawVsAvg();

  const crusher = [...vsAvg.summary].sort((a, b) => b.weeks_beat_average - a.weeks_beat_average).slice(0, 5);
  const crushed = [...vsAvg.summary].sort((a, b) => b.weeks_lost_to_average - a.weeks_lost_to_average).slice(0, 5);
  renderTable(
    document.getElementById("average-crusher"),
    [
      { label: "Name", key: "name" },
      { label: "Beat Avg", key: "weeks_beat_average", num: true },
      { label: "Best v Avg", key: "best_vs_average", num: true, format: (r) => fmtSigned(r.best_vs_average) },
    ],
    crusher
  );
  renderTable(
    document.getElementById("crushingly-average"),
    [
      { label: "Name", key: "name" },
      { label: "Lost to Avg", key: "weeks_lost_to_average", num: true },
      { label: "Worst v Avg", key: "worst_vs_average", num: true, format: (r) => fmtSigned(r.worst_vs_average) },
    ],
    crushed
  );

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
  }

  const scoreCols = [
    { label: "Name", key: "name" },
    { label: "GW", key: "gw", num: true },
    { label: "Hits", key: "hits", num: true },
    { label: "vs Avg", key: "vs_average", num: true, format: (r) => fmtSigned(r.vs_average) },
    { label: "Points", key: "points", num: true },
  ];
  renderTable(document.getElementById("best-10-scores"), scoreCols, DATA.derived.best_worst_scores.best_10);
  renderTable(document.getElementById("worst-10-scores"), scoreCols, DATA.derived.best_worst_scores.worst_10);

  const rankTrend = DATA.derived.overall_rank_trend;
  const rankIds = Object.keys(rankTrend).sort((a, b) => DATA.managers[a].name.localeCompare(DATA.managers[b].name));
  if (rankIds.length && rankTrend[rankIds[0]].length) {
    const labels = rankTrend[rankIds[0]].map((p) => `GW${p.gw}`);
    const datasets = rankIds.map((mid) => ({
      label: DATA.managers[mid].name,
      data: rankTrend[mid].map((p) => p.overall_rank),
      borderColor: colorFor(mid),
      backgroundColor: colorFor(mid),
      borderWidth: 2,
      pointRadius: 0,
    }));
    makeLineChart("chart-overall-rank", labels, datasets, { reverseY: true });
  }
}

/* ---------- boot ---------- */
async function main() {
  initTabs();
  try {
    await loadAll();
  } catch (err) {
    document.getElementById("header-subtitle").textContent = "Couldn't load data — " + err.message;
    return;
  }

  document.getElementById("header-subtitle").textContent =
    Object.keys(DATA.managers).length
      ? `${Object.keys(DATA.managers).length} managers this season`
      : "Waiting for the season to start...";
  document.getElementById("footer-note").textContent = "sportz-chat-fpl on GitHub Actions + Pages.";

  renderHome();
  renderHallOfFame();
  renderHistory();
  renderBench();
  renderTransfers();
  renderChips();
  renderCaptaincy();
  renderFun();
}

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
  assignManagerColors(managers);
}

main();
