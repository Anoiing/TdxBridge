from __future__ import annotations

import time
from typing import Any
from urllib.parse import urljoin

import requests

from app.config import AppConfig
from app.serializers import normalize_value


class LocalRpcError(RuntimeError):
    pass


HEAVY_METHOD_TIMEOUT_OVERRIDES = {
    "get_stock_list": 25,
    "formula_get_all": 45,
    "query_stock_asset": 30,
    "query_stock_positions": 30,
    "query_stock_orders": 30,
}

RETRYABLE_READ_METHODS = {
    "get_match_stkinfo",
    "get_stock_info",
    "get_market_data",
    "get_market_snapshot",
    "get_more_info",
    "formula_get_all",
    "formula_get_info",
    "formula_zb",
    "formula_xg",
    "formula_exp",
    "formula_process_mul_zb",
    "formula_process_mul_xg",
    "formula_process_mul_exp",
    "query_stock_asset",
    "query_stock_positions",
    "query_stock_orders",
}


class LocalRpcClient:
    """通达信 TQ-Local HTTP JSON-RPC 客户端。"""

    def __init__(self, config: AppConfig):
        self._base_url = config.local_rpc.base_url.rstrip("/") + "/"
        self._timeout = config.local_rpc.timeout_sec

    def _build_payload(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": trace_id or method,
            "method": method,
            "params": params or {},
        }

    def _extract_result(self, payload: Any) -> Any:
        if isinstance(payload, dict):
            if payload.get("error"):
                raise LocalRpcError(str(payload["error"]))
            if "result" in payload:
                return payload["result"]
            if "data" in payload:
                return payload["data"]
            if "Value" in payload:
                return payload["Value"]
        return payload

    def _timeout_for_method(self, method: str) -> float:
        return float(HEAVY_METHOD_TIMEOUT_OVERRIDES.get(method, self._timeout))

    @staticmethod
    def _should_retry(method: str, error: requests.RequestException) -> bool:
        if method not in RETRYABLE_READ_METHODS:
            return False
        if isinstance(error, requests.Timeout):
            return True
        return isinstance(error, requests.ConnectionError)

    def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        timeout = self._timeout_for_method(method)
        attempts = 2 if method in RETRYABLE_READ_METHODS else 1
        last_error: requests.RequestException | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = requests.post(
                    urljoin(self._base_url, ""),
                    json=self._build_payload(method, params, trace_id),
                    timeout=timeout,
                )
                response.raise_for_status()
                payload = response.json()
                data = normalize_value(self._extract_result(payload))
                return {
                    "ok": True,
                    "backend": "local",
                    "method": method,
                    "data": data,
                    "error": None,
                }
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= attempts or not self._should_retry(method, exc):
                    break
                time.sleep(0.5)
            except (TypeError, ValueError, LocalRpcError) as exc:
                return {
                    "ok": False,
                    "backend": "local",
                    "method": method,
                    "data": None,
                    "error": f"TQ-Local 返回结果解析失败：{exc}",
                }

        if last_error is not None:
            return {
                "ok": False,
                "backend": "local",
                "method": method,
                "data": None,
                "error": f"TQ-Local 请求失败：{last_error}",
            }

        try:
            return {
                "ok": False,
                "backend": "local",
                "method": method,
                "data": None,
                "error": "TQ-Local 请求失败：未得到明确异常信息。",
            }
        except Exception as exc:
            return {
                "ok": False,
                "backend": "local",
                "method": method,
                "data": None,
                "error": f"TQ-Local 未知异常：{exc}",
            }
