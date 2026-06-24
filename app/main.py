from __future__ import annotations

import json
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

from app.app_logging import get_json_logger, get_logger, setup_logging
from app.api_doc import DEFAULT_API_DOC
from app.bridgeService import (
    choose_backend,
    get_method_policy,
    supported_methods,
    validate_method_access,
)
from app.config import ensure_example_config, ensure_runtime_dirs, get_config, get_config_warnings, reload_config
from app.dependencies import enforce_access
from app.health import collect_health
from app.localRpcClient import LocalRpcClient
from app.models import (
    ApiResponse,
    BacktestSendRequest,
    BlockPushRequest,
    CodeQueryRequest,
    FormulaInfoRequest,
    FormulaListRequest,
    FormulaBatchRunRequest,
    FormulaRunRequest,
    MarketDataRequest,
    ParamsRequest,
    RpcRequest,
    StockSearchRequest,
    TradeCancelRequest,
    TradeOrderRequest,
    WarnSendRequest,
)
from app.request_adapters import adapt_method_params
from app.tqPythonRuntime import TqPythonRuntime


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_runtime_dirs()
    ensure_example_config()
    reload_config()
    setup_logging()
    get_logger(__name__).info("TdxBridge 服务启动。")
    yield
    get_logger(__name__).info("TdxBridge 服务停止。")


app = FastAPI(
    title="TdxBridge",
    version="0.2.0",
    description="Windows 通达信局域网桥接服务。",
    lifespan=lifespan,
)
logger = get_logger(__name__)
access_logger = get_json_logger("tdxbridge.access", "access.log")
audit_logger = get_json_logger("tdxbridge.audit", "audit.log")
API_DOC_PATH = Path(__file__).resolve().parent.parent / "TdxBridge接口文档.md"


def _next_trace_id() -> str:
    return uuid.uuid4().hex


def _get_trace_id(request: Request) -> str:
    trace_id = getattr(request.state, "trace_id", None)
    if trace_id:
        return trace_id
    trace_id = _next_trace_id()
    request.state.trace_id = trace_id
    return trace_id


def _response_from_result(result: dict[str, object], trace_id: str, backend: str | None = None) -> ApiResponse:
    payload = dict(result)
    payload["traceId"] = trace_id
    if backend and not payload.get("backend"):
        payload["backend"] = backend
    return ApiResponse(**payload)


def _append_access_log(record: dict[str, object]) -> None:
    access_logger.info(json.dumps(record, ensure_ascii=False))


def _append_audit_log(record: dict[str, object]) -> None:
    audit_logger.info(json.dumps(record, ensure_ascii=False))


def _load_api_doc() -> str:
    if API_DOC_PATH.exists():
        return API_DOC_PATH.read_text(encoding="utf-8")
    return DEFAULT_API_DOC


def _execute_method(
    method: str,
    params: dict[str, object] | None,
    trace_id: str,
    forced_backend: str | None = None,
) -> ApiResponse:
    config = get_config()
    policy = get_method_policy(method)
    backend = forced_backend or choose_backend(method)
    adapted_params = adapt_method_params(method, params, backend=backend)
    access_error = validate_method_access(config, method)

    if access_error:
        response = ApiResponse(
            ok=False,
            backend=backend,
            method=method,
            data=None,
            error=access_error,
            traceId=trace_id,
            meta={
                "category": policy.category if policy else None,
                "writeAction": policy.write_action if policy else None,
            },
        )
        if policy and policy.write_action:
            _append_audit_log(
                {
                    "traceId": trace_id,
                    "method": method,
                    "backend": backend,
                    "ok": False,
                    "blocked": True,
                    "category": policy.category,
                    "writeAction": policy.write_action,
                    "params": adapted_params,
                    "error": access_error,
                }
            )
        return response

    if backend == "local":
        result = LocalRpcClient(config).call(method, adapted_params, trace_id=trace_id)
        response = _response_from_result(result, trace_id, backend="local")
    elif backend == "python":
        result = TqPythonRuntime(config).call(method, adapted_params, trace_id=trace_id)
        response = _response_from_result(result, trace_id, backend="python")
    else:
        response = ApiResponse(
            ok=False,
            backend="auto",
            method=method,
            data=None,
            error="未命中默认路由规则，请改用 /rpc/local 或 /rpc/python 显式指定后端。",
            traceId=trace_id,
        )

    response.meta = {
        "category": policy.category if policy else None,
        "writeAction": policy.write_action if policy else None,
        "adaptedParams": adapted_params,
    }
    if policy and policy.write_action:
        _append_audit_log(
            {
                "traceId": trace_id,
                "method": method,
                "backend": response.backend,
                "ok": response.ok,
                "blocked": False,
                "category": policy.category,
                "writeAction": policy.write_action,
                "params": adapted_params,
                "error": response.error,
            }
        )
    return response


