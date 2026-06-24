from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


PLACEHOLDER_TOKENS = {"replace-with-generated-token", "auto-generated-token"}
CODE_PATTERN = re.compile(r"\b\d{6}\.(?:SH|SZ|BJ)\b", re.IGNORECASE)


def log(message: str = "") -> None:
    print(message, flush=True)


def mask_token(token: str) -> str:
    token = str(token or "").strip()
    if len(token) <= 8:
        return token
    return f"{token[:4]}...{token[-4:]}"


def load_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def summarize_value(value: Any, max_len: int = 240) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False)
    except TypeError:
        text = repr(value)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def iter_values(value: Any):
    if isinstance(value, dict):
        for item in value.values():
            yield from iter_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_values(item)
    else:
        yield value


def find_first_stock_code(value: Any) -> str | None:
    preferred_keys = ("code", "stock_code", "stockCode", "symbol", "ticker")
    if isinstance(value, dict):
        for key in preferred_keys:
            candidate = value.get(key)
            if isinstance(candidate, str):
                match = CODE_PATTERN.search(candidate)
                if match:
                    return match.group(0).upper()
        for nested in value.values():
            found = find_first_stock_code(nested)
            if found:
                return found
        return None
    if isinstance(value, list):
        for item in value:
            found = find_first_stock_code(item)
            if found:
                return found
        return None
    if isinstance(value, str):
        match = CODE_PATTERN.search(value)
        if match:
            return match.group(0).upper()
    return None


def find_first_formula_name(value: Any) -> str | None:
    preferred_keys = ("acCode", "name", "formula_name", "formulaName", "formula", "acName")
    if isinstance(value, dict):
        for key in preferred_keys:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        for nested in value.values():
            found = find_first_formula_name(nested)
            if found:
                return found
        return None
    if isinstance(value, list):
        for item in value:
            found = find_first_formula_name(item)
            if found:
                return found
        return None
    return None


def extract_business_error(response_payload: Any) -> str | None:
    if not isinstance(response_payload, dict):
        return None

    if response_payload.get("ok") is False:
        return str(response_payload.get("error") or "未知错误")

    payload = response_payload.get("data")
    if not isinstance(payload, dict):
        return None

    error_id = payload.get("ErrorId")
    error_text = str(payload.get("Error") or "").strip()
    if error_id is not None and str(error_id) not in {"0", "0.0", ""}:
        return error_text or f"ErrorId={error_id}"
    if error_text:
        return error_text
    return None


