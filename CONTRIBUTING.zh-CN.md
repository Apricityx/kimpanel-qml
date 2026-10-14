# 贡献说明

[English](CONTRIBUTING.md)

- 保持原生 / DBus 路由以及没有分页按钮的布局。
- 共用 QML 修改于 `shell/`，保留 `popup/` 的相对软链接。
- 新增 C++ 修改于 `native/`，对上游已有文件的修改纳入补丁。
- 执行 `make check` 和 `make test-renderer`，只在隔离 prefix 测试部署。
  常规测试不重启正在使用的桌面。
- 行为、构建、安装说明变化时同步维护中英文。
- 不提交 addon 二进制、venv、上游缓存、本地绝对路径、截图 / 日志或用户会话配置。
- 暂停的实验保持独立，明确区分局部动画测试与 compositor 屏幕连续性保证。
- 移植需审查 commit、ABI 和实际运行，不能只改版本锁或绕过检查。
- 公开分发前选定并审查项目许可证，见 NOTICE。
