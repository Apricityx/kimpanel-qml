"""Font preparation is pinned, offline-testable and never touches system paths."""
import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import prepare_fonts


class TestFonts(unittest.TestCase):
    def test_missing_and_modified_assets_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with self.assertRaisesRegex(RuntimeError, "make emoji-font"):
                prepare_fonts.verify(directory)
            (directory / "NotoColorEmoji.ttf").write_bytes(b"modified")
            with self.assertRaisesRegex(RuntimeError, "modified"):
                prepare_fonts.verify(directory)

    def test_verification_checks_font_and_license(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            lock = {"sha256": hashlib.sha256(b"font").hexdigest(),
                    "license_sha256": hashlib.sha256(b"license").hexdigest()}
            (directory / "NotoColorEmoji.ttf").write_bytes(b"font")
            (directory / "LICENSE").write_bytes(b"license")
            with patch.object(prepare_fonts, "LOCK", lock):
                prepare_fonts.verify(directory)
                (directory / "LICENSE").write_bytes(b"changed")
                with self.assertRaisesRegex(RuntimeError, "LICENSE"):
                    prepare_fonts.verify(directory)

    def test_download_is_pinned_verified_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "LICENSE").write_bytes(b"license")
            lock = dict(prepare_fonts.LOCK, sha256=hashlib.sha256(b"font").hexdigest(),
                        license_sha256=hashlib.sha256(b"license").hexdigest())
            with patch.object(prepare_fonts, "LOCK", lock), \
                    patch.object(prepare_fonts.urllib.request, "urlopen", return_value=io.BytesIO(b"font")) as fetch:
                prepare_fonts.prepare(directory)
                prepare_fonts.prepare(directory)
                fetch.assert_called_once_with(
                    f"https://raw.githubusercontent.com/googlefonts/noto-emoji/{lock['commit']}/{lock['file']}",
                    timeout=60)
            self.assertEqual((directory / "NotoColorEmoji.ttf").read_bytes(), b"font")
            self.assertFalse(list(directory.glob("*.tmp")))

    def test_bad_download_never_installed(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "LICENSE").write_bytes(b"license")
            lock = dict(prepare_fonts.LOCK, license_sha256=hashlib.sha256(b"license").hexdigest())
            with patch.object(prepare_fonts, "LOCK", lock), \
                    patch.object(prepare_fonts.urllib.request, "urlopen", return_value=io.BytesIO(b"bad")):
                with self.assertRaisesRegex(RuntimeError, "Downloaded emoji font"):
                    prepare_fonts.prepare(directory)
            self.assertFalse((directory / "NotoColorEmoji.ttf").exists())

    def test_existing_modified_font_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            font = directory / "NotoColorEmoji.ttf"
            font.write_bytes(b"user font")
            with patch.object(prepare_fonts.urllib.request, "urlopen") as fetch:
                with self.assertRaisesRegex(RuntimeError, "modified"):
                    prepare_fonts.prepare(directory)
                fetch.assert_not_called()
            self.assertEqual(font.read_bytes(), b"user font")
