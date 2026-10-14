import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from bridge import apply_im_signal
    from kimpanel.dbus_panel import ImPanel
except ImportError:
    ImPanel = None

from kimpanel.state import PanelModel


@unittest.skipIf(ImPanel is None, "requires dbus-python and PyGObject")
class TestPanelSignals(unittest.TestCase):
    def setUp(self):
        self.lines = []
        self.queued = []
        self.model = PanelModel(self.lines.append, self.queued.append, lambda _: None)
        # Exercise the decorated methods without exporting a real bus object.
        self.panel = ImPanel.__new__(ImPanel)
        self.panel.m = self.model
        self.panel.st = self.model.state

    def flush(self):
        pending = list(self.queued)
        self.queued.clear()
        for fn in pending:
            fn()
        return json.loads(self.lines[-1])

    def table(self, text):
        self.panel.SetLookupTable(["1"], [text], [""], False, False, 0, 2)

    def test_native_routing_hides_retained_toolkit_table(self):
        self.table("candidate")
        self.panel.UpdatePreeditText("ni", "")
        apply_im_signal(self.panel, "ShowPreedit", [True])
        self.assertTrue(self.flush()["visible"])
        for member in ("ShowAux", "ShowPreedit", "ShowLookupTable"):
            apply_im_signal(self.panel, member, [False])
        self.assertFalse(self.flush()["visible"])
        self.assertEqual(self.model.state.texts, ["candidate"])

    def test_lookup_signal_can_hide_without_preedit(self):
        self.table("first")
        self.assertTrue(self.flush()["visible"])
        apply_im_signal(self.panel, "ShowLookupTable", [False])
        self.assertFalse(self.flush()["visible"])
        self.table("second")
        apply_im_signal(self.panel, "ShowLookupTable", [True])
        state = self.flush()
        self.assertTrue(state["visible"])
        self.assertEqual(state["candidates"][0]["text"], "second")
        self.assertEqual(state["session"], 2)
