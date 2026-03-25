"""
Generate an SVG world map from Victoria 3 game files and save data.

Reads provinces.png and state_regions/ from the game install to build
a pixel-accurate state-level map, then colors states by ownership from
the parsed save game data.
"""
import os
import re
import json
from collections import defaultdict

# Scale factor: provinces.png is 8192x3616, we render at a smaller size
SCALE = 0.125  # → 1024x452 SVG


def parse_state_regions(game_dir: str) -> dict:
    """Parse all state region files.
    Returns: { province_hex_upper: state_name, ... }
    and { state_name: [province_hexes], ... }
    """
    sr_dir = os.path.join(game_dir, "game", "map_data", "state_regions")
    prov_to_state = {}
    state_to_provs = {}

    for fname in sorted(os.listdir(sr_dir)):
        if not fname.endswith(".txt") or fname.startswith("99_"):
            continue  # skip seas
        fpath = os.path.join(sr_dir, fname)
        with open(fpath, "r", encoding="utf-8-sig") as f:
            content = f.read()

        # Find each STATE_XXX block and its provinces list
        for m in re.finditer(
            r'(STATE_\w+)\s*=\s*\{[^}]*?provinces\s*=\s*\{([^}]+)\}',
            content, re.DOTALL
        ):
            state_name = m.group(1)
            provs_raw = m.group(2)
            # Province hex codes like "x0974E5"
            hexcodes = re.findall(r'"x([0-9A-Fa-f]{6})"', provs_raw)
            provs = [h.upper() for h in hexcodes]
            state_to_provs[state_name] = provs
            for p in provs:
                prov_to_state[p] = state_name

    return prov_to_state, state_to_provs


def scan_provinces_png(game_dir: str, prov_to_state: dict) -> dict:
    """Scan provinces.png and compute pixel regions for each state.
    Returns: { state_name: {"rows": {y: [(x_start, x_end), ...]}, "cx":, "cy":} }
    Uses run-length encoding per row for compact SVG output.
    """
    from PIL import Image

    img_path = os.path.join(game_dir, "game", "map_data", "provinces.png")
    img = Image.open(img_path)
    pixels = img.load()
    w, h = img.size

    # Build RGB → state lookup from hex codes
    rgb_to_state = {}
    for hex_code, state in prov_to_state.items():
        r = int(hex_code[0:2], 16)
        g = int(hex_code[2:4], 16)
        b = int(hex_code[4:6], 16)
        rgb_to_state[(r, g, b)] = state

    # Scan every Nth pixel and build run-length rows per state
    step = 4
    state_runs = defaultdict(lambda: defaultdict(list))  # state → y → [(x_start, x_end)]
    state_xs = defaultdict(list)
    state_ys = defaultdict(list)

    for y in range(0, h, step):
        # Scan this row, grouping consecutive pixels of same state
        cur_state = None
        run_start = 0
        for x in range(0, w, step):
            color = pixels[x, y][:3]
            state = rgb_to_state.get(color)
            if state != cur_state:
                if cur_state and run_start < x:
                    state_runs[cur_state][y].append((run_start, x))
                cur_state = state
                run_start = x
        if cur_state:
            state_runs[cur_state][y].append((run_start, w))

    # Compute centroids
    state_bounds = {}
    for state, rows in state_runs.items():
        all_x = []
        all_y = []
        total_pixels = 0
        for y, runs in rows.items():
            for x0, x1 in runs:
                mid = (x0 + x1) // 2
                all_x.append(mid)
                all_y.append(y)
                total_pixels += (x1 - x0) // step
        if all_x:
            state_bounds[state] = {
                "rows": dict(rows),
                "cx": sum(all_x) // len(all_x),
                "cy": sum(all_y) // len(all_y),
                "pixel_count": total_pixels,
            }

    return state_bounds


def build_state_rects(state_bounds: dict, scale: float) -> dict:
    """Convert run-length row data to scaled SVG rectangles."""
    step = 4  # matches scan step
    rect_h = int(step * scale + 1)
    state_rects = {}

    for state, info in state_bounds.items():
        rects = []
        for y_str, runs in info["rows"].items():
            y = int(y_str) if isinstance(y_str, str) else y_str
            sy = int(y * scale)
            for x0, x1 in runs:
                sx = int(x0 * scale)
                sw = int((x1 - x0) * scale) + 1
                if sw > 0:
                    rects.append((sx, sy, sw, rect_h))

        state_rects[state] = {
            "rects": rects,
            "cx": int(info["cx"] * scale),
            "cy": int(info["cy"] * scale),
        }

    return state_rects


