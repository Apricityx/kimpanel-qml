# kimpanel-qml

[English](README.md) | 简体中文

面向 **fcitx5 + niri/Wayland** 的 QML 候选前端，保留系统输入法核心和引擎。

## 功能

- 原生 Wayland 走 classicui popup；GTK/Qt DBus 走 Quickshell overlay，共用视觉组件。
- 候选文字实心上下滚动，快速输入重定向保留速度；保留高亮、鼠标选择、滚轮/键盘翻页。
- 不显示分页按钮，也不保留按钮布局占位。
- Overlay 位置、尺寸、显隐采用弹簧，淡出期间再次输入无缝接续。
- 可选 DankMaterialShell 配色/圆角集成；无 DMS 时使用内置主题。
- 独立离屏 renderer、过期命令保护、renderer 断开时 Cairo 回退。

**不是已完成的功能：原生 popup 的任意全局移动动画。** 扩画布实验已暂停，
不属于默认运行路径。平铺窗口滚动期间 overlay 坐标可能为估算值。

## 开始使用

构建固定的 fcitx **5.1.21** 修改版 addon，不构建独立输入法引擎：

```sh
make renderer-env
make prepare
make build
make test
make test-renderer
# 仅在系统 fcitx5 与版本锁一致时安装；不自动启动/重启
make install
```

先阅读依赖、适用版本和完整步骤：

- [构建说明](docs/build.zh-CN.md)
- [安装、启动、回退](docs/install.zh-CN.md)
- [架构、目录、维护规则与限制](docs/architecture.zh-CN.md)
- [许可与来源](docs/third-party.md)
- [暂停的原生移动实验](experiments/canvas-probe/README.zh-CN.md)

### 当前迁移状态

源码已移动到 `~/workspace/kimpanel-qml`。旧的
`~/.local/share/kimpanel-qml` 是兼容软链接；现有启动配置继续使用它。
`addon/`、`popup-venv/`、`local/` 是保留的本机运行产物/归档，不提交到 Git。
安装工具拒绝覆盖指向源码的链接。

迁移时本机 fcitx5 已是 **5.1.23**，补丁/旧 addon 仍基于 **5.1.21**；
这不代表已经验证跨版本兼容。安装工具拒绝版本不匹配，需另行移植、构建和验证。
本次整理不改变输入法环境，不升级 addon，也不重启 compositor/fcitx。

迁移验证：Python / 打包测试、离屏 renderer 测试、重复源码准备通过。本机重新
构建原生 addon 在缺少 extra-cmake-modules（ECM）处停止，本次未编译或部署新版。

## 控制

```sh
./kimpanel-qmlctl status
./kimpanel-qmlctl start
./kimpanel-qmlctl restart
./kimpanel-qmlctl logs
./kimpanel-qmlctl demo
```

控制器只管理 bridge/overlay；popup renderer 随 fcitx 启动。演示会显示 overlay，
单元测试和离屏测试不操作真实输入。自定义项目原始文件的统一许可证待所有者选择；
不要把本地 Git 仓库视为已授权公开发布的开源项目。
