"""Read the focused X window's virtual-root origin without moving/focusing it.

xwayland-satellite deliberately keeps X11 and compositor window positions
separate. XCB replies fail locally instead of Xlib's fatal default error handler.
Only WM_CLASS and geometry are read; window titles/input contents are not read.
"""
import ctypes as C
import ctypes.util
from pathlib import Path


def is_satellite_window(window):
    pid = (window or {}).get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        return (Path("/proc") / str(pid) / "exe").readlink().name == "xwayland-satellite"
    except OSError:
        return False


class _Cookie(C.Structure):
    _fields_ = [("sequence", C.c_uint)]


class _Focus(C.Structure):
    _fields_ = [("response", C.c_uint8), ("revert", C.c_uint8),
                ("sequence", C.c_uint16), ("length", C.c_uint32), ("focus", C.c_uint32)]


class _Tree(C.Structure):
    _fields_ = [("response", C.c_uint8), ("pad", C.c_uint8),
                ("sequence", C.c_uint16), ("length", C.c_uint32),
                ("root", C.c_uint32), ("parent", C.c_uint32)]


class _Translation(C.Structure):
    _fields_ = [("response", C.c_uint8), ("same_screen", C.c_uint8),
                ("sequence", C.c_uint16), ("length", C.c_uint32),
                ("child", C.c_uint32), ("x", C.c_int16), ("y", C.c_int16)]


class X11Client:
    def __init__(self):
        self.lib = C.CDLL(ctypes.util.find_library("xcb") or "libxcb.so.1")
        self.free = C.CDLL(None).free
        self.free.argtypes = [C.c_void_p]
        self.free.restype = None
        self._bind("xcb_connect", [C.c_char_p, C.c_void_p], C.c_void_p)
        self._bind("xcb_disconnect", [C.c_void_p], None)
        self._bind("xcb_connection_has_error", [C.c_void_p], C.c_int)
        self._bind("xcb_get_input_focus", [C.c_void_p], _Cookie)
        self._bind("xcb_query_tree", [C.c_void_p, C.c_uint32], _Cookie)
        self._bind("xcb_translate_coordinates",
                   [C.c_void_p, C.c_uint32, C.c_uint32, C.c_int16, C.c_int16], _Cookie)
        self._bind("xcb_get_property", [C.c_void_p, C.c_uint8, C.c_uint32,
                   C.c_uint32, C.c_uint32, C.c_uint32, C.c_uint32], _Cookie)
        for name in ("get_input_focus", "query_tree", "translate_coordinates", "get_property"):
            self._bind(f"xcb_{name}_reply", [C.c_void_p, _Cookie, C.c_void_p], C.c_void_p)
        self._bind("xcb_get_property_value", [C.c_void_p], C.c_void_p)
        self._bind("xcb_get_property_value_length", [C.c_void_p], C.c_int)

    def _bind(self, name, args, result):
        fn = getattr(self.lib, name)
        fn.argtypes, fn.restype = args, result

    def _query(self, connection, name, args, decode):
        cookie = getattr(self.lib, f"xcb_{name}")(connection, *args)
        reply = getattr(self.lib, f"xcb_{name}_reply")(connection, cookie, None)
        if not reply:
            return None
        try:
            return decode(reply)
        finally:
            self.free(reply)

    def window_origin(self, app_id):
        """Virtual-root device-pixel origin, only if X focus matches niri WM_CLASS."""
        if not app_id:
            return None
        connection = self.lib.xcb_connect(None, None)
        if not connection:
            return None
        try:
            if self.lib.xcb_connection_has_error(connection):
                return None
            window = self._query(connection, "get_input_focus", (),
                                 lambda p: C.cast(p, C.POINTER(_Focus)).contents.focus)
            if window is None or window <= 1:
                return None
            for _ in range(64):  # Focus can be a nested child, not a toplevel.
                tree = self._query(connection, "query_tree", (window,),
                                   lambda p: (C.cast(p, C.POINTER(_Tree)).contents.root,
                                              C.cast(p, C.POINTER(_Tree)).contents.parent))
                if not tree or not tree[1]:
                    return None
                root, parent = tree
                if parent == root:
                    break
                window = parent
            else:
                return None

            def classes(reply):
                data = C.string_at(self.lib.xcb_get_property_value(reply),
                                   self.lib.xcb_get_property_value_length(reply))
                return [s.decode("utf-8", "replace").casefold() for s in data.split(b"\0") if s]

            # Predefined atoms WM_CLASS=67 and STRING=31. Read at most 1024 bytes.
            names = self._query(connection, "get_property", (0, window, 67, 31, 0, 256), classes)
            if not names or app_id.casefold() not in names:
                return None  # Focus changed between the compositor and X queries.
            return self._query(connection, "translate_coordinates", (window, root, 0, 0),
                               lambda p: (C.cast(p, C.POINTER(_Translation)).contents.x,
                                          C.cast(p, C.POINTER(_Translation)).contents.y)
                               if C.cast(p, C.POINTER(_Translation)).contents.same_screen else None)
        finally:
            self.lib.xcb_disconnect(connection)
