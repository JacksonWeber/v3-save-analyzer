"""
Web server with file upload UI for the V3 Save Analyzer.
Serves an upload page, processes uploaded .v3 saves, and displays the dashboard.

Flow: Upload .v3 → Select countries to compare → View dashboard
"""
import http.server
import json
import os
import sys
import tempfile
import traceback
import urllib.parse

from .loader import load_save
from .parser import parse_pdx
from .extractor import extract_all, list_countries
from .generator import generate_dashboard

# Try to find Victoria 3 game install for map generation
_GAME_DIR = None
_MAP_CACHE = None  # cached state_rects + dimensions

def _find_game_dir():
    """Auto-detect Victoria 3 install directory."""
    import platform
    candidates = []
    home = os.path.expanduser("~")
    if platform.system() == "Darwin":
        candidates.append(os.path.join(home, "Library/Application Support/Steam/steamapps/common/Victoria 3"))
    elif platform.system() == "Windows":
        for drive in ["C:", "D:", "E:"]:
            candidates.append(os.path.join(drive, "\\Program Files (x86)\\Steam\\steamapps\\common\\Victoria 3"))
            candidates.append(os.path.join(drive, "\\Program Files\\Steam\\steamapps\\common\\Victoria 3"))
    else:  # Linux
        candidates.append(os.path.join(home, ".steam/steam/steamapps/common/Victoria 3"))
        candidates.append(os.path.join(home, ".local/share/Steam/steamapps/common/Victoria 3"))

    for d in candidates:
        if os.path.isfile(os.path.join(d, "game", "map_data", "provinces.png")):
            return d
    return None


def _get_map_cache():
    """Get or build cached map data from game files."""
    global _MAP_CACHE, _GAME_DIR
    if _MAP_CACHE is not None:
        return _MAP_CACHE

    if _GAME_DIR is None:
        _GAME_DIR = _find_game_dir()
    if _GAME_DIR is None:
        return None

    try:
        from .mapgen import parse_state_regions, scan_provinces_png, build_state_rects, SCALE
        from PIL import Image

        print("[v3analyzer] Building map from game files (one-time)...")
        prov_to_state, _ = parse_state_regions(_GAME_DIR)
        state_bounds = scan_provinces_png(_GAME_DIR, prov_to_state)
        state_rects = build_state_rects(state_bounds, SCALE)

        img = Image.open(os.path.join(_GAME_DIR, "game", "map_data", "provinces.png"))
        sw, sh = round(img.size[0] * SCALE), round(img.size[1] * SCALE)

        _MAP_CACHE = {"state_rects": state_rects, "width": sw, "height": sh}
        print(f"[v3analyzer] Map ready: {len(state_rects)} states, {sw}x{sh}")
        return _MAP_CACHE
    except Exception as e:
        print(f"[v3analyzer] Map generation failed: {e}")
        return None

OUTPUT_DIR = None
# Cached parsed data between the select and generate steps
_CACHED_GAMESTATE = None
_CACHED_META = None

