#!/usr/bin/env python3
"""pi → opencode → mimocode 两段流水线（mimocode 的 provider 以 opencode 为准整块覆盖）。

用法:
    python3 scripts/sync-pi-to-mimocode.py
    python3 scripts/sync-pi-to-mimocode.py --dry-run   # 第二段只打印计划

步骤:
    1. sync-pi-to-opencode.py  —— pi 基准合并进 opencode（只增不删 + 限制同步）
    2. sync-opencode-to-mimocode.py  —— 从 opencode 提取 provider，清空并覆盖 mimocode

约定:
    - pi 仍是「哪些渠道/模型」的权威；opencode 是中间汇聚层（含 {env:XXX} 占位符）
    - mimocode 不直接读 pi：provider 子树与 opencode 同构，整块拷贝即可，避免两套映射
    - mimocode 密钥须**明文**：第二段把 `{env:VAR}` / `!echo` 等占位符解析为环境变量实值
    - 任一段失败即中止，不继续第二段
"""
import os
import subprocess
import sys

sys.dont_write_bytecode = True

SCRIPTS = os.path.dirname(os.path.abspath(__file__))


def run(script, *extra):
    cmd = [sys.executable, os.path.join(SCRIPTS, script), *extra]
    print(f'\n=== {script} {" ".join(extra)} ===')
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        sys.exit(f'{script} 失败（exit {proc.returncode}），流水线中止')


def main():
    dry = '--dry-run' in sys.argv[1:]
    # 第一段：pi → opencode（合并式）；dry-run 也真实执行以保证 opencode 为最新基准
    # 若需只演练第二段，直接跑 sync-opencode-to-mimocode.py --dry-run
    run('sync-pi-to-opencode.py')
    run('sync-opencode-to-mimocode.py', *(['--dry-run'] if dry else []))
    print('\n流水线完成：pi → opencode → mimocode')


if __name__ == '__main__':
    main()
