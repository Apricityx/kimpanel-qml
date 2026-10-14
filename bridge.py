#!/usr/bin/env python3
"""kimpanel-qml bridge: fcitx5 kimpanel DBus frontend -> Quickshell UI.

    fcitx5 --DBus(org.kde.impanel)--> bridge --JSON lines/unix socket--> shell/
           <--DBus signals---------        <--"select N" / "prev" / "next"--

Single-threaded: DBus, the UI socket and niri IPC all run on one GLib loop.
"""

import argparse
import os
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gi.repository import GLib  # noqa: E402

from kimpanel.hub import Hub  # noqa: E402
from kimpanel.niri import SpotResolver  # noqa: E402
from kimpanel.state import PanelModel  # noqa: E402

FCITX_NAME = "org.kde.kimpanel.inputmethod"
# Long enough to cover one fcitx burst, short enough to stay under a frame.
COALESCE_MS = 2


def apply_im_signal(panel, member, args):
    """Map org.kde.kimpanel.inputmethod signals onto the panel object."""
    dispatch = {
        "UpdatePreeditText": panel.UpdatePreeditText,
        "UpdatePreeditCaret": panel.UpdatePreeditCaret,
        "ShowPreedit": panel.ShowPreedit,
        "UpdateAux": panel.UpdateAux,
        "ShowAux": panel.ShowAux,
        # classicui routing and focus loss hide the last table with a signal
        # alone. Respect it so toolkit candidates cannot linger over a popup.
        "ShowLookupTable": panel.ShowLookupTable,
        "UpdateLookupTableCursor": panel.UpdateLookupTableCursor,
        "UpdateSpotLocation": panel.UpdateSpotLocation,
        "Enable": panel.Enable,
        "RegisterProperties": panel.RegisterProperties,
        "UpdateProperty": panel.UpdateProperty,
        "RemoveProperty": panel.RemoveProperty,
        "ExecMenu": panel.ExecMenu,
        "ExecDialog": panel.ExecDialog,
        "UpdateScreen": panel.UpdateScreen,
    }
    fn = dispatch.get(member)
    if fn is None:
        return
    fn(*args)


def default_socket():
    run = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    return os.path.join(run, "kimpanel-qml", "panel.sock")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--socket", default=os.environ.get("KIMPANEL_QML_SOCK") or default_socket())
    ap.add_argument("--demo", action="store_true", help="play scripted sessions, no DBus")
    ap.add_argument("--grab", metavar="DIR", help="with --demo: save panel PNGs to DIR, run once")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    def log(*a):
        if args.verbose:
            print(time.strftime("%H:%M:%S"), *a, file=sys.stderr, flush=True)

    loop = GLib.MainLoop()
    panel = [None]

    def emit(line):
        log("->", line)
        # Always log a one-line summary so a missing window is diagnosable.
        vis = '"visible":true' in line.replace(" ", "").lower() or '"visible": true' in line
        print("kimpanel: %s" % ("show" if vis else "hide"), file=sys.stderr, flush=True)
        hub.broadcast(line)

    model = PanelModel(emit, lambda fn: GLib.timeout_add(COALESCE_MS, fn), SpotResolver())

    def on_command(cmd):
        log("<-", cmd)
        p = panel[0]
        if p is None:
            return
        verb, _, arg = cmd.partition(" ")
        if verb == "select":
            p.SelectCandidate(int(arg))
        elif verb == "prev":
            p.LookupTablePageUp()
        elif verb == "next":
            p.LookupTablePageDown()

    hub = Hub(args.socket, on_command)

    if args.demo:
        from kimpanel import demo
        try:
            out = SpotResolver().client.outputs()[0]
            geo = (out["x"], out["y"], out["width"], out["height"])
        except Exception:
            geo = (0, 0, 1920, 1080)
        if args.grab:
            os.makedirs(args.grab, exist_ok=True)
        demo.run(model, hub, loop, geo, args.grab)
    else:
        import dbus
        import dbus.mainloop.glib
        import dbus.service
        from kimpanel.dbus_panel import ImPanel

        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus = dbus.SessionBus()
        panel[0] = ImPanel(bus, model, log)  # export before taking the name
        try:
            name = dbus.service.BusName("org.kde.impanel", bus, do_not_queue=True)  # noqa: F841
        except dbus.exceptions.NameExistsException:
            print("kimpanel: org.kde.impanel is already owned; is another panel running?",
                  file=sys.stderr)
            hub.close()
            return 1

        def on_fcitx(owner):
            # Fires now if fcitx is up, and again every time it (re)starts.
            if owner:
                log("fcitx at", owner, "- announcing panel")
                panel[0].PanelCreated()
                panel[0].PanelCreated2()

        bus.watch_name_owner(FCITX_NAME, on_fcitx)

        # fcitx 5.1.x dual-writes: v2 methods on org.kde.impanel, plus the
        # original kimpanel signals on /kimpanel. Preedit/aux/show flags
        # often arrive only as signals, so we apply those too.
        def on_im_signal(*args, **kw):
            member = kw.get("member")
            p = panel[0]
            if p is None or not member:
                return
            log("signal", member, args)
            apply_im_signal(p, member, args)

        bus.add_signal_receiver(
            on_im_signal,
            dbus_interface=FCITX_NAME,
            path="/kimpanel",
            member_keyword="member",
        )

    for sig in (signal.SIGINT, signal.SIGTERM):
        GLib.unix_signal_add(GLib.PRIORITY_HIGH, sig, lambda *_: (loop.quit(), False)[1])

    print("kimpanel: bridge up on", args.socket, "(demo)" if args.demo else "",
          file=sys.stderr, flush=True)
    try:
        loop.run()
    finally:
        hub.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
