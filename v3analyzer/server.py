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
    </style>
</head>
<body>
    <div class="upload-container">
        <h1>Victoria 3 Save Analyzer</h1>
        <p class="subtitle">Upload a save file to generate an interactive dashboard</p>

        <form id="uploadForm" action="/upload" method="POST" enctype="multipart/form-data">
            <div class="drop-zone" id="dropZone">
                <input type="file" name="savefile" id="fileInput" accept=".v3,.zip">
                <div class="icon">📂</div>
                <div class="text">Drop your <strong>.v3 save file</strong> here<br>or click to browse</div>
            </div>
            <div class="file-name" id="fileName"></div>
            <button type="submit" id="submitBtn" disabled>Upload &amp; Analyze</button>
        </form>

        <div class="loading" id="loading">
            <div class="spinner"></div>
            <div>Parsing save file & generating dashboard...</div>
        </div>

        <div class="error" id="error"></div>

        <div class="hint">
            Save must be in <strong>text format</strong>. Set
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

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            fileName.textContent = fileInput.files[0].name;
            submitBtn.disabled = false;
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

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        errorDiv.classList.remove('active');
        loading.classList.add('active');
        submitBtn.disabled = true;

        const formData = new FormData(form);
        fetch('/upload', { method: 'POST', body: formData })
            .then(resp => {
                if (resp.redirected) {
                    window.location.href = resp.url;
                } else {
                    return resp.text().then(text => {
                        throw new Error(text || 'Upload failed');
                    });
                }
            })
            .catch(err => {
                loading.classList.remove('active');
                submitBtn.disabled = false;
                errorDiv.textContent = err.message;
                errorDiv.classList.add('active');
            });
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


class AnalyzerHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler with upload support."""

    def __init__(self, *args, output_dir=None, **kwargs):
        self.output_dir = output_dir or OUTPUT_DIR or "output"
        super().__init__(*args, directory=self.output_dir, **kwargs)

    def do_GET(self):
        if self.path == "/" or self.path == "/upload":
            self._serve_upload_page()
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

    def _serve_upload_page(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(UPLOAD_PAGE.encode("utf-8"))

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

            # Cache parsed data for the generate step
            _CACHED_GAMESTATE = gamestate
            _CACHED_META = meta_parsed

            # Redirect to country selection
            self.send_response(302)
            self.send_header("Location", "/select")
            self.end_headers()

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
    print(f"\n🌐 V3 Save Analyzer running at http://localhost:{port}")
    print("   Upload a .v3 save file to analyze it.")
    print("   Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()
