import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kimpanel.state import PageTracker, PanelModel, utf16_index  # noqa: E402


class Harness:
    def __init__(self, spot=None):
        self.lines, self.queued, self.resolves = [], [], 0
        self.spot = spot

        def resolve(_st):
            self.resolves += 1
            return self.spot

        self.m = PanelModel(self.lines.append, self.queued.append, resolve)

    def run(self):
        # PanelModel holds a bound self.queued.append, so drain in place.
        q = list(self.queued)
        del self.queued[:]
        for fn in q:
            fn()
        return [json.loads(x) for x in self.lines]

    def type(self, preedit, words, **kw):
        st = self.m.state
        st.preedit, st.show_preedit, st.caret = preedit, True, len(preedit)
        st.labels = [str(i + 1) for i in range(len(words))]
        st.texts, st.show_lookup = list(words), True
        st.cursor = kw.get("cursor", 0)
        st.has_prev = kw.get("prev", False)
        # one fcitx burst = many calls
        for _ in range(7):
            self.m.touch()


class TestUtf16(unittest.TestCase):
    def test_bmp_and_astral(self):
        self.assertEqual(utf16_index("ni hao", 2), 2)
        self.assertEqual(utf16_index("a😀b", 2), 3)  # emoji is two UTF-16 units
        self.assertEqual(utf16_index("abc", 99), 3)


class TestPageTracker(unittest.TestCase):
    def test_forward_back_and_typing(self):
        p = PageTracker()
        self.assertEqual(p.observe(["a", "b"], False), 0)
        self.assertEqual(p.observe(["a", "b"], False), 0)   # cursor move only
        self.assertEqual(p.observe(["c", "d"], True), 1)    # page down
        self.assertEqual(p.observe(["e", "f"], True), 1)
        self.assertEqual(p.observe(["c", "d"], True), -1)   # page up
        self.assertEqual(p.observe(["a", "b"], False), -1)
        self.assertEqual(p.observe(["x", "y"], False), 0)   # typed a letter


class TestPanelModel(unittest.TestCase):
    def test_burst_is_one_message(self):
        h = Harness()
        h.type("ni", ["你", "尼"])
        msgs = h.run()
        self.assertEqual(len(msgs), 1)
        m = msgs[0]
        self.assertTrue(m["visible"])
        self.assertEqual(m["text"], "ni")
        self.assertEqual(m["caret"], 2)
        self.assertEqual([c["text"] for c in m["candidates"]], ["你", "尼"])
        self.assertEqual(m["session"], 1)

    def test_duplicate_state_not_resent(self):
        h = Harness()
        h.type("ni", ["你"])
        h.run()
        h.m.touch()
        self.assertEqual(len(h.run()), 1)

    def test_sessions_and_hide(self):
        h = Harness()
        h.type("n", ["你"])
        h.run()
        st = h.m.state
        st.show_preedit = st.show_lookup = False
        h.m.touch()
        h.run()
        h.type("z", ["中"])
        msgs = h.run()
        self.assertEqual(msgs[1], {"visible": False, "session": 1})
        self.assertEqual(msgs[2]["session"], 2)

    def test_spot_resolved_lazily(self):
        h = Harness(spot={"output": "eDP-1", "x": 1, "y": 2, "w": 0, "h": 20})
        h.m.touch(spot=True)
        h.run()
        self.assertEqual(h.resolves, 0)  # hidden: no niri round trips
        h.type("n", ["你"])
        m = h.run()[-1]
        self.assertEqual(h.resolves, 1)
        self.assertEqual(m["spot"]["output"], "eDP-1")
        h.type("ni", ["你"])
        h.run()
        self.assertEqual(h.resolves, 1)  # rect unchanged

    def test_page_dir_and_cursor_bounds(self):
        h = Harness()
        h.type("ni", ["a", "b"])
        h.run()
        h.type("ni", ["c", "d"], prev=True, cursor=5)
        m = h.run()[-1]
        self.assertEqual(m["pageDir"], 1)
        self.assertEqual(m["cursor"], -1)

    def test_lookup_table_implies_visible(self):
        # fcitx 5.1.x: SetLookupTable arrives, ShowLookupTable often does not.
        h = Harness()
        st = h.m.state
        st.texts = ["你", "尼"]
        st.labels = ["1.", "2."]
        st.show_lookup = bool(st.texts)
        st.show_preedit = False
        h.m.touch()
        m = h.run()[-1]
        self.assertTrue(m["visible"])
        self.assertEqual([c["text"] for c in m["candidates"]], ["你", "尼"])

    def test_aux_only(self):
        h = Harness()
        st = h.m.state
        st.aux, st.show_aux = "中", True
        h.m.touch()
        m = h.run()[-1]
        self.assertEqual((m["text"], m["caret"], m["candidates"]), ("中", -1, []))


if __name__ == "__main__":
    unittest.main()
