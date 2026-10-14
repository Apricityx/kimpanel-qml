# Licensing and provenance / 许可与来源

This reorganization preserves existing license notices; it does not relicense
upstream code or choose a blanket license on the owner's behalf.

- `native/patches/fcitx5-integration.patch` modifies fcitx5 5.1.21, revision
  `1319952f284eae17a36cba9e800843ca61a163c1`. Upstream per-file license notices
  remain applicable (primarily LGPL-2.1-or-later; consult upstream LICENSES).
- `native/qmlpopup.cpp` and `.h` retain their LGPL-2.1-or-later SPDX identifiers.
- Yoga is downloaded at the locked revision and retains its upstream license.
- Qt/PySide6, Quickshell, fcitx and distro dependencies have their own licenses.
  Their source trees/binaries/venvs are not distributed through this Git history.
- A project-wide license for original Python/QML/tools/docs is **not yet
  selected**. Do not assume a public redistribution grant. Before publishing,
  the owner should choose a license and audit third-party notices.

本次整理不重新授权上游代码，也不代替所有者选择统一项目许可。补丁及带 SPDX
的 C++ 文件保留其许可；依赖各遵循原许可。原创 Python / QML / 工具 / 文档的
统一许可证尚未选定，公开分发前需由所有者选择并核查第三方声明。
