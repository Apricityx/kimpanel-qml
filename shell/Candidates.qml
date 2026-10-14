import QtQuick

// Candidate strip: a fixed pool of cells (no delegate churn per keystroke),
// one highlight that glides between cells with a slight liquid stretch.
Item {
    id: c

    property var items: []
    property int cursor: -1
    property bool vertical: false
    property int session: 0
    property real maxWidth: 900

    readonly property int pool: 16
    readonly property int cellH: 34
    readonly property int padX: 10
    readonly property int gap: 2
    readonly property real maxTextWidth: vertical ? 420 : 260

    FontMetrics { id: fmText; font.family: Theme.font; font.pixelSize: Theme.textSize }
    FontMetrics { id: fmLabel; font.family: Theme.font; font.pixelSize: Theme.labelSize }

    function cellWidth(e) {
        const lw = e.label ? fmLabel.advanceWidth(e.label) + 5 : 0;
        return Math.ceil(2 * padX + lw + Math.min(fmText.advanceWidth(e.text), maxTextWidth));
    }

    // Pure function of the data, so geometry is known before anything moves.
    readonly property var layout: {
        const n = Math.min(items.length, pool);
        const rects = [];
        let x = 0, y = 0, w = 0, rowW = 0;
        if (vertical) {
            for (let i = 0; i < n; i++) w = Math.max(w, cellWidth(items[i]));
            for (let i = 0; i < n; i++) rects.push({ x: 0, y: i * (cellH + gap), w: w });
            const h = n ? n * (cellH + gap) - gap : 0;
            return { rects, w: w, h: h };
        }
        const limit = maxWidth;
        for (let i = 0; i < n; i++) {
            const cw = cellWidth(items[i]);
            if (x > 0 && x + cw > limit) { y += cellH + gap; x = 0; }
            rects.push({ x: x, y: y, w: cw });
            x += cw + gap;
            rowW = Math.max(rowW, x - gap);
        }
        return { rects, w: rowW, h: n ? y + cellH : 0 };
    }

    implicitWidth: layout.w
    implicitHeight: layout.h

    property bool fresh: true
    onSessionChanged: fresh = true
    onLayoutChanged: refresh()
    onCursorChanged: placeHighlight(false)
    Component.onCompleted: refresh()

    function refresh() {
        if (!cells.count)
            return;
        for (let i = 0; i < pool; i++) {
            const cell = cells.itemAt(i);
            if (cell)
                cell.update(i < items.length ? items[i] : null, layout.rects[i] || null, fresh);
        }
        placeHighlight(fresh);
        fresh = false;
    }

    // ---- highlight: four edge springs; the leading edge moves first ----
    Spring { id: hl; stiffness: 900; dampingRatio: 0.86; epsilon: 0.1 }
    Spring { id: hr; stiffness: 900; dampingRatio: 0.86; epsilon: 0.1 }
    Spring { id: ht; stiffness: 900; dampingRatio: 0.86; epsilon: 0.1 }
    Spring { id: hb; stiffness: 900; dampingRatio: 0.86; epsilon: 0.1 }
    property real hlOpacity: 0
    Behavior on hlOpacity { NumberAnimation { duration: 120 } }

    function placeHighlight(jump) {
        const r = cursor >= 0 ? layout.rects[cursor] : null;
        if (!r) { hlOpacity = 0; return; }
        const L = r.x, R = r.x + r.w, T = r.y, B = r.y + cellH;
        if (jump || hlOpacity < 0.05) {
            hl.snap(L); hr.snap(R); ht.snap(T); hb.snap(B);
        } else {
            const fwdX = L > hl.to, fwdY = T > ht.to;
            hl.stiffness = fwdX ? 520 : 1100; hr.stiffness = fwdX ? 1100 : 520;
            ht.stiffness = fwdY ? 520 : 1100; hb.stiffness = fwdY ? 1100 : 520;
            hl.to = L; hr.to = R; ht.to = T; hb.to = B;
        }
        hlOpacity = 1;
    }

    // ---- page slide ----
    Spring { id: slide; stiffness: 520; dampingRatio: 0.9; epsilon: 0.2 }
    Connections {
        target: Bridge
        function onPageTurned(dir) {
            slide.kick(dir * 28);
            placeHighlight(true);
        }
    }

    Item {
        id: track
        width: c.width
        height: c.height
        x: c.vertical ? 0 : slide.value
        y: c.vertical ? slide.value * 0.6 : 0
        opacity: 1 - Math.min(Math.abs(slide.value) / 28, 1) * 0.7

        Repeater {
            id: cells
            model: c.pool
            delegate: CandidateSlot {
                required property int index
                order: index
                height: c.cellH
                padX: c.padX
                maxTextWidth: c.maxTextWidth
                selected: index === c.cursor
                onActivated: Bridge.select(index)
            }
        }

        // The highlight, plus an on-primary copy of each cell's text clipped to it.
        Rectangle {
            id: highlight
            x: hl.value
            y: ht.value
            width: Math.max(0, hr.value - hl.value)
            height: Math.max(0, hb.value - ht.value)
            radius: 10
            color: Theme.primary
            opacity: c.hlOpacity
            clip: true

            Repeater {
                model: c.pool
                delegate: CandidateInk {
                    required property int index
                    // itemAt() is not notifiable; resolve once both pools exist.
                    property Item cell: null
                    Component.onCompleted: cell = Qt.binding(() => cells.count > index ? cells.itemAt(index) : null)
                    layers: cell ? cell.textLayers : null
                    visible: cell ? cell.visible : false
                    labelColor: Theme.ink
                    textColor: Theme.ink
                    maxTextWidth: c.maxTextWidth
                    x: cell ? cell.x + cell.padX - highlight.x : 0
                    y: cell ? cell.y - highlight.y : 0
                    height: cell ? cell.height : 0
                    width: cell ? Math.max(0, cell.width - 2 * cell.padX) : 0
                    opacity: cell ? cell.opacity : 0
                    pressScale: cell ? cell.pressScale : 1
                }
            }
        }

    }
}
