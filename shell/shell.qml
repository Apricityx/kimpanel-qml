import QtQuick
import Quickshell
import Quickshell.Wayland

// fcitx5 candidate window for niri. State arrives from bridge.py (Bridge.qml).
//
// The surface covers the whole output and never resizes: the card moves and
// resizes inside it on springs, so typing never triggers a compositor
// reconfigure (the old per-keystroke resize was the main source of jank).
// Input is masked to the card, so clicks elsewhere pass through.
ShellRoot {
    id: root

    // Keep the surface mapped for a while after hiding so the next keystroke
    // animates in on the very first frame instead of waiting for a new map.
    Timer { id: linger; interval: 15000 }
    Connections {
        target: Bridge
        function onActiveChanged() { if (!Bridge.active) linger.restart(); }
    }

    property var lastScreen: Quickshell.screens.length ? Quickshell.screens[0] : null
    readonly property var targetScreen: {
        const name = Bridge.spot ? Bridge.spot.output : null;
        const all = Quickshell.screens;
        for (let i = 0; i < all.length; i++)
            if (all[i].name === name) return all[i];
        return lastScreen;
    }
    onTargetScreenChanged: if (targetScreen) lastScreen = targetScreen

    PanelWindow {
        id: win

        screen: root.targetScreen
        visible: Bridge.active || linger.running || panel.frame.visible
        color: "transparent"

        anchors { top: true; bottom: true; left: true; right: true }
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.namespace: "kimpanel-qml"
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

        mask: Region { item: panel.hitbox }

        Panel {
            id: panel
            anchors.fill: parent
        }

        // Debug aid for `kimpanel-qmlctl demo --grab`: save the card as PNG.
        Connections {
            target: Bridge
            function onGrabRequested(path) { grab.path = path; grab.restart(); }
        }
        Timer {
            id: grab
            property string path
            interval: 650
            onTriggered: panel.frame.grabToImage(r => {
                console.info("kimpanel: grabbed", path, r.saveToFile(path));
            })
        }
    }
}
