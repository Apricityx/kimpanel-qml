#!/usr/bin/env python3
"""Exercise the actual renderer IPC, animation, scaling and pointer path."""
import json
import mmap
import os
from pathlib import Path
import select
import socket
import subprocess
import time

from PySide6.QtGui import QImage

SLOT = 32 * 1024 * 1024
parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
fd = os.memfd_create("qml-popup-check")
os.ftruncate(fd, SLOT * 2)
memory = mmap.mmap(fd, SLOT * 2)
OUTPUT = Path(os.environ.get("KIMPANEL_TEST_OUTPUT", Path(__file__).resolve().parents[1] / "build/test-output"))
OUTPUT.mkdir(parents=True, exist_ok=True)
log = open(OUTPUT / "popup-check.log", "w")
process = subprocess.Popen([str(Path(__file__).with_name("launch")),
                            "--socket-fd", str(child.fileno()), "--memory-fd", str(fd)],
                           pass_fds=(child.fileno(), fd), stdout=log, stderr=log)
child.close()


def send(message):
    parent.send(json.dumps(message).encode())


def collect(seconds, epoch):
    frames, messages = [], []
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if not select.select([parent], [], [], max(0, end - time.monotonic()))[0]:
            break
        raw = parent.recv(65536)
        assert raw, f"renderer exited ({process.poll()})"
        m = json.loads(raw)
        if "frame" in m:
            size = m["stride"] * m["height"]
            assert 0 < size <= SLOT
            assert m["stride"] >= m["width"] * 4
            start = m["frame"] * SLOT
            pixels = memory[start:start + size]
            send({"release": m["frame"]})
            if m["epoch"] == epoch:
                frames.append((m, pixels))
        else:
            messages.append(m)
    return frames, messages


state = {"visible": True, "epoch": 1, "session": 1, "scale": 1.25,
          # A blinking caret legitimately sends idle frames; exclude it from
          # this idle-suppression assertion, then exercise it in later updates.
          "text": "ni hao", "caret": -1, "cursor": 0,
         "candidates": [{"label": "1", "text": "你好"}, {"label": "2", "text": "拟好"}],
         "hasPrev": False, "hasNext": True, "vertical": False}
try:
    send(state)
    frames, _ = collect(1.5, 1)
    assert len(frames) > 5, f"only {len(frames)} animation frames"
    assert len({hash(p) for _, p in frames}) > 5, "animation did not change pixels"
    m, pixels = frames[-1]
    assert abs(m["width"] - m["logicalWidth"] * 1.25) <= 1
    assert any(pixels[3::4]), "frame is transparent"
    image = QImage(pixels, m["width"], m["height"], m["stride"], QImage.Format.Format_ARGB32_Premultiplied)
    image.save(str(OUTPUT / "kimpanel-popup-ipc.png"))
    idle, _ = collect(.25, 1)
    assert len(idle) <= 2, f"idle renderer keeps sending ({len(idle)} frames)"
    for kind in ("move", "press", "release"):
        send({"pointer": kind, "x": 65, "y": 65, "epoch": 1})
    _, commands = collect(.35, 1)
    assert any(c.get("command") == "select 0" and c.get("epoch") == 1 for c in commands), commands
    for kind in ("move", "press", "release"):
        send({"pointer": kind, "x": m["logicalWidth"] - 35, "y": 65, "epoch": 1})
    _, commands = collect(.35, 1)
    assert any(c.get("command") == "select 1" for c in commands), commands
    assert not any(c.get("command") in ("prev", "next") for c in commands), commands
    state.update(epoch=2, cursor=1, text="ni hao shi jie", caret=14, scale=2)
    send(state)
    changed, _ = collect(.8, 2)
    assert len(changed) > 5
    assert changed[-1][0]["width"] == changed[-1][0]["logicalWidth"] * 2
    # A replacement with the same geometry must show intermediate text pixels,
    # including inside the selected highlight, before reaching its final frame.
    state.update(epoch=3, text="ni hao", caret=6, cursor=0, scale=1.25)
    send(state)
    before, _ = collect(.8, 3)
    state.update(epoch=4, candidates=[{"label": "1", "text": "世界"}, {"label": "2", "text": "是的"}])
    send(state)
    scrolling, _ = collect(.65, 4)
    assert len(scrolling) > 8, f"text replacement only has {len(scrolling)} frames"
    bm, bp = before[-1]
    fm, fp = scrolling[-1]
    assert (bm["width"], bm["height"]) == (fm["width"], fm["height"])
    def text_pixels(pixels, meta):
        # Selected first cell: avoid card/reveal and blinking preedit caret.
        return b"".join(pixels[y * meta["stride"] + 34 * 4:y * meta["stride"] + 100 * 4]
                        for y in range(64, 92))
    start, finish = text_pixels(bp, bm), text_pixels(fp, fm)
    intermediates = {text_pixels(p, m) for m, p in scrolling}
    assert len(intermediates - {start, finish}) > 5, "highlight text switches abruptly"
    for i in range(6):
        state.update(epoch=5+i, text="n" * (i + 1), caret=i + 1,
                     candidates=[{"label": "1", "text": "快速输入"[:i % 4 + 1]},
                                 {"label": "2", "text": "测试"}])
        send(state)
        collect(.05, state["epoch"])
    settled, _ = collect(.9, state["epoch"])
    assert settled, "rapid updates never settle"
    idle, _ = collect(.1, state["epoch"])
    assert all(text_pixels(p, m) == text_pixels(settled[-1][1], settled[-1][0])
               for m, p in idle), "candidate text scroll never stops"
    send({"visible": False, "epoch": 11, "session": 1})
    interrupted, messages = collect(.12, 11)
    assert interrupted and not any(m.get("hidden") for m in messages), messages
    state.update(epoch=12, session=2, text="xin", caret=-1)
    send(state)
    resumed, messages = collect(.8, 12)
    assert len(resumed) > 5, "interrupted hide did not animate back in"
    assert not any(m.get("hidden") for m in messages), messages
    send({"visible": False, "epoch": 13, "session": 2})
    fading, messages = collect(.8, 13)
    assert len(fading) > 5
    assert any(m.get("hidden") and m.get("epoch") == 13 for m in messages)
    print(f"PASS: {len(frames)} reveal, {len(changed)} resize/highlight, {len(fading)} hide frames; "
          f"{len(scrolling)} text scroll frames; fractional/2x scale, rapid updates, idle suppression, interrupted hide, candidate selection without pager buttons")
finally:
    parent.close()
    process.wait(timeout=5)
    memory.close()
    os.close(fd)
    log.close()
