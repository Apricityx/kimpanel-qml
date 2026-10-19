# Licensing and provenance / 许可与来源

- `native/patches/fcitx5-integration.patch` modifies fcitx5 5.1.23 at
  `27cca6e0239938b2d53937061d0980c087856b22`. Existing upstream copyright
  and license notices remain applicable; consult individual upstream files.
- `native/qmlpopup.cpp` and `.h` retain their existing `LGPL-2.1-or-later`
  SPDX identifiers. This reorganization does not relicense them.
- `native/overlaycursor.cpp` and `.h` use `LGPL-2.1-or-later` SPDX identifiers.
- Yoga, Qt/PySide6, Quickshell, fcitx5 and distro libraries retain their own
  licenses. Upstream sources and compiled dependencies are not vendored here.
- The private Noto Color Emoji font (v2.051, CBDT/CBLC) is downloaded separately,
  SHA-256 pinned by `assets/fonts/upstream.json`, and deployed with
  `assets/fonts/LICENSE` (SIL Open Font License 1.1). The font binary is not
  committed. It does not change the license of this project's original code.
- The owner has not yet selected a blanket license for original Python/QML,
  scripts and documentation. Do not assume redistribution rights. Select a
  project license and audit dependency notices before public release.

本次整理不改变已有许可。上游补丁、带 SPDX 的 C++ 和依赖分别保留原许可；未代替
所有者为原创 Python/QML、脚本、文档指定统一开源许可证。公开分发前需选择项目
许可并核查依赖声明。上游源码、二进制和虚拟环境不纳入 Git。
私有 Noto Color Emoji 字体（v2.051，CBDT/CBLC）单独下载，以
`assets/fonts/upstream.json` 固定 SHA-256，并随 `assets/fonts/LICENSE`
（SIL Open Font License 1.1）一起部署；字体二进制不提交，不改变项目原创代码许可。
