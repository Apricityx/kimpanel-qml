# 安装与回退

[English](install.en.md) · [首页](../README.zh-CN.md)

## 独立用户级安装

先构建匹配版本的 addon。安装器检查上游元数据、系统 fcitx5 版本、ELF、
RPATH / RUNPATH 和 `ldd` 依赖。当前 5.1.21 集成不能自动部署到 5.1.23。

```sh
python3 scripts/install.py --dry-run --prefix "$HOME/.local"
python3 scripts/install.py --prefix "$HOME/.local"
```

安装基目录下会生成：

- `PREFIX/share/kimpanel-qml`：运行代码和三个 addon。
- `PREFIX/share/kimpanel-qml-venv`：路径稳定的 PySide6 环境，在 runtime 内以
  `popup-venv` 软链接引用。
- `PREFIX/bin/fcitx5-user-local`、`PREFIX/bin/kimpanel-qmlctl`：启动器。

省略 `--prefix` 时，使用 `$XDG_DATA_HOME/kimpanel-qml`（默认
`~/.local/share/kimpanel-qml`）及 `~/.local/bin`。可通过
`--renderer-env /absolute/path/to/venv` 复用提供固定 PySide6 的环境；所有引用它
的运行环境都需要此目录持续存在。`--dry-run` 只打印路径，不校验二进制兼容性。

安装器拒绝源码目录、软链接目标和非受管已有目录。更新时，旧 runtime 和已有
启动器以带时间戳的 `.backup-*` 名称备份。安装不会重启进程、启用自启动，
或修改 niri / 环境设置。临时目录重命名失败时恢复旧 runtime；启动器备份另行报告。

## 明确启用

选择 kimpanel 作为 fcitx UI（或在启动器环境中使用 `fcitx5 --ui kimpanel`），
保留 classicui / Wayland addon。不要让其他 kimpanel 面板竞争同一 DBus 服务。
输入引擎仍通过现有 fcitx 工具配置，前端不替代这些设置。

如需自启动，审查 `packaging/niri-startup.kdl` 后手动合并 overlay 启动命令。
安装目录的 `fcitx5-user-local.desktop.example` 可在备份已有条目后复制到
`~/.config/autostart/fcitx5-user-local.desktop`。不要通过 niri 和 autostart
重复启动 fcitx。

准备好替换现有 fcitx 时，才运行安装的启动器（含 `--replace`），再启动 overlay：

```sh
fcitx5-user-local
# 另一个终端，或通过会话自启动：
kimpanel-qmlctl start
```

fcitx 启动器以前台方式运行。原生 renderer QML 改动需明确重启 fcitx；
`kimpanel-qmlctl restart` 只影响 bridge / overlay。

希望使用原生 Wayland 时，不要全局强制 GTK / QT 模块。
`packaging/toolkit-app.sh /path/to/app` 提供可选的单应用 DBus 路由，例如 QQ。
应用需重启才能继承新环境；安装器不覆盖现有输入法环境设置。

## 本次迁移机器

`~/.local/share/kimpanel-qml` 指向 `~/workspace/kimpanel-qml`，保留现有 niri
自启动、fcitx 包装和 venv 入口路径。旧 addon、venv、本地归档被 Git 忽略。
整理期间没有替换正在使用的 addon，也没有重启会话进程。

以后独立部署前，先移植到匹配的系统 fcitx 版本，再安装到另一个 prefix 并测试。
旧启动器和 venv 仍引用兼容链接时，不要删除它。只有明确更新会话路径后再退役
该链接；安装器不会自动执行此操作。

## 回退与移除

1. 用原控制器停止 overlay。必要时明确切回系统 addon：
   ```sh
   env -u FCITX_ADDON_DIRS -u FCITX_QML_POPUP_RENDERER \
       -u FCITX_KIMPANEL_WAYLAND_POPUP -u FCITX_KIMPANEL_TOOLKIT_UI \
       /usr/bin/fcitx5 -D --replace
   ```
2. 将当前安装 runtime 改名保留，把安装器报告的 `.backup-*` 目录恢复到原路径；
   启动器备份单独恢复。保持稳定路径的 renderer 环境不变。
3. 移除时只撤销自己启用的会话和自启动改动，只归档 / 删除受管安装及其启动器。
   其他 runtime 还引用的 venv 应保留。不要删除源码目录、递归穿过兼容软链接，
   或删除系统 fcitx 核心库和输入引擎。
