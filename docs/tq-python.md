---
name: 通达信TQ-Python
description: TdxQuant是由通达信软件提供的证券行情分析和量化投研平台，专注于为证券投资者提供行情信息获取、数据分析、策略研究、投资决策和智能交易的全流程解决方案。此技能支持python代码通过tqcenter接口与本地的通达信客户端交互。
---

# Tdx Quant Python Skill

> 本文档基于 tqcenter.py **Version 1.0.12（2026-06-12）**
> 官方文档：https://help.tdx.com.cn/quant/

TdxQuant 是由深圳市财富趋势科技股份有限公司研发的专业量化投研平台，本 Skill 通过 `tqcenter.py` 模块的 `tq` 类提供与通达信客户端交互的完整接口。

---

## 重要：Python 文件路径配置

### 文件目录结构

```
通达信安装目录\
├── Tdxw.exe                 # 主程序
├── PYPlugins\               # 插件目录
│   ├── TPyth.dll            # 通达信Python通信DLL
│   ├── TPythClient.dll      # 通达信Python通信DLL
│   ├── user\                # 用户策略目录
│   │   └── tqcenter.py      # TdxQuant核心模块
│   ├── data\                # 下载数据目录
│   └── file\                # 发送文件目录
```

**Python 策略文件可以放在任意位置。**

导入 `tqcenter` 前，必须将通达信安装目录的 `PYPlugins\user` 路径添加到 `sys.path`。**使用 `sys.path.insert(0, ...)` 确保加载正确的 `tqcenter.py`。**

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

### 第一步：检查通达信是否已安装

使用 Python + `winreg` 依次检查以下三个注册表键，**只要找到至少一个即视为已安装**。注意：因为 PowerShell 在 Git Bash 环境下输出可能被截断，必须用 Python 而非 PowerShell 读注册表。

```
HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信金融终端64
HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信专业版
HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信金融终端(量化模拟)
HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信金融终端(测试)
```

检查代码：

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
        disp = winreg.QueryValueEx(key, 'DisplayName')[0]
        loc = winreg.QueryValueEx(key, 'InstallLocation')[0]
        print(f'[已安装] {disp} -> {loc}')
        winreg.CloseKey(key)
        found = True
        break
    except FileNotFoundError:
        continue
if not found:
    print('NOT_INSTALLED')
```

- 已安装 → 记录 `InstallLocation` 作为 `tdx_root`，进入第三步
- 未安装 → 进入第二步

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
- 如果有多个 `TdxW.exe` 进程 → 依次寻找，直到找到第一个含有 `tqcenter.py` 的进程目录
- 如果 `TdxW.exe` 已在运行 → 进入第四步

### 第四步：检查 tqcenter.py 是否存在

确认 `{tdx_root}\PYPlugins\user\tqcenter.py` 文件存在：

```bash
ls -la "{tdx_root}/PYPlugins/user/tqcenter.py"
```

- 如果 `tqcenter.py` 不存在 → 提示用户当前的客户端不支持 TQ 策略，需升级通达信客户端
- 如果存在 → 可以开始执行用户请求

**`tdx_root` 找到后请记住这个位置，不用每次都查找，除非这个位置失效。**

---

### 获取通达信安装目录（供策略代码使用）

```python
import winreg

def get_tdx_install_path():
    """从注册表获取通达信安装目录"""
    key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信金融终端64"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            install_path, _ = winreg.QueryValueEx(key, "InstallLocation")
            return install_path
    except FileNotFoundError:
        print(f"未找到注册表项: HKLM\\{key_path}")
        return None

tdx_root = get_tdx_install_path()
# tdx_root 示例: "D:\\new_tdx" 或 "E:\\App\\new_tdx_test64"
```

### 初始化示例（动态获取安装目录）

```python
import sys, winreg, os

# 从注册表获取安装目录
key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\通达信金融终端64"
with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
    tdx_root, _ = winreg.QueryValueEx(key, "InstallLocation")

# 添加 PYPlugins/user 到 sys.path
sys.path.insert(0, os.path.join(tdx_root, 'PYPlugins', 'user'))

from tqcenter import tq

tq.initialize(__file__)
```

### 手动指定路径（已知安装目录时）

```python
import sys
sys.path.insert(0, 'E:/App/new_tdx_test64/PYPlugins/user')

from tqcenter import tq

