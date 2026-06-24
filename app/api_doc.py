DEFAULT_API_DOC = """# TdxBridge 接口文档

## 1. 用途

- `GET /doc` 会返回这份 Markdown 文档。
- 这份文档用于告诉开发者和智能体：当前 TdxBridge 暴露了哪些 HTTP 接口、它们分别映射到哪些底层方法、哪些接口有真实副作用。
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

## 5. HTTP 接口总表

### 5.1 基础发现接口

- `GET /health`
- `GET /doc`
- `GET /capabilities`

### 5.2 通用桥接接口

- `POST /rpc/auto`
- `POST /rpc/local`
- `POST /rpc/python`

### 5.3 股票类接口

- `POST /stock/search` -> `get_match_stkinfo`
- `POST /stock/info` -> `get_stock_info`

### 5.4 行情类接口

- `POST /market/data` -> `get_market_data`
- `POST /market/snapshot` -> `get_market_snapshot`
- `POST /market/moreInfo` -> `get_more_info`

### 5.5 公式类接口

- `POST /formula/list` -> `formula_get_all`
- `POST /formula/info` -> `formula_get_info`
- `POST /formula/run` -> `formula_zb` / `formula_xg` / `formula_exp`
- `POST /formula/runBatch` -> `formula_process_mul_zb` / `formula_process_mul_xg` / `formula_process_mul_exp`

### 5.6 交易查询接口

- `POST /trade/queryAsset` -> `query_stock_asset`
- `POST /trade/queryPositions` -> `query_stock_positions`
- `POST /trade/queryOrders` -> `query_stock_orders`

### 5.7 高风险写接口

- `POST /trade/order` -> `order_stock`
- `POST /trade/cancel` -> `cancel_order_stock`
- `POST /blocks/push` -> `send_user_block` / `create_sector`
- `POST /warn/send` -> `send_warn`
- `POST /backtest/send` -> `send_bt_data`

## 6. 风控约束

以下开关关闭时，对应写操作会被桥接层直接拒绝：

- `enable_trading`
- `enable_block_push`
- `enable_warn_send`
- `enable_backtest_send`

## 7. 调试建议

- 想看接口总表、参数入口和风险边界：先看 `GET /doc`
- 想看当前实例是否真的支持某方法、白名单是否限制、写开关是否开启：再看 `GET /capabilities`
- 想看服务、通达信、本地 RPC 是否活着：看 `GET /health`
"""
