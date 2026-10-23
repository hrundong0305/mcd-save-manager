"""麦当劳 MCP 客户端适配层。

- `MockClient`：零依赖离线实现，用于无 Token 自测 / 演示 / 单测。
- `RealClient`：薄封装官方 mcd-mcp（Streamable HTTP），懒加载官方 `mcp` SDK。
  真实模式下，Tool 名与 MCP_INTEGRATION.md 校准表完全一致。

统一的业务方法签名，让 flow / optimizer 与运行模式解耦。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import mock_data as mock
from .config import Config


# ---------- 轻量数据对象 ----------
@dataclass
class Item:
    productCode: str
    name: str
    qty: int = 1


@dataclass
class Coupon:
    couponId: str
    title: str
    boundProductCode: str
    discount: float = 0.0
    source: str = "store"  # store 到店可用券 / card 卡包券
    expiresAt: str = ""


@dataclass
class Combo:
    comboCode: str
    name: str
    price: float
    contains: dict = field(default_factory=dict)  # {productCode: qty}


@dataclass
class Plan:
    """一个待比价的候选「订单方案」。"""

    kind: str          # plain / coupon / combo / combo+coupon
    items: list[Item]
    couponId: str | None = None
    comboCode: str | None = None


# ---------- 客户端 ----------
class BaseClient:
    mode = "base"

    def nearby_stores(self, *args, **kw):
        raise NotImplementedError

    def meals(self, store=None):
        raise NotImplementedError

    def meal_detail(self, product_code):
        raise NotImplementedError

    def coupons(self, store=None):
        raise NotImplementedError

    def bind_all_available(self):
        """麦麦省一键领全部可领券（自动领券）。"""
        raise NotImplementedError

    def calculate_price(self, items, coupon_id=None, combo_code=None):
        raise NotImplementedError

    def my_points(self):
        raise NotImplementedError

    def nutrition(self):
        raise NotImplementedError

    def now_time(self):
        raise NotImplementedError


class MockClient(BaseClient):
    mode = "mock"

    def nearby_stores(self, *args, **kw):
        return [{"storeCode": "M0001", "name": "演示店(线下)", "address": "广州·mock"}]

    def meals(self, store=None):
        return mock.MEALS

    def meal_detail(self, product_code):
        for m in mock.MEALS:
            if m["productCode"] == product_code:
                return m
        raise KeyError(product_code)

    def coupons(self, store=None):
        return [Coupon(**c) for c in mock.COUPONS]

    def bind_all_available(self):
        return {"bound": [c["couponId"] for c in mock.COUPONS if c["source"] == "store"]}

    def calculate_price(self, items, coupon_id=None, combo_code=None):
        payload = [{"productCode": it.productCode, "qty": it.qty} for it in items]
        return mock.mock_calculate_price(payload, coupon_id, combo_code)

    def my_points(self):
        return mock.ACCOUNT

    def nutrition(self):
        return mock.NUTRITION

    def now_time(self):
        return {"datetime": "2026-10-24 12:00:00", "weekday": "Saturday"}


class RealClient(BaseClient):
    """官方 mcd-mcp 薄封装。需要 `mcp` 依赖：pip install "mcp[cli]"。

    说明：接入方式为 Streamable HTTP（https://mcp.mcd.cn），
    鉴权头 Authorization: Bearer <token>。Tool 名已按 MCP_INTEGRATION.md 校准。
    """

    mode = "real"

    def __init__(self, cfg: Config):
        self._cfg = cfg
        self._session = None
        try:
            from mcp.client.streamable_http import streamablehttp_client
            from mcp import ClientSession

            self._streamablehttp_client = streamablehttp_client
            self._ClientSession = ClientSession
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "real 模式需要安装 mcp SDK：pip install 'mcp[cli]'"
            ) from exc

    async def _ensure(self):
        if self._session is not None:
            return self._session
        url = self._cfg.url
        headers = {"Authorization": f"Bearer {self._cfg.token}"}
        # 官方 SDK 支持自定义请求头：url 上暂不支持携带 header，见 mcp 文档
        ctx = self._streamablehttp_client(url, headers=headers)
        self._exit_stack = ctx
        s = self._ClientSession(await ctx.__aenter__())
        await s.initialize()
        self._session = s
        return s

    async def _call(self, tool, args):
        s = await self._ensure()
        res = await s.call_tool(tool, args)
        # MCP 返回 content 列表，这里统一收成 dict（结构因 Tool 而异，按需扩展）
        return res

    def meals(self, store=None):
        import asyncio
        return asyncio.run(self._call("query-meals", {}))

    def calculate_price(self, items, coupon_id=None, combo_code=None):
        import asyncio
        args = {"items": [{"productCode": it.productCode, "qty": it.qty} for it in items]}
        if coupon_id:
            args["couponId"] = coupon_id
        if combo_code:
            args["comboCode"] = combo_code
        return asyncio.run(self._call("calculate-price", args))

    def coupons(self, store=None):
        import asyncio
        return asyncio.run(self._call("query-store-coupons", {}))

    # 其余 Tool 按同一模式扩展（query-meals / query-meal-detail / auto-bind-coupons /
    # query-my-coupons / query-my-account / mall-* / list-nutrition-foods /
    # query-meal-assistance / create-order / now-time-info）


def make_client(cfg: Config) -> BaseClient:
    if cfg.mode == "mock":
        return MockClient()
    return RealClient(cfg)
