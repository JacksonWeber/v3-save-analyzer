/**
 * SVG world map visualization.
 * Renders Victoria 3 state boundaries colored by country ownership.
 * Map geometry is pre-extracted from game files into map_data.json.
 */

import type { TerritoryMap } from './types';

interface MapData {
  width: number;
  height: number;
  states: Record<string, { r: number[][]; cx: number; cy: number }>;
}

const PLAYER_COLOR = '#d4a843';
const UNOWNED_COLOR = '#1a1a2e';
const WATER_COLOR = '#0d1117';
const PALETTE = [
  '#e94560', '#53917e', '#508cdc', '#ff8833', '#9b59b6',
  '#1abc9c', '#e67e22', '#3498db', '#e74c3c', '#2ecc71',
  '#f39c12', '#8e44ad', '#16a085', '#c0392b', '#27ae60',
  '#d35400', '#2980b9', '#7f8c8d', '#34495e', '#e056a0',
  '#45b7d1', '#96ceb4', '#ffeaa7', '#dfe6e9', '#fab1a0',
];

let cachedMapData: MapData | null = null;

async function loadMapData(): Promise<MapData | null> {
  if (cachedMapData) return cachedMapData;
  try {
    const resp = await fetch('/map_data.json');
    if (!resp.ok) return null;
    cachedMapData = await resp.json();
    return cachedMapData;
  } catch {
    return null;
  }
}

/** Build STATE_KEY → country tag mapping from territory data. */
function buildOwnership(territory: TerritoryMap): Map<string, string> {
  const ownership = new Map<string, string>();
  const subjectMap = territory.subjectMap ?? {};

  // Resolve subject chains: vassal → overlord
  function resolveOverlord(tag: string, depth = 0): string {
    if (depth > 10) return tag;
    const overlord = subjectMap[tag];
    return overlord ? resolveOverlord(overlord, depth + 1) : tag;
  }

  for (const country of territory.countries) {
    const effectiveTag = resolveOverlord(country.tag);
    for (const state of country.states) {
      if (state.stateKey) {
        ownership.set(state.stateKey, effectiveTag);
      }
    }
  }
  return ownership;
}

/** Convert rect list to a compact SVG path string. */
function rectsToPath(rects: number[][]): string {
  return rects
    .map(([x, y, w, h]) => `M${x} ${y}h${w}v${h}h-${w}z`)
    .join('');
}

