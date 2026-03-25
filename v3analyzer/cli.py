#!/usr/bin/env python3
"""
Victoria 3 Save Game Analyzer

Usage:
    python3 -m v3analyzer <savefile.v3> [--output-dir DIR] [--country TAG] [--open]
    python3 -m v3analyzer <savefile.v3> --serve [--port PORT]
"""
import argparse
import os
import sys
import webbrowser
import threading

from .loader import load_save
from .parser import parse_pdx
from .extractor import extract_all
from .generator import generate_dashboard


def _build(savefile, output_dir, country=None):
    """Parse save and generate dashboard. Returns the output path."""
    print(f"Loading save file: {savefile}")
    raw = load_save(savefile)

    meta_parsed = {}
    if raw.get("meta"):
        meta_parsed = parse_pdx(raw["meta"])
    print("Parsing gamestate...")
    gamestate = parse_pdx(raw["gamestate"])

    # For melted binary saves, meta_data is embedded in gamestate
    if not meta_parsed and isinstance(gamestate.get("meta_data"), dict):
        meta_parsed = gamestate["meta_data"]

    if country:
        meta_parsed["player"] = country

    print("Extracting metrics...")
    data = extract_all(gamestate, meta_parsed)

    output_path = os.path.join(output_dir, "index.html")
    print(f"Generating dashboard: {output_path}")
    generate_dashboard(data, output_path)
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Victoria 3 Save Game Analyzer — generates an interactive HTML dashboard"
    )
    parser.add_argument(
        "savefile",
        help="Path to the .v3 save file (text format, zipped or unzipped)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default="output",
        help="Directory for the output HTML (default: ./output)",
    )
    parser.add_argument(
        "--country", "-c",
        default=None,
        help="Override player country tag (e.g., GBR, FRA, PRU)",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the generated dashboard in the default browser",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start a web server with upload UI (ignores savefile if 'none')",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="Port for the web server (default: 8080)",
    )

    args = parser.parse_args()

    # Server-only mode: just launch the upload UI
    if args.serve and args.savefile.lower() in ("none", "serve", "-"):
        from .server import run_server
        if args.open:
            threading.Timer(0.5, lambda: webbrowser.open(f"http://localhost:{args.port}")).start()
        run_server(output_dir=args.output_dir, port=args.port)
        return

    if not os.path.exists(args.savefile):
        print(f"Error: File not found: {args.savefile}", file=sys.stderr)
        sys.exit(1)

    try:
        output_path = _build(args.savefile, args.output_dir, args.country)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    abs_path = os.path.abspath(output_path)
    print(f"\n✅ Dashboard generated: {abs_path}")

    if args.serve:
        from .server import run_server
        if args.open:
            threading.Timer(0.5, lambda: webbrowser.open(f"http://localhost:{args.port}")).start()
        run_server(output_dir=args.output_dir, port=args.port)
    elif args.open:
        webbrowser.open(f"file://{abs_path}")
        print("Opened in browser.")


if __name__ == "__main__":
    main()