tq.initialize(__file__)
```

**关键说明：**
- `tqcenter.py` 会在其上上级目录（`PYPlugins/`）自动定位 `TPythClient.dll`
- 使用 `sys.path.insert(0, ...)` 而非 `sys.path.append()`，优先加载通达信安装目录的 `tqcenter.py`
- `__file__` 为当前 Python 文件路径，用作策略唯一标识符

---

## 股票代码格式

- **上交所**：`600000.SH`
- **深交所**：`000001.SZ`
- **北交所**：`430047.BJ`
- **港股**：`00700.HK`
- **美股**：`AAPL.US`
- **新三板**：`430047.NQ`
- **股票期权**：`10004073.SZO` / `10004073.SHO`
- **国内期货**：代码.CFF / .SHF / .DCE / .CZC / .INE / .GFE
- **中证指数**：`000300.CSI`
- **开放式基金净值**：代码.OF

---

## 时间格式

- 仅日期：`YYYYMMDD`（如 `20231231`）
- 含时间：`YYYYMMDDHHMMSS`（如 `20231231150000`）

---

## 常量字典

### 市场代码后缀（股票代码后缀）

| 后缀 | 市场编号 | 说明 |
|------|----------|------|
| SZ | 0 | 深交所 |
| SH | 1 | 上交所 |
| BJ | 2 | 北交所 |
| US | 74 | 美股 |
| HK | 31 | 港股 |
| NQ | 44 | 新三板 |
| SZO | 9 | 深交所期权 |
| SHO | 8 | 上交所期权 |
| CSI | 62 | 中证指数 |
| CNI | 102 | 国证指数 |
| HG | 38 | 国内宏观指标 |
| CFF | 47 | 中金期货 |
| SHF | 30 | 上期所/上海能源 |
| DCE | 29 | 大商所 |
| CZC | 28 | 郑商所 |
| GFE | 66 | 广期所 |
| HI | 27 | 港股指数 |
| OF | 33 | 开放式基金净值 |
| CFFO | 7 | 中金所期权 |
| CZCO | 4 | 郑州期货期权 |
| DCEO | 5	 | 大连期货期权 |
| SHFO | 6	 | 上海期货期权 |
| GFEO | 67 | 广州期货期权
| QHZ | 42 | 期货类指数 |

### K线周期（period）

| 值 | 说明 |
|----|------|
| `'1m'` | 1分钟 |
| `'5m'` | 5分钟 |
| `'15m'` | 15分钟 |
| `'30m'` | 30分钟 |
| `'1h'` | 60分钟 |
| `'1d'` | 日线 |
| `'1w'` | 周线 |
| `'1mon'` | 月线 |
| `'1q'` | 季线 |
| `'1y'` | 年线 |
| `'tick'` | 分笔 |

### 复权类型（dividend_type）

| 值 | 说明 |
|----|------|
| `'none'` | 不复权 |
| `'front'` | 前复权 |
| `'back'` | 后复权 |

### 委托类型（order_type）

| 常量 | 值 | 说明 |
|------|-----|------|
| `tqconst.STOCK_BUY` | 0 | 买入 |
| `tqconst.STOCK_SELL` | 1 | 卖出 |
| `tqconst.CREDIT_BUY` | 0 | 担保品买入（信用账户） |
| `tqconst.CREDIT_SELL` | 1 | 担保品卖出（信用账户） |
| `tqconst.CREDIT_FIN_BUY` | 69 | 融资买入 |
| `tqconst.CREDIT_SLO_SELL` | 70 | 融券卖出 |

### 报价类型（price_type）

| 常量 | 值 | 说明 |
|------|-----|------|
| `tqconst.PRICE_MY` | 0 | 自填价格 |
| `tqconst.PRICE_SJ` | 1 | 市价 |
| `tqconst.PRICE_ZTJ` | 2 | 涨停价/笼子上限 |
| `tqconst.PRICE_DTJ` | 3 | 跌停价/笼子下限 |

---

## 一、初始化与关闭

### `tq.initialize(path, dll_path='')`
初始化与通达信客户端的连接。

```python
tq.initialize(path: str, dll_path: str = '')
```

- `path`：当前 Python 文件路径（传入 `__file__`），作为策略唯一标识
- `dll_path`：可选，自定义 `TPythClient.dll` 路径

**注意：**
- 函数名 `"initialize"` 不可修改；每个策略必须有该函数
- 错误码 `ErrorId='12'` 表示已有同名策略运行（会打印警告但不报错）
- 错误码 `ErrorId='6'` 或 `'7'` 表示连接断开，会自动触发重新初始化

### `tq.close()`
手动关闭与通达信客户端的连接并释放资源。程序退出时也会自动调用。

---

## 二、行情数据接口

### 2.1 获取K线行情 `get_market_data`

```python
tq.get_market_data(
    field_list: List[str] = [],
    stock_list: List[str] = [],
    period: str = '',
    start_time: str = '',
    end_time: str = '',
    count: int = -1,
    dividend_type: Optional[str] = None,
    fill_data: bool = True
) -> Dict
```

根据股票列表获取历史 K 线数据。

**参数说明：**

| 参数 | 必填 | 类型 | 说明 |
|------|------|------|------|
| field_list | N | List[str] | 需返回的字段列表；空列表返回所有字段 |
| stock_list | Y | List[str] | 股票代码列表 |
| period | Y | str | K线周期 |
| start_time | N | str | 开始时间 |
| end_time | N | str | 结束时间；未传则默认当前时间 |
| count | N | int | `count>0`：取截止 end_time 最近 n 条；`count<=0`：使用 start_time/end_time 区间 |
| dividend_type | N | str | 复权类型：`'none'`（不复权）、`'front'`（前复权）、`'back'`（后复权） |
| fill_data | N | bool | 是否向前填充缺失数据，默认 `True` |

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| Date | str | 日期 |
| Time | str | 时间 |
| Open | str | 开盘价（元） |
| High | str | 最高价（元） |
| Low | str | 最低价（元） |
| Close | str | 收盘价（元） |
| Volume | str | 成交量（手） |
| Amount | str | 成交额（万元） |
| ForwardFactor | str | 前复权因子（仅 dividend_type=none 时有效） |

**返回值：** `Dict`，键为字段名，值为 `pd.DataFrame`（**行=时间，列=股票代码**）

**重要注意：**
- `count>0` 时 `start_time` 失效，`end_time` 若未传默认为当前时间
- 一次最多返回 24000 条数据，获取完整分钟线需分批
- 后复权数据与取的数据个数有关，只在返回的数据中进行后复权
- `dividend_type=None`（Python None，非字符串）时默认不复权

**数据样本：**
```
{'Close':             688318.SH
 2025-12-24     131.58,
 'Volume':             688318.SH
 2025-12-24  2257325.0}
