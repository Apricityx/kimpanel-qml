import QtQuick

// "label  text" on one line. Each cell draws it twice: normally, and again in
// on-primary colors inside the highlight's clip, so text recolors exactly
// where the gliding highlight covers it.
Row {
    id: r

    property var entry: null
    property color labelColor: Theme.muted
    property color textColor: Theme.fg
    property real maxTextWidth: 260

    spacing: 5

    Text {
        visible: text.length > 0
        text: r.entry && r.entry.label ? r.entry.label : ""
        color: r.labelColor
        font.family: Theme.font
        font.pixelSize: Theme.labelSize
        anchors.baseline: main.baseline
    }

    Text {
        id: main
        text: r.entry ? r.entry.text : ""
        color: r.textColor
        font.family: Theme.font
        font.pixelSize: Theme.textSize
        width: Math.min(implicitWidth, r.maxTextWidth)
        elide: Text.ElideRight
    }
}
