# Building

[English](build.en.md) | [简体中文](build.zh-CN.md)

## Prerequisites

Linux/Wayland, Python 3.10+, Git, CMake 3.16+, a C++17 compiler, Make, binutils
(`readelf`), and matching fcitx5 system runtime/development dependencies.

Runtime: fcitx5 and your input engines, niri, Quickshell (`qs`, with Qt Quick
Effects and Wayland/Io modules), Python PyGObject and dbus-python, a Chinese font
(default: Noto Sans CJK SC). DankMaterialShell is optional.
XWayland satellite positioning also uses the system `libxcb` runtime library
for read-only focused-window geometry; no Python X11 package is required.
`make renderer-env` also runs `make emoji-font`, fetching the pinned private
Noto Color Emoji CBDT/CBLC font (~11 MB) with SHA-256 verification. Its OFL license
and provenance are in `assets/fonts/`; the binary is ignored by Git. This avoids
blank emoji on Qt builds unable to paint the system's COLRv1 font, without
changing fontconfig or installing a system font. If reusing an existing renderer
environment, run `make emoji-font` separately before testing or installing.

Native build dependencies include libuv, DBus, UUID, XCB/xcb-imdkit, xkbcommon/xkbfile,
cairo, pango, gdk-pixbuf, librsvg, GLib/GIO, nlohmann-json, Wayland/scanner, extra-cmake-modules,
iso-codes, xkeyboard-config, wayland-protocols >=1.46 and
plasma-wayland-protocols >=1.20. Systemd/libcap are optional upstream dependencies.

Example Fedora development packages (review availability for your release):

```sh
sudo dnf install gcc-c++ cmake make git binutils extra-cmake-modules \
  gettext-devel zlib-devel libuv-devel dbus-devel libuuid-devel \
  libxcb-devel xcb-util-devel xcb-util-wm-devel xcb-util-keysyms-devel xcb-imdkit-devel expat-devel \
  libxkbcommon-devel libxkbcommon-x11-devel libxkbfile-devel cairo-devel pango-devel \
  gdk-pixbuf2-devel librsvg2-devel glib2-devel json-devel wayland-devel \
  wayland-protocols-devel plasma-wayland-protocols-devel iso-codes-devel \
  xkeyboard-config-devel systemd-devel libcap-devel
sudo dnf install python3-gobject python3-dbus google-noto-sans-cjk-fonts
```

This installs development dependencies only. It does not install this frontend.
The pinned patch must be ported before deployment with fcitx5 versions other
than 5.1.23; installing dependencies on a newer distro does not perform that port.

## Reproducible source preparation

```sh
make prepare
make build JOBS=6
```

`scripts/build.py` fetches fcitx5 tag 5.1.23, verifies its exact commit, applies
`native/patches/fcitx5-integration.patch`, copies `native/qmlpopup.{cpp,h}` and
`native/overlaycursor.{cpp,h}`,
and initializes/verifies Yoga. Repeated preparation is safe for the managed
tree; conflicting/unrelated changes are rejected, not reset.

Outputs:

```text
build/fcitx5/              patched upstream checkout (ignored)
build/fcitx5-build/        CMake tree (ignored)
build/addons/             libclassicui.so, libkimpanel.so, libdbusfrontend.so
                         build-info.json
```

Only the three addons are collected. **Never run `cmake --install` on the
upstream tree**: its fcitx core libraries must not replace system libraries.
RPATH/RUNPATH in collected addons is rejected.

Pass optional CMake settings with `--cmake-arg=-DKEY=VALUE`:

```sh
python3 scripts/build.py build --jobs 6 --cmake-arg=-DENABLE_X11=ON
```

## Python renderer and tests

```sh
make renderer-env
make check
make test-renderer
make test-overlay
```

PySide6 6.11.2 is installed in `popup-venv/`; GLib/dbus modules use system Python.
The moved historical venv remains usable through the old compatibility path;
new environments should be created at their final path, not relocated manually.
The offscreen checks do not claim an input-method seat or change desktop focus.
Artifacts are in `build/test-output/`.

