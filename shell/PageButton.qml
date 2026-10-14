import QtQuick
import QtQuick.Shapes

// Chevron button for paging; dims instead of disappearing so the strip
// width does not jump when you reach the first/last page.
Item {
    id: b

    property int dir: 1
    property bool available: true

    signal clicked()

    width: 26
    opacity: available ? 1 : 0.28
    Behavior on opacity { NumberAnimation { duration: 160 } }

    Rectangle {
        anchors.centerIn: parent
        width: 22
        height: 22
        radius: 11
        color: Theme.fg
        opacity: hover.hovered && b.available ? (tap.pressed ? 0.16 : 0.09) : 0
        Behavior on opacity { NumberAnimation { duration: 120 } }
    }

    Shape {
        anchors.centerIn: parent
        anchors.horizontalCenterOffset: tap.pressed && b.available ? b.dir * 1.5 : 0
        Behavior on anchors.horizontalCenterOffset { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
        width: 7
        height: 12
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeColor: Theme.muted
            strokeWidth: 1.8
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            startX: b.dir > 0 ? 1 : 6
            startY: 1
            PathLine { x: b.dir > 0 ? 6 : 1; y: 6 }
            PathLine { x: b.dir > 0 ? 1 : 6; y: 11 }
        }
    }

    HoverHandler { id: hover; cursorShape: b.available ? Qt.PointingHandCursor : Qt.ArrowCursor }
    TapHandler { id: tap; enabled: b.available; onTapped: b.clicked() }
}
