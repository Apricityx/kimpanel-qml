"""Panel state, per-keystroke coalescing and page-direction inference.

fcitx updates the panel with a burst of ~7 DBus calls per keystroke
(UpdateAux, UpdatePreeditText, UpdatePreeditCaret, ShowPreedit, ShowAux,
SetLookupTable, ShowLookupTable). Pushing each one to the UI renders
half-updated states and flickers. PanelModel collects the burst and emits a
single snapshot once the burst is over.
"""

import json

# fcitx CandidateLayoutHint: NotSet=0, Vertical=1, Horizontal=2
LAYOUT_VERTICAL = 1


def utf16_index(text, cp_index):
    """fcitx reports the caret in code points; QML strings index UTF-16."""
    cp_index = max(0, min(cp_index, len(text)))
    return len(text[:cp_index].encode("utf-16-le")) // 2


class PageTracker:
    """Infers page-turn direction, which fcitx never reports.

    Within one composition, every page we have seen is kept in order. A list
    we saw before means we paged back; a new list that has a previous page
    means we paged forward; anything else (typing, cursor moves) is 0.
    """

    def __init__(self):
        self.pages = []

    def reset(self):
        self.pages = []

    def observe(self, texts, has_prev):
        key = tuple(texts)
        if not key:
            return 0
        if self.pages and self.pages[-1] == key:
            return 0
        if key in self.pages:
            del self.pages[self.pages.index(key) + 1:]
            return -1
        if has_prev and self.pages:
            self.pages.append(key)
            return 1
        self.pages = [key]
        return 0


class PanelState:
    """Raw state exactly as fcitx last described it."""

    def __init__(self):
        self.preedit = ""
        self.caret = -1
        self.show_preedit = False
        self.aux = ""
        self.show_aux = False
        self.labels = []
        self.texts = []
        self.cursor = -1
        self.has_prev = False
        self.has_next = False
        self.layout = 0
        self.show_lookup = False
        self.spot = (0, 0, 0, 0)
        self.spot_mode = "absolute"  # or "relative"
        self.spot_scale = 1.0

    def composition(self):
        """(text, utf16 caret or -1) for the line above the candidates."""
        if self.show_preedit and self.preedit:
            caret = utf16_index(self.preedit, self.caret) if self.caret >= 0 else -1
            return self.preedit, caret
        if self.show_aux and self.aux:
            return self.aux, -1
        return "", -1

    def candidates(self):
        if not self.show_lookup:
            return []
        out = []
        for i, text in enumerate(self.texts):
            label = self.labels[i] if i < len(self.labels) else ""
            out.append({"label": label, "text": text})
        return out


class PanelModel:
    """Owns PanelState and turns bursts of mutations into single snapshots.

    emit(line)          sends one JSON line to the UI
    schedule(fn)        runs fn once after the current burst (GLib timeout)
    resolve_spot(state) -> dict with output-local logical spot, or None
    """

    def __init__(self, emit, schedule, resolve_spot):
        self.state = PanelState()
        self._emit = emit
        self._schedule = schedule
        self._resolve_spot = resolve_spot
        self._pending = False
        self._spot_dirty = True
        self._visible = False
        self._session = 0
        self._spot = None
        self._pages = PageTracker()
        self._last_line = None

    def touch(self, spot=False):
        """Mark state changed; flushes once the current burst is done."""
        if spot:
            self._spot_dirty = True
        if not self._pending:
            self._pending = True
            self._schedule(self.flush)

    def flush(self):
        self._pending = False
        msg = self.snapshot()
        line = json.dumps(msg, ensure_ascii=False, separators=(",", ":"))
        if line != self._last_line:
            self._last_line = line
            self._emit(line)
        return False  # one-shot when used as a GLib source

    def snapshot(self):
        st = self.state
        text, caret = st.composition()
        cands = st.candidates()
        visible = bool(text) or bool(cands)

        if visible and not self._visible:
            self._session += 1
            self._pages.reset()
            self._spot_dirty = True
        self._visible = visible

        if not visible:
            return {"visible": False, "session": self._session}

        # Resolve lazily: only while shown, and only when the rect changed.
        if self._spot_dirty:
            self._spot_dirty = False
            self._spot = self._resolve_spot(st)

        page_dir = self._pages.observe([c["text"] for c in cands], st.has_prev)
        msg = {
            "visible": True,
            "session": self._session,
            "text": text,
            "caret": caret,
            "candidates": cands,
            "cursor": st.cursor if 0 <= st.cursor < len(cands) else -1,
            "hasPrev": st.has_prev,
            "hasNext": st.has_next,
            "vertical": st.layout == LAYOUT_VERTICAL,
            "pageDir": page_dir,
        }
        if self._spot:
            msg["spot"] = self._spot
        return msg
