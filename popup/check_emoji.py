#!/usr/bin/env python3
"""Assert emoji actually paints pixels, not just a nonzero text advance."""
import argparse
import os
from pathlib import Path

from render import Renderer, QGuiApplication
from PySide6.QtTest import QTest

def assert_color_pixels(image):
    assert image is not None and not image.isNull()
    # Gray text, dark backgrounds and a blue highlight cannot satisfy this check.
    yellow = sum(1 for y in range(image.height()) for x in range(image.width())
                 if (c := image.pixelColor(x, y)).red() > 180
                 and c.green() > 120 and c.blue() < 100 and c.alpha() > 200)
    assert yellow > 40, f"Emoji glyphs are blank or monochrome: {yellow} yellow pixels"
    return yellow


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--image", type=Path, help="Check a Quickshell offscreen screenshot")
args = parser.parse_args()
app = QGuiApplication([])
if args.image:
    from PySide6.QtGui import QImage
    yellow = assert_color_pixels(QImage(str(args.image)))
    print(f"PASS: Quickshell emoji screenshot paints color pixels ({yellow})")
else:
    renderer = Renderer(argparse.Namespace(socket_fd=None, memory_fd=None))
    renderer.active = True
    output = Path(os.environ.get("KIMPANEL_TEST_OUTPUT", "build/test-output"))
    output.mkdir(parents=True, exist_ok=True)
    # Check each glyph independently so one working emoji cannot mask another.
    for session, text in enumerate(("😄", "😊", "中文😄"), start=1):
        renderer.bridge.handle(dict(visible=True, session=session, text="", caret=-1,
                                    cursor=0, candidates=[dict(label="1", text=text)]))
        QTest.qWait(850)
        yellow = assert_color_pixels(renderer.image)
        # The font fix must not replace or strip emoji on the selection path.
        assert renderer.bridge.property("candidates")[0]["text"] == text
        print(f"PASS: {text} paints real color pixels ({yellow})")
    assert renderer.image.save(str(output / "emoji-after.png"))