def _execute_formula_run(
    method: str,
    params: dict[str, object] | None,
    trace_id: str,
) -> ApiResponse:
    adapted_params = adapt_method_params(method, params, backend="local")
    stock_code = adapted_params.get("stock_code")
    if not stock_code:
        return _execute_method(method, params, trace_id, forced_backend="local")

    config = get_config()
    local_client = LocalRpcClient(config)
    prepare_params = {
        "stock_code": stock_code,
        "stock_period": adapted_params.get("stock_period", "1d"),
        "start_time": adapted_params.get("start_time", ""),
        "end_time": adapted_params.get("end_time", ""),
        "count": adapted_params.get("count", 0),
        "dividend_type": adapted_params.get("dividend_type", 0),
    }
    prepare_result = local_client.call("formula_set_data_info", prepare_params, trace_id=trace_id)
    if not prepare_result.get("ok"):
        response = _response_from_result(prepare_result, trace_id, backend="local")
        response.method = method
        response.meta = {
            "prepared": False,
            "prepareMethod": "formula_set_data_info",
            "prepareParams": prepare_params,
            "adaptedParams": adapted_params,
        }
        return response

    run_params = {
        key: adapted_params[key]
        for key in ("formula_name", "formula_arg", "xsflag")
        if key in adapted_params
    }
    result = local_client.call(method, run_params, trace_id=trace_id)
    response = _response_from_result(result, trace_id, backend="local")
    response.meta = {
        "prepared": True,
        "prepareMethod": "formula_set_data_info",
        "prepareParams": prepare_params,
        "runParams": run_params,
        "adaptedParams": adapted_params,
    }
    return response


def _params_from_request(request: StockSearchRequest) -> dict[str, object]:
    params: dict[str, object] = dict(request.params)
    if request.keyword:
        params.setdefault("keyword", request.keyword)
    if request.query:
        params.setdefault("query", request.query)
    if request.text:
        params.setdefault("text", request.text)
    return params


def _supported_request_shapes() -> dict[str, object]:
    return {
        "/formula/run": {
            "method": ["formula_zb", "formula_xg", "formula_exp"],
            "params": "支持 formula_name/formula_arg；如同时提供 code/period，会先自动执行 formula_set_data_info",
        },
        "/formula/runBatch": {
            "method": [
                "formula_process_mul_zb",
                "formula_process_mul_xg",
                "formula_process_mul_exp",
            ],
            "params": "支持 name/codes/period/start/end/count/adjust，并自动映射到官方 formula_name/stock_list/stock_period/dividend_type",
        },
        "/trade/order": {
            "topLevelFields": ["code", "market", "price", "amount", "side"],
            "requiredMeaning": ["股票代码", "价格", "数量"],
            "sideValues": ["buy", "sell", "b", "s", "1", "2"],
            "codeFormat": ["600000.SH", "000001.SZ", "430047.BJ", "600000"],
        },
        "/stock/search": {
            "topLevelFields": ["keyword", "query", "text"],
            "requiredMeaning": ["搜索关键词"],
        },
        "/stock/info": {
            "topLevelFields": ["code", "market"],
            "requiredMeaning": ["股票代码"],
        },
        "/market/data": {
            "topLevelFields": ["code", "market", "period", "count", "adjust", "start", "end"],
            "requiredMeaning": ["股票代码"],
        },
        "/market/snapshot": {
            "topLevelFields": ["code", "market"],
            "requiredMeaning": ["股票代码"],
        },
        "/formula/info": {
            "topLevelFields": ["name", "formulaName"],
            "requiredMeaning": ["公式名称"],
        },
        "/trade/cancel": {
            "topLevelFields": ["orderId", "code"],
            "requiredMeaning": ["委托标识"],
        },
        "/warn/send": {
            "topLevelFields": ["title", "content"],
            "requiredMeaning": ["预警内容"],
        },
        "/backtest/send": {
            "topLevelFields": ["payload"],
            "requiredMeaning": ["回测数据载荷"],
        },
        "/blocks/push": {
            "topLevelFields": ["action", "codes", "name"],
            "actionValues": ["push", "create_sector"],
        },
    }


