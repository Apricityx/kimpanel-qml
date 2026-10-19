#!/usr/bin/env python3
"""Exercise shared panel placement/reveal without touching desktop input."""
import argparse
import json

from render import Renderer, QGuiApplication
from PySide6.QtQml import QQmlEngine, QQmlExpression
from PySide6.QtTest import QTest


app = QGuiApplication([])
renderer = Renderer(argparse.Namespace(socket_fd=None, memory_fd=None))
# Use the same Panel as the overlay in a fixed, offscreen output. Do not crop
# it to native-popup dimensions as Renderer.render() normally does.
renderer.tick.stop()
panel = renderer.panel
panel.setProperty("compositorPopup", False)
state = dict(visible=True, session=1, text="ni", caret=-1, cursor=0,
             candidates=[dict(label="1", text="你好")],
             spot=dict(x=180, y=200, w=1, h=24))


def evaluate(code):
    expression = QQmlExpression(QQmlEngine.contextForObject(panel.property("frame")), panel, code)
    value, _ = expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
    return value


def snapshot():
    return json.loads(evaluate("""
        JSON.stringify({x: cx.value, y: cy.value, tx: cx.to, ty: cy.to,
            vx: cx.velocity, vy: cy.velocity, width: cw.value, height: ch.value,
            reveal: reveal.value, rv: reveal.velocity,
            opacity: frame.opacity, visible: frame.visible, above: above,
            screenX: frame.mapToItem(p, 0, 0).x,
            screenY: frame.mapToItem(p, 0, 0).y})
    """))


def update(**changes):
    state.update(changes)
    renderer.bridge.handle(state)
    # Flush the coalesced placement synchronously to inspect the exact retarget
    # boundary, before any timer advances the springs.
    evaluate("{ if (_queued) { place(_fresh, _jump); _fresh = _jump = false; } }")


def spot(x, y):
    return dict(x=x, y=y, w=1, h=24)


def continuous(before, after):
    for key in ("x", "y", "vx", "vy", "reveal", "rv", "opacity", "screenX", "screenY"):
        assert abs(before[key] - after[key]) < .001, (key, before, after)


update()
QTest.qWait(850)
start = snapshot()
assert start["x"] == 180 and start["y"] == 230, start

# Only explicitly marked Wayland rectangles use caret-top alignment. Legacy
# XWayland states must keep their existing 24px caret height + 6px gap.
update(spot=dict(x=180, y=200, w=1, h=24, caretTop=True))
continuous(start, snapshot())
assert snapshot()["ty"] == 200, snapshot()
QTest.qWait(850)
assert abs(snapshot()["y"] - 200) < .1, snapshot()
update(spot=dict(x=180, y=200, w=1, h=48, caretTop=True))
assert snapshot()["ty"] == 200, snapshot()
update(spot=dict(x=180, y=200, w=1, h=0, caretTop=True))
assert snapshot()["ty"] == 200, snapshot()
update(spot=spot(180, 200))
assert snapshot()["ty"] == 230, snapshot()
QTest.qWait(850)
start = snapshot()

# Small caret steps used to be ignored while inside the sticky card width.
update(spot=spot(198, 200))
now = snapshot()
continuous(start, now)
assert now["tx"] == 198, now
QTest.qWait(35)
middle = snapshot()
assert start["x"] < middle["x"] < 198, middle
update(spot=spot(260, 245))
continuous(middle, snapshot())
QTest.qWait(850)
end = snapshot()
assert abs(end["x"] - 260) < .1 and abs(end["y"] - 275) < .1, end

# Interrupt both early and late hiding (including below the former .3 snap
# threshold). Restore from the exact rendered pose, opacity and velocity.
for threshold in (.65, .20, .025):
    before = snapshot()
    update(visible=False)
    continuous(before, snapshot())
    for _ in range(150):
        QTest.qWait(8)
        faded = snapshot()
        if faded["reveal"] < threshold:
            break
    assert faded["visible"] and .003 < faded["reveal"] < threshold, faded
    update(visible=True, session=state["session"] + 1,
           spot=spot(state["spot"]["x"] + 65, state["spot"]["y"] + 30))
    resumed = snapshot()
    continuous(faded, resumed)
    assert resumed["tx"] != resumed["x"], resumed
    QTest.qWait(850)
    settled = snapshot()
    assert settled["opacity"] == 1 and abs(settled["x"] - settled["tx"]) < .1, settled

# Repeated commit/retype while a move itself is in flight retains momentum.
for i in range(8):
    before = snapshot()
    update(visible=False)
    continuous(before, snapshot())
    QTest.qWait(25)
    before = snapshot()
    update(visible=True, session=state["session"] + 1,
           spot=spot(480 + i * 12, 360 + i * 8))
    continuous(before, snapshot())
    QTest.qWait(25)
QTest.qWait(850)

# Wrapping/above-below flips during a fade must not move the scale origin.
update(visible=False)
QTest.qWait(100)
before = snapshot()
update(visible=True, session=state["session"] + 1, spot=spot(500, 770))
continuous(before, snapshot())
assert snapshot()["above"], snapshot()
QTest.qWait(850)

# Wayland edge avoidance still flips above and touches the caret's top.
update(spot=dict(x=500, y=770, w=1, h=24, caretTop=True))
now = snapshot()
assert now["above"] and abs(now["ty"] + panel.property("targetH") - 770) < .1, now
update(spot=dict(x=0, y=0, w=1, h=24, caretTop=True), session=state["session"] + 1)
assert snapshot()["tx"] == 8 and snapshot()["ty"] == 8, snapshot()
update(spot=spot(500, 770), session=state["session"] + 1)
QTest.qWait(850)

# Output geometry changes retarget a still-visible card rather than snapping.
before = snapshot()
renderer.root.setWidth(540)
evaluate("{ if (_queued) { place(_fresh, _jump); _fresh = _jump = false; } }")
continuous(before, snapshot())
QTest.qWait(850)
assert snapshot()["x"] + snapshot()["width"] <= 540 - 8 + .1, snapshot()

# Once fully invisible, a fresh composition can initialize at its new caret.
update(visible=False)
QTest.qWait(1000)
assert not snapshot()["visible"], snapshot()
update(visible=True, session=state["session"] + 1, spot=spot(90, 120))
assert snapshot()["x"] == 90 and snapshot()["y"] == 150, snapshot()

# Native popup coordinates are still local; global positioning belongs to niri.
panel.setProperty("compositorPopup", True)
evaluate("place(true, true)")
assert snapshot()["x"] == 16 and snapshot()["y"] == 16, snapshot()
print("PASS: Wayland caret-top/XWayland below-caret alignment, caret following, position/velocity continuity, early/late fade interruption, "
      "rapid commit/retype, placement flip, output resize, hidden initialization, native placement")
