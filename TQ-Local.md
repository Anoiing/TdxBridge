---
name: 通达信TQ-Local
description: TdxQuant是由通达信软件提供的证券行情分析和量化投研平台。本Skill使用本地通达信客户端的HTTP服务直接调用tqcenter接口, 不再生成Python文件。
---

# Tdx Quant Local Skill

> 本文档改写自 tqcenter.py 接口说明, 当前调用方式为向本机 HTTP 服务发送 JSON-RPC 请求
> 地址: `http://127.0.0.1:17709/`

TdxQuant 是由深圳市财富趋势科技股份有限公司研发的专业量化投研平台。本 Skill 的执行方式已经从“生成 Python 文件并运行 tqcenter.py”改为“按 tqcenter 接口名构造 JSON-RPC 请求并发送到 HTTP 服务”。

---

## 执行前强制检查流程（必须按顺序完整执行，不可跳过任何一步）

### 第零步：检查当前操作系统是否为 Windows

该 SKILL 仅支持 Windows 系统。在执行任何操作前，必须先确认当前运行环境是否为 Windows。

**检查方法：**

```python
import platform
os_name = platform.system()
print(os_name)  # Windows 系统输出 "Windows"
```

- 如果 `platform.system()` 返回 `"Windows"` → 继续执行后续步骤
- 如果返回其他系统（如 `"Linux"` / `"Darwin"`）→ **立即终止**，提示用户：

> 该 SKILL 仅支持 Windows 系统。当前系统为 `{os_name}`，请切换到 Windows 环境后重试。

### 第一步：检查通达信是否已安装，需要通达信比较新的支持TQ策略的版本

使用 Python + `winreg` 依次检查以下三个注册表键，**只要找到至少一个即视为已安装**：

```
HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信金融终端64
HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信专业版
HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信金融终端(量化模拟)
HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信金融终端(测试)
```

检查代码示例（使用 Python + winreg，因为 PowerShell 在 Git Bash 环境下输出可能被截断）：

```python
import winreg
paths = [
    r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信金融终端64',
    r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信专业版',
    r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信金融终端(量化模拟)',
    r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信金融终端(测试)',
]
found = False
for p in paths:
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, p)
        # 读取 DisplayName 和 InstallLocation
        disp = winreg.QueryValueEx(key, 'DisplayName')[0]
        loc = winreg.QueryValueEx(key, 'InstallLocation')[0] if ... else ''
        print(f'[已安装] {disp} -> {loc}')
        winreg.CloseKey(key)
        found = True
        break
    except FileNotFoundError:
        continue
if not found:
    print('NOT_INSTALLED')
```

### 第二步：如未安装，自动下载并提示用户安装

如果第一步三个注册表键都不存在：

1. 使用 Python `urllib.request.urlretrieve` 从 `https://data.tdx.com.cn/level2/new_tdx64.exe` 下载到当前工作区目录
2. 如果下载失败，请告知用户这个下载地址，让用户自己下载
3. 下载完成后告知用户文件路径，**提示用户手动运行安装程序**
4. 安装完成前**不得**继续执行后续步骤

> 注意：不要用 `curl` 或浏览器下载（Git Bash 路径兼容性问题），用 Python 下载；目标路径放在当前 workspace 下，避免 `Downloads` 目录权限问题。

### 第三步：检查 TdxW.exe 是否运行

通达信已安装后，检查进程列表中是否有 `TdxW.exe`：

```bash
tasklist 2>/dev/null | grep -i "TdxW"
```

- 如果 `TdxW.exe` 未运行 → 提示用户先启动通达信客户端并登录
- 如果 `TdxW.exe` 已在运行 → 进入第四步

### 第四步：验证 HTTP 服务连通性

向 `http://127.0.0.1:17709/` 发送测试请求确认 HTTP 服务可用：

```bash
curl -s --connect-timeout 3 -X POST "http://127.0.0.1:17709/" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"id":1,"method":"get_match_stkinfo","params":{"key_word":"茅台"}}'
```

- 如果返回正常 JSON-RPC 响应 → 可以开始执行用户请求
- 如果连接失败 → 提示用户确认通达信客户端已完全启动并登录后进入到主界面

---

## 核心规则

1. **执行前必须完成上述五步强制检查流程（第零步系统检查 + 第一到第四步），任意一步未通过则不得继续。**
2. 不要生成 Python 策略文件执行 tqcenter 指令。
3. 不要导入 `tqcenter.py`, 不要调用 `tq.initialize()` 或 `tq.close()`。
4. 所有接口都通过 HTTP POST 发送到 `http://127.0.0.1:17709/`。
5. JSON-RPC 请求格式固定为:

```json
{
  "id": 1,
  "method": "接口名",
  "params": {
    "参数名": "参数值"
  }
}
```