def build_headers(token: str | None, with_auth: bool = True) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "TdxBridge-Debugger/1.0",
    }
    if with_auth and token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def http_request(
    base_url: str,
    path: str,
    method: str = "GET",
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 15.0,
    with_auth: bool = True,
) -> dict[str, Any]:
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    request = urllib.request.Request(
        url=base_url.rstrip("/") + path,
        data=body,
        headers=build_headers(token, with_auth=with_auth),
        method=method.upper(),
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = raw
            return {
                "ok": True,
                "status": response.status,
                "headers": dict(response.headers.items()),
                "data": parsed,
                "raw": raw,
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
        return {
            "ok": False,
            "status": exc.code,
            "headers": dict(exc.headers.items()),
            "data": parsed,
            "raw": raw,
            "error": f"HTTP {exc.code}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status": None,
            "headers": {},
            "data": None,
            "raw": "",
            "error": repr(exc),
        }


def classify_result(
    path: str,
    response: dict[str, Any],
    *,
    expect_block: bool = False,
    expect_validation_error: bool = False,
) -> tuple[str, str]:
    status = response.get("status")
    data = response.get("data")
    transport_error = str(response.get("error") or "").strip()
    error_text = ""
    if isinstance(data, dict):
        error_text = str(data.get("error") or data.get("detail") or "")
    elif data is not None:
        error_text = str(data)
    if status is None and transport_error:
        return "fail", f"请求未到达服务：{transport_error}"
    if expect_block:
        if status == 200 and isinstance(data, dict) and data.get("ok") is False:
            return "pass", "已命中安全拦截，未触发真实副作用。"
        if status == 422:
            return "pass", "已完成安全校验，接口可达但未触发真实动作。"
        return "fail", f"未命中预期的安全拦截，当前返回：{status} {error_text}".strip()
    if expect_validation_error:
        if status == 422:
            return "pass", "已完成安全校验，接口可达。"
        return "fail", f"未命中预期的 422 校验结果，当前返回：{status} {error_text}".strip()

    if status == 200:
        if isinstance(data, dict):
            business_error = extract_business_error(data)
            if business_error:
                return "fail", f"接口已到达后端，但业务返回失败：{business_error}"
            return "pass", "接口调用成功。"
        return "pass", "接口调用成功。"
    return "fail", f"HTTP 状态异常：{status} {error_text or transport_error}".strip()


def extract_first_dict_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value
    if isinstance(value, dict):
        for candidate in value.values():
            nested = extract_first_dict_list(candidate)
            if nested:
                return nested
    if isinstance(value, list):
        for candidate in value:
            nested = extract_first_dict_list(candidate)
            if nested:
                return nested
    return []


def resolve_formula_name(formula_list_response: dict[str, Any]) -> str | None:
    data = formula_list_response.get("data")
    if isinstance(data, dict):
        payload = data.get("data", data)
    else:
        payload = data
    return find_first_formula_name(payload)


def resolve_formula_arg_defaults(formula_info_response: dict[str, Any]) -> str | None:
    data = formula_info_response.get("data")
    if isinstance(data, dict):
        payload = data.get("Value") or data.get("data") or data
    else:
        payload = data
    if not isinstance(payload, dict):
        return None

    params = payload.get("Para")
    if not isinstance(params, list) or not params:
        return None

    defaults: list[str] = []
    for item in params:
        if not isinstance(item, dict):
            return None
        default_value = item.get("Default")
        if default_value is None:
            return None
        defaults.append(str(default_value))
    return ",".join(defaults)


def write_reports(
    project_root: Path,
    summary: dict[str, Any],
    results: list[dict[str, Any]],
) -> tuple[Path, Path]:
    logs_dir = project_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = logs_dir / f"debug-all-endpoints-{timestamp}.json"
    md_path = logs_dir / f"debug-all-endpoints-{timestamp}.md"

    payload = {
        "summary": summary,
        "results": results,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# TdxBridge 全接口调试报告",
        "",
        f"- 调试时间：{summary['timestamp']}",
        f"- 服务地址：`{summary['base_url']}`",
        f"- Token：`{summary['masked_token']}`",
        f"- 总用例数：`{summary['total']}`",
        f"- 通过：`{summary['pass']}`",
        f"- 警告：`{summary['warn']}`",
        f"- 失败：`{summary['fail']}`",
        f"- 跳过：`{summary['skip']}`",
        "",
    ]

    for item in results:
        lines.extend(
            [
                f"## {item['name']}",
                "",
                f"- 分类：`{item['kind']}`",
                f"- 判定：`{item['result']}`",
                f"- 说明：{item['message']}",
                f"- 请求：`{item['method']} {item['path']}`",
                f"- 状态码：`{item['status']}`",
                f"- 请求体摘要：`{item['request_summary']}`",
                f"- 返回摘要：`{item['response_summary']}`",
                "",
            ]
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def make_case(
    name: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None,
    kind: str,
    *,
    expect_block: bool = False,
    expect_validation_error: bool = False,
) -> dict[str, Any]:
    return {
        "name": name,
        "method": method,
        "path": path,
        "payload": payload,
        "kind": kind,
        "expect_block": expect_block,
        "expect_validation_error": expect_validation_error,
    }


def run_case(
    base_url: str,
    token: str,
    case: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    log("")
    log(f"========== {case['name']} ==========")
    log(f"[请求] {case['method']} {case['path']}")
    if case["payload"] is not None:
        log(f"[请求体] {summarize_value(case['payload'], max_len=400)}")

    response = http_request(
        base_url=base_url,
        path=case["path"],
        method=case["method"],
        token=token,
        payload=case["payload"],
        timeout=timeout,
    )
    result, message = classify_result(
        case["path"],
        response,
        expect_block=case["expect_block"],
        expect_validation_error=case["expect_validation_error"],
    )
    log(f"[状态] {response.get('status')}")
    log(f"[结果] {result} - {message}")
    log(f"[返回摘要] {summarize_value(response.get('data'), max_len=500)}")
    return {
        "name": case["name"],
        "kind": case["kind"],
        "method": case["method"],
        "path": case["path"],
        "status": response.get("status"),
        "result": result,
        "message": message,
        "request_summary": summarize_value(case["payload"]),
        "response_summary": summarize_value(response.get("data"), max_len=400),
        "response": response,
    }


def run_cases(
    base_url: str,
    token: str,
    cases: list[dict[str, Any]],
    timeout: float,
    interval_sec: float,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        if index > 0 and interval_sec > 0:
            log(f"[节流] 等待 {interval_sec:.1f} 秒，避免连续请求压垮通达信。")
            time.sleep(interval_sec)
        results.append(run_case(base_url, token, case, timeout))
    return results


def resolve_defaults(project_root: Path) -> tuple[str, str | None]:
    config_path = project_root / "config" / "bridge.json"
    base_url = "http://127.0.0.1:18888"
    token = None
    if config_path.exists():
        try:
            config = load_json_file(config_path)
            port = int(config.get("server", {}).get("port") or 18888)
            base_url = f"http://127.0.0.1:{port}"
            token_candidate = str(config.get("auth", {}).get("token") or "").strip()
            if token_candidate and token_candidate not in PLACEHOLDER_TOKENS:
                token = token_candidate
        except Exception:
            pass
    return base_url, token


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="调试 TdxBridge 全部接口（默认安全模式）")
    parser.add_argument("--project-root", default="", help="项目根目录")
    parser.add_argument("--base-url", default="", help="服务地址，例如 http://127.0.0.1:18888")
    parser.add_argument("--token", default="", help="Bearer Token")
    parser.add_argument("--timeout", type=float, default=15.0, help="单次请求超时秒数")
    parser.add_argument("--interval-sec", type=float, default=8.0, help="两次请求之间的默认等待秒数")
    parser.add_argument(
        "--include-dangerous-local-rpc",
        action="store_true",
        help="显式包含 /rpc/local get_stock_list。该请求可能拖慢或拖挂通达信，默认跳过。",
    )
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve() if args.project_root else Path(__file__).resolve().parent.parent
    default_base_url, default_token = resolve_defaults(project_root)
    base_url = (args.base_url or default_base_url).strip().rstrip("/")
    token = (args.token or default_token or "").strip()

    if not base_url:
        log("错误：缺少服务地址。")
        return 2
    if not token:
        log("错误：缺少 Bearer Token。")
        return 2

    log("TdxBridge 全接口调试开始。")
    log(f"服务地址：{base_url}")
    log(f"Bearer Token：{mask_token(token)}")
    log("说明：读接口会做真实联调；高副作用接口只做安全验证，不触发真实交易或写入。")
    log(f"默认节流间隔：{args.interval_sec:.1f} 秒")
    if not args.include_dangerous_local_rpc:
        log("安全模式：默认跳过显式 /rpc/local get_stock_list，避免拖挂通达信。")

    results: list[dict[str, Any]] = []

    health_case = make_case("健康检查", "GET", "/health", None, "health")
    health_result = run_case(base_url, token, health_case, args.timeout)
    results.append(health_result)

    capabilities_case = make_case("能力发现", "GET", "/capabilities", None, "capabilities")
    capabilities_result = run_case(base_url, token, capabilities_case, args.timeout)
    results.append(capabilities_result)

    capabilities_payload = capabilities_result.get("response", {}).get("data")
    risk_control = {}
    if isinstance(capabilities_payload, dict):
        risk_control = capabilities_payload.get("riskControl") or {}

    stock_search_case = make_case("股票搜索", "POST", "/stock/search", {"keyword": "寒武纪"}, "stock")
    stock_search_result = run_case(base_url, token, stock_search_case, args.timeout)
    results.append(stock_search_result)

    stock_code = "000001.SZ"
    stock_search_data = stock_search_result.get("response", {}).get("data")
    resolved_code = find_first_stock_code(stock_search_data)
    if resolved_code:
        stock_code = resolved_code
    log(f"[信息] 本轮后续测试使用股票代码：{stock_code}")

    primary_cases = [
        make_case("股票详情", "POST", "/stock/info", {"code": stock_code}, "stock"),
        make_case("行情 K 线", "POST", "/market/data", {"code": stock_code, "period": "1d", "count": 5}, "market"),
        make_case("行情快照", "POST", "/market/snapshot", {"code": stock_code}, "market"),
        make_case("行情扩展信息", "POST", "/market/moreInfo", {"params": {"code": stock_code}}, "market"),
        make_case("Python RPC - 用户板块", "POST", "/rpc/python", {"method": "get_user_sector", "params": {}}, "rpc"),
        make_case("Python RPC - 股票列表", "POST", "/rpc/python", {"method": "get_stock_list", "params": {"market": "5"}}, "rpc"),
        make_case("公式列表", "POST", "/formula/list", {"params": {}}, "formula"),
        make_case("资产查询", "POST", "/trade/queryAsset", {"params": {"account_id": 0}}, "trade-read"),
        make_case("持仓查询", "POST", "/trade/queryPositions", {"params": {"account_id": 0}}, "trade-read"),
        make_case("委托查询", "POST", "/trade/queryOrders", {"params": {"account_id": 0}}, "trade-read"),
        make_case("自动路由 RPC", "POST", "/rpc/auto", {"method": "get_stock_list", "params": {"market": "5"}}, "rpc"),
    ]
    if args.include_dangerous_local_rpc:
        primary_cases.append(
            make_case("本地 RPC", "POST", "/rpc/local", {"method": "get_stock_list", "params": {"market": "5"}}, "rpc")
        )
    else:
        results.append(
            {
                "name": "本地 RPC",
                "kind": "rpc",
                "method": "POST",
                "path": "/rpc/local",
                "status": None,
                "result": "skip",
                "message": "安全模式默认跳过显式 /rpc/local get_stock_list，避免拖挂通达信。",
                "request_summary": summarize_value({"method": "get_stock_list", "params": {"market": "5"}}),
                "response_summary": "",
                "response": {"status": None, "data": None},
            }
        )
    results.extend(run_cases(base_url, token, primary_cases, args.timeout, args.interval_sec))

    formula_list_response = next((item for item in results if item["name"] == "公式列表"), None)
    formula_name = None
    if formula_list_response:
        formula_name = resolve_formula_name(formula_list_response.get("response", {}))

    if formula_name:
        log(f"[信息] 本轮后续测试使用公式名称：{formula_name}")
        formula_info_case = make_case("公式详情", "POST", "/formula/info", {"name": formula_name}, "formula")
        formula_info_results = run_cases(base_url, token, [formula_info_case], args.timeout, args.interval_sec)
        results.extend(formula_info_results)
        formula_arg_defaults = resolve_formula_arg_defaults(formula_info_results[0].get("response", {}))
        if formula_arg_defaults:
            log(f"[信息] 本轮公式默认参数：{formula_arg_defaults}")

        formula_run_params: dict[str, Any] = {"name": formula_name, "code": stock_code, "period": "1d"}
        formula_batch_params: dict[str, Any] = {"name": formula_name, "codes": [stock_code], "period": "1d"}
        if formula_arg_defaults:
            formula_run_params["formula_arg"] = formula_arg_defaults
            formula_batch_params["formula_arg"] = formula_arg_defaults

        formula_run_case = make_case(
            "公式单次计算",
            "POST",
            "/formula/run",
            {"method": "formula_zb", "params": formula_run_params},
            "formula",
        )
        formula_batch_case = make_case(
            "公式批量计算",
            "POST",
            "/formula/runBatch",
            {"method": "formula_process_mul_zb", "params": formula_batch_params},
            "formula",
        )
        results.extend(run_cases(base_url, token, [formula_run_case, formula_batch_case], args.timeout, args.interval_sec))
    else:
        for name in ("公式详情", "公式单次计算", "公式批量计算"):
            results.append(
                {
                    "name": name,
                    "kind": "formula",
                    "method": "POST",
                    "path": "",
                    "status": None,
                    "result": "skip",
                    "message": "未能从公式列表中解析出公式名称，已跳过。",
                    "request_summary": "",
                    "response_summary": "",
                    "response": {},
                }
            )
            log(f"[跳过] {name}：未能从公式列表中解析出公式名称。")

    risky_cases: list[dict[str, Any]] = []
    if not risk_control.get("enableTrading", False):
        risky_cases.extend(
            [
                make_case(
                    "交易下单安全验证",
                    "POST",
                    "/trade/order",
                    {"code": stock_code, "price": 0.01, "amount": 100, "side": "buy"},
                    "trade-write",
                    expect_block=True,
                ),
                make_case(
                    "交易撤单安全验证",
                    "POST",
                    "/trade/cancel",
                    {"orderId": "DEBUG-ONLY-ORDER-ID", "code": stock_code},
                    "trade-write",
                    expect_block=True,
                ),
            ]
        )
    else:
        risky_cases.extend(
            [
                make_case("交易下单接口校验", "POST", "/trade/order", {}, "trade-write", expect_validation_error=True),
                make_case("交易撤单接口校验", "POST", "/trade/cancel", {}, "trade-write", expect_validation_error=True),
            ]
        )

    if not risk_control.get("enableWarnSend", False):
        risky_cases.append(
            make_case(
                "预警发送安全验证",
                "POST",
                "/warn/send",
                {"title": "debug", "content": "debug only"},
                "warn-write",
                expect_block=True,
            )
        )
    else:
        risky_cases.append(
            make_case("预警发送接口校验", "POST", "/warn/send", {}, "warn-write", expect_validation_error=True)
        )

    if not risk_control.get("enableBacktestSend", False):
        risky_cases.append(
            make_case(
                "回测回灌安全验证",
                "POST",
                "/backtest/send",
                {"payload": [{"code": stock_code, "note": "debug only"}]},
                "backtest-write",
                expect_block=True,
            )
        )
    else:
        risky_cases.append(
            make_case("回测回灌接口校验", "POST", "/backtest/send", {}, "backtest-write", expect_validation_error=True)
        )

    if not risk_control.get("enableBlockPush", False):
        risky_cases.append(
            make_case(
                "板块推送安全验证",
                "POST",
                "/blocks/push",
                {"action": "push", "codes": [stock_code]},
                "block-write",
                expect_block=True,
            )
        )
    else:
        risky_cases.append(
            make_case("板块推送接口校验", "POST", "/blocks/push", {"action": "push", "codes": []}, "block-write", expect_validation_error=True)
        )

    for case in risky_cases:
            results.extend(run_cases(base_url, token, [case], args.timeout, args.interval_sec))

    counters = {"pass": 0, "warn": 0, "fail": 0, "skip": 0}
    for item in results:
        result = item["result"]
        if result in counters:
            counters[result] += 1

    summary = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "base_url": base_url,
        "masked_token": mask_token(token),
        "total": len(results),
        **counters,
    }
    json_path, md_path = write_reports(project_root, summary, results)

    log("")
    log("========== 调试完成 ==========")
    log(f"通过：{counters['pass']}  警告：{counters['warn']}  失败：{counters['fail']}  跳过：{counters['skip']}")
    log(f"JSON 报告：{json_path}")
    log(f"Markdown 报告：{md_path}")

    return 1 if counters["fail"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