LANDING_PAGE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>V3 Save Analyzer</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #0d1117; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        h1 { font-size: 2.4rem; margin-bottom: 0.3rem; color: #d4a843; }
        .subtitle { color: #8b949e; margin-bottom: 2.5rem; font-size: 1.1rem; }
        .cards { display: flex; gap: 2rem; flex-wrap: wrap; justify-content: center; padding: 0 1rem; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 2.5rem 2rem; width: 340px; text-decoration: none; color: #e6edf3; transition: transform 0.2s, border-color 0.3s, box-shadow 0.3s; display: flex; flex-direction: column; align-items: center; text-align: center; }
        .card:hover { transform: translateY(-6px); border-color: #d4a843; box-shadow: 0 8px 30px rgba(212,168,67,0.15); }
        .card-icon { font-size: 3rem; margin-bottom: 1rem; }
        .card h2 { font-size: 1.4rem; margin-bottom: 0.5rem; color: #d4a843; }
        .card p { color: #8b949e; font-size: 0.95rem; line-height: 1.5; }
        .footer { margin-top: 3rem; color: #484f58; font-size: 0.85rem; }
    </style>
</head>
<body>
    <h1>Victoria 3 Tools</h1>
    <p class="subtitle">Choose a tool to get started</p>
    <div class="cards">
        <a href="/upload" class="card">
            <div class="card-icon">&#128202;</div>
            <h2>Save Game Analyzer</h2>
            <p>Upload a .v3 save file and explore a detailed dashboard of your nation&#39;s economy, military, politics, and more. Compare multiple countries side-by-side.</p>
        </a>
        <a href="/army" class="card">
            <div class="card-icon">&#9876;&#65039;</div>
            <h2>Army Composition Optimizer</h2>
            <p>Plan the perfect army. Select your technologies, general traits, and orders to see real-time stat calculations and optimal battalion compositions.</p>
        </a>
    </div>
    <p class="footer">V3 Save Analyzer</p>
</body>
</html>'''


UPLOAD_PAGE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>V3 Save Analyzer</title>
    <style>
        :root {
            --bg-primary: #1a1a2e;
            --bg-secondary: #16213e;
            --bg-card: #0f3460;
            --accent: #e94560;
            --accent2: #53917e;
            --text-primary: #eee;
            --text-secondary: #a0a0b0;
            --gold: #d4a843;
            --border: #2a2a4a;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .upload-container {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 48px;
            max-width: 560px;
            width: 90%;
            text-align: center;
        }
        h1 {
            color: var(--gold);
            font-size: 2em;
            margin-bottom: 8px;
        }
        .subtitle {
            color: var(--text-secondary);
            margin-bottom: 32px;
            font-size: 0.95em;
        }
        .drop-zone {
            border: 2px dashed var(--border);
            border-radius: 12px;
            padding: 48px 24px;
            cursor: pointer;
            transition: all 0.2s;
            margin-bottom: 24px;
            position: relative;
        }
        .drop-zone:hover, .drop-zone.drag-over {
            border-color: var(--gold);
            background: rgba(212, 168, 67, 0.05);
        }
        .drop-zone .icon { font-size: 3em; margin-bottom: 12px; }
        .drop-zone .text { color: var(--text-secondary); }
        .drop-zone .text strong { color: var(--gold); }
        .drop-zone input[type="file"] {
            position: absolute;
            inset: 0;
            opacity: 0;
            cursor: pointer;
        }
        .file-name {
            color: var(--accent2);
            font-weight: bold;
            margin: 12px 0;
            min-height: 1.5em;
        }
        button {
            background: var(--accent);
            color: white;
            border: none;
            padding: 14px 40px;
            border-radius: 8px;
            font-size: 1.1em;
            cursor: pointer;
            transition: background 0.2s;
            font-weight: bold;
        }
        button:hover { background: #c73a52; }
        button:disabled {
            background: var(--border);
            cursor: not-allowed;
        }
        .loading {
            display: none;
            margin-top: 20px;
        }
        .loading.active { display: block; }
        .spinner {
            border: 3px solid var(--border);
            border-top: 3px solid var(--gold);
            border-radius: 50%;
            width: 36px;
            height: 36px;
            animation: spin 1s linear infinite;
            margin: 0 auto 12px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .error {
            color: var(--accent);
            margin-top: 16px;
            font-size: 0.9em;
            display: none;
        }
        .error.active { display: block; }
        .hint {
            color: var(--text-secondary);
            font-size: 0.8em;
            margin-top: 24px;
            line-height: 1.6;
        }
        .hint code {
            background: var(--bg-card);
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.95em;
        }
        .status-text {
            color: var(--text-secondary);
            font-size: 0.9em;
            margin-top: 8px;
        }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js"></script>
</head>
<body>
    <div class="upload-container">
        <h1>Victoria 3 Save Analyzer</h1>
        <p class="subtitle">Upload a save file to generate an interactive dashboard</p>

        <form id="uploadForm" action="/upload" method="POST" enctype="multipart/form-data">
            <div class="drop-zone" id="dropZone">
                <input type="file" name="savefile" id="fileInput" accept=".v3,.zip">
                <div class="icon">&#128194;</div>
                <div class="text">Drop your <strong>.v3 save file</strong> here<br>or click to browse</div>
            </div>
            <div class="file-name" id="fileName"></div>
            <button type="submit" id="submitBtn" disabled>Upload &amp; Analyze</button>
        </form>

        <div class="loading" id="loading">
            <div class="spinner"></div>
            <div class="status-text" id="statusText">Reading save file...</div>
        </div>

        <div class="error" id="error"></div>

        <div class="hint">
            Supports <strong>text</strong> and <strong>zipped text</strong> saves.
            For best results set
            <code>"save_file_format": "zip_text_all"</code>
            in your <code>pdx_settings.json</code>
        </div>
    </div>

    <script>
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const fileName = document.getElementById('fileName');
    const submitBtn = document.getElementById('submitBtn');
    const form = document.getElementById('uploadForm');
    const loading = document.getElementById('loading');
    const errorDiv = document.getElementById('error');
    const statusText = document.getElementById('statusText');

    function setStatus(msg) { statusText.textContent = msg; }
    function showError(msg) {
        loading.classList.remove('active');
        submitBtn.disabled = false;
        errorDiv.innerHTML = msg;
        errorDiv.classList.add('active');
    }

    function isBinaryGamestate(bytes) {
        if (bytes.length >= 2) {
            const magic = bytes[0] | (bytes[1] << 8);
            if (magic === 0x55AD) return true;
        }
        const sample = bytes.slice(0, 500);
        let nonPrintable = 0;
        for (let i = 0; i < sample.length; i++) {
            const b = sample[i];
            if (b < 0x09 || (b >= 0x0E && b < 0x20 && b !== 0x1B))
                nonPrintable++;
        }
        return nonPrintable > sample.length * 0.10;
    }

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            fileName.textContent = fileInput.files[0].name;
            submitBtn.disabled = false;
            errorDiv.classList.remove('active');
        }
    });

    ['dragover', 'dragenter'].forEach(evt => {
        dropZone.addEventListener(evt, e => {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        });
    });
    ['dragleave', 'drop'].forEach(evt => {
        dropZone.addEventListener(evt, () => dropZone.classList.remove('drag-over'));
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        errorDiv.classList.remove('active');
        loading.classList.add('active');
        submitBtn.disabled = true;

        const file = fileInput.files[0];
        if (!file) { showError('No file selected.'); return; }

        try {
            setStatus('Reading save file...');
            const buf = await file.arrayBuffer();

            // Check if it's a ZIP
            const header = new Uint8Array(buf.slice(0, 4));
            const isZip = (header[0] === 0x50 && header[1] === 0x4B &&
                           header[2] === 0x03 && header[3] === 0x04);

            if (isZip) {
                setStatus('Extracting save archive...');
                const zip = await JSZip.loadAsync(buf);

                // Find gamestate entry
                let gsEntry = null;
                zip.forEach((path, entry) => {
                    if (path.toLowerCase().includes('gamestate')) gsEntry = entry;
                });
                if (!gsEntry) {
                    showError('No gamestate file found inside the archive.');
                    return;
                }

                // Check if binary
                setStatus('Checking save format...');
                const gsBytes = await gsEntry.async('uint8array');
                if (isBinaryGamestate(gsBytes)) {
                    setStatus('Binary/Ironman save detected — converting on server...');
                }
            }

            setStatus('Uploading to server...');
            const formData = new FormData();
            formData.append('savefile', file);

            const resp = await fetch('/upload', { method: 'POST', body: formData });
            if (resp.redirected) {
                window.location.href = resp.url;
            } else {
                const text = await resp.text();
                throw new Error(text || 'Upload failed');
            }
        } catch (err) {
            if (err.message && !errorDiv.classList.contains('active')) {
                showError(err.message);
            }
        }
    });
    </script>
</body>
</html>'''


SELECT_PAGE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Select Countries — V3 Save Analyzer</title>
    <style>
        :root {
            --bg-primary: #1a1a2e;
            --bg-secondary: #16213e;
            --bg-card: #0f3460;
            --accent: #e94560;
            --accent2: #53917e;
            --text-primary: #eee;
            --text-secondary: #a0a0b0;
            --gold: #d4a843;
            --border: #2a2a4a;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .select-container {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 36px 48px;
            max-width: 650px;
            width: 90%;
        }
        h1 { color: var(--gold); font-size: 1.6em; margin-bottom: 4px; }
        .subtitle { color: var(--text-secondary); margin-bottom: 20px; font-size: 0.9em; }
        .controls {
            display: flex;
            gap: 12px;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }
        .controls button {
            background: var(--bg-card);
            color: var(--text-secondary);
            border: 1px solid var(--border);
            padding: 6px 14px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85em;
        }
        .controls button:hover { border-color: var(--gold); color: var(--text-primary); }
        .search-box {
            flex: 1;
            min-width: 150px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 6px 12px;
            color: var(--text-primary);
            font-size: 0.9em;
        }
        .search-box:focus { outline: none; border-color: var(--gold); }
        .country-list {
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid var(--border);
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .country-item {
            display: flex;
            align-items: center;
            padding: 10px 14px;
            border-bottom: 1px solid var(--border);
            cursor: pointer;
            transition: background 0.15s;
        }
        .country-item:last-child { border-bottom: none; }
        .country-item:hover { background: rgba(212, 168, 67, 0.05); }
        .country-item.selected { background: rgba(212, 168, 67, 0.1); }
        .country-item input[type="checkbox"] {
            width: 16px; height: 16px;
            accent-color: var(--gold);
            margin-right: 12px;
            cursor: pointer;
        }
        .country-tag {
            font-weight: bold;
            color: var(--gold);
            width: 50px;
            flex-shrink: 0;
        }
        .country-name {
            flex: 1;
            color: var(--text-primary);
        }
        .country-gdp {
            color: var(--text-secondary);
            font-size: 0.85em;
            font-variant-numeric: tabular-nums;
        }
        .player-badge {
            background: var(--accent);
            color: white;
            font-size: 0.7em;
            padding: 2px 6px;
            border-radius: 4px;
            margin-left: 8px;
        }
        .count {
            color: var(--text-secondary);
            font-size: 0.85em;
            margin-bottom: 16px;
        }
        .actions {
            display: flex;
            gap: 12px;
        }
        .btn-primary {
            background: var(--accent);
            color: white;
            border: none;
            padding: 12px 32px;
            border-radius: 8px;
            font-size: 1.05em;
            cursor: pointer;
            font-weight: bold;
            flex: 1;
        }
        .btn-primary:hover { background: #c73a52; }
        .btn-primary:disabled { background: var(--border); cursor: not-allowed; }
        .btn-secondary {
            background: var(--bg-card);
            color: var(--text-primary);
            border: 1px solid var(--border);
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 1.05em;
            cursor: pointer;
        }
        .btn-secondary:hover { border-color: var(--gold); }
        .loading { display: none; text-align: center; margin-top: 16px; }
        .loading.active { display: block; }
        .spinner {
            border: 3px solid var(--border);
            border-top: 3px solid var(--gold);
            border-radius: 50%;
            width: 30px; height: 30px;
            animation: spin 1s linear infinite;
            margin: 0 auto 8px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .country-list::-webkit-scrollbar { width: 8px; }
        .country-list::-webkit-scrollbar-track { background: var(--bg-card); }
        .country-list::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
    </style>
</head>
<body>
    <div class="select-container">
        <h1>Select Countries to Compare</h1>
        <p class="subtitle">Your country is pre-selected. Pick others to compare against.</p>

        <div class="controls">
            <input type="text" class="search-box" id="search" placeholder="Search countries...">
            <button onclick="selectAll()">Select All</button>
            <button onclick="selectNone()">Clear All</button>
            <button onclick="selectTop(10)">Top 10</button>
        </div>

        <div class="count" id="countLabel">0 selected</div>
        <div class="country-list" id="countryList"></div>

        <div class="actions">
            <button class="btn-secondary" onclick="window.location='/'">← Back</button>
            <button class="btn-primary" id="generateBtn" onclick="generate()">Generate Dashboard</button>
        </div>

        <div class="loading" id="loading">
            <div class="spinner"></div>
            <div>Generating dashboard...</div>
        </div>
    </div>

    <script>
    const countries = __COUNTRIES_JSON__;

    const listEl = document.getElementById('countryList');
    const countEl = document.getElementById('countLabel');
    const searchEl = document.getElementById('search');

    function render(filter) {
        filter = (filter || '').toLowerCase();
        listEl.innerHTML = '';
        countries.forEach((c, i) => {
            if (filter && !c.tag.toLowerCase().includes(filter) && !c.name.toLowerCase().includes(filter)) return;
            const div = document.createElement('div');
            div.className = 'country-item' + (c._selected ? ' selected' : '');
            const gdp = formatNum(c.final_gdp);
            div.innerHTML = `
                <input type="checkbox" ${c._selected ? 'checked' : ''} data-idx="${i}">
                <span class="country-tag">${esc(c.tag)}</span>
                <span class="country-name">${esc(c.name)}${c.is_player ? '<span class=\\"player-badge\\">PLAYER</span>' : ''}</span>
                <span class="country-gdp">GDP: ${gdp}</span>
            `;
            div.addEventListener('click', (e) => {
                if (e.target.type === 'checkbox') return;
                c._selected = !c._selected;
                render(searchEl.value);
            });
            div.querySelector('input').addEventListener('change', (e) => {
                c._selected = e.target.checked;
                updateCount();
                div.classList.toggle('selected', c._selected);
            });
            listEl.appendChild(div);
        });
        updateCount();
    }

    function updateCount() {
        const n = countries.filter(c => c._selected).length;
        countEl.textContent = n + ' selected';
    }

    function selectAll() { countries.forEach(c => c._selected = true); render(searchEl.value); }
    function selectNone() { countries.forEach(c => c._selected = false); render(searchEl.value); }
    function selectTop(n) {
        countries.forEach((c, i) => c._selected = i < n);
        render(searchEl.value);
    }

    function formatNum(n) {
        if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
        if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
        if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
        return Math.round(n).toString();
    }

    function esc(s) {
        return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    function generate() {
        const tags = countries.filter(c => c._selected).map(c => c.tag);
        document.getElementById('loading').classList.add('active');
        document.getElementById('generateBtn').disabled = true;

        fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tags }),
        })
        .then(r => r.json())
        .then(data => { window.location.href = data.redirect; })
        .catch(err => {
            alert('Error: ' + err.message);
            document.getElementById('loading').classList.remove('active');
            document.getElementById('generateBtn').disabled = false;
        });
    }

    searchEl.addEventListener('input', () => render(searchEl.value));

    // Pre-select player country
    countries.forEach(c => { c._selected = c.is_player; });
    render();
    </script>
</body>
</html>'''


ARMY_PAGE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Army Composition Optimizer - V3 Tools</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{background:#0d1117;color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;line-height:1.5;}
a{color:#d4a843;text-decoration:none;}
a:hover{text-decoration:underline;}
header{background:#161b22;border-bottom:1px solid #30363d;padding:1rem 2rem;display:flex;align-items:center;justify-content:space-between;}
header h1{font-size:1.4rem;color:#d4a843;}
.container{max-width:1400px;margin:0 auto;padding:1.5rem;}
.grid{display:grid;grid-template-columns:340px 1fr;gap:1.5rem;}
@media(max-width:900px){.grid{grid-template-columns:1fr;}}
.panel{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:1.2rem;}
.panel h2{font-size:1.1rem;color:#d4a843;margin-bottom:0.8rem;border-bottom:1px solid #30363d;padding-bottom:0.5rem;}
.panel h3{font-size:0.95rem;color:#8b949e;margin:0.8rem 0 0.4rem;}
label{display:flex;align-items:center;gap:0.4rem;cursor:pointer;padding:2px 0;font-size:0.9rem;}
label:hover{color:#d4a843;}
input[type=checkbox],input[type=radio]{accent-color:#d4a843;}
select{background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:6px;padding:0.4rem;font-size:0.9rem;width:100%;}
select:focus{border-color:#d4a843;outline:none;}
.era-group{margin-bottom:0.6rem;}
.era-label{font-size:0.8rem;color:#d4a843;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.2rem;}
table{width:100%;border-collapse:collapse;font-size:0.85rem;}
th{text-align:left;padding:0.5rem 0.4rem;border-bottom:2px solid #30363d;color:#d4a843;font-weight:600;position:sticky;top:0;background:#161b22;}
td{padding:0.4rem;border-bottom:1px solid #21262d;}
tr:hover td{background:#1c2128;}
.group-infantry{border-left:3px solid #3fb950;}
.group-artillery{border-left:3px solid #f0883e;}
.group-cavalry{border-left:3px solid #58a6ff;}
.stat-off{color:#f0883e;}
.stat-def{color:#58a6ff;}
.stat-mor{color:#bc8cff;}
.stat-kill{color:#f85149;}
input[type=number]{background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:4px;padding:0.25rem 0.4rem;width:60px;text-align:center;font-size:0.85rem;}
input[type=number]:focus{border-color:#d4a843;outline:none;}
.totals-bar{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem;margin-top:1rem;}
.total-card{background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:0.8rem;text-align:center;}
.total-card .val{font-size:1.5rem;font-weight:700;}
.total-card .lbl{font-size:0.75rem;color:#8b949e;text-transform:uppercase;}
.warning{background:#f8514922;border:1px solid #f85149;color:#f85149;padding:0.5rem 0.8rem;border-radius:6px;margin-top:0.8rem;font-size:0.85rem;}
.rec-section{margin-top:1.5rem;}
.rec-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem;margin-top:0.8rem;}
.rec-card{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:1rem;}
.rec-card h3{color:#d4a843;margin-bottom:0.5rem;font-size:1rem;}
.rec-card .rec-score{font-size:0.8rem;color:#8b949e;margin-bottom:0.5rem;}
.rec-card ul{list-style:none;padding:0;}
.rec-card li{padding:0.15rem 0;font-size:0.85rem;}
.rec-card li span{color:#d4a843;font-weight:600;}
.trait-cat{margin-bottom:0.5rem;}
.trait-cat summary{cursor:pointer;font-size:0.9rem;color:#8b949e;padding:0.2rem 0;}
.trait-cat summary:hover{color:#d4a843;}
.trait-list{padding-left:0.2rem;max-height:200px;overflow-y:auto;}
.config-row{display:flex;gap:1rem;align-items:center;margin-bottom:0.5rem;}
.config-row label{font-size:0.9rem;white-space:nowrap;}
.btn-apply{background:#d4a843;color:#0d1117;border:none;padding:0.4rem 1rem;border-radius:6px;cursor:pointer;font-weight:600;font-size:0.85rem;margin-left:0.5rem;}
.btn-apply:hover{background:#e0b84f;}
</style>
</head>
<body>
<header>
    <h1>&#9876;&#65039; Army Composition Optimizer</h1>
    <a href="/">&#8592; Back to Home</a>
</header>
<div class="container">
<div class="grid">
<!-- LEFT PANEL: CONFIG -->
<div>
    <div class="panel" id="techPanel">
        <h2>Technologies</h2>
        <div id="techChecks"></div>
    </div>
    <div class="panel" style="margin-top:1rem;">
        <h2>General Traits</h2>
        <div id="traitChecks"></div>
    </div>
    <div class="panel" style="margin-top:1rem;">
        <h2>Orders &amp; Veterancy</h2>
        <h3>Order</h3>
        <div id="orderRadios"></div>
        <h3>Veterancy</h3>
        <select id="vetSelect"></select>
    </div>
    <div class="panel" style="margin-top:1rem;">
        <h2>Optimizer Settings</h2>
        <div class="config-row">
            <label for="totalBn">Total Battalions:</label>
            <input type="number" id="totalBn" value="20" min="1" max="100">
        </div>
        <button class="btn-apply" onclick="recalc()">Update</button>
    </div>
</div>
<!-- RIGHT PANEL: RESULTS -->
<div>
    <div class="panel">
        <h2>Unit Stats (Effective)</h2>
        <div style="overflow-x:auto;">
        <table id="unitTable">
            <thead>
                <tr><th>Unit</th><th>Group</th><th>Off</th><th>Def</th><th>Morale Loss</th><th>Kill Rate</th><th>Morale Dmg</th><th>Devastation</th><th>Upkeep</th></tr>
            </thead>
            <tbody id="unitBody"></tbody>
        </table>
        </div>
    </div>
    <div class="panel" style="margin-top:1rem;">
        <h2>Army Builder</h2>
        <table id="armyTable">
            <thead>
                <tr><th>Unit</th><th>Battalions</th><th>Total Off</th><th>Total Def</th><th>Total Morale Loss</th><th>Total Kill Rate</th></tr>
            </thead>
            <tbody id="armyBody"></tbody>
        </table>
        <div class="totals-bar" id="totalsBar"></div>
        <div id="warningBox"></div>
    </div>
    <div class="panel rec-section">
        <h2>Optimal Compositions</h2>
        <div class="rec-cards" id="recCards"></div>
    </div>
</div>
</div>
</div>

<script>
const UNITS=[
{id:"irregular_infantry",name:"Irregular Infantry",group:"infantry",offense:10,defense:10,morale_loss:15,kill_rate:0,morale_damage:0,devastation:0,occupation:0,tech:null,upkeep:[],speed:0},
{id:"line_infantry",name:"Line Infantry",group:"infantry",offense:20,defense:25,morale_loss:10,kill_rate:0,morale_damage:0,devastation:0,occupation:0,tech:"line_infantry",upkeep:[{good:"small_arms",qty:1}],speed:0},
{id:"skirmish_infantry",name:"Skirmish Infantry",group:"infantry",offense:25,defense:35,morale_loss:10,kill_rate:0,morale_damage:0,devastation:0,occupation:0,tech:"general_staff",upkeep:[{good:"small_arms",qty:2},{good:"ammunition",qty:1}],speed:0},
{id:"trench_infantry",name:"Trench Infantry",group:"infantry",offense:30,defense:40,morale_loss:8,kill_rate:0,morale_damage:0,devastation:0,occupation:0,tech:"trench_works",upkeep:[{good:"small_arms",qty:3},{good:"ammunition",qty:2}],speed:0},
{id:"squad_infantry",name:"Squad Infantry",group:"infantry",offense:40,defense:50,morale_loss:6,kill_rate:0,morale_damage:0,devastation:0,occupation:0,tech:"nco_training",upkeep:[{good:"small_arms",qty:3},{good:"ammunition",qty:3},{good:"radios",qty:1}],speed:0},
{id:"mechanized_infantry",name:"Mechanized Infantry",group:"infantry",offense:50,defense:60,morale_loss:4,kill_rate:0,morale_damage:0,devastation:0.1,occupation:0,tech:"mobile_armor",upkeep:[{good:"small_arms",qty:3},{good:"ammunition",qty:3},{good:"oil",qty:1},{good:"radios",qty:1},{good:"tanks",qty:1}],speed:0},
{id:"cannon_artillery",name:"Cannon Artillery",group:"artillery",offense:25,defense:15,morale_loss:10,kill_rate:0.1,morale_damage:0,devastation:0.1,occupation:0,tech:"artillery",upkeep:[{good:"artillery",qty:1}],speed:-0.2},
{id:"mobile_artillery",name:"Mobile Artillery",group:"artillery",offense:30,defense:15,morale_loss:8,kill_rate:0.2,morale_damage:0,devastation:0.15,occupation:0,tech:"napoleonic_warfare",upkeep:[{good:"artillery",qty:2}],speed:-0.2},
{id:"shrapnel_artillery",name:"Shrapnel Artillery",group:"artillery",offense:45,defense:25,morale_loss:6,kill_rate:0.3,morale_damage:0,devastation:0.15,occupation:0,tech:"breech_loading_artillery",upkeep:[{good:"artillery",qty:3},{good:"ammunition",qty:3}],speed:-0.2},
{id:"siege_artillery",name:"Siege Artillery",group:"artillery",offense:55,defense:30,morale_loss:6,kill_rate:0.25,morale_damage:0,devastation:0.2,occupation:0,tech:"defense_in_depth",upkeep:[{good:"artillery",qty:4},{good:"ammunition",qty:4},{good:"radios",qty:1}],speed:-0.2},
{id:"heavy_tank",name:"Heavy Tank",group:"artillery",offense:70,defense:35,morale_loss:4,kill_rate:0.25,morale_damage:0.15,devastation:0.2,occupation:0,tech:"mobile_armor",upkeep:[{good:"tanks",qty:3},{good:"artillery",qty:4},{good:"ammunition",qty:4},{good:"radios",qty:1},{good:"oil",qty:3}],speed:-0.2},
{id:"hussars",name:"Hussars",group:"cavalry",offense:15,defense:10,morale_loss:10,kill_rate:0,morale_damage:0,devastation:0,occupation:0,tech:"standing_army",upkeep:[{good:"grain",qty:1}],speed:0.25},
{id:"dragoons",name:"Dragoons",group:"cavalry",offense:20,defense:25,morale_loss:8,kill_rate:0,morale_damage:0,devastation:0,occupation:0.3,tech:"line_infantry",upkeep:[{good:"grain",qty:1},{good:"small_arms",qty:2}],speed:0},
{id:"cuirassiers",name:"Cuirassiers",group:"cavalry",offense:25,defense:20,morale_loss:8,kill_rate:0,morale_damage:0,devastation:0,occupation:0.3,tech:"line_infantry",upkeep:[{good:"grain",qty:1},{good:"small_arms",qty:2}],speed:0},
{id:"lancers",name:"Lancers",group:"cavalry",offense:30,defense:20,morale_loss:6,kill_rate:0.05,morale_damage:0,devastation:0,occupation:0.3,tech:"napoleonic_warfare",upkeep:[{good:"grain",qty:2},{good:"small_arms",qty:2},{good:"iron",qty:2}],speed:0,morale_loss_mult:0.05},
{id:"light_tanks",name:"Light Tanks",group:"cavalry",offense:45,defense:45,morale_loss:4,kill_rate:0,morale_damage:0,devastation:0.1,occupation:0.3,tech:"mobile_armor",upkeep:[{good:"tanks",qty:2},{good:"artillery",qty:2},{good:"oil",qty:2},{good:"ammunition",qty:2},{good:"radios",qty:2}],speed:0.2}
];

// Upgrade paths from game data — if ANY upgrade is available, the base unit is superseded
const UPGRADES={
irregular_infantry:["line_infantry","skirmish_infantry","trench_infantry","squad_infantry","mechanized_infantry"],
line_infantry:["skirmish_infantry","trench_infantry","squad_infantry","mechanized_infantry"],
skirmish_infantry:["trench_infantry","squad_infantry","mechanized_infantry"],
trench_infantry:["squad_infantry","mechanized_infantry"],
squad_infantry:["mechanized_infantry"],
cannon_artillery:["mobile_artillery","shrapnel_artillery","siege_artillery"],
mobile_artillery:["shrapnel_artillery","siege_artillery"],
shrapnel_artillery:["siege_artillery"],
hussars:["dragoons","cuirassiers","lancers"]
};

const TECHNOLOGIES=[
{id:"standing_army",name:"Standing Army",era:1},
{id:"line_infantry",name:"Line Infantry",era:1},
{id:"artillery",name:"Artillery",era:1},
{id:"napoleonic_warfare",name:"Napoleonic Warfare",era:1},
{id:"general_staff",name:"General Staff",era:2},
{id:"breech_loading_artillery",name:"Breech-Loading Artillery",era:3},
{id:"trench_works",name:"Trench Works",era:4},
{id:"defense_in_depth",name:"Defense in Depth",era:4},
{id:"nco_training",name:"NCO Training",era:5},
{id:"mobile_armor",name:"Mobile Armor",era:5}
];

const TRAITS={
skill:[
{id:"basic_offensive_planner",name:"Basic Offensive Planner",mods:{unit_offense_mult:0.05}},
{id:"experienced_offensive_planner",name:"Experienced Offensive Planner",mods:{unit_offense_mult:0.1}},
{id:"expert_offensive_planner",name:"Expert Offensive Planner",mods:{unit_offense_mult:0.2}},
{id:"basic_defensive_strategist",name:"Basic Defensive Strategist",mods:{unit_defense_mult:0.1}},
{id:"experienced_defensive_strategist",name:"Experienced Defensive Strategist",mods:{unit_defense_mult:0.2}},
{id:"expert_defensive_strategist",name:"Expert Defensive Strategist",mods:{unit_defense_mult:0.3}},
{id:"basic_artillery_commander",name:"Basic Artillery Commander",mods:{unit_artillery_offense_mult:0.05}},
{id:"experienced_artillery_commander",name:"Experienced Artillery Commander",mods:{unit_artillery_offense_mult:0.1}},
{id:"expert_artillery_commander",name:"Expert Artillery Commander",mods:{unit_artillery_offense_mult:0.15}},
{id:"stalwart_defender",name:"Stalwart Defender",mods:{unit_defense_mult:0.1}},
{id:"trench_rat",name:"Trench Rat",mods:{unit_defense_add:10}},
{id:"defense_in_depth_specialist",name:"Defense in Depth Specialist",mods:{unit_defense_add:20}},
{id:"bandit",name:"Bandit",mods:{unit_morale_damage_mult:0.1}},
{id:"social_bandit",name:"Social Bandit",mods:{unit_morale_damage_mult:0.1}},
{id:"pillager",name:"Pillager",mods:{unit_devastation_mult:0.25}},
{id:"plains_commander",name:"Plains Commander",mods:{unit_offense_flat_mult:0.25}},
{id:"forest_commander",name:"Forest Commander",mods:{unit_defense_forested_mult:0.25}},
{id:"mountain_commander",name:"Mountain Commander",mods:{unit_defense_elevated_mult:0.25}},
{id:"surveyor",name:"Surveyor",mods:{battle_offense_owned_province_mult:0.1,battle_defense_owned_province_mult:0.1}},
{id:"elder",name:"Elder",mods:{unit_supply_consumption_mult:-0.1,battle_offense_owned_province_mult:0.1,battle_defense_owned_province_mult:0.1}},
{id:"resupply_commander",name:"Resupply Commander",mods:{unit_supply_consumption_mult:-0.1}},
{id:"basic_diplomat",name:"Basic Diplomat",mods:{unit_morale_recovery_mult:0.25}},
{id:"experienced_diplomat",name:"Experienced Diplomat",mods:{unit_morale_recovery_mult:0.5}},
{id:"masterful_diplomat",name:"Masterful Diplomat",mods:{unit_morale_recovery_mult:1.0}},
{id:"inept",name:"Inept",mods:{unit_morale_recovery_mult:-0.25,unit_defense_mult:-0.1,unit_offense_mult:-0.1}},
{id:"inexperienced",name:"Inexperienced",mods:{unit_morale_recovery_mult:0.10,unit_defense_mult:-0.05,unit_offense_mult:-0.05}}
],
personality:[
{id:"direct",name:"Direct",mods:{unit_offense_mult:0.1}},
{id:"persistent",name:"Persistent",mods:{unit_morale_loss_mult:-0.15}},
{id:"cautious",name:"Cautious",mods:{unit_morale_loss_mult:-0.05}},
{id:"brave",name:"Brave",mods:{unit_morale_loss_mult:-0.1}},
{id:"innovative",name:"Innovative",mods:{unit_morale_loss_mult:-0.15}},
{id:"imposing",name:"Imposing",mods:{unit_morale_loss_mult:-0.1}},
{id:"reserved",name:"Reserved",mods:{unit_morale_loss_mult:-0.1}},
{id:"meticulous",name:"Meticulous",mods:{unit_offense_mult:0.05,unit_defense_mult:0.05,unit_recovery_rate_add:0.1}},
{id:"charismatic",name:"Charismatic",mods:{unit_morale_recovery_mult:0.1}},
{id:"tactful",name:"Tactful",mods:{unit_defense_add:5,unit_morale_damage_mult:-0.05}},
{id:"cruel",name:"Cruel",mods:{unit_kill_rate_add:0.10}},
{id:"wrathful",name:"Wrathful",mods:{unit_morale_loss_mult:0.05,unit_morale_damage_mult:0.1}},
{id:"ambitious",name:"Ambitious",mods:{unit_offense_mult:0.05,unit_recovery_rate_add:-0.05}},
{id:"bigoted",name:"Bigoted",mods:{unit_offense_mult:0.05,unit_morale_loss_mult:0.05}},
{id:"romantic",name:"Romantic",mods:{unit_morale_loss_mult:-0.1,unit_offense_mult:-0.1}},
{id:"pious",name:"Pious",mods:{unit_kill_rate_add:-0.1,unit_morale_loss_mult:-0.25,unit_morale_recovery_mult:0.25}},
{id:"imperious",name:"Imperious",mods:{unit_morale_loss_mult:-0.15,unit_morale_recovery_mult:-0.15}},
{id:"reckless",name:"Reckless",mods:{unit_recovery_rate_add:-0.1}},
{id:"hedonist",name:"Hedonist",mods:{unit_supply_consumption_mult:0.1,unit_morale_recovery_mult:0.05}}
],
condition:[
{id:"alcoholic",name:"Alcoholic",mods:{unit_morale_damage_mult:-0.1}},
{id:"shellshocked",name:"Shellshocked",mods:{unit_morale_loss_mult:0.2,unit_offense_mult:-0.2,unit_defense_mult:-0.2}},
{id:"war_criminal",name:"War Criminal",mods:{unit_kill_rate_add:0.1}},
{id:"wounded",name:"Wounded",mods:{unit_morale_loss_mult:0.1}},
{id:"senile",name:"Senile",mods:{unit_morale_loss_mult:0.1}},
{id:"kidney_stones",name:"Kidney Stones",mods:{unit_offense_mult:-0.1,unit_defense_mult:-0.1}},
{id:"grifter",name:"Grifter",mods:{unit_supply_consumption_mult:0.05}}
]
};

const ORDERS={
advance:{name:"Advance",mods:{unit_offense_mult:0.1},requires:null},
advance_reckless:{name:"Advance (Reckless)",mods:{unit_offense_mult:0.15,unit_morale_loss_mult:0.1,unit_recovery_rate_add:-0.1},requires:{traits:["reckless"]}},
advance_pillager:{name:"Advance (Pillage)",mods:{unit_kill_rate_add:0.3,unit_devastation_mult:1,unit_morale_damage_mult:0.2},requires:{traits:["cruel","wrathful","pillager"],any:true}},
advance_cautious:{name:"Advance (Cautious)",mods:{unit_morale_loss_mult:-0.05,unit_recovery_rate_add:0.1},requires:{traits:["cautious"]}},
advance_heavy_barrage:{name:"Advance (Heavy Barrage)",mods:{unit_devastation_mult:0.75,unit_kill_rate_add:0.25,unit_morale_damage_mult:0.15},requires:{traits:["basic_artillery_commander","experienced_artillery_commander","expert_artillery_commander"],any:true,note:"Requires 20%+ artillery"}},
advance_cavalry_assault:{name:"Advance (Cavalry Assault)",mods:{unit_morale_damage_mult:0.1,unit_offense_mult:0.1,battle_casualties_mult:0.15},requires:{note:"Requires 30%+ cavalry"}},
advance_tank_assault:{name:"Advance (Tank Assault)",mods:{unit_morale_loss_mult:-0.05,unit_offense_mult:0.15},requires:{traits:["innovative"],note:"Requires 30%+ heavy tanks"}},
defend:{name:"Defend",mods:{unit_defense_mult:0.1},requires:null},
defend_dig_in:{name:"Defend (Dig In)",mods:{unit_defense_mult:0.15,unit_supply_consumption_mult:0.2},requires:{traits:["basic_defensive_strategist","experienced_defensive_strategist","expert_defensive_strategist"],any:true}},
defend_desperate_charge:{name:"Defend (Desperate Charge)",mods:{unit_kill_rate_add:0.25,unit_morale_damage_mult:0.15,battle_casualties_mult:0.2},requires:{traits:["brave"],note:"Requires 50%+ cavalry"}},
defend_last_stand:{name:"Defend (Last Stand)",mods:{battle_casualties_mult:0.3,unit_defense_mult:0.2},requires:{traits:["stalwart_defender","trench_rat","defense_in_depth_specialist"],any:true}},
defend_guerilla:{name:"Defend (Guerrilla Warfare)",mods:{unit_defense_mult:0.1,unit_morale_loss_mult:0.25},requires:{traits:["pillager","cruel","wrathful","bandit","social_bandit"],any:true,note:"Requires 80%+ infantry"}}
};

const VETERANCY=[
{level:0,name:"No Veterancy",offense_mult:0,defense_mult:0,morale_damage_mult:0},
{level:1,name:"Veterancy I",offense_mult:0.05,defense_mult:0.05,morale_damage_mult:0},
{level:2,name:"Veterancy II",offense_mult:0.10,defense_mult:0.10,morale_damage_mult:0},
{level:3,name:"Veterancy III",offense_mult:0.15,defense_mult:0.15,morale_damage_mult:0.25},
{level:4,name:"Veterancy IV",offense_mult:0.25,defense_mult:0.25,morale_damage_mult:0.5}
];

// State
let selectedTechs = new Set();
let selectedTraits = new Set();
let selectedOrder = null;
let selectedVet = 0;
let battalions = {};

function init() {
    buildTechUI();
    buildTraitUI();
    buildOrderUI();
    buildVetUI();
    recalc();
}

function buildTechUI() {
    const container = document.getElementById("techChecks");
    const eras = {};
    TECHNOLOGIES.forEach(t => {
        if (!eras[t.era]) eras[t.era] = [];
        eras[t.era].push(t);
    });
    // Era buttons row
    const btnRow = document.createElement("div");
    btnRow.style.cssText = "display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap;";
    const allEras = Object.keys(eras).sort();
    allEras.forEach(era => {
        const btn = document.createElement("button");
        btn.textContent = "Era " + era;
        btn.style.cssText = "padding:4px 12px;border-radius:4px;border:1px solid #444;background:#21262d;color:#c9d1d9;cursor:pointer;font-size:0.8rem;";
        btn.onclick = function() { selectUpToEra(parseInt(era)); };
        btnRow.appendChild(btn);
    });
    const clearBtn = document.createElement("button");
    clearBtn.textContent = "Clear All";
    clearBtn.style.cssText = "padding:4px 12px;border-radius:4px;border:1px solid #444;background:#21262d;color:#f85149;cursor:pointer;font-size:0.8rem;";
    clearBtn.onclick = function() { selectUpToEra(0); };
    btnRow.appendChild(clearBtn);
    container.appendChild(btnRow);

    allEras.forEach(era => {
        const div = document.createElement("div");
        div.className = "era-group";
        const eraNames = {1:"Pre-1836",2:"1836\u20131861",3:"1862\u20131886",4:"1887\u20131911",5:"1911\u20131936"};
        div.innerHTML = '<div class="era-label">Era ' + era + ' <span style="color:#484f58;font-weight:normal;font-size:0.75rem;">(' + (eraNames[era]||"") + ')</span></div>';
        eras[era].forEach(t => {
            // Show what unit this tech unlocks
            const unlocks = UNITS.filter(u => u.tech === t.id).map(u => u.name);
            const unlockStr = unlocks.length ? ' <span style="color:#58a6ff;font-size:0.7rem;">\u2192 ' + unlocks.join(", ") + '</span>' : '';
            const lbl = document.createElement("label");
            lbl.innerHTML = '<input type="checkbox" data-tech="' + t.id + '" data-era="' + t.era + '" onchange="toggleTech(this)"> ' + t.name + unlockStr;
            div.appendChild(lbl);
        });
        container.appendChild(div);
    });
}

function selectUpToEra(maxEra) {
    selectedTechs.clear();
    document.querySelectorAll('#techChecks input[type=checkbox]').forEach(cb => {
        const era = parseInt(cb.dataset.era);
        cb.checked = era <= maxEra;
        if (cb.checked) selectedTechs.add(cb.dataset.tech);
    });
    recalc();
}

function buildTraitUI() {
    const container = document.getElementById("traitChecks");
    const catNames = {skill: "Skill Traits", personality: "Personality Traits", condition: "Conditions"};
    Object.keys(TRAITS).forEach(cat => {
        const details = document.createElement("details");
        details.className = "trait-cat";
        details.open = cat === "skill";
        const summary = document.createElement("summary");
        summary.textContent = catNames[cat] + " (" + TRAITS[cat].length + ")";
        details.appendChild(summary);
        const list = document.createElement("div");
        list.className = "trait-list";
        TRAITS[cat].forEach(t => {
            const lbl = document.createElement("label");
            const modStr = Object.entries(t.mods).map(([k,v]) => {
                const pct = (v > 0 ? "+" : "") + Math.round(v*100) + "%";
                return k.replace(/unit_|_mult|_add/g,"").replace(/_/g," ") + " " + pct;
            }).join(", ");
            lbl.innerHTML = '<input type="checkbox" data-trait="' + t.id + '" data-cat="' + cat + '" onchange="toggleTrait(this)"> ' + t.name + ' <span style="color:#484f58;font-size:0.75rem;">(' + modStr + ')</span>';
            list.appendChild(lbl);
        });
        details.appendChild(list);
        container.appendChild(details);
    });
}

function buildOrderUI() {
    const container = document.getElementById("orderRadios");
    const noneLbl = document.createElement("label");
    noneLbl.innerHTML = '<input type="radio" name="order" value="" checked onchange="setOrder(this)"> None';
    container.appendChild(noneLbl);
    Object.keys(ORDERS).forEach(k => {
        const o = ORDERS[k];
        const lbl = document.createElement("label");
        let tip = "";
        if (o.requires) {
            const parts = [];
            if (o.requires.traits) parts.push("Trait: " + o.requires.traits.join(o.requires.any ? " / " : " + "));
            if (o.requires.note) parts.push(o.requires.note);
            tip = ' title="' + parts.join("; ") + '"';
        }
        lbl.innerHTML = '<input type="radio" name="order" value="' + k + '" onchange="setOrder(this)"> <span' + tip + '>' + o.name + (o.requires ? ' *' : '') + '</span>';
        container.appendChild(lbl);
    });
}

function buildVetUI() {
    const sel = document.getElementById("vetSelect");
    VETERANCY.forEach(v => {
        const opt = document.createElement("option");
        opt.value = v.level;
        opt.textContent = v.name + (v.offense_mult ? " (+" + Math.round(v.offense_mult*100) + "% off/def)" : "");
        sel.appendChild(opt);
    });
    sel.onchange = function() { selectedVet = parseInt(this.value); recalc(); };
}

function toggleTech(cb) {
    if (cb.checked) selectedTechs.add(cb.dataset.tech);
    else selectedTechs.delete(cb.dataset.tech);
    recalc();
}

function toggleTrait(cb) {
    if (cb.checked) selectedTraits.add(cb.dataset.trait);
    else selectedTraits.delete(cb.dataset.trait);
    recalc();
}

function setOrder(rb) {
    selectedOrder = rb.value || null;
    recalc();
}

function getModifiers() {
    const mods = {};
    selectedTraits.forEach(tid => {
        for (const cat of Object.keys(TRAITS)) {
            const t = TRAITS[cat].find(x => x.id === tid);
            if (t) {
                Object.entries(t.mods).forEach(([k,v]) => {
                    mods[k] = (mods[k] || 0) + v;
                });
            }
        }
    });
    return mods;
}

function getAvailableUnits() {
    const techAvail = UNITS.filter(u => u.tech === null || selectedTechs.has(u.tech));
    const availIds = new Set(techAvail.map(u => u.id));
    // Hide units that have been superseded by an available upgrade
    return techAvail.filter(u => {
        const ups = UPGRADES[u.id];
        if (!ups) return true;
        return !ups.some(uid => availIds.has(uid));
    });
}

function computeStats(unit, mods) {
    const vet = VETERANCY[selectedVet] || VETERANCY[0];
    let offAdd = mods.unit_offense_add || 0;
    let defAdd = mods.unit_defense_add || 0;
    let killAdd = mods.unit_kill_rate_add || 0;
    let offMult = (mods.unit_offense_mult || 0) + vet.offense_mult;
    let defMult = (mods.unit_defense_mult || 0) + vet.defense_mult;
    let moraleMult = mods.unit_morale_loss_mult || 0;
    let moraleDmgMult = (mods.unit_morale_damage_mult || 0) + vet.morale_damage_mult;
    let devMult = mods.unit_devastation_mult || 0;

    // Artillery commander per-unit-type offense bonus
    if (unit.group === "artillery") {
        offMult += (mods.unit_artillery_offense_mult || 0);
    }

    // Unit-specific morale loss multiplier (e.g. Lancers)
    if (unit.morale_loss_mult) {
        moraleMult += unit.morale_loss_mult;
    }

    if (selectedOrder && ORDERS[selectedOrder]) {
        const om = ORDERS[selectedOrder].mods;
        if (om.unit_offense_mult) offMult += om.unit_offense_mult;
        if (om.unit_defense_mult) defMult += om.unit_defense_mult;
        if (om.unit_morale_loss_mult) moraleMult += om.unit_morale_loss_mult;
        if (om.unit_kill_rate_add) killAdd += om.unit_kill_rate_add;
        if (om.unit_morale_damage_mult) moraleDmgMult += om.unit_morale_damage_mult;
        if (om.unit_devastation_mult) devMult += om.unit_devastation_mult;
        if (om.unit_recovery_rate_add) {} // tracked but not displayed per-unit
    }

    const effOff = (unit.offense + offAdd) * (1 + offMult);
    const effDef = (unit.defense + defAdd) * (1 + defMult);
    const effMorale = unit.morale_loss * (1 + moraleMult);
    const effKill = unit.kill_rate + killAdd;
    const effMoraleDmg = unit.morale_damage + moraleDmgMult;
    const effDev = unit.devastation + devMult;

    return {offense: effOff, defense: effDef, morale_loss: effMorale, kill_rate: effKill, morale_damage: effMoraleDmg, devastation: effDev, occupation: unit.occupation, speed: unit.speed};
}

function fmtUpkeep(upkeep) {
    if (!upkeep.length) return "-";
    return upkeep.map(u => u.qty + " " + u.good.replace(/_/g," ")).join(", ");
}

function recalc() {
    const mods = getModifiers();
    const available = getAvailableUnits();
    const availIds = new Set(available.map(u => u.id));

    // Clean battalions for unavailable units
    Object.keys(battalions).forEach(k => {
        if (!availIds.has(k)) delete battalions[k];
    });

    renderUnitTable(available, mods);
    renderArmyBuilder(available, mods);
    renderRecommendations(available, mods);
}

function renderUnitTable(available, mods) {
    const tbody = document.getElementById("unitBody");
    tbody.innerHTML = "";
    const groupOrder = {infantry: 0, artillery: 1, cavalry: 2};
    const sorted = [...available].sort((a,b) => (groupOrder[a.group]||0) - (groupOrder[b.group]||0));
    sorted.forEach(u => {
        const s = computeStats(u, mods);
        const tr = document.createElement("tr");
        tr.className = "group-" + u.group;
        tr.innerHTML =
            '<td><strong>' + u.name + '</strong><br><span style="color:#484f58;font-size:0.75rem;">Base: ' + u.offense + '/' + u.defense + '/' + u.morale_loss + '/' + u.kill_rate + '</span></td>' +
            '<td>' + u.group + '</td>' +
            '<td class="stat-off">' + s.offense.toFixed(1) + '</td>' +
            '<td class="stat-def">' + s.defense.toFixed(1) + '</td>' +
            '<td class="stat-mor">' + s.morale_loss.toFixed(1) + '</td>' +
            '<td class="stat-kill">' + s.kill_rate.toFixed(2) + '</td>' +
            '<td>' + (s.morale_damage > 0 ? '+' + (s.morale_damage * 100).toFixed(0) + '%' : '-') + '</td>' +
            '<td>' + (s.devastation > 0 ? '+' + (s.devastation * 100).toFixed(0) + '%' : '-') + '</td>' +
            '<td style="font-size:0.75rem;color:#8b949e;">' + fmtUpkeep(u.upkeep) + '</td>';
        tbody.appendChild(tr);
    });
}

function renderArmyBuilder(available, mods) {
    const tbody = document.getElementById("armyBody");
    tbody.innerHTML = "";
    let totalOff = 0, totalDef = 0, totalMorale = 0, totalKill = 0, totalBn = 0, infBn = 0;
    const groupOrder = {infantry: 0, artillery: 1, cavalry: 2};
    const sorted = [...available].sort((a,b) => (groupOrder[a.group]||0) - (groupOrder[b.group]||0));
    sorted.forEach(u => {
        const s = computeStats(u, mods);
        const bn = battalions[u.id] || 0;
        const tr = document.createElement("tr");
        tr.className = "group-" + u.group;
        tr.innerHTML =
            '<td>' + u.name + '</td>' +
            '<td><input type="number" min="0" max="100" value="' + bn + '" data-uid="' + u.id + '" onchange="setBn(this)"></td>' +
            '<td class="stat-off">' + (s.offense * bn).toFixed(1) + '</td>' +
            '<td class="stat-def">' + (s.defense * bn).toFixed(1) + '</td>' +
            '<td class="stat-mor">' + (s.morale_loss * bn).toFixed(1) + '</td>' +
            '<td class="stat-kill">' + (s.kill_rate * bn).toFixed(2) + '</td>';
        tbody.appendChild(tr);
        totalOff += s.offense * bn;
        totalDef += s.defense * bn;
        totalMorale += s.morale_loss * bn;
        totalKill += s.kill_rate * bn;
        totalBn += bn;
        if (u.group === "infantry") infBn += bn;
    });

    document.getElementById("totalsBar").innerHTML =
        '<div class="total-card"><div class="val">' + totalBn + '</div><div class="lbl">Battalions</div></div>' +
        '<div class="total-card"><div class="val stat-off">' + totalOff.toFixed(1) + '</div><div class="lbl">Offense</div></div>' +
        '<div class="total-card"><div class="val stat-def">' + totalDef.toFixed(1) + '</div><div class="lbl">Defense</div></div>' +
        '<div class="total-card"><div class="val stat-mor">' + totalMorale.toFixed(1) + '</div><div class="lbl">Morale Loss</div></div>' +
        '<div class="total-card"><div class="val stat-kill">' + totalKill.toFixed(2) + '</div><div class="lbl">Kill Rate</div></div>';

    const wb = document.getElementById("warningBox");
    if (totalBn > 0 && infBn / totalBn < 0.5) {
        wb.innerHTML = '<div class="warning">&#9888; Infantry is below 50% of total battalions (' + infBn + '/' + totalBn + '). Most armies require at least 50% infantry.</div>';
    } else {
        wb.innerHTML = "";
    }
}

function setBn(input) {
    const uid = input.dataset.uid;
    const val = Math.max(0, parseInt(input.value) || 0);
    input.value = val;
    battalions[uid] = val;
    const mods = getModifiers();
    const available = getAvailableUnits();
    renderArmyBuilder(available, mods);
    renderRecommendations(available, mods);
}

function bestUnit(units, scoreFn) {
    return [...units].sort((a,b) => scoreFn(b) - scoreFn(a))[0] || null;
}

function buildComp(available, mods, ratios, N) {
    // ratios: {infantry: 0.5, artillery: 0.4, cavalry: 0.1}
    const offScore = u => { const s = computeStats(u, mods); return s.offense + s.kill_rate * 100; };
    const defScore = u => { const s = computeStats(u, mods); return s.defense; };
    const balScore = u => { const s = computeStats(u, mods); return s.offense + s.defense; };

    const comp = {};
    let assigned = 0;
    const groups = ["infantry","artillery","cavalry"];

    groups.forEach(g => {
        const pct = ratios[g] || 0;
        if (pct <= 0) return;
        const candidates = available.filter(u => u.group === g);
        if (candidates.length === 0) return;
        const pick = bestUnit(candidates, balScore);
        const cnt = Math.round(N * pct);
        comp[pick.id] = cnt;
        assigned += cnt;
    });

    // Adjust rounding to hit N exactly — add/remove from largest group
    let diff = N - assigned;
    if (diff !== 0) {
        const largestGroup = groups.reduce((best, g) => {
            const gUnits = Object.entries(comp).filter(([uid]) => UNITS.find(u => u.id === uid).group === g);
            const gTotal = gUnits.reduce((s, [,c]) => s + c, 0);
            return gTotal > (best.total || 0) ? {group: g, total: gTotal} : best;
        }, {});
        const adjustUid = Object.keys(comp).find(uid => UNITS.find(u => u.id === uid).group === largestGroup.group);
        if (adjustUid) comp[adjustUid] += diff;
    }

    // Compute totals
    let totalOff = 0, totalDef = 0, totalKill = 0, totalMorale = 0;
    Object.entries(comp).forEach(([uid, cnt]) => {
        if (cnt <= 0) return;
        const u = UNITS.find(x => x.id === uid);
        const s = computeStats(u, mods);
        totalOff += s.offense * cnt;
        totalDef += s.defense * cnt;
        totalKill += s.kill_rate * cnt;
        totalMorale += s.morale_loss * cnt;
    });
    return {comp, totalOff, totalDef, totalKill, totalMorale};
}

function renderRecommendations(available, mods) {
    const N = parseInt(document.getElementById("totalBn").value) || 20;
    const container = document.getElementById("recCards");
    container.innerHTML = "";

    const infantry = available.filter(u => u.group === "infantry");
    const artillery = available.filter(u => u.group === "artillery");
    const cavalry = available.filter(u => u.group === "cavalry");

    if (infantry.length === 0) {
        container.innerHTML = '<p style="color:#8b949e;">No infantry available. Unlock at least one infantry unit.</p>';
        return;
    }

    // Community-meta compositions (sourced from Paradox forums, Reddit, guides)
    const templates = [];

    // Always show offensive and defensive
    if (artillery.length > 0) {
        templates.push({
            name: "Offensive (Meta)",
            desc: "50/50 infantry-artillery — community consensus best offensive composition",
            ratios: {infantry: 0.5, artillery: 0.5, cavalry: 0}
        });
        templates.push({
            name: "Defensive",
            desc: "90% infantry / 10% artillery — cheap, holds the line",
            ratios: {infantry: 0.9, artillery: 0.1, cavalry: 0}
        });
    }

    // Balanced with all three groups
    if (artillery.length > 0 && cavalry.length > 0) {
        templates.push({
            name: "Balanced",
            desc: "50/40/10 infantry-artillery-cavalry — all-rounder composition",
            ratios: {infantry: 0.5, artillery: 0.4, cavalry: 0.1}
        });
    }

    // Colonial / blitz if cavalry available
    if (cavalry.length > 0) {
        templates.push({
            name: "Colonial / Blitz",
            desc: "50% infantry / 50% cavalry — fast occupation and naval invasions",
            ratios: {infantry: 0.5, artillery: 0, cavalry: 0.5}
        });
    }

    // Late-game tank composition if tanks are available
    const hasTanks = available.some(u => u.id === "heavy_tank" || u.id === "light_tanks");
    if (hasTanks && artillery.length > 0) {
        templates.push({
            name: "Armored Offensive",
            desc: "40/40/20 infantry-artillery-tanks — late-game breakthrough force",
            ratios: {infantry: 0.4, artillery: 0.4, cavalry: 0.2}
        });
    }

    // Fallback: infantry only if nothing else available
    if (artillery.length === 0 && cavalry.length === 0) {
        templates.push({
            name: "Infantry Only",
            desc: "100% infantry — no support units researched yet",
            ratios: {infantry: 1, artillery: 0, cavalry: 0}
        });
    }

    templates.forEach(tmpl => {
        const {comp, totalOff, totalDef, totalKill, totalMorale} = buildComp(available, mods, tmpl.ratios, N);

        const card = document.createElement("div");
        card.className = "rec-card";
        let listHtml = "";
        Object.entries(comp).filter(([_,c]) => c > 0).forEach(([uid, cnt]) => {
            const u = UNITS.find(x => x.id === uid);
            const s = computeStats(u, mods);
            listHtml += '<li><span>' + cnt + 'x</span> ' + u.name + ' <span style="color:#8b949e;font-size:0.75rem;">(off ' + s.offense.toFixed(0) + ' def ' + s.defense.toFixed(0) + ' kill ' + s.kill_rate.toFixed(2) + ')</span></li>';
        });
        card.innerHTML =
            '<h3>' + tmpl.name + '</h3>' +
            '<div style="color:#8b949e;font-size:0.8rem;margin-bottom:6px;">' + tmpl.desc + '</div>' +
            '<div class="rec-score">Off: ' + totalOff.toFixed(1) + ' | Def: ' + totalDef.toFixed(1) + ' | Kill: ' + totalKill.toFixed(2) + ' | Morale: ' + totalMorale.toFixed(1) + '</div>' +
            '<ul>' + listHtml + '</ul>';
        container.appendChild(card);
    });
}

init();
// Unit stats sourced from Victoria 3 game data files (common/combat_unit_types, character_traits, commander_orders, combat_unit_experience_levels)
</script>
</body>
</html>'''


class AnalyzerHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler with upload support."""

    def __init__(self, *args, output_dir=None, **kwargs):
        self.output_dir = output_dir or OUTPUT_DIR or "output"
        super().__init__(*args, directory=self.output_dir, **kwargs)

    def do_GET(self):
        if self.path == "/":
            self._serve_landing_page()
        elif self.path == "/upload":
            self._serve_upload_page()
        elif self.path == "/army":
            self._serve_army_page()
        elif self.path.startswith("/select"):
            self._serve_select_page()
        elif self.path == "/dashboard" or self.path == "/dashboard/":
            dashboard_path = os.path.join(self.output_dir, "index.html")
            if os.path.exists(dashboard_path):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(dashboard_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/upload":
            self._handle_upload()
        elif self.path == "/generate":
            self._handle_generate()
        else:
            self.send_error(404)

    def _serve_landing_page(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(LANDING_PAGE.encode("utf-8"))

    def _serve_upload_page(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(UPLOAD_PAGE.encode("utf-8"))

    def _serve_army_page(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(ARMY_PAGE.encode("utf-8"))

    def _handle_upload(self):
        """Step 1: Upload save → parse → cache data → redirect to /select."""
        global _CACHED_GAMESTATE, _CACHED_META
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._send_error_text(400, "Expected multipart/form-data")
            return

        boundary = content_type.split("boundary=")[-1].encode()
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        file_data = self._extract_file(body, boundary)
        if file_data is None:
            self._send_error_text(400, "No file uploaded")
            return

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".v3", delete=False) as tmp:
                tmp.write(file_data)
                tmp_path = tmp.name

            raw = load_save(tmp_path)

            meta_parsed = {}
            if raw.get("meta"):
                meta_parsed = parse_pdx(raw["meta"])
            gamestate = parse_pdx(raw["gamestate"])

            # For melted binary saves, meta_data is embedded in gamestate
            if not meta_parsed and isinstance(gamestate.get("meta_data"), dict):
                meta_parsed = gamestate["meta_data"]

            # Cache parsed data for the generate step
            _CACHED_GAMESTATE = gamestate
            _CACHED_META = meta_parsed

            # Redirect to country selection
            self.send_response(302)
            self.send_header("Location", "/select")
            self.end_headers()

        except ValueError as e:
            msg = str(e)
            if "Binary" in msg or "Rakaly" in msg:
                self._send_error_text(
                    400,
                    "Binary/Ironman save detected but the server cannot "
                    "convert it (Rakaly CLI not found). Options:\n"
                    "1. Use https://pdx.tools to melt it online first\n"
                    "2. Install Rakaly CLI on the server\n"
                    "3. Re-save your game with save_file_format: zip_text_all"
                )
            else:
                traceback.print_exc()
                self._send_error_text(500, msg)
        except Exception as e:
            traceback.print_exc()
            self._send_error_text(500, str(e))
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _serve_select_page(self):
        """Step 2: Show country selection page."""
        global _CACHED_GAMESTATE, _CACHED_META
        if _CACHED_GAMESTATE is None:
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return

        countries = list_countries(_CACHED_GAMESTATE, _CACHED_META or {})
        countries_json = json.dumps(countries)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html = SELECT_PAGE.replace("__COUNTRIES_JSON__", countries_json)
        self.wfile.write(html.encode("utf-8"))

    def _handle_generate(self):
        """Step 3: Generate dashboard with selected countries."""
        global _CACHED_GAMESTATE, _CACHED_META
        if _CACHED_GAMESTATE is None:
            self._send_error_text(400, "No save data cached. Please upload a save first.")
            return

        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # Parse the selected tags from the POST body (JSON)
        try:
            payload = json.loads(body.decode("utf-8"))
            selected_tags = payload.get("tags", [])
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_error_text(400, "Invalid request body")
            return

        try:
            compare = selected_tags if selected_tags else False
            data = extract_all(
                _CACHED_GAMESTATE, _CACHED_META or {},
                compare_countries=compare,
            )

            # Generate map SVG if game files available
            map_svg = ""
            map_cache = _get_map_cache()
            if map_cache and data.get("territory_map"):
                from .mapgen import generate_map_svg, build_ownership_from_save
                ownership = build_ownership_from_save(data["territory_map"])
                player_tag = data.get("meta", {}).get("player_tag", "")
                map_svg = generate_map_svg(
                    map_cache["state_rects"], ownership, player_tag,
                    map_cache["width"], map_cache["height"]
                )

            output_path = os.path.join(self.output_dir, "index.html")
            generate_dashboard(data, output_path, map_svg=map_svg)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"redirect": "/dashboard"}).encode())

        except Exception as e:
            traceback.print_exc()
            self._send_error_text(500, str(e))

    def _extract_file(self, body, boundary):
        """Extract file content from multipart form data."""
        parts = body.split(b"--" + boundary)
        for part in parts:
            if b"filename=" in part and b"name=\"savefile\"" in part:
                header_end = part.find(b"\r\n\r\n")
                if header_end == -1:
                    continue
                file_content = part[header_end + 4:]
                if file_content.endswith(b"\r\n"):
                    file_content = file_content[:-2]
                return file_content
        return None

    def _send_error_text(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(message.encode("utf-8"))

    def log_message(self, format, *args):
        sys.stderr.write(f"[v3analyzer] {args[0]}\n")


def run_server(output_dir="output", port=8080):
    """Start the analyzer web server."""
    global OUTPUT_DIR
    OUTPUT_DIR = os.path.abspath(output_dir)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    handler = lambda *args, **kwargs: AnalyzerHandler(
        *args, output_dir=OUTPUT_DIR, **kwargs
    )
    server = http.server.HTTPServer(("0.0.0.0", port), handler)
    print(f"\n[*] V3 Save Analyzer running at http://localhost:{port}")
    print("   Upload a .v3 save file to analyze it.")
    print("   Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()
