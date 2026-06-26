# TdxBridge 文档索引

这组文档面向项目使用者、接入方、维护者和智能体协作者。根目录 `README.md` 只保留项目概览和常用入口，细节统一放在这里。

## 使用者

- [用户指南](user-guide.md)：Windows 端安装、启动、停止、卸载和日常维护。
- [接口文档](api.md)：`/doc` 返回的接口总表、请求结构、风险边界和联调顺序。

## 接入方

- [TQ-Local 参考](tq-local.md)：通过通达信本地 HTTP JSON-RPC 服务调用 TQ 接口。
- [TQ-Python 参考](tq-python.md)：通过通达信 Python 插件环境调用 TQ 接口。
- [tdxbridge-agent](../tdxbridge-agent/SKILL.md)：给支持 skill 的智能体使用的接入说明。

## 维护者

- [架构设计](architecture.md)：项目设计目标、运行模型和桥接层边界。
- [开发指南](development.md)：本地开发、验证命令和目录约定。
- [发版说明](release.md)：发布包边界、打包命令和 tag release 流程。
