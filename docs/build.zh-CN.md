# 构建方法

[English](build.en.md) | [简体中文](build.zh-CN.md)

## 依赖

需要 Linux / Wayland、Python 3.10+、Git、CMake 3.16+、C++17 编译器、Make、
binutils（`readelf`）及匹配的系统 fcitx5 运行和开发依赖。

运行依赖：fcitx5 及输入引擎、niri、Quickshell（`qs`，含 Qt Quick Effects 和
Wayland / Io 模块）、Python PyGObject 和 dbus-python、中文字体（默认 Noto Sans
CJK SC）。DankMaterialShell 可选。
XWayland satellite 定位还使用系统 `libxcb` 运行库只读查询聚焦窗口几何，
无需额外 Python X11 包。
`make renderer-env` 同时执行 `make emoji-font`，下载固定版本、项目私有的 Noto
Color Emoji CBDT/CBLC 字体（约 11 MB），并校验 SHA-256。OFL 许可和来源记录在
`assets/fonts/`；字体二进制由 Git 忽略。这样可以避开部分 Qt 版本无法绘制系统
COLRv1 字体导致的 emoji 空白，不修改 fontconfig 或安装系统字体。复用已有
renderer 环境时，请在测试或安装前单独执行 `make emoji-font`。

原生构建依赖包括 libuv、DBus、UUID、XCB / xcb-imdkit、xkbcommon / xkbfile、cairo、pango、
gdk-pixbuf、librsvg、GLib / GIO、nlohmann-json、Wayland / scanner、extra-cmake-modules、
iso-codes、xkeyboard-config、wayland-protocols >=1.46 及
plasma-wayland-protocols >=1.20。systemd / libcap 是上游可选依赖。

Fedora 开发包示例（请确认对应发行版的包名和可用性）：

```sh
sudo dnf install gcc-c++ cmake make git binutils extra-cmake-modules \
  gettext-devel zlib-devel libuv-devel dbus-devel libuuid-devel \
  libxcb-devel xcb-util-devel xcb-util-wm-devel xcb-util-keysyms-devel xcb-imdkit-devel expat-devel \
  libxkbcommon-devel libxkbcommon-x11-devel libxkbfile-devel cairo-devel pango-devel \
  gdk-pixbuf2-devel librsvg2-devel glib2-devel json-devel wayland-devel \
  wayland-protocols-devel plasma-wayland-protocols-devel iso-codes-devel \
  xkeyboard-config-devel systemd-devel libcap-devel
sudo dnf install python3-gobject python3-dbus google-noto-sans-cjk-fonts
```

这里只安装依赖，不安装候选前端。除 5.1.23 外的 fcitx5 版本需要先移植补丁，
在新发行版安装开发依赖不会自动完成移植。

## 可复现的源码准备与构建

```sh
make prepare
make build JOBS=6
```

`scripts/build.py` 拉取 fcitx5 5.1.23，校验精确 commit，应用
`native/patches/fcitx5-integration.patch`，复制 `native/qmlpopup.{cpp,h}` 和 `native/overlaycursor.{cpp,h}`，
并初始化、验证 Yoga。受管理源码可重复准备；遇到冲突或其他改动会拒绝操作，
不会 reset 或丢弃修改。

输出目录：

```text
build/fcitx5/              打补丁的上游源码（Git 忽略）
build/fcitx5-build/        CMake 构建目录（Git 忽略）
build/addons/             libclassicui.so、libkimpanel.so、libdbusfrontend.so
                         build-info.json
```

只收集三个 addon。**不要在上游构建树执行 `cmake --install`**，不能用构建的
fcitx 核心库覆盖系统库。收集时会拒绝带 RPATH / RUNPATH 的 addon。

可用 `--cmake-arg=-DKEY=VALUE` 传入额外 CMake 设置：

```sh
python3 scripts/build.py build --jobs 6 --cmake-arg=-DENABLE_X11=ON
```

## Python 绘制环境与测试

```sh
make renderer-env
make check
make test-renderer
make test-overlay
```

PySide6 6.11.2 安装于 `popup-venv/`；GLib / DBus 使用系统 Python。
迁移的历史 venv 可通过旧兼容路径继续使用，新环境应直接创建在最终目录，
不要手动搬动。离屏测试不会占用输入法 seat 或改变桌面焦点。
测试产物位于 `build/test-output/`。

