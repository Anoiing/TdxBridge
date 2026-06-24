from __future__ import annotations

from dataclasses import dataclass

from app.config import AppConfig


@dataclass(frozen=True)
class MethodPolicy:
    backend: str
    category: str
    write_action: str | None = None


METHOD_POLICIES: dict[str, MethodPolicy] = {
    "get_match_stkinfo": MethodPolicy("local", "stock"),
    "get_stock_info": MethodPolicy("local", "stock"),
    "get_stock_list": MethodPolicy("python", "stock"),
    "get_market_data": MethodPolicy("local", "market"),
    "get_market_snapshot": MethodPolicy("local", "market"),
    "get_more_info": MethodPolicy("local", "market"),
    "formula_get_all": MethodPolicy("local", "formula"),
    "formula_get_info": MethodPolicy("local", "formula"),
    "formula_zb": MethodPolicy("local", "formula"),
    "formula_xg": MethodPolicy("local", "formula"),
    "formula_exp": MethodPolicy("local", "formula"),
    "formula_process_mul_zb": MethodPolicy("local", "formula"),
    "formula_process_mul_xg": MethodPolicy("local", "formula"),
    "formula_process_mul_exp": MethodPolicy("local", "formula"),
    "query_stock_asset": MethodPolicy("local", "trade"),
    "query_stock_positions": MethodPolicy("local", "trade"),
    "query_stock_orders": MethodPolicy("local", "trade"),
    "order_stock": MethodPolicy("local", "trade", "trading"),
    "cancel_order_stock": MethodPolicy("local", "trade", "trading"),
    "send_user_block": MethodPolicy("python", "block", "block_push"),
    "create_sector": MethodPolicy("python", "block", "block_push"),
    "send_warn": MethodPolicy("python", "warn", "warn_send"),
    "send_bt_data": MethodPolicy("python", "backtest", "backtest_send"),
    "price_df": MethodPolicy("python", "market"),
}


WRITE_ACTION_MESSAGES = {
    "trading": "交易写操作当前未开启，请先打开 enable_trading。",
    "block_push": "板块推送当前未开启，请先打开 enable_block_push。",
    "warn_send": "预警发送当前未开启，请先打开 enable_warn_send。",
    "backtest_send": "回测回灌当前未开启，请先打开 enable_backtest_send。",
}


def choose_backend(method: str) -> str:
    policy = METHOD_POLICIES.get(method)
    if policy:
        return policy.backend
    return "auto"


def get_method_policy(method: str) -> MethodPolicy | None:
    return METHOD_POLICIES.get(method)


def is_write_method(method: str) -> bool:
    policy = get_method_policy(method)
    return bool(policy and policy.write_action)


def validate_method_access(config: AppConfig, method: str) -> str | None:
    policy = get_method_policy(method)
    if not policy or not policy.write_action:
        return None

    if policy.write_action == "trading" and not config.risk_control.enable_trading:
        return WRITE_ACTION_MESSAGES["trading"]
    if policy.write_action == "block_push" and not config.risk_control.enable_block_push:
        return WRITE_ACTION_MESSAGES["block_push"]
    if policy.write_action == "warn_send" and not config.risk_control.enable_warn_send:
        return WRITE_ACTION_MESSAGES["warn_send"]
    if policy.write_action == "backtest_send" and not config.risk_control.enable_backtest_send:
        return WRITE_ACTION_MESSAGES["backtest_send"]
    return None


def supported_methods() -> dict[str, dict[str, str | None]]:
    return {
        method: {
            "backend": policy.backend,
            "category": policy.category,
            "writeAction": policy.write_action,
        }
        for method, policy in METHOD_POLICIES.items()
    }
