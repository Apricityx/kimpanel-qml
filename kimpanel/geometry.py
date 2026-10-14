"""Map fcitx cursor rects to output-local logical pixels for the UI.

Absolute rects (SetSpotRect, XIM/X11 clients) are global compositor
coordinates. Relative rects (SetRelativeSpotRect[V2], GTK/Qt im modules on
Wayland) are relative to the focused window and need its on-screen origin.

niri's IPC only reports positions for floating windows, so tiled window
origins are estimated from the scrolling layout (columns, gaps, struts).
That is exact for fullscreen, maximized and fully visible column sets, and a
close guess when the strip is scrolled.
"""


def output_at(outputs, x, y, slack=0):
    for o in outputs:
        if (o["x"] - slack <= x < o["x"] + o["width"] + slack
                and o["y"] - slack <= y < o["y"] + o["height"] + slack):
            return o
    return None


def _inside(x, y, w, h, slack=0):
    return -slack <= x < w + slack and -slack <= y < h + slack


def spot_from_rect(rect, mode, scale, window_origin, outputs, focused):
    """rect=(x,y,w,h) from fcitx -> {"output","x","y","w","h"} or None.

    window_origin: (x, y) of the focused window inside `focused` output,
    or None when unknown. focused: output dict or None.
    """
    x, y, w, h = rect
    if x == 0 and y == 0 and w == 0 and h == 0:
        # Client never reported a cursor (e.g. input-method-v2): no position,
        # but still say which output to show the fallback card on.
        return {"output": focused["name"]} if focused else None

    if mode == "relative":
        s = scale if scale and scale > 0 else 1.0
        x, y, w, h = x / s, y / s, w / s, h / s
        ox, oy = window_origin or (0.0, 0.0)
        name = focused["name"] if focused else None
        return _spot(name, x + ox, y + oy, w, h)

    return _absolute(x, y, w, h, outputs, focused)


def _absolute(x, y, w, h, outputs, focused):
    """fcitx SetSpotRect is inconsistently global-logical, output-local, or physical."""
    if focused is None:
        out = output_at(outputs, x, y)
        if out is None:
            return _spot(None, x, y, w, h)
        return _spot(out["name"], x - out["x"], y - out["y"], w, h)

    fw, fh, sc = focused["width"], focused["height"], focused.get("scale") or 1.0
    # A disabled laptop panel can leave the remaining output at a non-zero
    # origin. On a single mapped screen, never subtract that phantom offset.
    multi = len(outputs) > 1
    if multi:
        out = output_at(outputs, x, y)
        if out is not None:
            return _spot(out["name"], x - out["x"], y - out["y"], w, h)
    # Scaled outputs: fcitx kimpanel's SetSpotRect is device pixels (the
    # "fits in logical bounds" test is a trap — 152x400 looks logical on a
    # 2048x1152 screen but is actually 1.25× physical, which lands the card
    # down-right of the caret).
    if sc > 1.01:
        lx, ly, lw, lh = x / sc, y / sc, w / sc, h / sc
        if _inside(lx, ly, fw, fh, slack=80):
            return _spot(focused["name"], lx, ly, lw, lh)
    if _inside(x, y, fw, fh, slack=80):
        return _spot(focused["name"], x, min(y, fh - 1), w, h)
    return _spot(focused["name"], x, y, w, h)


def _spot(name, x, y, w, h):
    return {"output": name, "x": round(x, 1), "y": round(y, 1),
            "w": round(max(w, 0), 1), "h": round(max(h, 0), 1)}


def estimate_window_origin(win, siblings, output, gap, bar_size, bar_edge):
    """Best-effort (x, y) of `win`'s visual geometry inside `output`.

    win/siblings are niri Window dicts; siblings are the tiled windows on
    the same workspace (including win). Returns None if nothing usable.
    """
    lay = win.get("layout") or {}
    off = lay.get("window_offset_in_tile") or (0.0, 0.0)
    pos = lay.get("tile_pos_in_workspace_view")
    if pos is not None:  # floating: niri gives it to us
        return pos[0] + off[0], pos[1] + off[1]

    tw, th = lay.get("tile_size") or (0.0, 0.0)
    ow, oh = output["width"], output["height"]
    if tw >= ow - 1 and th >= oh - 1:  # fullscreen
        return off[0], off[1]

    # Working area: output minus the bar's exclusive zone, inset by gaps.
    top = bar_size if bar_edge == "top" else 0.0
    left = bar_size if bar_edge == "left" else 0.0
    area_w = ow - (bar_size if bar_edge in ("left", "right") else 0.0)

    slot = lay.get("pos_in_scrolling_layout")
    if not slot:
        return left + gap + off[0], top + gap + off[1]
    col, row = slot

    columns = {}
    for s in siblings:
        sl = (s.get("layout") or {}).get("pos_in_scrolling_layout")
        if sl:
            columns.setdefault(sl[0], []).append(s)

    # y: tiles above us in our column.
    y = top + gap
    for s in sorted(columns.get(col, []), key=lambda s: s["layout"]["pos_in_scrolling_layout"][1]):
        if s["layout"]["pos_in_scrolling_layout"][1] >= row:
            break
        y += s["layout"]["tile_size"][1] + gap

    # x: column widths to our left; if the strip overflows the screen,
    # niri keeps the focused column in view, typically at an edge.
    widths = {c: max(t["layout"]["tile_size"][0] for t in ts) for c, ts in columns.items()}
    total = gap + sum(w + gap for w in widths.values())
    if total <= area_w + 1:
        x = left + gap + sum(widths[c] + gap for c in widths if c < col)
    elif col == max(widths):
        x = left + area_w - gap - tw
    else:
        x = left + gap
    return x + off[0], y + off[1]


def window_guess(win, siblings, focused, gap, bar_size, bar_edge):
    """A caret-like point inside the focused window when the client sent (0,0,0,0)."""
    if not focused:
        return None
    origin = (0.0, 0.0)
    ww, wh = focused["width"], focused["height"]
    if win:
        o = estimate_window_origin(win, siblings, focused, gap, bar_size, bar_edge)
        if o:
            origin = o
        lay = win.get("layout") or {}
        size = lay.get("window_size") or lay.get("tile_size")
        if size:
            ww, wh = size[0], size[1]
    ox, oy = origin
    # Slightly left of centre, mid-window: closer to where people type than
    # the screen bottom, and not covering the first line of a terminal.
    return _spot(focused["name"], ox + min(ww * 0.18, 120), oy + min(wh * 0.52, wh - 64), 2, 22)
