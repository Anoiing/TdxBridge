# TdxBridge

TdxBridge 是一个面向 Windows 的通达信局域网桥接服务。  
它把本机通达信能力封装成 HTTP 接口，供局域网中的 Hermes、OpenClaw 等 Linux 侧智能体或工具直接调用。

## 适用场景

- 通达信必须运行在 Windows
- 智能体、自动化调试工具或主控服务更适合运行在 Linux
- 希望把通达信能力稳定暴露成一个可验证、可审计、可后台常驻的桥接服务

## 主要能力

- 提供 `/health`、`/capabilities` 等基础探活与能力发现接口
- 同时支持 `TQ-Local` 和 `TQ-Python` 两条通道
- `TQ-Python` 采用 `subprocess-per-call` 隔离模式，单次异常不会拖死整个桥接服务
- 自动探测通达信安装目录，支持手动输入兜底
- 支持局域网来源白名单
- 自动生成 Token
- 自动注册 Windows 计划任务，实现后台常驻
- 自动生成给 Hermes / OpenClaw 等智能体使用的连接提示和接入文档
- 发布包默认包含 `tdxbridge-agent/`，方便用户直接交给支持 skill 的智能体接入

## 面向使用者

### 1. 环境要求

请在 Windows 机器上准备好以下环境：

- 已安装并可正常启动的通达信客户端
- 已登录 Windows 桌面用户
- 已安装 Python，并且 `python` 命令可用
- 当前机器与 Hermes / OpenClaw 所在机器位于可互通的局域网

### 2. 第一次安装

用户进入项目根目录后，只需要关注这些文件：

- `00-右键管理员打开安装-TdxBridge.cmd`
- `01-启动-TdxBridge.cmd`
- `02-停止-TdxBridge.cmd`
- `03-右键管理员打开卸载-TdxBridge.cmd`
- `tdxbridge-agent/`

第一次使用时，请直接双击：

`00-右键管理员打开安装-TdxBridge.cmd`

安装程序会在终端窗口里逐步完成以下动作：

1. 准备运行目录和基础配置
2. 检查 Python 环境
3. 检查全部依赖，并仅安装缺失依赖
4. 自动探测通达信目录
5. 让用户确认允许访问的局域网白名单
6. 写入配置文件
7. 注册 Windows 计划任务
8. 启动后台桥接服务
9. 配置防火墙
10. 执行带进度提示的健康检查
11. 生成连接提示、接入文档与 `/doc` 文档入口，方便用户直接接入智能体

安装过程中需要用到的临时文件，会统一放在：

- `TdxBridge/runtime/install-temp`

安装流程结束后，无论成功还是失败，安装器都会自动清理这个临时目录，避免把安装痕迹散落到用户主目录。

如果健康检查未通过，安装器还会在终端里直接打印最近的启动日志摘要和后台进程状态，方便现场定位问题。

### 3. 通达信目录探测规则

安装程序会按下面顺序探测通达信目录：

1. 已填写在配置中的目录
2. 当前 `TdxBridge` 目录的父级目录
3. 当前 `TdxBridge` 目录的同级目录
4. 各盘符根目录下的 `\new_tdx64` 和 `\tdx64`
5. 各盘符 `Program Files` 和 `Program Files (x86)` 下的常见目录

如果仍未找到，会提示用户手动输入通达信安装目录。

### 4. 白名单填写规则

安装时会要求填写“允许访问网段”。

- 默认值会自动使用当前设备所在局域网段
- 直接回车即可采用默认值
- 支持多个 CIDR，使用英文逗号分隔

示例：

- `192.168.10.0/24`
- `192.168.10.0/24,10.10.0.0/16`

### 5. 安装完成后会得到什么

安装成功后，终端会明确打印：

- 服务地址
- 调用 Token
- 通达信目录
- 允许访问网段
- 当前运行模式
- 健康检查结果
- 计划任务状态
- 防火墙规则状态

安装完成后，项目根目录会生成：

