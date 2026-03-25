"""
Loader for Victoria 3 .v3 save files.
Handles ZIP extraction and format detection.
For binary/ironman saves, uses Rakaly CLI to melt to text first.
"""
import zipfile
import subprocess
import tempfile
import shutil
import io
import os


def load_save(path: str) -> dict:
    """Load a V3 save file and return raw text content for gamestate and meta.

    Returns {"gamestate": str, "meta": str}.
    Binary saves are automatically melted to text via Rakaly CLI.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Save file not found: {path}")

    if zipfile.is_zipfile(path):
        return _load_zip(path)
    else:
        # Might be an already-extracted gamestate file
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        return {"gamestate": text, "meta": ""}


def _load_zip(path: str) -> dict:
    """Extract gamestate and meta from a zipped .v3 save."""
    result = {}
    with zipfile.ZipFile(path, "r") as zf:
        names = zf.namelist()

        gamestate_name = None
        meta_name = None
        for name in names:
            lower = name.lower()
            if "gamestate" in lower:
                gamestate_name = name
            elif "meta" in lower:
                meta_name = name

        if gamestate_name is None:
            raise ValueError(
                f"No 'gamestate' file found in ZIP. Contents: {names}"
            )

        gs_bytes = zf.read(gamestate_name)
        meta_bytes = zf.read(meta_name) if meta_name else b""

        if _is_binary(gs_bytes):
            return _melt_binary_save(path)

        result["gamestate"] = gs_bytes.decode("utf-8", errors="replace")
        result["meta"] = meta_bytes.decode("utf-8", errors="replace") if meta_bytes else ""

    return result


def _melt_binary_save(path: str) -> dict:
    """Use Rakaly CLI to convert a binary save to text format."""
    rakaly = _find_rakaly()
    if rakaly is None:
        raise ValueError(
            "Binary/ironman save detected but Rakaly CLI not found.\n"
            "Install it with: python3 -m v3analyzer install-rakaly\n"
            "Or download from: https://github.com/rakaly/cli/releases\n"
            "Place the 'rakaly' binary next to the v3analyzer package or on your PATH."
        )

    # Melt to a temp file
    tmp_out = None
    try:
        tmp_out = tempfile.mktemp(suffix=".v3")
        cmd = [rakaly, "melt", "-o", tmp_out, path]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )
        if proc.returncode != 0:
            raise ValueError(
                f"Rakaly melt failed (exit {proc.returncode}): {proc.stderr.strip()}"
            )

        # The melted file is a plain text save — load it
        with open(tmp_out, "r", encoding="utf-8", errors="replace") as f:
            melted = f.read()

        # The melted output has everything in one file with meta_data embedded
        return {"gamestate": melted, "meta": ""}

    finally:
        if tmp_out and os.path.exists(tmp_out):
            os.unlink(tmp_out)


def _find_rakaly() -> str:
    """Find the Rakaly CLI binary. Search order:
    1. Next to this module (v3analyzer/rakaly)
    2. In the project root (../rakaly relative to this module)
    3. In a rakaly-* subdirectory of project root
    4. On system PATH
    """
    module_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(module_dir)

    candidates = [
        os.path.join(module_dir, "rakaly"),
        os.path.join(project_dir, "rakaly"),
    ]

    # Check rakaly-* directories in project root
    if os.path.isdir(project_dir):
        for entry in os.listdir(project_dir):
            if entry.startswith("rakaly-") and os.path.isdir(
                os.path.join(project_dir, entry)
            ):
                candidates.append(os.path.join(project_dir, entry, "rakaly"))

    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    # Check PATH
    found = shutil.which("rakaly")
    if found:
        return found

    return None


def _is_binary(data: bytes) -> bool:
    """Check if data is Clausewitz binary format."""
    if len(data) >= 2:
        import struct
        magic = struct.unpack_from('<H', data, 0)[0]
        if magic == 0x55AD:
            return True
    sample = data[:500]
    non_printable = sum(
        1 for b in sample
        if b < 0x09 or (0x0E <= b < 0x20 and b != 0x1B)
    )
    return non_printable > len(sample) * 0.10
