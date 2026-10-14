# Building

[English](build.en.md) | [简体中文](build.zh-CN.md)

## Prerequisites

Linux/Wayland, Python 3.10+, Git, CMake 3.16+, a C++17 compiler, Make, binutils
(`readelf`), and matching fcitx5 system runtime/development dependencies.

Runtime: fcitx5 and your input engines, niri, Quickshell (`qs`, with Qt Quick
Effects and Wayland/Io modules), Python PyGObject and dbus-python, a Chinese font
(default: Noto Sans CJK SC). DankMaterialShell is optional.

Native build dependencies include libuv, DBus, UUID, XCB/xcb-imdkit, xkbcommon,
cairo, pango, gdk-pixbuf, GLib/GIO, nlohmann-json, Wayland/scanner, extra-cmake-modules,
iso-codes, xkeyboard-config, wayland-protocols >=1.46 and
plasma-wayland-protocols >=1.20. Systemd/libcap are optional upstream dependencies.

Example Fedora development packages (review availability for your release):

```sh
sudo dnf install gcc-c++ cmake make git binutils extra-cmake-modules \
  gettext-devel zlib-devel libuv-devel dbus-devel libuuid-devel \
  libxcb-devel xcb-util-devel xcb-util-wm-devel xcb-util-keysyms-devel xcb-imdkit-devel expat-devel \
  libxkbcommon-devel libxkbcommon-x11-devel cairo-devel pango-devel \
  gdk-pixbuf2-devel glib2-devel json-devel wayland-devel \
  wayland-protocols-devel plasma-wayland-protocols-devel iso-codes-devel \
  xkeyboard-config-devel systemd-devel libcap-devel
sudo dnf install python3-gobject python3-dbus google-noto-sans-cjk-fonts
```

This installs development dependencies only. It does not install this frontend.
The pinned patch must be ported before deployment with fcitx5 versions other
than 5.1.21; installing dependencies on a newer distro does not perform that port.

## Reproducible source preparation

```sh
make prepare
make build JOBS=6
```

`scripts/build.py` fetches fcitx5 tag 5.1.21, verifies its exact commit, applies
`native/patches/fcitx5-integration.patch`, copies `native/qmlpopup.{cpp,h}`,
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
```

PySide6 6.11.2 is installed in `popup-venv/`; GLib/dbus modules use system Python.
The moved historical venv remains usable through the old compatibility path;
new environments should be created at their final path, not relocated manually.
The offscreen checks do not claim an input-method seat or change desktop focus.
Artifacts are in `build/test-output/`.

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
