# 架构与维护

[English](architecture.en.md) · [首页](../README.zh-CN.md)

## 两条路由

- 原生 `wayland_v2`：修改后的 classicui 持有 Wayland popup 和 buffer。
  独立 PySide6 进程离屏绘制 Qt Quick；Seqpacket JSON 传递状态和命令，两个
  各 32 MiB 的共享内存槽传递预乘 ARGB 像素。epoch 校验拒绝过期选择。
  renderer 失败后，该 fcitx 进程回退到 classicui Cairo。
- toolkit DBus：kimpanel → GLib bridge → Unix socket → Quickshell layer-shell
  overlay。覆盖输出的 surface 尺寸稳定，只有卡片接收输入。
- `shell/` 保存共用布局、文字和弹簧组件；`popup/` 用相对软链接复用。
  两个宿主各自使用 Bridge 和 Theme 单例。

路由开关为 `FCITX_KIMPANEL_WAYLAND_POPUP=1` 和 `FCITX_KIMPANEL_TOOLKIT_UI=1`，
不会伪装桌面环境或全局设置 GTK / QT 输入模块。只选择三个本地 addon，
不替换系统核心库和输入引擎。

## 动画和限制

位置、显隐弹簧在重定向和淡出打断时保留速度。候选文字实心垂直滚动。
分页按钮组件保留为源码，但没有放入候选布局。

原生全局移动仍由 compositor 控制，没有动画。离屏定位测试只能证明 QML
局部连续性。niri IPC 不提供精确平铺窗口屏幕原点，DBus 相对坐标在滚动期间
采用估算。软件 Qt Quick 可能不显示阴影。DMS 配色可选，缺失时使用内置
配色和圆角。多输出和真实原生输入仍需交互验证。

`experiments/` 中的扩画布原型已暂停：它能在补偿后保持原位并绘制弹簧移动，
但旧 surface 可能先于替换像素到达而被重定位；扩大边界也会改变边缘放置。
实验不会安装，不能宣称为已支持的动画功能。

## 开发

`native/qmlpopup.{cpp,h}` 是新增代码的唯一源文件；对上游文件的修改放在
`native/patches/fcitx5-integration.patch`，版本由 `native/upstream.json` 锁定。
不要只改生成的上游副本，不要安装上游核心库。保留开发者编辑的 checkout，
移植时使用新目录。升级需一并审查两个 revision、补丁、测试和文档。

```sh
make check             # Python 测试、shell 语法，不操作桌面
make test-renderer     # 离屏 IPC 像素、文字滚动、定位测试
```

自动输入可能绕过 IM。手动验收应覆盖原生和工具包输入、选择提交、翻页、快速
提交重输、淡出打断、换行、边缘、多输出以及 renderer 故障回退。
不要把 compositor 重启作为常规测试步骤。
