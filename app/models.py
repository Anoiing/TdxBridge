from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class RpcRequest(BaseModel):
    method: str = Field(..., description="Tongdaxin method name")
    params: dict[str, Any] = Field(default_factory=dict)


class ParamsRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


class NonEmptyParamsRequest(ParamsRequest):
    @model_validator(mode="after")
    def validate_params_not_empty(self) -> "NonEmptyParamsRequest":
        merged = self.params
        to_params = getattr(self, "to_params", None)
        if callable(to_params):
            merged = to_params()
        if not merged:
            raise ValueError("params 不能为空。")
        return self


class StockSearchRequest(BaseModel):
    keyword: str | None = None
    query: str | None = None
    text: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class RouteMethodRequest(BaseModel):
    method: str = Field(..., description="桥接方法名")
    params: dict[str, Any] = Field(default_factory=dict)


class CodeQueryRequest(ParamsRequest):
    code: str | None = None
    market: str | None = None

    @model_validator(mode="after")
    def validate_code_query(self) -> "CodeQueryRequest":
        merged = self.to_params()
        if not any(key in merged for key in ("code", "stock_code", "stockCode", "symbol", "ticker")):
            raise ValueError("请求缺少股票代码，请提供 code 或等价字段。")
        return self

    def to_params(self) -> dict[str, Any]:
        params = dict(self.params)
        if self.code is not None:
            params.setdefault("code", self.code)
        if self.market is not None:
            params.setdefault("market", self.market)
        return params


class MarketDataRequest(CodeQueryRequest):
    period: str | None = None
    count: int | None = Field(default=None, gt=0)
    adjust: str | None = None
    start: str | None = None
    end: str | None = None

    def to_params(self) -> dict[str, Any]:
        params = super().to_params()
        if self.period is not None:
            params.setdefault("period", self.period)
        if self.count is not None:
            params.setdefault("count", self.count)
        if self.adjust is not None:
            params.setdefault("adjust", self.adjust)
        if self.start is not None:
            params.setdefault("start", self.start)
        if self.end is not None:
            params.setdefault("end", self.end)
        return params


class FormulaInfoRequest(ParamsRequest):
    name: str | None = None
    formula_name: str | None = Field(default=None, alias="formulaName")

    @model_validator(mode="after")
    def validate_formula_info(self) -> "FormulaInfoRequest":
        merged = self.to_params()
        if not any(key in merged for key in ("name", "formula_name", "formulaName")):
            raise ValueError("公式详情请求缺少公式名称，请提供 name 或 formulaName。")
        return self

    def to_params(self) -> dict[str, Any]:
        params = dict(self.params)
        if self.name is not None:
            params.setdefault("name", self.name)
        if self.formula_name is not None:
            params.setdefault("formula_name", self.formula_name)
        return params


class FormulaListRequest(ParamsRequest):
    category: str | None = None

    def to_params(self) -> dict[str, Any]:
        params = dict(self.params)
        if self.category is not None:
            params.setdefault("category", self.category)
        return params


class FormulaRunRequest(RouteMethodRequest):
    method: Literal["formula_zb", "formula_xg", "formula_exp"]


class FormulaBatchRunRequest(RouteMethodRequest):
    method: Literal[
        "formula_process_mul_zb",
        "formula_process_mul_xg",
        "formula_process_mul_exp",
    ]


class TradeOrderRequest(NonEmptyParamsRequest):
    code: str | None = None
    market: str | None = None
    price: float | None = Field(default=None, gt=0)
    amount: int | None = Field(default=None, gt=0)
    side: str | None = None

    @model_validator(mode="after")
    def validate_trade_order(self) -> "TradeOrderRequest":
        merged = self.to_params()
        if not any(key in merged for key in ("code", "stock_code", "stockCode")):
            raise ValueError("下单请求缺少股票代码，请提供 code 或等价字段。")
        if not any(key in merged for key in ("price", "order_price", "orderPrice")):
            raise ValueError("下单请求缺少价格，请提供 price 或等价字段。")
        if not any(key in merged for key in ("amount", "volume", "qty", "quantity")):
            raise ValueError("下单请求缺少数量，请提供 amount 或等价字段。")
        side = merged.get("side") or merged.get("action") or merged.get("direction")
        if side is not None and str(side).lower() not in {"buy", "sell", "b", "s", "1", "2"}:
            raise ValueError("下单请求 side 非法，请使用 buy / sell 或等价取值。")
        return self

    def to_params(self) -> dict[str, Any]:
        params = dict(self.params)
        if self.code is not None:
            params.setdefault("code", self.code)
        if self.market is not None:
            params.setdefault("market", self.market)
        if self.price is not None:
            params.setdefault("price", self.price)
        if self.amount is not None:
            params.setdefault("amount", self.amount)
        if self.side is not None:
            params.setdefault("side", self.side)
        return params


