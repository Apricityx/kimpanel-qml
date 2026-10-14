#!/usr/bin/env python3
"""Prepare pinned upstream source and build the three modified fcitx addons."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = json.loads((ROOT / "native/upstream.json").read_text())
ADDONS = ("classicui", "kimpanel", "dbusfrontend")
OVERLAYS = ("qmlpopup.cpp", "qmlpopup.h")


def run(args, **kwargs):
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True, **kwargs)


def git_output(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args], text=True).rstrip("\n")


def prepare(source):
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--branch", UPSTREAM["version"], "--depth", "1",
             UPSTREAM["repository"], source])
    if git_output(source, "rev-parse", "HEAD") != UPSTREAM["commit"]:
        raise RuntimeError("Upstream HEAD does not match native/upstream.json; use a fresh work directory")
    patch = ROOT / "native/patches/fcitx5-integration.patch"
    check = subprocess.run(["git", "-C", str(source), "apply", "--check", str(patch)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if check.returncode == 0:
        # Never patch a tree containing unrelated developer edits.
        if git_output(source, "status", "--porcelain", "--untracked-files=all"):
            raise RuntimeError("Refusing to modify a non-clean upstream checkout")
        run(["git", "-C", source, "apply", patch])
    else:
        reverse = subprocess.run(["git", "-C", str(source), "apply", "--reverse", "--check", str(patch)],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if reverse.returncode:
            raise RuntimeError("Integration patch conflicts; use a fresh work directory")
        # Repeated prepare is allowed only for the exact tree we manage.
        expected = {line.split(" b/", 1)[1] for line in patch.read_text().splitlines()
                    if line.startswith("diff --git ")}
        expected.update("src/ui/classic/" + name for name in OVERLAYS)
        changes = git_output(source, "status", "--porcelain", "--untracked-files=all")
        if any(line[3:] not in expected for line in changes.splitlines()):
            raise RuntimeError("Upstream checkout contains unrelated changes")
    for name in OVERLAYS:
        target = source / "src/ui/classic" / name
        contents = (ROOT / "native" / name).read_bytes()
        if target.exists() and target.read_bytes() != contents:
            raise RuntimeError(f"Refusing to overwrite edited overlay: {target}")
        target.write_bytes(contents)
    run(["git", "-C", source, "submodule", "update", "--init", "--depth", "1", "third_party/yoga"])
    if git_output(source / "third_party/yoga", "rev-parse", "HEAD") != UPSTREAM["yoga_commit"]:
        raise RuntimeError("Yoga revision does not match the upstream lock")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "build"))
    parser.add_argument("--work-dir", type=Path, default=ROOT / "build")
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument("--sysroot", type=Path, help="Optional extracted Fedora development packages")
    parser.add_argument("--cmake-arg", action="append", default=[], help="Use --cmake-arg=-DKEY=VALUE")
    args = parser.parse_args()
    work = args.work_dir.resolve()
    source, binary = work / "fcitx5", work / "fcitx5-build"
    prepare(source)
    if args.action == "prepare":
        return
    env = os.environ.copy()
    options = ["-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_SKIP_RPATH=ON",
               "-DENABLE_TEST=OFF", "-DENABLE_DOC=OFF", "-DENABLE_ENCHANT=OFF",
               "-DBUILD_SPELL_DICT=OFF", "-DUSE_SYSTEM_YOGA=OFF"]
    if args.sysroot:
        prefix = args.sysroot.resolve() / "usr"
        env["PKG_CONFIG_PATH"] = f"{prefix}/lib64/pkgconfig:{prefix}/share/pkgconfig"
        env["PKG_CONFIG_SYSROOT_DIR"] = str(args.sysroot.resolve())
        options += [f"-DCMAKE_PREFIX_PATH={prefix}", f"-DCMAKE_PROGRAM_PATH={prefix}/bin",
                    f"-DCMAKE_SHARED_LINKER_FLAGS=-L{prefix}/lib64",
                    "-DISOCODES_ISO639_JSON=/usr/share/iso-codes/json/iso_639-3.json",
                    "-DXKEYBOARDCONFIG_XKBBASE=/usr/share/X11/xkb",
                    "-DXKEYBOARDCONFIG_DATADIR=/usr/share"]
    run(["cmake", "-S", source, "-B", binary, *options, *args.cmake_arg], env=env)
    run(["cmake", "--build", binary, "--target", *ADDONS, "-j", str(max(1, args.jobs))], env=env)
    output = work / "addons"
    output.mkdir(exist_ok=True)
    for name in ADDONS:
        library = binary / "bin" / f"lib{name}.so"
        dynamic = subprocess.check_output(["readelf", "-d", str(library)], text=True)
        if "(RPATH)" in dynamic or "(RUNPATH)" in dynamic:
            raise RuntimeError(f"Unexpected runtime search path in {library}")
        shutil.copy2(library, output / library.name)
    (output / "build-info.json").write_text(json.dumps(UPSTREAM, indent=2) + "\n")
    print(f"Addons ready: {output}. No core libraries installed.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        sys.exit(f"Build failed: {error}")
