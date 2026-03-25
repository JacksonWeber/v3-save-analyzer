"""
Loader for Victoria 3 .v3 save files.
Handles ZIP extraction and format detection.
"""
import zipfile
import io
import os


def load_save(path: str) -> dict:
    """Load a V3 save file and return raw text content for gamestate and meta.

    Returns {"gamestate": str, "meta": str}.
    Raises ValueError for binary/ironman saves (not yet supported).
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
            raise ValueError(
                "Binary/ironman saves are not yet supported. "
                "Please use a text-format save (set 'save_as_binary = no' in pdx_settings.json)."
            )

        result["gamestate"] = gs_bytes.decode("utf-8", errors="replace")
        result["meta"] = meta_bytes.decode("utf-8", errors="replace") if meta_bytes else ""

    return result


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
