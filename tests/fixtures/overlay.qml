import QtQuick
import Quickshell
import "." as UI

// Offscreen harness: no layer-shell surface, real input or desktop interaction.
ShellRoot {
    Window {
        id: window
        width: 1000
        height: 1000
        visible: true
        UI.Panel { id: panel; anchors.fill: parent }
    }
    Connections {
        target: UI.Bridge
        function onGrabRequested(path) { grab.path = path; grab.restart(); }
    }
    Timer {
        id: grab
        property string path
        interval: 650
        onTriggered: panel.frame.grabToImage(result => {
            console.info("GRABBED", result.saveToFile(path));
            // Exercise the same buffered command path as pointer selection.
            UI.Bridge.select(0);
        })
    }
    Timer {
        interval: 50
        running: true
        repeat: true
        onTriggered: console.info("OVERLAY", JSON.stringify({
            active: UI.Bridge.active, count: UI.Bridge.candidates.length,
            fontReady: UI.Theme.emojiFont.status === FontLoader.Ready,
            session: UI.Bridge.session, visible: panel.frame.visible,
            width: panel.frame.width, height: panel.frame.height,
            x: panel.frame.x, y: panel.frame.y
        }))
    }
    Timer { interval: 12000; running: true; onTriggered: Qt.quit() }
}
