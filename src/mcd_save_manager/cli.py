"""命令行入口：python src/main.py "巨无霸+中薯条+中杯可乐" --mode mock

没有 MCD_MCP_TOKEN 时默认走 mock（离线自测）；设了 Token 且 --mode real 时走官方 MCP。
下单 / 领券默认不做 —— 只出最优方案与讲解；确认逻辑在 flow.confirmation。
"""

from __future__ import annotations

import argparse
import sys

from .config import load_config
from .flow import SaveFlow
from .mcp_client import Item, make_client

# 常见菜品名 → productCode（与 mock_data 对齐；真实模式由 query-meals 校准）
_ALIAS = {
    "巨无霸": "100001",
    "中薯条": "100002",
    "中杯可乐": "100003",
    "麦辣鸡翅": "100004",
    "鸡翅": "100004",
    "麦旋风": "100005",
    "冰淇淋": "100005",
}


def _parse_request(text: str) -> list[Item]:
    """把「巨无霸+中薯条+可乐」拆成 Item 列表；无法识别的名字直接报错，不猜测。"""
    items: list[Item] = []
    for chunk in text.replace("，", "+").replace(" ", "").split("+"):
        if not chunk:
            continue
        code = _ALIAS.get(chunk)
        if code is None:
            raise ValueError(f"无法识别的餐品：{chunk}（请在 mock 菜单或 query-meals 结果中选择）")
        items.append(Item(productCode=code, name=chunk, qty=1))
    if not items:
        raise ValueError("没有解析到任何餐品")
    return items


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="麦当劳省钱管家")
    ap.add_argument("request", nargs="?", default="巨无霸+中薯条+中杯可乐",
                    help="想点的餐，用 + 分隔")
    ap.add_argument("--mode", choices=["mock", "real"], default=None,
                    help="real 需设 MCD_MCP_TOKEN；默认有 Token 走 real，否则 mock")
    args = ap.parse_args(argv)

    cfg = load_config(mode=args.mode)
    client = make_client(cfg)
    flow = SaveFlow(client)

    try:
        requested = _parse_request(args.request)
    except ValueError as exc:
        print(f"[输入错误] {exc}")
        return 2

    best = flow.best_plan(requested)
    print(f"运行模式：{cfg.mode}")
    print("--- 最优方案 ---")
    print(flow.explain(best, requested))
    print("--- 确认单 ---")
    print(flow.confirmation(best))
    return 0


if __name__ == "__main__":
    sys.exit(main())