- `给Hermes和OpenClaw的连接提示.txt`
- `给Hermes和OpenClaw的TdxBridge接入文档.md`

同时，发布包本身也会带上：

- `tdxbridge-agent/`

分工如下：

- `连接提示.txt`：极简引导卡，方便用户直接复制给智能体
- `接入文档.md`：完整接入说明，告诉智能体先看 `/doc`、如何联调、哪些接口不能碰
- `tdxbridge-agent/`：适合支持 skill 的智能体直接加载

### 6. 后续维护

日常维护只需要用这些入口：

- `01-启动-TdxBridge.cmd`
- `02-停止-TdxBridge.cmd`
- `03-右键管理员打开卸载-TdxBridge.cmd`

说明：

- 关闭安装窗口不会停止后台服务
- 卸载脚本默认会清理配置、日志和运行时目录
- 如需保留配置或日志，可手动执行 `scripts/Uninstall-TdxBridge.ps1 -KeepConfig` 或 `scripts/Uninstall-TdxBridge.ps1 -KeepLogs`

## 面向维护者

以下内容面向源码仓库维护者。  
如果你拿到的是最终发布给 Windows 用户的压缩包，其中通常不会包含 GitHub 工作流和设计文档等维护材料。

### 1. 本地启动

如果你要直接在源码目录调试：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 18888 --reload
```

### 2. 快速语法检查

```bash
python3 -m compileall app scripts
```

### 3. 正式打包命令

项目根目录已经提供了明确的打包入口：

- Windows 双击：`10-打包发布-TdxBridge.cmd`
- macOS 双击：`10-打包发布-TdxBridge.command`

这两个入口最终都会调用同一个跨平台打包器：

- `scripts/build_release.py`

Windows 下的 `scripts/Build-Release.ps1` 只是一个包装脚本，用来转调 Python 打包器。

也可以手动执行：

```bash
python3 scripts/build_release.py
```

### 4. 打包产物

执行打包后，会生成：

- 发布目录：`dist/TdxBridge`
- 发布压缩包：`dist/TdxBridge-release.zip`

发布包默认包含：

- 4 个用户入口脚本
- `README.md`
- `requirements.txt`
- `app/`
- `scripts/`
- `config/`
- `tdxbridge-agent/`

发布包默认不包含：

- 设计方案文档
- 运行日志
- 运行时文件
- `__pycache__` 和 `*.pyc`

### 5. GitHub Tag 自动发布 Release

仓库已经配置好 GitHub Actions：

- 工作流文件：`.github/workflows/release-on-tag.yml`

触发规则：

- 当你推送形如 `v*` 的 tag 时，自动触发

工作流会自动完成：

1. 检出代码
2. 安装 Python 3.13
3. 执行 `python -m compileall app scripts`
4. 执行 `python3 scripts/build_release.py`
5. 生成 `dist/TdxBridge-release.zip`
6. 自动创建 GitHub Release
7. 把发布压缩包挂到该 Release

### 6. 发版方式

本地确认代码无误后，执行：

```bash
git tag v0.1.0
git push origin v0.1.0
```

推送成功后，GitHub 会自动生成对应 Release。

## 发布包说明

发布包默认面向 Windows 终端用户，只包含：

- 安装入口
- 启动入口
- 停止入口
- 卸载入口
- `tdxbridge-agent/`
- 运行所需脚本与应用代码

开发者联调用的调试入口和调试脚本默认不进入发布包；但用户接入智能体需要的 skill、连接提示和接入文档会保留。

## 源码仓库结构

```text
TdxBridge/
  00-右键管理员打开安装-TdxBridge.cmd
  01-启动-TdxBridge.cmd
  02-停止-TdxBridge.cmd
  03-右键管理员打开卸载-TdxBridge.cmd
  10-打包发布-TdxBridge.cmd
  10-打包发布-TdxBridge.command
  README.md
  requirements.txt
  app/
  config/
  scripts/
```
