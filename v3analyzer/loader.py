"""
Loader for Victoria 3 .v3 save files.
Handles ZIP extraction and format detection.
"""
import zipfile
import io
import os


def load_save(path: str) -> dict:
    """Load a V3 save file and return raw text content for gamestate and meta."""
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
        if _is_binary(gs_bytes):
            raise ValueError(
                "Binary save format detected. Please re-save your game in text format.\n"
                "Edit pdx_settings.json and set: \"save_file_format\": \"zip_text_all\""
            )
        result["gamestate"] = gs_bytes.decode("utf-8", errors="replace")

        if meta_name:
            meta_bytes = zf.read(meta_name)
            result["meta"] = meta_bytes.decode("utf-8", errors="replace")
        else:
            result["meta"] = ""

    return result


def _is_binary(data: bytes) -> bool:
    """Heuristic check: binary saves start with non-printable bytes."""
    # Text saves start with readable ASCII like "SAV" header or direct key=value
    # Binary saves have lots of non-printable characters in the first 200 bytes
    sample = data[:500]
    non_printable = sum(
        1 for b in sample
        if b < 0x09 or (0x0E <= b < 0x20 and b != 0x1B)
    )
    # If more than 10% non-printable, it's likely binary
    return non_printable > len(sample) * 0.10