6. `method` 对应 tqcenter 原接口名, 例如 `get_market_data`, `get_stock_list`, `stock_account`。
7. `params` 对应原 tqcenter 接口入参, 不需要额外包一层 `tq.`。
8. 请求体必须是标准 JSON: 字段和值之间使用 `:`, 字符串使用双引号, 不要使用 Python 字典的单引号或 `=`。
9. 返回结果是 JSON-RPC 响应, 正常结果在 `result` 字段中, 错误信息在 `error` 字段中。
10. 交易类接口需要 `account_id` 时, 默认传 `0`; 只有当用户明确指定账号和账号类型时, 才先调用 `stock_account` 获取返回的 `account_id`, 再把该 `account_id` 传入后续查询、下单或撤单接口。
11. 当接口返回结果没有股票名但展示内容需要股票名时, 若已有股票代码, 优先调用 `get_stock_info` 查询股票名, 不要根据记忆或代码前缀猜测名称。
12. 当用户只输入股票名而没有输入股票代码时, 优先调用 `get_match_stkinfo` 以股票名检索股票代码, 再用匹配到的标准代码调用后续接口。
13. 当用户取最新涨幅等，优先调用`get_more_info`中的ZAF等。
14. 需要获取某个数据前，先遍历每个接口的参数和返回字段，确认该数据在哪个接口的哪个字段里；如果不确定数据在哪个接口里，直接询问用户应该调用哪个接口获取该数据，不要盲猜或根据历史记忆调用某个接口。
15. 文档网址为 `help.tdx.com.cn/quant/`

---

## HTTP 请求格式

### PowerShell 示例

```powershell
$body = @{
  id = 1
  method = "get_market_data"
  params = @{
    stock_list = @("688318.SH")
    count = 5
    dividend_type = "none"
    period = "1d"
  }
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Uri "http://127.0.0.1:17709/" -Method Post -ContentType "application/json; charset=utf-8" -Body $body
```

### curl 示例

```bash
curl -s -X POST "http://127.0.0.1:17709/" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"id":1,"method":"get_market_data","params":{"stock_list":["688318.SH"],"count":5,"dividend_type":"none","period":"1d"}}'
```

### Python 仅作为 HTTP 客户端示例

可以用 Python 发送 HTTP 请求, 但只能作为通用 HTTP 客户端, 不允许导入或运行 `tqcenter.py`。

```python
import json
import urllib.request

payload = {
    "id": 1,
    "method": "get_market_data",
    "params": {
        "stock_list": ["688318.SH"],
        "count": 5,
        "dividend_type": "none",
        "period": "1d",
    },
}
req = urllib.request.Request(
    "http://127.0.0.1:17709/",
    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    headers={"Content-Type": "application/json; charset=utf-8"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=60) as resp:
    result = json.loads(resp.read().decode("utf-8"))
print(result)
```

---

## 典型调用

### 获取 688318.SH 最近五日 K 线

```json
{
  "id": 1,
  "method": "get_market_data",
  "params": {
    "stock_list": ["688318.SH"],
    "count": 5,
    "dividend_type": "none",
    "period": "1d"
  }
}
```

### 获取全部 A 股列表

```json
{
  "id": 1,
  "method": "get_stock_list",
  "params": {
    "market": "5"
  }
}
```

### 获取实时行情快照

```json
{
  "id": 1,
  "method": "get_market_snapshot",
  "params": {
    "stock_code": "688318.SH"
  }
}
```

### 打开688318的个股分析页面 或 打开688318的走势图 或 打开688318

```json
{
  "id": 1,
  "method": "exec_to_tdx",
  "params": {
    "url": "http://www.treeid/breed_1#688318"
  }
}
```

### 打开排行 或 进入排行

```json
{
  "id": 1,
  "method": "exec_to_tdx",
  "params": {
    "url": "http://www.treeid/SORT67"
  }
}
```

### 打开网站(举例为打开百度网站)

```json
{
  "id": 1,
  "method": "exec_to_tdx",
  "params": {
    "url": "http://www.treeid/dlghttp://baidu.com"
  }
}
```

### 打开主力期货合约

|ZXG			|自选股列表|
|ETF			|ETF基金|
|HK				|显示港股|
|QH				|显示期货|
|MAINQH		|显示为主力期货合约|

```json
{
  "id": 1,
  "method": "exec_to_tdx",
  "params": {
    "url": "http://www.treeid/MAINQH"
  }
}
```

### 交易账号选择规则

- 用户未指定账号时, 所有需要 `account_id` 的交易接口默认传 `0`, 不要先调用 `stock_account`。
- 用户明确指定账号和账号类型时, 先调用 `stock_account` 获取账户句柄, 再把响应中的 `result.Value` 作为后续接口的 `account_id`。
- 用户只说“查询持仓”“查询资产”“买入/卖出/撤单”但未指定账号时, 直接使用 `account_id: 0`。
- 用户指定“账号 1190306953, STOCK 账户”这类信息时, 流程是: `stock_account` -> `query_stock_positions`/`query_stock_asset`/`order_stock`/`cancel_order_stock`。

### 股票代码与名称补全规则