export async function renderWorldMap(
  container: HTMLElement,
  territory: TerritoryMap,
): Promise<void> {
  container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-secondary)">Loading map data…</div>';

  const mapData = await loadMapData();
  if (!mapData) {
    container.innerHTML = '<p style="color:var(--text-secondary);text-align:center;padding:40px">Map data not available (map_data.json not found)</p>';
    return;
  }

  const { width, height, states } = mapData;
  const ownership = buildOwnership(territory);

  // Assign colors to country tags
  const colorMap = new Map<string, string>();
  const allTags = new Set(ownership.values());
  let ci = 0;
  for (const tag of [...allTags].sort()) {
    if (tag === territory.playerTag) {
      colorMap.set(tag, PLAYER_COLOR);
    } else {
      colorMap.set(tag, PALETTE[ci % PALETTE.length]);
      ci++;
    }
  }

  // Group states by color for efficient SVG (fewer path elements)
  const colorGroups = new Map<string, { rects: number[][]; stateNames: string[] }>();
  const unownedRects: number[][] = [];
  const unownedNames: string[] = [];

  for (const [stateKey, stateData] of Object.entries(states)) {
    const tag = ownership.get(stateKey);
    if (tag) {
      const color = colorMap.get(tag) ?? '#555';
      if (!colorGroups.has(color)) {
        colorGroups.set(color, { rects: [], stateNames: [] });
      }
      const group = colorGroups.get(color)!;
      group.rects.push(...stateData.r);
      group.stateNames.push(stateKey);
    } else {
      unownedRects.push(...stateData.r);
      unownedNames.push(stateKey);
    }
  }

  // Build country label positions (average centroid of owned states)
  const tagCentroids = new Map<string, { sx: number; sy: number; count: number }>();
  for (const [stateKey, stateData] of Object.entries(states)) {
    const tag = ownership.get(stateKey);
    if (!tag) continue;
    const entry = tagCentroids.get(tag) ?? { sx: 0, sy: 0, count: 0 };
    entry.sx += stateData.cx;
    entry.sy += stateData.cy;
    entry.count++;
    tagCentroids.set(tag, entry);
  }

  // Build SVG
  const svgParts: string[] = [];
  svgParts.push(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" style="background:${WATER_COLOR};border-radius:8px;display:block;width:100%">`);

  // Unowned states (dim)
  if (unownedRects.length > 0) {
    svgParts.push(`<path d="${rectsToPath(unownedRects)}" fill="${UNOWNED_COLOR}" opacity="0.4"/>`);
  }

  // Owned states grouped by color
  for (const [color, group] of colorGroups) {
    svgParts.push(`<path d="${rectsToPath(group.rects)}" fill="${color}" opacity="0.9"/>`);
  }

  // Country labels
  for (const [tag, centroid] of tagCentroids) {
    if (centroid.count < 2) continue;
    const x = Math.round(centroid.sx / centroid.count);
    const y = Math.round(centroid.sy / centroid.count);
    const isPlayer = tag === territory.playerTag;
    const label = isPlayer ? `★${tag}` : tag;
    svgParts.push(
      `<text x="${x}" y="${y}" text-anchor="middle" dominant-baseline="central" ` +
      `font-family="'Inter','Segoe UI',system-ui,sans-serif" font-size="7" font-weight="bold" ` +
      `fill="white" opacity="0.9" style="text-shadow:0 0 3px rgba(0,0,0,0.8)">${label}</text>`,
    );
  }

  svgParts.push('</svg>');

  // Render with zoom/pan controls
  container.innerHTML = `
    <div class="map-controls">
      <button class="map-btn" id="map-zoom-in" title="Zoom in">+</button>
      <button class="map-btn" id="map-zoom-out" title="Zoom out">−</button>
      <button class="map-btn" id="map-reset" title="Reset">↺</button>
    </div>
    <div class="map-viewport" id="map-viewport">
      <div class="map-inner" id="map-inner">
        ${svgParts.join('')}
      </div>
    </div>
    <div class="map-legend" id="map-legend"></div>
  `;

  // Build legend
  const legendEl = document.getElementById('map-legend')!;
  const tagNames = new Map<string, string>();
  for (const c of territory.countries) {
    tagNames.set(c.tag, c.name || c.tag);
  }
  const sortedTags = [...allTags].sort((a, b) => {
    if (a === territory.playerTag) return -1;
    if (b === territory.playerTag) return 1;
    return (tagNames.get(a) ?? a).localeCompare(tagNames.get(b) ?? b);
  });

  legendEl.innerHTML = sortedTags
    .slice(0, 20)
    .map((tag) => {
      const color = colorMap.get(tag) ?? '#555';
      const name = tagNames.get(tag) ?? tag;
      const isPlayer = tag === territory.playerTag;
      return `<span class="map-legend-item">
        <span class="map-legend-swatch" style="background:${color}"></span>
        ${isPlayer ? '★ ' : ''}${name}
      </span>`;
    })
    .join('') +
    (sortedTags.length > 20 ? `<span class="map-legend-item" style="opacity:0.5">+${sortedTags.length - 20} more</span>` : '');

  // Zoom/pan interactivity
  const viewport = document.getElementById('map-viewport')!;
  const inner = document.getElementById('map-inner')!;
  let scale = 1;
  let translateX = 0;
  let translateY = 0;
  let isDragging = false;
  let startX = 0;
  let startY = 0;

  function applyTransform(): void {
    inner.style.transform = `translate(${translateX}px, ${translateY}px) scale(${scale})`;
  }

  function zoom(factor: number): void {
    const oldScale = scale;
    scale = Math.max(0.5, Math.min(8, scale * factor));
    // Zoom toward center
    const rect = viewport.getBoundingClientRect();
    const cx = rect.width / 2;
    const cy = rect.height / 2;
    translateX = cx - (cx - translateX) * (scale / oldScale);
    translateY = cy - (cy - translateY) * (scale / oldScale);
    applyTransform();
  }

  document.getElementById('map-zoom-in')!.addEventListener('click', () => zoom(1.4));
  document.getElementById('map-zoom-out')!.addEventListener('click', () => zoom(1 / 1.4));
  document.getElementById('map-reset')!.addEventListener('click', () => {
    scale = 1;
    translateX = 0;
    translateY = 0;
    applyTransform();
  });

  viewport.addEventListener('wheel', (e) => {
    e.preventDefault();
    zoom(e.deltaY < 0 ? 1.15 : 1 / 1.15);
  }, { passive: false });

  viewport.addEventListener('mousedown', (e) => {
    isDragging = true;
    startX = e.clientX - translateX;
    startY = e.clientY - translateY;
    viewport.style.cursor = 'grabbing';
  });

  window.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    translateX = e.clientX - startX;
    translateY = e.clientY - startY;
    applyTransform();
  });

  window.addEventListener('mouseup', () => {
    isDragging = false;
    viewport.style.cursor = 'grab';
  });

  // Tooltip on individual state hover
  const svgEl = container.querySelector('svg')!;
  const tooltip = document.createElement('div');
  tooltip.className = 'map-tooltip';
  container.appendChild(tooltip);

  // Build state-level hit testing: for each state, store its bounding box
  const stateBounds = new Map<string, { x0: number; y0: number; x1: number; y1: number; tag: string | null; name: string }>();
  for (const [stateKey, stateData] of Object.entries(states)) {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const [rx, ry, rw, rh] of stateData.r) {
      x0 = Math.min(x0, rx);
      y0 = Math.min(y0, ry);
      x1 = Math.max(x1, rx + rw);
      y1 = Math.max(y1, ry + rh);
    }
    const tag = ownership.get(stateKey) ?? null;
    const displayName = stateKey.replace(/^STATE_/, '').replace(/_/g, ' ').toLowerCase()
      .replace(/\b\w/g, (c) => c.toUpperCase());
    stateBounds.set(stateKey, { x0, y0, x1, y1, tag, name: displayName });
  }

  svgEl.addEventListener('mousemove', (e) => {
    const rect = svgEl.getBoundingClientRect();
    const svgX = ((e.clientX - rect.left) / rect.width) * width;
    const svgY = ((e.clientY - rect.top) / rect.height) * height;

    let found: { tag: string | null; name: string } | null = null;
    for (const [, sb] of stateBounds) {
      if (svgX >= sb.x0 && svgX <= sb.x1 && svgY >= sb.y0 && svgY <= sb.y1) {
        found = sb;
        break;
      }
    }

    if (found) {
      const countryName = found.tag ? (tagNames.get(found.tag) ?? found.tag) : 'Uncolonized';
      tooltip.innerHTML = found.tag
        ? `<strong style="color:${colorMap.get(found.tag) ?? '#888'}">${countryName}</strong><br>${found.name}`
        : found.name;
      tooltip.style.opacity = '1';
      const cx = e.clientX - container.getBoundingClientRect().left + 12;
      const cy = e.clientY - container.getBoundingClientRect().top - 10;
      tooltip.style.left = `${cx}px`;
      tooltip.style.top = `${cy}px`;
    } else {
      tooltip.style.opacity = '0';
    }
  });

  svgEl.addEventListener('mouseleave', () => {
    tooltip.style.opacity = '0';
  });
}