@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-Id") or _next_trace_id()
    request.state.trace_id = trace_id
    started = time.time()
    response: Response | None = None
    error_message: str | None = None

    try:
        response = await call_next(request)
        return response
    except Exception as exc:
        error_message = str(exc)
        raise
    finally:
        elapsed_ms = round((time.time() - started) * 1000, 2)
        status_code = response.status_code if response else 500
        if response is not None:
            response.headers["X-Trace-Id"] = trace_id

        record = {
            "traceId": trace_id,
            "method": request.method,
            "path": request.url.path,
            "statusCode": status_code,
            "durationMs": elapsed_ms,
            "clientIp": request.client.host if request.client else None,
            "error": error_message,
        }
        _append_access_log(record)
        logger.info(
            "请求完成 path=%s method=%s status=%s durationMs=%s trace_id=%s",
            request.url.path,
            request.method,
            status_code,
            elapsed_ms,
            trace_id,
        )


@app.get("/health", dependencies=[Depends(enforce_access)])
async def health() -> dict[str, object]:
    config = get_config()
    payload = collect_health(config)
    payload["warnings"] = get_config_warnings(config)
    return payload


@app.get("/doc", dependencies=[Depends(enforce_access)], response_class=PlainTextResponse)
async def api_doc() -> PlainTextResponse:
    return PlainTextResponse(_load_api_doc(), media_type="text/markdown; charset=utf-8")


@app.get("/capabilities", dependencies=[Depends(enforce_access)])
async def capabilities() -> dict[str, object]:
    config = get_config()
    return {
        "service": "TdxBridge",
        "version": "0.2.0",
        "documentation": {
            "endpoint": "/doc",
            "format": "markdown",
        },
        "localRpc": {
            "baseUrl": config.local_rpc.base_url,
            "timeoutSec": config.local_rpc.timeout_sec,
        },
        "pythonRuntime": {
            "mode": config.python_runtime.mode,
            "pythonExecutable": config.python_runtime.python_executable,
            "timeoutSec": config.python_runtime.timeout_sec,
        },
        "tdx": {
            "installDir": config.tdx.install_dir,
        },
        "riskControl": {
            "enableTrading": config.risk_control.enable_trading,
            "enableBlockPush": config.risk_control.enable_block_push,
            "enableWarnSend": config.risk_control.enable_warn_send,
            "enableBacktestSend": config.risk_control.enable_backtest_send,
        },
        "network": {
            "allowedCidrs": config.network.allowed_cidrs,
        },
        "supportedMethods": supported_methods(),
        "requestShapes": _supported_request_shapes(),
        "warnings": get_config_warnings(config),
    }


@app.post("/rpc/auto", response_model=ApiResponse, dependencies=[Depends(enforce_access)])
async def rpc_auto(request: Request, payload: RpcRequest) -> ApiResponse:
    trace_id = _get_trace_id(request)
    backend = choose_backend(payload.method)
    logger.info("收到自动路由请求: method=%s trace_id=%s backend=%s", payload.method, trace_id, backend)
    return _execute_method(payload.method, payload.params, trace_id)


@app.post("/rpc/local", response_model=ApiResponse, dependencies=[Depends(enforce_access)])
async def rpc_local(request: Request, payload: RpcRequest) -> ApiResponse:
    trace_id = _get_trace_id(request)
    logger.info("收到 TQ-Local 请求: method=%s trace_id=%s", payload.method, trace_id)
    return _execute_method(payload.method, payload.params, trace_id, forced_backend="local")


@app.post("/rpc/python", response_model=ApiResponse, dependencies=[Depends(enforce_access)])
async def rpc_python(request: Request, payload: RpcRequest) -> ApiResponse:
    trace_id = _get_trace_id(request)
    logger.info("收到 TQ-Python 请求: method=%s trace_id=%s", payload.method, trace_id)
    return _execute_method(payload.method, payload.params, trace_id, forced_backend="python")


@app.post("/stock/search", response_model=ApiResponse, dependencies=[Depends(enforce_access)])
async def stock_search(request: Request, payload: StockSearchRequest) -> ApiResponse:
    return _execute_method("get_match_stkinfo", _params_from_request(payload), _get_trace_id(request), forced_backend="local")


@app.post("/stock/info", response_model=ApiResponse, dependencies=[Depends(enforce_access)])
async def stock_info(request: Request, payload: CodeQueryRequest) -> ApiResponse:
    return _execute_method("get_stock_info", payload.to_params(), _get_trace_id(request), forced_backend="local")