class TradeCancelRequest(NonEmptyParamsRequest):
    order_id: str | None = Field(default=None, alias="orderId")
    code: str | None = None

    @model_validator(mode="after")
    def validate_trade_cancel(self) -> "TradeCancelRequest":
        merged = self.to_params()
        if not any(key in merged for key in ("order_id", "orderId", "entrust_no", "contract_no", "id")):
            raise ValueError("撤单请求缺少委托标识，请提供 order_id 或等价字段。")
        return self

    def to_params(self) -> dict[str, Any]:
        params = dict(self.params)
        if self.order_id is not None:
            params.setdefault("order_id", self.order_id)
        if self.code is not None:
            params.setdefault("code", self.code)
        return params


class WarnSendRequest(NonEmptyParamsRequest):
    title: str | None = None
    content: str | None = None

    @model_validator(mode="after")
    def validate_warn_send(self) -> "WarnSendRequest":
        merged = self.to_params()
        if not any(key in merged for key in ("content", "message", "text")):
            raise ValueError("预警请求缺少内容，请提供 content 或等价字段。")
        content = merged.get("content") or merged.get("message") or merged.get("text")
        if content is not None and not str(content).strip():
            raise ValueError("预警请求内容不能为空字符串。")
        return self

    def to_params(self) -> dict[str, Any]:
        params = dict(self.params)
        if self.title is not None:
            params.setdefault("title", self.title)
        if self.content is not None:
            params.setdefault("content", self.content)
        return params


class BacktestSendRequest(NonEmptyParamsRequest):
    payload: dict[str, Any] | list[dict[str, Any]] | None = None

    @model_validator(mode="after")
    def validate_backtest_send(self) -> "BacktestSendRequest":
        merged = self.to_params()
        if not merged:
            raise ValueError("回测回灌请求不能为空。")
        payload = merged.get("payload", merged)
        if isinstance(payload, list) and not payload:
            raise ValueError("回测回灌 payload 不能为空列表。")
        if isinstance(payload, dict) and not payload:
            raise ValueError("回测回灌 payload 不能为空对象。")
        return self

    def to_params(self) -> dict[str, Any]:
        params = dict(self.params)
        if self.payload is not None:
            params.setdefault("payload", self.payload)
        return params


class BlockPushRequest(NonEmptyParamsRequest):
    action: Literal["push", "create_sector"] = "push"
    codes: list[str] = Field(default_factory=list)
    name: str | None = None

    @model_validator(mode="after")
    def validate_block_push(self) -> "BlockPushRequest":
        merged = self.to_params()
        if self.action == "push":
            if not any(key in merged for key in ("codes", "code", "stock_list", "stockList")):
                raise ValueError("板块推送缺少股票代码，请提供 codes 或等价字段。")
            codes = merged.get("codes") or merged.get("stock_list") or merged.get("stockList")
            code = merged.get("code")
            if codes is not None and isinstance(codes, list) and not codes:
                raise ValueError("板块推送 codes 不能为空列表。")
            if code is not None and not str(code).strip():
                raise ValueError("板块推送 code 不能为空字符串。")
        else:
            if not any(key in merged for key in ("name", "sector_name", "sectorName")):
                raise ValueError("创建板块缺少名称，请提供 name 或等价字段。")
            name = merged.get("name") or merged.get("sector_name") or merged.get("sectorName")
            if name is not None and not str(name).strip():
                raise ValueError("创建板块名称不能为空字符串。")
        return self

    def to_params(self) -> dict[str, Any]:
        params = dict(self.params)
        if self.codes:
            params.setdefault("codes", self.codes)
        if self.name is not None:
            params.setdefault("name", self.name)
        return params


class ApiResponse(BaseModel):
    ok: bool
    backend: str | None = None
    method: str | None = None
    data: Any = None
    error: str | None = None
    trace_id: str | None = Field(default=None, alias="traceId")
    meta: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}
