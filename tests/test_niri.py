import unittest
from unittest.mock import Mock, patch

from kimpanel.niri import SpotResolver
from kimpanel.state import PanelState
from test_geometry import OUT, OUT2, win


class TestSatelliteResolver(unittest.TestCase):
    def setUp(self):
        self.window = dict(win(2, 1, 847, 1025), id=140, pid=42, app_id="wechat")
        self.client = Mock(available=True)
        self.client.outputs.return_value = [OUT]
        self.client.focus.return_value = (OUT, self.window, [win(1, 1, 847, 1025), self.window])
        self.x11 = Mock()
        self.x11.window_origin.return_value = (0, 0)
        self.state = PanelState()
        self.state.spot = (765, 1389, 3, 27)

    def test_satellite_absolute_rect_uses_both_origins(self):
        resolver = SpotResolver(self.client, gap=4, bar_size=33, x11=self.x11)
        with patch("kimpanel.niri.is_satellite_window", return_value=True):
            spot = resolver(self.state)
        self.assertEqual((spot["x"], spot["y"]), (1365, 963))
        self.assertNotIn("caretTop", spot)
        self.x11.window_origin.assert_called_once_with("wechat")

    def test_non_satellite_absolute_rect_keeps_existing_conversion(self):
        resolver = SpotResolver(self.client, gap=4, bar_size=33, x11=self.x11)
        with patch("kimpanel.niri.is_satellite_window", return_value=False):
            spot = resolver(self.state)
        self.assertEqual((spot["x"], spot["y"]), (510, 926))
        self.x11.window_origin.assert_not_called()

    def test_toolkit_relative_rect_keeps_existing_conversion(self):
        self.state.spot_mode, self.state.spot_scale = "relative", 1.5
        resolver = SpotResolver(self.client, gap=4, bar_size=33, x11=self.x11)
        with patch("kimpanel.niri.is_satellite_window", return_value=True):
            spot = resolver(self.state)
        self.assertEqual((spot["x"], spot["y"]), (1365, 963))
        self.assertNotIn("caretTop", spot)
        self.x11.window_origin.assert_not_called()

    def test_mismatched_x_focus_falls_back_without_guessing_a_transform(self):
        self.x11.window_origin.return_value = None
        resolver = SpotResolver(self.client, gap=4, bar_size=33, x11=self.x11)
        with patch("kimpanel.niri.is_satellite_window", return_value=True):
            spot = resolver(self.state)
        self.assertEqual((spot["x"], spot["y"]), (510, 926))

    def test_explicit_bar_override_is_preserved(self):
        resolver = SpotResolver(self.client, gap=4, bar_size=43, x11=self.x11)
        with patch("kimpanel.niri.is_satellite_window", return_value=True):
            spot = resolver(self.state)
        self.assertEqual(spot["y"], 973)

    def test_default_bar_inferred_for_satellite_only(self):
        with patch.dict("os.environ", {}, clear=True):
            resolver = SpotResolver(self.client, gap=4, x11=self.x11)
        with patch("kimpanel.niri.is_satellite_window", return_value=True):
            spot = resolver(self.state)
        self.assertEqual(spot["y"], 963)


class TestNativeOverlayResolver(unittest.TestCase):
    def setUp(self):
        self.window = dict(win(0, 0, 600, 400, floating_pos=[120, 80]), id=42)
        self.client = Mock(available=True)
        self.client.outputs.return_value = [OUT, OUT2]
        self.client.focus.return_value = (OUT, self.window, [])
        self.x11 = Mock()
        self.resolver = SpotResolver(self.client, gap=4, bar_size=33, x11=self.x11)
        self.state = PanelState()
        self.state.spot_mode, self.state.spot_scale = "relative", 1.0
        self.state.spot = (300, 150, 2, 22)

    def test_native_logical_rect_is_not_divided_by_output_scale(self):
        self.assertEqual(self.resolver(self.state),
                          dict(output=OUT["name"], x=420, y=230, w=2, h=22, caretTop=True))
        self.x11.window_origin.assert_not_called()

    def test_native_caret_motion_updates_existing_window(self):
        self.resolver(self.state)
        self.state.spot = (360, 190, 2, 22)
        self.assertEqual(self.resolver(self.state),
                          dict(output=OUT["name"], x=480, y=270, w=2, h=22, caretTop=True))

    def test_output_switch_keeps_relative_spot_output_local(self):
        self.client.focus.return_value = (OUT2, self.window, [])
        self.assertEqual(self.resolver(self.state),
                          dict(output=OUT2["name"], x=420, y=230, w=2, h=22, caretTop=True))

    def test_missing_rect_reuses_only_same_window(self):
        previous = self.resolver(self.state)
        self.state.spot = (0, 0, 0, 0)
        self.assertEqual(self.resolver(self.state), previous)
        other = dict(win(0, 0, 500, 300, floating_pos=[40, 20]), id=43)
        self.client.focus.return_value = (OUT, other, [])
        self.assertNotEqual(self.resolver(self.state), previous)

    def test_repeated_caret_does_not_freeze_window_origin(self):
        self.resolver(self.state)
        self.window["layout"]["tile_pos_in_workspace_view"] = [180, 120]
        self.assertEqual(self.resolver(self.state),
                          dict(output=OUT["name"], x=480, y=270, w=2, h=22, caretTop=True))

    def test_toolkit_wayland_scaled_relative_rect_anchors_at_top(self):
        self.state.spot_scale = 1.5
        spot = self.resolver(self.state)
        self.assertEqual(spot, dict(output=OUT["name"], x=320, y=180,
                                    w=1.3, h=14.7, caretTop=True))

    def test_cached_rect_does_not_leak_wayland_anchor_to_xwayland(self):
        self.assertTrue(self.resolver(self.state)["caretTop"])
        self.state.spot = (0, 0, 0, 0)
        with patch("kimpanel.niri.is_satellite_window", return_value=True):
            self.assertNotIn("caretTop", self.resolver(self.state))

    def test_unknown_window_does_not_enable_wayland_anchor(self):
        self.client.focus.return_value = (OUT, None, [])
        self.assertNotIn("caretTop", self.resolver(self.state))
