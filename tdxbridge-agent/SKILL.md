---
name: tdxbridge-agent
description: 联调、验证和排障 Windows 上的 TdxBridge 通达信桥接服务。Use when Codex needs to connect Hermes、OpenClaw 或其他智能体到 TdxBridge，验证 /health、/capabilities、/stock/search、/rpc/python 等低副作用接口，检查 Bearer Token、白名单、Windows 登录状态、TdxW.exe、127.0.0.1:17709 连通性，或在不触发真实交易的前提下定位桥接问题。
---

# TdxBridge Agent

按“先读取实例信息，再做低副作用验证，最后给出接入结论”的顺序工作。默认把真实交易、板块写入、预警发送和回测数据发送视为禁区，除非用户明确授权。

## 工作流

### 1. 先读取当前实例信息

优先查找项目根目录下由安装器生成的运行时文件：

- `给Hermes和OpenClaw的连接提示.txt`
- `给Hermes和OpenClaw的TdxBridge接入文档.md`

如果这两份文件存在，先读它们，再决定服务地址、Token、允许访问网段和调试顺序。

如果运行时文件不存在，再回退读取这些源码或配置文件：

- `config/bridge.json`
- `README.md`
- `app/main.py`

如果仍然缺少服务地址或 Token，再向用户要最少必要信息，不要直接猜。

### 2. 只按低副作用顺序联调

严格按下面顺序验证，前一步失败时先停下来定位原因，不要直接跳到后面的请求：

0. 确认 Windows 用户已登录桌面，且 `TdxW.exe` 已启动；如果未启动，先启动通达信客户端
1. `GET /health`
2. `GET /doc`
3. `GET /capabilities`
4. `POST /stock/search`
5. `POST /rpc/python` with `get_user_sector`
6. `POST /rpc/python` with `get_stock_list`

如果 `/health` 已通过，优先读取 `/doc`，把它当成当前实例的接口总表入口；需要看动态开关和白名单时，再继续看 `/capabilities`。

如果要把这个实例作为长期可用服务交给用户或其他智能体，还要额外确认：

1. 通达信客户端是否已配置开机自启
2. 安装摘要里是否显示 `通达信客户端开机自启：已开启`
3. 如果显示 `未开启`，先提醒用户补上这一步，再把它视为稳定接入目标

除非实例文档明确说明匿名可访问，否则默认所有请求都带：

```http
Authorization: Bearer <token>
Content-Type: application/json
```

请求体、示例和风险边界优先读取 [references/接口与联调参考.md](references/接口与联调参考.md)。

### 3. 失败时按固定顺序排障

如果请求失败，优先检查：

1. 服务地址是否正确
2. Bearer Token 是否正确
3. Windows 用户是否已登录桌面
4. `TdxW.exe` 是否在运行
5. 通达信客户端开机自启是否已经配置
6. `127.0.0.1:17709` 是否可达
7. `/capabilities` 中 `pythonRuntime.mode` 是否是 `subprocess-per-call`
8. 白名单、Windows 防火墙、来源网段是否拦截
9. `logs/service.stdout.log` 和 `logs/service.stderr.log` 中是否有启动错误

如果项目根目录存在生成后的接入文档，也要优先看其中记录的健康检查结果和安装阶段状态。

### 4. 始终遵守风险边界

在没有用户明确授权前，不要调用这些高风险接口：

- `POST /trade/order`
- `POST /trade/cancel`
- `POST /warn/send`
- `POST /backtest/send`
- `POST /blocks/push`

也不要调用这些底层真实动作：

- `order_stock`
- `cancel_order_stock`
- `send_warn`
- `send_bt_data`

### 5. 输出要让人能直接复盘

每一步至少输出：

1. 请求方法
2. 完整 URL
3. 请求头
4. 请求体
5. HTTP 状态码
6. 返回结果摘要
7. 当前判断

如果低副作用接口全部通过，再补充：

- 推荐 base URL
- 认证头写法
- 建议默认开放的只读工具
- 需要人工确认后再开放的高风险工具

## 参考

只有在你需要具体请求体、接口清单、排障提示时，再读取：

- [references/接口与联调参考.md](references/接口与联调参考.md)
