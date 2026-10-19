# 架构与维护

[English](architecture.en.md) · [首页](../README.zh-CN.md)

## 稳定 overlay 与显式 popup 回退

- 原生 `wayland_v2`：classicui 持有透明、无输入区域的 1×1 popup，仅接收
  `text_input_rectangle`。应用 surface 局部逻辑像素以 scale 1.0 保存并通过
  `SetRelativeSpotRectV2` 转发。kimpanel 将可见候选交给 overlay，而非定位
  surface。失焦先销毁 role，再销毁 surface。
  locator 为当前上下文保存最后收到的协议光标矩形，并在 kimpanel 转发光标/
  面板更新前恢复，防止 fcitx 虚拟上下文的焦点刷新将其覆盖为父上下文的旧
  光标。新协议矩形替换缓存，失焦/销毁后清除。这不提供全局窗口原点，也不
  重放 locator 创建前提交的矩形。
- 原生、toolkit DBus / XWayland fcitx4/XIM：kimpanel → GLib bridge → Unix socket → Quickshell layer-shell
  overlay。覆盖输出的 surface 尺寸稳定，只有卡片接收输入。
  `Socket` 直接解析以换行分隔的状态，重连后收到最新状态的重放。原子替换的
  `panel-state.json` 仅用于诊断，不作为 UI 传输：`tail -F` 可能漏掉短暂输入。
  对 xwayland-satellite 窗口，bridge 先减去聚焦 X 顶层窗口的虚拟根坐标，
  再除以输出缩放并加上 niri 窗口原点。WM_CLASS 必须匹配 niri app ID；
  只读取 X 几何和类名，不读取文字。浮动窗口原点精确，平铺仍为估算；
  未显式设置 `KIMPANEL_BAR_SIZE` 时，此路由通过满高列估算上下栏占位。
  原生和工具包相对光标矩形使用聚焦窗口原点；平铺/滚动时仍为估算。
  已知 Wayland 窗口的相对矩形携带 `spot.caretTop=true`：候选框左上角
  对齐光标矩形左上角，不再额外加光标高度或间距。XWayland 保留原有的
  光标下方放置方式。屏幕边缘限制和向上避让仍生效；没有光标矩形的
  估算回退点保留原有放置方式。
- 原生和工具包上下文可能在不同的 fcitx 焦点组中同时保持聚焦。聚焦上下文
  持有非空面板时，其他上下文的光标/聚焦事件和空面板刷新不能移动或替换它。
  新的非空面板可以接管；面板更新同时发送该上下文保存的光标矩形，
  无需等待先前被抑制的光标事件再次发生。
- 显式回退（`KIMPANEL_NATIVE_UI=popup`）：classicui 持有可见原生 popup。
  独立 PySide6 进程离屏绘制 Qt Quick；Seqpacket JSON 传递状态和命令，两个
  各 32 MiB 的共享内存槽传递预乘 ARGB。epoch 校验拒绝过期选择；renderer
  失败后，该 fcitx 进程回退到 Cairo。工具包上下文仍走 overlay。
- `shell/` 保存共用布局、文字和弹簧组件；`popup/` 用相对软链接复用。
  两个宿主各自使用 Bridge 和 Theme 单例。
  两个 Theme 均注册私有的 CBDT/CBLC Noto emoji 字体以显示彩色候选，
  不修改系统字体配置。

启动器默认 `KIMPANEL_NATIVE_UI=overlay`，设置 `FCITX_KIMPANEL_NATIVE_OVERLAY=1`；
`popup` 将其设置为 0，并恢复 renderer 启动器。
`FCITX_KIMPANEL_WAYLAND_POPUP=1` 保留旧原生路由，
`FCITX_KIMPANEL_TOOLKIT_UI=1` 保留工具包 overlay。
不会伪装桌面环境或全局设置 GTK / QT 输入模块。只选择三个本地 addon，
不替换系统核心库和输入引擎。

## 动画和限制

位置、显隐弹簧在重定向和淡出打断时保留速度。候选文字实心垂直滚动。
分页按钮组件保留为源码，但没有放入候选布局。

原生候选在稳定 overlay 内移动，不移动 compositor 管理的 popup。
显式 popup 回退的全局移动仍没有动画。离屏定位测试只能证明 QML 连续性。
niri IPC 不提供精确平铺窗口屏幕原点，相对坐标在滚动期间采用估算。
光标矩形不提供全局窗口原点；缺少矩形时使用同窗口缓存或估算点。
nested niri 检查没有重放定位 surface 创建前提交的矩形；重复激活也可能清空
矩形，直到应用再次更新才恢复。
子 surface/客户端装饰也可能使 surface 局部光标坐标与顶层窗口几何不同。
软件 Qt Quick 可能不显示阴影。DMS 配色可选，缺失时使用内置
配色和圆角。多输出和真实原生输入仍需交互验证。

`experiments/` 中的扩画布原型已暂停：它能在补偿后保持原位并绘制弹簧移动，
但旧 surface 可能先于替换像素到达而被重定位；扩大边界也会改变边缘放置。
实验不会安装，不能宣称为已支持的动画功能。

## 开发

`native/qmlpopup.{cpp,h}` 和 `native/overlaycursor.{cpp,h}` 是新增代码的源文件；对上游文件的修改放在
`native/patches/fcitx5-integration.patch`，版本由 `native/upstream.json` 锁定。
不要只改生成的上游副本，不要安装上游核心库。保留开发者编辑的 checkout，
移植时使用新目录。升级需一并审查两个 revision、补丁、测试和文档。

```sh
make check             # Python 测试、shell 语法，不操作桌面
make test-renderer     # 离屏 IPC 像素、文字滚动、定位测试
make test-overlay      # Quickshell 离屏 socket/重连测试，不创建桌面 surface
```

自动输入可能绕过 IM。手动验收应覆盖原生和工具包输入、选择提交、翻页、快速
提交重输、淡出打断、换行、边缘、多输出以及 renderer 故障回退。
不要把 compositor 重启作为常规测试步骤。