### Native-overlay validation boundary

The 5.1.23 integration was built against an extracted sysroot and checked with
the system core/dependencies on 2026-10-14. Clean and repeated source preparation,
63 Python/packaging tests, renderer/overlay offscreen tests, system symbol
resolution and a real-addon installation under a temporary prefix passed.
Only the three addons were installed there; no desktop runtime was activated.

A separate disposable nested niri with private DBus and temporary XDG
configuration loaded the new classicui/kimpanel addons into system fcitx.
Native text-input caret changes reached the bridge through
`SetRelativeSpotRectV2` unchanged at output scale 1.5. Disabling/re-enabling
text-input destroyed/recreated the locator, and client disconnect cleaned it up.
An additional private Rime test produced real Chinese candidates (including
“你好”) in the actual Quickshell layer-shell overlay and captured the card in
`build/native-caret-protocol/chinese-overlay.png`. Quickshell Bridge selection
committed text to the native text-input client; next/previous paging, injected
PageDown/PageUp, Escape, three commit/retype cycles, caret movement while showing
candidates and text-input disable/re-enable passed. Keys were injected by a
disposable test addon into the focused native fcitx context: the virtual-keyboard
attempt did not reach fcitx's grab. Selection/paging used a temporary QML IPC
handler calling the real Bridge methods, not physical pointer/wheel events.
Neither test driver is installed or part of the supported runtime.

A competing-context regression kept native text-input and a real DBus toolkit
context focused in separate fcitx groups. The previous overlay addon allowed an
empty toolkit context to move native candidates. With panel ownership checks,
background caret/focus events and empty refreshes no longer moved or replaced
the active panel in either direction. Stored toolkit caret restoration on
ownership change, owner caret motion, toolkit Bridge paging/selection, and
returning to native input passed in the same private environment. Toolkit keys
used `ProcessKeyEvent`; native keys used the disposable test addon. This is not
physical keyboard/pointer acceptance. The one-off harness is not installed.

A private nested niri/DBus geometry regression reproduced a nonzero stale
rectangle overwriting the active native context. With the locator protocol
caret guard, injected same-context stale rectangles/scales, repeated updates,
new protocol caret motion, real toplevel title/app-monitor refreshes, and
text-input disable/re-enable passed. Zero-width carets remain valid. This used
a disposable test addon and a text-input client, not physical keyboard/pointer
input; neither is installed. It does not validate estimated tiled origins or
rectangles submitted before locator creation.

An explicit native-popup fallback smoke test also started the QML renderer,
observed candidate-sized Wayland buffers, committed “你好” with injected Space
and accepted PageDown/PageUp/Escape without leaking candidates to the overlay.
This does not establish popup pointer interaction or visual paging correctness.

These checks sent fresh cursor rectangles after the locator role existed.
The already-committed initial rectangle was not replayed in the tested nested
niri; repeated activation also cleared the rectangle in one run until a fresh
update arrived. Placement without a current rectangle remains cached/estimated.
Physical typing/click/wheel acceptance, popup visual interaction, tiled scrolling and
multiple outputs remain unverified before live activation. The paused canvas
probe is not a runtime dependency or supported UI route.

## Optional extracted Fedora sysroot

Prefer system development packages. If unavailable, extract only x86_64/noarch
RPMs (never i686) to a separate sysroot and provide:

```sh
python3 scripts/build.py build --sysroot /path/to/sysroot
```

The helper configures pkg-config's sysroot/prefix and CMake/library paths.
Development `.so` symlinks require the corresponding runtime RPMs as well.
Keep host tools available; this is not a cross-compilation recipe. The sysroot
is a build dependency, never a runtime dependency or Git artifact.

## Updating upstream

Change `native/upstream.json` only alongside patch rebasing, review, build and
runtime testing on that exact system version. Rebuild in a fresh work directory.
Do not bypass the installer version guard to treat a newer version as supported.
Edit added C++ code in `native/`, not only in the generated upstream checkout.
