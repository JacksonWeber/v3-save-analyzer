/**
 * SPA router and page orchestration for V3 Save Analyzer.
 * Hash-based routing: #/landing, #/upload, #/select, #/dashboard, #/army
 */

import { Chart, registerables } from 'chart.js';
import { loadSave, initWasmMelter } from './loader';
import { parsePdx } from './parser';
import { extractAll, listCountries } from './extractor';
import { buildDashboard, fmtNumber } from './generator';
import { renderWorldMap } from './treemap';
import { renderArmyPage } from './army';
import type {
  ParsedData,
  CountryListItem,
  DashboardData,
  ChartConfig,
} from './types';

Chart.register(...registerables);

// Start loading WASM melter in background (non-blocking)
initWasmMelter();

// ---------------------------------------------------------------------------
// Application state
// ---------------------------------------------------------------------------

interface AppState {
  gamestateRaw: string | null;
  metaRaw: string | null;
  gamestate: ParsedData | null;
  meta: ParsedData | null;
  countries: CountryListItem[];
  selectedTags: Set<string>;
  dashboard: DashboardData | null;
  chartInstances: Chart[];
}

const state: AppState = {
  gamestateRaw: null,
  metaRaw: null,
  gamestate: null,
  meta: null,
  countries: [],
  selectedTags: new Set(),
  dashboard: null,
  chartInstances: [],
};

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------

