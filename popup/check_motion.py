#!/usr/bin/env python3
"""Check the shared text reel without touching the user's desktop or input."""
import argparse
import json

from render import Renderer, QGuiApplication
from PySide6.QtQml import QQmlEngine, QQmlExpression
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest


def items(root):
    yield root
    for child in root.childItems():
        yield from items(child)


app = QGuiApplication([])
renderer = Renderer(argparse.Namespace(socket_fd=None, memory_fd=None))
state = dict(visible=True, session=1, epoch=1, scale=1, text="ni", caret=-1,
             cursor=0, candidates=[dict(label="1", text="AAAA")])
renderer.active = True
renderer.bridge.handle(state)
QTest.qWait(700)
cell = next(item for item in items(renderer.root)
            if item.metaObject().className().startswith("CandidateSlot")
            and item.property("order") == 0)


def snapshot():
    expression = QQmlExpression(QQmlEngine.contextForObject(cell), cell, """
        JSON.stringify({height: height, active: activeFace,
            faces: Array.from({length: textLayers.count}, (_, i) => {
                const face = textLayers.itemAt(i);
                return {row: face.row, dy: face.dy, visible: face.onTrack,
                        text: face.entry ? face.entry.text : null};
            })})
    """)
    value, _ = expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
    return json.loads(value)


def replace(text):
    state.update(candidates=[dict(label="1", text=text)])
    renderer.bridge.handle(state)
    renderer.invalidate()


replace("BBBB")
QTest.qWait(65)
middle = snapshot()
visible = [face for face in middle["faces"] if face["visible"]]
assert len(visible) == 2, middle
old = next(face for face in visible if face["text"] == "AAAA")
new = next(face for face in visible if face["text"] == "BBBB")
assert -middle["height"] < old["dy"] < 0, middle
assert 0 < new["dy"] < middle["height"], middle
assert abs(new["dy"] - old["dy"] - middle["height"]) < .001, middle
inks = [item for item in items(renderer.root)
        if item.metaObject().className().startswith("CandidateInk")]
assert len(inks) >= 2, "normal or highlighted text copy is missing"
for ink in inks:
    assert ink.clip(), "text reel is not clipped"
    for item in ink.childItems():
        if item.metaObject().className().startswith("SlotText"):
            assert item.opacity() == 1, "candidate text is fading"

for text in ("CCCC", "DDDD", "EEEE", "FFFF", "GGGG", "HHHH"):
    before = snapshot()
    replace(text)
    after = snapshot()
    for previous, current in zip(before["faces"], after["faces"]):
        if previous["visible"]:
            assert previous["row"] == current["row"], "visible row was recycled"
            assert previous["dy"] == current["dy"], "visible text jumped"
    QTest.qWait(25)
QTest.qWait(750)
end = snapshot()
latest = end["faces"][end["active"]]
assert latest["text"] == "HHHH" and abs(latest["dy"]) < .03, end

state.update(session=2, text="new", candidates=[dict(label="1", text="IIII")])
renderer.bridge.handle(state)
QTest.qWait(30)
fresh = snapshot()
assert fresh["faces"][fresh["active"]]["text"] == "IIII", fresh
assert all(face["text"] == "IIII" for face in fresh["faces"] if face["visible"]), fresh
strip = next(item for item in items(renderer.root)
             if item.metaObject().className().startswith("Candidates"))
for vertical in (False, True):
    state.update(vertical=vertical, hasPrev=True, hasNext=True)
    renderer.bridge.handle(state)
    QTest.qWait(700)
    expression = QQmlExpression(QQmlEngine.contextForObject(strip), strip,
                               "JSON.stringify(layout)")
    value, _ = expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
    layout = json.loads(value)
    assert layout["w"] == max(rect["x"] + rect["w"] for rect in layout["rects"]), layout
    assert layout["h"] == max(rect["y"] + strip.property("cellH") for rect in layout["rects"]), layout
assert not any(item.metaObject().className().startswith("PageButton")
               for item in items(renderer.root)), "page buttons are still present"
commands = []
renderer.native.send = lambda message: commands.append(message.get("command"))
pos = cell.mapToScene(QPointF(cell.width() / 2, cell.height() / 2))
event = QWheelEvent(pos, pos, QPoint(), QPoint(0, -120),
                    Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                    Qt.ScrollPhase.NoScrollPhase, False)
QGuiApplication.sendEvent(renderer.window, event)
QTest.qWait(50)
assert "next" in commands, commands
print("PASS: opaque scroll, clipping, spacing, rapid continuity, session reset, no pager space/buttons, wheel paging")