def generate_map_svg(state_rects: dict, ownership: dict,
                     player_tag: str, width: int, height: int) -> str:
    """Generate SVG string with states colored by ownership."""
    country_colors = {}
    palette = [
        "#e94560", "#53917e", "#508cdc", "#ff8833", "#9b59b6",
        "#1abc9c", "#e67e22", "#3498db", "#e74c3c", "#2ecc71",
        "#f39c12", "#8e44ad", "#16a085", "#c0392b", "#27ae60",
        "#d35400", "#2980b9", "#7f8c8d", "#34495e", "#e056a0",
        "#45b7d1", "#96ceb4", "#ffeaa7", "#dfe6e9", "#fab1a0",
    ]
    player_color = "#d4a843"
    unowned_color = "#1a1a2e"
    water_color = "#0d1117"

    ci = 0
    for tag in sorted(set(ownership.values())):
        if tag == player_tag:
            country_colors[tag] = player_color
        else:
            country_colors[tag] = palette[ci % len(palette)]
            ci += 1

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'style="background:{water_color};border-radius:8px;">'
    ]

    # Group rects by color for compact SVG
    color_rects = defaultdict(list)  # color → [(state_name, rects)]
    for state_name, rdata in state_rects.items():
        tag = ownership.get(state_name)
        if tag:
            color = country_colors.get(tag, unowned_color)
        else:
            color = unowned_color
        color_rects[color].append((state_name, tag, rdata))

    # Render unowned first, then colored
    render_order = [unowned_color] + [c for c in color_rects if c != unowned_color]
    for color in render_order:
        if color not in color_rects:
            continue
        states = color_rects[color]
        opacity = '0.4' if color == unowned_color else '0.9'

        for state_name, tag, rdata in states:
            # Use SVG path with M/h/v commands for compact representation
            d_parts = []
            for x, y, w, h in rdata["rects"]:
                d_parts.append(f"M{x} {y}h{w}v{h}h-{w}z")
            if d_parts:
                title = f"{tag}: {state_name}" if tag else state_name
                svg_parts.append(
                    f'<path d="{"".join(d_parts)}" fill="{color}" opacity="{opacity}">'
                    f'<title>{title}</title></path>'
                )

    # Country labels
    label_positions = defaultdict(lambda: {"xs": [], "ys": [], "count": 0})
    for state_name, rdata in state_rects.items():
        tag = ownership.get(state_name)
        if tag:
            label_positions[tag]["xs"].append(rdata["cx"])
            label_positions[tag]["ys"].append(rdata["cy"])
            label_positions[tag]["count"] += 1

    for tag, pos in label_positions.items():
        if pos["count"] >= 2:
            cx = sum(pos["xs"]) // len(pos["xs"])
            cy = sum(pos["ys"]) // len(pos["ys"])
            label = f"★{tag}" if tag == player_tag else tag
            svg_parts.append(
                f'<text x="{cx}" y="{cy}" text-anchor="middle" '
                f'font-size="7" font-weight="bold" fill="white" '
                f'style="text-shadow:1px 1px 2px #000;pointer-events:none;">'
                f'{label}</text>'
            )

    svg_parts.append('</svg>')
    return "\n".join(svg_parts)


def generate_map_data(game_dir: str) -> dict:
    """Pre-compute map data from game files. Returns serializable dict.
    This is expensive (~10-15s) so should be cached.
    """
    prov_to_state, state_to_provs = parse_state_regions(game_dir)
    state_bounds = scan_provinces_png(game_dir, prov_to_state)

    img_path = os.path.join(game_dir, "game", "map_data", "provinces.png")
    from PIL import Image
    img = Image.open(img_path)
    w, h = img.size

    sw = round(w * SCALE)
    sh = round(h * SCALE)

    state_rects = build_state_rects(state_bounds, SCALE)

    return {
        "state_rects": state_rects,
        "width": sw,
        "height": sh,
        "state_count": len(state_rects),
    }


def build_ownership_from_save(territory_map: dict) -> dict:
    """Build state_name → country_tag mapping from save's territory_map data.
    The territory_map.countries list has entries with 'tag' and 'states' list.
    State names in the save are like 'Home Counties' but in game files they're
    'STATE_HOME_COUNTIES'. We need to map between them.
    Subjects are resolved to their overlord so they appear as one realm on the map.
    """
    subject_map = territory_map.get("subject_map", {})
    ownership = {}
    for country in territory_map.get("countries", []):
        tag = country.get("tag", "")
        # Resolve subject → overlord chain
        resolved = tag
        seen = {resolved}
        while resolved in subject_map:
            resolved = subject_map[resolved]
            if resolved in seen:
                break  # guard against circular refs
            seen.add(resolved)
        for state in country.get("states", []):
            # Use pre-computed state_key (STATE_XXX) if available,
            # otherwise convert display name back
            state_key = state.get("state_key")
            if not state_key:
                name = state.get("name", "")
                state_key = "STATE_" + name.upper().replace(" ", "_")
            ownership[state_key] = resolved
    return ownership
