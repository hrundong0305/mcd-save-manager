"""核心优化器：枚举候选 + calculate-price 实算取最小。

这是整个 Skill 唯一「动脑」的地方，且它不做价格算术 ——
每个候选方案的总价都调用 client.calculate_price 获得，只比大小。

实现红线（来自 docs/省钱管家-Skill设计.md，每条都是实测踩坑）：
  1. 一切金额只认 calculate-price 返回值；
  2. 到店不自动套券，必须显式挂券；
  3. 券生效三条件：有券 + 车里绑定的商品 + 显式传 couponId；
  4. 一单一券；套餐 + 1 张券可同单；多券同单必须拆单；
  5. BOGO 用专用 SKU，不在常规菜单里；
  6. 积分不直接抵现，只能换券再抵。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .mcp_client import BaseClient, Combo, Coupon, Item, Plan


@dataclass
class PricedPlan:
    """一个已用 calculate-price 实算过的方案。"""

    plan: Plan
    total: float
    base: float
    discount: float
    couponUsed: str | None

    @property
    def saved(self) -> float:
        return round(self.base - self.total, 2)

    @property
    def label(self) -> str:
        p = self.plan
        if p.kind == "combo":
            return f"套餐【{p.comboCode}】"
        if p.kind == "combo+coupon":
            return f"套餐【{p.comboCode}】+ 券【{p.couponId}】"
        if p.kind == "coupon":
            return f"单品 + 券【{p.couponId}】"
        return "单品（不用券）"


class Optimizer:
    """候选池枚举 + 取最小。构造时注入 client（mock 或 real 皆可）。"""

    def __init__(self, client: BaseClient):
        self._client = client

    # ---------- 候选池 ----------
    def build_plans(
        self,
        requested: list[Item],
        combos: list[Combo],
        coupons: list[Coupon],
    ) -> list[Plan]:
        """根据用户点单生成候选方案池。

        - plain        ：单品，不用券
        - coupon       ：单品 + 1 张可生效券（券绑定的商品在购物车里才进池）
        - combo        ：能覆盖 requested 的套餐
        - combo+coupon ：套餐 + 1 张可生效券（合法叠加空间）
        多券方案交给 split_orders 单独展开（一单一券）。
        """
        plans: list[Plan] = [Plan(kind="plain", items=requested)]
        req_codes = [it.productCode for it in requested]

        # 券：只保留「绑定商品在购物车里」的可生效券（红线 3）
        for c in coupons:
            if c.boundProductCode in req_codes:
                plans.append(Plan(kind="coupon", items=requested, couponId=c.couponId))

        # 套餐：覆盖 requested 全集合才进池
        for co in combos:
            if self._combo_covers(co, req_codes):
                plans.append(Plan(kind="combo", items=requested, comboCode=co.comboCode))
                # 套餐 + 1 张券（合法叠加；券绑定商品须在套餐覆盖的码里）
                for c in coupons:
                    if c.boundProductCode in co.contains:
                        plans.append(
                            Plan(
                                kind="combo+coupon",
                                items=requested,
                                comboCode=co.comboCode,
                                couponId=c.couponId,
                            )
                        )
        return plans

    @staticmethod
    def _combo_covers(co: Combo, req_codes: list[str]) -> bool:
        return set(req_codes).issubset(set(co.contains))

    # ---------- 实算 ----------
    def price_plan(self, plan: Plan) -> PricedPlan:
        """对单个候选调用 calculate-price（唯一计价来源）。

        套餐方案以套餐价计价（comboCode 传给计价器），单品方案以单品价计价。
        """
        items = list(plan.items)
        res = self._client.calculate_price(
            items, plan.couponId, combo_code=plan.comboCode
        )
        return PricedPlan(
            plan=plan,
            total=res["total"],
            base=res.get("base", res["total"]),
            discount=res.get("discount", 0.0),
            couponUsed=res.get("couponUsed"),
        )

    # ---------- 决策 ----------
    def choose_cheapest(self, plans: list[Plan]) -> PricedPlan:
        """对候选池全部实算，返回总价最低者（并保留并列首选）。"""
        if not plans:
            raise ValueError("候选池为空，无法决策")
        priced = [self.price_plan(p) for p in plans]
        return min(priced, key=lambda pp: pp.total)

    # ---------- 多券拆单（红线 4：一单一券） ----------
    def split_orders(self, requested: list[Item], coupons: list[Coupon]) -> list[list[Item]]:
        """把「想用多张券」的需求拆成多张单，每单挂一张券。

        返回若干订单（每个订单 = 该券绑定的商品清单），供 flow 逐个实算。
        """
        orders: list[list[Item]] = []
        req_codes = [it.productCode for it in requested]
        for c in coupons:
            if c.boundProductCode in req_codes:
                orders.append([Item(productCode=c.boundProductCode, name=c.title, qty=1)])
        return orders
