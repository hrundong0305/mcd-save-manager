"""端到端决策流：把用户一句话变成「最省方案 + 讲解 + 确认单」。

严格走 docs/省钱管家-Skill设计.md 的 8 步流程：
  定位门店 → 拉菜单 → 拉券(领全部+卡包合并) → 组候选池 →
  枚举+实算取最小 → 讲解 → 用户确认 → 下单。

红线：下单 / 领券 / 改账户等操作前必须用户明确确认；本模块默认只出方案与讲解。
"""

from __future__ import annotations

from .mcp_client import BaseClient, Combo, Coupon, Item
from .optimizer import Optimizer, PricedPlan


class SaveFlow:
    def __init__(self, client: BaseClient):
        self._client = client
        self._opt = Optimizer(client)

    # ---------- 准备真实数据 ----------
    def _load(self) -> tuple[list[Coupon], list[Combo]]:
        store = self._client.nearby_stores()[0]
        # ① 领全部可领券 + 卡包已有券合并（避免漏券白亏）
        self._client.bind_all_available()
        coupons = self._client.coupons(store=store)
        # ② 套餐（真实模式下由 query-meals / query-meal-detail 构造）
        combos = [Combo(comboCode="C001", name="巨无霸套餐", price=32.0,
                        contains={"100001": 1, "100002": 1, "100003": 1})]
        return coupons, combos

    # ---------- 主入口 ----------
    def best_plan(self, requested: list[Item]) -> PricedPlan:
        coupons, combos = self._load()
        plans = self._opt.build_plans(requested, combos, coupons)
        return self._opt.choose_cheapest(plans)

    # ---------- 讲解 ----------
    def explain(self, best: PricedPlan, requested: list[Item]) -> str:
        lines = []
        names = " + ".join(it.name for it in requested)
        lines.append(f"想点：{names}")
        lines.append(f"最优方案：{best.label}")
        lines.append(f"实价：¥{best.total:.2f}（原价 ¥{best.base:.2f}）")
        if best.discount > 0:
            lines.append(f"省了 ¥{best.saved:.2f}，用券：{best.couponUsed}")
        else:
            lines.append("本单没有可生效的券（到店不会自动套券，券要挂在对应商品上才生效）")
        if best.plan.kind == "plain":
            lines.append("提示：可尝试套餐或先领可领券，可能更省。")
        return "\n".join(lines)

    # ---------- 确认单（下单前最后一道） ----------
    def confirmation(self, best: PricedPlan) -> str:
        """生成确认单文本；真实模式下用户明确同意后才 create-order。"""
        return (
            f"确认单 —— {best.label}\n"
            f"金额：¥{best.total:.2f}（实价，以下单时 calculate-price 为准）\n"
            f"请在到店/下单前再次核价，确认后我才会下单。"
        )
