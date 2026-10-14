# Native Wayland canvas experiment

[简体中文](README.zh-CN.md) · **Paused research; not installed or enabled.**

This prototype exercises real `zwp_input_popup_surface_v2` surfaces on a
disposable nested niri 26.04. It does not load an fcitx addon or claim the
desktop input-method seat. The client implements both sides of text-input-v3
and input-method-v2, sends controlled cursor rectangles, and paints a solid
120 × 48 marker in a transparent canvas.

The test starts a separate niri window, so desktop focus can briefly change.
The nested instance uses a separate Wayland socket and IPC socket. Screenshots,
logs, generated protocol sources and the test binary stay under `build/canvas-probe/`.
It terminates the instance it started and does not restart the desktop compositor.

```sh
make prepare
python3 experiments/canvas-probe/build.py
popup-venv/bin/python experiments/canvas-probe/check.py
```

The build defaults use the project's prepared fcitx 5.1.21 source and system
development packages. `build.py --help` allows their paths to be changed;
`--sysroot` optionally selects extracted Fedora packages.
`check.py --work-dir` and `build.py --work-dir` must refer to the same directory.
The test needs niri, gcc, wayland-scanner, the XML protocols and PySide6.

## Results on this machine

Coordinates below are actual pixels from the nested compositor's screenshots,
with a 1271 × 1523 output at scale 1. The parent fills that output.

| State | Marker x, y | Meaning |
| --- | --- | --- |
| Compact popup, cursor 150, 150 | 166, 190 | Baseline with 16 px padding |
| `wl_surface.offset(-64, -64)` | 166, 190 | Root attach offset does not reposition this IM popup |
| Expanded 360 × 240 root | 246, 270 | Positive canvas padding changes the visible anchor |
| Cursor x +30, marker x −30 inside canvas | 246, 270 | Relative compensation preserves position after commit |
| Negative subsurface canvas | 166, 190 | Provides space above and left of the root |
| Cursor x +30, before responding | 196, 190 | Old surface already moves with the new cursor |
| Same cursor, after compensation | 166, 190 | Compensation restores the previous pose |
| Spring samples after compensation | 170 → 184 → 196, y=190 | Native surface can display intermediate moving frames |
| Wrap to cursor 80, 200, before responding | 66, 240 | Cursor updates move the old surface independently |
| Wrap compensated in fixed canvas | 166, 190, width 114 | Canvas clips the last 6 pixels of the marker |
| Wrap compensated in expanded canvas | 166, 190, width 120 | Expanding to cover both poses resolves that clipping |
| Compact root near output bottom | 166, 1413 | Fits below cursor |
| Expanded root at same cursor | 246, 1229 | Larger bbox makes niri choose above |
| Negative subsurface at same cursor | 166, 1149 | Entire surface-tree bbox affects edge positioning |

After running, `build/canvas-probe/measurements.json` contains measured positions; `protocol.log` there contains
the corresponding rectangle events and commits. Tests assert screen positions,
intermediate spring poses, preserved marker width and the edge-placement change.
Root input regions cover only the marker, or are empty when the marker is in
a subsurface. Transparent subsurface pixels also have an empty input region
outside the marker. Pointer delivery has not been separately automated.

## Limit of this prototype

Canvas expansion and in-surface animation work, including recovering a
clipped wrap by enlarging the canvas. They do not alone guarantee continuous
screen movement with niri's current popup placement behavior.

When an application changes its cursor rectangle, niri repositions the existing
popup before the input-method client commits a compensating frame. The test
deliberately pauses between these operations to capture both states. This
demonstrates an unsynchronized interval; it does **not** prove every real
keypress presents a bad frame. A fast renderer may respond before the next
compositor frame, but the current protocol supplies no atomic synchronization
guarantee. Losing that race can show a jump and correction before the spring.

Edge placement depends on the full root/subsurface bounding box. Adding canvas
space can itself change above/below placement or horizontal clamping. The
`text_input_rectangle` event reports the application's cursor rectangle and
does not report niri's final popup origin or its placement decision. The current
niri IPC does not provide exact tiled-window screen origins either.

A complete implementation needs a way to synchronize relocation with the
replacement pixels and determine the final popup origin, or a surface whose
screen origin remains stable while the caret moves. This experiment does not
establish that changing the compositor is the only possible solution. It does
establish that the simple expanded-popup approach is not ready to replace the
current native frontend for arbitrary movement.
