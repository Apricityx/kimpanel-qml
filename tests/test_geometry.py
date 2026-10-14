import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kimpanel.geometry import estimate_window_origin, spot_from_rect  # noqa: E402

OUT = {"name": "eDP-1", "x": 0, "y": 0, "width": 1706, "height": 1066, "scale": 1.5}
OUT2 = {"name": "HDMI-A-1", "x": 1706, "y": 0, "width": 1920, "height": 1080, "scale": 1.0}


def win(col, row, w, h, floating_pos=None):
    return {"is_floating": floating_pos is not None, "layout": {
        "pos_in_scrolling_layout": None if floating_pos else [col, row],
        "tile_size": [w, h], "window_size": [int(w), int(h)],
        "tile_pos_in_workspace_view": floating_pos,
        "window_offset_in_tile": [0.0, 0.0]}}


class TestSpot(unittest.TestCase):
    def test_no_cursor_rect(self):
        self.assertEqual(spot_from_rect((0, 0, 0, 0), "absolute", 1, None, [OUT], OUT),
                         {"output": "eDP-1"})
        self.assertIsNone(spot_from_rect((0, 0, 0, 0), "absolute", 1, None, [], None))

    def test_absolute_picks_output(self):
        s = spot_from_rect((1800, 100, 2, 20), "absolute", 1, None, [OUT, OUT2], OUT)
        self.assertEqual((s["output"], s["x"], s["y"]), ("HDMI-A-1", 94, 100))

    def test_relative_v2_scales_and_offsets(self):
        s = spot_from_rect((300, 150, 3, 30), "relative", 1.5, (10, 47), [OUT], OUT)
        self.assertEqual((s["x"], s["y"], s["w"], s["h"]), (210, 147, 2, 20))

    def test_absolute_already_local(self):
        # DP-2 lives at global x=1706; a local caret must not be subtracted.
        dp = {"name": "DP-2", "x": 1706, "y": 0, "width": 2048, "height": 1152, "scale": 1.25}
        s = spot_from_rect((400, 400, 2, 22), "absolute", 1, None, [dp], dp)
        self.assertEqual(s["output"], "DP-2")
        self.assertAlmostEqual(s["x"], 400 / 1.25, places=1)
        self.assertAlmostEqual(s["y"], 400 / 1.25, places=1)

    def test_absolute_physical_pixels(self):
        dp = {"name": "DP-2", "x": 1706, "y": 0, "width": 2048, "height": 1152, "scale": 1.25}
        s = spot_from_rect((408, 1173, 0, 27), "absolute", 1, None, [dp], dp)
        self.assertEqual(s["output"], "DP-2")
        self.assertAlmostEqual(s["x"], 408 / 1.25, places=1)
        self.assertAlmostEqual(s["y"], 1173 / 1.25, places=1)

    def test_absolute_local_on_right_side_ignores_phantom_origin(self):
        dp = {"name": "DP-2", "x": 1706, "y": 0, "width": 2048, "height": 1152, "scale": 1.25}
        s = spot_from_rect((1800, 100, 2, 20), "absolute", 1, None, [dp], dp)
        self.assertEqual(s["output"], "DP-2")
        self.assertAlmostEqual(s["x"], 1800 / 1.25, places=1)
        self.assertAlmostEqual(s["y"], 100 / 1.25, places=1)


class TestWindowOrigin(unittest.TestCase):
    def origin(self, w, sib):
        return estimate_window_origin(w, sib, OUT, gap=4, bar_size=43, bar_edge="top")

    def test_floating_is_exact(self):
        w = win(0, 0, 600, 400, floating_pos=[120.0, 80.0])
        self.assertEqual(self.origin(w, []), (120.0, 80.0))

    def test_fullscreen(self):
        w = win(1, 1, 1707.3, 1067.3)
        self.assertEqual(self.origin(w, [w]), (0.0, 0.0))

    def test_two_half_columns_fit(self):
        a, b = win(1, 1, 847.3, 1015.3), win(2, 1, 847.3, 1015.3)
        self.assertEqual(self.origin(a, [a, b]), (4, 47))
        self.assertAlmostEqual(self.origin(b, [a, b])[0], 4 + 847.3 + 4)

    def test_stacked_tiles(self):
        a, b = win(1, 1, 1699, 505), win(1, 2, 1699, 506)
        self.assertEqual(self.origin(b, [a, b]), (4, 47 + 505 + 4))

    def test_overflowing_strip_last_column_at_right(self):
        cols = [win(1, 1, 1699, 1015), win(2, 1, 1699, 1015), win(3, 1, 847, 1015)]
        x, _ = self.origin(cols[2], cols)
        self.assertAlmostEqual(x, 1706 - 4 - 847)


if __name__ == "__main__":
    unittest.main()
