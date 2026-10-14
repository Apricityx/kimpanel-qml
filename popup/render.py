#!/usr/bin/env python3
"""Offscreen Qt Quick renderer for classicui's input-method popup.

Only classicui owns the Wayland connection and popup role. JSON messages travel
over an inherited seqpacket socket; two acknowledged slots hold premultiplied
ARGB pixels in a memfd. No Qt or Python code runs in the input-method process.
"""
import argparse
import json
import math
import mmap
import os
from pathlib import Path
import socket
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QSG_RENDER_LOOP"] = "basic"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_SCALE_FACTOR"] = "2"

from PySide6.QtCore import QObject, Property, QTimer, QSocketNotifier, QUrl, Signal, Slot, Qt, QPointF
from PySide6.QtGui import QGuiApplication, QImage, QColor, QMouseEvent
from PySide6.QtQml import QQmlEngine, QQmlComponent
from PySide6.QtQuick import QQuickWindow

SLOT_SIZE = 32 * 1024 * 1024


class Native(QObject):
    changed = Signal()

    def __init__(self, send):
        super().__init__()
        self.send = send
        self._colors = {}
        self._radius = 14.0
        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self.reload_theme)
        self.theme_timer.start(1000)
        self.reload_theme()

    @Property("QVariantMap", notify=changed)
    def colors(self):
        return self._colors

    @Property(float, notify=changed)
    def radius(self):
        return self._radius

    @Slot(str)
    def command(self, text):
        self.send({"command": text})

    def reload_theme(self):
        try:
            cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
            config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
            data = json.loads((cache / "DankMaterialShell/dms-colors.json").read_text())
            colors = data["colors"][data.get("mode", "dark")]
            colors["surface"] = colors.get("surface_container_high", "#202018")
            radius = json.loads((config / "DankMaterialShell/settings.json").read_text()).get("cornerRadius", 12) + 2
            if colors != self._colors or radius != self._radius:
                self._colors = colors
                self._radius = max(6, radius)
                self.changed.emit()
        except (OSError, ValueError, KeyError, TypeError):
            pass


