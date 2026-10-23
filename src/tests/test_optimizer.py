"""核心优化器单元测试（离线、零依赖，验证验收清单要求）。

运行：cd src && python -m pytest tests/ -q   （或 python tests/test_optimizer.py）
"""

from __future__ import annotations

import unittest

from mcd_save_manager.mcp_client import Combo, Coupon, Item, MockClient
from mcd_save_manager.optimizer import Optimizer

COMBO = Combo(comboCode="C001", name="巨无霸套餐", price=32.0,
              contains={"100001": 1, "100002": 1, "100003": 1})
CPN_WING = Coupon(couponId="CPN001", title="麦辣鸡翅立减3元",
                  boundProductCode="100004", discount=3.0)
CPN_BOGO = Coupon(couponId="CPN002", title="中薯条买一送一",
                  boundProductCode="9900012387", discount=11.5)


class TestOptimizer(unittest.TestCase):
    def setUp(self):
        self.opt = Optimizer(MockClient())

    def test_plain_is_cheapest_without_coupon(self):
        req = [Item("100005", "麦旋风")]
        plans = self.opt.build_plans(req, [COMBO], [CPN_WING, CPN_BOGO])
        best = self.opt.choose_cheapest(plans)
        # 麦旋风没有券可挂，也没有套餐覆盖 → 只能 plain
        self.assertEqual(best.plan.kind, "plain")
        self.assertEqual(best.total, 12.0)

    def test_combo_beats_singles_for_set(self):
        req = [Item("100001", "巨无霸"), Item("100002", "中薯条"),
               Item("100003", "中杯可乐")]
        plans = self.opt.build_plans(req, [COMBO], [CPN_WING, CPN_BOGO])
        best = self.opt.choose_cheapest(plans)
        self.assertEqual(best.plan.kind, "combo")
        self.assertEqual(best.total, 32.0)  # 46.5 单品 vs 32 套餐

    def test_coupon_requires_product_in_cart(self):
        # 券绑定的商品不在购物车 → 不进候选池（红线 3）
        req = [Item("100001", "巨无霸")]
        plans = self.opt.build_plans(req, [COMBO], [CPN_WING, CPN_BOGO])
        kinds = [p.kind for p in plans]
        self.assertNotIn("coupon", kinds)  # 无券可挂

    def test_coupon_applies_when_product_in_cart(self):
        req = [Item("100004", "麦辣鸡翅")]
        plans = self.opt.build_plans(req, [COMBO], [CPN_WING, CPN_BOGO])
        best = self.opt.choose_cheapest(plans)
        self.assertEqual(best.plan.kind, "coupon")
        self.assertEqual(best.total, 10.0)  # 13 - 3

    def test_deterministic_price(self):
        """验收：同场景两次调用报价一致（确定性）。"""
        req = [Item("100001", "巨无霸"), Item("100002", "中薯条"),
               Item("100003", "中杯可乐")]
        p1 = self.opt.choose_cheapest(self.opt.build_plans(req, [COMBO], []))
        p2 = self.opt.choose_cheapest(self.opt.build_plans(req, [COMBO], []))
        self.assertEqual(p1.total, p2.total)

    def test_split_orders_one_coupon_per_order(self):
        """验收：多券 → 正确拆成多张单（红线 4）。"""
        req = [Item("100004", "麦辣鸡翅"), Item("9900012387", "中薯条买一送一")]
        orders = self.opt.split_orders(req, [CPN_WING, CPN_BOGO])
        self.assertEqual(len(orders), 2)
        for order in orders:
            self.assertEqual(len(order), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
