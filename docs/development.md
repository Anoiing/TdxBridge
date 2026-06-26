# 开发指南

这份文档面向 TdxBridge 维护者和贡献者。

## 本地环境

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

本地启动服务：

```bash
uvicorn app.main:app --host 127.0.0.1 --port 18888 --reload
```

快速语法检查：

```bash
python3 -m compileall app scripts
```

## 目录约定

- `app/`：FastAPI 服务、请求适配、风控、健康检查和通达信桥接逻辑
- `scripts/`：Windows 安装维护脚本、本地调试脚本和发布打包器
- `config/`：配置模板；本地真实配置不提交
- `docs/`：项目文档
- `tdxbridge-agent/`：给智能体使用的 skill、提示和参考资料
- `runtime/`：运行时文件占位目录，实际 `.pid`、`.lock` 等文件不提交
- `logs/`：运行日志目录，不提交
- `dist/`：发布产物目录，不提交

## 接口文档来源

`GET /doc` 默认读取 [docs/api.md](api.md)。如果发布包缺少该文件，服务会回退到 `app/api_doc.py` 中的内置简版文档。

修改接口、请求参数、风险开关或推荐联调顺序时，需要同步更新：

1. `docs/api.md`
2. `app/api_doc.py` 的 fallback 文档
3. `tdxbridge-agent/references/接口与联调参考.md`

## 脚本边界

- 安装期机器配置放在 `scripts/Install-TdxBridge.ps1`
- 启停服务分别放在 `scripts/Start-TdxBridge.ps1` 和 `scripts/Stop-TdxBridge.ps1`
- 卸载逻辑放在 `scripts/Uninstall-TdxBridge.ps1`
- 全接口调试放在 `scripts/Debug-AllEndpoints.ps1`，不进入发布包
- 发布包构建逻辑放在 `scripts/build_release.py`

## 提交前检查

至少运行：

```bash
python3 -m compileall app scripts
python3 scripts/build_release.py
```

如果修改了 Windows 安装脚本，还需要在真实 Windows 通达信机器上验证安装、健康检查和 `/doc` 访问。
