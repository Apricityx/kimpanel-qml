#!/usr/bin/env python3
"""Fetch the pinned, Qt-compatible color emoji font; never alter system fonts."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "assets/fonts"
LOCK = json.loads((FONT_DIR / "upstream.json").read_text())


def verify(directory=FONT_DIR):
    for name, key in (("NotoColorEmoji.ttf", "sha256"), ("LICENSE", "license_sha256")):
        path = directory / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != LOCK[key]:
            raise RuntimeError(f"Missing or modified emoji asset: {path}; run make emoji-font")


def prepare(directory=FONT_DIR):
    font = directory / "NotoColorEmoji.ttf"
    if font.exists():
        verify(directory)  # Do not overwrite a developer's different font.
        return
    license_path = directory / "LICENSE"
    if hashlib.sha256(license_path.read_bytes()).hexdigest() != LOCK["license_sha256"]:
        raise RuntimeError("Emoji font license does not match the pinned SHA-256")
    url = f"https://raw.githubusercontent.com/googlefonts/noto-emoji/{LOCK['commit']}/{LOCK['file']}"
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read(16 * 1024 * 1024 + 1)
    if hashlib.sha256(data).hexdigest() != LOCK["sha256"]:
        raise RuntimeError("Downloaded emoji font does not match the pinned SHA-256")
    # Never leave a partially written font if downloading/writing is interrupted.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        temporary.chmod(0o644)
        temporary.replace(font)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    verify(directory)
    print(f"Prepared {font} ({LOCK['version']}); no system font configuration changed.")


if __name__ == "__main__":
    try:
        prepare()
    except (OSError, RuntimeError) as error:
        sys.exit(f"Font preparation failed: {error}")
