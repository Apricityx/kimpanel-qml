import QtQuick

// The preedit / aux line. Each glyph is its own delegate so typing animates
// only what changed: new glyphs rise in, deleted ones roll upward, the rest
// slide to make room. The caret glides between glyph boundaries.
Item {
    id: c

    property string text: ""
    property int caret: -1
    property int session: 0
    property color color: Theme.muted
    property color caretColor: Theme.primary
    property int pixelSize: Theme.compSize

    readonly property real contentWidth: measure(Array.from(text))
    implicitWidth: contentWidth
    implicitHeight: Math.ceil(fm.height)
    clip: true

    FontMetrics { id: fm; font.family: Theme.font; font.pixelSize: c.pixelSize }

    function measure(glyphs) {
        let w = 0;
        for (const g of glyphs) w += fm.advanceWidth(g);
        return w;
    }

    ListModel { id: glyphs }
    property var shown: []

    // Patch the model with the minimal edit (common prefix/suffix kept).
    function sync() {
        const next = Array.from(text);
        const cur = shown;
        let p = 0;
        while (p < cur.length && p < next.length && cur[p] === next[p]) p++;
        let s = 0;
        while (s < cur.length - p && s < next.length - p
               && cur[cur.length - 1 - s] === next[next.length - 1 - s]) s++;
        const del = cur.length - p - s;
        if (del > 0) glyphs.remove(p, del);
        for (let i = p; i < next.length - s; i++) glyphs.insert(i, { g: next[i] });
        shown = next;
    }

    onTextChanged: sync()
    // A new session never animates away the previous one's text.
    // Deferred so it sees this message's text, which lands after `session`.
    onSessionChanged: {
        glyphs.clear();
        shown = [];
        Qt.callLater(() => { sync(); caretX.snap(caretTarget); });
    }

    ListView {
        id: list
        anchors.fill: parent
        orientation: ListView.Horizontal
        interactive: false
        model: glyphs
        delegate: Item {
            id: glyph
            required property string g
            property int glyphSession: -1
            width: fm.advanceWidth(g)
            height: list.height
            Spring {
                id: glyphLift
                stiffness: 980
                dampingRatio: 1
                epsilon: 0.02
            }
            Component.onCompleted: {
                glyphSession = c.session;
                glyphLift.snap(c.height);
                glyphLift.to = 0;
            }
            ListView.onRemove: {
                // Retain pixels without delaying layout of the new text.
                if (glyphSession === c.session && glyphLift.value < c.height)
                    outgoingGlyph.createObject(c, { text: g, x: glyph.x,
                        width: glyph.width, startY: glyphLift.value,
                        glyphSession: c.session });
            }
            Text {
                text: glyph.g
                color: c.color
                font.family: Theme.font
                font.pixelSize: c.pixelSize
                width: parent.width
                height: parent.height
                verticalAlignment: Text.AlignVCenter
                y: glyphLift.value
            }
        }
        displaced: Transition {
            NumberAnimation { property: "x"; duration: 160; easing.type: Easing.OutCubic }
        }
    }

    Component {
        id: outgoingGlyph
        Text {
            id: ghost
            property real startY: 0
            required property int glyphSession
            visible: glyphSession === c.session
            font.family: Theme.font
            font.pixelSize: c.pixelSize
            color: c.color
            height: c.height
            verticalAlignment: Text.AlignVCenter
            y: lift.value
            Spring {
                id: lift
                stiffness: 1100
                dampingRatio: 1
                epsilon: 0.02
                onValueChanged: if (value <= -c.height + 0.02) ghost.destroy()
            }
            Component.onCompleted: { lift.snap(startY); lift.to = -c.height; }
        }
    }

    // ---- caret ----
    readonly property real caretTarget: caret < 0 ? 0 : measure(Array.from(text.substring(0, caret)))
    Spring { id: caretX; to: c.caretTarget; stiffness: 900; dampingRatio: 0.95 }

    Rectangle {
        id: caretBar
        visible: c.caret >= 0
        x: caretX.value - width / 2
        width: 2
        height: Math.round(fm.height * 0.9)
        anchors.verticalCenter: parent.verticalCenter
        radius: 1
        color: c.caretColor

        // Solid while typing; soft blink once idle.
        SequentialAnimation on opacity {
            id: blink
            loops: Animation.Infinite
            PauseAnimation { duration: 500 }
            NumberAnimation { to: 0.15; duration: 380; easing.type: Easing.InOutSine }
            NumberAnimation { to: 1; duration: 380; easing.type: Easing.InOutSine }
        }
    }
    onCaretTargetChanged: { caretBar.opacity = 1; blink.restart(); }
}