function getRoute(): string {
  const hash = window.location.hash || '#/';
  return hash.replace(/^#/, '') || '/';
}

function navigate(path: string): void {
  window.location.hash = `#${path}`;
}

function onRouteChange(): void {
  const route = getRoute();
  destroyCharts();
  const app = document.getElementById('app')!;

  switch (route) {
    case '/':
    case '/landing':
      renderLanding(app);
      break;
    case '/upload':
      renderUpload(app);
      break;
    case '/select':
      renderSelect(app);
      break;
    case '/dashboard':
      renderDashboard(app);
      break;
    case '/army':
      renderArmy(app);
      break;
    default:
      renderLanding(app);
  }
}

// ---------------------------------------------------------------------------
// Chart cleanup
// ---------------------------------------------------------------------------

function destroyCharts(): void {
  for (const c of state.chartInstances) {
    c.destroy();
  }
  state.chartInstances = [];
}

// ---------------------------------------------------------------------------
// Pages
// ---------------------------------------------------------------------------

function navBar(active: string = ''): string {
  const link = (href: string, label: string) => {
    const cls = active === href ? ' class="active"' : '';
    return `<a href="#${href}"${cls}>${label}</a>`;
  };
  return `
    <nav>
      <div class="container">
        <a class="brand" href="#/">V3 Save Analyzer</a>
        <div class="nav-links">
          ${link('/', 'Home')}
          ${link('/upload', 'Upload')}
          ${state.dashboard ? link('/dashboard', 'Dashboard') : ''}
        </div>
      </div>
    </nav>`;
}

// ---- Landing ----

function renderLanding(app: HTMLElement): void {
  app.innerHTML = `
    ${navBar('/')}
    <div class="container">
      <h1>Victoria 3 Save Analyzer<small>Visualize your campaign data</small></h1>
      <div class="landing-cards">
        <div class="landing-card" id="card-analyzer">
          <div class="icon">📊</div>
          <h3>Save Game Analyzer</h3>
          <p>Upload a .v3 save file to visualize GDP, population, technology, and more.</p>
        </div>
        <div class="landing-card" id="card-army">
          <div class="icon">⚔️</div>
          <h3>Army Composition Optimizer</h3>
          <p>Optimize your army composition for maximum effectiveness.</p>
        </div>
      </div>
    </div>
    <footer>V3 Save Analyzer &mdash; Not affiliated with Paradox Interactive</footer>`;

  document.getElementById('card-analyzer')!.addEventListener('click', () => navigate('/upload'));
  document.getElementById('card-army')!.addEventListener('click', () => navigate('/army'));
}

// ---- Upload ----

function renderUpload(app: HTMLElement): void {
  app.innerHTML = `
    ${navBar('/upload')}
    <div class="page-center">
      <div class="upload-container">
        <h2 style="border:none;margin-top:0">Upload Save File</h2>
        <div class="drop-zone" id="drop-zone">
          <div class="icon">📁</div>
          <div class="text">
            <strong>Drop your .v3 save</strong> here or click to browse
          </div>
          <input type="file" id="file-input" accept=".v3,.zip">
        </div>
        <div class="file-name" id="file-name"></div>
        <button id="upload-btn" disabled>Analyze Save</button>
        <div class="loading" id="loading">
          <div class="spinner"></div>
          <div class="status-text" id="status-text">Loading…</div>
        </div>
        <div class="error" id="error-msg"></div>
        <div class="hint">
          Save files are located at:<br>
          <code>Documents/Paradox Interactive/Victoria 3/save games/</code>
        </div>
      </div>
    </div>`;

  const dropZone = document.getElementById('drop-zone')!;
  const fileInput = document.getElementById('file-input') as HTMLInputElement;
  const fileNameEl = document.getElementById('file-name')!;
  const uploadBtn = document.getElementById('upload-btn') as HTMLButtonElement;
  const loadingEl = document.getElementById('loading')!;
  const statusEl = document.getElementById('status-text')!;
  const errorEl = document.getElementById('error-msg')!;

  let selectedFile: File | null = null;

  function selectFile(file: File): void {
    selectedFile = file;
    fileNameEl.textContent = file.name;
    uploadBtn.disabled = false;
    errorEl.classList.remove('active');
  }

  dropZone.addEventListener('click', (e) => {
    // Don't re-trigger if clicking directly on the file input
    if (e.target !== fileInput) fileInput.click();
  });

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    if (e.dataTransfer?.files.length) selectFile(e.dataTransfer.files[0]);
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files?.length) selectFile(fileInput.files[0]);
  });

  uploadBtn.addEventListener('click', async () => {
    if (!selectedFile) return;
    uploadBtn.disabled = true;
    loadingEl.classList.add('active');
    errorEl.classList.remove('active');

    // Helper to yield to browser so status text actually renders
    const setStatus = async (msg: string) => {
      statusEl.textContent = msg;
      console.log(`[upload] ${msg}`);
      await new Promise((r) => setTimeout(r, 0));
    };

    try {
      await setStatus(`Reading file (${(selectedFile.size / 1048576).toFixed(1)} MB)…`);
      const buf = await selectedFile.arrayBuffer();

      await setStatus('Extracting save archive…');
      const raw = await loadSave(buf, (msg) => { statusEl.textContent = msg; });
      console.log(`[upload] gamestate: ${(raw.gamestate.length / 1048576).toFixed(1)} MB text`);

      await setStatus(`Parsing gamestate (${(raw.gamestate.length / 1048576).toFixed(1)} MB)… this may take a moment`);
      state.gamestateRaw = raw.gamestate;
      state.metaRaw = raw.meta;
      state.gamestate = parsePdx(raw.gamestate);
      console.log('[upload] gamestate parsed, keys:', Object.keys(state.gamestate).slice(0, 10));

      if (raw.meta) {
        await setStatus('Parsing metadata…');
        state.meta = parsePdx(raw.meta);
      } else {
        state.meta = {};
      }

      await setStatus('Building country list…');
      state.countries = listCountries(state.gamestate, state.meta);
      console.log(`[upload] Found ${state.countries.length} countries`);

      if (state.countries.length === 0) {
        throw new Error('No countries found in save file. The save may be in an unsupported format.');
      }

      // Pre-select the player country
      state.selectedTags.clear();
      for (const c of state.countries) {
        if (c.isPlayer) state.selectedTags.add(c.tag);
      }

      loadingEl.classList.remove('active');
      navigate('/select');
    } catch (err: unknown) {
      console.error('[upload] Error:', err);
      loadingEl.classList.remove('active');
      const msg = err instanceof Error ? err.message : String(err);
      errorEl.textContent = msg;
      errorEl.classList.add('active');
      uploadBtn.disabled = false;
    }
  });
}

// ---- Country select ----

