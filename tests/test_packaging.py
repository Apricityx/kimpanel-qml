"""Packaging checks use temporary directories and mocks, never the live runtime."""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("installer", ROOT / "scripts/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class TestPackaging(unittest.TestCase):
    def launcher_environment(self, **overrides):
        """Run the real launcher with only its final exec replaced; never start fcitx."""
        source = (ROOT / "packaging/fcitx5-user-local").read_text()
        command = "exec /usr/bin/fcitx5 -D --replace"
        self.assertEqual(source.count(command), 1)
        with tempfile.TemporaryDirectory(prefix="kimpanel-launcher-") as tmp:
            runtime = Path(tmp)
            (runtime / "addon").mkdir()
            for name in installer.ADDONS:
                (runtime / "addon" / f"lib{name}.so").touch()
            (runtime / "popup").mkdir()
            launch = runtime / "popup/launch"
            launch.write_text("#!/bin/sh\nexit 0\n")
            launch.chmod(0o755)
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith(("FCITX_", "KIMPANEL_"))}
            env.update(KIMPANEL_QML_DIR=str(runtime), **overrides)
            result = subprocess.run(["bash"], input=source.replace(command, "env -0"),
                                    env=env, capture_output=True, text=True)
            values = dict(item.split("=", 1) for item in result.stdout.split("\0") if "=" in item)
            return result, values

    def test_launcher_defaults_native_overlay_and_clears_stale_renderer(self):
        result, env = self.launcher_environment(FCITX_QML_POPUP_RENDERER="/stale/renderer")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(env["FCITX_KIMPANEL_NATIVE_OVERLAY"], "1")
        self.assertEqual(env["FCITX_KIMPANEL_TOOLKIT_UI"], "1")
        self.assertNotIn("FCITX_QML_POPUP_RENDERER", env)

    def test_launcher_explicit_native_popup_retains_toolkit_route(self):
        result, env = self.launcher_environment(KIMPANEL_NATIVE_UI="popup",
                                               FCITX_KIMPANEL_NATIVE_OVERLAY="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(env["FCITX_KIMPANEL_NATIVE_OVERLAY"], "0")
        self.assertEqual(env["FCITX_KIMPANEL_WAYLAND_POPUP"], "1")
        self.assertEqual(env["FCITX_KIMPANEL_TOOLKIT_UI"], "1")
        self.assertTrue(env["FCITX_QML_POPUP_RENDERER"].endswith("/popup/launch"))

    def test_launcher_explicit_cairo_popup(self):
        result, env = self.launcher_environment(KIMPANEL_NATIVE_UI="popup", FCITX_QML_POPUP="0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(env["FCITX_KIMPANEL_NATIVE_OVERLAY"], "0")
        self.assertNotIn("FCITX_QML_POPUP_RENDERER", env)

    def test_launcher_rejects_unknown_route(self):
        result, _ = self.launcher_environment(KIMPANEL_NATIVE_UI="typo")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be overlay or popup", result.stderr)

    def test_isolated_install_and_update(self):
        with tempfile.TemporaryDirectory(prefix="kimpanel-install-") as tmp:
            base = Path(tmp)
            prefix = base / "prefix with $literal"
            addons = base / "addons"
            addons.mkdir()
            for name in installer.ADDONS:
                (addons / f"lib{name}.so").write_bytes(b"test-fixture")
            (addons / "build-info.json").write_text(json.dumps(installer.UPSTREAM))
            argv = ["install.py", "--prefix", str(prefix), "--addon-dir", str(addons),
                    "--renderer-env", str(base / "env")]
            with patch.object(sys, "argv", argv), patch.object(installer, "check_addons"), \
                    patch.object(installer, "check_fonts"), \
                    patch.object(installer.subprocess, "run"):
                installer.main()
                installer.main()
            target = prefix / "share/kimpanel-qml"
            self.assertTrue((target / "install-info.json").exists())
            self.assertTrue((target / "popup/Panel.qml").exists())
            self.assertEqual(len(list(target.parent.glob("kimpanel-qml.backup-*"))), 1)
            for name in ("fcitx5-user-local", "kimpanel-qmlctl"):
                subprocess.run(["bash", "-n", str(prefix / "bin" / name)], check=True)
            self.assertTrue((target / "fcitx5-user-local.desktop.example").exists())

    def test_prefix_layout(self):
        runtime, binaries = installer.deployment_paths(Path("/example/prefix"))
        self.assertEqual(runtime, Path("/example/prefix/share/kimpanel-qml"))
        self.assertEqual(binaries, Path("/example/prefix/bin"))

    def test_source_symlink_is_never_overwritten(self):
        with tempfile.TemporaryDirectory(prefix="kimpanel-install-") as tmp:
            prefix = Path(tmp)
            (prefix / "share").mkdir()
            link = prefix / "share/kimpanel-qml"
            link.symlink_to(ROOT, target_is_directory=True)
            with patch.object(sys, "argv", ["install.py", "--prefix", str(prefix)]):
                with self.assertRaisesRegex(RuntimeError, "source checkout"):
                    installer.main()
            self.assertTrue(link.is_symlink())

    def test_unmanaged_target_is_never_overwritten(self):
        with tempfile.TemporaryDirectory(prefix="kimpanel-install-") as tmp:
            prefix = Path(tmp)
            target = prefix / "share/kimpanel-qml"
            target.mkdir(parents=True)
            marker = target / "user-file"
            marker.write_text("preserve me")
            with patch.object(sys, "argv", ["install.py", "--prefix", str(prefix)]):
                with self.assertRaisesRegex(RuntimeError, "not a managed"):
                    installer.main()
            self.assertEqual(marker.read_text(), "preserve me")

    def test_version_mismatch_rejected_before_library_checks(self):
        with tempfile.TemporaryDirectory(prefix="kimpanel-packaging-") as tmp:
            directory = Path(tmp)
            (directory / "build-info.json").write_text(json.dumps(installer.UPSTREAM))
            with patch.object(installer.subprocess, "check_output", return_value="0.0.0\n"):
                with self.assertRaisesRegex(RuntimeError, "System fcitx5"):
                    installer.check_addons(directory)

    def test_unknown_build_rejected(self):
        with tempfile.TemporaryDirectory(prefix="kimpanel-packaging-") as tmp:
            directory = Path(tmp)
            (directory / "build-info.json").write_text(json.dumps({"version": "unknown"}))
            with self.assertRaisesRegex(RuntimeError, "metadata"):
                installer.check_addons(directory)

    def test_runtime_is_source_and_experiment_free(self):
        with tempfile.TemporaryDirectory(prefix="kimpanel-packaging-") as tmp:
            base = Path(tmp)
            addons, stage = base / "addons", base / "stage"
            addons.mkdir()
            stage.mkdir()
            for name in installer.ADDONS:
                (addons / f"lib{name}.so").write_bytes(b"test-fixture")
            (addons / "build-info.json").write_text(json.dumps(installer.UPSTREAM))
            # Test font deployment even on fresh clones with no downloaded TTF.
            source = base / "source"
            source.mkdir()
            for name in installer.RUNTIME:
                if name != "assets":
                    (source / name).symlink_to(ROOT / name, target_is_directory=(ROOT / name).is_dir())
            fonts = source / "assets/fonts"
            fonts.mkdir(parents=True)
            (fonts / "NotoColorEmoji.ttf").write_bytes(b"font fixture")
            (fonts / "LICENSE").write_bytes(b"license fixture")
            with patch.object(installer, "ROOT", source):
                installer.copy_runtime(stage, addons, base / "env")
            self.assertEqual((stage / "assets/fonts/NotoColorEmoji.ttf").read_bytes(), b"font fixture")
            self.assertEqual((stage / "assets/fonts/LICENSE").read_bytes(), b"license fixture")
            self.assertEqual((stage / "popup/Panel.qml").resolve(), stage / "shell/Panel.qml")
            self.assertTrue((stage / "popup-venv").is_symlink())
            self.assertFalse((stage / "popup/check.py").exists())
            self.assertFalse((stage / "popup/check_emoji.py").exists())
            self.assertFalse((stage / "experiments").exists())
            self.assertFalse(list(stage.rglob("__pycache__")))
            self.assertEqual(len(list((stage / "addon").glob("*.so"))), 3)

    def test_launcher_backup_and_idempotence(self):
        with tempfile.TemporaryDirectory(prefix="kimpanel-packaging-") as tmp:
            launcher = Path(tmp) / "bin/tool"
            installer.install_launcher(launcher, "#!/bin/sh\nexit 0\n")
            installer.install_launcher(launcher, "#!/bin/sh\nexit 0\n")
            self.assertFalse(list(launcher.parent.glob("*.backup-*")))
            installer.install_launcher(launcher, "#!/bin/sh\nexit 1\n")
            backups = list(launcher.parent.glob("*.backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), "#!/bin/sh\nexit 0\n")

    def test_shared_qml_links_are_relative_and_valid(self):
        for link in (ROOT / "popup").iterdir():
            if link.is_symlink():
                self.assertFalse(link.readlink().is_absolute())
                self.assertTrue(link.exists(), link)

    def test_documentation_links(self):
        documents = [ROOT / "README.md", ROOT / "README.zh-CN.md", ROOT / "NOTICE.md",
                     *ROOT.glob("CONTRIBUTING*.md"), *(ROOT / "docs").glob("*.md"),
                     *(ROOT / "experiments/canvas-probe").glob("*.md")]
        for document in documents:
            for link in re.findall(r"\]\(([^)]+)\)", document.read_text()):
                if "://" not in link and not link.startswith("#"):
                    self.assertTrue((document.parent / link.split("#")[0]).exists(), (document, link))

    def test_git_status_preserves_leading_space(self):
        spec = importlib.util.spec_from_file_location("builder", ROOT / "scripts/build.py")
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        with patch.object(builder.subprocess, "check_output", return_value=" M src/example.cpp\n"):
            self.assertEqual(builder.git_output(ROOT, "status"), " M src/example.cpp")