class Renderer:
    def __init__(self, args):
        self.args = args
        self.sock = socket.socket(fileno=args.socket_fd) if args.socket_fd is not None else None
        if self.sock:
            self.sock.setblocking(False)
        self.memory = mmap.mmap(args.memory_fd, 2 * SLOT_SIZE) if args.memory_fd is not None else None
        self.busy = set()
        self.scale = 1.0
        self.epoch = 0
        self.active = False
        self.dirty = True
        self.native = Native(self.send)
        # The offscreen platform creates no Wayland surface. A normal Quick
        # window supplies Qt's animation driver (RenderControl alone does not).
        self.window = QQuickWindow()
        self.window.setColor(QColor("transparent"))
        self.window.setGeometry(0, 0, 1420, 800)
        self.engine = QQmlEngine()
        self.engine.rootContext().setContextProperty("Native", self.native)
        self.component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(Path(__file__).with_name("Popup.qml"))))
        self.root = self.component.create()
        if self.root is None:
            raise RuntimeError("\n".join(e.toString() for e in self.component.errors()))
        self.root.setParentItem(self.window.contentItem())
        self.panel = self.root.property("panel")
        self.bridge = self.root.property("bridge")
        self.window.afterAnimating.connect(self.invalidate)
        self.image = None
        self.last_frame = None
        self.tick = QTimer()
        self.tick.setTimerType(Qt.TimerType.PreciseTimer)
        self.tick.timeout.connect(self.render)
        self.tick.start(8)
        self.window.show()
        if self.sock:
            self.notifier = QSocketNotifier(self.sock.fileno(), QSocketNotifier.Type.Read)
            self.notifier.activated.connect(self.receive)

    def invalidate(self):
        self.dirty = True

    def send(self, data):
        if "command" in data:
            data["epoch"] = self.epoch
        if self.sock:
            try:
                self.sock.send(json.dumps(data, separators=(",", ":")).encode())
                return True
            except BlockingIOError:
                return False
            except (BrokenPipeError, ConnectionResetError):
                QGuiApplication.quit()
                return False
        return True

    def receive(self):
        while True:
            try:
                raw = self.sock.recv(65536)
            except BlockingIOError:
                return
            if not raw:
                QGuiApplication.quit()
                return
            message = json.loads(raw)
            if "release" in message:
                self.busy.discard(message["release"])
            elif "visible" in message:
                self.active = message["visible"]
                self.epoch = message["epoch"]
                self.scale = message.get("scale", 1)
                self.bridge.handle(message)
                self.dirty = True
            elif "pointer" in message:
                if message.get("epoch") != self.epoch or not self.active:
                    continue
                kind = message["pointer"]
                pos = QPointF(message.get("x", -1), message.get("y", -1))
                event_type = {"move": QMouseEvent.Type.MouseMove, "press": QMouseEvent.Type.MouseButtonPress,
                              "release": QMouseEvent.Type.MouseButtonRelease}[kind]
                button = Qt.MouseButton.NoButton if kind == "move" else Qt.MouseButton.LeftButton
                buttons = Qt.MouseButton.LeftButton if kind == "press" else Qt.MouseButton.NoButton
                QGuiApplication.sendEvent(self.window, QMouseEvent(event_type, pos, pos, button, buttons, Qt.KeyboardModifier.NoModifier))
                self.dirty = True

    def render(self):
        if not self.dirty or len(self.busy) >= 2:
            return
        # The compositor positions the popup using the real surface size.
        # Within a composition, preserve headroom for shrinking animations.
        frame = self.panel.property("frame")
        visible = frame.property("visible")
        if not self.active and not visible:
            self.send({"hidden": True, "epoch": self.epoch})
            self.last_frame = None
            self.dirty = False
            return
        w = math.ceil(max(self.panel.property("targetW"), frame.width()) + 32)
        h = math.ceil(max(self.panel.property("targetH"), frame.height()) + 32)
        w, h = max(48, min(w, 1420)), max(48, min(h, 800))
        pw, ph = math.ceil(w * self.scale), math.ceil(h * self.scale)
        if pw * ph * 4 > SLOT_SIZE:
            raise RuntimeError("popup exceeds shared-memory slot")
        if self.window.width() != w or self.window.height() != h:
            self.window.setGeometry(0, 0, w, h)
        self.dirty = False
        image = self.window.grabWindow()
        if image.isNull():
            self.dirty = True
            return
        self.image = image.scaled(pw, ph, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        if self.memory:
            data = bytes(self.image.constBits())
            signature = (self.epoch, pw, ph, data)
            if signature == self.last_frame:
                return
            slot = next(i for i in range(2) if i not in self.busy)
            start = slot * SLOT_SIZE
            self.memory[start:start + self.image.sizeInBytes()] = data
            if self.send({"frame": slot, "width": pw, "height": ph, "stride": self.image.bytesPerLine(),
                          "logicalWidth": w, "logicalHeight": h, "epoch": self.epoch}):
                self.busy.add(slot)
                self.last_frame = signature


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--socket-fd", type=int)
    ap.add_argument("--memory-fd", type=int)
    ap.add_argument("--preview", type=Path)
    args = ap.parse_args()
    app = QGuiApplication(sys.argv)
    renderer = Renderer(args)
    if args.preview:
        renderer.active = True
        renderer.bridge.handle({"visible": True, "session": 1, "text": "ni hao", "caret": 6,
                                "cursor": 0, "candidates": [{"label": "1", "text": "你好"},
                                                           {"label": "2", "text": "拟好"}], "hasNext": True})
        def save():
            renderer.image.save(str(args.preview))
            app.quit()
        QTimer.singleShot(700, save)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
