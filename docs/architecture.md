# TdxBridge 桥接服务设计与实施方案

## 1. 文档目的

这份文档将 `TdxBridge` 定义为一个面向 Windows 的独立桥接服务方案，用来解决下面这个实际问题：

1. 通达信 Skill 体系只能稳定运行在 Windows 上
2. `Hermes` / `OpenClaw` 在 Linux 上更好用
3. 需要一条稳定的局域网桥，把 Windows 上的通达信能力暴露给 Linux 调用

换句话说，这是一个典型的“鱼和熊掌不可兼得”问题：智能体、自动化工具和后台服务更适合在 Linux/macOS 上运行，通达信客户端和本地软件能力却被 Windows 桌面环境绑定。`TdxBridge` 不试图改变通达信的运行前提，而是在 Windows 侧常驻一个桥接服务，让非 Windows 调用方可以稳定、安全、可审计地访问通达信能力。

本方案刻意保持简单：

1. 不拆成多个产品
2. 不强依赖 `exe` 打包
3. 不把调用方绑死到 SDK
4. 只做一个可静默常驻、可自启动、可局域网访问的 Windows 桥接服务

## 2. 产品定义

`TdxBridge` 的唯一职责是：

**在 Windows 上静默运行，把本机通达信能力通过 HTTP 服务提供给局域网内的 Linux 调用方。**

对外的主要调用方包括：

1. `Hermes`
2. `OpenClaw`
3. 后续任何能发 HTTP 请求的本地或局域网服务

## 3. 核心设计原则

本方案遵循下面几条原则：

1. **单入口**
   - 用户只需要运行一个安装脚本
2. **非单文件**
   - 内部保持正常的 Python 工程结构，便于维护和排障
3. **不做 exe 依赖**
   - 避免被误判为病毒
   - 保持部署链路透明
4. **静默常驻**
   - 安装完成后后台运行
   - 关闭当前 PowerShell 窗口不影响服务
5. **登录后自动可用**
   - 通过 Windows 计划任务在用户登录后拉起
6. **局域网稳定优先**
   - 优先满足 Linux 远程调用稳定性
   - 不追求过度包装

## 4. 现实约束

当前方案明确接受这些现实条件：

1. 通达信运行在 Windows 桌面环境中
2. 部分能力依赖通达信 GUI 所在用户会话
3. 因此 `TdxBridge` 当前以“**用户登录后自动静默启动**”为正式运行模式
4. 暂不把“Windows 重启后无人登录也完全自动运行”作为 V1 目标

这不是能力退化，而是对通达信运行方式的真实适配。

## 5. 最终交付形态

对用户来说，`TdxBridge` 是一套**单脚本入口的桥接服务**。

建议交付结构如下：

```text
TdxBridge/
  00-右键管理员打开安装-TdxBridge.cmd
  01-启动-TdxBridge.cmd
  02-停止-TdxBridge.cmd
  03-右键管理员打开卸载-TdxBridge.cmd
  scripts/
    Install-TdxBridge.ps1
    Start-TdxBridge.ps1
    Stop-TdxBridge.ps1
    Uninstall-TdxBridge.ps1
  app/
    main.py
    config.py
    models.py
    security.py
    health.py
    bridgeService.py
    localRpcClient.py
    tqPythonRuntime.py
    tqPythonWorker.py
    serializers.py
  config/
    bridge.example.json
  docs/
    api.md
    user-guide.md
    tq-local.md
    tq-python.md
  tdxbridge-agent/
  runtime/
  logs/
  requirements.txt
  README.md
```

其中：

1. `00-右键管理员打开安装-TdxBridge.cmd`
   - Windows 用户双击入口
   - 打开交互式终端并执行安装流程
2. `01-启动-TdxBridge.cmd`
   - Windows 用户双击启动入口
3. `02-停止-TdxBridge.cmd`
   - Windows 用户双击停止入口
4. `03-右键管理员打开卸载-TdxBridge.cmd`
   - Windows 用户双击卸载入口
5. `scripts/Install-TdxBridge.ps1`
   - 安装逻辑主体
6. `scripts/Start-TdxBridge.ps1`
   - 静默启动后台服务
7. `scripts/Stop-TdxBridge.ps1`
   - 停止后台服务
8. `scripts/Uninstall-TdxBridge.ps1`
   - 卸载计划任务和相关配置