```

---

### 2.2 获取实时行情快照 `get_market_snapshot`

```python
tq.get_market_snapshot(
    stock_code: str,
    field_list: List = []
) -> Dict
```

获取指定股票的最新行情快照数据。

**参数说明：**
- `stock_code`：单个股票代码，如 `'300505.SZ'`
- `field_list`：可选，指定返回字段（大小写不敏感）；空列表返回所有字段

**完整返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| ItemNum | str | 快照笔数 |
| LastClose | str | 前收盘价 |
| Open | str | 开盘价 |
| Max | str | 最高价 |
| Min | str | 最低价 |
| Now | str | 现价 |
| Volume | str | 总手 |
| NowVol | str | 现手 |
| Amount | str | 总成交金额 |
| Inside | str | 内盘（板块指数时为跌停家数） |
| Outside | str | 外盘（板块指数时为涨停家数） |
| TickDiff | str | 笔涨跌 |
| InOutFlag | str | 内外盘标志：0=Buy, 1=Sell, 2=Unknown |
| Jjjz | str | 基金净值 |
| Buyp | List[str] | 五档买价列表 |
| Buyv | List[str] | 五档买盘量列表 |
| Sellp | List[str] | 五档卖价列表 |
| Sellv | List[str] | 五档卖盘量列表 |
| UpHome | str | 上涨家数（对指数有效） |
| DownHome | str | 下跌家数（对指数有效） |
| Before5MinNow | str | 5分钟前价格 |
| Average | str | 均价 |
| XsFlag | str | 小数位数 |
| Zangsu | str | 涨速 |
| ZAFPre3 | str | 3日涨幅 |

**数据样本：**
```python
{'ItemNum': '3342', 'LastClose': '34.21', 'Open': '33.78', 'Max': '36.49',
 'Min': '32.50', 'Now': '35.06', 'Volume': '122881', 'NowVol': '1449',
 'Amount': '43068.48', 'Insi…