function renderSelect(app: HTMLElement): void {
  if (!state.countries.length) {
    navigate('/upload');
    return;
  }

  app.innerHTML = `
    ${navBar('/select')}
    <div class="page-center">
      <div class="select-container">
        <h2 style="border:none;margin-top:0">Select Countries</h2>
        <div class="controls">
          <button id="sel-all">Select All</button>
          <button id="sel-none">Clear</button>
          <button id="sel-top10">Top 10</button>
          <button id="sel-player">Player Only</button>
          <input type="text" class="search-box" id="search-box" placeholder="Search countries…">
        </div>
        <div class="count" id="count-label"></div>
        <div class="country-list" id="country-list"></div>
        <div class="btn-row">
          <button class="btn-primary" id="go-btn">Analyze Selected</button>
        </div>
        <div class="loading" id="loading-select">
          <div class="spinner"></div>
          <div class="status-text" id="status-select">Extracting data…</div>
        </div>
        <div class="error" id="error-select"></div>
      </div>
    </div>`;

  const listEl = document.getElementById('country-list')!;
  const countEl = document.getElementById('count-label')!;
  const searchBox = document.getElementById('search-box') as HTMLInputElement;

  function renderList(filter: string = ''): void {
    const lc = filter.toLowerCase();
    const filtered = lc
      ? state.countries.filter(
          (c) =>
            c.tag.toLowerCase().includes(lc) ||
            c.name.toLowerCase().includes(lc),
        )
      : state.countries;

    listEl.innerHTML = filtered
      .map(
        (c) => `
        <div class="country-item${state.selectedTags.has(c.tag) ? ' selected' : ''}" data-tag="${c.tag}">
          <input type="checkbox" ${state.selectedTags.has(c.tag) ? 'checked' : ''}>
          <span class="country-tag">${c.tag}</span>
          <span class="country-name">${c.name}${c.isPlayer ? '<span class="player-badge">YOU</span>' : ''}</span>
          <span class="country-gdp">${fmtNumber(c.finalGdp)}</span>
        </div>`,
      )
      .join('');

    countEl.textContent = `${state.selectedTags.size} of ${state.countries.length} selected`;

    // Attach click handlers
    for (const el of listEl.querySelectorAll('.country-item')) {
      el.addEventListener('click', (e) => {
        const tag = (el as HTMLElement).dataset.tag!;
        if (state.selectedTags.has(tag)) {
          state.selectedTags.delete(tag);
        } else {
          state.selectedTags.add(tag);
        }
        // Prevent checkbox double-toggle
        if ((e.target as HTMLElement).tagName !== 'INPUT') {
          const cb = el.querySelector('input') as HTMLInputElement;
          cb.checked = state.selectedTags.has(tag);
        }
        el.classList.toggle('selected', state.selectedTags.has(tag));
        countEl.textContent = `${state.selectedTags.size} of ${state.countries.length} selected`;
      });
    }
  }

  renderList();

  searchBox.addEventListener('input', () => renderList(searchBox.value));

  document.getElementById('sel-all')!.addEventListener('click', () => {
    state.selectedTags = new Set(state.countries.map((c) => c.tag));
    renderList(searchBox.value);
  });

  document.getElementById('sel-none')!.addEventListener('click', () => {
    state.selectedTags.clear();
    renderList(searchBox.value);
  });

  document.getElementById('sel-top10')!.addEventListener('click', () => {
    state.selectedTags.clear();
    for (const c of state.countries.slice(0, 10)) {
      state.selectedTags.add(c.tag);
    }
    renderList(searchBox.value);
  });

  document.getElementById('sel-player')!.addEventListener('click', () => {
    state.selectedTags.clear();
    for (const c of state.countries) {
      if (c.isPlayer) state.selectedTags.add(c.tag);
    }
    renderList(searchBox.value);
  });

  document.getElementById('go-btn')!.addEventListener('click', async () => {
    if (!state.gamestate || !state.meta) return;
    const loadingEl = document.getElementById('loading-select')!;
    const statusEl = document.getElementById('status-select')!;
    const errorEl = document.getElementById('error-select')!;
    const goBtn = document.getElementById('go-btn') as HTMLButtonElement;

    goBtn.disabled = true;
    loadingEl.classList.add('active');
    errorEl.classList.remove('active');

    try {
      statusEl.textContent = 'Extracting data…';
      const compareTags = state.selectedTags.size > 1 ? [...state.selectedTags] : undefined;
      const extracted = extractAll(state.gamestate, state.meta, compareTags);

      statusEl.textContent = 'Building dashboard…';
      state.dashboard = buildDashboard(extracted);

      loadingEl.classList.remove('active');
      navigate('/dashboard');
    } catch (err: unknown) {
      loadingEl.classList.remove('active');
      const msg = err instanceof Error ? err.message : String(err);
      errorEl.textContent = msg;
      errorEl.classList.add('active');
      goBtn.disabled = false;
    }
  });
}

