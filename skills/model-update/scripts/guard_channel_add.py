#!/usr/bin/env python3
"""渠道新增守卫：判断是否允许向目标平台"新增渠道"（model-update 技能约束）。

约束：除非用户显式声明，否则不得主动添加 opencode / openrouter 渠道。
本脚本供执行 model-update 技能的 AI 在"新增渠道"前调用，防止违反约束。

用法:
    python3 guard_channel_add.py <channel> [<channel> ...]

输出（退出码 0）:
    OK      全部渠道允许新增
    BLOCKED 存在禁止新增的渠道（标准输出列出）

显式声明放行（任一满足即放行该渠道）:
    1. 环境变量 ALLOW_NO_AUTO_ADD=1（全放行）
    2. ALLOW_NO_AUTO_ADD 为逗号分隔渠道列表（如 opencode,openrouter）——仅放行列表内渠道

判断不区分大小写（渠道名转小写比较）。

注意：本守卫只限制"新增渠道"动作；更新已有渠道的模型不受影响。
"""
from __future__ import annotations

import os
import sys

NO_AUTO_ADD_CHANNELS = ("opencode", "openrouter")


def no_auto_add(channel: str) -> bool:
    """渠道是否禁止主动新增（不区分大小写）。显式声明放行时返回 False。"""
    c = (channel or "").strip().lower()
    if c not in NO_AUTO_ADD_CHANNELS:
        return False
    if os.environ.get("ALLOW_NO_AUTO_ADD") == "1":
        return False
    allow = (os.environ.get("ALLOW_NO_AUTO_ADD") or "").lower().split(",")
    return c not in [a.strip() for a in allow if a.strip()]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("用法: guard_channel_add.py <channel> [<channel> ...]", file=sys.stderr)
        return 2
    blocked = [c for c in argv[1:] if no_auto_add(c)]
    if blocked:
        print("BLOCKED 禁止主动新增渠道: " + ", ".join(blocked)
              + "（默认不添加 opencode/openrouter；如确实需要，请用户显式声明后重试）")
        return 1
    print("OK 全部渠道允许新增")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
