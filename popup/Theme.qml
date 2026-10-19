pragma Singleton
import QtQuick
QtObject {
    readonly property var colors: Native ? Native.colors : ({})
    property color surface: colors.surface || "#202018"
    property color surfaceHigh: colors.surface_container_highest || "#2a2b22"
    property color fg: colors.on_surface || "#e5e3d6"
    property color muted: colors.on_surface_variant || "#c8c7b7"
    property color outline: colors.outline_variant || "#47483b"
    property color primary: colors.primary || "#c3cd7c"
    property color ink: colors.on_primary || "#2d3400"
    property color shadow: colors.shadow || "#000000"
    property real radius: Native ? Native.radius : 14
    readonly property string font: "Noto Sans CJK SC"
    readonly property var emojiFont: FontLoader {
        source: Qt.resolvedUrl("../assets/fonts/NotoColorEmoji.ttf")
    }
    readonly property int textSize: 17
    readonly property int labelSize: 11
    readonly property int compSize: 14
    Behavior on surface { ColorAnimation { duration: 400 } }
    Behavior on primary { ColorAnimation { duration: 400 } }
}