// ---- Dashboard ----

function renderDashboard(app: HTMLElement): void {
  if (!state.dashboard) {
    navigate('/upload');
    return;
  }

  const d = state.dashboard;

  const cardsHtml = d.cards
    .map(
      (c) => `
      <div class="card">
        <div class="label">${c.label}</div>
        <div class="value">${c.value}</div>
      </div>`,
    )
    .join('');

  const chartsHtml = d.charts
    .map(
      (_, i) => `
      <div class="chart-container">
        <h3>${d.charts[i].title}</h3>
        <div class="chart-wrap"><canvas id="chart-${i}"></canvas></div>
      </div>`,
    )
    .join('');

  const comparisonHtml = d.comparisonCharts.length
    ? `<h2>Country Comparison</h2>
       <div class="charts-grid">
         ${d.comparisonCharts
           .map(
             (_, i) => `
             <div class="chart-container">
               <h3>${d.comparisonCharts[i].title}</h3>
               <div class="chart-wrap"><canvas id="comp-chart-${i}"></canvas></div>
             </div>`,
           )
           .join('')}
       </div>`
    : '';

  const topHtml = d.topCountries.length
    ? `<h2>Top Countries</h2>
       <table class="top10-table">
         <thead>
           <tr>
             <th>#</th><th>Country</th><th class="num">Prestige</th>
             <th class="num">GDP</th><th class="num">Population</th>
             <th class="num">Army</th><th class="num">Navy</th>
             <th class="num">States</th>
           </tr>
         </thead>
         <tbody>
           ${d.topCountries
             .map(
               (c) => `
               <tr class="rank-${c.rank}${c.isPlayer ? ' player-row' : ''}">
                 <td class="rank-num">${c.rank}</td>
                 <td>${c.name}${c.isPlayer ? '<span class="player-badge">YOU</span>' : ''}</td>
                 <td class="num">${fmtNumber(c.prestige)}</td>
                 <td class="num">${fmtNumber(c.gdp)}</td>
                 <td class="num">${fmtNumber(c.population)}</td>
                 <td class="num">${fmtNumber(c.armySize)}</td>
                 <td class="num">${fmtNumber(c.navySize)}</td>
                 <td class="num">${c.numStates}</td>
               </tr>`,
             )
             .join('')}
         </tbody>
       </table>`
    : '';

  const statesHtml =
    d.showPlayerDetails && d.states.length
      ? `<h2>States</h2>
         <table>
           <thead>
             <tr><th>State</th><th class="num">Population</th><th class="num">GDP</th><th class="num">Infrastructure</th></tr>
           </thead>
           <tbody>
             ${d.states
               .map(
                 (s) => `
                 <tr>
                   <td>${s.name}</td>
                   <td class="num">${s.populationFmt}</td>
                   <td class="num">${s.gdpFmt}</td>
                   <td class="num">${s.infrastructure.toFixed(1)}</td>
                 </tr>`,
               )
               .join('')}
           </tbody>
         </table>`
      : '';

  const techHtml =
    d.showPlayerDetails && d.technology.acquired.length
      ? `<h2>Technology (${d.technology.acquired.length})</h2>
         ${d.technology.researching ? `<p style="color:var(--accent2);margin-bottom:12px">Currently researching: <strong>${d.technology.researching}</strong></p>` : ''}
         <table>
           <thead><tr><th>#</th><th>Technology</th></tr></thead>
           <tbody>
             ${d.technology.acquired
               .map(
                 (t, i) => `<tr><td class="num">${i + 1}</td><td>${t}</td></tr>`,
               )
               .join('')}
           </tbody>
         </table>`
      : '';

  const goodsHtml =
    d.showPlayerDetails && d.goods.length
      ? `<h2>Goods</h2>
         <table>
           <thead>
             <tr><th>Good</th><th class="num">Production</th><th class="num">Consumption</th><th class="num">Price</th></tr>
           </thead>
           <tbody>
             ${d.goods
               .map(
                 (g) => `
                 <tr>
                   <td>${g.name}</td>
                   <td class="num">${fmtNumber(g.production)}</td>
                   <td class="num">${fmtNumber(g.consumption)}</td>
                   <td class="num">${g.price.toFixed(1)}</td>
                 </tr>`,
               )
               .join('')}
           </tbody>
         </table>`
      : '';

  const hasTerritory = d.territoryMap?.countries?.length > 0;

  app.innerHTML = `
    ${navBar('/dashboard')}
    <div class="container">
      <header style="background:none;border:none;padding:0;margin-bottom:16px">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
          <h1>${d.meta.countryName || d.meta.playerTag}<small>${d.meta.playerTag}</small></h1>
          <span class="date-badge">${d.meta.gameDate}</span>
        </div>
      </header>
      <div class="cards">${cardsHtml}</div>
      ${hasTerritory ? '<h2>Territory Map</h2><div id="territory-treemap" class="treemap-container"></div>' : ''}
      ${d.charts.length ? `<h2>Player Timeseries</h2><div class="charts-grid">${chartsHtml}</div>` : ''}
      ${comparisonHtml}
      ${topHtml}
      ${statesHtml}
      ${techHtml}
      ${goodsHtml}
      <footer>V3 Save Analyzer &mdash; Not affiliated with Paradox Interactive</footer>
    </div>`;

  // Render territory map
  if (hasTerritory) {
    const treemapEl = document.getElementById('territory-treemap');
    if (treemapEl) renderWorldMap(treemapEl, d.territoryMap);
  }

  // Initialize Chart.js instances
  initCharts(d.charts, 'chart');
  initCharts(d.comparisonCharts, 'comp-chart');
}

