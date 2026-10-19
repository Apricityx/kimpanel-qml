#!/usr/bin/env python3
"""Test the real Quickshell Bridge offscreen using a private Unix socket."""
import json
import os
from pathlib import Path
import queue
import shutil
import socket
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "build/test-output"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="overlay-", dir=output) as temporary:
        base = Path(temporary).resolve()
        # Include spaces to ensure we no longer interpolate paths into a shell.
        config = base / "config with spaces"
        shutil.copytree(ROOT / "shell", config / "shell")
        shutil.copytree(ROOT / "assets", config / "assets")
        shutil.copy2(ROOT / "tests/fixtures/overlay.qml", config / "shell/check.qml")
        runtime = base / "runtime"
        runtime.mkdir(mode=0o700)
        path = str(base / "panel.sock")
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(path)
        server.listen()
        server.settimeout(5)
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                   KIMPANEL_QML_SOCK=path, XDG_RUNTIME_DIR=str(runtime),
                   XDG_CACHE_HOME=str(base / "cache"), XDG_CONFIG_HOME=str(base / "settings"))
        env.pop("WAYLAND_DISPLAY", None)
        env.pop("DISPLAY", None)
        proc = subprocess.Popen(["qs", "-p", str(config / "shell/check.qml")],
                                env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
        messages = queue.Queue()
        log = []

        def read_log():
            for line in proc.stdout:
                log.append(line)
                if "OVERLAY {" in line:
                    messages.put(json.loads(line.split("OVERLAY ", 1)[1]))

        thread = threading.Thread(target=read_log, daemon=True)
        thread.start()
        conn = None

        def wait_for(predicate, timeout=.6):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    item = messages.get(timeout=max(.001, deadline - time.monotonic()))
                except queue.Empty:
                    break
                if predicate(item):
                    return item
            raise AssertionError("Overlay did not receive state in time\n" + "".join(log[-8:]))

        def send(message, fragmented=False):
            raw = (json.dumps(message) + "\n").encode()
            if fragmented:
                conn.sendall(raw[:17])
                conn.sendall(raw[17:])
            else:
                conn.sendall(raw)

        try:
            conn, _ = server.accept()
            # There deliberately is no panel-state.json: socket is authoritative.
            send(dict(visible=False, session=0))
            wait_for(lambda m: not m["active"], 2)
            for session in range(1, 4):
                send(dict(visible=True, session=session, text="", cursor=0,
                          candidates=[dict(label=str(i), text="你好") for i in range(1, 6)],
                          spot=dict(x=291.3, y=926, w=2, h=18)), fragmented=True)
                shown = wait_for(lambda m: m["active"] and m["visible"]
                                 and m["session"] == session and m["count"] == 5)
                assert shown["width"] > 12 and shown["height"] > 12, shown
                assert shown["fontReady"], "Private emoji font failed to load in Quickshell"
                send(dict(visible=False, session=session))
                wait_for(lambda m: not m["active"] and m["session"] == session)
            # Verify placement metadata survives the real socket/Bridge path.
            for session, caret_top, expected_y in ((20, True, 200), (21, False, 230)):
                spot = dict(x=180, y=200, w=1, h=24)
                if caret_top:
                    spot["caretTop"] = True
                send(dict(visible=True, session=session, text="", cursor=0,
                          candidates=[dict(label="1", text="你好")], spot=spot))
                wait_for(lambda m: m["active"] and m["session"] == session
                         and abs(m["x"] - 180) < .15
                         and abs(m["y"] - expected_y) < .15, 2)
            send(dict(visible=False, session=21))
            wait_for(lambda m: not m["active"] and m["session"] == 21)
            conn.close()
            conn, _ = server.accept()
            # Hub's replay after reconnect; no new input keystroke needed.
            send(dict(visible=True, session=10, text="", cursor=0,
                      candidates=[dict(label="1", text="😄"), dict(label="2", text="😊"),
                                  dict(label="3", text="中文😄")]))
            wait_for(lambda m: m["active"] and m["session"] == 10, 2)
            screenshot = output / "emoji-overlay-after.png"
            send(dict(grab=str(screenshot)))
            conn.settimeout(3)
            assert conn.recv(4096) == b"select 0\n", "Selection command was not flushed"
            renderer_python = os.environ.get("KIMPANEL_RENDERER_PYTHON", str(ROOT / "popup-venv/bin/python"))
            subprocess.run([renderer_python, str(ROOT / "popup/check_emoji.py"),
                            "--image", str(screenshot)], env=env, check=True)
            print("PASS: socket-only candidate display, Wayland caret-top/XWayland below-caret placement, short compositions, fragmented JSON, reconnect replay, selection command")
        finally:
            if conn:
                conn.close()
            server.close()
            if proc.poll() is None:
                proc.terminate()
            proc.wait(timeout=5)
            thread.join(timeout=2)
            (output / "overlay-test.log").write_text("".join(log))


if __name__ == "__main__":
    main()
