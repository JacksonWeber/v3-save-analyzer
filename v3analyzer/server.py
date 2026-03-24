"""
Web server with file upload UI for the V3 Save Analyzer.
Serves an upload page, processes uploaded .v3 saves, and displays the dashboard.
"""
import http.server
import cgi
import os
import sys
import tempfile
import traceback
import urllib.parse

from .loader import load_save
from .parser import parse_pdx
from .extractor import extract_all
from .generator import generate_dashboard

OUTPUT_DIR = None
LAST_DASHBOARD = None

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
            <button type="submit" id="submitBtn" disabled>Analyze Save</button>
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


class AnalyzerHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler with upload support."""

    def __init__(self, *args, output_dir=None, **kwargs):
        self.output_dir = output_dir or OUTPUT_DIR or "output"
        super().__init__(*args, directory=self.output_dir, **kwargs)

    def do_GET(self):
        if self.path == "/" or self.path == "/upload":
            self._serve_upload_page()
        elif self.path == "/dashboard" or self.path == "/dashboard/":
            # Serve the generated dashboard
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
        else:
            self.send_error(404)

    def _serve_upload_page(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(UPLOAD_PAGE.encode("utf-8"))

    def _handle_upload(self):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._send_error_text(400, "Expected multipart/form-data")
            return

        # Parse multipart form data
        boundary = content_type.split("boundary=")[-1].encode()
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # Extract the file from multipart data
        file_data = self._extract_file(body, boundary)
        if file_data is None:
            self._send_error_text(400, "No file uploaded")
            return

        # Save to temp file and process
        try:
            with tempfile.NamedTemporaryFile(suffix=".v3", delete=False) as tmp:
                tmp.write(file_data)
                tmp_path = tmp.name

            raw = load_save(tmp_path)
            meta_parsed = {}
            if raw.get("meta"):
                meta_parsed = parse_pdx(raw["meta"])

            gamestate = parse_pdx(raw["gamestate"])
            data = extract_all(gamestate, meta_parsed)

            output_path = os.path.join(self.output_dir, "index.html")
            generate_dashboard(data, output_path)

            # Redirect to dashboard
            self.send_response(302)
            self.send_header("Location", "/dashboard")
            self.end_headers()

        except Exception as e:
            traceback.print_exc()
            self._send_error_text(500, str(e))
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _extract_file(self, body, boundary):
        """Extract file content from multipart form data."""
        parts = body.split(b"--" + boundary)
        for part in parts:
            if b"filename=" in part and b"name=\"savefile\"" in part:
                # Split headers from body at double CRLF
                header_end = part.find(b"\r\n\r\n")
                if header_end == -1:
                    continue
                file_content = part[header_end + 4:]
                # Remove trailing \r\n--
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
        # Cleaner logging
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