function initCharts(configs: ChartConfig[], prefix: string): void {
  for (let i = 0; i < configs.length; i++) {
    const canvas = document.getElementById(`${prefix}-${i}`) as HTMLCanvasElement | null;
    if (!canvas) continue;

    const cfg = configs[i];
    const ctx = canvas.getContext('2d')!;

    const datasets = cfg.datasets.map((ds) => {
      const color = ds.borderColor || '#d4a843';
      const hasFill = !!ds.backgroundColor && ds.backgroundColor !== 'transparent';

      let bgColor: string | CanvasGradient = ds.backgroundColor || 'transparent';
      if (hasFill) {
        const grad = ctx.createLinearGradient(0, 0, 0, canvas.clientHeight || 300);
        grad.addColorStop(0, color + '4D'); // ~0.3 alpha
        grad.addColorStop(1, 'transparent');
        bgColor = grad;
      }

      return {
        label: ds.label,
        data: ds.data,
        borderColor: color,
        backgroundColor: bgColor,
        borderWidth: ds.borderWidth ?? 2,
        tension: ds.tension ?? 0.3,
        pointRadius: ds.pointRadius ?? 0,
        fill: hasFill,
        spanGaps: true,
      };
    });

    const chart = new Chart(canvas, {
      type: 'line',
      data: { labels: cfg.labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            display: cfg.datasets.length > 1,
            position: 'top',
            align: 'end',
            labels: {
              color: '#c0c0d0',
              boxWidth: 12,
              boxHeight: 12,
              useBorderRadius: true,
              borderRadius: 3,
              padding: 14,
              font: { size: 12 },
            },
          },
          tooltip: {
            backgroundColor: 'rgba(16,24,48,0.95)',
            titleColor: '#eee',
            bodyColor: '#c0c0d0',
            borderColor: '#2a2a4a',
            borderWidth: 1,
            cornerRadius: 6,
            padding: 10,
            boxPadding: 4,
            usePointStyle: true,
            callbacks: {
              label: (ctx) =>
                `${ctx.dataset.label}: ${fmtNumber(ctx.parsed.y ?? 0)}`,
            },
          },
          decimation: { enabled: true, algorithm: 'lttb', samples: 500 },
        },
        scales: {
          x: {
            ticks: {
              color: '#a0a0b0',
              maxRotation: 45,
              autoSkip: true,
              maxTicksLimit: 20,
            },
            grid: { color: 'rgba(42,42,74,0.3)' },
          },
          y: {
            ticks: {
              color: '#a0a0b0',
              callback: (value) => fmtNumber(Number(value)),
            },
            grid: { color: 'rgba(42,42,74,0.3)' },
          },
        },
      },
    });
    state.chartInstances.push(chart);
  }
}

// ---- Army optimizer ----

function renderArmy(app: HTMLElement): void {
  renderArmyPage(app);
}

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------

window.addEventListener('hashchange', onRouteChange);
onRouteChange();
