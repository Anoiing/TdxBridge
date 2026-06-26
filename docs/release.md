# 发版说明

TdxBridge 的发布包面向 Windows 终端用户。发布包应保留用户安装和智能体接入所需材料，排除源码仓库中的调试工具、日志和运行时产物。

## 本地打包

项目根目录提供两个打包入口：

```text
10-打包发布-TdxBridge.cmd
10-打包发布-TdxBridge.command
```

它们最终都会调用：

```bash
python3 scripts/build_release.py
```

打包后生成：

```text
dist/TdxBridge
dist/TdxBridge-release.zip
```

## 发布包包含

- 4 个 Windows 用户入口脚本
- `README.md`
- `requirements.txt`
- `app/`
- `scripts/` 中的安装、启动、停止、卸载脚本
- `config/bridge.example.json`
- `docs/` 中的项目文档、用户文档和接口参考
- `tdxbridge-agent/`

## 发布包不包含

- GitHub Actions 配置
- 全接口调试入口和调试脚本
- `dist/`
- `logs/`
- `runtime/` 中的运行时文件
- `__pycache__`、`*.pyc`
- 本地真实配置 `config/bridge.json`、`config/bridge.local.json`

## GitHub Release

仓库配置了 `.github/workflows/release-on-tag.yml`。推送形如 `v*` 的 tag 会触发自动发布：

```bash
git tag v0.1.0
git push origin v0.1.0
```

工作流会执行：

1. 检出代码
2. 安装 Python 3.13
3. 执行 `python -m compileall app scripts`
4. 执行 `python scripts/build_release.py`
5. 上传 `dist/TdxBridge-release.zip` 到 GitHub Release
