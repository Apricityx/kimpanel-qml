# Contributing

[中文](CONTRIBUTING.zh-CN.md)

- Preserve native/DBus routing and the no-page-buttons layout.
- Edit shared QML in `shell/`; retain relative symlinks in `popup/`.
- Edit added C++ in `native/`; upstream modifications belong in the patch.
- Run `make check` and `make test-renderer`; test deployment only with an
  isolated prefix. Do not restart the live desktop during routine tests.
- Update both languages when behavior/build/install instructions change.
- Never commit binary addons, virtual environments, cached upstream trees,
  local paths, screenshots/logs or user session configuration.
- Keep the paused experiment separate; clearly distinguish local animation
  tests from compositor screen-continuity guarantees.
- For ports, review exact commits/ABI and runtime behavior; do not only edit
  the version lock or disable checks.
- Choose and audit a project license before public redistribution; see NOTICE.
