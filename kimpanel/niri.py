"""Minimal niri IPC client and the spot resolver built on top of it."""

import json
import os
import socket
import sys
import time

from . import geometry
from .x11 import X11Client, is_satellite_window


class NiriClient:
    """One short-lived connection per request (round trip is ~0.1 ms)."""

    def __init__(self, path=None, timeout=0.05):
        self.path = path or os.environ.get("NIRI_SOCKET", "")
        self.timeout = timeout
        self._outputs = None
        self._outputs_at = 0.0

    @property
    def available(self):
        return bool(self.path) and os.path.exists(self.path)

    def request(self, req):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(self.timeout)
            s.connect(self.path)
            s.sendall((json.dumps(req) + "\n").encode())
            with s.makefile("rb") as f:
                reply = json.loads(f.readline())
        if "Ok" not in reply:
            raise RuntimeError("niri: %r" % (reply,))
        ok = reply["Ok"]
        return next(iter(ok.values())) if isinstance(ok, dict) else ok

    def outputs(self, max_age=5.0):
        now = time.monotonic()
        if self._outputs is None or now - self._outputs_at > max_age:
            self._outputs = [_logical(name, o) for name, o in self.request("Outputs").items()
                             if o.get("logical")]
            self._outputs_at = now
        return self._outputs

    def focus(self):
        """(focused output dict or None, focused window or None, siblings)."""
        fo = self.request("FocusedOutput")
        out = _logical(fo["name"], fo) if fo and fo.get("logical") else None
        win = self.request("FocusedWindow")
        siblings = []
        if win and not win.get("is_floating"):
            siblings = [w for w in self.request("Windows")
                        if w.get("workspace_id") == win.get("workspace_id")
                        and not w.get("is_floating")]
        return out, win, siblings


def _logical(name, o):
    lg = o["logical"]
    return {"name": name, "x": lg["x"], "y": lg["y"],
            "width": lg["width"], "height": lg["height"], "scale": lg.get("scale", 1.0)}


class SpotResolver:
    """Callable used by PanelModel: PanelState -> spot dict or None."""

    def __init__(self, client=None, gap=None, bar_size=None, bar_edge=None, x11=None):
        env = os.environ.get
        self.client = client or NiriClient()
        self.gap = float(gap if gap is not None else env("KIMPANEL_NIRI_GAPS", "4"))
        self.bar_size = float(bar_size if bar_size is not None else env("KIMPANEL_BAR_SIZE", "43"))
        self.bar_edge = bar_edge or env("KIMPANEL_BAR_EDGE", "top")
        self._auto_bar = bar_size is None and env("KIMPANEL_BAR_SIZE") is None
        self._x11 = x11
        self._warned = False
        self._last = None  # (spot, monotonic, window_id)

    def __call__(self, state):
        outputs, focused, origin, win, siblings = [], None, None, None, []
        if self.client.available:
            try:
                outputs = self.client.outputs()
                focused, win, siblings = self.client.focus()
                if state.spot_mode == "relative" and win and focused:
                    origin = geometry.estimate_window_origin(
                        win, siblings, focused, self.gap, self.bar_size, self.bar_edge)
            except (OSError, ValueError, RuntimeError) as e:
                if not self._warned:
                    self._warned = True
                    print("kimpanel: niri IPC unavailable (%s); spot not translated" % e,
                          file=sys.stderr, flush=True)
        spot = None
        satellite = is_satellite_window(win)
        if state.spot_mode == "absolute" and focused and satellite:
            try:
                if self._x11 is None:
                    self._x11 = X11Client()
                x11_origin = self._x11.window_origin(win.get("app_id"))
                bar_size = self.bar_size
                if self._auto_bar and self.bar_edge in ("top", "bottom"):
                    inferred = geometry.tiled_bar_size(siblings, focused, self.gap)
                    if inferred is not None:
                        bar_size = inferred
                origin = geometry.estimate_window_origin(
                    win, siblings, focused, self.gap, bar_size, self.bar_edge)
                spot = geometry.satellite_spot(state.spot, x11_origin, origin, focused)
            except OSError as e:
                if not self._warned:
                    self._warned = True
                    print(f"kimpanel: X11 geometry unavailable ({e})", file=sys.stderr, flush=True)
        if spot is None:
            spot = geometry.spot_from_rect(state.spot, state.spot_mode, state.spot_scale,
                                           origin, outputs, focused)
        win_id = (win or {}).get("id")
        caret_top = state.spot_mode == "relative" and bool(win) and not satellite
        if spot and "x" in spot:
            spot = _placement(spot, caret_top)
            self._last = (spot, time.monotonic(), win_id)
            return spot
        # wayland_v2 clients (Alacritty, Edge) often send (0,0,0,0). Keep the
        # last rect from this window, else guess a point inside it.
        if self._last:
            last, t, last_id = self._last
            if last_id == win_id and time.monotonic() - t < 8:
                return _placement(last, caret_top)
        guess = geometry.window_guess(win, siblings, focused, self.gap, self.bar_size, self.bar_edge)
        if guess:
            return guess
        return spot


def _placement(spot, caret_top):
    """Align Wayland relative carets at their top; preserve XWayland placement."""
    spot = dict(spot)
    spot.pop("caretTop", None)
    if caret_top:
        spot["caretTop"] = True
    return spot
