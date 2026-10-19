import ctypes
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from kimpanel.x11 import X11Client, _Translation, is_satellite_window


class TestX11Geometry(unittest.TestCase):
    def client(self, replies):
        client = X11Client.__new__(X11Client)
        client.lib = Mock()
        client.lib.xcb_connect.return_value = 1
        client.lib.xcb_connection_has_error.return_value = 0
        client._query = Mock(side_effect=replies)
        return client

    def test_nested_focus_resolves_matching_toplevel(self):
        client = self.client([30, (10, 20), (10, 10), ["wechat", "wechat"], (75, 54)])
        self.assertEqual(client.window_origin("WeChat"), (75, 54))
        client.lib.xcb_disconnect.assert_called_once_with(1)
        self.assertEqual(client._query.call_args_list[-1].args[2], (20, 10, 0, 0))

    def test_other_application_and_root_focus_rejected(self):
        for replies in ([30, (10, 10), ["other"]], [1], [30, None]):
            client = self.client(replies)
            self.assertIsNone(client.window_origin("wechat"))
            client.lib.xcb_disconnect.assert_called_once_with(1)

    def test_connection_failure_is_local(self):
        client = self.client([])
        client.lib.xcb_connection_has_error.return_value = 1
        self.assertIsNone(client.window_origin("wechat"))
        client.lib.xcb_disconnect.assert_called_once_with(1)

    def test_translation_reply_layout_and_decode(self):
        client = self.client([30, (10, 10), ["wechat"]])
        replies = iter([30, (10, 10), ["wechat"],
                        lambda *args: args[-1](ctypes.pointer(_Translation(
                            response=1, same_screen=1, child=99, x=-75, y=54)))])
        # Feed the actual C reply through the decoder used by window_origin.
        def query(*args):
            result = next(replies)
            return result(*args) if callable(result) else result
        client._query = query
        self.assertEqual(_Translation.x.offset, 12)
        self.assertEqual(client.window_origin("wechat"), (-75, 54))

    def test_backend_detection_uses_compositor_pid_not_app_name(self):
        with patch.object(Path, "readlink", return_value=Path("/usr/bin/xwayland-satellite")):
            self.assertTrue(is_satellite_window(dict(pid=42, app_id="wechat")))
        with patch.object(Path, "readlink", return_value=Path("/usr/bin/wechat")):
            self.assertFalse(is_satellite_window(dict(pid=42, app_id="wechat")))
        self.assertFalse(is_satellite_window({}))
