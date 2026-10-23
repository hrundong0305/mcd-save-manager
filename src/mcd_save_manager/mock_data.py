"""离线 mock 数据源：让省钱管家在【没有任何 Token】时也能跑通并自测。

所有价格 / 折扣 / 积分都是确定性常量，保证同场景两次调用报价一致（验收清单要求）。
真实模式下这些数据全部来自麦当劳 MCP，本文件不参与。
"""

from __future__ import annotations

# ---- 餐品（productCode 与 SKU 名，价格单位为「元」） ----
MEALS = [
    {"productCode": "100001", "name": "巨无霸", "price": 25.0, "tags": ["汉堡"]},
    {"productCode": "100002", "name": "中薯条", "price": 11.5, "tags": ["小食"]},
    {"productCode": "100003", "name": "中杯可乐", "price": 10.0, "tags": ["饮品"]},
    {"productCode": "100004", "name": "麦辣鸡翅(2块)", "price": 13.0, "tags": ["小食"]},
    {"productCode": "100005", "name": "麦旋风", "price": 12.0, "tags": ["甜品"]},
    # 买一送一专用 SKU（BOGO，不在常规菜单枚举里，需专用码下单）
    {"productCode": "9900012387", "name": "中薯条买一送一", "price": 11.5, "tags": ["bogo"]},
]

# ---- 套餐（组合覆盖 requested 集合时更省） ----
COMBOS = [
    {
        "comboCode": "C001",
        "name": "巨无霸套餐",
        "price": 32.0,
        "contains": {"100001": 1, "100002": 1, "100003": 1},  # 巨无霸 + 中薯 + 可乐
    },
]

# ---- 优惠券（一单只能挂一张；绑定的商品必须在购物车里才生效） ----
COUPONS = [
    {
        "couponId": "CPN001",
        "title": "麦辣鸡翅立减3元",
        "boundProductCode": "100004",
        "discount": 3.0,
        "source": "store",  # 到店可用券
    },
    {
        "couponId": "CPN002",
        "title": "中薯条买一送一",
        "boundProductCode": "9900012387",  # BOGO 专用 SKU
        "discount": 11.5,
        "source": "card",  # 卡包券
    },
]

# ---- 积分（不直接抵现，只能换券再抵） ----
ACCOUNT = {"points": 1200, "pointsToCouponRate": 200}  # 1200 积分可换 6 张（演示）

# ---- 营养（热量约束用，只覆盖 mock 菜单） ----
NUTRITION = [
    {"productCode": "100001", "name": "巨无霸", "calories": 563},
    {"productCode": "100002", "name": "中薯条", "calories": 342},
    {"productCode": "100003", "name": "中杯可乐", "calories": 210},
    {"productCode": "100004", "name": "麦辣鸡翅(2块)", "calories": 450},
    {"productCode": "100005", "name": "麦旋风", "calories": 410},
    {"productCode": "9900012387", "name": "中薯条买一送一", "calories": 342},
]


def lookup_price(product_code: str) -> float:
    """确定性单价；找不到就抛错，绝不静默给 0（红线：宁可信不过，不信错）。"""
    for m in MEALS:
        if m["productCode"] == product_code:
            return m["price"]
    raise KeyError(f"mock 菜单中不存在 productCode={product_code}")


def mock_calculate_price(
    items: list[dict],
    coupon_id: str | None = None,
    combo_code: str | None = None,
) -> dict:
    """离线计价器：模拟 MCP calculate-price 的返回结构。

    - 单品方案：base = items 单价之和；
    - 套餐方案：base = 套餐一口价（套餐价盖过单品价）；
    两者都最多扣一张券面额。返回确定性结果。
    真实模式下绝不调用本函数 —— 一切金额只认线上 calculate-price 返回值。
    """
    if combo_code is not None:
        combo = next((c for c in COMBOS if c["comboCode"] == combo_code), None)
        if combo is None:
            raise KeyError(f"mock 中不存在 comboCode={combo_code}")
        base = combo["price"]
        cart_codes = set(combo["contains"])
    else:
        base = sum(lookup_price(it["productCode"]) * it.get("qty", 1) for it in items)
        cart_codes = {it["productCode"] for it in items}

    coupon_used = None
    discount = 0.0
    if coupon_id is not None:
        c = next((x for x in COUPONS if x["couponId"] == coupon_id), None)
        if c is None:
            raise KeyError(f"mock 中不存在 couponId={coupon_id}")
        # 红线：券绑定的商品必须在购物车里（缺一个条件，优惠视为 0）
        if c["boundProductCode"] in cart_codes:
            coupon_used = coupon_id
            discount = c["discount"]

    total = round(base - discount, 2)
    return {
        "total": total,
        "base": round(base, 2),
        "discount": round(discount, 2),
        "couponUsed": coupon_used,
        "currency": "CNY",
        "items": items,
        "comboCode": combo_code,
    }
