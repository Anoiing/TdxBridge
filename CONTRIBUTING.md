# 贡献指南

欢迎通过 issue 或 pull request 改进 TdxBridge。

## 开发流程

1. 从一个明确的问题或需求开始。
2. 保持改动聚焦，避免把功能、重构和文档大范围混在一个提交里。
3. 修改接口行为时，同步更新 `docs/api.md` 和 `tdxbridge-agent/references/接口与联调参考.md`。
4. 修改发布边界时，同步检查 `scripts/build_release.py` 和 `docs/release.md`。

## 提交前检查

```bash
python3 -m compileall app scripts
```

如果改动影响发布包，继续运行：

```bash
python3 scripts/build_release.py
```

如果改动影响 Windows 安装、通达信启动、计划任务或防火墙配置，请在真实 Windows 通达信机器上验证。
