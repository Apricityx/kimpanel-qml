pragma Singleton
import QtQuick
QtObject {
    id: b
    property bool active: false
    property int session: 0
    property string text: ""
    property int caret: -1
    property var candidates: []
    property int cursor: -1
    property bool hasPrev: false
    property bool hasNext: false
    property bool vertical: false
    property var spot: null
    signal pageTurned(int dir)
    function select(i) { Native.command("select " + i); }
    function prev() { if (hasPrev) Native.command("prev"); }
    function next() { if (hasNext) Native.command("next"); }
    function handle(m) {
        session = m.session;
        if (!m.visible) { active = false; return; }
        spot = m.spot || null;
        vertical = !!m.vertical;
        hasPrev = !!m.hasPrev;
        hasNext = !!m.hasNext;
        text = m.text || "";
        caret = m.caret === undefined ? -1 : m.caret;
        candidates = m.candidates || [];
        cursor = m.cursor;
        if (m.pageDir) pageTurned(m.pageDir);
        active = true;
    }
}
