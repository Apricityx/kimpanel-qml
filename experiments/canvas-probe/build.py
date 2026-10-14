#!/usr/bin/env python3
"""Build the native popup prototype without installing it or claiming a seat."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
project = Path(__file__).resolve().parents[2]
parser.add_argument("--work-dir", type=Path, default=project / "build/canvas-probe")
parser.add_argument("--sysroot", type=Path, help="Optional extracted development packages")
parser.add_argument("--fcitx-source", type=Path, default=project / "build/fcitx5")
args = parser.parse_args()
root = args.work_dir.resolve()
root.mkdir(parents=True, exist_ok=True)
prefix = args.sysroot.resolve() / "usr" if args.sysroot else Path("/usr")
scanner = str(prefix / "bin/wayland-scanner") if (prefix / "bin/wayland-scanner").exists() else shutil.which("wayland-scanner")
assert scanner, "Install wayland-devel or provide --sysroot"
protocols = {
    "xdg-shell": prefix / "share/wayland-protocols/stable/xdg-shell/xdg-shell.xml",
    "text-input": prefix / "share/wayland-protocols/unstable/text-input/text-input-unstable-v3.xml",
    "input-method": args.fcitx_source.resolve() / "src/lib/fcitx-wayland/input-method-v2/input-method-unstable-v2.xml",
}
env = dict(os.environ)
if args.sysroot:
    env["LD_LIBRARY_PATH"] = str(prefix / "lib64")
for name, xml in protocols.items():
    assert xml.exists(), f"Missing protocol: {xml}"
    for kind, suffix in [("client-header", ".h"), ("private-code", ".c")]:
        subprocess.run([scanner, kind, str(xml), str(root / (name + suffix))], env=env, check=True)
subprocess.run([
    "gcc", "-Wall", "-Wextra", "-I" + str(prefix / "include"), "-I" + str(root),
    str(Path(__file__).with_name("probe.c")),
    *[str(root / (name + ".c")) for name in protocols],
    "-L" + str(prefix / "lib64"), "-lwayland-client", "-o", str(root / "probe"),
], check=True)
print(f"Built {root / 'probe'} (no runtime RPATH)")
