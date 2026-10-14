"""The org.kde.impanel / org.kde.impanel2 object fcitx5's kimpanel addon talks to.

Methods are called by fcitx; signals are how the panel talks back (fcitx
subscribes with a match rule on our object).
"""

import dbus
import dbus.service

IF1 = "org.kde.impanel"
IF2 = "org.kde.impanel2"
PATH = "/org/kde/impanel"


class ImPanel(dbus.service.Object):
    def __init__(self, bus, model, log):
        super().__init__(bus, PATH)
        self.m = model
        self.st = model.state
        self.log = log

    # ---- org.kde.impanel ----------------------------------------------
    @dbus.service.method(IF1, in_signature="ss")
    def UpdatePreeditText(self, text, attrs):
        self.st.preedit = str(text)
        self.m.touch()

    @dbus.service.method(IF1, in_signature="i")
    def UpdatePreeditCaret(self, pos):
        self.st.caret = int(pos)
        self.m.touch()

    @dbus.service.method(IF1, in_signature="b")
    def ShowPreedit(self, show):
        self.st.show_preedit = bool(show)
        self.m.touch()

    @dbus.service.method(IF1, in_signature="ss")
    def UpdateAux(self, text, attrs):
        self.st.aux = str(text)
        self.m.touch()

    @dbus.service.method(IF1, in_signature="b")
    def ShowAux(self, show):
        self.st.show_aux = bool(show)
        self.m.touch()

    @dbus.service.method(IF1, in_signature="b")
    def ShowLookupTable(self, show):
        self.st.show_lookup = bool(show)
        self.m.touch()

    @dbus.service.method(IF1, in_signature="i")
    def UpdateLookupTableCursor(self, cursor):
        self.st.cursor = int(cursor)
        self.m.touch()

    @dbus.service.method(IF1, in_signature="ii")
    def UpdateSpotLocation(self, x, y):
        self._spot((x, y, 0, 0), "absolute", 1.0)

    # Properties/menus are drawn by the tray, not by this panel; accept and
    # ignore so fcitx never sees UnknownMethod errors.
    @dbus.service.method(IF1, in_signature="i")
    def UpdateScreen(self, screen):
        pass

    @dbus.service.method(IF1, in_signature="b")
    def Enable(self, enable):
        pass

    @dbus.service.method(IF1, in_signature="as")
    def RegisterProperties(self, props):
        pass

    @dbus.service.method(IF1, in_signature="s")
    def UpdateProperty(self, prop):
        pass

    @dbus.service.method(IF1, in_signature="s")
    def RemoveProperty(self, prop):
        pass

    @dbus.service.method(IF1, in_signature="as")
    def ExecMenu(self, entries):
        pass

    @dbus.service.method(IF1, in_signature="s")
    def ExecDialog(self, prop):
        pass

    # ---- org.kde.impanel2 ---------------------------------------------
    @dbus.service.method(IF2, in_signature="asasasbbii")
    def SetLookupTable(self, labels, texts, attrs, has_prev, has_next, cursor, layout):
        st = self.st
        st.labels = [str(x) for x in labels]
        st.texts = [str(x) for x in texts]
        st.has_prev, st.has_next = bool(has_prev), bool(has_next)
        st.cursor, st.layout = int(cursor), int(layout)
        # fcitx 5.1.x often never calls ShowLookupTable as a method; the
        # table itself is the visibility signal.
        st.show_lookup = bool(st.texts)
        self.m.touch()

    @dbus.service.method(IF2, in_signature="iiii")
    def SetSpotRect(self, x, y, w, h):
        self._spot((x, y, w, h), "absolute", 1.0)

    @dbus.service.method(IF2, in_signature="iiii")
    def SetRelativeSpotRect(self, x, y, w, h):
        self._spot((x, y, w, h), "relative", 1.0)

    @dbus.service.method(IF2, in_signature="iiiid")
    def SetRelativeSpotRectV2(self, x, y, w, h, scale):
        self._spot((x, y, w, h), "relative", float(scale))

    def _spot(self, rect, mode, scale):
        rect = tuple(int(v) for v in rect)
        st = self.st
        self.log("spot", mode, rect, scale)
        if (rect, mode, scale) != (st.spot, st.spot_mode, st.spot_scale):
            st.spot, st.spot_mode, st.spot_scale = rect, mode, scale
            self.m.touch(spot=True)

    # ---- signals back to fcitx ----------------------------------------
    @dbus.service.signal(IF1, signature="")
    def PanelCreated(self):
        pass

    @dbus.service.signal(IF2, signature="")
    def PanelCreated2(self):
        pass

    @dbus.service.signal(IF1, signature="i")
    def SelectCandidate(self, index):
        pass

    @dbus.service.signal(IF1, signature="")
    def LookupTablePageUp(self):
        pass

    @dbus.service.signal(IF1, signature="")
    def LookupTablePageDown(self):
        pass
