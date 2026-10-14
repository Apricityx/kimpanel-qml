import QtQuick

// Critically-tunable spring that follows `to`, keeping its velocity when the
// target moves mid-flight (so rapid keystrokes glide instead of restarting).
//
// Quickshell's render loop has no animation driver, so FrameAnimation never
// ticks. A 8 ms Timer is the reliable clock here; at 125 Hz it still looks
// smooth, and niri-style stiffness/damping still apply.
Item {
    id: s

    property real to: 0
    property real value: 0
    property real velocity: 0
    property real stiffness: 700
    property real dampingRatio: 0.9
    property real epsilon: 0.05

    implicitWidth: 0
    implicitHeight: 0
    width: 0
    height: 0

    readonly property bool moving: anim.running

    function snap(v) {
        anim.stop();
        velocity = 0;
        // Assign value first so onToChanged sees them equal and does not restart.
        if (v !== undefined) {
            value = v;
            to = v;
        } else {
            value = to;
        }
    }

    function kick(from) {
        value = from;
        velocity = 0;
        anim.restart();
    }

    onToChanged: if (value !== to && !anim.running) anim.start()

    Timer {
        id: anim
        interval: 8
        repeat: true
        onTriggered: {
            const dt = interval / 1000;
            const k = s.stiffness;
            const c = 2 * s.dampingRatio * Math.sqrt(k);
            let x = s.value, v = s.velocity;
            const n = Math.max(1, Math.ceil(dt * 1000));
            const h = dt / n;
            for (let i = 0; i < n; i++) {
                v += (-k * (x - s.to) - c * v) * h;
                x += v * h;
            }
            if (Math.abs(x - s.to) < s.epsilon && Math.abs(v) < s.epsilon * 10) {
                s.velocity = 0;
                s.value = s.to;
                stop();
            } else {
                s.velocity = v;
                s.value = x;
            }
        }
    }
}
