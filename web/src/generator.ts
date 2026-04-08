/**
 * Dashboard data preparation.
 * Takes ExtractedData and produces DashboardData for rendering.
 */

import type {
  ExtractedData,
  DashboardData,
  CardData,
  ChartConfig,
  ChartDataset,
  TopCountry,
  StateInfo,
  TimeseriesData,
} from './types';

const GAME_START_YEAR = 1836;
const WEEKS_PER_YEAR = 52;
const MAX_POINTS = 200;

const PLAYER_COLOR = '#d4a843';
const PALETTE = [
  '#e94560', '#53917e', '#4a90d9', '#d4843a', '#9b59b6',
  '#2ecc71', '#e67e22', '#1abc9c', '#c0392b', '#3498db',
];

// ---------------------------------------------------------------------------
// Number formatting
// ---------------------------------------------------------------------------

export function fmtNumber(n: number | undefined): string {
  if (n === undefined || n === null) return '0';
  if (typeof n !== 'number' || isNaN(n)) return String(n);
  const abs = Math.abs(n);
  if (abs >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  if (!Number.isInteger(n)) return n.toFixed(1);
  return String(n);
}

// ---------------------------------------------------------------------------
// X-axis labels: week index → game year
// ---------------------------------------------------------------------------

function weekToYearLabels(numWeeks: number): string[] {
  const totalYears = numWeeks / WEEKS_PER_YEAR;
  const showQuarters = totalYears <= 15;
  const quarterSize = Math.floor(WEEKS_PER_YEAR / 4);
  const monthNames = ['', 'Apr', 'Jul', 'Oct'];
  const labels: string[] = [];
  for (let i = 0; i < numWeeks; i++) {
    const year = GAME_START_YEAR + i / WEEKS_PER_YEAR;
    if (i % WEEKS_PER_YEAR === 0) {
      labels.push(String(Math.floor(year)));
    } else if (showQuarters && i % quarterSize === 0) {
      const q = Math.floor((i % WEEKS_PER_YEAR) / quarterSize);
      labels.push(`${monthNames[q]} ${Math.floor(year)}`);
    } else {
      labels.push('');
    }
  }
  return labels;
}

// ---------------------------------------------------------------------------
// Resampling
// ---------------------------------------------------------------------------

function resample<T>(arr: T[], max: number): T[] {
  if (arr.length <= max) return arr;
  const step = arr.length / max;
  const out: T[] = [];
  for (let i = 0; i < max; i++) {
    out.push(arr[Math.floor(i * step)]);
  }
  // Always include the last element
  if (out[out.length - 1] !== arr[arr.length - 1]) {
    out[out.length - 1] = arr[arr.length - 1];
  }
  return out;
}

function resampleLabelsAndData(
  labels: string[],
  datasets: ChartDataset[],
): { labels: string[]; datasets: ChartDataset[] } {
  const n = labels.length;
  if (n <= MAX_POINTS) return { labels, datasets };
  const step = n / MAX_POINTS;
  const indices: number[] = [];
  for (let i = 0; i < MAX_POINTS; i++) {
    indices.push(Math.floor(i * step));
  }
  // Ensure last index is included
  if (indices[indices.length - 1] !== n - 1) {
    indices[indices.length - 1] = n - 1;
  }
  return {
    labels: indices.map((i) => labels[i]),
    datasets: datasets.map((ds) => ({
      ...ds,
      data: indices.map((i) => ds.data[i] ?? ds.data[ds.data.length - 1]),
    })),
  };
}

// ---------------------------------------------------------------------------
// Card building
// ---------------------------------------------------------------------------

function buildCards(data: ExtractedData): CardData[] {
  const cards: CardData[] = [];
  const { meta, snapshot, timeseries, technology } = data;

  if (meta.playerTag) {
    cards.push({ label: 'Country Tag', value: meta.playerTag });
  }

  // GDP
  if (timeseries.gdp?.length) {
    cards.push({ label: 'GDP', value: fmtNumber(timeseries.gdp[timeseries.gdp.length - 1]) });
  }

  // GDP per capita
  if (timeseries.gdp_per_capita?.length) {
    cards.push({
      label: 'GDP/Capita',
      value: fmtNumber(timeseries.gdp_per_capita[timeseries.gdp_per_capita.length - 1]),
    });
  }

  // Population
  if (timeseries.population?.length) {
    cards.push({
      label: 'Population',
      value: fmtNumber(timeseries.population[timeseries.population.length - 1]),
    });
  } else if (snapshot.population !== undefined) {
    cards.push({ label: 'Population', value: fmtNumber(snapshot.population) });
  }

  // Standard of Living
  if (timeseries.standard_of_living?.length) {
    const sol = timeseries.standard_of_living[timeseries.standard_of_living.length - 1];
    cards.push({ label: 'Std. of Living', value: sol.toFixed(1) });
  }

  // Literacy
  if (timeseries.literacy?.length) {
    const lit = timeseries.literacy[timeseries.literacy.length - 1];
    cards.push({
      label: 'Literacy',
      value: lit <= 1 ? `${(lit * 100).toFixed(1)}%` : `${lit.toFixed(1)}%`,
    });
  }

  // Prestige
  if (timeseries.prestige?.length) {
    cards.push({
      label: 'Prestige',
      value: fmtNumber(timeseries.prestige[timeseries.prestige.length - 1]),
    });
  } else if (snapshot.prestige !== undefined) {
    cards.push({ label: 'Prestige', value: fmtNumber(snapshot.prestige) });
  }

  // Treasury
  if (timeseries.treasury?.length) {
    cards.push({
      label: 'Treasury',
      value: fmtNumber(timeseries.treasury[timeseries.treasury.length - 1]),
    });
  } else if (snapshot.treasury !== undefined) {
    cards.push({ label: 'Treasury', value: fmtNumber(snapshot.treasury) });
  }

  // Technologies
  if (technology.acquired.length) {
    cards.push({ label: 'Technologies', value: String(technology.acquired.length) });
  } else if (snapshot.techCount !== undefined) {
    cards.push({ label: 'Technologies', value: String(snapshot.techCount) });
  }

  // Revenue / Expenditure from snapshot
  if (snapshot.revenue !== undefined) {
    cards.push({ label: 'Revenue', value: fmtNumber(snapshot.revenue) });
  }
  if (snapshot.expense !== undefined) {
    cards.push({ label: 'Expenditure', value: fmtNumber(snapshot.expense) });
  }

  // Fallback: if no cards from timeseries, populate from snapshot
  if (cards.length === 0) {
    for (const [k, v] of Object.entries(snapshot)) {
      if (v !== undefined) {
        const label = k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
        cards.push({ label, value: typeof v === 'number' ? fmtNumber(v) : String(v) });
      }
    }
  }

  return cards;
}

// ---------------------------------------------------------------------------
// Player chart building (single-country timeseries)
// ---------------------------------------------------------------------------

interface ChartDef {
  key: string;
  title: string;
  label: string;
  fill: boolean;
}

const CHART_DEFS: ChartDef[] = [
  { key: 'gdp', title: 'GDP Over Time', label: 'GDP', fill: true },
  { key: 'gdp_growth_rate', title: 'GDP Growth Rate (%)', label: 'Growth %', fill: false },
  { key: 'gdp_per_capita', title: 'GDP Per Capita', label: 'GDP/Cap', fill: true },
  { key: 'population', title: 'Population Over Time', label: 'Population', fill: true },
  { key: 'standard_of_living', title: 'Standard of Living', label: 'SoL', fill: false },
  { key: 'literacy', title: 'Literacy Rate', label: 'Literacy', fill: false },
  { key: 'prestige', title: 'Prestige Over Time', label: 'Prestige', fill: true },
];

function buildCharts(timeseries: TimeseriesData): ChartConfig[] {
  const charts: ChartConfig[] = [];

  // Budget chart (revenue + expenditure)
  if (timeseries.revenue?.length && timeseries.expenditure?.length) {
    const maxLen = Math.max(timeseries.revenue.length, timeseries.expenditure.length);
    const labels = weekToYearLabels(maxLen);
    const datasets: ChartDataset[] = [
      {
        label: 'Revenue',
        data: timeseries.revenue,
        borderColor: '#2ecc71',
        backgroundColor: 'rgba(46,204,113,0.1)',
        borderWidth: 2,
        tension: 0.3,
        pointRadius: 0,
      },
      {
        label: 'Expenditure',
        data: timeseries.expenditure,
        borderColor: '#e94560',
        backgroundColor: 'rgba(233,69,96,0.1)',
        borderWidth: 2,
        tension: 0.3,
        pointRadius: 0,
      },
    ];
    const resampled = resampleLabelsAndData(labels, datasets);
    charts.push({
      title: 'Budget: Revenue vs Expenditure',
      labels: resampled.labels,
      datasets: resampled.datasets,
    });
  }

  for (const def of CHART_DEFS) {
    const data = timeseries[def.key];
    if (!data || data.length < 2) continue;
    const labels = weekToYearLabels(data.length);
    const ds: ChartDataset = {
      label: def.label,
      data,
      borderColor: PLAYER_COLOR,
      backgroundColor: def.fill ? 'rgba(212,168,67,0.15)' : undefined,
      borderWidth: 2,
      tension: 0.3,
      pointRadius: 0,
    };
    const resampled = resampleLabelsAndData(labels, [ds]);
    charts.push({
      title: def.title,
      labels: resampled.labels,
      datasets: resampled.datasets,
    });
  }

  return charts;
}

// ---------------------------------------------------------------------------
// Comparison charts (multi-country)
// ---------------------------------------------------------------------------

interface ComparisonCountry {
  tag: string;
  isPlayer: boolean;
  timeseries: TimeseriesData;
}

const COMPARISON_METRICS: [string, string][] = [
  ['gdp', 'GDP Comparison'],
  ['gdp_growth_rate', 'GDP Growth Rate (%) Comparison'],
  ['gdp_per_capita', 'GDP Per Capita Comparison'],
  ['population', 'Population Comparison'],
  ['standard_of_living', 'Standard of Living Comparison'],
  ['literacy', 'Literacy Rate Comparison'],
  ['prestige', 'Prestige Comparison'],
  ['revenue', 'Revenue Comparison'],
  ['expenditure', 'Expenditure Comparison'],
];

function buildComparisonCharts(comparison: ExtractedData['comparison']): ChartConfig[] {
  if (!comparison || !comparison.tags.length) return [];

  const charts: ChartConfig[] = [];
  const { timeseries, tags, names } = comparison;

  for (const [metricKey, title] of COMPARISON_METRICS) {
    const datasets: ChartDataset[] = [];
    let maxLen = 0;

    for (let ci = 0; ci < tags.length; ci++) {
      const tag = tags[ci];
      // Comparison timeseries keys are prefixed: "tag:metric"
      const key = `${tag}:${metricKey}`;
      const data = timeseries[key];
      if (!data || data.length < 2) continue;

      const isPlayer = ci === 0; // first tag is typically the player
      const color = isPlayer ? PLAYER_COLOR : PALETTE[ci % PALETTE.length];
      const displayName = names[tag] || tag;

      datasets.push({
        label: isPlayer ? `${displayName} ★` : displayName,
        data,
        borderColor: color,
        backgroundColor: 'transparent',
        borderWidth: isPlayer ? 3 : 2,
        tension: 0.3,
        pointRadius: 0,
      });
      maxLen = Math.max(maxLen, data.length);
    }

    if (datasets.length > 1) {
      const labels = weekToYearLabels(maxLen);
      const resampled = resampleLabelsAndData(labels, datasets);
      charts.push({
        title,
        labels: resampled.labels,
        datasets: resampled.datasets,
      });
    }
  }

  return charts;
}

// ---------------------------------------------------------------------------
// Top countries table
// ---------------------------------------------------------------------------

function buildTopCountries(data: ExtractedData): TopCountry[] {
  const tm = data.territoryMap;
  if (!tm?.countries?.length) return [];

  return tm.countries.slice(0, 10).map((c, i) => ({
    rank: i + 1,
    tag: c.tag,
    name: c.name || c.tag,
    isPlayer: c.isPlayer,
    prestige: c.prestige,
    gdp: c.gdp,
    population: c.population,
    armySize: c.armySize,
    navySize: c.navySize,
    numStates: c.numStates,
  }));
}

// ---------------------------------------------------------------------------
// Format states
// ---------------------------------------------------------------------------

function formatStates(states: StateInfo[]): StateInfo[] {
  const out = states.map((s) => ({
    ...s,
    populationFmt: fmtNumber(s.population),
    gdpFmt: fmtNumber(s.gdp),
  }));
  out.sort((a, b) => b.population - a.population);
  return out;
}

// ---------------------------------------------------------------------------
// Main entry point
// ---------------------------------------------------------------------------

export function buildDashboard(data: ExtractedData): DashboardData {
  const cards = buildCards(data);
  const charts = buildCharts(data.timeseries);
  const comparisonCharts = buildComparisonCharts(data.comparison);

  const playerTag = data.meta.playerTag;
  let showPlayerDetails = true;
  if (comparisonCharts.length > 0 && data.comparison) {
    const playerInComparison = data.comparison.tags.includes(playerTag);
    showPlayerDetails = comparisonCharts.length === 0 || playerInComparison;
  }

  return {
    meta: data.meta,
    cards,
    charts,
    comparisonCharts,
    showPlayerDetails,
    states: formatStates(data.states),
    technology: data.technology,
    goods: data.goods,
    territoryMap: data.territoryMap,
    topCountries: buildTopCountries(data),
  };
}
