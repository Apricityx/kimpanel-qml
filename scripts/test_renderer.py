#!/usr/bin/env python3
"""Run offscreen checks with the current (PySide6-enabled) Python interpreter."""
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
output = Path(os.environ.get("KIMPANEL_TEST_OUTPUT", root / "build/test-output"))
output.mkdir(parents=True, exist_ok=True)
runtime = output / "runtime"
runtime.mkdir(mode=0o700, exist_ok=True)
env = dict(os.environ, KIMPANEL_TEST_OUTPUT=str(output.resolve()),
            KIMPANEL_RENDERER_PYTHON=sys.executable, KIMPANEL_QML_DIR=str(root),
            XDG_RUNTIME_DIR=str(runtime.resolve()),
            XDG_CACHE_HOME=str(output.resolve() / "cache"),
            XDG_CONFIG_HOME=str(output.resolve() / "settings"))
for name in ("check.py", "check_motion.py", "check_placement.py", "check_emoji.py"):
    subprocess.run([sys.executable, str(root / "popup" / name)], env=env, check=True)
