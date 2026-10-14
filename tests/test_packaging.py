"""Packaging checks use temporary directories and mocks, never the live runtime."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("installer", ROOT / "scripts/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class TestPackaging(unittest.TestCase):
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
            with patch.object(installer.subprocess, "check_output", return_value="5.1.23\n"):
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
            installer.copy_runtime(stage, addons, base / "env")
            self.assertEqual((stage / "popup/Panel.qml").resolve(), stage / "shell/Panel.qml")
            self.assertTrue((stage / "popup-venv").is_symlink())
            self.assertFalse((stage / "popup/check.py").exists())
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
