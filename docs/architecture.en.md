# Architecture and maintenance

[中文](architecture.zh-CN.md) · [Home](../README.md)

## Two routes

- Native `wayland_v2`: patched classicui owns the Wayland popup and buffers.
  An independent PySide6 process renders Qt Quick offscreen. Seqpacket JSON
  transports state/commands; two 32 MiB shared-memory slots carry premultiplied
  ARGB pixels. Epoch checks reject stale selections. Renderer failure falls
  back to classicui Cairo for that fcitx process.
- Toolkit DBus: kimpanel → GLib bridge → Unix socket → Quickshell layer-shell
  overlay. The output-sized surface stays stable; only the card receives input.
- `shell/` owns shared layout/text/spring components. Relative links in
  `popup/` reuse them; each host has its own Bridge and Theme singleton.

The routing flags are `FCITX_KIMPANEL_WAYLAND_POPUP=1` and
`FCITX_KIMPANEL_TOOLKIT_UI=1`. They do not spoof the desktop environment or
globally set GTK/QT input modules. Only three local addons are selected;
system core libraries and input engines are not replaced.

## Motion and limits

Position/reveal springs preserve velocity during retargeting and interrupted
fades. Candidate text scrolls vertically and remains opaque. The page-button
component is retained as source but is not included in candidate layout.

Native global movement remains compositor-owned, not animated. Offscreen
placement tests establish local QML continuity only. niri IPC does not expose
exact tiled-window screen origins; DBus relative-coordinate mapping uses
estimates during scrolling. Software Qt Quick can omit shadows. DMS colors are
optional; fallback colors/radius are built in. Multi-output/native typing needs
interactive validation.

The canvas probe in `experiments/` is paused research. It can preserve a pose
after compensation and display spring movement, but old surfaces can relocate
before replacement pixels arrive. Expanded bounds alter edge placement. It is
not installed and must not be presented as a supported animation feature.

## Development

`native/qmlpopup.{cpp,h}` are canonical added sources. Upstream file changes
live in `native/patches/fcitx5-integration.patch`. Source preparation is locked
by `native/upstream.json`. Never edit only the generated upstream copy or
install its core libraries. Preserve developer-edited checkouts; use a fresh
work directory for ports. Both revision hashes, the patch, tests and documents
must be reviewed together for an upstream upgrade.

```sh
make check             # Python tests and shell syntax; no desktop activity
make test-renderer     # IPC pixels, text reel and placement offscreen
```

Automated typing may bypass the IM. Manual acceptance should cover native
typing, toolkit typing, selection/submission, paging, rapid commit/retype,
fade interruption, wrapping, edges, outputs, and renderer-failure fallback.
Never restart the compositor as a routine test.
