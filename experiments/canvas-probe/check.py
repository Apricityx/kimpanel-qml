#!/usr/bin/env python3
"""Measure native IM-popup screen placement on a disposable nested niri."""
import json
import argparse
import atexit
import os
from pathlib import Path
import re
import subprocess
import time
import math

from PySide6.QtGui import QImage

SOURCE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--work-dir", type=Path, default=SOURCE.parents[1] / "build/canvas-probe")
args = parser.parse_args()
ROOT = args.work_dir.resolve()
ROOT.mkdir(parents=True, exist_ok=True)
assert (ROOT / "probe").is_file(), "Build probe with build.py first"

niri_log = (ROOT / "niri.log").open("w")
niri = subprocess.Popen(["niri", "-c", str(SOURCE / "config.kdl")],
                        env=dict(os.environ, WINIT_UNIX_BACKEND="wayland"),
                        stdin=subprocess.DEVNULL, stdout=niri_log, stderr=niri_log)
atexit.register(lambda: niri.terminate() if niri.poll() is None else None)
deadline = time.monotonic() + 5
while True:
    log = (ROOT / "niri.log").read_text()
    match = re.search(r"IPC listening on: (\S+)", log)
    if match:
        break
    assert time.monotonic() < deadline and niri.poll() is None, log
    time.sleep(.03)
wayland = re.search(r"Wayland socket: (\S+)", log)[1]
ipc = match[1]
env = dict(os.environ, WAYLAND_DISPLAY=wayland, NIRI_SOCKET=ipc)
assert wayland != os.environ.get("WAYLAND_DISPLAY"), "Never claim the main seat"


def msg(*args):
    return subprocess.check_output(["niri", "msg", *args], env=env, text=True)


def region(image, color):
    x0, y0, x1, y1 = image.width(), image.height(), -1, -1
    # Search opaque BGRA runs; avoid per-pixel Python/Qt calls.
    converted = image.convertToFormat(QImage.Format.Format_ARGB32)
    data = bytes(converted.constBits())
    needle = color.to_bytes(4, "little")[:3] + b"\xff"
    stride = converted.bytesPerLine()
    for y in range(image.height()):
        row = data[y * stride:y * stride + image.width() * 4]
        first, last = row.find(needle), row.rfind(needle)
        if first >= 0:
            x0, y0 = min(x0, first // 4), min(y0, y)
            x1, y1 = max(x1, last // 4), max(y1, y)
    return None if x1 < 0 else [x0, y0, x1 - x0 + 1, y1 - y0 + 1]


def capture(name):
    time.sleep(.12)
    path = ROOT / (name + "-" + str(time.monotonic_ns()) + ".png")
    msg("action", "screenshot-screen", "--path", str(path), "--show-pointer", "false")
    deadline = time.monotonic() + 3
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(.03)
    image = QImage(str(path))
    assert not image.isNull(), path
    return dict(card=region(image, 0xff2400), app=region(image, 0x202020),
                screen=[image.width(), image.height()])


with (ROOT / "probe.log").open("w") as errors, (ROOT / "protocol.log").open("w") as protocol:
    probe = subprocess.Popen([str(ROOT / "probe")], env=env, stdin=subprocess.PIPE,
                             stdout=protocol, stderr=errors, text=True, bufsize=1)
    try:
        def command(text):
            probe.stdin.write(text + "\n")
            probe.stdin.flush()
            time.sleep(.05)

        time.sleep(.3)
        # Focus the disposable test app inside the nested compositor only.
        windows = json.loads(msg("-j", "windows"))
        window = next(w for w in windows if w["app_id"] == "popup-canvas-probe")
        msg("action", "focus-window", "--id", str(window["id"]))
        output = next(iter(json.loads(msg("-j", "outputs")).values()))
        logical = output["logical"]
        w, h = logical["width"], logical["height"]
        results = {}
        command("rect 150 150 24")
        command("draw 152 80 16 16")
        results["compact"] = capture("compact")
        command("offset -64 -64")
        results["offset"] = capture("offset")
        command("draw 360 240 96 96")
        results["expanded"] = capture("expanded")
        command("rect 180 150 24")
        command("draw 360 240 66 96")
        results["right-compensated"] = capture("right-compensated")
        command("rect 150 150 24")
        command("draw 360 240 96 96")
        command(f"rect 150 {h-150} 24")
        results["expanded-edge"] = capture("expanded-edge")
        command("draw 152 80 16 16")
        results["compact-edge"] = capture("compact-edge")
        command("rect 150 150 24")
        command(f"draw {w} {h} 150 174")
        results["full-canvas"] = capture("full-canvas")
        command("rect 180 150 24")
        command(f"draw {w} {h} 150 174")
        results["full-canvas-moved-cursor"] = capture("full-canvas-moved-cursor")
        command("rect 150 150 24")
        command("child 360 240 -80 -80 176 176")
        results["subsurface"] = capture("subsurface")
        command("rect 180 150 24")
        results["subsurface-right-before-response"] = capture("subsurface-right-before-response")
        command("child 360 240 -80 -80 146 176")
        results["subsurface-right-compensated"] = capture("subsurface-right-compensated")
        # Actual native-window animation after compensation, using the same
        # critically damped k=760 spring as Panel.qml. Sample screen pixels.
        samples = []
        displacement, velocity = 0., 0.
        for i in range(12):
            for _ in range(24):
                velocity += (-760 * (displacement - 30) - 2 * math.sqrt(760) * velocity) * .001
                displacement += velocity * .001
            command(f"child 360 240 -80 -80 {round(146 + displacement)} 176")
            if i in (0, 2, 11):
                samples.append(capture(f"spring-{i}"))
        results["spring"] = samples
        command("child 360 240 -80 -80 146 176")
        command("rect 80 200 24")
        results["subsurface-wrap-before-response"] = capture("subsurface-wrap-before-response")
        command("child 360 240 -80 -80 246 126")
        results["subsurface-wrap-compensated"] = capture("subsurface-wrap-compensated")
        command("child 440 240 -80 -80 246 126")
        results["subsurface-wrap-expanded"] = capture("subsurface-wrap-expanded")
        command(f"rect 150 {h-150} 24")
        command("child 360 240 -80 -80 176 176")
        results["subsurface-edge"] = capture("subsurface-edge")
        assert results["offset"]["card"] == results["compact"]["card"]
        assert results["right-compensated"]["card"] == results["expanded"]["card"]
        assert results["subsurface-right-compensated"]["card"] == results["subsurface"]["card"]
        assert results["subsurface-right-before-response"]["card"][0] == results["subsurface"]["card"][0] + 30
        x_start = results["subsurface"]["card"][0]
        assert x_start < samples[0]["card"][0] < samples[1]["card"][0] < samples[2]["card"][0] == x_start + 30
        assert results["subsurface-wrap-compensated"]["card"][2] < 120
        assert results["subsurface-wrap-expanded"]["card"] == results["subsurface"]["card"]
        assert results["expanded-edge"]["card"][1] != results["compact-edge"]["card"][1]
        (ROOT / "measurements.json").write_text(json.dumps(results, indent=2) + "\n")
        print(json.dumps(results, indent=2))
    finally:
        try:
            if probe.poll() is None:
                probe.stdin.write("quit\n")
                probe.stdin.flush()
                probe.wait(timeout=3)
        finally:
            if niri.poll() is None:
                niri.terminate()
                niri.wait(timeout=3)
