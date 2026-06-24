from __future__ import annotations

from typing import Any


BUY_SIDE_VALUES = {"buy", "b", "1"}
SELL_SIDE_VALUES = {"sell", "s", "2"}
PERIOD_ALIASES = {
    "1": "1m",
    "1m": "1m",
    "1min": "1m",
    "5": "5m",
    "5m": "5m",
    "5min": "5m",
    "15": "15m",
    "15m": "15m",
    "15min": "15m",
    "30": "30m",
    "30m": "30m",
    "30min": "30m",
    "60": "1h",
    "60m": "1h",
    "60min": "1h",
    "1h": "1h",
    "day": "1d",
    "daily": "1d",
    "d": "1d",
    "1d": "1d",
    "week": "1w",
    "weekly": "1w",
    "w": "1w",
    "1w": "1w",
    "month": "1mon",
    "monthly": "1mon",
    "1mon": "1mon",
    "quarter": "1q",
    "1q": "1q",
    "year": "1y",
    "yearly": "1y",
    "1y": "1y",
    "tick": "tick",
}
MARKET_ALIASES = {
    "SZ": "0",
    "SH": "1",
    "BJ": "2",
    "ALL": "5",
    "A": "5",
    "A_SHARE": "5",
    "A-SHARE": "5",
}
FORMULA_TYPE_ALIASES = {
    "0": 0,
    "ZB": 0,
    "INDICATOR": 0,
    "指标": 0,
    "1": 1,
    "XG": 1,
    "SELECT": 1,
    "STOCK_SELECT": 1,
    "选股": 1,
    "2": 2,
    "EXP": 2,
    "EXPERT": 2,
    "专家": 2,
}