9. `docs/api.md`
   - `/doc` 的源文档
10. `tdxbridge-agent/`
   - 支持 skill 的智能体接入资料

## 6. 总体架构

```text
Linux Hermes / OpenClaw
          |
          | HTTP
          v
TdxBridge (Windows :18888)
          |
          |-- LocalRpcClient  -> http://127.0.0.1:17709/
          |
          |-- TqPythonRuntime
                 |
                 |-- subprocess-per-call
                 v
               TqPythonWorker
                 -> C:\tdx64\PYPlugins\user\tqcenter.py
                 -> TPyth.dll
                 -> TPythClient.dll
          |
          v
        通达信客户端 TdxW.exe
```

架构重点如下：

1. 对外统一只暴露一个 HTTP 服务
2. 高频只读请求优先走 `TQ-Local`
3. 高级能力和 Python 逻辑走 `TQ-Python`
4. Python 通道继续保持 `subprocess-per-call`
5. 单次 Python 调用异常或卡死时，不拖垮桥接主进程

## 7. 运行模型

`TdxBridge` 采用“**脚本安装 + Python 后台常驻 + 计划任务自启动**”模型。

### 7.1 用户侧使用方式

Windows 用户只需要直接双击：

```text
00-右键管理员打开安装-TdxBridge.cmd
```

双击后应表现为：

1. 自动打开一个交互式终端窗口
2. 在窗口中一步一步输出安装日志
3. 需要人工输入时，直接在该窗口内完成
4. 安装结束后窗口保持打开，方便用户查看结果
5. 用户手动关闭窗口后，不影响已经成功启动的后台服务

### 7.2 安装脚本职责

安装脚本负责：

1. 检查当前系统是否为 Windows
2. 自动探测通达信安装目录
3. 优先检查常见目录：
   - 当前 `TdxBridge` 目录的父级目录
   - 当前 `TdxBridge` 目录的同级目录
   - 各盘符根目录下的 `\new_tdx64`
   - 各盘符根目录下的 `\tdx64`
   - 各盘符下的 `\Program Files\new_tdx64`
   - 各盘符下的 `\Program Files\tdx64`
   - 各盘符下的 `\Program Files (x86)\new_tdx64`
   - 各盘符下的 `\Program Files (x86)\tdx64`
4. 自动探测失败时，要求用户手动输入通达信安装目录
5. 检查 `tqcenter.py`、`TPyth.dll`、`TPythClient.dll`
6. 检查 Python 运行时是否存在
7. 检查并安装所需 Python 依赖
8. 生成配置文件
9. 引导用户填写“允许访问网段”
10. 默认值自动使用当前设备所在局域网段，直接回车即可采用默认值
11. 对填写的 CIDR 做格式校验
12. 把最终确认的通达信目录和白名单写入配置文件
13. 自动生成访问 Token
14. 创建运行目录和日志目录
15. 注册 Windows 计划任务 `TdxBridge`
16. 按填写的白名单配置防火墙规则
17. 首次静默启动服务
18. 调用 `/health` 完成安装后自检
19. 根据实际安装结果自动生成给 Hermes / OpenClaw 的连接提示
20. 自动生成给智能体读取的接入说明文档
21. 打印最终成功信息

安装输出形式要求：

1. 每个关键阶段都要打印清晰的“步骤标题”
2. 每个步骤内部要打印当前动作日志
3. 出错时直接在当前终端显示错误原因
4. 成功后在当前终端显示服务地址、Token、白名单、运行状态
5. 成功后在当前终端完整打印一份可直接复制给智能体的连接提示
6. 成功后额外生成一份给智能体读取的 Markdown 接入文档

### 7.3 成功提示要求

安装成功后，脚本必须明确打印：

1. 服务地址
2. 服务端口
3. Token
4. 自动探测到的通达信目录或手动输入后的最终目录
5. 允许访问的来源网段白名单
6. 当前运行模式
7. 通达信进程状态
8. `17709` 可达状态
9. 自启动状态是否注册成功
10. 防火墙规则是否配置成功
11. 智能体连接提示文件路径
12. 智能体接入文档路径

安装成功后，还必须输出一整段可直接复制给 Hermes / OpenClaw 的提示词；同时生成一份给智能体读取的 Markdown 接入文档，至少说明：