### 原生 overlay 的验证边界

2026-10-14，5.1.23 集成通过解包 sysroot 构建，并使用系统核心库/依赖检查。
干净和重复源码准备、63 项 Python/打包测试、renderer/overlay 离屏测试、系统
符号解析，以及真实 addon 的临时 prefix 安装均通过。只在临时目录安装三个
addon，没有启用当前桌面运行环境。

另在独立 nested niri、私有 DBus 和临时 XDG 配置中，由系统 fcitx 加载新
classicui/kimpanel addon。原生 text-input 光标变化经 `SetRelativeSpotRectV2`
到达 bridge，在 1.5 倍输出缩放下数值保持不变。停用/重新启用 text-input 时
定位 surface 能销毁/重建，客户端断开后也完成清理。

进一步的私有 Rime 测试在实际 Quickshell layer-shell overlay 中显示了“你好”等
真实中文候选，并保存卡片截图 `build/native-caret-protocol/chinese-overlay.png`。
通过 Quickshell Bridge 选择后，文字提交到原生 text-input 客户端；前后翻页、
注入 PageDown/PageUp、Esc 取消、三轮提交/重输、候选显示期间光标移动，以及
停用/重新启用 text-input 均通过。按键由一次性测试 addon 注入聚焦的原生 fcitx
上下文：虚拟键盘尝试没有进入 fcitx 的 grab。选择/翻页通过临时 QML IPC handler
调用真实 Bridge 方法，并非物理点击/滚轮事件。两个测试驱动均不安装，也不是
受支持运行环境的一部分。

另一次双上下文回归让原生 text-input 与真实 DBus 工具包上下文在不同 fcitx
焦点组中同时聚焦。旧 overlay addon 会让没有候选的工具包上下文移动原生
候选。加入面板归属检查后，两个方向的后台光标/聚焦事件和空刷新都没有移动
或替换当前面板；归属切换时恢复保存的工具包矩形、当前上下文光标移动、
工具包 Bridge 翻页/选择及恢复原生输入均在同一私有环境中通过。工具包按键
通过 `ProcessKeyEvent` 发送，原生按键仍用一次性测试 addon 注入；这不是
物理键盘/指针验收。一次性测试脚本不安装到运行环境。

私有 nested niri/DBus 几何回归复现了非零旧矩形覆盖当前原生上下文的问题。
加入 locator 协议光标保护后，注入同上下文旧矩形/缩放、反复更新、新协议
光标移动、真实顶层窗口标题/应用识别刷新，以及 text-input 停用/重启用均
通过；零宽度光标仍然有效。使用一次性测试 addon 和 text-input 客户端，
不是物理键盘/指针输入，两者均不安装。此测试不验证估算的平铺原点，也不
验证 locator 创建前提交的矩形。

显式 native-popup 回退的冒烟测试也启动了 QML renderer，观察到候选窗口尺寸的
Wayland buffer，通过注入空格提交“你好”，并接受 PageDown/PageUp/Esc，候选没有
泄漏到 overlay。此结果不证明 popup 的指针交互或翻页视觉效果正确。

检查在定位 role 创建后发送新光标矩形。测试的 nested niri 没有重放初次聚焦前
已经提交的矩形；一轮测试中重复激活也清空了矩形，直到新的更新到达才恢复。
缺少当前矩形时，位置仍使用缓存/估算。真实键盘、点击/滚轮、popup 视觉交互、平铺
滚动和多输出尚未验收，启用前仍需验证。暂停的扩画布原型不是运行依赖或受
支持的 UI 路由。

## 可选 Fedora 解包 sysroot

优先使用系统开发包。无法安装时，可以将 x86_64 / noarch RPM（不要混入 i686）
解包到独立 sysroot：

```sh
python3 scripts/build.py build --sysroot /path/to/sysroot
```

脚本会设置 pkg-config 的 sysroot / prefix 和 CMake / 库路径。开发包的 `.so`
软链接还需要相应运行包；宿主构建工具也必须可用，这不是交叉编译方案。
sysroot 只用于构建，不应成为运行依赖或 Git 内容。

## 更新上游版本

修改 `native/upstream.json` 时，必须同时重整补丁、审查、构建并在精确匹配的系统
版本上做运行测试。使用新的构建目录，不要绕过安装版本检查宣称新版受支持。
新增 C++ 应修改 `native/`，不能只修改生成的上游源码目录。
