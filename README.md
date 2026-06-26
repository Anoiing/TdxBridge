# TdxBridge

TdxBridge 是一个运行在 Windows 上的通达信局域网桥接服务。它把本机通达信能力封装成 HTTP 接口，供局域网中的 Hermes、OpenClaw 或其他自动化工具调用。

这个项目的目标不是把通达信重新包装成另一个客户端，而是提供一条可安装、可探活、可审计、可后台常驻的桥接通道。

## 主要能力

- Windows 一键安装、启动、停止和卸载入口
- `GET /health`、`GET /doc`、`GET /capabilities` 三类基础发现接口
- 同时支持 `TQ-Local` 和 `TQ-Python` 两条通达信调用通道
- `TQ-Python` 使用 `subprocess-per-call` 隔离模式，单次异常不会拖垮桥接服务
- 自动探测通达信安装目录，支持手动输入兜底
- 支持局域网来源白名单和 Bearer Token 认证
- 自动注册 Windows 计划任务，实现登录后后台常驻
- 发布包包含 `tdxbridge-agent/`，便于支持 skill 的智能体直接接入

## 快速开始

面向 Windows 使用者，建议先到 [GitHub Release tag 页面](https://github.com/Anoiing/TdxBridge/releases/tag) 下载已经打包好的 `TdxBridge-release.zip`。解压后，在项目根目录右键管理员运行：

```text
00-右键管理员打开安装-TdxBridge.cmd
```

安装器会逐步完成环境检查、通达信目录探测、依赖安装、配置生成、计划任务注册、服务启动和健康检查。

注意：发布包中的 `.cmd` 入口都建议右键选择“以管理员身份运行”。安装、启动、停止和卸载流程可能会读写服务配置、计划任务、防火墙或后台进程；如果直接普通双击，可能出现权限不足、启动失败、停止失败或卸载不完整。

日常维护入口也请右键管理员运行：

```text
01-启动-TdxBridge.cmd
02-停止-TdxBridge.cmd
03-右键管理员打开卸载-TdxBridge.cmd
```

完整安装说明见 [docs/user-guide.md](docs/user-guide.md)。

## 接口入口

服务启动后，推荐按下面顺序联调：

1. `GET /health`
2. `GET /doc`
3. `GET /capabilities`
4. 低副作用业务接口，例如 `POST /stock/search`

`/doc` 是当前实例的接口总表；`/capabilities` 是当前实例的动态能力快照。完整接口说明见 [docs/api.md](docs/api.md)。

## 面向智能体接入

发布包默认带有：

- `tdxbridge-agent/`

安装成功后还会生成：

- `给Hermes和OpenClaw的连接提示.txt`
- `给Hermes和OpenClaw的TdxBridge接入文档.md`

支持 skill 的智能体可以加载 `tdxbridge-agent/`；不支持 skill 的工具可以直接读取安装器生成的连接提示和接入文档。

## 本地开发

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 18888 --reload
```

快速语法检查：

```bash
python3 -m compileall app scripts
```

更多维护说明见 [docs/development.md](docs/development.md) 和 [docs/release.md](docs/release.md)。

## 源码仓库结构

```text
TdxBridge/
  app/                  FastAPI 服务与桥接逻辑
  config/               配置模板
  docs/                 项目文档
  runtime/              运行时占位目录，实际运行文件不入库
  scripts/              安装、启动、停止、卸载、打包脚本
  tdxbridge-agent/      给智能体使用的 skill 与参考资料
  00-*.cmd              Windows 用户入口
  10-*.cmd/.command     本地打包入口，发布包中默认不包含
```

生成产物、日志、运行时文件和本地配置默认不提交到仓库。

## 文档

- [用户指南](docs/user-guide.md)
- [接口文档](docs/api.md)
- [架构设计](docs/architecture.md)
- [开发指南](docs/development.md)
- [发版说明](docs/release.md)
- [TQ-Local 参考](docs/tq-local.md)
- [TQ-Python 参考](docs/tq-python.md)

## 贡献

欢迎通过 issue 或 pull request 反馈问题、补充文档或改进桥接能力。提交前请至少运行：

```bash
python3 -m compileall app scripts
```
