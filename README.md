# kimpanel-qml

English | [简体中文](README.zh-CN.md)

A QML candidate frontend for **fcitx5 on niri/Wayland**, keeping system input
method core libraries and engines.

## Features

- Native Wayland classicui popups and GTK/Qt DBus Quickshell overlays, sharing visuals.
- Opaque vertical candidate-text reels with rapid retargeting, highlighting,
  pointer selection and wheel/keyboard paging.
- No paging buttons or reserved button space in the candidate layout.
- Spring-based overlay position, size and reveal; typing during fade-out resumes
  from the current pose and velocity.
- Optional DankMaterialShell colors/radius; built-in theme without DMS.
- Separate offscreen renderer, stale-command protection and Cairo fallback on failure.

**Not implemented: arbitrary global movement animation for native popups.** The
expanded-canvas experiment is paused and not part of the default runtime.
Overlay geometry can be approximate for tiled windows while scrolling.

## Getting started

The native addons target pinned fcitx **5.1.21**; this is not a standalone engine:

```sh
make renderer-env
make prepare
make build
make test
make test-renderer
# Only when system fcitx5 matches the lock; no automatic activation/restart
make install
```

Read the dependencies, version constraints and complete instructions first:

- [Build](docs/build.en.md)
- [Install, activate and roll back](docs/install.en.md)
- [Architecture, layout, maintenance and limits](docs/architecture.en.md)
- [Licensing and provenance](docs/third-party.md)
- [Paused native canvas experiment](experiments/canvas-probe/README.md)

### Local migration status

Sources now live in `~/workspace/kimpanel-qml`. The former
`~/.local/share/kimpanel-qml` is a compatibility symlink, so existing startup
paths remain valid. `addon/`, `popup-venv/` and `local/` contain preserved local
artifacts/archives, not Git sources. The installer refuses to overwrite a
symlink pointing to the source checkout.

At migration the host runs fcitx **5.1.23**, while the patch/old addons target
**5.1.21**. This does not establish cross-version compatibility. Installation
rejects mismatches; porting, rebuilding and validation are separate work.
This reorganization does not change IM environment settings, upgrade addons or
restart fcitx/the compositor.

Migration checks: Python/packaging tests, offscreen renderer tests and repeated
source preparation pass. A new native build on this host stops at missing
extra-cmake-modules (ECM); it has not been compiled or deployed in this migration.

## Controls

```sh
./kimpanel-qmlctl status
./kimpanel-qmlctl start
./kimpanel-qmlctl restart
./kimpanel-qmlctl logs
./kimpanel-qmlctl demo
```

The controller manages bridge/overlay only; the native renderer belongs to
fcitx. Demo displays an overlay; unit/offscreen tests do not operate real input.
A blanket license for original project files is pending the owner's selection;
a local Git repository is not itself authorization for public redistribution.
