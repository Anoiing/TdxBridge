# TdxBridge 接口文档

## 1. 用途

- `GET /doc` 会直接返回这份 Markdown 文档。
- 这份文档用于告诉用户、Hermes、OpenClaw 和其他智能体：当前 TdxBridge 暴露了哪些 HTTP 接口、它们分别映射到哪些底层方法、哪些接口有真实副作用。
- 这份文档是静态总表；`GET /capabilities` 是当前实例的动态能力快照。排障时优先同时看这两者。

## 2. 认证与访问约束

- `GET /health` 可能允许匿名，是否匿名取决于实例配置。
- `GET /doc` 默认需要认证。
- `GET /capabilities` 默认需要认证。
- 绝大多数 `POST` 接口默认都需要认证。

默认请求头：

```http
Authorization: Bearer <token>
Content-Type: application/json
```

如果来源 IP 不在允许网段内，服务会直接返回 `403`。

## 3. 推荐调用顺序

建议按下面顺序联调，不要跳步：

1. `GET /health`
2. `GET /doc`
3. `GET /capabilities`
4. `POST /stock/search`
5. `POST /rpc/python` with `get_user_sector`
6. `POST /rpc/python` with `get_stock_list`

## 4. 统一响应结构

大多数业务接口返回统一结构：

```json
{
  "ok": true,
  "backend": "local",
  "method": "get_stock_info",
  "data": {},
  "error": null,
  "traceId": "string",
  "meta": {}
}
```

字段说明：

- `ok`：业务是否成功
- `backend`：命中的后端，通常为 `local`、`python` 或 `auto`
- `method`：底层实际调用的方法名
- `data`：接口返回结果
- `error`：失败时的错误消息
- `traceId`：请求跟踪 ID
- `meta`：附加调试信息，例如参数适配结果、类别、写操作类型

## 5. HTTP 接口总表

### 5.1 基础发现接口

#### `GET /health`

- 用途：检查服务是否存活，以及 Windows、通达信、本地 RPC 是否正常
- 风险：无
- 认证：可能允许匿名，取决于配置

#### `GET /doc`

- 用途：获取这份完整接口文档
- 风险：无
- 认证：默认需要 Bearer Token

#### `GET /capabilities`

- 用途：获取当前实例的动态能力信息
- 返回重点：`supportedMethods`、`requestShapes`、`riskControl`、`network.allowedCidrs`、`warnings`
- 风险：无
- 认证：默认需要 Bearer Token

### 5.2 通用桥接接口

#### `POST /rpc/auto`

- 用途：按 method 自动选择后端
- 请求体：

```json
{
  "method": "get_stock_info",
  "params": {
    "code": "600000.SH"
  }
}
```

#### `POST /rpc/local`

- 用途：显式走 TQ-Local 后端
- 适合：行情、公式、交易查询类方法

#### `POST /rpc/python`

- 用途：显式走 TQ-Python 子进程后端
- 适合：`get_stock_list`、板块推送、预警、回测回灌等方法

### 5.3 股票类接口

#### `POST /stock/search`

- 底层方法：`get_match_stkinfo`
- 后端：`local`
- 用途：按股票名称、简称、关键字模糊搜索
- 顶层字段：`keyword`、`query`、`text`
- 示例：

```json
{"keyword":"寒武纪"}
```

#### `POST /stock/info`

- 底层方法：`get_stock_info`
- 后端：`local`
- 用途：获取单只股票的基础信息
- 顶层字段：`code`、`market`
- 示例：

```json
{"code":"600000.SH"}
```

### 5.4 行情类接口

#### `POST /market/data`

- 底层方法：`get_market_data`
- 后端：`local`
- 用途：获取行情序列或 K 线数据
- 顶层字段：`code`、`market`、`period`、`count`、`adjust`、`start`、`end`

#### `POST /market/snapshot`

- 底层方法：`get_market_snapshot`
- 后端：`local`
- 用途：获取单只股票快照
- 顶层字段：`code`、`market`

#### `POST /market/moreInfo`

- 底层方法：`get_more_info`
- 后端：`local`
- 用途：透传更多行情扩展信息查询
- 请求体：`{"params": {...}}`

### 5.5 公式类接口

#### `POST /formula/list`

- 底层方法：`formula_get_all`
- 后端：`local`
- 用途：列出公式

#### `POST /formula/info`

- 底层方法：`formula_get_info`
- 后端：`local`
- 用途：读取指定公式信息
- 顶层字段：`name`、`formulaName`

#### `POST /formula/run`

- 底层方法：`formula_zb`、`formula_xg`、`formula_exp`
- 后端：`local`
- 用途：执行单次公式
- 特殊行为：如果同时提供 `code` / `period` / `start` / `end` / `count` 等股票上下文字段，服务会先自动执行 `formula_set_data_info`
- 顶层字段重点：
  - `method`
  - `params.formula_name`
  - `params.formula_arg`
  - `params.code`
  - `params.period`

#### `POST /formula/runBatch`