@app.post("/market/data", response_model=ApiResponse, dependencies=[Depends(enforce_access)])
async def market_data(request: Request, payload: MarketDataRequest) -> ApiResponse:
    return _execute_method("get_market_data", payload.to_params(), _get_trace_id(request), forced_backend="local")


@app.post("/market/snapshot", response_model=ApiResponse, dependencies=[Depends(enforce_access)])
async def market_snapshot(request: Request, payload: CodeQueryRequest) -> ApiResponse:
    return _execute_method("get_market_snapshot", payload.to_params(), _get_trace_id(request), forced_backend="local")


@app.post("/market/moreInfo", response_model=ApiResponse, dependencies=[Depends(enforce_access)])
async def market_more_info(request: Request, payload: ParamsRequest) -> ApiResponse:
    return _execute_method("get_more_info", payload.params, _get_trace_id(request), forced_backend="local")


@app.post("/formula/list", response_model=ApiResponse, dependencies=[Depends(enforce_access)])
async def formula_list(request: Request, payload: FormulaListRequest) -> ApiResponse:
    return _execute_method("formula_get_all", payload.to_params(), _get_trace_id(request), forced_backend="local")


@app.post("/formula/info", response_model=ApiResponse, dependencies=[Depends(enforce_access)])
async def formula_info(request: Request, payload: FormulaInfoRequest) -> ApiResponse:
    return _execute_method("formula_get_info", payload.to_params(), _get_trace_id(request), forced_backend="local")


@app.post("/formula/run", response_model=ApiResponse, dependencies=[Depends(enforce_access)])
async def formula_run(request: Request, payload: FormulaRunRequest) -> ApiResponse:
    return _execute_formula_run(payload.method, payload.params, _get_trace_id(request))


@app.post("/formula/runBatch", response_model=ApiResponse, dependencies=[Depends(enforce_access)])
async def formula_run_batch(request: Request, payload: FormulaBatchRunRequest) -> ApiResponse:
    return _execute_method(payload.method, payload.params, _get_trace_id(request))


@app.post("/trade/queryAsset", response_model=ApiResponse, dependencies=[Depends(enforce_access)])
async def trade_query_asset(request: Request, payload: ParamsRequest) -> ApiResponse:
    return _execute_method("query_stock_asset", payload.params, _get_trace_id(request), forced_backend="local")


@app.post("/trade/queryPositions", response_model=ApiResponse, dependencies=[Depends(enforce_access)])
async def trade_query_positions(request: Request, payload: ParamsRequest) -> ApiResponse:
    return _execute_method("query_stock_positions", payload.params, _get_trace_id(request), forced_backend="local")


@app.post("/trade/queryOrders", response_model=ApiResponse, dependencies=[Depends(enforce_access)])
async def trade_query_orders(request: Request, payload: ParamsRequest) -> ApiResponse:
    return _execute_method("query_stock_orders", payload.params, _get_trace_id(request), forced_backend="local")


@app.post("/trade/order", response_model=ApiResponse, dependencies=[Depends(enforce_access)])
async def trade_order(request: Request, payload: TradeOrderRequest) -> ApiResponse:
    return _execute_method("order_stock", payload.to_params(), _get_trace_id(request), forced_backend="local")


@app.post("/trade/cancel", response_model=ApiResponse, dependencies=[Depends(enforce_access)])
async def trade_cancel(request: Request, payload: TradeCancelRequest) -> ApiResponse:
    return _execute_method("cancel_order_stock", payload.to_params(), _get_trace_id(request), forced_backend="local")


@app.post("/blocks/push", response_model=ApiResponse, dependencies=[Depends(enforce_access)])
async def blocks_push(request: Request, payload: BlockPushRequest) -> ApiResponse:
    method = "send_user_block" if payload.action == "push" else "create_sector"
    return _execute_method(method, payload.to_params(), _get_trace_id(request), forced_backend="python")


@app.post("/warn/send", response_model=ApiResponse, dependencies=[Depends(enforce_access)])
async def warn_send(request: Request, payload: WarnSendRequest) -> ApiResponse:
    return _execute_method("send_warn", payload.to_params(), _get_trace_id(request), forced_backend="python")


@app.post("/backtest/send", response_model=ApiResponse, dependencies=[Depends(enforce_access)])
async def backtest_send(request: Request, payload: BacktestSendRequest) -> ApiResponse:
    return _execute_method("send_bt_data", payload.to_params(), _get_trace_id(request), forced_backend="python")
