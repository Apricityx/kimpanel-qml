import QtQuick

// Normal and highlighted text share the same fully opaque scrolling rows.
Item {
    id: ink
    property var layers: null
    property color labelColor: Theme.muted
    property color textColor: Theme.fg
    property real maxTextWidth: 260
    property real pressScale: 1
    clip: true

    Repeater {
        model: ink.layers ? ink.layers.count : 0
        delegate: SlotText {
            required property int index
            readonly property var face: ink.layers && ink.layers.count > index
                ? ink.layers.itemAt(index) : null
            entry: face ? face.entry : null
            visible: face ? face.onTrack : false
            y: (ink.height - implicitHeight) / 2 + (face ? face.dy : 0)
            labelColor: ink.labelColor
            textColor: ink.textColor
            maxTextWidth: ink.maxTextWidth
            scale: ink.pressScale
        }
    }
}
