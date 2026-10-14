import QtQuick

// A clipped vertical text reel. All rows share one continuous spring so rapid
// updates preserve spacing and velocity instead of overlapping outgoing text.
Item {
    id: s

    property int order: 0
    property var entry: null
    property bool live: false
    property bool selected: false
    property int padX: 10
    property real radius: 10
    property real maxTextWidth: 260
    property real pressScale: tap.pressed ? 0.93 : 1
    readonly property alias textLayers: faces
    property int activeFace: -1
    property int activeRow: 0

    signal activated()

    x: px.value
    y: py.value
    width: pw.value
    opacity: live ? 1 : 0
    visible: opacity > 0.01

    Behavior on opacity { NumberAnimation { duration: 110; easing.type: Easing.OutQuad } }
    Behavior on pressScale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }

    Spring { id: px; stiffness: 700; dampingRatio: 0.9; epsilon: 0.1 }
    Spring { id: py; stiffness: 700; dampingRatio: 0.9; epsilon: 0.1 }
    Spring { id: pw; stiffness: 700; dampingRatio: 0.9; epsilon: 0.1 }
    Spring { id: reel; stiffness: 1500; dampingRatio: 1; epsilon: 0.02 }

    function update(e, r, snap) {
        if (!e || !r) { live = false; return; }
        const changed = !entry || entry.text !== e.text || entry.label !== e.label;
        const jump = snap || !live || opacity < 0.05;
        if (changed || jump) rollText(e, jump);
        entry = e;
        live = true;
        if (jump) {
            px.snap(r.x); py.snap(r.y); pw.snap(r.w);
        } else {
            px.to = r.x; py.to = r.y; pw.to = r.w;
        }
    }

    function rollText(e, jump) {
        if (jump) {
            for (let i = 0; i < faces.count; i++) faces.itemAt(i).row = -1;
            activeFace = 0;
            activeRow = 0;
            faces.itemAt(0).entry = e;
            faces.itemAt(0).row = 0;
            reel.snap(0);
            return;
        }
        // Coalesce pending rows only while they are entirely below the clip.
        if (activeFace >= 0 && faces.itemAt(activeFace).dy >= height) {
            faces.itemAt(activeFace).entry = e;
            return;
        }
        let pick = -1;
        for (let i = 0; i < faces.count; i++) {
            const f = faces.itemAt(i);
            if (i !== activeFace && (f.row < 0 || f.dy <= -height || f.dy >= height)) {
                pick = i;
                break;
            }
        }
        if (pick < 0) return;
        const incoming = faces.itemAt(pick);
        activeRow++;
        incoming.row = activeRow;
        incoming.entry = e;
        reel.to = activeRow * height;
        activeFace = pick;
    }

    Repeater {
        id: faces
        model: 6
        delegate: Item {
            property var entry: null
            property int row: -1
            readonly property real dy: row * s.height - reel.value
            readonly property bool onTrack: row >= 0 && dy > -s.height && dy < s.height
        }
    }

    Rectangle {
        anchors.fill: parent
        radius: s.radius
        color: Theme.fg
        opacity: hover.hovered && !s.selected ? (tap.pressed ? 0.14 : 0.08) : 0
        Behavior on opacity { NumberAnimation { duration: 140 } }
    }

    CandidateInk {
        id: content
        layers: s.textLayers
        maxTextWidth: s.maxTextWidth
        x: s.padX
        width: Math.max(0, s.width - 2 * s.padX)
        height: parent.height
        pressScale: s.pressScale
    }

    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
    TapHandler { id: tap; enabled: s.live; onTapped: s.activated() }
}
