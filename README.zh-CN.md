# kimpanel-qml

[English](README.md) | 简体中文

面向 **fcitx5 + niri/Wayland** 的 Quickshell QML 候选前端。保留系统输入法核心
与引擎，只替换界面。

## 功能

- 原生 Wayland、工具包 DBus、XWayland 与 XIM 候选共用同一个稳定的 overlay。
- 透明的原生光标 surface；可见的原生 popup 仅作为 `KIMPANEL_NATIVE_UI=popup` 回退。
- Wayland 光标顶部对齐、xwayland-satellite 光标坐标转换，平铺窗口原点为估算值。
- 上下滚动候选列表，弹簧动画，支持鼠标、滚轮和键盘翻页，不显示分页按钮。
- 项目私有的固定版本彩色 emoji 字体；可选 DankMaterialShell 配色与圆角。

## 构建

原生 addon 固定针对 fcitx5 **5.1.23**，不是独立输入法引擎。

```sh
make emoji-font renderer-env   # PySide6 环境 + 固定版本 emoji 字体
make prepare build
make test test-renderer test-overlay
make install                   # 仅当系统 fcitx5 与版本锁一致
```

安装不会激活、重启或修改会话设置。依赖、版本与回退：
[构建](docs/build.zh-CN.md)、[安装](docs/install.zh-CN.md)、
[架构](docs/architecture.zh-CN.md)、[许可与来源](docs/third-party.md)。

## 控制

```sh
./kimpanel-qmlctl status | start | restart | logs | demo
```

## 限制

- 原生 popup 回退的任意全局移动动画尚未实现，画布实验保持暂停。
- 平铺窗口的 overlay 坐标是估算值，滚动时可能滞后。
- 项目尚未选定统一许可证，见 [NOTICE.md](NOTICE.md)。
