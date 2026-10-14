"""Scripted fake IME sessions, for previewing the UI without fcitx.

Drives the real PanelModel (coalescing, page inference, spot mapping), so
what you see is what fcitx would produce. With grab_dir set it also asks
the UI to save PNGs of the panel at chosen moments and exits after one run.
"""

import json
import os

from gi.repository import GLib


def _compose(preedit, words, cursor=0, prev=False, nxt=True, layout=2):
    def act(st):
        st.preedit, st.show_preedit, st.caret = preedit, True, len(preedit)
        st.show_aux = False
        st.labels = ["%d." % (i + 1) for i in range(len(words))]
        st.texts = list(words)
        st.cursor, st.has_prev, st.has_next, st.layout = cursor, prev, nxt, layout
        st.show_lookup = True
    return act


def _cursor(i):
    def act(st):
        st.cursor = i
    return act


def _aux(text):
    def act(st):
        st.aux, st.show_aux = text, True
    return act


def _spot(x, y, h=22):
    def act(st):
        st.spot, st.spot_mode, st.spot_scale = (int(x), int(y), 2, int(h)), "absolute", 1.0
    return act


def _hide(st):
    st.show_preedit = st.show_aux = st.show_lookup = False
    st.preedit = st.aux = ""
    st.spot = (0, 0, 0, 0)


def script(ox, oy, w, h):
    """[(actions, hold_ms)]; a str action is a grab file name."""
    at = lambda fx, fy: _spot(ox + fx * w, oy + fy * h)
    P1 = ["你好", "你号", "拟好", "你耗", "尼好"]
    P2 = ["妮好", "倪浩", "你嚎", "泥壕", "霓昊"]
    V = ["中文", "中闻 zhōng wén", "钟文", "种文", "众闻"]
    return [
        ([at(.28, .38), _compose("n", ["你", "呢", "那", "年", "女"])], 170),
        ([at(.283, .38), _compose("ni", ["你", "尼", "泥", "逆", "拟"])], 170),
        ([at(.286, .38), _compose("ni h", ["你好", "你会", "你还", "你和", "逆火"])], 170),
        ([at(.289, .38), _compose("ni ha", ["你还", "你哈", "尼哈", "你好", "拟化"])], 170),
        ([at(.292, .38), _compose("ni hao", P1)], 650),
        (["01-typed.png"], 900),
        ([_cursor(1)], 260), ([_cursor(2)], 260), ([_cursor(3)], 650),
        (["02-cursor.png"], 900),
        ([_cursor(0)], 400),
        ([_compose("ni hao", P2, prev=True, nxt=False)], 650),
        (["03-page2.png"], 900),
        ([_compose("ni hao", P1)], 700),
        ([_hide], 900),
        ([at(.62, .86), _compose("zhong wen", V, layout=1)], 650),
        (["04-vertical.png"], 900),
        ([_cursor(1)], 300), ([_cursor(2)], 700),
        ([_hide], 900),
        ([_aux("中州韻 · 中")], 650),
        (["05-aux.png"], 900),
        ([_hide], 1200),
    ]


def run(model, hub, loop, output, grab_dir=None):
    ox, oy, w, h = output
    steps = script(ox, oy, w, h)
    idx = [0]

    def step():
        if idx[0] >= len(steps):
            if grab_dir:
                loop.quit()
                return False
            idx[0] = 0
        acts, hold = steps[idx[0]]
        idx[0] += 1
        for a in acts:
            if isinstance(a, str):
                if grab_dir:
                    hub.broadcast(json.dumps({"grab": os.path.join(grab_dir, a)}),
                                  remember=False)
            else:
                a(model.state)
        model.touch(spot=True)
        GLib.timeout_add(hold, step)
        return False

    GLib.timeout_add(800, step)  # give the UI time to connect