def _first_value(params: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in params and params[key] is not None:
            return params[key]
    return None


def _normalize_code_value(code: Any) -> tuple[str | None, str | None]:
    if code is None:
        return None, None
    code_text = str(code).strip()
    if not code_text:
        return None, None

    if "." in code_text:
        base, suffix = code_text.rsplit(".", maxsplit=1)
        suffix = suffix.upper()
        if suffix in {"SH", "SZ", "BJ"}:
            return base, suffix
    return code_text, None


def _normalize_side_value(side: Any) -> tuple[str | None, int | None]:
    if side is None:
        return None, None
    side_text = str(side).strip().lower()
    if side_text in BUY_SIDE_VALUES:
        return "buy", 1
    if side_text in SELL_SIDE_VALUES:
        return "sell", 2
    return None, None


def _normalize_formula_type(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value if value in {0, 1, 2} else None
    text = str(value).strip().upper()
    return FORMULA_TYPE_ALIASES.get(text)


def _normalize_formula_arg_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text if text else ""
    if isinstance(value, (list, tuple)):
        return ",".join("" if item is None else str(item) for item in value)
    return str(value).strip()


def _normalize_formula_dividend_type(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value if value in {0, 1, 2} else 0
    text = str(value).strip().lower()
    if text in {"1", "front", "qfq"}:
        return 1
    if text in {"2", "back", "hfq"}:
        return 2
    return 0


def adapt_common_stock_params(params: dict[str, Any]) -> dict[str, Any]:
    adapted = dict(params)
    raw_code = _first_value(adapted, ("code", "stock_code", "stockCode", "symbol", "ticker"))
    normalized_code, inferred_market = _normalize_code_value(raw_code)
    preferred_code: str | None = None
    if raw_code is not None:
        raw_code_text = str(raw_code).strip()
        adapted["raw_code"] = raw_code_text
        adapted["code"] = raw_code_text
        preferred_code = raw_code_text if inferred_market else normalized_code
    elif normalized_code:
        preferred_code = normalized_code
    if preferred_code:
        adapted["stock_code"] = preferred_code
        adapted["stockCode"] = preferred_code
        adapted["symbol"] = preferred_code
        adapted["ticker"] = preferred_code
        adapted["codestr"] = preferred_code
    if normalized_code:
        adapted["plain_code"] = normalized_code
    if inferred_market:
        adapted.setdefault("market", inferred_market)
        adapted.setdefault("market_code", inferred_market)
        adapted.setdefault("marketCode", inferred_market)
    return adapted


def adapt_trade_order_params(params: dict[str, Any]) -> dict[str, Any]:
    adapted = adapt_common_stock_params(params)
    side = _first_value(adapted, ("side", "action", "direction"))
    normalized_side, side_code = _normalize_side_value(side)
    if normalized_side:
        adapted["side"] = normalized_side
        adapted.setdefault("action", normalized_side)
        adapted.setdefault("direction", side_code)
    amount = _first_value(adapted, ("amount", "volume", "qty", "quantity"))
    if amount is not None:
        adapted.setdefault("amount", amount)
        adapted.setdefault("volume", amount)
        adapted.setdefault("qty", amount)
        adapted.setdefault("quantity", amount)
    price = _first_value(adapted, ("price", "order_price", "orderPrice"))
    if price is not None:
        adapted.setdefault("price", price)
        adapted.setdefault("order_price", price)
        adapted.setdefault("orderPrice", price)
    return adapted


def adapt_trade_cancel_params(params: dict[str, Any]) -> dict[str, Any]:
    adapted = adapt_common_stock_params(params)
    order_id = _first_value(adapted, ("order_id", "orderId", "entrust_no", "contract_no", "id"))
    if order_id is not None:
        adapted.setdefault("order_id", order_id)
        adapted.setdefault("orderId", order_id)
        adapted.setdefault("entrust_no", order_id)
        adapted.setdefault("contract_no", order_id)
        adapted.setdefault("id", order_id)
    return adapted


def adapt_warn_send_params(params: dict[str, Any]) -> dict[str, Any]:
    adapted = dict(params)
    content = _first_value(adapted, ("content", "message", "text"))
    if content is not None:
        adapted.setdefault("content", content)
        adapted.setdefault("message", content)
        adapted.setdefault("text", content)
    title = _first_value(adapted, ("title", "subject"))
    if title is not None:
        adapted.setdefault("title", title)
        adapted.setdefault("subject", title)
    return adapted


def adapt_backtest_send_params(params: dict[str, Any]) -> dict[str, Any]:
    adapted = dict(params)
    payload = _first_value(adapted, ("payload", "data", "records"))
    if payload is not None:
        adapted.setdefault("payload", payload)
        adapted.setdefault("data", payload)
        adapted.setdefault("records", payload)
    return adapted


def adapt_block_push_params(params: dict[str, Any]) -> dict[str, Any]:
    adapted = dict(params)
    codes = _first_value(adapted, ("codes", "stock_list", "stockList"))
    code = adapted.get("code")
    if codes is not None:
        adapted.setdefault("codes", codes)
        adapted.setdefault("stock_list", codes)
        adapted.setdefault("stockList", codes)
    elif code is not None:
        adapted.setdefault("codes", [code])
        adapted.setdefault("stock_list", [code])
        adapted.setdefault("stockList", [code])

    name = _first_value(adapted, ("name", "sector_name", "sectorName", "block_name", "blockName"))
    if name is not None:
        adapted.setdefault("name", name)
        adapted.setdefault("sector_name", name)
        adapted.setdefault("sectorName", name)
        adapted.setdefault("block_name", name)
        adapted.setdefault("blockName", name)
    return adapt_common_stock_params(adapted)


def adapt_formula_params(params: dict[str, Any], method: str | None = None) -> dict[str, Any]:
    adapted = adapt_common_stock_params(params)
    name = _first_value(adapted, ("name", "formula_name", "formulaName", "formula"))
    if name is not None:
        adapted.setdefault("name", name)
        adapted.setdefault("formula_name", name)
        adapted.setdefault("formulaName", name)
        adapted.setdefault("formula", name)
        if method == "formula_get_info":
            adapted.setdefault("formula_code", name)
            adapted.setdefault("formulaCode", name)

    formula_code = _first_value(adapted, ("formula_code", "formulaCode"))
    if formula_code is not None:
        adapted.setdefault("formula_code", formula_code)
        adapted.setdefault("formulaCode", formula_code)

    formula_type = _first_value(adapted, ("formula_type", "formulaType", "category", "type"))
    normalized_formula_type = _normalize_formula_type(formula_type)
    if normalized_formula_type is not None:
        adapted["formula_type"] = normalized_formula_type
        adapted.setdefault("formulaType", normalized_formula_type)
        adapted.setdefault("category", normalized_formula_type)
        adapted.setdefault("type", normalized_formula_type)

    formula_arg = _first_value(adapted, ("formula_arg", "formulaArg", "arg", "args", "parameters"))
    normalized_formula_arg = _normalize_formula_arg_value(formula_arg)
    if normalized_formula_arg is not None:
        adapted["formula_arg"] = normalized_formula_arg
        adapted.setdefault("formulaArg", normalized_formula_arg)
        adapted.setdefault("arg", normalized_formula_arg)

    xsflag = _first_value(adapted, ("xsflag", "xsFlag"))
    if xsflag is not None:
        adapted.setdefault("xsflag", xsflag)
        adapted.setdefault("xsFlag", xsflag)

    stock_list = _first_value(adapted, ("stock_list", "stockList", "codes"))
    if stock_list is None:
        stock_code = _first_value(adapted, ("stock_code", "stockCode", "code", "symbol", "ticker"))
        if stock_code is not None:
            stock_list = [stock_code]
    if stock_list is not None:
        adapted["stock_list"] = stock_list
        adapted.setdefault("stockList", stock_list)
        adapted.setdefault("codes", stock_list)

    period = _first_value(adapted, ("stock_period", "stockPeriod", "period", "cycle", "kline_type", "klineType", "freq"))
    if period is not None:
        period_text = str(period).strip()
        normalized_period = PERIOD_ALIASES.get(period_text.lower(), period_text)
        adapted["stock_period"] = normalized_period
        adapted.setdefault("stockPeriod", normalized_period)
        adapted.setdefault("period", normalized_period)
        adapted.setdefault("cycle", normalized_period)
        adapted.setdefault("kline_type", normalized_period)
        adapted.setdefault("klineType", normalized_period)
        adapted.setdefault("freq", normalized_period)

    start = _first_value(adapted, ("start", "start_date", "startDate", "begin", "start_time"))
    end = _first_value(adapted, ("end", "end_date", "endDate", "finish", "end_time"))
    if start is not None:
        adapted["start_time"] = start
        adapted.setdefault("start", start)
        adapted.setdefault("start_date", start)
        adapted.setdefault("startDate", start)
        adapted.setdefault("begin", start)
    if end is not None:
        adapted["end_time"] = end
        adapted.setdefault("end", end)
        adapted.setdefault("end_date", end)
        adapted.setdefault("endDate", end)
        adapted.setdefault("finish", end)

    count = _first_value(adapted, ("count", "limit", "size"))
    if count is not None:
        adapted.setdefault("count", count)
        adapted.setdefault("limit", count)
        adapted.setdefault("size", count)

    return_count = _first_value(adapted, ("return_count", "returnCount"))
    if return_count is not None:
        adapted["return_count"] = return_count
        adapted.setdefault("returnCount", return_count)

    return_date = _first_value(adapted, ("return_date", "returnDate"))
    if return_date is not None:
        adapted["return_date"] = return_date
        adapted.setdefault("returnDate", return_date)

    dividend_type = _first_value(adapted, ("dividend_type", "dividendType", "adjust", "fq", "adjust_type", "adjustType"))
    if dividend_type is not None or method in {"formula_set_data_info", "formula_process_mul_zb", "formula_process_mul_xg", "formula_process_mul_exp"}:
        normalized_dividend_type = _normalize_formula_dividend_type(dividend_type)
        adapted["dividend_type"] = normalized_dividend_type
        adapted.setdefault("dividendType", normalized_dividend_type)
    return adapted


def adapt_market_data_params(params: dict[str, Any]) -> dict[str, Any]:
    adapted = adapt_common_stock_params(params)
    stock_list = _first_value(adapted, ("stock_list", "stockList"))
    if stock_list is None:
        stock_code = _first_value(adapted, ("stock_code", "stockCode", "code", "symbol", "ticker"))
        if stock_code is not None:
            adapted["stock_list"] = [stock_code]
            adapted.setdefault("stockList", [stock_code])
    period = _first_value(adapted, ("period", "cycle", "kline_type", "klineType", "freq"))
    if period is not None:
        period_text = str(period).strip()
        normalized_period = PERIOD_ALIASES.get(period_text.lower(), period_text.upper())
        adapted["period"] = normalized_period
        adapted.setdefault("cycle", normalized_period)
        adapted.setdefault("kline_type", normalized_period)
        adapted.setdefault("klineType", normalized_period)
        adapted.setdefault("freq", normalized_period)
    count = _first_value(adapted, ("count", "limit", "size"))
    if count is not None:
        adapted.setdefault("count", count)
        adapted.setdefault("limit", count)
        adapted.setdefault("size", count)
    adjust = _first_value(adapted, ("adjust", "fq", "adjust_type", "adjustType"))
    if adjust is not None:
        adjust_text = str(adjust).strip().lower()
        if adjust_text in {"qfq", "front"}:
            normalized_adjust = "front"
        elif adjust_text in {"hfq", "back"}:
            normalized_adjust = "back"
        else:
            normalized_adjust = "none"
        adapted["adjust"] = normalized_adjust
        adapted.setdefault("fq", normalized_adjust)
        adapted.setdefault("adjust_type", normalized_adjust)
        adapted.setdefault("adjustType", normalized_adjust)
        adapted.setdefault("dividend_type", normalized_adjust)
    else:
        adapted.setdefault("dividend_type", "none")
    start = _first_value(adapted, ("start", "start_date", "startDate", "begin"))
    end = _first_value(adapted, ("end", "end_date", "endDate", "finish"))
    if start is not None:
        adapted.setdefault("start", start)
        adapted.setdefault("start_date", start)
        adapted.setdefault("startDate", start)
        adapted.setdefault("begin", start)
        adapted.setdefault("start_time", start)
    if end is not None:
        adapted.setdefault("end", end)
        adapted.setdefault("end_date", end)
        adapted.setdefault("endDate", end)
        adapted.setdefault("finish", end)
        adapted.setdefault("end_time", end)
    return adapted


def adapt_stock_params(params: dict[str, Any]) -> dict[str, Any]:
    adapted = adapt_common_stock_params(params)
    keyword = _first_value(adapted, ("keyword", "name", "query", "text"))
    if keyword is not None:
        adapted.setdefault("keyword", keyword)
        adapted.setdefault("query", keyword)
        adapted.setdefault("text", keyword)
    return adapted


def adapt_match_stock_params(params: dict[str, Any]) -> dict[str, Any]:
    adapted = dict(params)
    keyword = _first_value(adapted, ("key_word", "keyword", "name", "query", "text"))
    if keyword is not None:
        adapted["key_word"] = keyword
        adapted.setdefault("keyword", keyword)
        adapted.setdefault("query", keyword)
        adapted.setdefault("text", keyword)
    return adapted


def adapt_stock_list_params(params: dict[str, Any]) -> dict[str, Any]:
    adapted = dict(params)
    market = _first_value(adapted, ("market", "market_code", "marketCode"))
    if market is not None:
        market_text = str(market).strip().upper()
        normalized_market = MARKET_ALIASES.get(market_text, market_text)
        adapted["market"] = normalized_market
        adapted.setdefault("market_code", normalized_market)
        adapted.setdefault("marketCode", normalized_market)
    else:
        adapted["market"] = "5"
        adapted.setdefault("market_code", "5")
        adapted.setdefault("marketCode", "5")

    list_type = _first_value(adapted, ("list_type", "listType", "type"))
    normalized_list_type = str(list_type).strip().upper() if list_type is not None else "ALL"
    adapted["list_type"] = normalized_list_type
    adapted.setdefault("listType", normalized_list_type)
    adapted.setdefault("type", normalized_list_type)
    return adapted


def adapt_trade_query_params(params: dict[str, Any]) -> dict[str, Any]:
    adapted = dict(params)
    account_id = _first_value(adapted, ("account_id", "accountId"))
    if account_id is None:
        adapted["account_id"] = 0
        adapted.setdefault("accountId", 0)
    else:
        adapted.setdefault("account_id", account_id)
        adapted.setdefault("accountId", account_id)
    return adapted


def adapt_method_params(
    method: str,
    params: dict[str, Any] | None,
    *,
    backend: str | None = None,
) -> dict[str, Any]:
    current = dict(params or {})
    if method == "get_stock_list":
        if backend == "python":
            return current
        return adapt_stock_list_params(current)
    if method == "get_match_stkinfo":
        return adapt_match_stock_params(current)
    if method in {"get_stock_info", "get_more_info", "get_market_snapshot"}:
        return adapt_stock_params(current)
    if method == "get_market_data":
        return adapt_market_data_params(current)
    if method in {
        "formula_get_all",
        "formula_get_info",
        "formula_set_data_info",
        "formula_get_data",
        "formula_zb",
        "formula_xg",
        "formula_exp",
        "formula_process_mul_zb",
        "formula_process_mul_xg",
        "formula_process_mul_exp",
    }:
        return adapt_formula_params(current, method)
    if method == "order_stock":
        return adapt_trade_order_params(current)
    if method == "cancel_order_stock":
        return adapt_trade_cancel_params(current)
    if method in {"query_stock_asset", "query_stock_positions", "query_stock_orders"}:
        return adapt_trade_query_params(current)
    if method == "send_warn":
        return adapt_warn_send_params(current)
    if method == "send_bt_data":
        return adapt_backtest_send_params(current)
    if method in {"send_user_block", "create_sector"}:
        return adapt_block_push_params(current)
    if method == "price_df":
        return adapt_common_stock_params(current)
    return current
