# 用户指南

TdxBridge 面向 Windows 通达信机器安装。安装完成后，局域网内的 Hermes、OpenClaw 或其他 HTTP 客户端可以通过 TdxBridge 调用通达信能力。

## 环境要求

- 已安装并可正常启动的通达信客户端
- 已登录 Windows 桌面用户
- 已安装 Python，并且 `python` 命令可用
- 通达信机器与调用方位于可互通的局域网

## 第一次安装

建议先到 [GitHub Release tag 页面](https://github.com/Anoiing/TdxBridge/releases/tag) 下载已经打包好的 `TdxBridge-release.zip`，不要直接把源码仓库当作用户包使用。

解压发布包后，在项目根目录右键管理员运行：

```text
00-右键管理员打开安装-TdxBridge.cmd
```

安装程序会逐步完成：

1. 准备运行目录和基础配置
2. 检查 Python 环境
3. 仅安装缺失依赖
4. 自动探测通达信目录
5. 检查并启动 `TdxW.exe`
6. 让用户确认允许访问的局域网白名单
7. 写入配置文件和访问 Token
8. 注册 Windows 计划任务
9. 启动后台桥接服务
10. 配置防火墙
11. 执行健康检查
12. 生成智能体连接提示和接入文档

安装过程中使用的临时文件会放在 `runtime/install-temp`，安装结束后自动清理。

## 运行权限

发布包中的 `.cmd` 入口都建议右键选择“以管理员身份运行”，包括安装、启动、停止和卸载。

这些脚本可能需要读写服务配置、注册或删除 Windows 计划任务、配置防火墙、启动后台服务、停止后台进程或清理运行目录。直接普通双击时，Windows 可能因为权限不足导致脚本报错、服务没有启动、服务无法停止或卸载清理不完整。

## 通达信目录探测规则

安装程序会按下面顺序探测通达信目录：

1. 已填写在配置中的目录
2. 当前 `TdxBridge` 目录的父级目录
3. 当前 `TdxBridge` 目录的同级目录
4. 各盘符根目录下的 `new_tdx64` 和 `tdx64`
5. 各盘符 `Program Files` 和 `Program Files (x86)` 下的常见目录

如果仍未找到，会提示用户手动输入通达信安装目录。

## 白名单填写规则

安装时会要求填写允许访问网段。

- 默认值会自动使用当前设备所在局域网段
- 直接回车即可采用默认值
- 支持多个 CIDR，使用英文逗号分隔

示例：

```text
192.168.10.0/24
192.168.10.0/24,10.10.0.0/16
```

## 安装完成后

安装成功后，终端会打印：

- 服务地址
- 调用 Token
- 通达信目录
- 允许访问网段
- 当前运行模式
- 健康检查结果
- 计划任务状态
- 防火墙规则状态

项目根目录会生成：

- `给Hermes和OpenClaw的连接提示.txt`
- `给Hermes和OpenClaw的TdxBridge接入文档.md`

服务端接口文档统一通过 `GET /doc` 获取。

## 日常维护

请在项目根目录右键管理员运行：

```text
01-启动-TdxBridge.cmd
02-停止-TdxBridge.cmd
03-右键管理员打开卸载-TdxBridge.cmd
```

说明：

- 关闭安装窗口不会停止后台服务
- 卸载脚本默认清理配置、日志和运行时目录
- 如需保留配置或日志，可手动执行 `scripts/Uninstall-TdxBridge.ps1 -KeepConfig` 或 `scripts/Uninstall-TdxBridge.ps1 -KeepLogs`