1. 当前实例地址和 Token
2. 能调用的读取类接口
3. 推荐的低副作用验证顺序
4. 认证头怎么写
5. 高风险接口有哪些，默认不要调用
6. 失败时优先排查哪些层

## 8. 静默运行与自启动设计

### 8.1 静默运行

后台服务由 Python 启动，但不依赖前台控制台窗口。

推荐方式：

1. 由 `scripts/Start-TdxBridge.ps1` 启动 Python 服务
2. 使用 `pythonw.exe`，或通过计划任务以隐藏方式运行 `python.exe`
3. 启动完成后，安装脚本可以退出
4. 关闭 PowerShell 或 SSH 会话后，服务继续运行

用户看到的交互式终端只负责展示安装或维护过程，不承担后台常驻职责。

### 8.2 开机自启动

V1 使用 Windows 计划任务而不是 `exe` 服务包装。

推荐配置：

1. 任务名：`TdxBridge`
2. 触发时机：指定用户登录时
3. 运行模式：隐藏窗口、最高权限
4. 失败后自动重试
5. 启动入口：`scripts/Start-TdxBridge.ps1`

### 8.3 为什么不用 exe

V1 不要求打包成 `exe`，原因如下：

1. 自制 `exe` 更容易被误报
2. PowerShell + Python 更透明
3. 出问题时排查成本更低
4. 当前目标是稳定桥接，不是桌面发行包装

## 9. 启动前检查

桥接服务启动时应检查以下条件：

1. 当前系统是否为 Windows
2. 配置中的 `tdx.install_dir` 是否存在
3. `tdx.install_dir\PYPlugins\user\tqcenter.py` 是否存在
4. `tdx.install_dir\PYPlugins\TPyth.dll` 是否存在
5. `tdx.install_dir\PYPlugins\TPythClient.dll` 是否存在
6. Python 运行时是否可用
7. `TdxW.exe` 是否运行
8. `http://127.0.0.1:17709/` 是否可达
9. 是否已经配置有效的允许访问网段

如果关键检查失败，服务应：

1. 在日志中记录明确原因
2. 在 `/health` 中返回降级状态
3. 对必须依赖对应能力的接口返回结构化错误

补充约束：

1. 如果“允许访问网段”为空，服务默认只允许 `127.0.0.1` 本机访问
2. 安装脚本应默认给出当前设备所在局域网段，并允许用户直接回车采用默认值
3. 面向局域网发布前，必须先通过安装脚本填写白名单

## 10. 对外接口设计

### 10.1 基础接口

1. `GET /health`
   - 返回服务是否存活
   - 返回 `TdxW.exe` 状态
   - 返回 `17709` 连通性
   - 返回 Python 运行时状态
2. `GET /capabilities`
   - 返回支持的方法
   - 返回风险开关状态
   - 返回 `pythonRuntime.mode`

### 10.2 通用桥接接口

1. `POST /rpc/auto`
   - 根据方法自动选择后端
2. `POST /rpc/local`
   - 强制走 `TQ-Local`
3. `POST /rpc/python`
   - 强制走 `TQ-Python`

### 10.3 业务接口

1. `POST /stock/search`
2. `POST /stock/info`
3. `POST /market/data`
4. `POST /market/snapshot`
5. `POST /market/moreInfo`
6. `POST /formula/list`
7. `POST /formula/info`
8. `POST /formula/run`
9. `POST /formula/runBatch`
10. `POST /trade/queryAsset`
11. `POST /trade/queryPositions`
12. `POST /trade/queryOrders`
13. `POST /trade/order`
14. `POST /trade/cancel`
15. `POST /blocks/push`
16. `POST /warn/send`
17. `POST /backtest/send`

### 10.4 统一响应格式

所有接口建议返回统一结构：

```json
{
  "ok": true,
  "backend": "local",
  "method": "get_stock_list",
  "data": {},
  "error": null,
  "traceId": "20260620-xxxx"
}
```

这样可以让 `Hermes` / `OpenClaw` 侧更容易做兼容和诊断。

## 11. 路由策略

### 11.1 默认走 `TQ-Local`

下面这些高频只读能力默认优先走 `TQ-Local`：

