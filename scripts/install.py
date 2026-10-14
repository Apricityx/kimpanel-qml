#!/usr/bin/env python3
"""Deploy a standalone user-local runtime, with backups and no activation."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = json.loads((ROOT / "native/upstream.json").read_text())
ADDONS = ("classicui", "kimpanel", "dbusfrontend")
RUNTIME = ("bridge.py", "kimpanel-qmlctl", "kimpanel", "shell", "popup", "requirements-renderer.txt")


def deployment_paths(prefix=None):
    if prefix:
        return prefix / "share/kimpanel-qml", prefix / "bin"
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return data / "kimpanel-qml", Path.home() / ".local/bin"


def backup_path(path):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return path.with_name(path.name + f".backup-{stamp}-{uuid.uuid4().hex[:8]}")


def check_addons(directory):
    info = json.loads((directory / "build-info.json").read_text())
    if any(info.get(key) != UPSTREAM[key] for key in ("version", "commit", "yoga_commit")):
        raise RuntimeError("Addon build metadata does not match native/upstream.json")
    version = subprocess.check_output(["fcitx5", "--version"], text=True).strip()
    if version != UPSTREAM["version"]:
        raise RuntimeError(f"System fcitx5 is {version}; addons target {UPSTREAM['version']}. "
                           "Update/revalidate the upstream lock and patch before installing.")
    for name in ADDONS:
        library = directory / f"lib{name}.so"
        if library.read_bytes()[:4] != b"\x7fELF":
            raise RuntimeError(f"Not an ELF shared object: {library}")
        dynamic = subprocess.check_output(["readelf", "-d", str(library)], text=True)
        if "(RPATH)" in dynamic or "(RUNPATH)" in dynamic:
            raise RuntimeError(f"Refusing runtime RPATH/RUNPATH: {library}")
        result = subprocess.run(["ldd", str(library)], capture_output=True, text=True, check=True)
        if "not found" in result.stdout:
            raise RuntimeError(f"Unresolved runtime dependency: {library}\n{result.stdout}")


def copy_runtime(stage, addons, renderer_env):
    for name in RUNTIME:
        source = ROOT / name
        if source.is_dir():
            shutil.copytree(source, stage / name, symlinks=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.log"))
        else:
            shutil.copy2(source, stage / name)
    (stage / "addon").mkdir()
    for name in ADDONS:
        shutil.copy2(addons / f"lib{name}.so", stage / "addon" / f"lib{name}.so")
    shutil.copy2(addons / "build-info.json", stage / "addon/build-info.json")
    (stage / "popup-venv").symlink_to(renderer_env, target_is_directory=True)
    (stage / "kimpanel-qmlctl").chmod(0o755)
    (stage / "popup/launch").chmod(0o755)
    # Source-only offscreen checks are intentionally not deployed.
    for name in ("check.py", "check_motion.py", "check_placement.py"):
        (stage / "popup" / name).unlink()


def install_launcher(path, contents):
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if path.exists() or path.is_symlink():
        if not path.is_symlink() and path.read_text() == contents:
            return
        backup = backup_path(path)
        path.rename(backup)
        print(f"Launcher backup: {backup}")
    try:
        path.write_text(contents)
        path.chmod(0o755)
    except BaseException:
        if path.exists() and path.is_file():
            path.unlink()
        if backup:
            backup.rename(path)
        raise


def check_renderer(environment):
    subprocess.run([str(environment / "bin/python"), "-c", "import PySide6; "
                    "assert PySide6.__version__ == '6.11.2'"], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--addon-dir", type=Path, default=ROOT / "build/addons")
    parser.add_argument("--prefix", type=Path, help="Install into PREFIX/share and PREFIX/bin")
    parser.add_argument("--renderer-env", type=Path, help="Reuse an existing PySide6 environment")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without modifying files")
    args = parser.parse_args()
    target, bindir = deployment_paths(args.prefix.resolve() if args.prefix else None)
    if target.is_symlink() or target.resolve() == ROOT or ROOT in target.resolve().parents or target.resolve() in ROOT.parents:
        raise RuntimeError("Installation target points to the source checkout. Keep the development "
                           "link, use --prefix elsewhere, or manually unlink it before standalone installation.")
    addons = args.addon_dir.resolve()
    if target.exists() and not (target / "install-info.json").is_file():
        raise RuntimeError("Existing target is not a managed installation; choose a different prefix")
    renderer_env = args.renderer_env.resolve() if args.renderer_env else target.with_name("kimpanel-qml-venv")
    if renderer_env == target.resolve() or target.resolve() in renderer_env.parents:
        raise RuntimeError("Renderer environment must live outside the replaceable runtime directory")
    for name in ("fcitx5-user-local", "kimpanel-qmlctl"):
        launcher = bindir / name
        if launcher.exists() and not launcher.is_symlink() and not launcher.is_file():
            raise RuntimeError(f"Launcher destination is not a file: {launcher}")
    print(f"Runtime: {target}\nLaunchers: {bindir}\nAddons: {addons}\nRenderer environment: {renderer_env}")
    print("No compositor/fcitx restart, autostart edits or global environment changes.")
    if args.dry_run:
        return
    check_addons(addons)
    if args.renderer_env or renderer_env.exists():
        # Reuse only verified environments, never mutate an unrelated/old venv.
        check_renderer(renderer_env)
    else:
        # Keep the venv at a stable, final path; venv shebangs cannot be relocated.
        subprocess.run([sys.executable, "-m", "venv", str(renderer_env)], check=True)
        subprocess.run([str(renderer_env / "bin/python"), "-m", "pip", "install", "-r",
                        str(ROOT / "requirements-renderer.txt")], check=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    with tempfile.TemporaryDirectory(prefix=".kimpanel-qml-stage-", dir=target.parent) as temp:
        stage = Path(temp) / "runtime"
        stage.mkdir()
        copy_runtime(stage, addons, renderer_env)
        (stage / "install-info.json").write_text(json.dumps({"upstream": UPSTREAM, "renderer_env": str(renderer_env)}, indent=2) + "\n")
        if target.exists():
            backup = backup_path(target)
            target.rename(backup)
            print(f"Runtime backup: {backup}")
        try:
            stage.rename(target)
        except BaseException:
            if backup:
                backup.rename(target)
            raise
    quoted = shlex.quote(str(target))
    install_launcher(bindir / "fcitx5-user-local", (ROOT / "packaging/fcitx5-user-local").read_text().replace(
        'qml_dir="${KIMPANEL_QML_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/kimpanel-qml}"',
        f'qml_dir={quoted}\nqml_dir="${{KIMPANEL_QML_DIR:-$qml_dir}}"'))
    install_launcher(bindir / "kimpanel-qmlctl", f"#!/usr/bin/env sh\nexec env KIMPANEL_QML_DIR={quoted} {quoted}/kimpanel-qmlctl \"$@\"\n")
    # This is a template, not an enabled entry in ~/.config/autostart.
    executable = str(bindir / "fcitx5-user-local").replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "\\$").replace("`", "\\`")
    (target / "fcitx5-user-local.desktop.example").write_text(
        "[Desktop Entry]\nType=Application\nName=Fcitx 5 QML\n"
        f'Exec="{executable}"\nTerminal=false\nNoDisplay=true\n')
    print("Installed. Review docs/install.en.md before activation.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(f"Installation failed: {error}")
