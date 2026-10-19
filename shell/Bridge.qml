pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

// Connection to bridge.py. Receives one JSON state line per IME update and
// sends plain-text commands back. Reconnects on its own if the bridge restarts.
Singleton {
    id: b

    readonly property string socketPath: Quickshell.env("KIMPANEL_QML_SOCK")
        || ((Quickshell.env("XDG_RUNTIME_DIR") || "/tmp") + "/kimpanel-qml/panel.sock")

    readonly property bool connected: sock.connected
    // `active` drives show/hide. While hidden, the fields below keep the last
    // shown content, so the panel can animate out without going blank.
    property bool active: false
    property int session: 0
    property string text: ""
    property int caret: -1
    property var candidates: []
    property int cursor: -1
    property bool hasPrev: false
    property bool hasNext: false
    property bool vertical: false
    property var spot: null       // {output, x, y, w, h} in output-local logical px

    signal pageTurned(int dir)    // +1 next, -1 prev
    signal grabRequested(string path)

    function select(i) { send("select " + i); }
    function prev() { if (hasPrev) send("prev"); }
    function next() { if (hasNext) send("next"); }
    function send(cmd) {
        if (sock.connected) { sock.write(cmd + "\n"); sock.flush(); }
    }

    function handle(line) {
        if (!line || !line.length) return;
        let m;
        try { m = JSON.parse(line); } catch (e) { return; }
        if (m.grab) { grabRequested(m.grab); return; }

        if (m.session !== undefined) session = m.session;  // before content
        if (!m.visible) { active = false; return; }

        spot = m.spot || null;
        vertical = !!m.vertical;
        hasPrev = !!m.hasPrev;
        hasNext = !!m.hasNext;
        text = m.text || "";
        caret = m.caret === undefined ? -1 : m.caret;
        candidates = m.candidates || [];
        cursor = m.cursor === undefined ? -1 : m.cursor;
        if (m.pageDir) pageTurned(m.pageDir);
        active = true;
    }

    Socket {
        id: sock
        path: b.socketPath
        connected: true
        // The hub replays the latest state on connect. tail -F on the diagnostic
        // snapshot can skip entire compositions between atomic replacements.
        parser: SplitParser { onRead: line => b.handle(line) }
        onConnectionStateChanged: {
            if (connected) {
                retry.interval = 250;
            } else {
                retry.restart();
            }
        }
        onError: retry.restart()
    }

    // Back off 250 ms -> 4 s while the bridge is down.
    Timer {
        id: retry
        interval: 250
        onTriggered: {
            if (sock.connected) return;
            sock.connected = false;
            sock.connected = true;
            interval = Math.min(interval * 2, 4000);
            if (!sock.connected) restart();
        }
    }
}
