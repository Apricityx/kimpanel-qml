# kimpanel-qml

English | [简体中文](README.zh-CN.md)

A Quickshell QML candidate frontend for **fcitx5 on niri/Wayland**. It keeps the
system input method core and engines and only replaces the UI.

## Features

- One stable overlay for native Wayland, toolkit DBus, XWayland and XIM candidates.
- Invisible native caret surface; visible native popups remain an explicit
  `KIMPANEL_NATIVE_UI=popup` fallback.
- Caret-top alignment on Wayland, xwayland-satellite cursor translation, and
  best-effort tiled-window origins.
- Vertically scrolling candidate reel with spring animation, pointer, wheel and
  keyboard paging, but no paging buttons.
- Private pinned color emoji font; optional DankMaterialShell colors and radius.

## Build

The native addons target a pinned fcitx5 **5.1.23**; this is not a standalone engine.

```sh
make emoji-font renderer-env   # PySide6 environment + pinned emoji font
make prepare build
make test test-renderer test-overlay
make install                   # only if the system fcitx5 matches the lock
```

Installation never activates, restarts or edits session settings. Sources,
versions and rollback: [build](docs/build.en.md), [install](docs/install.en.md),
[architecture](docs/architecture.en.md), [provenance](docs/third-party.md).

## Control

```sh
./kimpanel-qmlctl status | start | restart | logs | demo
```