1. `get_match_stkinfo`
2. `get_stock_info`
3. `get_market_data`
4. `get_market_snapshot`
5. `get_more_info`
6. `get_stock_list`
7. `formula_get_all`
8. `formula_get_info`
9. `formula_zb`
10. `formula_xg`
11. `formula_exp`
12. `formula_process_mul_zb`
13. `formula_process_mul_xg`
14. `formula_process_mul_exp`
15. `query_stock_asset`
16. `query_stock_positions`
17. `query_stock_orders`

### 11.2 默认走 `TQ-Python`

下面这些能力默认优先走 `TQ-Python`：

1. `send_user_block`
2. `create_sector`
3. `send_warn`
4. `send_bt_data`
5. `price_df`
6. 需要 `DataFrame` 或本地 Python 二次处理的场景

### 11.3 自动回退规则

自动路由时遵循下面规则：

1. 只读请求允许按配置回退
2. `TQ-Local` 不可用时，可回退到 `TQ-Python`
3. 写请求默认不自动回退
4. 交易写操作必须显式受风控开关约束

## 12. Python 通道设计

`TQ-Python` 通道必须保持 `subprocess-per-call`。

原因如下：

1. 通达信 Python 插件及 DLL 调用稳定性不可完全假设
2. 单次请求独立子进程，更容易限制超时
3. 某个接口挂死时，不会拖垮桥接主服务
4. stderr/stdout 可以单独采集，便于排障

建议实现要求：

1. 每个 Python 请求独立进程
2. 独立超时控制
3. 独立返回码
4. 主进程统一做 JSON 解析和错误包装

## 13. 结果序列化策略

桥接服务需要把 `TQ-Python` 返回值统一转换为 JSON 可传输格式。

重点处理以下类型：

1. `dict`
2. `list`
3. `pandas.DataFrame`
4. `numpy` 标量
5. `datetime`

序列化约定：

1. `DataFrame`
   - 输出为 `index + columns + records`
2. `numpy`
   - 转为普通 `int` / `float`
3. `datetime`
   - 转为 ISO 字符串

## 14. 安全设计

### 14.1 认证

桥接服务必须支持：

1. `Authorization: Bearer <token>`
2. `X-Tdx-Token: <token>`

无令牌时默认仅允许：

1. `GET /health`
2. 可选 `GET /capabilities`

### 14.2 网络限制

监听地址可为：

1. `0.0.0.0:18888`

但应通过 Windows 防火墙限制来源：

1. `192.168.10.0/24`
2. 或明确指定 `Hermes` / `OpenClaw` 所在主机 IP

### 14.3 风险开关

默认关闭高风险写操作：

1. `ENABLE_TRADING=false`
2. `ENABLE_BLOCK_PUSH=false`
3. `ENABLE_WARN_SEND=false`
4. `ENABLE_BACKTEST_SEND=false`

也就是说，能力已经接通，不代表默认对外开放。

## 15. 配置文件设计

建议使用统一配置文件：

```text
config/bridge.json
```

示例：

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 18888
  },
  "local_rpc": {
    "base_url": "http://127.0.0.1:17709/",
    "timeout_sec": 15
  },
  "auth": {
    "token": "auto-generated-token"
  },
  "network": {
    "allowed_cidrs": []
  },
  "tdx": {
    "install_dir": ""
  },
  "python_runtime": {
    "mode": "subprocess-per-call",
    "timeout_sec": 20,
    "python_executable": "python"
  },
  "risk_control": {
    "enable_trading": false,
    "enable_block_push": false,
    "enable_warn_send": false,
    "enable_backtest_send": false
  },
  "logging": {
    "level": "INFO",
    "retain_days": 14
  }
}
```

其中：

1. `tdx.install_dir` 允许初始为空
2. 安装脚本会优先自动探测并回写实际目录
3. 配置项 `network.allowed_cidrs` 初始可为空，但为空时只允许本机 `127.0.0.1` 访问
4. 安装脚本填写白名单时，默认值应为当前设备所在局域网段，直接回车即可采用默认值
5. 正式对局域网开放前，应由安装脚本要求用户确认或修改白名单
6. 如果配置目录无效，服务端运行时也会再次尝试按常见目录自动探测

## 16. 日志与排障

至少保留以下三类日志：

1. `service.log`
   - 启动、停止、异常、降级信息
2. `access.log`
   - 来源 IP、接口、耗时、状态码
3. `audit.log`
   - 写接口调用记录

日志要求：

1. 按天滚动
2. 自动清理历史日志
3. 排障时能快速区分以下问题：
   - 通达信未启动
   - `17709` 不可达
   - Python worker 超时
   - 鉴权失败
   - 写接口被风控拒绝

## 17. 脚本职责定义

### 17.1 `scripts/Install-TdxBridge.ps1`

负责：

1. 自检
2. 安装依赖
3. 写配置
4. 生成 Token
5. 注册计划任务
6. 配置防火墙
7. 首次启动
8. 打印成功结果

### 17.2 `scripts/Start-TdxBridge.ps1`

负责：

1. 检查服务是否已运行
2. 静默拉起 Python 主服务
3. 记录启动日志

### 17.3 `scripts/Stop-TdxBridge.ps1`

负责：

1. 停止后台服务
2. 清理运行态 PID 或锁文件

### 17.4 `scripts/Uninstall-TdxBridge.ps1`

负责：

1. 停止服务
2. 删除计划任务
3. 删除防火墙规则
4. 默认清理配置、日志和运行时目录
5. 可选保留配置和日志

## 18. Git 仓库关联

当前项目应关联到以下 GitHub 仓库：

1. 仓库地址：`https://github.com/Anoiing/TdxBridge.git`
2. 推荐远端名：`origin`

