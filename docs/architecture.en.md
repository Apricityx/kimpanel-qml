# Architecture and maintenance

[中文](architecture.zh-CN.md) · [Home](../README.md)

## Stable overlay and explicit popup fallback

- Native `wayland_v2`: classicui owns a transparent, input-empty 1×1 popup
  solely for `text_input_rectangle` events. Application-surface-local logical
  pixels are stored with scale 1.0 and sent as `SetRelativeSpotRectV2`.
  kimpanel sends visible candidates to the overlay, never to this locator.
  Focus loss clears the role before destroying its surface.
  The locator retains the last protocol rectangle for its active context and
  restores it before kimpanel forwards cursor/panel updates. This prevents
  fcitx's virtual-context focus refresh from replacing it with a stale parent
  caret. New protocol rectangles replace the cache; focus loss/destruction
  clears it. This does not provide a global window origin or replay rectangles
  committed before locator creation.
- Native, toolkit DBus / XWayland fcitx4/XIM: kimpanel → GLib bridge → Unix socket → Quickshell layer-shell
  overlay. The output-sized surface stays stable; only the card receives input.
  `Socket` parses newline-delimited state directly and receives a latest-state
  replay on reconnect. The atomically replaced `panel-state.json` is a diagnostic
  snapshot, not a UI transport: `tail -F` can miss short compositions.
  For xwayland-satellite windows, the bridge subtracts the focused X toplevel's
  virtual-root origin, divides by output scale, and adds the niri window origin.
  WM_CLASS must match niri's app ID; only X geometry/class are read, never text.
  Floating origins are exact. Tiled origins remain estimates; absent an explicit
  `KIMPANEL_BAR_SIZE`, full-height column stacks estimate the top/bottom bar zone
  for the satellite route. Native and toolkit relative rects use the focused
  window origin; tiled/scrolling origins remain estimates.
  Known Wayland windows with relative rectangles carry `spot.caretTop=true`:
  the card's top-left aligns with the caret rectangle's top-left, without adding
  caret height or a gap. XWayland keeps its existing below-caret placement.
  Screen-edge clamping/above placement still apply; estimated fallback points
  without a caret retain their previous placement.
- Native and toolkit contexts can retain focus in different fcitx focus groups
  at the same time. While a focused context owns a nonempty panel, unrelated
  caret/focus events and empty panel refreshes must not move or replace it.
  A new nonempty panel can take ownership; its stored caret is sent with the
  panel update so a previously suppressed cursor event is not required again.
- Explicit fallback (`KIMPANEL_NATIVE_UI=popup`): classicui owns the visible
  native popup. An independent PySide6 process renders Qt Quick offscreen.
  Seqpacket JSON carries state/commands; two 32 MiB shared-memory slots carry
  premultiplied ARGB. Epoch checks reject stale selections. Renderer failure
  falls back to Cairo for that fcitx process. Toolkit contexts stay on overlay.
- `shell/` owns shared layout/text/spring components. Relative links in
  `popup/` reuse them; each host has its own Bridge and Theme singleton.
  Both Themes register a private CBDT/CBLC Noto emoji font for color candidates;
  no system font configuration is modified.

The launcher defaults `KIMPANEL_NATIVE_UI` to `overlay`, setting
`FCITX_KIMPANEL_NATIVE_OVERLAY=1`. `popup` sets it to 0 and restores the renderer
launcher. `FCITX_KIMPANEL_WAYLAND_POPUP=1` retains the legacy native route;
`FCITX_KIMPANEL_TOOLKIT_UI=1` retains toolkit overlay. They do not spoof the desktop environment or
globally set GTK/QT input modules. Only three local addons are selected;
system core libraries and input engines are not replaced.

## Motion and limits

Position/reveal springs preserve velocity during retargeting and interrupted
fades. Candidate text scrolls vertically and remains opaque. The page-button
component is retained as source but is not included in candidate layout.

Native candidates animate inside the stable overlay, not by moving a
compositor-owned popup. Global movement in the explicit popup fallback remains
unanimated. Offscreen placement tests establish QML continuity only. niri IPC
does not expose exact tiled-window screen origins; relative-coordinate mapping
uses estimates during scrolling. Caret rectangles do not provide a global window
origin; absent a rectangle, the bridge uses a cached same-window spot or a guess.
The nested niri check did not replay a rectangle committed before locator
creation; repeated activation can also clear it until the next application update.
Surface-local caret coordinates can also differ from toplevel geometry for
subsurfaces/client-side decorations. Software Qt Quick can omit shadows. DMS colors are
optional; fallback colors/radius are built in. Multi-output/native typing needs
interactive validation.

The canvas probe in `experiments/` is paused research. It can preserve a pose
after compensation and display spring movement, but old surfaces can relocate
before replacement pixels arrive. Expanded bounds alter edge placement. It is
not installed and must not be presented as a supported animation feature.

## Development

`native/qmlpopup.{cpp,h}` and `native/overlaycursor.{cpp,h}` are canonical added sources. Upstream file changes
live in `native/patches/fcitx5-integration.patch`. Source preparation is locked
by `native/upstream.json`. Never edit only the generated upstream copy or
install its core libraries. Preserve developer-edited checkouts; use a fresh
work directory for ports. Both revision hashes, the patch, tests and documents
must be reviewed together for an upstream upgrade.

```sh
make check             # Python tests and shell syntax; no desktop activity
make test-renderer     # IPC pixels, text reel and placement offscreen
make test-overlay      # Quickshell offscreen socket/reconnect, no desktop surface
```

Automated typing may bypass the IM. Manual acceptance should cover native
typing, toolkit typing, selection/submission, paging, rapid commit/retype,
fade interruption, wrapping, edges, outputs, and renderer-failure fallback.
Never restart the compositor as a routine test.
