pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

// Colors follow DankMaterialShell's matugen palette and update live (with a
// cross-fade) when the wallpaper or theme changes.
Singleton {
    id: t

    readonly property string cacheDir: Quickshell.env("XDG_CACHE_HOME") || (Quickshell.env("HOME") + "/.cache")
    readonly property string configDir: Quickshell.env("XDG_CONFIG_HOME") || (Quickshell.env("HOME") + "/.config")

    // Avoid on* names: QML treats `onFoo` as a signal handler for `foo`.
    property color surface: "#202018"
    property color surfaceHigh: "#2a2b22"
    property color fg: "#e5e3d6"
    property color muted: "#c8c7b7"
    property color outline: "#47483b"
    property color primary: "#c3cd7c"
    property color ink: "#2d3400"
    property color shadow: "#000000"

    Behavior on surface { ColorAnimation { duration: 400 } }
    Behavior on surfaceHigh { ColorAnimation { duration: 400 } }
    Behavior on fg { ColorAnimation { duration: 400 } }
    Behavior on muted { ColorAnimation { duration: 400 } }
    Behavior on outline { ColorAnimation { duration: 400 } }
    Behavior on primary { ColorAnimation { duration: 400 } }
    Behavior on ink { ColorAnimation { duration: 400 } }

    property real radius: 14
    readonly property string font: "Noto Sans CJK SC"
    // Register a private CBDT/CBLC emoji font. System COLRv1 fonts can match
    // successfully yet produce entirely blank glyphs with current Qt builds.
    readonly property var emojiFont: FontLoader {
        // Quickshell's QML scanner blocks relative resources outside shell/.
        source: "file://" + Quickshell.shellDir + "/../assets/fonts/NotoColorEmoji.ttf"
    }
    readonly property int textSize: 17
    readonly property int labelSize: 11
    readonly property int compSize: 14

    FileView {
        path: t.cacheDir + "/DankMaterialShell/dms-colors.json"
        watchChanges: true
        onFileChanged: reload()
        onLoaded: t.applyColors(text())
    }

    FileView {
        path: t.configDir + "/DankMaterialShell/settings.json"
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            try {
                const r = JSON.parse(text()).cornerRadius;
                if (typeof r === "number")
                    t.radius = Math.max(6, r + 2);
            } catch (e) {}
        }
    }

    function applyColors(raw) {
        let all;
        try { all = JSON.parse(raw); } catch (e) { return; }
        const c = (all.colors || {})[all.mode || "dark"];
        if (!c) return;
        const pick = (k, cur) => c[k] ? c[k] : cur;
        surface = pick("surface_container_high", surface);
        surfaceHigh = pick("surface_container_highest", surfaceHigh);
        fg = pick("on_surface", fg);
        muted = pick("on_surface_variant", muted);
        outline = pick("outline_variant", outline);
        primary = pick("primary", primary);
        ink = pick("on_primary", ink);
        shadow = pick("shadow", shadow);
    }
}