本地仓库建议保持以下约定：

1. 设计文档和脚本与代码同仓管理
2. 远端主仓库统一使用 `origin`
3. 后续脚本、服务代码、文档都直接围绕该仓库演进

## 19. 当前代码状态

当前仓库内已经完成：

1. Windows 用户双击 `.cmd` 入口
2. `scripts/` 下的安装、启动、停止、卸载脚本
3. FastAPI 桥接服务主体
4. `TQ-Local` 直连通道
5. `TQ-Python` 子进程隔离调用通道
6. 写接口默认关闭的风控策略
7. `service.log`、`access.log`、`audit.log` 三类日志
8. 通达信目录自动探测与手动输入兜底
9. 来源网段白名单手动输入与 CIDR 校验

## 20. 当前验证状态

当前仓库侧已经完成的验证包括：

1. 代码可导入，关键 API 路由已注册
2. Python 代码语法编译通过
3. 配置文件校验逻辑已覆盖端口、Token、CIDR、Python 路径等基础约束
4. 目录结构与文档描述已对齐

仍需在真实 Windows 环境补充的发布前验证包括：

1. 双击安装入口的终端展示效果
2. Python 依赖安装链路
3. 计划任务注册与自动重试行为
4. 防火墙规则创建与局域网访问
5. 通达信已启动场景下的 `/health`、`/stock/search`、`/rpc/python`

## 21. 当前保守策略

下面这些有真实副作用的能力，当前不作为默认自动验证范围：

1. `order_stock`
2. `cancel_order_stock`
3. `send_warn`
4. `send_bt_data`
5. `blocks/push`

原因不是链路不能做，而是这些操作会对通达信侧产生真实写入或提醒效果。

## 22. V1 验收标准

满足以下条件即可认定 V1 成熟可用：

1. 用户只执行一次安装脚本即可完成部署
2. 安装完成后可通过局域网访问 `/health`
3. 关闭 PowerShell 窗口后服务继续运行
4. Windows 重启并登录后服务自动恢复
5. `/stock/search`、`/market/data`、`/rpc/python` 可正常使用
6. `/capabilities` 能确认 `pythonRuntime.mode = subprocess-per-call`
7. 写接口默认关闭
8. 日志能清楚说明故障原因

## 23. 建议实施顺序

建议按下面顺序推进：

1. 固化本设计文档
2. 固化目录结构
3. 编写 `Install/Start/Stop/Uninstall` 四个脚本
4. 固化配置文件和日志策略
5. 整合服务启动、自检、计划任务注册
6. 在 Windows 上完成完整安装验证与重启验证

## 24. 结论

`TdxBridge` V1 不应该被设计成一个重包装的 Windows 产品，而应该被设计成：

**一个单脚本入口安装、后台 Python 静默常驻、登录后自动拉起、对局域网提供通达信桥接服务的 Windows 桥。**

这条路线最贴合当前目标：

1. 保留现有已跑通的双后端能力
2. 不额外引入 `exe` 误报风险
3. 直接服务于 Linux 上的 `Hermes` / `OpenClaw`
4. 让通达信的 Windows 限制通过局域网桥的方式被稳定消化掉
