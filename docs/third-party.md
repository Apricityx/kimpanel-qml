# Licensing and provenance / 许可与来源

- `native/patches/fcitx5-integration.patch` modifies fcitx5 5.1.21 at
  `1319952f284eae17a36cba9e800843ca61a163c1`. Existing upstream copyright
  and license notices remain applicable; consult individual upstream files.
- `native/qmlpopup.cpp` and `.h` retain their existing `LGPL-2.1-or-later`
  SPDX identifiers. This reorganization does not relicense them.
- Yoga, Qt/PySide6, Quickshell, fcitx5 and distro libraries retain their own
  licenses. Upstream sources and compiled dependencies are not vendored here.
- The owner has not yet selected a blanket license for original Python/QML,
  scripts and documentation. Do not assume redistribution rights. Select a
  project license and audit dependency notices before public release.

本次整理不改变已有许可。上游补丁、带 SPDX 的 C++ 和依赖分别保留原许可；未代替
所有者为原创 Python/QML、脚本、文档指定统一开源许可证。公开分发前需选择项目
许可并核查依赖声明。上游源码、二进制和虚拟环境不纳入 Git。
