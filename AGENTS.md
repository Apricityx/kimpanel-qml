# Project maintenance

- Read `README.md` and `docs/architecture.en.md` before changing routing.
- Keep English and Chinese documentation aligned.
- Native Wayland contexts use classicui popup surfaces; DBus toolkit contexts
  use the Quickshell overlay. Do not silently switch either route.
- Global native-popup movement animation remains unsolved. The canvas probe is
  paused research, not a supported runtime feature.
- Never install fcitx core libraries from the upstream build. Only classicui,
  kimpanel and dbusfrontend addons are deployed.
- `native/qmlpopup.{cpp,h}` are the canonical added C++ sources;
  `native/patches/fcitx5-integration.patch` contains changes to upstream files.
- Runtime paths must not depend on a developer's home directory or temporary
  sysroot. Do not commit venvs, addons, build trees, logs or local configuration.
- Run `make test` for Python changes and `make test-renderer` for shared QML.
  Installation tests must use an isolated prefix, never the live desktop.
- Do not restart the user's input method/compositor or edit session settings
  as part of normal tests. Installation does not activate the runtime.