- 底层方法：`formula_process_mul_zb`、`formula_process_mul_xg`、`formula_process_mul_exp`
- 后端：`local`
- 用途：批量执行公式
- 顶层字段重点：
  - `method`
  - `params.name`
  - `params.codes`
  - `params.period`
  - `params.start`
  - `params.end`
  - `params.count`
  - `params.adjust`

### 5.6 交易查询接口

#### `POST /trade/queryAsset`

- 底层方法：`query_stock_asset`
- 后端：`local`
- 用途：查询资产
- 风险：低，但属于交易域

#### `POST /trade/queryPositions`

- 底层方法：`query_stock_positions`
- 后端：`local`
- 用途：查询持仓
- 风险：低，但属于交易域

#### `POST /trade/queryOrders`

- 底层方法：`query_stock_orders`
- 后端：`local`
- 用途：查询委托
- 风险：低，但属于交易域

### 5.7 高风险写接口

#### `POST /trade/order`

- 底层方法：`order_stock`
- 后端：`local`
- 写操作类型：`trading`
- 风险：真实下单
- 顶层字段：`code`、`market`、`price`、`amount`、`side`

#### `POST /trade/cancel`

- 底层方法：`cancel_order_stock`
- 后端：`local`
- 写操作类型：`trading`
- 风险：真实撤单
- 顶层字段：`orderId`、`code`

#### `POST /blocks/push`

- 底层方法：
  - `send_user_block` when `action=push`
  - `create_sector` when `action=create_sector`
- 后端：`python`
- 写操作类型：`block_push`
- 风险：写入或推送板块
- 顶层字段：`action`、`codes`、`name`

#### `POST /warn/send`

- 底层方法：`send_warn`
- 后端：`python`
- 写操作类型：`warn_send`
- 风险：真实发送预警
- 顶层字段：`title`、`content`

#### `POST /backtest/send`

- 底层方法：`send_bt_data`
- 后端：`python`
- 写操作类型：`backtest_send`
- 风险：真实回灌回测数据
- 顶层字段：`payload`

## 6. 支持的底层方法总表

### 6.1 只读或低副作用方法

- `get_match_stkinfo` -> `local` -> `stock`
- `get_stock_info` -> `local` -> `stock`
- `get_stock_list` -> `python` -> `stock`
- `get_market_data` -> `local` -> `market`
- `get_market_snapshot` -> `local` -> `market`
- `get_more_info` -> `local` -> `market`
- `formula_get_all` -> `local` -> `formula`
- `formula_get_info` -> `local` -> `formula`
- `formula_zb` -> `local` -> `formula`
- `formula_xg` -> `local` -> `formula`
- `formula_exp` -> `local` -> `formula`
- `formula_process_mul_zb` -> `local` -> `formula`
- `formula_process_mul_xg` -> `local` -> `formula`
- `formula_process_mul_exp` -> `local` -> `formula`
- `query_stock_asset` -> `local` -> `trade`
- `query_stock_positions` -> `local` -> `trade`
- `query_stock_orders` -> `local` -> `trade`
- `price_df` -> `python` -> `market`

### 6.2 高风险方法

- `order_stock` -> `local` -> `trade` -> `writeAction=trading`
- `cancel_order_stock` -> `local` -> `trade` -> `writeAction=trading`
- `send_user_block` -> `python` -> `block` -> `writeAction=block_push`
- `create_sector` -> `python` -> `block` -> `writeAction=block_push`
- `send_warn` -> `python` -> `warn` -> `writeAction=warn_send`
- `send_bt_data` -> `python` -> `backtest` -> `writeAction=backtest_send`

## 7. 风控约束

以下开关关闭时，对应写操作会被桥接层直接拒绝：

- `enable_trading`
- `enable_block_push`
- `enable_warn_send`
- `enable_backtest_send`

如果被拒绝，响应中的 `error` 会明确提示需要开启哪个开关。

## 8. 常用示例

### 8.1 健康检查

```bash
curl -X GET "http://<host>:18888/health" \
  -H "Authorization: Bearer <token>"
```

### 8.2 获取文档

```bash
curl -X GET "http://<host>:18888/doc" \
  -H "Authorization: Bearer <token>"
```

### 8.3 获取能力快照

```bash
curl -X GET "http://<host>:18888/capabilities" \
  -H "Authorization: Bearer <token>"
```

### 8.4 搜索股票

```bash
curl -X POST "http://<host>:18888/stock/search" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d "{\"keyword\":\"寒武纪\"}"
```

## 9. 调试建议

- 想看接口总表、参数入口和风险边界：先看 `GET /doc`
- 想看当前实例是否真的支持某方法、白名单是否限制、写开关是否开启：再看 `GET /capabilities`
- 想看服务、通达信、本地 RPC 是否活着：看 `GET /health`

## 10. 禁区提醒

在没有用户明确授权前，不要调用以下真实写接口：

- `POST /trade/order`
- `POST /trade/cancel`
- `POST /warn/send`
- `POST /backtest/send`
- `POST /blocks/push`