- 当用户输入股票名但没有输入股票代码时, 优先调用 `get_match_stkinfo` 检索股票代码, 参数 `key_word` 填用户输入的股票名。
- `get_match_stkinfo` 返回多个候选时, 优先选择名称完全匹配或最接近用户输入的结果; 无法判断唯一结果时, 向用户展示候选并要求确认。
- 获得标准股票代码后, 再用该代码调用 `get_market_data`, `get_stock_info`, `get_market_snapshot` 等后续接口。
- 当返回数据只有股票代码而没有股票名, 且回答、表格或图表需要显示股票名时, 优先使用已有股票代码调用 `get_stock_info` 获取名称。
- 不要根据历史记忆、代码前缀或板块规则猜测股票名; `get_stock_info` 失败或未返回名称时, 保留股票代码并说明名称不可用。
- 多只股票需要补全名称时, 只对最终需要展示的股票代码调用 `get_stock_info`, 避免对全量结果做不必要的逐只查询。

股票名查代码示例:

```json
{
  "id": 1,
  "method": "get_match_stkinfo",
  "params": {
    "key_word": "寒武纪"
  }
}
```

股票代码查名称示例:

```json
{
  "id": 1,
  "method": "get_stock_info",
  "params": {
    "stock_code": "688318.SH"
  }
}
```

### 查询交易账户

```json
{
  "id": 1,
  "method": "stock_account",
  "params": {
    "account": "1190306953",
    "account_type": "STOCK"
  }
}
```

### 查询持仓

```json
{
  "id": 1,
  "method": "query_stock_positions",
  "params": {
    "account_id": 0
  }
}
```

### 下单

```json
{
  "id": 1,
  "method": "order_stock",
  "params": {
    "account_id": 0,
    "stock_code": "688318.SH",
    "order_type": 0,
    "order_volume": 100,
    "price_type": 0,
    "price": 130.0
  }
}
```

---

## 股票代码格式

- 上交所: `600000.SH`
- 深交所: `000001.SZ`
- 北交所: `430047.BJ`
- 港股: `00700.HK`
- 美股: `AAPL.US`
- 新三板: `430047.NQ`
- 股票期权: `10004073.SZO` / `10004073.SHO`
- 国内期货: `代码.CFF` / `.SHF` / `.DCE` / `.CZC` / `.INE` / `.GFE`
- 中证指数: `000300.CSI`
- 开放式基金净值: `代码.OF`

---

## 常用参数

### K 线周期 `period`

| 值 | 含义 |
|----|------|
| `1m` | 1 分钟 |
| `5m` | 5 分钟 |
| `15m` | 15 分钟 |
| `30m` | 30 分钟 |
| `1h` | 60 分钟 |
| `1d` | 日线 |
| `1w` | 周线 |
| `1M` | 月线 |

### 复权类型 `dividend_type`

| 值 | 含义 |
|----|------|
| `none` | 不复权 |
| `front` / `qfq` | 前复权 |
| `back` / `hfq` | 后复权 |

### 时间格式

- 仅日期: `YYYYMMDD`, 例如 `20260605`
- 含时间: `YYYYMMDDHHMMSS`, 例如 `20260605150000`

---

## tqconst 常量与中文别名

HTTP 请求中不直接写 `tqconst.PRICE_SJ` 这类 Python 表达式, 应写入对应整数值。用户用中文描述时, 按下表转换。

### 股票买卖 `order_type`

| 中文别名 | tqconst 名称 | 数值 | 说明 |
|----------|--------------|------|------|
| 买入 | `STOCK_BUY` | 0 | 普通股票买入 |
| 卖出 | `STOCK_SELL` | 1 | 普通股票卖出 |

### 信用交易 `order_type`

| 中文别名 | tqconst 名称 | 数值 | 说明 |
|----------|--------------|------|------|
| 担保品买入 | `CREDIT_BUY` | 0 | 信用账户担保品买入 |
| 担保品卖出 | `CREDIT_SELL` | 1 | 信用账户担保品卖出 |
| 融资买入 | `CREDIT_FIN_BUY` | 69 | 融资买入 |
| 融券卖出 | `CREDIT_SLO_SELL` | 70 | 融券卖出 |
| 买券还券 | `CREDIT_COV_BUY` | 71 | 买券还券 |
| 卖券还款 | `CREDIT_STK_REPAY` | 76 | 卖券还款 |

### ETF 交易 `order_type`

| 中文别名 | tqconst 名称 | 数值 | 说明 |
|----------|--------------|------|------|
| 基金申购 | `ETF_PURCHASE` | 45 | ETF 或基金申购 |
| 基金赎回 | `ETF_REDEMPTION` | 46 | ETF 或基金赎回 |

### 期货 `order_type`

| 中文别名 | tqconst 名称 | 数值 | 说明 |
|----------|--------------|------|------|
| 期货开多 | `FUTURE_OPEN_LONG` | 101 | 开多仓 |
| 期货开空 | `FUTURE_OPEN…