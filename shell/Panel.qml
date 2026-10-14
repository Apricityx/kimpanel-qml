import QtQuick
import QtQuick.Effects

// The floating card. Content lays out instantly at its final geometry; the
// card's frame (position, size) follows on springs, and reveal/hide is a
// spring too, so every change retargets smoothly mid-flight.
Item {
    id: p

    // Native input-method popup: the compositor owns the global position.
    property bool compositorPopup: false
    readonly property real popupPadding: 16

    readonly property bool active: Bridge.active
    readonly property bool hasComp: Bridge.text.length > 0
    readonly property bool hasCands: Bridge.candidates.length > 0
    readonly property bool pill: hasComp && !hasCands   // aux-only, e.g. IM switch
    readonly property var spot: Bridge.spot && Bridge.spot.x !== undefined ? Bridge.spot : null

    readonly property int pad: 6
    readonly property int compPadX: 10
    readonly property int compH: 24
    readonly property int margin: 8
    readonly property int caretGap: 6

    readonly property real targetW: Math.ceil(Math.max(
        hasComp ? comp.implicitWidth + 2 * compPadX : 0,
        hasCands ? cands.implicitWidth : 0) + 2 * pad)
    readonly property real targetH: Math.ceil((hasComp ? compH : 0)
        + (hasCands ? cands.implicitHeight + (hasComp ? 2 : 0) : 0) + 2 * pad)

    // ---- placement ----
    property bool above: false

    function place(fresh, jump) {
        const w = targetW, h = targetH;
        let x, y;
        if (compositorPopup) {
            x = popupPadding;
            y = popupPadding;
            above = false;
        } else if (!spot) {
            x = (width - w) / 2;
            y = height * 0.86 - h;
            above = true;
        } else {
            const sh = Math.max(spot.h, 18);
            const caretX = spot.x;
            // Follow every caret update, including committed text advancing
            // the next composition. Springs keep their current velocity.
            const below = height - (spot.y + sh) - caretGap - margin;
            const roomAbove = spot.y - caretGap - margin;
            if (fresh || (above ? roomAbove < h : below < h))
                above = below < h && roomAbove > below;
            x = caretX;
            y = above ? spot.y - caretGap - h : spot.y + sh + caretGap;
        }
        x = Math.max(margin, Math.min(x, width - w - margin));
        y = Math.max(margin, Math.min(y, height - h - margin));
        if (jump) { cx.snap(x); cy.snap(y); cw.snap(w); ch.snap(h); }
        else { cx.to = x; cy.to = y; cw.to = w; ch.to = h; }
    }

    // Coalesce: one placement per event-loop turn, after all fields landed.
    property bool _fresh: false
    property bool _jump: false
    property bool _queued: false
    function schedule(fresh, jump) {
        _fresh = _fresh || fresh;
        _jump = _jump || jump;
        if (_queued) return;
        _queued = true;
        Qt.callLater(() => { _queued = false; place(_fresh, _jump); _fresh = _jump = false; });
    }

    // A partially faded card is still on screen: never teleport it when a
    // new composition interrupts hiding, even near the end of the fade.
    onActiveChanged: if (active) schedule(true, !frame.visible)
    Connections {
        target: Bridge
        function onSessionChanged() { if (p.active) p.schedule(true, false); }
    }
    onSpotChanged: if (active) schedule(false, false)
    onTargetWChanged: if (active) schedule(false, false)
    onTargetHChanged: if (active) schedule(false, false)
    onWidthChanged: schedule(false, !frame.visible)
    onHeightChanged: schedule(false, !frame.visible)

    Spring { id: cx; stiffness: 760; dampingRatio: 1.0; epsilon: 0.1 }
    Spring { id: cy; stiffness: 760; dampingRatio: 1.0; epsilon: 0.1 }
    Spring { id: cw; stiffness: 620; dampingRatio: 0.92; epsilon: 0.1 }
    Spring { id: ch; stiffness: 620; dampingRatio: 0.92; epsilon: 0.1 }

    // 0 = hidden, 1 = shown. Snappier and overshoot-free on the way out.
    Spring {
        id: reveal
        to: p.active ? 1 : 0
        stiffness: p.active ? 560 : 900
        dampingRatio: p.active ? 0.74 : 1.0
        epsilon: 0.002
        // Do not snap(0) here: that would write `to` and destroy the binding.
    }

    // If the spring clock never ticks, still show the card.
    Timer {
        interval: 80
        running: p.active && reveal.value < 0.05
        onTriggered: {
            if (reveal.value < 0.05)
                reveal.value = 1;
        }
    }

    readonly property alias frame: frame
    readonly property alias hitbox: hitbox
    Item {
        id: hitbox
        x: cx.value; y: cy.value
        width: p.active ? cw.value : 0
        height: p.active ? ch.value : 0
    }

    Item {
        id: frame
        x: cx.value
        y: cy.value
        width: cw.value
        height: ch.value
        visible: reveal.value > 0.003
        // Use one curve in both directions. Switching active must not change
        // opacity until the spring actually advances on its next tick.
        opacity: Math.min(1, Math.max(0, reveal.value * 1.6))

        transform: [
            Scale {
                // Stable origin, even when the caret wraps or placement flips
                // while reveal is midway through an interrupted hide.
                origin.x: frame.width / 2
                origin.y: frame.height / 2
                xScale: 0.94 + 0.06 * reveal.value
                yScale: 0.88 + 0.12 * reveal.value
            },
            Translate { y: (1 - reveal.value) * -6 }
        ]

        RectangularShadow {
            anchors.fill: card
            offset: Qt.vector2d(0, 6)
            blur: 22
            spread: -2
            radius: card.radius
            color: Qt.alpha(Theme.shadow, 0.42)
        }

        Rectangle {
            id: card
            anchors.fill: parent
            radius: p.pill ? Math.min(height / 2, Theme.radius + 4) : Theme.radius
            Behavior on radius { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
            color: Theme.surface
            border.width: 1
            border.color: Qt.alpha(Theme.outline, 0.7)

            Item {
                anchors.fill: parent
                anchors.margins: 1
                clip: true

                Composition {
                    id: comp
                    visible: p.hasComp
                    x: p.pad + p.compPadX - 1
                    y: p.pad - 1 + (p.compH - height) / 2
                    text: Bridge.text
                    caret: Bridge.caret
                    session: Bridge.session
                    pixelSize: p.pill ? Theme.textSize : Theme.compSize
                    color: p.pill ? Theme.fg : Theme.muted
                }

                Candidates {
                    id: cands
                    visible: p.hasCands
                    x: p.pad - 1
                    y: p.pad - 1 + (p.hasComp ? p.compH + 2 : 0)
                    width: implicitWidth
                    height: implicitHeight
                    items: Bridge.candidates
                    cursor: Bridge.cursor
                    vertical: Bridge.vertical
                    session: Bridge.session
                    maxWidth: Math.min(980, p.width * 0.7)
                }
            }

            WheelHandler {
                property real acc: 0
                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                onWheel: ev => {
                    acc += ev.angleDelta.y;
                    if (acc <= -120) { acc = 0; Bridge.next(); }
                    else if (acc >= 120) { acc = 0; Bridge.prev(); }
                }
            }
        }
    }
}
