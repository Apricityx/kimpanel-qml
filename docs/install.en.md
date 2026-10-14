# Installation and rollback

[中文](install.zh-CN.md) · [Home](../README.md)

## Standalone user installation

Build matching addons first. The installer checks the upstream metadata,
system fcitx5 version, ELF libraries, RPATH/RUNPATH and `ldd` dependencies.
The current 5.1.21 integration cannot be deployed automatically on 5.1.23.

```sh
python3 scripts/install.py --dry-run --prefix "$HOME/.local"
python3 scripts/install.py --prefix "$HOME/.local"
```

The base prefix produces:

- `PREFIX/share/kimpanel-qml`: runtime code and the three addons.
- `PREFIX/share/kimpanel-qml-venv`: stable-path PySide6 environment, linked
  into the runtime as `popup-venv`.
- `PREFIX/bin/fcitx5-user-local` and `PREFIX/bin/kimpanel-qmlctl`: launchers.

Without `--prefix`, use `$XDG_DATA_HOME/kimpanel-qml` (default
`~/.local/share/kimpanel-qml`) and `~/.local/bin`. An existing environment can
be reused with `--renderer-env /absolute/path/to/venv`; it must provide the
pinned PySide6. Keep that environment available for every runtime using it.
`--dry-run` prints paths only; it does not validate binary compatibility.

Source trees, symlink installation targets and unmanaged existing directories
are refused. Updated managed runtimes and existing launchers are backed up
with timestamped `.backup-*` names. Installation does not restart anything,
enable autostart or edit niri/environment settings. A failed staging rename
restores the previous runtime; launcher backups are reported separately.

## Activation (explicit)

Select kimpanel as fcitx's UI (or use `fcitx5 --ui kimpanel` with the launcher's
environment), and keep classicui/Wayland addons enabled. Another kimpanel panel
must not compete for the same DBus service. Input engines remain configured
through the existing fcitx tools; this frontend does not configure them.

Review `packaging/niri-startup.kdl` and merge its overlay startup command into
your existing niri configuration if desired. The generated
`fcitx5-user-local.desktop.example` in the installed runtime may be copied to
`~/.config/autostart/fcitx5-user-local.desktop` after backing up an existing
entry. Do not start fcitx twice through both niri and autostart.

For the current session, use the installed fcitx launcher only when ready to
replace the existing fcitx process (`--replace`), then start the overlay:

```sh
fcitx5-user-local
# In another terminal, or through session startup:
kimpanel-qmlctl start
```

The fcitx launcher stays in the foreground. QML renderer changes require an
explicit fcitx restart; `kimpanel-qmlctl restart` affects only bridge/overlay.

Do not globally force GTK/QT modules if native Wayland input is desired.
`packaging/toolkit-app.sh /path/to/app` provides an optional per-application
DBus route (for example for QQ). Restart that application to apply environment
changes. The installer does not replace your current IM environment settings.

## Migration machine

`~/.local/share/kimpanel-qml` links to `~/workspace/kimpanel-qml` to preserve
existing niri startup, fcitx wrapper and venv entry-point paths. Legacy addons,
venv and local archives are ignored by Git. No live addon was replaced and no
session process was restarted during reorganization.

For a future standalone deployment, first port to the matching system fcitx
version, install to a separate prefix and test. Do not remove the compatibility
link while old launchers/venv entry points still use it. Only retire it after
explicitly updating your own session paths; this is not done automatically.

## Rollback and removal

1. Stop the overlay with its original controller. Switch fcitx explicitly to
   system addons if needed:
   ```sh
   env -u FCITX_ADDON_DIRS -u FCITX_QML_POPUP_RENDERER \
       -u FCITX_KIMPANEL_WAYLAND_POPUP -u FCITX_KIMPANEL_TOOLKIT_UI \
       /usr/bin/fcitx5 -D --replace
   ```
2. Rename the current installed runtime aside; restore the printed runtime
   `.backup-*` directory to its original path. Restore launcher `.backup-*`
   files separately. Leave the stable renderer environment in place.
3. For removal, undo only session/autostart changes you enabled yourself and
   archive/remove only that managed installation and its launchers. Keep a
   renderer environment if another runtime uses it. Do not delete the source
   checkout, follow the compatibility symlink recursively, or remove system
   fcitx libraries/engines.
