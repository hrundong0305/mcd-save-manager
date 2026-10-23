"""配置读取。

安全红线：真实 Token 只允许来自环境变量，绝不写入任何仓库文件。
"""

import os
from dataclasses import dataclass

# 官方 MCP 接入点与占位符变量名（与 README / MCP_INTEGRATION 保持一致）
MCD_MCP_URL = "https://mcp.mcd.cn"
MCD_MCP_TOKEN_VAR = "MCD_MCP_TOKEN"


@dataclass
class Config:
    url: str
    token: str  # 环境变量中的真实 Token；缺省为 ""，此时只能走 mock 模式
    mode: str   # "mock" | "real"

    @property
    def has_token(self) -> bool:
        return bool(self.token)


def load_config(mode: str | None = None) -> Config:
    """从环境变量构建配置。mode 未指定时：有 Token 走 real，否则走 mock。"""
    token = os.environ.get(MCD_MCP_TOKEN_VAR, "").strip()
    url = os.environ.get("MCD_MCP_URL", MCD_MCP_URL).strip() or MCD_MCP_URL

    if mode is None:
        mode = "real" if token else "mock"
    if mode not in {"mock", "real"}:
        raise ValueError("mode 只支持 mock / real")

    if mode == "real" and not token:
        raise RuntimeError(
            f"real 模式需要环境变量 {MCD_MCP_TOKEN_VAR}（不要写进任何仓库文件）"
        )
    return Config(url=url, token=token, mode=mode)
