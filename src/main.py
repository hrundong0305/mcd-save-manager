"""麦当劳省钱管家 可运行入口。

用法（在 src/ 目录下）：
  python main.py "巨无霸+中薯条+中杯可乐" --mode mock
  python main.py "巨无霸+中薯条+中杯可乐" --mode real   # 需设 MCD_MCP_TOKEN
"""

import sys

from mcd_save_manager.cli import main

if __name__ == "__main__":
    sys.exit(main())
