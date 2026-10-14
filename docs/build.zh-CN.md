# 构建方法

[English](build.en.md) | [简体中文](build.zh-CN.md)

## 依赖

需要 Linux / Wayland、Python 3.10+、Git、CMake 3.16+、C++17 编译器、Make、
binutils（`readelf`）及匹配的系统 fcitx5 运行和开发依赖。

运行依赖：fcitx5 及输入引擎、niri、Quickshell（`qs`，含 Qt Quick Effects 和
Wayland / Io 模块）、Python PyGObject 和 dbus-python、中文字体（默认 Noto Sans
CJK SC）。DankMaterialShell 可选。

原生构建依赖包括 libuv、DBus、UUID、XCB / xcb-imdkit、xkbcommon、cairo、pango、
gdk-pixbuf、GLib / GIO、nlohmann-json、Wayland / scanner、extra-cmake-modules、
iso-codes、xkeyboard-config、wayland-protocols >=1.46 及
plasma-wayland-protocols >=1.20。systemd / libcap 是上游可选依赖。

Fedora 开发包示例（请确认对应发行版的包名和可用性）：

```sh
sudo dnf install gcc-c++ cmake make git binutils extra-cmake-modules \
  gettext-devel zlib-devel libuv-devel dbus-devel libuuid-devel \
  libxcb-devel xcb-util-devel xcb-util-wm-devel xcb-util-keysyms-devel xcb-imdkit-devel expat-devel \
  libxkbcommon-devel libxkbcommon-x11-devel cairo-devel pango-devel \
  gdk-pixbuf2-devel glib2-devel json-devel wayland-devel \
  wayland-protocols-devel plasma-wayland-protocols-devel iso-codes-devel \
  xkeyboard-config-devel systemd-devel libcap-devel
sudo dnf install python3-gobject python3-dbus google-noto-sans-cjk-fonts
```

这里只安装依赖，不安装候选前端。除 5.1.21 外的 fcitx5 版本需要先移植补丁，
在新发行版安装开发依赖不会自动完成移植。

## 可复现的源码准备与构建

```sh
make prepare
make build JOBS=6
```

`scripts/build.py` 拉取 fcitx5 5.1.21，校验精确 commit，应用
`native/patches/fcitx5-integration.patch`，复制 `native/qmlpopup.{cpp,h}`，
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
```

PySide6 6.11.2 安装于 `popup-venv/`；GLib / DBus 使用系统 Python。
迁移的历史 venv 可通过旧兼容路径继续使用，新环境应直接创建在最终目录，
不要手动搬动。离屏测试不会占用输入法 seat 或改变桌面焦点。
测试产物位于 `build/test-output/`。

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
